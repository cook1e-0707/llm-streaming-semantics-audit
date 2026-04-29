#!/usr/bin/env python3
"""Generate paired Phase 3 analysis over prompt_id x provider x mode cells."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lssa.schema.events import EventType, StreamEvent
from lssa.schema.metrics import (
    settlement_lag_ms,
    time_to_first_byte_ms,
    time_to_first_safety_signal_ms,
    time_to_first_token_ms,
)

DEFAULT_RUNS_ROOT = ROOT / "artifacts" / "p3_overnight"
DEFAULT_PROVIDERS = ("openai_responses", "anthropic_messages", "aws_bedrock_converse")
DEFAULT_MODES = ("streaming", "nonstreaming")


@dataclass
class TraceCell:
    sample_id: str
    prompt_id: str
    provider: str
    mode: str
    trace_id: str
    benchmark: str = "unknown"
    category: str = "unknown"
    source_file: str = "unknown"
    source_line: str = "unknown"
    model: str = "unknown"
    provider_stop_reason: str = "unknown"
    terminal_reason: str = "unknown"
    final_response_present: bool = False
    final_response_chars: int | None = None
    chunk_count: int = 0
    safety_signal_count: int = 0
    safety_event_types: tuple[str, ...] = ()
    ttfb_ms: float | None = None
    ttft_ms: float | None = None
    ttfss_ms: float | None = None
    settlement_lag_ms: float | None = None
    judge_labels: dict[str, str] = field(default_factory=dict)
    judge_output_chars: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "prompt_id": self.prompt_id,
            "provider": self.provider,
            "mode": self.mode,
            "trace_id": self.trace_id,
            "benchmark": self.benchmark,
            "category": self.category,
            "source_file": self.source_file,
            "source_line": self.source_line,
            "model": self.model,
            "provider_stop_reason": self.provider_stop_reason,
            "terminal_reason": self.terminal_reason,
            "final_response_present": self.final_response_present,
            "final_response_chars": self.final_response_chars,
            "chunk_count": self.chunk_count,
            "safety_signal_count": self.safety_signal_count,
            "safety_event_types": list(self.safety_event_types),
            "TTFB_ms": self.ttfb_ms,
            "TTFT_ms": self.ttft_ms,
            "TTFSS_ms": self.ttfss_ms,
            "settlement_lag_ms": self.settlement_lag_ms,
            "judge_labels": dict(sorted(self.judge_labels.items())),
            "judge_output_chars": self.judge_output_chars,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        run_root = args.run_root or _latest_run_root(DEFAULT_RUNS_ROOT)
        payload = analyze_run(run_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output_path = args.output or (run_root / "p3_paired_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    markdown_path = args.markdown
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(payload), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"p3_paired_analysis run_root={run_root} samples={payload['sample_count']} "
            f"unique_prompt_ids={payload['prompt_count']} "
            f"observed_cells={payload['observed_trace_cells']} output={output_path}"
        )
        if markdown_path is not None:
            print(f"p3_paired_markdown output={markdown_path}")
    return 0


def analyze_run(run_root: Path) -> dict[str, Any]:
    if not run_root.exists():
        raise ValueError(f"run root does not exist: {run_root}")
    cells = collect_trace_cells(run_root)
    attach_response_judges(cells, run_root)
    samples = sorted({cell.sample_id for cell in cells.values()})
    providers = sorted({provider for _, provider, _ in cells} or DEFAULT_PROVIDERS)
    modes = sorted({mode for _, _, mode in cells} or DEFAULT_MODES)
    expected_cells = len(samples) * len(providers) * len(modes)
    missing_cells = [
        {"sample_id": sample_id, "provider": provider, "mode": mode}
        for sample_id in samples
        for provider in providers
        for mode in modes
        if (sample_id, provider, mode) not in cells
    ]

    by_provider_mode = Counter(f"{cell.provider}:{cell.mode}" for cell in cells.values())
    stop_by_provider_mode: dict[str, Counter[str]] = defaultdict(Counter)
    terminal_by_provider_mode: dict[str, Counter[str]] = defaultdict(Counter)
    final_response_by_provider_mode: dict[str, Counter[str]] = defaultdict(Counter)
    safety_signal_by_provider_mode: dict[str, Counter[str]] = defaultdict(Counter)
    metric_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    judge_profile_labels: dict[str, Counter[str]] = defaultdict(Counter)
    judge_pair = Counter()
    judge_pair_examples: list[dict[str, Any]] = []

    for cell in cells.values():
        key = f"{cell.provider}:{cell.mode}"
        stop_by_provider_mode[key][cell.provider_stop_reason] += 1
        terminal_by_provider_mode[key][cell.terminal_reason] += 1
        final_response_by_provider_mode[key][str(cell.final_response_present)] += 1
        safety_signal_by_provider_mode[key][str(cell.safety_signal_count > 0)] += 1
        _record_optional(metric_values[key]["TTFB_ms"], cell.ttfb_ms)
        _record_optional(metric_values[key]["TTFT_ms"], cell.ttft_ms)
        _record_optional(metric_values[key]["TTFSS_ms"], cell.ttfss_ms)
        _record_optional(metric_values[key]["settlement_lag_ms"], cell.settlement_lag_ms)
        for profile, label in cell.judge_labels.items():
            judge_profile_labels[profile][label] += 1
        if "a" in cell.judge_labels and "b" in cell.judge_labels:
            labels = (cell.judge_labels["a"], cell.judge_labels["b"])
            if labels[0] == labels[1]:
                judge_pair["agree"] += 1
            else:
                judge_pair["disagree"] += 1
                if len(judge_pair_examples) < 30:
                    judge_pair_examples.append(
                        {
                            "prompt_id": cell.prompt_id,
                            "sample_id": cell.sample_id,
                            "provider": cell.provider,
                            "mode": cell.mode,
                            "judge_a": labels[0],
                            "judge_b": labels[1],
                            "provider_stop_reason": cell.provider_stop_reason,
                            "terminal_reason": cell.terminal_reason,
                            "benchmark": cell.benchmark,
                            "category": cell.category,
                        }
                    )

    return {
        "run_root": str(run_root),
        "raw_text_committed": False,
        "sample_count": len(samples),
        "prompt_count": len({cell.prompt_id for cell in cells.values()}),
        "providers": providers,
        "modes": modes,
        "expected_trace_cells": expected_cells,
        "observed_trace_cells": len(cells),
        "missing_trace_cells": missing_cells,
        "by_provider_mode": dict(sorted(by_provider_mode.items())),
        "provider_stop_reasons_by_provider_mode": _counter_mapping(stop_by_provider_mode),
        "trace_terminal_reasons_by_provider_mode": _counter_mapping(terminal_by_provider_mode),
        "final_response_present_by_provider_mode": _counter_mapping(final_response_by_provider_mode),
        "safety_signal_present_by_provider_mode": _counter_mapping(safety_signal_by_provider_mode),
        "metrics_by_provider_mode": {
            key: {name: _aggregate(values) for name, values in sorted(metrics.items())}
            for key, metrics in sorted(metric_values.items())
        },
        "streaming_nonstreaming_pairs": _streaming_nonstreaming_pairs(cells, samples, providers),
        "judge_profile_labels": _counter_mapping(judge_profile_labels),
        "judge_profile_pair_agreement": dict(sorted(judge_pair.items())),
        "judge_profile_pair_disagreement_examples": judge_pair_examples,
        "paired_records": [
            _paired_record(sample_id, providers, modes, cells) for sample_id in samples
        ],
    }


def collect_trace_cells(run_root: Path) -> dict[tuple[str, str, str], TraceCell]:
    cells: dict[tuple[str, str, str], TraceCell] = {}
    for path in sorted((run_root / "safety_signal").rglob("*.jsonl")):
        events = _load_events(path)
        if not events:
            continue
        provider, path_prompt_id, mode = _trace_path_parts(path)
        request_metadata = _request_metadata(events)
        prompt_id = str(request_metadata.get("prompt_id") or path_prompt_id)
        source_file = str(request_metadata.get("source_file") or "unknown")
        source_line = str(request_metadata.get("source_line") or "unknown")
        sample_id = _sample_id(source_file, source_line, prompt_id)
        model = str(request_metadata.get("model") or _first_model(events))
        final_response = _first_event(events, EventType.FINAL_RESPONSE)
        safety_events = [
            event
            for event in events
            if event.event_type
            in {EventType.SAFETY_ANNOTATION, EventType.REFUSAL, EventType.CONTENT_FILTER}
            or event.safety_signal is not None
        ]
        cell = TraceCell(
            sample_id=sample_id,
            prompt_id=prompt_id,
            provider=provider,
            mode=mode,
            trace_id=events[0].trace_id,
            benchmark=str(request_metadata.get("benchmark") or "unknown"),
            category=str(request_metadata.get("category") or "unknown"),
            source_file=source_file,
            source_line=source_line,
            model=model,
            provider_stop_reason=_provider_stop_reason(events),
            terminal_reason=_trace_terminal_reason(events),
            final_response_present=final_response is not None,
            final_response_chars=final_response.char_count if final_response is not None else None,
            chunk_count=sum(1 for event in events if event.event_type == EventType.CHUNK),
            safety_signal_count=len(safety_events),
            safety_event_types=tuple(event.event_type.value for event in safety_events),
            ttfb_ms=time_to_first_byte_ms(events),
            ttft_ms=time_to_first_token_ms(events),
            ttfss_ms=time_to_first_safety_signal_ms(events),
            settlement_lag_ms=settlement_lag_ms(events),
        )
        cells[(sample_id, provider, mode)] = cell
    return cells


def attach_response_judges(
    cells: dict[tuple[str, str, str], TraceCell],
    run_root: Path,
) -> None:
    by_trace_id = {cell.trace_id: cell for cell in cells.values()}
    for path in sorted((run_root / "response_judge").rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        trace_id = payload.get("trace_id")
        cell = by_trace_id.get(str(trace_id)) if trace_id is not None else None
        if cell is None:
            provider, prompt_id, mode = _judge_path_parts(path)
            source_file = str(payload.get("source_file") or "unknown")
            source_line = str(payload.get("source_line") or "unknown")
            cell = cells.get((_sample_id(source_file, source_line, prompt_id), provider, mode))
        if cell is None:
            continue
        profile = str(payload.get("judge_profile") or "unknown")
        label = str(payload.get("label") or "unknown")
        cell.judge_labels[profile] = label
        output_chars = payload.get("raw_provider_output_chars")
        if isinstance(output_chars, int):
            cell.judge_output_chars = output_chars


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# P3 Stratified Safety Paired Analysis",
        "",
        "This report is redacted. It analyzes normalized trace metadata and judge labels only.",
        "",
        f"- Run root: `{payload['run_root']}`",
        f"- Sample count: {payload['sample_count']}",
        f"- Unique prompt_id count: {payload['prompt_count']}",
        f"- Observed trace cells: {payload['observed_trace_cells']} / {payload['expected_trace_cells']}",
        f"- Missing trace cells: {len(payload['missing_trace_cells'])}",
        "",
        "## Provider/Mode Coverage",
        "",
        _render_counter(payload["by_provider_mode"], "provider_mode"),
        "",
        "## Trace Terminal Reasons",
        "",
        _render_nested_counter(payload["trace_terminal_reasons_by_provider_mode"], "provider_mode"),
        "",
        "## Provider Stop Reasons",
        "",
        _render_nested_counter(payload["provider_stop_reasons_by_provider_mode"], "provider_mode"),
        "",
        "## Safety Signal Presence",
        "",
        _render_nested_counter(payload["safety_signal_present_by_provider_mode"], "provider_mode"),
        "",
        "## Streaming Vs Nonstreaming Pairing",
        "",
        _render_provider_pair_table(payload["streaming_nonstreaming_pairs"]),
        "",
        "## Judge Profile Agreement",
        "",
        _render_counter(payload["judge_profile_pair_agreement"], "agreement"),
        "",
        "## Judge Labels By Profile",
        "",
        _render_nested_counter(payload["judge_profile_labels"], "judge_profile"),
        "",
        "## Timing Metrics By Provider/Mode",
        "",
        _render_metrics_table(payload["metrics_by_provider_mode"]),
        "",
        "## Judge Disagreement Examples",
        "",
        _render_disagreement_examples(payload["judge_profile_pair_disagreement_examples"]),
        "",
    ]
    return "\n".join(lines)


def _streaming_nonstreaming_pairs(
    cells: dict[tuple[str, str, str], TraceCell],
    samples: list[str],
    providers: list[str],
) -> dict[str, dict[str, int]]:
    output: dict[str, dict[str, int]] = {}
    for provider in providers:
        counts = Counter()
        for sample_id in samples:
            streaming = cells.get((sample_id, provider, "streaming"))
            nonstreaming = cells.get((sample_id, provider, "nonstreaming"))
            if streaming is None or nonstreaming is None:
                counts["missing_pair"] += 1
                continue
            counts["paired_prompt_count"] += 1
            if streaming.provider_stop_reason == nonstreaming.provider_stop_reason:
                counts["provider_stop_reason_agree"] += 1
            else:
                counts["provider_stop_reason_disagree"] += 1
            if streaming.terminal_reason == nonstreaming.terminal_reason:
                counts["terminal_reason_agree"] += 1
            else:
                counts["terminal_reason_disagree"] += 1
            streaming_filter = streaming.terminal_reason == "content_filter"
            nonstreaming_filter = nonstreaming.terminal_reason == "content_filter"
            if streaming_filter and nonstreaming_filter:
                counts["content_filter_both"] += 1
            elif streaming_filter:
                counts["content_filter_streaming_only"] += 1
            elif nonstreaming_filter:
                counts["content_filter_nonstreaming_only"] += 1
            else:
                counts["content_filter_neither"] += 1
            if streaming.safety_signal_count > 0 and nonstreaming.safety_signal_count > 0:
                counts["safety_signal_both"] += 1
            elif streaming.safety_signal_count > 0:
                counts["safety_signal_streaming_only"] += 1
            elif nonstreaming.safety_signal_count > 0:
                counts["safety_signal_nonstreaming_only"] += 1
            else:
                counts["safety_signal_neither"] += 1
        output[provider] = dict(sorted(counts.items()))
    return output


def _paired_record(
    sample_id: str,
    providers: list[str],
    modes: list[str],
    cells: dict[tuple[str, str, str], TraceCell],
) -> dict[str, Any]:
    record: dict[str, Any] = {"sample_id": sample_id, "cells": {}}
    for provider in providers:
        for mode in modes:
            cell = cells.get((sample_id, provider, mode))
            key = f"{provider}:{mode}"
            record["cells"][key] = cell.to_dict() if cell is not None else None
    first_cell = next(
        (cell for (candidate, _, _), cell in cells.items() if candidate == sample_id),
        None,
    )
    if first_cell is not None:
        record.update(
            {
                "prompt_id": first_cell.prompt_id,
                "benchmark": first_cell.benchmark,
                "category": first_cell.category,
                "source_file": first_cell.source_file,
                "source_line": first_cell.source_line,
            }
        )
    return record


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


def _trace_path_parts(path: Path) -> tuple[str, str, str]:
    parts = path.parts
    index = parts.index("safety_signal")
    return parts[index + 1], parts[index + 2], parts[index + 3]


def _judge_path_parts(path: Path) -> tuple[str, str, str]:
    parts = path.parts
    index = parts.index("response_judge")
    return parts[index + 1], parts[index + 2], parts[index + 3]


def _sample_id(source_file: str, source_line: str, prompt_id: str) -> str:
    return f"{source_file}:{source_line}:{prompt_id}"


def _request_metadata(events: list[StreamEvent]) -> dict[str, Any]:
    event = _first_event(events, EventType.REQUEST_START)
    return dict(event.metadata) if event is not None else {}


def _first_model(events: list[StreamEvent]) -> str:
    for event in events:
        model = event.metadata.get("model")
        if isinstance(model, str) and model:
            return model
    return "unknown"


def _provider_stop_reason(events: list[StreamEvent]) -> str:
    for event in reversed(events):
        value = event.metadata.get("provider_stop_reason")
        if isinstance(value, str) and value:
            return value
    return "unknown"


def _trace_terminal_reason(events: list[StreamEvent]) -> str:
    for event in reversed(events):
        if event.terminal_reason is not None:
            return event.terminal_reason.value
    return "unknown"


def _first_event(events: list[StreamEvent], event_type: EventType) -> StreamEvent | None:
    return next((event for event in events if event.event_type == event_type), None)


def _record_optional(values: list[float], value: float | int | None) -> None:
    if value is not None:
        values.append(float(value))


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


def _render_counter(counter: dict[str, int], key_name: str) -> str:
    if not counter:
        return "_No records._"
    lines = [f"| {key_name} | count |", "| --- | ---: |"]
    for key, count in sorted(counter.items()):
        lines.append(f"| `{key}` | {count} |")
    return "\n".join(lines)


def _render_nested_counter(mapping: dict[str, dict[str, int]], key_name: str) -> str:
    if not mapping:
        return "_No records._"
    lines = [f"| {key_name} | value | count |", "| --- | --- | ---: |"]
    for key, counter in sorted(mapping.items()):
        for value, count in sorted(counter.items()):
            lines.append(f"| `{key}` | `{value}` | {count} |")
    return "\n".join(lines)


def _render_provider_pair_table(mapping: dict[str, dict[str, int]]) -> str:
    if not mapping:
        return "_No provider pairs._"
    keys = sorted({key for counts in mapping.values() for key in counts})
    lines = ["| provider | " + " | ".join(keys) + " |"]
    lines.append("| --- | " + " | ".join("---:" for _ in keys) + " |")
    for provider, counts in sorted(mapping.items()):
        values = [str(counts.get(key, 0)) for key in keys]
        lines.append(f"| `{provider}` | " + " | ".join(values) + " |")
    return "\n".join(lines)


def _render_metrics_table(mapping: dict[str, dict[str, dict[str, float | int | None]]]) -> str:
    if not mapping:
        return "_No metrics._"
    lines = [
        "| provider_mode | metric | count | p50_ms | p95_ms | max_ms |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for provider_mode, metrics in sorted(mapping.items()):
        for name, aggregate in sorted(metrics.items()):
            lines.append(
                f"| `{provider_mode}` | `{name}` | {aggregate['count']} | "
                f"{_fmt(aggregate['p50'])} | {_fmt(aggregate['p95'])} | {_fmt(aggregate['max'])} |"
            )
    return "\n".join(lines)


def _render_disagreement_examples(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No judge profile disagreements._"
    lines = [
        "| sample_id | prompt_id | provider | mode | judge_a | judge_b | stop_reason | terminal_reason | category |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['sample_id']}` | `{row['prompt_id']}` | `{row['provider']}` | `{row['mode']}` | "
            f"`{row['judge_a']}` | `{row['judge_b']}` | `{row['provider_stop_reason']}` | "
            f"`{row['terminal_reason']}` | `{row['category']}` |"
        )
    return "\n".join(lines)


def _fmt(value: float | int | None) -> str:
    if value is None:
        return ""
    return f"{float(value):.3f}"


if __name__ == "__main__":
    sys.exit(main())
