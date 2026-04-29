#!/usr/bin/env python3
"""Generate provider documentation matrix from evidence registry."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from .provider_evidence import (
        MATRIX_SEMANTIC_COLUMNS,
        UNKNOWN_FIELD_VALUES,
        EvidenceClaim,
        EvidenceSource,
        load_provider_evidence,
        validate_provider_evidence,
    )
except ImportError:
    from provider_evidence import (
        MATRIX_SEMANTIC_COLUMNS,
        UNKNOWN_FIELD_VALUES,
        EvidenceClaim,
        EvidenceSource,
        load_provider_evidence,
        validate_provider_evidence,
    )

MATRIX_COLUMNS = [
    "provider_family",
    "api_surface",
    *MATRIX_SEMANTIC_COLUMNS,
    "source_id",
    "evidence_status",
    "confidence",
]
UNKNOWN_VALUE = "unknown_from_official_docs"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if matrix is stale")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )
    args = parser.parse_args(argv)

    matrix_path = args.root / "docs" / "provider_matrix.md"
    generated = generate_provider_matrix(args.root)

    if args.check:
        current = matrix_path.read_text(encoding="utf-8")
        if current != generated:
            print("docs/provider_matrix.md is stale; run python scripts/generate_provider_matrix.py")
            return 1
        print("docs/provider_matrix.md is up to date")
        return 0

    matrix_path.write_text(generated, encoding="utf-8")
    print("Updated docs/provider_matrix.md")
    return 0


def generate_provider_matrix(root: Path) -> str:
    sources = load_provider_evidence(root)
    errors = validate_provider_evidence(sources)
    if errors:
        raise ValueError("Invalid provider evidence:\n" + "\n".join(errors))

    rows = [
        "# Provider Documentation Matrix",
        "",
        "This matrix is generated from `docs/provider_evidence.yaml`. Do not edit",
        "the table by hand; update the evidence registry and run",
        "`python scripts/generate_provider_matrix.py`.",
        "",
        "Unsupported fields are rendered as `unknown_from_official_docs` until",
        "an official documentation claim supports a more specific value.",
        "",
        "| " + " | ".join(MATRIX_COLUMNS) + " |",
        "| " + " | ".join("---" for _ in MATRIX_COLUMNS) + " |",
    ]
    for source in sources:
        rows.append(_source_to_matrix_row(source))
    rows.append("")
    return "\n".join(rows)


def _source_to_matrix_row(source: EvidenceSource) -> str:
    values = {
        "provider_family": source.provider_family,
        "api_surface": source.api_surface,
        "source_id": source.source_id,
        "evidence_status": source.evidence_status,
        "confidence": _row_confidence(source.claims),
    }
    for column in MATRIX_SEMANTIC_COLUMNS:
        values[column] = _semantic_value(source.claims, column)
    return "| " + " | ".join(values[column] for column in MATRIX_COLUMNS) + " |"


def _semantic_value(claims: tuple[EvidenceClaim, ...], column: str) -> str:
    supported = []
    for claim in claims:
        if column not in claim.claim_scope:
            continue
        value = claim.extracted_semantics.get(column, "").strip()
        if value and value not in UNKNOWN_FIELD_VALUES:
            supported.append(value)
    if not supported:
        return UNKNOWN_VALUE
    return "; ".join(dict.fromkeys(supported))


def _row_confidence(claims: tuple[EvidenceClaim, ...]) -> str:
    if not claims:
        return "unknown"
    confidences = {claim.confidence for claim in claims}
    for value in ("low", "medium", "high"):
        if value in confidences:
            return value
    return "unknown"


if __name__ == "__main__":
    sys.exit(main())
