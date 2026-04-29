#!/usr/bin/env python3
"""Summarize redacted real benign pilot traces into a tracked report."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lssa.schema.events import EventType, StreamEvent
from lssa.schema.metrics import (
    settlement_lag_ms,
    time_to_first_byte_ms,
    time_to_first_token_ms,
)
from lssa.tracing.validator import validate_trace

DEFAULT_ARTIFACTS_DIR = Path("artifacts/real_pilot")
DEFAULT_OUTPUTS = {
    "anthropic_messages": Path("docs/pilot_runs/anthropic_messages_benign_pilot.md"),
    "aws_bedrock_converse": Path("docs/pilot_runs/aws_bedrock_converse_benign_pilot.md"),
    "openai_responses": Path("docs/pilot_runs/openai_responses_benign_pilot.md"),
}
SUPPORTED_PROVIDERS = set(DEFAULT_OUTPUTS)
MODE_ORDER = {"streaming": 0, "nonstreaming": 1}


@dataclass(frozen=True)
class PilotTraceRow:
    provider: str
    prompt_id: str
    mode: str
    model: str
    trace_id: str
    started_at_utc: str
    valid: bool
    validation_errors: tuple[str, ...]
    event_count: int
    chunk_count: int
    final_response_chars: int | None
    ttfb_ms: float | None
    ttft_ms: float | None
    settlement_lag_ms: float | None
    terminal_reason: str
    unredacted_content_events: int
    trace_path: Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=sorted(SUPPORTED_PROVIDERS), required=True)
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS_DIR)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true", help="fail if report is stale")
    args = parser.parse_args(argv)

    output = args.output or DEFAULT_OUTPUTS[args.provider]
    try:
        rows = collect_latest_trace_rows(args.artifacts_dir, args.provider)
        report = render_markdown(args.provider, rows, args.artifacts_dir)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != report:
            print(f"{output} is stale; run python scripts/summarize_real_pilot.py")
            return 1
        print(f"{output} is up to date")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"Wrote {output}")
    return 0


def collect_latest_trace_rows(
    artifacts_dir: Path,
    provider: str,
) -> list[PilotTraceRow]:
    provider_root = artifacts_dir / provider
    if not provider_root.exists():
        raise ValueError(f"missing provider artifacts directory: {provider_root}")

    grouped: dict[tuple[str, str], list[PilotTraceRow]] = {}
    for trace_path in sorted(provider_root.glob("*/*/*.jsonl")):
        prompt_id = trace_path.parent.parent.name
        mode = trace_path.parent.name
        events = _load_events(trace_path)
        row = _row_from_events(
            provider=provider,
            prompt_id=prompt_id,
            mode=mode,
            trace_path=trace_path,
            events=events,
        )
        if row.unredacted_content_events:
            raise ValueError(
                f"trace contains unredacted content fields: {trace_path}"
            )
        grouped.setdefault((prompt_id, mode), []).append(row)

    if not grouped:
        raise ValueError(f"no JSONL traces found under {provider_root}")

    latest_rows = [max(rows, key=_row_sort_key) for rows in grouped.values()]
    return sorted(
        latest_rows,
        key=lambda row: (row.prompt_id, MODE_ORDER.get(row.mode, 99), row.mode),
    )


def render_markdown(
    provider: str,
    rows: list[PilotTraceRow],
    artifacts_dir: Path,
) -> str:
    if not rows:
        raise ValueError("cannot render an empty pilot summary")
    provider_title = _provider_title(provider)
    latest_started = max(row.started_at_utc for row in rows)
    all_valid = all(row.valid for row in rows)
    all_redacted = all(row.unredacted_content_events == 0 for row in rows)

    lines = [
        f"# {provider_title} Benign Pilot Summary",
        "",
        "This report summarizes the latest redacted trace for each benign prompt",
        f"and response mode under `{artifacts_dir / provider}`.",
        "",
        "## Status",
        "",
        "- Phase: P2 real benign pilot result consolidation",
        f"- Provider: `{provider}`",
        f"- Latest trace start: `{latest_started}`",
        f"- Trace validity: `{_yes_no(all_valid)}`",
        f"- Content fields redacted: `{_yes_no(all_redacted)}`",
        "- Provider API calls in this report: historical local artifacts only; this",
        "  script does not call provider APIs.",
        "",
        "## Scope Boundary",
        "",
        "These traces use benign prompts only and validate harness behavior. They do",
        "not support claims about provider safety, refusal behavior, or harmful-content",
        "exposure windows.",
        "",
        "## Latest Trace Summary",
        "",
        "| Prompt | Mode | Model | Valid | Events | Chunks | Final chars | TTFB ms | TTFT ms | Settlement lag ms | Terminal reason |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row.prompt_id}`",
                    f"`{row.mode}`",
                    f"`{row.model}`",
                    _yes_no(row.valid),
                    str(row.event_count),
                    str(row.chunk_count),
                    _format_optional_int(row.final_response_chars),
                    _format_optional_float(row.ttfb_ms),
                    _format_optional_float(row.ttft_ms),
                    _format_optional_float(row.settlement_lag_ms),
                    f"`{row.terminal_reason}`",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `TTFB_ms` is measured from normalized `request_start` to `first_byte`.",
            "- `TTFT_ms` is only defined for streaming traces that emit `first_token`.",
            "- `Final chars` uses normalized character counts and does not require",
            "  retaining model text.",
            "- Artifacts remain under ignored local directories and are not committed.",
            "",
        ]
    )
    return "\n".join(lines)


def _row_from_events(
    *,
    provider: str,
    prompt_id: str,
    mode: str,
    trace_path: Path,
    events: list[StreamEvent],
) -> PilotTraceRow:
    validation = validate_trace(events)
    trace_id = events[0].trace_id if events else "unknown"
    final_response_chars = _final_response_chars(events)
    terminal_reason = _terminal_reason(events)
    return PilotTraceRow(
        provider=provider,
        prompt_id=prompt_id,
        mode=mode,
        trace_id=trace_id,
        model=_model(events),
        started_at_utc=_started_at_utc(events),
        valid=validation.ok,
        validation_errors=validation.errors,
        event_count=len(events),
        chunk_count=sum(event.event_type == EventType.CHUNK for event in events),
        final_response_chars=final_response_chars,
        ttfb_ms=time_to_first_byte_ms(events),
        ttft_ms=time_to_first_token_ms(events),
        settlement_lag_ms=settlement_lag_ms(events),
        terminal_reason=terminal_reason,
        unredacted_content_events=sum(event.content is not None for event in events),
        trace_path=trace_path,
    )


def _load_events(path: Path) -> list[StreamEvent]:
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(StreamEvent.from_dict(json.loads(line)))
    if not events:
        raise ValueError(f"trace has no events: {path}")
    return events


def _started_at_utc(events: list[StreamEvent]) -> str:
    for event in events:
        value = event.metadata.get("wall_time_iso")
        if isinstance(value, str) and value:
            return _normalize_iso_datetime(value)
    return "unknown"


def _model(events: list[StreamEvent]) -> str:
    for event in events:
        value = event.metadata.get("model")
        if isinstance(value, str) and value:
            return value
    return "unknown"


def _normalize_iso_datetime(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _row_sort_key(row: PilotTraceRow) -> tuple[str, str]:
    return (row.started_at_utc, row.trace_path.name)


def _final_response_chars(events: list[StreamEvent]) -> int | None:
    for event in reversed(events):
        if event.event_type == EventType.FINAL_RESPONSE:
            return event.char_count
    return None


def _terminal_reason(events: list[StreamEvent]) -> str:
    for event in reversed(events):
        if event.terminal_reason is not None:
            return event.terminal_reason.value
    return "unknown"


def _provider_title(provider: str) -> str:
    if provider == "anthropic_messages":
        return "Anthropic Messages"
    if provider == "aws_bedrock_converse":
        return "AWS Bedrock Converse"
    if provider == "openai_responses":
        return "OpenAI Responses"
    return provider


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _format_optional_float(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _format_optional_int(value: int | None) -> str:
    return "n/a" if value is None else str(value)


if __name__ == "__main__":
    sys.exit(main())
