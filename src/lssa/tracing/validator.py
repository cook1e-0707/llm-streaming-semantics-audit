"""Validation rules for normalized stream traces."""

from __future__ import annotations

from dataclasses import dataclass

from lssa.schema.events import EventType, StreamEvent


@dataclass(frozen=True)
class TraceValidationResult:
    ok: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def validate_trace(events: list[StreamEvent]) -> TraceValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not events:
        return TraceValidationResult(ok=False, errors=("trace has no events",))

    errors.extend(_validate_sequence_indexes(events))
    errors.extend(_validate_monotonic_timestamps(events))
    errors.extend(_validate_required_order(events))
    errors.extend(_validate_terminal_lifecycle(events))

    return TraceValidationResult(
        ok=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def assert_valid_trace(events: list[StreamEvent]) -> None:
    result = validate_trace(events)
    if not result.ok:
        raise ValueError("; ".join(result.errors))


def _validate_sequence_indexes(events: list[StreamEvent]) -> list[str]:
    expected = list(range(len(events)))
    observed = [event.sequence_index for event in events]
    if observed != expected:
        return [f"sequence indexes are not contiguous: {observed}"]
    return []


def _validate_monotonic_timestamps(events: list[StreamEvent]) -> list[str]:
    errors: list[str] = []
    previous_ms = events[0].timestamp_ms
    previous_ns = _monotonic_ns(events[0])
    for event in events[1:]:
        if event.timestamp_ms < previous_ms:
            errors.append(
                f"timestamp_ms decreases at sequence {event.sequence_index}"
            )
        current_ns = _monotonic_ns(event)
        if previous_ns is not None and current_ns is not None and current_ns < previous_ns:
            errors.append(
                f"monotonic_time_ns decreases at sequence {event.sequence_index}"
            )
        previous_ms = event.timestamp_ms
        previous_ns = current_ns if current_ns is not None else previous_ns
    return errors


def _validate_required_order(events: list[StreamEvent]) -> list[str]:
    errors: list[str] = []
    first = _first_indexes(events)

    errors.extend(_requires_before(first, EventType.REQUEST_START, EventType.REQUEST_SENT))
    errors.extend(_requires_before(first, EventType.REQUEST_SENT, EventType.FIRST_BYTE))
    errors.extend(_requires_before(first, EventType.FIRST_BYTE, EventType.FIRST_TOKEN))

    if EventType.CHUNK in first and EventType.FIRST_TOKEN in first:
        if first[EventType.CHUNK] < first[EventType.FIRST_TOKEN]:
            errors.append("chunk appears before first_token")
    elif EventType.CHUNK in first and _has_text_chunk(events):
        errors.append("text chunk appears without first_token")

    if EventType.STREAM_END in first and EventType.REQUEST_SENT in first:
        if first[EventType.STREAM_END] < first[EventType.REQUEST_SENT]:
            errors.append("stream_end appears before request_sent")
    errors.extend(_requires_before(first, EventType.STREAM_END, EventType.ITERATOR_END))
    errors.extend(_requires_before(first, EventType.ITERATOR_END, EventType.SETTLED))
    return errors


def _validate_terminal_lifecycle(events: list[StreamEvent]) -> list[str]:
    errors: list[str] = []
    first = _first_indexes(events)

    if EventType.REQUEST_START not in first:
        errors.append("missing request_start")
    if EventType.REQUEST_SENT not in first:
        errors.append("missing request_sent")
    if EventType.SETTLED not in first:
        errors.append("missing settled")

    for index, event in enumerate(events):
        if event.event_type == EventType.ERROR and not event.metadata.get("recoverable", False):
            later = events[index + 1 :]
            allowed = {EventType.SETTLED}
            if any(later_event.event_type not in allowed for later_event in later):
                errors.append("non-recoverable error is not terminal")

    if EventType.CANCEL in first:
        if EventType.ITERATOR_END not in first:
            errors.append("cancel is not followed by iterator_end")
        if EventType.SETTLED not in first:
            errors.append("cancel is not followed by settled")
        if EventType.ITERATOR_END in first and first[EventType.ITERATOR_END] < first[EventType.CANCEL]:
            errors.append("iterator_end appears before cancel")
        if EventType.SETTLED in first and first[EventType.SETTLED] < first[EventType.CANCEL]:
            errors.append("settled appears before cancel")

    if EventType.SETTLED in first and first[EventType.SETTLED] != len(events) - 1:
        errors.append("settled is not terminal")

    return errors


def _first_indexes(events: list[StreamEvent]) -> dict[EventType, int]:
    first: dict[EventType, int] = {}
    for index, event in enumerate(events):
        first.setdefault(event.event_type, index)
    return first


def _requires_before(
    first: dict[EventType, int],
    earlier: EventType,
    later: EventType,
) -> list[str]:
    if earlier in first and later in first and first[earlier] > first[later]:
        return [f"{earlier.value} appears after {later.value}"]
    return []


def _has_text_chunk(events: list[StreamEvent]) -> bool:
    return any(event.event_type == EventType.CHUNK and event.content for event in events)


def _monotonic_ns(event: StreamEvent) -> int | None:
    value = event.metadata.get("monotonic_time_ns")
    if value is None:
        return None
    return int(value)
