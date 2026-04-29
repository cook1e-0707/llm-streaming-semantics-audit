#!/usr/bin/env python3
"""Check Phase 3 mock safety-signal harness readiness."""

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
    from .check_phase3_ready import check_phase3_ready
    from .run_mock_safety_pilot import DEFAULT_OUTPUT_DIR, main as run_mock_safety_main
except ImportError:
    from check_phase1_ready import GateCheck
    from check_phase3_ready import check_phase3_ready
    from run_mock_safety_pilot import DEFAULT_OUTPUT_DIR, main as run_mock_safety_main


@dataclass(frozen=True)
class P3MockSafetyReadyResult:
    ready: bool
    real_safety_calls_allowed: bool
    checks: tuple[GateCheck, ...]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )
    args = parser.parse_args(argv)

    result = check_p3_mock_safety_ready(args.root)
    if args.json:
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
    else:
        for check in result.checks:
            status = "ok" if check.ok else "fail"
            print(f"[{status}] {check.name}: {check.detail}")
        print("P3 mock safety harness ready" if result.ready else "P3 mock safety harness not ready")
        print("Real safety calls allowed: no")
    return 0 if result.ready else 1


def check_p3_mock_safety_ready(root: Path) -> P3MockSafetyReadyResult:
    checks = (
        _phase3_policy_ready_check(root),
        _mock_safety_pilot_check(root),
    )
    return P3MockSafetyReadyResult(
        ready=all(check.ok for check in checks),
        real_safety_calls_allowed=False,
        checks=checks,
    )


def _phase3_policy_ready_check(root: Path) -> GateCheck:
    result = check_phase3_ready(root)
    failed = [check.name for check in result.checks if not check.ok]
    return GateCheck(
        name="phase3_policy_gate_still_passes",
        ok=result.ready and result.p3m2_allowed is False,
        detail="ready; real safety calls remain blocked" if result.ready else ", ".join(failed),
    )


def _mock_safety_pilot_check(root: Path) -> GateCheck:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = run_mock_safety_main(
            [
                "--all",
                "--output-dir",
                str(root / DEFAULT_OUTPUT_DIR),
            ]
        )
    return GateCheck(
        name="mock_safety_pilot_scenarios_pass",
        ok=exit_code == 0,
        detail="all mock safety scenarios pass" if exit_code == 0 else f"exit_code={exit_code}",
    )


if __name__ == "__main__":
    sys.exit(main())
