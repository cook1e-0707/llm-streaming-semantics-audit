"""Pure metric functions for stream traces."""

from __future__ import annotations

from collections.abc import Iterable

from lssa.schema.events import EventType, SafetySignalType, StreamEvent

_SAFETY_EVENT_TYPES = {
    EventType.SAFETY_ANNOTATION,
    EventType.REFUSAL,
    EventType.CONTENT_FILTER,
}


def time_to_first_byte_ms(events: Iterable[StreamEvent]) -> float | None:
    """Return elapsed milliseconds from request start to first byte."""

    return _elapsed_from_start(events, EventType.FIRST_BYTE)


def time_to_first_token_ms(events: Iterable[StreamEvent]) -> float | None:
    """Return elapsed milliseconds from request start to first token."""

    return _elapsed_from_start(events, EventType.FIRST_TOKEN)


def time_to_first_safety_signal_ms(events: Iterable[StreamEvent]) -> float | None:
    """Return elapsed milliseconds from request start to first safety signal."""

    sorted_events = _sorted_events(events)
    start = _first_event(sorted_events, EventType.REQUEST_START)
    if start is None:
        return None
    safety_event = next((event for event in sorted_events if _is_safety_event(event)), None)
    if safety_event is None:
        return None
    return safety_event.timestamp_ms - start.timestamp_ms


def settlement_lag_ms(events: Iterable[StreamEvent]) -> float | None:
    """Return elapsed milliseconds from last terminal output event to settlement."""

    sorted_events = _sorted_events(events)
    settled = _first_event(sorted_events, EventType.SETTLED)
    if settled is None:
        return None
    terminal_events = [
        event
        for event in sorted_events
        if event.event_type
        in {EventType.STREAM_END, EventType.FINAL_RESPONSE, EventType.ITERATOR_END}
        and event.timestamp_ms <= settled.timestamp_ms
    ]
    if not terminal_events:
        return None
    terminal_event = max(terminal_events, key=lambda event: event.timestamp_ms)
    return settled.timestamp_ms - terminal_event.timestamp_ms


def validation_lag_chars(events: Iterable[StreamEvent]) -> int | None:
    """Return emitted characters beyond the safety event's validation watermark.

    The metric is defined only for traces that carry an explicit
    ``validation_range.end_char`` on a safety event. It does not infer unsafe
    spans from content text.
    """

    sorted_events = _sorted_events(events)
    safety_event = _first_safety_event_with_range(sorted_events)
    if safety_event is None or safety_event.validation_range is None:
        return None
    end_char = safety_event.metadata.get(
        "validation_watermark_char",
        safety_event.validation_range.end_char,
    )
    if end_char is None:
        return None
    end_char = int(end_char)
    emitted = _emitted_chars_before_or_at(sorted_events, safety_event)
    if emitted is None:
        return None
    return max(0, emitted - end_char)


def validation_lag_tokens(events: Iterable[StreamEvent]) -> int | None:
    """Return emitted tokens beyond the safety event's validation watermark."""

    sorted_events = _sorted_events(events)
    safety_event = _first_safety_event_with_range(sorted_events)
    if safety_event is None or safety_event.validation_range is None:
        return None
    end_token = safety_event.metadata.get(
        "validation_watermark_token",
        safety_event.validation_range.end_token,
    )
    if end_token is None:
        return None
    end_token = int(end_token)
    emitted = _emitted_tokens_before_or_at(sorted_events, safety_event)
    if emitted is None:
        return None
    return max(0, emitted - end_token)


def exposure_window_chars(events: Iterable[StreamEvent]) -> int | None:
    """Return explicitly invalidated visible characters, when range labels exist.

    This function intentionally requires trace labels. It returns ``None`` when
    the safety event does not carry a validation range with character offsets.
    """

    safety_event = _first_safety_event_with_range(_sorted_events(events))
    if safety_event is None or safety_event.validation_range is None:
        return None
    start_char = safety_event.validation_range.start_char
    end_char = safety_event.validation_range.end_char
    if start_char is None or end_char is None:
        return None
    return max(0, end_char - start_char)


def exposure_window_tokens(events: Iterable[StreamEvent]) -> int | None:
    """Return explicitly invalidated visible tokens, when range labels exist."""

    safety_event = _first_safety_event_with_range(_sorted_events(events))
    if safety_event is None or safety_event.validation_range is None:
        return None
    start_token = safety_event.validation_range.start_token
    end_token = safety_event.validation_range.end_token
    if start_token is None or end_token is None:
        return None
    return max(0, end_token - start_token)


def exposure_window_ms(events: Iterable[StreamEvent]) -> float | None:
    """Return elapsed time from first covered visible chunk to safety signal.

    The metric is computed only when a safety event carries an explicit
    validation range. It does not inspect raw prompt or output text.
    """

    sorted_events = _sorted_events(events)
    safety_event = _first_safety_event_with_range(sorted_events)
    if safety_event is None or safety_event.validation_range is None:
        return None
    start_char = safety_event.validation_range.start_char
    first_visible = _first_chunk_covering_char(sorted_events, start_char)
    if first_visible is None:
        return None
    return safety_event.timestamp_ms - first_visible.timestamp_ms


def _elapsed_from_start(
    events: Iterable[StreamEvent], target_event_type: EventType
) -> float | None:
    sorted_events = _sorted_events(events)
    start = _first_event(sorted_events, EventType.REQUEST_START)
    target = _first_event(sorted_events, target_event_type)
    if start is None or target is None:
        return None
    return target.timestamp_ms - start.timestamp_ms


def _first_event(
    events: Iterable[StreamEvent], event_type: EventType
) -> StreamEvent | None:
    return next((event for event in events if event.event_type == event_type), None)


def _is_safety_event(event: StreamEvent) -> bool:
    if event.event_type in _SAFETY_EVENT_TYPES:
        return True
    if event.safety_signal is None:
        return False
    return event.safety_signal.signal_type != SafetySignalType.UNKNOWN


def _sorted_events(events: Iterable[StreamEvent]) -> list[StreamEvent]:
    return sorted(events, key=lambda event: (event.timestamp_ms, event.sequence_index))


def _first_safety_event_with_range(events: Iterable[StreamEvent]) -> StreamEvent | None:
    return next(
        (
            event
            for event in events
            if _is_safety_event(event) and event.validation_range is not None
        ),
        None,
    )


def _emitted_chars_before_or_at(
    events: Iterable[StreamEvent],
    boundary: StreamEvent,
) -> int | None:
    total = 0
    observed = False
    for event in events:
        if event.sequence_index > boundary.sequence_index:
            break
        if event.event_type != EventType.CHUNK:
            continue
        if event.char_count is None:
            if event.content is None:
                continue
            total += len(event.content)
        else:
            total += event.char_count
        observed = True
    return total if observed else None


def _emitted_tokens_before_or_at(
    events: Iterable[StreamEvent],
    boundary: StreamEvent,
) -> int | None:
    total = 0
    observed = False
    for event in events:
        if event.sequence_index > boundary.sequence_index:
            break
        if event.event_type != EventType.CHUNK:
            continue
        if event.token_count is None:
            continue
        total += event.token_count
        observed = True
    return total if observed else None


def _first_chunk_covering_char(
    events: Iterable[StreamEvent],
    start_char: int | None,
) -> StreamEvent | None:
    if start_char is None:
        return _first_event(events, EventType.CHUNK)
    total = 0
    for event in events:
        if event.event_type != EventType.CHUNK:
            continue
        chunk_chars = event.char_count
        if chunk_chars is None:
            chunk_chars = len(event.content or "")
        chunk_start = total
        total += chunk_chars
        if chunk_start <= start_char < total:
            return event
    return None
