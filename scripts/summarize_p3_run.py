#!/usr/bin/env python3
"""Summarize Phase 3 safety-signal runs without reading raw prompt text."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lssa.schema.events import EventType, ResponseMode, StreamEvent
from lssa.schema.metrics import (
    exposure_window_chars,
    exposure_window_ms,
    exposure_window_tokens,
    settlement_lag_ms,
    time_to_first_byte_ms,
    time_to_first_safety_signal_ms,
    time_to_first_token_ms,
    validation_lag_chars,
    validation_lag_tokens,
)

DEFAULT_RUNS_ROOT = ROOT / "artifacts" / "p3_overnight"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        run_root = args.run_root or _latest_run_root(DEFAULT_RUNS_ROOT)
        payload = summarize_run(run_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output_path = args.output or (run_root / "p3_run_metrics.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"p3_summary run_root={run_root} traces={payload['trace_count']} "
            f"streaming_traces={payload['streaming_trace_count']} "
            f"judge_results={payload['judge_result_count']} output={output_path}"
        )
    return 0


def summarize_run(run_root: Path) -> dict[str, Any]:
    if not run_root.exists():
        raise ValueError(f"run root does not exist: {run_root}")

    trace_paths = sorted((run_root / "safety_signal").rglob("*.jsonl"))
    judge_paths = sorted((run_root / "judge_adjudication").glob("*.json"))
    response_judge_paths = sorted((run_root / "response_judge").rglob("*.json"))
    by_provider_mode: Counter[str] = Counter()
    event_type_counts: Counter[str] = Counter()
    terminal_reasons: Counter[str] = Counter()
    provider_stop_reasons: Counter[str] = Counter()
    safety_signal_types: Counter[str] = Counter()
    safety_signal_event_types: Counter[str] = Counter()
    metric_values: dict[str, list[float]] = defaultdict(list)
    chunk_interarrival_ms: list[float] = []
    first_chunk_after_request_sent_ms: list[float] = []
    streaming_duration_ms: list[float] = []
    chunk_count_by_trace: list[int] = []
    chars_per_chunk: list[int] = []
    streaming_trace_count = 0
    nonstreaming_trace_count = 0

    for path in trace_paths:
        events = _load_events(path)
        if not events:
            continue
        response_mode = _response_mode_for_path(path)
        if response_mode == ResponseMode.STREAMING:
            streaming_trace_count += 1
        elif response_mode == ResponseMode.NON_STREAMING:
            nonstreaming_trace_count += 1
        provider = _provider_for_path(path)
        by_provider_mode[f"{provider}:{response_mode.value}"] += 1

        for event in events:
            event_type_counts[event.event_type.value] += 1
            if event.terminal_reason is not None:
                terminal_reasons[event.terminal_reason.value] += 1
            if event.safety_signal is not None:
                safety_signal_types[event.safety_signal.signal_type.value] += 1
            if event.event_type in {
                EventType.SAFETY_ANNOTATION,
                EventType.REFUSAL,
                EventType.CONTENT_FILTER,
            }:
                safety_signal_event_types[event.event_type.value] += 1
            if event.event_type == EventType.FINAL_RESPONSE:
                provider_stop_reasons[str(event.metadata.get("provider_stop_reason") or "unknown")] += 1

        _record_optional(metric_values["TTFB_ms"], time_to_first_byte_ms(events))
        _record_optional(metric_values["TTFT_ms"], time_to_first_token_ms(events))
        _record_optional(metric_values["TTFSS_ms"], time_to_first_safety_signal_ms(events))
        _record_optional(metric_values["settlement_lag_ms"], settlement_lag_ms(events))
        _record_optional(metric_values["validation_lag_chars"], validation_lag_chars(events))
        _record_optional(metric_values["validation_lag_tokens"], validation_lag_tokens(events))
        _record_optional(metric_values["exposure_window_chars"], exposure_window_chars(events))
        _record_optional(metric_values["exposure_window_tokens"], exposure_window_tokens(events))
        _record_optional(metric_values["exposure_window_ms"], exposure_window_ms(events))

        chunks = [event for event in events if event.event_type == EventType.CHUNK]
        chunk_count_by_trace.append(len(chunks))
        chars_per_chunk.extend(event.char_count for event in chunks if event.char_count is not None)
        if response_mode == ResponseMode.STREAMING and chunks:
            request_sent = _first_event(events, EventType.REQUEST_SENT)
            stream_end = _first_event(events, EventType.STREAM_END)
            if request_sent is not None:
                first_chunk_after_request_sent_ms.append(
                    chunks[0].timestamp_ms - request_sent.timestamp_ms
                )
            for previous, current in zip(chunks, chunks[1:]):
                chunk_interarrival_ms.append(current.timestamp_ms - previous.timestamp_ms)
            if stream_end is not None:
                streaming_duration_ms.append(stream_end.timestamp_ms - chunks[0].timestamp_ms)

    judge_labels: Counter[str] = Counter()
    judge_profiles: Counter[str] = Counter()
    for path in judge_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        judge_labels[str(payload.get("label") or "unknown")] += 1
        judge_profiles[str(payload.get("judge_profile") or "unknown")] += 1

    response_judge_labels: Counter[str] = Counter()
    response_judge_profiles: Counter[str] = Counter()
    response_judge_subjects: Counter[str] = Counter()
    response_judge_calls: Counter[str] = Counter()
    for path in response_judge_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        response_judge_labels[str(payload.get("label") or "unknown")] += 1
        response_judge_profiles[str(payload.get("judge_profile") or "unknown")] += 1
        response_judge_subjects[str(payload.get("judge_subject") or "unknown")] += 1
        response_judge_calls[str(payload.get("response_judge_call_made"))] += 1

    return {
        "run_root": str(run_root),
        "raw_text_committed": False,
        "trace_count": len(trace_paths),
        "streaming_trace_count": streaming_trace_count,
        "nonstreaming_trace_count": nonstreaming_trace_count,
        "judge_result_count": len(judge_paths),
        "response_judge_result_count": len(response_judge_paths),
        "by_provider_mode": dict(sorted(by_provider_mode.items())),
        "event_type_counts": dict(sorted(event_type_counts.items())),
        "terminal_reasons": dict(sorted(terminal_reasons.items())),
        "provider_stop_reasons": dict(sorted(provider_stop_reasons.items())),
        "safety_signal_event_count": sum(safety_signal_event_types.values()),
        "safety_signal_event_types": dict(sorted(safety_signal_event_types.items())),
        "safety_signal_types": dict(sorted(safety_signal_types.items())),
        "metrics": {name: _aggregate(values) for name, values in sorted(metric_values.items())},
        "chunk_latency": {
            "chunk_count_by_trace": _aggregate(chunk_count_by_trace),
            "chars_per_chunk": _aggregate(chars_per_chunk),
            "first_chunk_after_request_sent_ms": _aggregate(first_chunk_after_request_sent_ms),
            "interarrival_ms": _aggregate(chunk_interarrival_ms),
            "streaming_duration_ms": _aggregate(streaming_duration_ms),
        },
        "judge_labels": dict(sorted(judge_labels.items())),
        "judge_profiles": dict(sorted(judge_profiles.items())),
        "response_judge_labels": dict(sorted(response_judge_labels.items())),
        "response_judge_profiles": dict(sorted(response_judge_profiles.items())),
        "response_judge_subjects": dict(sorted(response_judge_subjects.items())),
        "response_judge_calls": dict(sorted(response_judge_calls.items())),
    }


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
    if index + 1 >= len(parts):
        return "unknown"
    return parts[index + 1]


def _first_event(events: list[StreamEvent], event_type: EventType) -> StreamEvent | None:
    return next((event for event in events if event.event_type == event_type), None)


def _record_optional(values: list[float], value: float | int | None) -> None:
    if value is not None:
        values.append(float(value))


def _aggregate(values: list[float] | list[int]) -> dict[str, float | int | None]:
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


def _percentile(sorted_values: list[float] | list[int], quantile: float) -> float | int:
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = round((len(sorted_values) - 1) * quantile)
    return sorted_values[index]


if __name__ == "__main__":
    sys.exit(main())
