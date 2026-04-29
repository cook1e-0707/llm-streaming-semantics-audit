#!/usr/bin/env python3
"""Write a redacted Phase 3 result-audit report."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lssa.schema.events import EventType, ResponseMode, StreamEvent
from lssa.schema.metrics import time_to_first_safety_signal_ms

DEFAULT_RUNS_ROOT = ROOT / "artifacts" / "p3_overnight"
LENGTH_STOP_REASONS = {"length", "max_output_tokens", "max_tokens"}


@dataclass(frozen=True)
class TraceAuditRow:
    provider: str
    mode: str
    prompt_id: str
    trace_id: str
    terminal_reason: str
    provider_stop_reason: str
    category: str
    benchmark: str
    source_file: str
    safety_event_types: tuple[str, ...]
    ttfss_ms: float | None
    first_chunk_after_request_sent_ms: float | None
    interarrival_ms: tuple[float, ...]
    streaming_duration_ms: float | None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        run_root = args.run_root or _latest_run_root(DEFAULT_RUNS_ROOT)
        rows, manifest = collect_audit_rows(run_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    payload = build_audit_payload(run_root, rows, manifest)
    output_path = args.output or (run_root / "p3_result_audit.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if args.json:
        json_path = output_path.with_suffix(".json")
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        output_path.write_text(render_markdown(payload), encoding="utf-8")
        print(f"p3_audit run_root={run_root} traces={len(rows)} output={output_path}")
    return 0


def collect_audit_rows(run_root: Path) -> tuple[list[TraceAuditRow], dict[str, Any]]:
    if not run_root.exists():
        raise ValueError(f"run root does not exist: {run_root}")
    manifest_path = run_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    rows = []
    for path in sorted((run_root / "safety_signal").rglob("*.jsonl")):
        events = _load_events(path)
        if not events:
            continue
        provider = _provider_for_path(path)
        mode = _response_mode_for_path(path).value
        request_metadata = _request_metadata(events)
        chunks = [event for event in events if event.event_type == EventType.CHUNK]
        request_sent = _first_event(events, EventType.REQUEST_SENT)
        stream_end = _first_event(events, EventType.STREAM_END)
        first_chunk_after_request_sent_ms = None
        if request_sent is not None and chunks:
            first_chunk_after_request_sent_ms = chunks[0].timestamp_ms - request_sent.timestamp_ms
        streaming_duration_ms = None
        if stream_end is not None and chunks:
            streaming_duration_ms = stream_end.timestamp_ms - chunks[0].timestamp_ms
        rows.append(
            TraceAuditRow(
                provider=provider,
                mode=mode,
                prompt_id=str(request_metadata.get("prompt_id") or _prompt_id_for_path(path)),
                trace_id=events[0].trace_id,
                terminal_reason=_terminal_reason(events),
                provider_stop_reason=_provider_stop_reason(events),
                category=str(request_metadata.get("category") or "unknown"),
                benchmark=str(request_metadata.get("benchmark") or "unknown"),
                source_file=str(request_metadata.get("source_file") or "unknown"),
                safety_event_types=tuple(
                    event.event_type.value
                    for event in events
                    if event.event_type
                    in {EventType.SAFETY_ANNOTATION, EventType.REFUSAL, EventType.CONTENT_FILTER}
                ),
                ttfss_ms=time_to_first_safety_signal_ms(events),
                first_chunk_after_request_sent_ms=first_chunk_after_request_sent_ms,
                interarrival_ms=tuple(
                    current.timestamp_ms - previous.timestamp_ms
                    for previous, current in zip(chunks, chunks[1:])
                ),
                streaming_duration_ms=streaming_duration_ms,
            )
        )
    return rows, manifest


def build_audit_payload(
    run_root: Path,
    rows: list[TraceAuditRow],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    stop_by_provider_mode: dict[str, Counter[str]] = defaultdict(Counter)
    terminal_by_provider_mode: dict[str, Counter[str]] = defaultdict(Counter)
    content_filter_distribution: dict[str, Counter[str]] = defaultdict(Counter)
    unknown_rows: list[dict[str, str]] = []
    length_rows: list[dict[str, str]] = []
    ttfss_values = []
    safety_event_types: Counter[str] = Counter()
    first_chunk_by_provider_mode: dict[str, list[float]] = defaultdict(list)
    interarrival_by_provider_mode: dict[str, list[float]] = defaultdict(list)
    streaming_duration_by_provider_mode: dict[str, list[float]] = defaultdict(list)

    for row in rows:
        key = f"{row.provider}:{row.mode}"
        stop_by_provider_mode[key][row.provider_stop_reason] += 1
        terminal_by_provider_mode[key][row.terminal_reason] += 1
        for event_type in row.safety_event_types:
            safety_event_types[event_type] += 1
        if row.ttfss_ms is not None:
            ttfss_values.append(row.ttfss_ms)
        if row.provider_stop_reason in {"content_filter", "content_filtered", "guardrail_intervened"}:
            content_filter_distribution[key][f"{row.benchmark}/{row.category}"] += 1
        if row.provider_stop_reason in LENGTH_STOP_REASONS or row.terminal_reason == "length":
            length_rows.append(_row_reference(row))
        if row.provider_stop_reason == "unknown" or row.terminal_reason == "unknown":
            unknown_rows.append(_row_reference(row))
        if row.first_chunk_after_request_sent_ms is not None:
            first_chunk_by_provider_mode[key].append(row.first_chunk_after_request_sent_ms)
        interarrival_by_provider_mode[key].extend(row.interarrival_ms)
        if row.streaming_duration_ms is not None:
            streaming_duration_by_provider_mode[key].append(row.streaming_duration_ms)

    return {
        "run_root": str(run_root),
        "raw_text_committed": False,
        "trace_count": len(rows),
        "manifest": {
            "run_id": manifest.get("run_id", run_root.name),
            "limit_per_provider_mode": manifest.get("limit_per_provider_mode"),
            "sample_strategy": manifest.get("sample_strategy", "unknown"),
            "sample_seed": manifest.get("sample_seed", "unknown"),
            "max_output_tokens": manifest.get("max_output_tokens"),
            "judge_responses": manifest.get("judge_responses"),
            "judge_limit": manifest.get("judge_limit"),
        },
        "stop_reasons_by_provider_mode": _counter_mapping(stop_by_provider_mode),
        "terminal_reasons_by_provider_mode": _counter_mapping(terminal_by_provider_mode),
        "content_filter_distribution": _counter_mapping(content_filter_distribution),
        "length_trace_count": len(length_rows),
        "length_trace_examples": length_rows[:20],
        "unknown_trace_count": len(unknown_rows),
        "unknown_trace_examples": unknown_rows[:20],
        "safety_signal_event_count": sum(safety_event_types.values()),
        "safety_signal_event_types": dict(sorted(safety_event_types.items())),
        "TTFSS_ms": _aggregate(ttfss_values),
        "chunk_latency_by_provider_mode": {
            key: {
                "first_chunk_after_request_sent_ms": _aggregate(first_chunk_by_provider_mode[key]),
                "interarrival_ms": _aggregate(interarrival_by_provider_mode[key]),
                "streaming_duration_ms": _aggregate(streaming_duration_by_provider_mode[key]),
            }
            for key in sorted(
                set(first_chunk_by_provider_mode)
                | set(interarrival_by_provider_mode)
                | set(streaming_duration_by_provider_mode)
            )
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Phase 3 Result Audit",
        "",
        "This audit is redacted. It uses trace metadata and normalized events, not raw prompt text or raw provider output.",
        "",
        f"- Run root: `{payload['run_root']}`",
        f"- Trace count: {payload['trace_count']}",
        f"- Sample strategy: `{payload['manifest']['sample_strategy']}`",
        f"- Max output tokens: `{payload['manifest']['max_output_tokens']}`",
        f"- Safety-signal event count: {payload['safety_signal_event_count']}",
        f"- TTFSS count: {payload['TTFSS_ms']['count']}",
        "",
        "## Provider Stop Reasons",
        "",
        _render_counter_table(payload["stop_reasons_by_provider_mode"], "provider_mode"),
        "",
        "## Terminal Reasons",
        "",
        _render_counter_table(payload["terminal_reasons_by_provider_mode"], "provider_mode"),
        "",
        "## Content Filter Distribution",
        "",
        _render_counter_table(payload["content_filter_distribution"], "provider_mode"),
        "",
        "## Length Stop Audit",
        "",
        f"- Length-like trace count: {payload['length_trace_count']}",
        "- Interpretation: a length-like stop reason is consistent with the configured output-token cap, but this audit does not infer model intent.",
        "",
        _render_reference_table(payload["length_trace_examples"]),
        "",
        "## Unknown Stop Audit",
        "",
        f"- Unknown trace count: {payload['unknown_trace_count']}",
        "- Interpretation: unknown means the adapter did not observe a provider stop reason or terminal reason in the mapped events.",
        "",
        _render_reference_table(payload["unknown_trace_examples"]),
        "",
        "## Chunk Latency By Provider/Mode",
        "",
        _render_latency_table(payload["chunk_latency_by_provider_mode"]),
        "",
    ]
    return "\n".join(lines)


def _latest_run_root(runs_root: Path) -> Path:
    candidates = sorted(path for path in runs_root.iterdir() if path.is_dir())
    if not candidates:
        raise ValueError(f"no P3 run directories under {runs_root}")
    return candidates[-1]


def _load_events(path: Path) -> list[StreamEvent]:
    events: list[StreamEvent] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                events.append(StreamEvent.from_dict(json.loads(line)))
    return events


def _request_metadata(events: list[StreamEvent]) -> dict[str, Any]:
    request_start = _first_event(events, EventType.REQUEST_START)
    return dict(request_start.metadata) if request_start is not None else {}


def _provider_stop_reason(events: list[StreamEvent]) -> str:
    for event in reversed(events):
        value = event.metadata.get("provider_stop_reason")
        if isinstance(value, str) and value:
            return value
    return "unknown"


def _terminal_reason(events: list[StreamEvent]) -> str:
    for event in reversed(events):
        if event.terminal_reason is not None:
            return event.terminal_reason.value
    return "unknown"


def _first_event(events: list[StreamEvent], event_type: EventType) -> StreamEvent | None:
    return next((event for event in events if event.event_type == event_type), None)


def _response_mode_for_path(path: Path) -> ResponseMode:
    parts = path.parts
    if "streaming" in parts:
        return ResponseMode.STREAMING
    if "nonstreaming" in parts:
        return ResponseMode.NON_STREAMING
    return ResponseMode.UNKNOWN


def _provider_for_path(path: Path) -> str:
    parts = path.parts
    try:
        index = parts.index("safety_signal")
    except ValueError:
        return "unknown"
    return parts[index + 1] if index + 1 < len(parts) else "unknown"


def _prompt_id_for_path(path: Path) -> str:
    parts = path.parts
    try:
        index = parts.index("safety_signal")
    except ValueError:
        return "unknown"
    return parts[index + 2] if index + 2 < len(parts) else "unknown"


def _row_reference(row: TraceAuditRow) -> dict[str, str]:
    return {
        "provider": row.provider,
        "mode": row.mode,
        "prompt_id": row.prompt_id,
        "trace_id": row.trace_id,
        "provider_stop_reason": row.provider_stop_reason,
        "terminal_reason": row.terminal_reason,
        "benchmark": row.benchmark,
        "category": row.category,
        "source_file": row.source_file,
    }


def _counter_mapping(mapping: dict[str, Counter[str]]) -> dict[str, dict[str, int]]:
    return {key: dict(sorted(counter.items())) for key, counter in sorted(mapping.items())}


def _aggregate(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "mean": None, "p50": None, "p95": None, "max": None}
    sorted_values = sorted(values)
    return {
        "count": len(sorted_values),
        "mean": mean(sorted_values),
        "p50": _percentile(sorted_values, 0.50),
        "p95": _percentile(sorted_values, 0.95),
        "max": sorted_values[-1],
    }


def _percentile(sorted_values: list[float], quantile: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = round((len(sorted_values) - 1) * quantile)
    return sorted_values[index]


def _render_counter_table(mapping: dict[str, dict[str, int]], key_label: str) -> str:
    if not mapping:
        return "_No matching records._"
    lines = [f"| {key_label} | value | count |", "| --- | --- | ---: |"]
    for key, counter in mapping.items():
        for value, count in counter.items():
            lines.append(f"| `{key}` | `{value}` | {count} |")
    return "\n".join(lines)


def _render_reference_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "_No matching records._"
    lines = [
        "| provider | mode | prompt_id | provider_stop_reason | terminal_reason | benchmark | category |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['provider']}` | `{row['mode']}` | `{row['prompt_id']}` | "
            f"`{row['provider_stop_reason']}` | `{row['terminal_reason']}` | "
            f"`{row['benchmark']}` | `{row['category']}` |"
        )
    return "\n".join(lines)


def _render_latency_table(mapping: dict[str, dict[str, dict[str, float | int | None]]]) -> str:
    if not mapping:
        return "_No streaming chunk latency records._"
    lines = [
        "| provider_mode | metric | count | p50_ms | p95_ms | max_ms |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for key, metrics in mapping.items():
        for metric_name, aggregate in metrics.items():
            lines.append(
                f"| `{key}` | `{metric_name}` | {aggregate['count']} | "
                f"{_fmt(aggregate['p50'])} | {_fmt(aggregate['p95'])} | {_fmt(aggregate['max'])} |"
            )
    return "\n".join(lines)


def _fmt(value: float | int | None) -> str:
    if value is None:
        return ""
    return f"{float(value):.3f}"


if __name__ == "__main__":
    sys.exit(main())
