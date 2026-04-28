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
    """TODO: compute only after traces include validated character watermarks."""

    _consume(events)
    return None


def validation_lag_tokens(events: Iterable[StreamEvent]) -> int | None:
    """TODO: compute only after traces include validated token watermarks."""

    _consume(events)
    return None


def exposure_window_chars(events: Iterable[StreamEvent]) -> int | None:
    """TODO: requires unsafe-span labels and user-visible invalidation ranges."""

    _consume(events)
    return None


def exposure_window_tokens(events: Iterable[StreamEvent]) -> int | None:
    """TODO: requires unsafe-span labels and token-level invalidation ranges."""

    _consume(events)
    return None


def exposure_window_ms(events: Iterable[StreamEvent]) -> float | None:
    """TODO: requires first visibility and later invalidation timestamps."""

    _consume(events)
    return None


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


def _consume(events: Iterable[StreamEvent]) -> None:
    list(events)
