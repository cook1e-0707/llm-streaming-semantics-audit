from dataclasses import replace

from lssa.schema.events import EventType, ValidationRange
from lssa.tracing.fixtures import benign_streaming_trace, make_event, reindex_events
from lssa.tracing.validator import validate_trace


def test_trace_validator_accepts_valid_streaming_trace() -> None:
    result = validate_trace(benign_streaming_trace())

    assert result.ok, result.errors


def test_trace_validator_rejects_non_contiguous_sequence_indexes() -> None:
    events = benign_streaming_trace()
    events[3] = replace(events[3], sequence_index=99)

    result = validate_trace(events)

    assert not result.ok
    assert any("sequence indexes" in error for error in result.errors)


def test_trace_validator_rejects_decreasing_monotonic_timestamp() -> None:
    events = benign_streaming_trace()
    bad_metadata = dict(events[4].metadata)
    bad_metadata["monotonic_time_ns"] = 1
    events[4] = replace(events[4], metadata=bad_metadata)

    result = validate_trace(events)

    assert not result.ok
    assert any("monotonic_time_ns decreases" in error for error in result.errors)


def test_trace_validator_rejects_chunk_before_first_token() -> None:
    events = [
        make_event(EventType.REQUEST_START, 0),
        make_event(EventType.REQUEST_SENT, 1),
        make_event(EventType.FIRST_BYTE, 2),
        make_event(EventType.CHUNK, 3, content="too early"),
        make_event(EventType.FIRST_TOKEN, 4, content="late"),
        make_event(EventType.STREAM_END, 5),
        make_event(EventType.ITERATOR_END, 6),
        make_event(EventType.SETTLED, 7),
    ]

    result = validate_trace(events)

    assert not result.ok
    assert any("chunk appears before first_token" in error for error in result.errors)


def test_trace_validator_rejects_non_recoverable_error_with_later_content() -> None:
    events = [
        make_event(EventType.REQUEST_START, 0),
        make_event(EventType.REQUEST_SENT, 1),
        make_event(EventType.FIRST_BYTE, 2),
        make_event(EventType.ERROR, 3, recoverable=False),
        make_event(EventType.CHUNK, 4, content="bad"),
        make_event(EventType.SETTLED, 5),
    ]

    result = validate_trace(events)

    assert not result.ok
    assert any("error is not terminal" in error for error in result.errors)


def test_trace_validator_rejects_cancel_without_cleanup() -> None:
    events = reindex_events(
        [
            make_event(EventType.REQUEST_START, 0),
            make_event(EventType.REQUEST_SENT, 1),
            make_event(EventType.FIRST_BYTE, 2),
            make_event(EventType.CANCEL, 3),
            make_event(EventType.SETTLED, 4),
        ]
    )

    result = validate_trace(events)

    assert not result.ok
    assert any("cancel is not followed by iterator_end" in error for error in result.errors)


def test_trace_validator_rejects_decreasing_validation_range() -> None:
    events = benign_streaming_trace()
    events.insert(
        6,
        make_event(EventType.SAFETY_ANNOTATION, 6, timestamp_ms=55),
    )
    events = reindex_events(events)
    events[6] = replace(
        events[6],
        validation_range=ValidationRange(start_char=10, end_char=5),
    )

    result = validate_trace(events)

    assert not result.ok
    assert any("validation_range char offsets decrease" in error for error in result.errors)


def test_trace_validator_rejects_future_validation_watermark() -> None:
    events = benign_streaming_trace()
    events.insert(
        6,
        make_event(EventType.SAFETY_ANNOTATION, 6, timestamp_ms=55),
    )
    events = reindex_events(events)
    events[6] = replace(
        events[6],
        validation_range=ValidationRange(start_char=0, end_char=5, watermark_event_index=99),
    )

    result = validate_trace(events)

    assert not result.ok
    assert any("validation watermark points to a future event" in error for error in result.errors)
