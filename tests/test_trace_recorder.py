import json

from lssa.schema.events import EventType, ResponseMode, TerminalReasonType
from lssa.tracing.recorder import TraceRecorder
from lssa.tracing.validator import validate_trace


def test_trace_recorder_assigns_sequence_indexes_and_metadata() -> None:
    recorder = TraceRecorder(
        provider_family="mock",
        api_surface="mock",
        model="mock-model",
        response_mode=ResponseMode.STREAMING,
    )

    recorder.append(EventType.REQUEST_START, monotonic_time_ns=10, timestamp_ms=0)
    event = recorder.append(
        EventType.REQUEST_SENT,
        monotonic_time_ns=20,
        timestamp_ms=1,
        raw_event_type="mock.request_sent",
        payload_summary="request sent",
    )

    assert [item.sequence_index for item in recorder.events] == [0, 1]
    assert event.metadata["payload_redacted"] is True
    assert event.metadata["raw_event_type"] == "mock.request_sent"


def test_trace_recorder_writes_jsonl_and_summary(tmp_path) -> None:
    recorder = TraceRecorder(
        trace_id="trace-write",
        provider_family="mock",
        api_surface="mock",
        model="mock-model",
        response_mode=ResponseMode.NON_STREAMING,
    )
    recorder.append(EventType.REQUEST_START, timestamp_ms=0, monotonic_time_ns=0)
    recorder.append(EventType.REQUEST_SENT, timestamp_ms=1, monotonic_time_ns=1)
    recorder.append(EventType.FIRST_BYTE, timestamp_ms=2, monotonic_time_ns=2)
    recorder.append(EventType.FINAL_RESPONSE, timestamp_ms=3, monotonic_time_ns=3)
    recorder.append(EventType.ITERATOR_END, timestamp_ms=4, monotonic_time_ns=4)
    recorder.append(
        EventType.SETTLED,
        timestamp_ms=5,
        monotonic_time_ns=5,
        terminal_reason=TerminalReasonType.COMPLETE,
    )

    assert validate_trace(recorder.events).ok

    trace_path = recorder.write_jsonl(tmp_path / "trace.jsonl")
    summary_path = recorder.write_summary_json(tmp_path / "summary.json")

    trace_lines = trace_path.read_text(encoding="utf-8").splitlines()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert len(trace_lines) == 6
    assert json.loads(trace_lines[0])["trace_id"] == "trace-write"
    assert summary["settled"] is True
    assert summary["metadata"]["event_count"] == 6
