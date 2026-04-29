#!/usr/bin/env python3
"""Check readiness for guarded external safety-prompt pilots."""

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
    from .check_phase1_ready import GateCheck, forbidden_tracked_paths
    from .check_p3_mock_safety_ready import check_p3_mock_safety_ready
    from .run_safety_signal_pilot import main as run_safety_signal_pilot_main
    from .update_readme_status import update_readme_text
except ImportError:
    from check_phase1_ready import GateCheck, forbidden_tracked_paths
    from check_p3_mock_safety_ready import check_p3_mock_safety_ready
    from run_safety_signal_pilot import main as run_safety_signal_pilot_main
    from update_readme_status import update_readme_text

from lssa.prompts.safety_external import inventory_safety_prompt_root, resolve_safety_prompt_root


@dataclass(frozen=True)
class P3SafetyPilotReadyResult:
    ready: bool
    real_safety_calls_allowed_by_default: bool
    checks: tuple[GateCheck, ...]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--prompt-root", type=Path)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )
    args = parser.parse_args(argv)

    result = check_p3_safety_pilot_ready(args.root, args.prompt_root)
    if args.json:
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
    else:
        for check in result.checks:
            status = "ok" if check.ok else "fail"
            print(f"[{status}] {check.name}: {check.detail}")
        print("P3 safety pilot ready" if result.ready else "P3 safety pilot not ready")
        print("Real safety calls allowed by default: no")
    return 0 if result.ready else 1


def check_p3_safety_pilot_ready(
    root: Path,
    prompt_root: Path | None = None,
) -> P3SafetyPilotReadyResult:
    checks = (
        _mock_safety_ready_check(root),
        _readme_check(root),
        _external_prompt_root_check(prompt_root),
        _safety_runner_guard_check(root),
        _safety_runner_dry_run_check(root, prompt_root),
        _forbidden_tracked_files_check(root),
    )
    return P3SafetyPilotReadyResult(
        ready=all(check.ok for check in checks),
        real_safety_calls_allowed_by_default=False,
        checks=checks,
    )


def _mock_safety_ready_check(root: Path) -> GateCheck:
    result = check_p3_mock_safety_ready(root)
    failed = [check.name for check in result.checks if not check.ok]
    return GateCheck(
        name="p3_mock_safety_ready",
        ok=result.ready and result.real_safety_calls_allowed is False,
        detail="ready; real safety calls remain opt-in" if result.ready else ", ".join(failed),
    )


def _readme_check(root: Path) -> GateCheck:
    readme_path = root / "README.md"
    try:
        current = readme_path.read_text(encoding="utf-8")
        updated = update_readme_text(current, root)
    except (OSError, ValueError) as exc:
        return GateCheck(name="readme_up_to_date", ok=False, detail=str(exc))
    return GateCheck(
        name="readme_up_to_date",
        ok=current == updated,
        detail="up to date" if current == updated else "README is stale",
    )


def _external_prompt_root_check(prompt_root: Path | None) -> GateCheck:
    try:
        inventory = inventory_safety_prompt_root(resolve_safety_prompt_root(prompt_root))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return GateCheck(name="external_safety_prompt_root", ok=False, detail=str(exc))
    return GateCheck(
        name="external_safety_prompt_root",
        ok=inventory.prompt_record_count > 0,
        detail=(
            f"files={inventory.file_count}; prompt_records={inventory.prompt_record_count}; "
            "raw_text_committed=false"
        ),
    )


def _safety_runner_guard_check(root: Path) -> GateCheck:
    script_path = root / "scripts" / "run_safety_signal_pilot.py"
    if not script_path.exists():
        return GateCheck(name="safety_runner_requires_double_opt_in", ok=False, detail="missing runner")
    content = script_path.read_text(encoding="utf-8")
    required = [
        "--allow-network",
        "--allow-safety-prompts",
        "--reviewed-source",
        "redact_content=True",
        "raw_text_in_plan",
    ]
    missing = [item for item in required if item not in content]
    return GateCheck(
        name="safety_runner_requires_double_opt_in",
        ok=not missing,
        detail="double opt-in and redaction guards present" if not missing else ", ".join(missing),
    )


def _safety_runner_dry_run_check(root: Path, prompt_root: Path | None) -> GateCheck:
    args = [
        "--provider",
        "openai_responses",
        "--limit",
        "1",
        "--max-calls",
        "1",
        "--plan-dir",
        str(root / "artifacts" / "p3_safety_ready"),
    ]
    if prompt_root is not None:
        args.extend(["--prompt-root", str(prompt_root)])
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = run_safety_signal_pilot_main(args)
    return GateCheck(
        name="safety_runner_dry_run_passes",
        ok=exit_code == 0 and "network=disabled" in stdout.getvalue(),
        detail="dry-run safety plan passes" if exit_code == 0 else stderr.getvalue().strip(),
    )


def _forbidden_tracked_files_check(root: Path) -> GateCheck:
    import subprocess

    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        return GateCheck(name="no_forbidden_tracked_safety_files", ok=False, detail=str(exc))
    tracked = proc.stdout.splitlines()
    forbidden = forbidden_tracked_paths(tracked)
    forbidden.extend(path for path in tracked if path.startswith(("data/safety/", "safety_prompts/")))
    forbidden = sorted(set(forbidden))
    return GateCheck(
        name="no_forbidden_tracked_safety_files",
        ok=not forbidden,
        detail="no raw safety prompt files tracked" if not forbidden else ", ".join(forbidden),
    )


if __name__ == "__main__":
    sys.exit(main())
