import json
from pathlib import Path

from lssa.schema.events import EventType, ResponseMode, TerminalReasonType
from lssa.tracing.recorder import TraceRecorder
from scripts.summarize_real_pilot import (
    collect_latest_trace_rows,
    main,
    render_markdown,
)


def test_collect_latest_trace_rows_uses_latest_started_trace(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts" / "real_pilot"
    _write_trace(
        artifacts_dir,
        prompt_id="short_text_generation",
        mode="streaming",
        trace_id="older",
        started_at="2026-04-29T00:00:00+00:00",
        ttfb_ms=10,
        streaming=True,
    )
    _write_trace(
        artifacts_dir,
        prompt_id="short_text_generation",
        mode="streaming",
        trace_id="newer",
        started_at="2026-04-29T01:00:00+00:00",
        ttfb_ms=25,
        streaming=True,
    )

    rows = collect_latest_trace_rows(artifacts_dir, "openai_responses")

    assert len(rows) == 1
    assert rows[0].trace_id == "newer"
    assert rows[0].ttfb_ms == 25


def test_render_markdown_excludes_model_content(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts" / "real_pilot"
    _write_trace(
        artifacts_dir,
        prompt_id="short_text_generation",
        mode="streaming",
        trace_id="trace-redacted",
        started_at="2026-04-29T00:00:00+00:00",
        streaming=True,
    )

    rows = collect_latest_trace_rows(artifacts_dir, "openai_responses")
    markdown = render_markdown("openai_responses", rows, artifacts_dir)

    assert "model output text" not in markdown
    assert "Content fields redacted: `yes`" in markdown
    assert "`short_text_generation`" in markdown


def test_collect_latest_trace_rows_rejects_unredacted_content(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts" / "real_pilot"
    _write_trace(
        artifacts_dir,
        prompt_id="short_text_generation",
        mode="streaming",
        trace_id="trace-unredacted",
        started_at="2026-04-29T00:00:00+00:00",
        streaming=True,
        redact_content=False,
    )

    try:
        collect_latest_trace_rows(artifacts_dir, "openai_responses")
    except ValueError as exc:
        assert "unredacted content" in str(exc)
    else:
        raise AssertionError("unredacted trace content should fail summary collection")


def test_summary_cli_writes_and_checks_report(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts" / "real_pilot"
    output = tmp_path / "docs" / "pilot.md"
    _write_trace(
        artifacts_dir,
        prompt_id="short_text_generation",
        mode="nonstreaming",
        trace_id="trace-nonstreaming",
        started_at="2026-04-29T00:00:00+00:00",
        streaming=False,
    )

    assert main(
        [
            "--provider",
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
            "--provider",
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
            "--provider",
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
    prompt_id: str,
    mode: str,
    trace_id: str,
    started_at: str,
    ttfb_ms: float = 10,
    streaming: bool,
    redact_content: bool = True,
) -> Path:
    response_mode = ResponseMode.STREAMING if streaming else ResponseMode.NON_STREAMING
    recorder = TraceRecorder(
        trace_id=trace_id,
        provider_family="OpenAI",
        api_surface="Responses API",
        model="fake-model",
        response_mode=response_mode,
    )
    recorder.append(
        EventType.REQUEST_START,
        timestamp_ms=0,
        monotonic_time_ns=0,
        wall_time_iso=started_at,
    )
    recorder.append(
        EventType.REQUEST_SENT,
        timestamp_ms=1,
        monotonic_time_ns=1,
        wall_time_iso=started_at,
    )
    recorder.append(
        EventType.FIRST_BYTE,
        timestamp_ms=ttfb_ms,
        monotonic_time_ns=int(ttfb_ms),
        wall_time_iso=started_at,
    )
    if streaming:
        recorder.append(
            EventType.FIRST_TOKEN,
            timestamp_ms=ttfb_ms + 5,
            monotonic_time_ns=int(ttfb_ms + 5),
            wall_time_iso=started_at,
            content="model output text",
            char_count=17,
        )
        recorder.append(
            EventType.CHUNK,
            timestamp_ms=ttfb_ms + 6,
            monotonic_time_ns=int(ttfb_ms + 6),
            wall_time_iso=started_at,
            content="model output text",
            char_count=17,
        )
        recorder.append(
            EventType.STREAM_END,
            timestamp_ms=ttfb_ms + 7,
            monotonic_time_ns=int(ttfb_ms + 7),
            wall_time_iso=started_at,
        )
    recorder.append(
        EventType.FINAL_RESPONSE,
        timestamp_ms=ttfb_ms + 8,
        monotonic_time_ns=int(ttfb_ms + 8),
        wall_time_iso=started_at,
        content="model output text",
        char_count=17,
    )
    recorder.append(
        EventType.ITERATOR_END,
        timestamp_ms=ttfb_ms + 9,
        monotonic_time_ns=int(ttfb_ms + 9),
        wall_time_iso=started_at,
    )
    recorder.append(
        EventType.SETTLED,
        timestamp_ms=ttfb_ms + 10,
        monotonic_time_ns=int(ttfb_ms + 10),
        wall_time_iso=started_at,
        terminal_reason=TerminalReasonType.COMPLETE,
    )

    path = artifacts_dir / "openai_responses" / prompt_id / mode / f"{trace_id}.jsonl"
    return recorder.write_jsonl(path, redact_content=redact_content)
