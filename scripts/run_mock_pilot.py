#!/usr/bin/env python3
"""Run deterministic mock pilot scenarios without provider API calls."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lssa.adapters.mock import MockProviderAdapter, MockScenario, request_for_scenario
from lssa.tracing.recorder import TraceRecorder
from lssa.tracing.validator import validate_trace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        choices=[scenario.value for scenario in MockScenario],
        help="mock scenario to run",
    )
    parser.add_argument("--all", action="store_true", help="run all mock scenarios")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/mock_pilot"),
        help="directory for JSONL traces and summaries",
    )
    args = parser.parse_args(argv)

    if not args.all and args.scenario is None:
        parser.error("provide --scenario or --all")

    scenarios = (
        list(MockScenario) if args.all else [MockScenario(args.scenario)]
    )
    failures = []
    for scenario in scenarios:
        result = run_scenario(scenario, args.output_dir)
        print(result)
        if "status=ok" not in result:
            failures.append(scenario.value)
    return 1 if failures else 0


def run_scenario(scenario: MockScenario, output_dir: Path) -> str:
    adapter = MockProviderAdapter()
    request = request_for_scenario(scenario)
    events = list(adapter.run(request))
    validation = validate_trace(events)

    scenario_dir = output_dir / scenario.value
    recorder = TraceRecorder(
        trace_id=request.trace_id,
        provider_family=adapter.provider_family,
        api_surface=adapter.api_surface,
        model=request.model,
        response_mode=request.response_mode,
    )
    recorder.extend(events)
    trace_path = recorder.write_jsonl(scenario_dir / "trace.jsonl")
    summary_path = recorder.write_summary_json(scenario_dir / "summary.json")

    status = "ok" if validation.ok else "fail"
    detail = "valid" if validation.ok else "; ".join(validation.errors)
    return (
        f"scenario={scenario.value} status={status} events={len(events)} "
        f"trace={trace_path} summary={summary_path} detail={detail}"
    )


if __name__ == "__main__":
    sys.exit(main())
