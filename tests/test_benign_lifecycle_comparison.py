from pathlib import Path

from lssa.schema.events import EventType, ResponseMode, TerminalReasonType
from lssa.tracing.recorder import TraceRecorder
from scripts.compare_benign_lifecycle import (
    collect_observations,
    main,
    render_markdown,
)


def test_lifecycle_comparison_renders_without_model_content(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts" / "real_pilot"
    _write_trace(
        artifacts_dir,
        provider="openai_responses",
        prompt_id="short_text_generation",
        mode="streaming",
        streaming=True,
        trace_id="streaming",
    )
    _write_trace(
        artifacts_dir,
        provider="openai_responses",
        prompt_id="short_text_generation",
        mode="nonstreaming",
        streaming=False,
        trace_id="nonstreaming",
    )

    observations = collect_observations(artifacts_dir, ("openai_responses",))
    markdown = render_markdown(observations, artifacts_dir)

    assert "model output text" not in markdown
    assert "Lifecycle Findings" in markdown
    assert "P3 Decision" in markdown
    assert "`stream_end` / `final_response` / `iterator_end` / `settled`" in markdown


def test_lifecycle_comparison_rejects_unredacted_content(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts" / "real_pilot"
    _write_trace(
        artifacts_dir,
        provider="openai_responses",
        prompt_id="short_text_generation",
        mode="streaming",
        streaming=True,
        trace_id="unredacted",
        redact_content=False,
    )

    try:
        collect_observations(artifacts_dir, ("openai_responses",))
    except ValueError as exc:
        assert "unredacted content" in str(exc)
    else:
        raise AssertionError("unredacted content should fail comparison collection")


def test_lifecycle_comparison_cli_writes_and_checks_report(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts" / "real_pilot"
    output = tmp_path / "docs" / "comparison.md"
    _write_trace(
        artifacts_dir,
        provider="openai_responses",
        prompt_id="short_text_generation",
        mode="streaming",
        streaming=True,
        trace_id="streaming",
    )

    assert main(
        [
            "--providers",
            "openai_responses",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(output),
        ]
    ) == 0
    assert output.exists()
    assert main(
        [
            "--providers",
            "openai_responses",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(output),
            "--check",
        ]
    ) == 0

    output.write_text("stale\n", encoding="utf-8")
    assert main(
        [
            "--providers",
            "openai_responses",
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(output),
            "--check",
        ]
    ) == 1


def _write_trace(
    artifacts_dir: Path,
    *,
    provider: str,
    prompt_id: str,
    mode: str,
    streaming: bool,
    trace_id: str,
    redact_content: bool = True,
) -> Path:
    recorder = TraceRecorder(
        trace_id=trace_id,
        provider_family="fake",
        api_surface="fake",
        model="fake-model",
        response_mode=ResponseMode.STREAMING if streaming else ResponseMode.NON_STREAMING,
    )
    recorder.append(
        EventType.REQUEST_START,
        timestamp_ms=0,
        monotonic_time_ns=0,
        wall_time_iso="2026-04-29T00:00:00+00:00",
        raw_event_type="lssa.request_start",
    )
    recorder.append(
        EventType.REQUEST_SENT,
        timestamp_ms=1,
        monotonic_time_ns=1,
        wall_time_iso="2026-04-29T00:00:00+00:00",
        raw_event_type="lssa.request_sent",
    )
    recorder.append(
        EventType.FIRST_BYTE,
        timestamp_ms=10,
        monotonic_time_ns=10,
        wall_time_iso="2026-04-29T00:00:00+00:00",
        raw_event_type="provider.start",
    )
    if streaming:
        recorder.append(
            EventType.FIRST_TOKEN,
            timestamp_ms=12,
            monotonic_time_ns=12,
            wall_time_iso="2026-04-29T00:00:00+00:00",
            raw_event_type="provider.delta",
            content="model output text",
            char_count=17,
        )
        recorder.append(
            EventType.CHUNK,
            timestamp_ms=13,
            monotonic_time_ns=13,
            wall_time_iso="2026-04-29T00:00:00+00:00",
            raw_event_type="provider.delta",
            content="model output text",
            char_count=17,
        )
        recorder.append(
            EventType.STREAM_END,
            timestamp_ms=14,
            monotonic_time_ns=14,
            wall_time_iso="2026-04-29T00:00:00+00:00",
            raw_event_type="provider.stop",
        )
    recorder.append(
        EventType.FINAL_RESPONSE,
        timestamp_ms=15,
        monotonic_time_ns=15,
        wall_time_iso="2026-04-29T00:00:00+00:00",
        raw_event_type="provider.completed",
        content="model output text",
        char_count=17,
    )
    recorder.append(
        EventType.ITERATOR_END,
        timestamp_ms=16,
        monotonic_time_ns=16,
        wall_time_iso="2026-04-29T00:00:00+00:00",
        raw_event_type="lssa.iterator_end",
    )
    recorder.append(
        EventType.SETTLED,
        timestamp_ms=17,
        monotonic_time_ns=17,
        wall_time_iso="2026-04-29T00:00:00+00:00",
        raw_event_type="lssa.settled",
        terminal_reason=TerminalReasonType.COMPLETE,
    )
    path = artifacts_dir / provider / prompt_id / mode / f"{trace_id}.jsonl"
    return recorder.write_jsonl(path, redact_content=redact_content)
