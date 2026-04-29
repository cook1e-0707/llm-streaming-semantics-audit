#!/usr/bin/env python3
"""Validate generated provider documentation matrix evidence backing."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from .generate_provider_matrix import MATRIX_COLUMNS
    from .provider_evidence import (
        ALLOWED_CONFIDENCE,
        ALLOWED_EVIDENCE_STATUS,
        MATRIX_SEMANTIC_COLUMNS,
        UNKNOWN_FIELD_VALUES,
        load_provider_evidence,
        supported_semantics_by_source,
        validate_provider_evidence,
    )
except ImportError:
    from generate_provider_matrix import MATRIX_COLUMNS
    from provider_evidence import (
        ALLOWED_CONFIDENCE,
        ALLOWED_EVIDENCE_STATUS,
        MATRIX_SEMANTIC_COLUMNS,
        UNKNOWN_FIELD_VALUES,
        load_provider_evidence,
        supported_semantics_by_source,
        validate_provider_evidence,
    )

REQUIRED_COLUMNS = [
    *MATRIX_COLUMNS,
]
EXPLICIT_UNKNOWN_VALUES = UNKNOWN_FIELD_VALUES | {"unknown_from_official_docs"}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: tuple[str, ...]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )
    args = parser.parse_args(argv)

    result = validate_provider_matrix(args.root)
    if not result.ok:
        for error in result.errors:
            print(error, file=sys.stderr)
        return 1
    print("Provider matrix is valid")
    return 0


def validate_provider_matrix(root: Path) -> ValidationResult:
    matrix_path = root / "docs" / "provider_matrix.md"
    errors: list[str] = []

    try:
        sources = load_provider_evidence(root)
        errors.extend(validate_provider_evidence(sources))
        source_ids = {source.source_id for source in sources}
        support_by_source = supported_semantics_by_source(sources)
    except ValueError as exc:
        return ValidationResult(ok=False, errors=(str(exc),))

    try:
        rows = parse_markdown_table(matrix_path)
    except ValueError as exc:
        return ValidationResult(ok=False, errors=(str(exc),))

    if not rows:
        errors.append("provider matrix has no provider rows")

    for row_number, row in enumerate(rows, start=1):
        provider = row.get("provider_family", f"row {row_number}")
        for column in REQUIRED_COLUMNS:
            value = row.get(column)
            if value is None:
                errors.append(f"{provider}: missing column {column}")
            elif not value.strip():
                errors.append(f"{provider}: blank value in {column}")

        evidence_status = row.get("evidence_status", "")
        if evidence_status not in ALLOWED_EVIDENCE_STATUS:
            errors.append(
                f"{provider}: invalid evidence_status {evidence_status!r}"
            )

        confidence = row.get("confidence", "")
        if confidence not in ALLOWED_CONFIDENCE:
            errors.append(f"{provider}: invalid confidence {confidence!r}")

        source_id = row.get("source_id", "")
        if source_id not in source_ids:
            errors.append(f"{provider}: source_id does not exist: {source_id}")
            continue

        for column in MATRIX_SEMANTIC_COLUMNS:
            value = row.get(column, "")
            if value in EXPLICIT_UNKNOWN_VALUES:
                continue
            supported = support_by_source[source_id].get(column, set())
            rendered_values = {part.strip() for part in value.split(";")}
            if not rendered_values <= supported:
                errors.append(
                    f"{provider}: {column} lacks supporting evidence for {value!r}"
                )

    return ValidationResult(ok=not errors, errors=tuple(errors))


def parse_markdown_table(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    table_lines = [line for line in lines if line.startswith("|")]
    if len(table_lines) < 2:
        raise ValueError("provider matrix does not contain a markdown table")

    header = _split_table_row(table_lines[0])
    if header != REQUIRED_COLUMNS:
        raise ValueError(f"provider matrix columns do not match required schema: {header}")

    separator = _split_table_row(table_lines[1])
    if len(separator) != len(header) or any(set(cell) - {"-"} for cell in separator):
        raise ValueError("provider matrix has an invalid separator row")

    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cells = _split_table_row(line)
        if len(cells) != len(header):
            raise ValueError(f"provider matrix row has wrong cell count: {line}")
        rows.append(dict(zip(header, cells, strict=True)))
    return rows


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        raise ValueError(f"invalid markdown table row: {line}")
    return [cell.strip() for cell in stripped.strip("|").split("|")]


if __name__ == "__main__":
    sys.exit(main())
