#!/usr/bin/env python3
"""Check whether Phase 1 is ready to hand off to a benign raw API pilot."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    from .generate_provider_matrix import generate_provider_matrix
    from .provider_evidence import (
        ALLOWED_EVIDENCE_STATUS,
        EvidenceSource,
        load_provider_evidence,
        validate_provider_evidence,
    )
    from .update_readme_status import load_metrics_registry
    from .validate_provider_matrix import (
        MATRIX_SEMANTIC_COLUMNS,
        parse_markdown_table,
        validate_provider_matrix,
    )
except ImportError:
    from generate_provider_matrix import generate_provider_matrix
    from provider_evidence import (
        ALLOWED_EVIDENCE_STATUS,
        EvidenceSource,
        load_provider_evidence,
        validate_provider_evidence,
    )
    from update_readme_status import load_metrics_registry
    from validate_provider_matrix import (
        MATRIX_SEMANTIC_COLUMNS,
        parse_markdown_table,
        validate_provider_matrix,
    )

REQUIRED_PROVIDER_FAMILIES = {
    "OpenAI / OpenAI Guardrails",
    "Azure OpenAI",
    "AWS Bedrock Guardrails",
    "Anthropic Claude",
    "Google Gemini / Vertex AI",
    "OpenAI Agents SDK",
}
REQUIRED_PHASE2_METRICS = {"TTFB_ms", "TTFT_ms", "settlement_lag_ms"}
FORBIDDEN_TRACKED_PREFIXES = (
    "results/",
    "data/raw/",
    "data/processed/",
    "keys/",
)
EXPLICIT_UNKNOWN_VALUES = {
    "unknown_from_official_docs",
    "not_documented_in_source",
}


@dataclass(frozen=True)
class GateCheck:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class GateResult:
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

    result = check_phase1_ready(args.root)
    if args.json:
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
    else:
        for check in result.checks:
            status = "ok" if check.ok else "fail"
            print(f"[{status}] {check.name}: {check.detail}")
        print("Phase 1 ready" if result.ready else "Phase 1 not ready")
    return 0 if result.ready else 1


def check_phase1_ready(root: Path) -> GateResult:
    checks: list[GateCheck] = []
    evidence_path = root / "docs" / "provider_evidence.yaml"
    checks.append(
        GateCheck(
            name="provider_evidence_exists",
            ok=evidence_path.exists(),
            detail=str(evidence_path),
        )
    )

    sources: list[EvidenceSource] = []
    if evidence_path.exists():
        try:
            sources = load_provider_evidence(root)
            evidence_errors = validate_provider_evidence(sources)
            checks.append(
                GateCheck(
                    name="provider_evidence_valid",
                    ok=not evidence_errors,
                    detail="valid" if not evidence_errors else "; ".join(evidence_errors),
                )
            )
        except ValueError as exc:
            checks.append(
                GateCheck(
                    name="provider_evidence_valid",
                    ok=False,
                    detail=str(exc),
                )
            )

    checks.extend(_source_readiness_checks(sources))
    checks.append(_matrix_freshness_check(root))
    checks.extend(_matrix_validation_checks(root))
    checks.append(_phase2_metrics_check(root))
    checks.append(_forbidden_tracked_files_check(root))

    return GateResult(
        ready=all(check.ok for check in checks),
        checks=tuple(checks),
    )


def forbidden_tracked_paths(paths: list[str]) -> list[str]:
    return [
        path
        for path in paths
        if any(path.startswith(prefix) for prefix in FORBIDDEN_TRACKED_PREFIXES)
    ]


def _source_readiness_checks(sources: list[EvidenceSource]) -> list[GateCheck]:
    checks: list[GateCheck] = []
    provider_families = {
        source.provider_family
        for source in sources
        if source.source_type == "official_docs"
    }
    missing = sorted(REQUIRED_PROVIDER_FAMILIES - provider_families)
    checks.append(
        GateCheck(
            name="required_provider_families_have_official_sources",
            ok=not missing,
            detail="all required families present" if not missing else ", ".join(missing),
        )
    )

    source_field_errors: list[str] = []
    for source in sources:
        for field_name in (
            "source_id",
            "provider_family",
            "api_surface",
            "source_title",
            "source_url",
            "access_date",
            "source_type",
            "evidence_status",
        ):
            value = str(getattr(source, field_name))
            if not value.strip() or value.startswith("TODO("):
                source_field_errors.append(f"{source.source_id}:{field_name}")
        if source.source_type != "official_docs":
            source_field_errors.append(f"{source.source_id}:source_type")
        if source.evidence_status not in ALLOWED_EVIDENCE_STATUS:
            source_field_errors.append(f"{source.source_id}:evidence_status")
    checks.append(
        GateCheck(
            name="source_entries_have_required_fields",
            ok=not source_field_errors,
            detail="all source fields present"
            if not source_field_errors
            else ", ".join(source_field_errors),
        )
    )

    claim_errors: list[str] = []
    for family in sorted(REQUIRED_PROVIDER_FAMILIES):
        family_sources = [source for source in sources if source.provider_family == family]
        if family_sources and all(
            source.evidence_status == "deferred" for source in family_sources
        ):
            continue
        if not any(source.claims for source in family_sources):
            claim_errors.append(family)
    checks.append(
        GateCheck(
            name="required_provider_families_have_claims",
            ok=not claim_errors,
            detail="all required families have claims"
            if not claim_errors
            else ", ".join(claim_errors),
        )
    )
    return checks


def _matrix_freshness_check(root: Path) -> GateCheck:
    matrix_path = root / "docs" / "provider_matrix.md"
    try:
        current = matrix_path.read_text(encoding="utf-8")
        generated = generate_provider_matrix(root)
    except (OSError, ValueError) as exc:
        return GateCheck(
            name="provider_matrix_generated_and_up_to_date",
            ok=False,
            detail=str(exc),
        )
    return GateCheck(
        name="provider_matrix_generated_and_up_to_date",
        ok=current == generated,
        detail="up to date" if current == generated else "matrix is stale",
    )


def _matrix_validation_checks(root: Path) -> list[GateCheck]:
    checks: list[GateCheck] = []
    try:
        validation = validate_provider_matrix(root)
    except OSError as exc:
        return [
            GateCheck(
                name="provider_matrix_evidence_backed",
                ok=False,
                detail=str(exc),
            ),
            GateCheck(
                name="provider_matrix_cells_non_blank",
                ok=False,
                detail=str(exc),
            ),
            GateCheck(
                name="provider_matrix_unknowns_explicit",
                ok=False,
                detail=str(exc),
            ),
        ]
    checks.append(
        GateCheck(
            name="provider_matrix_evidence_backed",
            ok=validation.ok,
            detail="valid" if validation.ok else "; ".join(validation.errors),
        )
    )

    try:
        rows = parse_markdown_table(root / "docs" / "provider_matrix.md")
    except ValueError as exc:
        return [
            *checks,
            GateCheck(name="provider_matrix_cells_non_blank", ok=False, detail=str(exc)),
            GateCheck(name="provider_matrix_unknowns_explicit", ok=False, detail=str(exc)),
        ]

    blank_cells = [
        f"{row.get('provider_family', 'unknown')}:{column}"
        for row in rows
        for column, value in row.items()
        if not value.strip()
    ]
    checks.append(
        GateCheck(
            name="provider_matrix_cells_non_blank",
            ok=not blank_cells,
            detail="no blank cells" if not blank_cells else ", ".join(blank_cells),
        )
    )

    ambiguous_unknowns = [
        f"{row.get('provider_family', 'unknown')}:{column}"
        for row in rows
        for column in MATRIX_SEMANTIC_COLUMNS
        if row[column] in {"unknown", "TODO(source needed)"}
    ]
    checks.append(
        GateCheck(
            name="provider_matrix_unknowns_explicit",
            ok=not ambiguous_unknowns,
            detail="unknowns are explicit"
            if not ambiguous_unknowns
            else ", ".join(ambiguous_unknowns),
        )
    )
    return checks


def _phase2_metrics_check(root: Path) -> GateCheck:
    try:
        metric_names = {entry.name for entry in load_metrics_registry(root)}
    except (OSError, ValueError) as exc:
        return GateCheck(
            name="phase2_core_metrics_registered",
            ok=False,
            detail=str(exc),
        )
    missing = sorted(REQUIRED_PHASE2_METRICS - metric_names)
    return GateCheck(
        name="phase2_core_metrics_registered",
        ok=not missing,
        detail="required metrics present" if not missing else ", ".join(missing),
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
        return GateCheck(
            name="no_forbidden_tracked_files",
            ok=False,
            detail=str(exc),
        )
    forbidden = forbidden_tracked_paths(proc.stdout.splitlines())
    return GateCheck(
        name="no_forbidden_tracked_files",
        ok=not forbidden,
        detail="no forbidden tracked files" if not forbidden else ", ".join(forbidden),
    )


if __name__ == "__main__":
    sys.exit(main())
