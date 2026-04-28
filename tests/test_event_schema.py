from datetime import datetime, timezone

import pytest

from lssa.schema.events import (
    EventType,
    Layer,
    ReleasePolicy,
    ResponseMode,
    SafetySignal,
    SafetySignalType,
    StreamEvent,
    TerminalReasonType,
    TraceIdentity,
    TraceSummary,
    ValidationRange,
)
from lssa.schema.metrics import (
    exposure_window_chars,
    settlement_lag_ms,
    time_to_first_byte_ms,
    time_to_first_safety_signal_ms,
    time_to_first_token_ms,
)


def test_required_event_type_values_are_present() -> None:
    expected = {
        "request_start",
        "request_sent",
        "first_byte",
        "first_token",
        "chunk",
        "safety_annotation",
        "refusal",
        "content_filter",
        "tool_call_delta",
        "tool_call_commit",
        "stream_end",
        "final_response",
        "iterator_end",
        "settled",
        "cancel",
        "error",
    }

    assert expected <= {event_type.value for event_type in EventType}


def test_trace_summary_serializes_and_round_trips() -> None:
    identity = TraceIdentity(
        trace_id="trace-1",
        provider_family="example",
        provider_model="example-model",
        response_mode=ResponseMode.STREAMING,
        release_policy=ReleasePolicy.IMMEDIATE_STREAMING,
        started_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    signal = SafetySignal(
        signal_type=SafetySignalType.ANNOTATION,
        layer=Layer.PROVIDER,
        category="benign",
    )
    event = StreamEvent(
        trace_id="trace-1",
        event_type=EventType.SAFETY_ANNOTATION,
        layer=Layer.PROVIDER,
        timestamp_ms=10.0,
        sequence_index=1,
        safety_signal=signal,
        validation_range=ValidationRange(start_char=0, end_char=5),
        terminal_reason=TerminalReasonType.COMPLETE,
    )
    summary = TraceSummary(
        identity=identity,
        events=[event],
        terminal_reason=TerminalReasonType.COMPLETE,
        settled=True,
    )

    data = summary.to_dict()
    restored = TraceSummary.from_dict(data)

    assert data["identity"]["response_mode"] == "streaming"
    assert data["events"][0]["safety_signal"]["signal_type"] == "annotation"
    assert restored == summary


def test_stream_event_validates_non_negative_ordering_fields() -> None:
    with pytest.raises(ValueError, match="timestamp_ms"):
        StreamEvent(
            trace_id="trace-1",
            event_type=EventType.REQUEST_START,
            layer=Layer.PROVIDER,
            timestamp_ms=-1.0,
            sequence_index=0,
        )

    with pytest.raises(ValueError, match="sequence_index"):
        StreamEvent(
            trace_id="trace-1",
            event_type=EventType.REQUEST_START,
            layer=Layer.PROVIDER,
            timestamp_ms=0.0,
            sequence_index=-1,
        )


def test_basic_metric_computation_on_synthetic_benign_trace() -> None:
    events = [
        _event(EventType.REQUEST_START, 100.0, 0),
        _event(EventType.REQUEST_SENT, 105.0, 1),
        _event(EventType.FIRST_BYTE, 150.0, 2),
        _event(EventType.FIRST_TOKEN, 175.0, 3),
        _event(EventType.CHUNK, 200.0, 4, content="hello"),
        StreamEvent(
            trace_id="trace-1",
            event_type=EventType.SAFETY_ANNOTATION,
            layer=Layer.PROVIDER,
            timestamp_ms=230.0,
            sequence_index=5,
            safety_signal=SafetySignal(
                signal_type=SafetySignalType.VALIDATION,
                layer=Layer.PROVIDER,
            ),
        ),
        _event(EventType.STREAM_END, 250.0, 6),
        _event(EventType.SETTLED, 280.0, 7),
    ]

    assert time_to_first_byte_ms(events) == 50.0
    assert time_to_first_token_ms(events) == 75.0
    assert time_to_first_safety_signal_ms(events) == 130.0
    assert settlement_lag_ms(events) == 30.0
    assert exposure_window_chars(events) is None


def _event(
    event_type: EventType,
    timestamp_ms: float,
    sequence_index: int,
    content: str | None = None,
) -> StreamEvent:
    return StreamEvent(
        trace_id="trace-1",
        event_type=event_type,
        layer=Layer.PROVIDER,
        timestamp_ms=timestamp_ms,
        sequence_index=sequence_index,
        content=content,
    )
