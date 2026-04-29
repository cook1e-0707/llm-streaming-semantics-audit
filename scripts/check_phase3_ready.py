#!/usr/bin/env python3
"""Check Phase 3 policy readiness without authorizing safety-signal runs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
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
    from .compare_benign_lifecycle import DEFAULT_OUTPUT as COMPARISON_OUTPUT
    from .compare_benign_lifecycle import collect_observations, render_markdown
    from .summarize_real_pilot import DEFAULT_ARTIFACTS_DIR, DEFAULT_OUTPUTS
    from .summarize_real_pilot import collect_latest_trace_rows, render_markdown as render_provider_summary
    from .update_readme_status import update_readme_text
except ImportError:
    from check_phase1_ready import GateCheck, forbidden_tracked_paths
    from compare_benign_lifecycle import DEFAULT_OUTPUT as COMPARISON_OUTPUT
    from compare_benign_lifecycle import collect_observations, render_markdown
    from summarize_real_pilot import DEFAULT_ARTIFACTS_DIR, DEFAULT_OUTPUTS
    from summarize_real_pilot import collect_latest_trace_rows, render_markdown as render_provider_summary
    from update_readme_status import update_readme_text

REQUIRED_P3_DOCS = {
    "docs/phase3_plan.md",
    "docs/phase3_quality_gate.md",
    "docs/safety_prompt_policy.md",
    "docs/safety_prompt_registry.example.yaml",
}
REQUIRED_PROVIDERS = (
    "openai_responses",
    "anthropic_messages",
    "aws_bedrock_converse",
)
FORBIDDEN_SAFETY_PROMPT_PATH_PREFIXES = (
    "data/safety/",
    "data/prompts/safety/",
    "prompts/safety/",
    "safety_prompts/",
)
FORBIDDEN_REGISTRY_PATTERNS = (
    "raw_text_committed: true",
    "raw_prompt:",
    "prompt_text:",
    "raw_text:",
    "jailbreak_text:",
)


@dataclass(frozen=True)
class Phase3GateResult:
    ready: bool
    p3m2_allowed: bool
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

    result = check_phase3_ready(args.root)
    if args.json:
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
    else:
        for check in result.checks:
            status = "ok" if check.ok else "fail"
            print(f"[{status}] {check.name}: {check.detail}")
        print("Phase 3 policy gate ready" if result.ready else "Phase 3 policy gate not ready")
        print("P3.M2 safety-signal runs allowed: no")
    return 0 if result.ready else 1


def check_phase3_ready(root: Path) -> Phase3GateResult:
    checks = (
        _readme_check(root),
        _p3_docs_check(root),
        _project_progress_check(root),
        _provider_summaries_check(root),
        _lifecycle_comparison_check(root),
        _safety_prompt_registry_check(root),
        _forbidden_tracked_files_check(root),
    )
    return Phase3GateResult(
        ready=all(check.ok for check in checks),
        p3m2_allowed=False,
        checks=checks,
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


def _p3_docs_check(root: Path) -> GateCheck:
    missing = sorted(path for path in REQUIRED_P3_DOCS if not (root / path).exists())
    return GateCheck(
        name="phase3_policy_docs_exist",
        ok=not missing,
        detail="all required P3 policy docs present" if not missing else ", ".join(missing),
    )


def _project_progress_check(root: Path) -> GateCheck:
    try:
        data = tomllib.loads((root / "docs" / "project_progress.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return GateCheck(name="phase3_progress_state", ok=False, detail=str(exc))

    phases = data.get("phases", [])
    phase_status = {
        phase.get("id"): phase.get("status")
        for phase in phases
        if isinstance(phase, dict)
    }
    milestone_status = {
        milestone.get("id"): milestone.get("status")
        for phase in phases
        if isinstance(phase, dict)
        for milestone in phase.get("milestones", [])
        if isinstance(milestone, dict)
    }
    expected = {
        "current_phase": data.get("current_phase") == "P3",
        "P2_done": phase_status.get("P2") == "done",
        "P3_in_progress": phase_status.get("P3") == "in_progress",
        "P3_M1_done": milestone_status.get("P3.M1") == "done",
        "P3_M2_controlled": milestone_status.get("P3.M2") in {"blocked", "next", "done"},
    }
    failed = [name for name, ok in expected.items() if not ok]
    return GateCheck(
        name="phase3_progress_state",
        ok=not failed,
        detail="P3 policy active and safety runs remain opt-in" if not failed else ", ".join(failed),
    )


def _provider_summaries_check(root: Path) -> GateCheck:
    stale = []
    for provider in REQUIRED_PROVIDERS:
        output = root / DEFAULT_OUTPUTS[provider]
        try:
            rows = collect_latest_trace_rows(root / DEFAULT_ARTIFACTS_DIR, provider)
            rendered = render_provider_summary(provider, rows, DEFAULT_ARTIFACTS_DIR)
            current = output.read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            return GateCheck(name="provider_pilot_summaries_up_to_date", ok=False, detail=str(exc))
        if current != rendered:
            stale.append(provider)
    return GateCheck(
        name="provider_pilot_summaries_up_to_date",
        ok=not stale,
        detail="all provider summaries up to date" if not stale else ", ".join(stale),
    )


def _lifecycle_comparison_check(root: Path) -> GateCheck:
    try:
        observations = collect_observations(root / DEFAULT_ARTIFACTS_DIR, REQUIRED_PROVIDERS)
        rendered = render_markdown(observations, DEFAULT_ARTIFACTS_DIR)
        current = (root / COMPARISON_OUTPUT).read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        return GateCheck(name="benign_lifecycle_comparison_up_to_date", ok=False, detail=str(exc))
    return GateCheck(
        name="benign_lifecycle_comparison_up_to_date",
        ok=current == rendered,
        detail="comparison up to date" if current == rendered else "comparison is stale",
    )


def _safety_prompt_registry_check(root: Path) -> GateCheck:
    registry_paths = sorted((root / "docs").glob("*safety*prompt*.yaml"))
    problems = []
    for path in registry_paths:
        content = path.read_text(encoding="utf-8").lower()
        for pattern in FORBIDDEN_REGISTRY_PATTERNS:
            if pattern in content:
                problems.append(f"{path.relative_to(root)} contains {pattern}")
    return GateCheck(
        name="safety_prompt_registry_redacted",
        ok=not problems,
        detail="safety prompt registry examples are redacted" if not problems else "; ".join(problems),
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

    tracked = proc.stdout.splitlines()
    forbidden = forbidden_tracked_paths(tracked)
    forbidden.extend(
        path
        for path in tracked
        if path.startswith(FORBIDDEN_SAFETY_PROMPT_PATH_PREFIXES)
    )
    forbidden = sorted(set(forbidden))
    return GateCheck(
        name="no_forbidden_tracked_files",
        ok=not forbidden,
        detail="no forbidden tracked files" if not forbidden else ", ".join(forbidden),
    )


if __name__ == "__main__":
    sys.exit(main())
