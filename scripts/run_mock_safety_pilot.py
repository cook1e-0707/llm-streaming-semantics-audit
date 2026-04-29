#!/usr/bin/env python3
"""Run redacted mock safety-signal pilot scenarios without provider APIs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lssa.schema.metrics import (
    exposure_window_chars,
    exposure_window_ms,
    exposure_window_tokens,
    time_to_first_safety_signal_ms,
    validation_lag_chars,
    validation_lag_tokens,
)
from lssa.schema.events import ResponseMode
from lssa.tracing.recorder import TraceRecorder
from lssa.tracing.safety_fixtures import MockSafetyScenario, safety_trace_for_scenario
from lssa.tracing.validator import validate_trace

DEFAULT_OUTPUT_DIR = Path("artifacts/mock_safety_pilot")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        choices=[scenario.value for scenario in MockSafetyScenario],
        help="mock safety scenario to run",
    )
    parser.add_argument("--all", action="store_true", help="run all scenarios")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="directory for redacted JSONL traces and summaries",
    )
    args = parser.parse_args(argv)

    if not args.all and args.scenario is None:
        parser.error("provide --scenario or --all")

    scenarios = (
        list(MockSafetyScenario)
        if args.all
        else [MockSafetyScenario(args.scenario)]
    )
    failures = []
    for scenario in scenarios:
        status_line = run_scenario(scenario, args.output_dir)
        print(status_line)
        if "status=ok" not in status_line:
            failures.append(scenario.value)
    return 1 if failures else 0


def run_scenario(scenario: MockSafetyScenario, output_dir: Path) -> str:
    events = safety_trace_for_scenario(scenario)
    validation = validate_trace(events)
    recorder = TraceRecorder(
        trace_id=events[0].trace_id,
        provider_family="mock",
        api_surface="mock_safety_provider",
        model="mock-safety-model",
        response_mode=ResponseMode.STREAMING,
    )
    recorder.extend(events)

    scenario_dir = output_dir / scenario.value
    trace_path = recorder.write_jsonl(
        scenario_dir / "trace.jsonl",
        redact_content=True,
    )
    summary_path = recorder.write_summary_json(
        scenario_dir / "summary.json",
        redact_content=True,
    )
    metrics_path = scenario_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(_metrics_for_events(events), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    status = "ok" if validation.ok else "fail"
    detail = "valid" if validation.ok else "; ".join(validation.errors)
    return (
        f"scenario={scenario.value} status={status} events={len(events)} "
        f"ttfss_ms={time_to_first_safety_signal_ms(events)} "
        f"validation_lag_chars={validation_lag_chars(events)} "
        f"trace={trace_path} summary={summary_path} metrics={metrics_path} "
        f"detail={detail}"
    )


def _metrics_for_events(events) -> dict[str, float | int | None]:
    return {
        "TTFSS_ms": time_to_first_safety_signal_ms(events),
        "validation_lag_chars": validation_lag_chars(events),
        "validation_lag_tokens": validation_lag_tokens(events),
        "exposure_window_chars": exposure_window_chars(events),
        "exposure_window_tokens": exposure_window_tokens(events),
        "exposure_window_ms": exposure_window_ms(events),
    }


if __name__ == "__main__":
    sys.exit(main())
