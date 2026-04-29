#!/usr/bin/env python3
"""Check optional NVIDIA judge readiness without authorizing network calls."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from .check_phase1_ready import GateCheck
    from .check_p3_safety_pilot_ready import check_p3_safety_pilot_ready
    from .run_judge_adjudication import main as run_judge_adjudication_main
except ImportError:
    from check_phase1_ready import GateCheck
    from check_p3_safety_pilot_ready import check_p3_safety_pilot_ready
    from run_judge_adjudication import main as run_judge_adjudication_main


@dataclass(frozen=True)
class JudgeReadyResult:
    ready: bool
    judge_network_allowed_by_default: bool
    checks: tuple[GateCheck, ...]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--prompt-root", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)

    result = check_judge_ready(args.root, args.prompt_root)
    if args.json:
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
    else:
        for check in result.checks:
            status = "ok" if check.ok else "fail"
            print(f"[{status}] {check.name}: {check.detail}")
        print("Judge dry-run ready" if result.ready else "Judge dry-run not ready")
        print("Judge network allowed by default: no")
    return 0 if result.ready else 1


def check_judge_ready(root: Path, prompt_root: Path | None = None) -> JudgeReadyResult:
    checks = (
        _p3_safety_ready_check(root, prompt_root),
        _judge_runner_guard_check(root),
        _judge_dry_run_check(root, prompt_root),
    )
    return JudgeReadyResult(
        ready=all(check.ok for check in checks),
        judge_network_allowed_by_default=False,
        checks=checks,
    )


def _p3_safety_ready_check(root: Path, prompt_root: Path | None) -> GateCheck:
    result = check_p3_safety_pilot_ready(root, prompt_root)
    failed = [check.name for check in result.checks if not check.ok]
    return GateCheck(
        name="p3_safety_pilot_ready",
        ok=result.ready,
        detail="ready" if result.ready else ", ".join(failed),
    )


def _judge_runner_guard_check(root: Path) -> GateCheck:
    script_path = root / "scripts" / "run_judge_adjudication.py"
    if not script_path.exists():
        return GateCheck(name="judge_runner_requires_opt_in", ok=False, detail="missing runner")
    content = script_path.read_text(encoding="utf-8")
    required = [
        "--allow-judge-network",
        "--allow-safety-prompts",
        "--reviewed-source",
        "raw_text_in_plan",
    ]
    missing = [item for item in required if item not in content]
    return GateCheck(
        name="judge_runner_requires_opt_in",
        ok=not missing,
        detail="judge network and safety prompt guards present" if not missing else ", ".join(missing),
    )


def _judge_dry_run_check(root: Path, prompt_root: Path | None) -> GateCheck:
    args = [
        "--limit",
        "1",
        "--max-calls",
        "1",
        "--plan-dir",
        str(root / "artifacts" / "judge_ready"),
    ]
    if prompt_root is not None:
        args.extend(["--prompt-root", str(prompt_root)])
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = run_judge_adjudication_main(args)
    return GateCheck(
        name="judge_dry_run_passes",
        ok=exit_code == 0 and "network=disabled" in stdout.getvalue(),
        detail="dry-run judge planning passes" if exit_code == 0 else stderr.getvalue().strip(),
    )


if __name__ == "__main__":
    sys.exit(main())
