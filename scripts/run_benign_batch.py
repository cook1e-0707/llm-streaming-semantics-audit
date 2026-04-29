#!/usr/bin/env python3
"""Plan or run a bounded benign provider batch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lssa.experiments.manifest import (
    PlannedRun,
    build_planned_runs,
    load_benign_batch_manifest,
)

try:
    from .run_real_benign_pilot import (
        DEFAULT_OUTPUT_DIR as DEFAULT_REAL_PILOT_OUTPUT_DIR,
    )
    from .run_real_benign_pilot import SUPPORTED_PROVIDERS, load_benign_prompts
    from .run_real_benign_pilot import main as run_real_benign_pilot_main
except ImportError:
    from run_real_benign_pilot import (
        DEFAULT_OUTPUT_DIR as DEFAULT_REAL_PILOT_OUTPUT_DIR,
    )
    from run_real_benign_pilot import SUPPORTED_PROVIDERS, load_benign_prompts
    from run_real_benign_pilot import main as run_real_benign_pilot_main

DEFAULT_MANIFEST = Path("docs/benign_experiment_manifest.example.toml")
DEFAULT_PLAN_DIR = Path("artifacts/benign_batch_plans")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-total-calls", type=int)
    parser.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_DIR)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_REAL_PILOT_OUTPUT_DIR,
        help="real pilot output directory; must be ignored by git",
    )
    args = parser.parse_args(argv)

    try:
        manifest = load_benign_batch_manifest(args.manifest)
        runs = build_planned_runs(manifest)
        _validate_planned_runs(runs)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    cap = args.max_total_calls or manifest.max_total_calls_without_force
    if len(runs) > cap and not args.force:
        print(
            f"planned calls {len(runs)} exceed cap {cap}; use --force after review",
            file=sys.stderr,
        )
        return 2
    if not _is_ignored_output_dir(args.plan_dir):
        print(f"plan directory is not ignored by git policy: {args.plan_dir}", file=sys.stderr)
        return 2
    if not _is_ignored_output_dir(args.output_dir):
        print(f"output directory is not ignored by git policy: {args.output_dir}", file=sys.stderr)
        return 2

    plan_path = write_plan(args.plan_dir, args.manifest, runs, allow_network=args.allow_network)
    if not args.allow_network:
        print(
            f"dry-run batch_manifest={args.manifest} planned_calls={len(runs)} "
            f"providers={','.join(sorted({run.provider for run in runs}))} "
            f"network=disabled plan={plan_path}"
        )
        return 0

    failures = 0
    for run in runs:
        exit_code = run_one_real_call(run, args.output_dir)
        if exit_code != 0:
            failures += 1
    print(
        f"batch_manifest={args.manifest} planned_calls={len(runs)} "
        f"completed={len(runs) - failures} failures={failures} plan={plan_path}"
    )
    return 1 if failures else 0


def write_plan(
    plan_dir: Path,
    manifest_path: Path,
    runs: list[PlannedRun],
    *,
    allow_network: bool,
) -> Path:
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / f"benign-batch-{uuid4().hex}.plan.json"
    payload = {
        "manifest": str(manifest_path),
        "allow_network": allow_network,
        "planned_calls": len(runs),
        "runs": [run.to_redacted_dict() for run in runs],
    }
    plan_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return plan_path


def run_one_real_call(run: PlannedRun, output_dir: Path) -> int:
    return run_real_benign_pilot_main(
        [
            "--provider",
            run.provider,
            "--prompt-id",
            run.prompt_id,
            "--mode",
            run.mode,
            "--allow-network",
            "--max-calls",
            "1",
            "--max-output-tokens",
            str(run.max_output_tokens),
            "--timeout-seconds",
            str(run.timeout_seconds),
            "--temperature",
            str(run.temperature),
            "--output-dir",
            str(output_dir),
        ]
    )


def _validate_planned_runs(runs: list[PlannedRun]) -> None:
    prompts = load_benign_prompts()
    unknown_prompts = sorted({run.prompt_id for run in runs} - set(prompts))
    if unknown_prompts:
        raise ValueError(f"unknown benign prompt ids: {unknown_prompts}")
    unknown_providers = sorted({run.provider for run in runs} - SUPPORTED_PROVIDERS)
    if unknown_providers:
        raise ValueError(f"unsupported providers: {unknown_providers}")


def _is_ignored_output_dir(path: Path) -> bool:
    if path.is_absolute():
        try:
            path = path.relative_to(ROOT)
        except ValueError:
            return False
    parts = path.parts
    return bool(parts) and parts[0] == "artifacts"


if __name__ == "__main__":
    sys.exit(main())
