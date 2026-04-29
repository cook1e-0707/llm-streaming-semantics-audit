#!/usr/bin/env python3
"""Check whether Phase 2 can proceed to a benign real API pilot."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from .check_phase1_ready import (
        GateCheck,
        check_phase1_ready,
        forbidden_tracked_paths,
    )
    from .generate_provider_matrix import generate_provider_matrix
    from .run_mock_pilot import run_scenario
    from .update_readme_status import update_readme_text
    from .validate_provider_matrix import validate_provider_matrix
except ImportError:
    from check_phase1_ready import (
        GateCheck,
        check_phase1_ready,
        forbidden_tracked_paths,
    )
    from generate_provider_matrix import generate_provider_matrix
    from run_mock_pilot import run_scenario
    from update_readme_status import update_readme_text
    from validate_provider_matrix import validate_provider_matrix

from lssa.adapters.mock import MockScenario

ALLOWED_ADAPTER_FILES = {
    "__init__.py",
    "anthropic_messages.py",
    "aws_bedrock_converse.py",
    "base.py",
    "mock.py",
    "openai_responses.py",
}
REQUIRED_DOCS = {
    "docs/benign_pilot_policy.md",
    "docs/phase2_plan.md",
    "docs/phase2_real_pilot_plan.md",
    "docs/real_api_data_policy.md",
    "docs/trace_contract.md",
}
PROMPT_FORBIDDEN_TERMS = {
    "unsafe",
    "jailbreak",
    "malicious",
    "exploit",
}


@dataclass(frozen=True)
class Phase2GateResult:
    ready: bool
    checks: tuple[GateCheck, ...]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )
    args = parser.parse_args(argv)

    result = check_phase2_pilot_ready(args.root)
    if args.json:
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
    else:
        for check in result.checks:
            status = "ok" if check.ok else "fail"
            print(f"[{status}] {check.name}: {check.detail}")
        print("Phase 2 pilot ready" if result.ready else "Phase 2 pilot not ready")
    return 0 if result.ready else 1


def check_phase2_pilot_ready(root: Path) -> Phase2GateResult:
    checks = [
        _phase1_ready_check(root),
        _provider_matrix_check(root),
        _readme_check(root),
        _phase2_docs_check(root),
        _mock_pilot_check(root),
        _adapter_scope_check(root),
        _real_pilot_runner_guard_check(root),
        _prompt_scope_check(root),
        _forbidden_tracked_files_check(root),
    ]
    return Phase2GateResult(
        ready=all(check.ok for check in checks),
        checks=tuple(checks),
    )


def _phase1_ready_check(root: Path) -> GateCheck:
    result = check_phase1_ready(root)
    failed = [check.name for check in result.checks if not check.ok]
    return GateCheck(
        name="phase1_readiness_still_passes",
        ok=result.ready,
        detail="ready" if result.ready else ", ".join(failed),
    )


def _provider_matrix_check(root: Path) -> GateCheck:
    validation = validate_provider_matrix(root)
    if not validation.ok:
        return GateCheck(
            name="provider_matrix_valid",
            ok=False,
            detail="; ".join(validation.errors),
        )
    try:
        current = (root / "docs" / "provider_matrix.md").read_text(encoding="utf-8")
        generated = generate_provider_matrix(root)
    except (OSError, ValueError) as exc:
        return GateCheck(name="provider_matrix_valid", ok=False, detail=str(exc))
    return GateCheck(
        name="provider_matrix_valid",
        ok=current == generated,
        detail="valid and up to date" if current == generated else "matrix is stale",
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


def _phase2_docs_check(root: Path) -> GateCheck:
    missing = sorted(path for path in REQUIRED_DOCS if not (root / path).exists())
    return GateCheck(
        name="phase2_docs_exist",
        ok=not missing,
        detail="all required docs present" if not missing else ", ".join(missing),
    )


def _mock_pilot_check(root: Path) -> GateCheck:
    output_dir = root / "artifacts" / "mock_pilot_gate"
    failures = []
    for scenario in MockScenario:
        status_line = run_scenario(scenario, output_dir)
        if "status=ok" not in status_line:
            failures.append(status_line)
    return GateCheck(
        name="mock_pilot_scenarios_pass",
        ok=not failures,
        detail="all mock scenarios pass" if not failures else "; ".join(failures),
    )


def _adapter_scope_check(root: Path) -> GateCheck:
    adapter_dir = root / "src" / "lssa" / "adapters"
    files = {
        path.name
        for path in adapter_dir.glob("*.py")
        if path.is_file()
    }
    disallowed = sorted(files - ALLOWED_ADAPTER_FILES)
    return GateCheck(
        name="only_allowed_provider_adapters",
        ok=not disallowed,
        detail="only approved P2 adapters present" if not disallowed else ", ".join(disallowed),
    )


def _real_pilot_runner_guard_check(root: Path) -> GateCheck:
    script_path = root / "scripts" / "run_real_benign_pilot.py"
    if not script_path.exists():
        return GateCheck(
            name="real_pilot_runner_requires_network_opt_in",
            ok=False,
            detail="missing scripts/run_real_benign_pilot.py",
        )
    content = script_path.read_text(encoding="utf-8")
    required = [
        "--allow-network",
        "network=disabled",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AWS_BEARER_TOKEN_BEDROCK",
    ]
    missing = [item for item in required if item not in content]
    return GateCheck(
        name="real_pilot_runner_requires_network_opt_in",
        ok=not missing,
        detail="network guard present" if not missing else ", ".join(missing),
    )


def _prompt_scope_check(root: Path) -> GateCheck:
    prompt_dir = root / "src" / "lssa" / "prompts"
    suspicious = []
    for path in prompt_dir.glob("*"):
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8").lower()
        if any(term in content for term in PROMPT_FORBIDDEN_TERMS):
            suspicious.append(str(path.relative_to(root)))
    return GateCheck(
        name="benign_prompt_scope",
        ok=not suspicious,
        detail="benign prompt registry only" if not suspicious else ", ".join(suspicious),
    )


def _forbidden_tracked_files_check(root: Path) -> GateCheck:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        return GateCheck(name="no_forbidden_tracked_files", ok=False, detail=str(exc))
    forbidden = forbidden_tracked_paths(proc.stdout.splitlines())
    return GateCheck(
        name="no_forbidden_tracked_files",
        ok=not forbidden,
        detail="no forbidden tracked files" if not forbidden else ", ".join(forbidden),
    )


if __name__ == "__main__":
    sys.exit(main())
