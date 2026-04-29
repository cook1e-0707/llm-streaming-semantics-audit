#!/usr/bin/env python3
"""Check readiness for scaled benign batch runs."""

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
    from .check_phase2_pilot_ready import check_phase2_pilot_ready
    from .run_benign_batch import DEFAULT_MANIFEST
    from .run_benign_batch import main as run_benign_batch_main
    from .update_readme_status import update_readme_text
except ImportError:
    from check_phase1_ready import GateCheck
    from check_phase2_pilot_ready import check_phase2_pilot_ready
    from run_benign_batch import DEFAULT_MANIFEST
    from run_benign_batch import main as run_benign_batch_main
    from update_readme_status import update_readme_text


@dataclass(frozen=True)
class ScaledBenignReadyResult:
    ready: bool
    real_network_allowed_by_default: bool
    checks: tuple[GateCheck, ...]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )
    args = parser.parse_args(argv)

    result = check_scaled_benign_ready(args.root, args.manifest)
    if args.json:
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
    else:
        for check in result.checks:
            status = "ok" if check.ok else "fail"
            print(f"[{status}] {check.name}: {check.detail}")
        print("Scaled benign batch ready" if result.ready else "Scaled benign batch not ready")
        print("Real network allowed by default: no")
    return 0 if result.ready else 1


def check_scaled_benign_ready(root: Path, manifest: Path) -> ScaledBenignReadyResult:
    checks = (
        _phase2_ready_check(root),
        _readme_check(root),
        _manifest_exists_check(root, manifest),
        _batch_dry_run_check(root, manifest),
    )
    return ScaledBenignReadyResult(
        ready=all(check.ok for check in checks),
        real_network_allowed_by_default=False,
        checks=checks,
    )


def _phase2_ready_check(root: Path) -> GateCheck:
    result = check_phase2_pilot_ready(root)
    failed = [check.name for check in result.checks if not check.ok]
    return GateCheck(
        name="phase2_readiness_still_passes",
        ok=result.ready,
        detail="ready" if result.ready else ", ".join(failed),
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


def _manifest_exists_check(root: Path, manifest: Path) -> GateCheck:
    path = manifest if manifest.is_absolute() else root / manifest
    return GateCheck(
        name="benign_batch_manifest_exists",
        ok=path.exists(),
        detail=str(path.relative_to(root)) if path.exists() else f"missing {manifest}",
    )


def _batch_dry_run_check(root: Path, manifest: Path) -> GateCheck:
    manifest_arg = manifest if manifest.is_absolute() else root / manifest
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = run_benign_batch_main(
            [
                "--manifest",
                str(manifest_arg),
                "--plan-dir",
                str(root / "artifacts" / "scaled_benign_ready"),
            ]
        )
    return GateCheck(
        name="benign_batch_dry_run_passes",
        ok=exit_code == 0,
        detail="dry-run batch planning passes" if exit_code == 0 else f"exit_code={exit_code}",
    )


if __name__ == "__main__":
    sys.exit(main())
