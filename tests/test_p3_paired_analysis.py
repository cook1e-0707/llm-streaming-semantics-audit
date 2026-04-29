import json
from pathlib import Path

from lssa.schema.events import EventType, ResponseMode, TerminalReasonType
from lssa.tracing.recorder import TraceRecorder
from scripts.analyze_p3_paired import analyze_run, render_markdown


def test_p3_paired_analysis_aligns_prompt_provider_mode_cells(tmp_path: Path) -> None:
    run_root = tmp_path / "paired-run"
    _write_trace(
        run_root,
        provider="openai_responses",
        mode="streaming",
        prompt_id="prompt-1",
        provider_stop_reason="completed",
        terminal_reason=TerminalReasonType.COMPLETE,
        safety=False,
    )
    _write_trace(
        run_root,
        provider="openai_responses",
        mode="nonstreaming",
        prompt_id="prompt-1",
        provider_stop_reason="completed",
        terminal_reason=TerminalReasonType.COMPLETE,
        safety=False,
    )
    _write_judge(
        run_root,
        provider="openai_responses",
        mode="streaming",
        prompt_id="prompt-1",
        profile="a",
        label="safe",
    )
    _write_judge(
        run_root,
        provider="openai_responses",
        mode="streaming",
        prompt_id="prompt-1",
        profile="b",
        label="unsafe",
    )

    payload = analyze_run(run_root)
    markdown = render_markdown(payload)

    assert payload["prompt_count"] == 1
    assert payload["observed_trace_cells"] == 2
    assert payload["missing_trace_cells"] == []
    assert payload["streaming_nonstreaming_pairs"]["openai_responses"][
        "provider_stop_reason_agree"
    ] == 1
    assert payload["streaming_nonstreaming_pairs"]["openai_responses"][
        "terminal_reason_agree"
    ] == 1
    assert payload["judge_profile_pair_agreement"] == {"disagree": 1}
    assert payload["judge_profile_pair_disagreement_examples"][0]["prompt_id"] == "prompt-1"
    assert "P3 Stratified Safety Paired Analysis" in markdown


def _write_trace(
    run_root: Path,
    *,
    provider: str,
    mode: str,
    prompt_id: str,
    provider_stop_reason: str,
    terminal_reason: TerminalReasonType,
    safety: bool,
) -> None:
    response_mode = (
        ResponseMode.STREAMING if mode == "streaming" else ResponseMode.NON_STREAMING
    )
    recorder = TraceRecorder(
        trace_id=f"trace-{provider}-{mode}-{prompt_id}",
        provider_family=provider,
        api_surface="test",
        model="test-model",
        response_mode=response_mode,
    )
    recorder.append(
        EventType.REQUEST_START,
        timestamp_ms=0,
        monotonic_time_ns=0,
        metadata={
            "prompt_id": prompt_id,
            "benchmark": "unit_test",
            "category": "redacted_category",
            "source_file": "sample.jsonl",
            "mode": mode,
            "model": "test-model",
        },
    )
    recorder.append(EventType.REQUEST_SENT, timestamp_ms=1, monotonic_time_ns=1)
    recorder.append(EventType.FIRST_BYTE, timestamp_ms=10, monotonic_time_ns=10)
    if mode == "streaming":
        recorder.append(EventType.FIRST_TOKEN, timestamp_ms=12, monotonic_time_ns=12, char_count=1)
        recorder.append(EventType.CHUNK, timestamp_ms=12, monotonic_time_ns=12, char_count=1)
        recorder.append(EventType.STREAM_END, timestamp_ms=20, monotonic_time_ns=20)
    if safety:
        recorder.append(
            EventType.CONTENT_FILTER,
            timestamp_ms=21,
            monotonic_time_ns=21,
            terminal_reason=TerminalReasonType.CONTENT_FILTER,
            metadata={"provider_stop_reason": provider_stop_reason},
        )
    recorder.append(
        EventType.FINAL_RESPONSE,
        timestamp_ms=22,
        monotonic_time_ns=22,
        char_count=10,
        metadata={"provider_stop_reason": provider_stop_reason},
    )
    recorder.append(EventType.ITERATOR_END, timestamp_ms=23, monotonic_time_ns=23)
    recorder.append(
        EventType.SETTLED,
        timestamp_ms=24,
        monotonic_time_ns=24,
        terminal_reason=terminal_reason,
    )
    trace_dir = run_root / "safety_signal" / provider / prompt_id / mode
    recorder.write_jsonl(trace_dir / f"{recorder.trace_id}.jsonl", redact_content=True)


def _write_judge(
    run_root: Path,
    *,
    provider: str,
    mode: str,
    prompt_id: str,
    profile: str,
    label: str,
) -> None:
    path = (
        run_root
        / "response_judge"
        / provider
        / prompt_id
        / mode
        / f"response-judge-{profile}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "judge_profile": profile,
                "judge_model": "test-judge",
                "label": label,
                "trace_id": f"trace-{provider}-{mode}-{prompt_id}",
                "raw_provider_output_chars": 10,
                "raw_provider_output_committed": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
