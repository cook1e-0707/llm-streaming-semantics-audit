#!/usr/bin/env python3
"""Validate provider documentation matrix placeholders and evidence files."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

REQUIRED_COLUMNS = [
    "provider_family",
    "api_surface",
    "response_mode",
    "release_policy",
    "moderation_timing",
    "safety_signal_surface",
    "validation_watermark",
    "refusal_semantics",
    "settlement_semantics",
    "client_obligations",
    "evidence_file",
    "evidence_status",
]
SEMANTICS_COLUMNS = [
    "api_surface",
    "response_mode",
    "release_policy",
    "moderation_timing",
    "safety_signal_surface",
    "validation_watermark",
    "refusal_semantics",
    "settlement_semantics",
    "client_obligations",
]
UNKNOWN_VALUES = {"unknown", "TODO(source needed)"}
ALLOWED_EVIDENCE_STATUS = {
    "TODO(source needed)",
    "unknown",
    "partial",
    "supported",
}


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

        evidence_file = row.get("evidence_file", "")
        if evidence_file:
            evidence_path = root / evidence_file
            if not evidence_path.exists():
                errors.append(f"{provider}: evidence file does not exist: {evidence_file}")

        if evidence_status in {"TODO(source needed)", "unknown"}:
            for column in SEMANTICS_COLUMNS:
                value = row.get(column, "")
                if value not in UNKNOWN_VALUES:
                    errors.append(
                        f"{provider}: {column} is filled without evidence status"
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
