import json
from pathlib import Path

from lssa.schema.events import EventType, Layer, ResponseMode, StreamEvent, TerminalReasonType
from scripts.summarize_p3_run import summarize_run


def test_p3_run_summary_computes_chunk_latency(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    trace_path = (
        run_root
        / "safety_signal"
        / "openai_responses"
        / "prompt-1"
        / "streaming"
        / "trace.jsonl"
    )
    trace_path.parent.mkdir(parents=True)
    events = [
        _event(EventType.REQUEST_START, 0, 0),
        _event(EventType.REQUEST_SENT, 1, 10),
        _event(EventType.FIRST_BYTE, 2, 30),
        _event(EventType.FIRST_TOKEN, 3, 40, char_count=2),
        _event(EventType.CHUNK, 4, 40, char_count=2),
        _event(EventType.CHUNK, 5, 55, char_count=4),
        _event(EventType.CHUNK, 6, 85, char_count=3),
        _event(EventType.STREAM_END, 7, 100),
        _event(
            EventType.FINAL_RESPONSE,
            8,
            101,
            metadata={"provider_stop_reason": "stop"},
        ),
        _event(EventType.ITERATOR_END, 9, 102),
        _event(EventType.SETTLED, 10, 105, terminal_reason=TerminalReasonType.STOP),
    ]
    trace_path.write_text(
        "".join(json.dumps(event.to_dict(), sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )
    judge_dir = run_root / "judge_adjudication"
    judge_dir.mkdir()
    (judge_dir / "judge-a.json").write_text(
        json.dumps({"judge_profile": "a", "label": "unsafe"}),
        encoding="utf-8",
    )

    payload = summarize_run(run_root)

    assert payload["trace_count"] == 1
    assert payload["streaming_trace_count"] == 1
    assert payload["by_provider_mode"] == {"openai_responses:streaming": 1}
    assert payload["provider_stop_reasons"] == {"stop": 1}
    assert payload["trace_terminal_reasons"] == {"stop": 1}
    assert payload["event_terminal_reason_counts"] == {"stop": 1}
    assert payload["terminal_reasons"] == {"stop": 1}
    assert payload["judge_labels"] == {"unsafe": 1}
    assert payload["chunk_latency"]["interarrival_ms"]["count"] == 2
    assert payload["chunk_latency"]["interarrival_ms"]["max"] == 30
    assert payload["chunk_latency"]["first_chunk_after_request_sent_ms"]["p50"] == 30
    assert payload["metrics"]["TTFB_ms"]["p50"] == 30
    assert payload["metrics"]["TTFT_ms"]["p50"] == 40


def _event(
    event_type: EventType,
    sequence_index: int,
    timestamp_ms: float,
    *,
    char_count: int | None = None,
    terminal_reason: TerminalReasonType | None = None,
    metadata: dict[str, object] | None = None,
) -> StreamEvent:
    event_metadata = {
        "monotonic_time_ns": int(timestamp_ms * 1_000_000),
        "wall_time_iso": "2026-04-29T00:00:00+00:00",
    }
    if metadata:
        event_metadata.update(metadata)
    return StreamEvent(
        trace_id="trace-1",
        event_type=event_type,
        layer=Layer.PROVIDER,
        timestamp_ms=timestamp_ms,
        sequence_index=sequence_index,
        char_count=char_count,
        terminal_reason=terminal_reason,
        metadata=event_metadata,
    )
