import json
from pathlib import Path

from lssa.schema.events import EventType, ResponseMode, TerminalReasonType
from lssa.tracing.recorder import TraceRecorder
from scripts.audit_p3_results import build_audit_payload, collect_audit_rows, render_markdown


def test_p3_result_audit_counts_safety_and_chunk_latency(tmp_path: Path) -> None:
    run_root = tmp_path / "p3-run"
    run_root.mkdir()
    (run_root / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "p3-run",
                "limit_per_provider_mode": 1,
                "sample_strategy": "stratified",
                "sample_seed": 7,
                "max_output_tokens": 512,
                "judge_responses": True,
                "judge_limit": 0,
            }
        ),
        encoding="utf-8",
    )
    trace_dir = (
        run_root
        / "safety_signal"
        / "openai_responses"
        / "safety-test-1"
        / "streaming"
    )
    recorder = TraceRecorder(
        trace_id="trace-filtered",
        provider_family="OpenAI",
        api_surface="Responses API",
        model="fake-model",
        response_mode=ResponseMode.STREAMING,
    )
    recorder.append(
        EventType.REQUEST_START,
        timestamp_ms=0,
        monotonic_time_ns=0,
        metadata={
            "prompt_id": "safety-test-1",
            "benchmark": "unit_test",
            "category": "redacted_category",
            "source_file": "sample.jsonl",
        },
    )
    recorder.append(EventType.REQUEST_SENT, timestamp_ms=10, monotonic_time_ns=10)
    recorder.append(EventType.FIRST_BYTE, timestamp_ms=20, monotonic_time_ns=20)
    recorder.append(EventType.FIRST_TOKEN, timestamp_ms=30, monotonic_time_ns=30)
    recorder.append(EventType.CHUNK, timestamp_ms=30, monotonic_time_ns=30, content="a", char_count=1)
    recorder.append(EventType.CHUNK, timestamp_ms=40, monotonic_time_ns=40, content="b", char_count=1)
    recorder.append(EventType.STREAM_END, timestamp_ms=50, monotonic_time_ns=50)
    recorder.append(
        EventType.CONTENT_FILTER,
        timestamp_ms=55,
        monotonic_time_ns=55,
        terminal_reason=TerminalReasonType.CONTENT_FILTER,
        metadata={"provider_stop_reason": "content_filtered"},
    )
    recorder.append(
        EventType.FINAL_RESPONSE,
        timestamp_ms=60,
        monotonic_time_ns=60,
        metadata={"provider_stop_reason": "content_filtered"},
    )
    recorder.append(EventType.ITERATOR_END, timestamp_ms=70, monotonic_time_ns=70)
    recorder.append(
        EventType.SETTLED,
        timestamp_ms=80,
        monotonic_time_ns=80,
        terminal_reason=TerminalReasonType.CONTENT_FILTER,
    )
    recorder.write_jsonl(trace_dir / "trace-filtered.jsonl", redact_content=True)

    rows, manifest = collect_audit_rows(run_root)
    payload = build_audit_payload(run_root, rows, manifest)
    markdown = render_markdown(payload)

    assert payload["trace_count"] == 1
    assert payload["manifest"]["sample_strategy"] == "stratified"
    assert payload["safety_signal_event_count"] == 1
    assert payload["TTFSS_ms"]["count"] == 1
    assert payload["stop_reasons_by_provider_mode"]["openai_responses:streaming"] == {
        "content_filtered": 1
    }
    assert payload["content_filter_distribution"]["openai_responses:streaming"] == {
        "unit_test/redacted_category": 1
    }
    assert payload["content_filter_examples"][0]["prompt_id"] == "safety-test-1"
    assert "Chunk Latency By Provider/Mode" in markdown
