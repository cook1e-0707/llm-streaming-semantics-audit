from pathlib import Path

from scripts.validate_provider_matrix import (
    parse_markdown_table,
    validate_provider_matrix,
)


def test_repository_provider_matrix_is_valid() -> None:
    root = Path(__file__).resolve().parents[1]

    result = validate_provider_matrix(root)

    assert result.ok, result.errors


def test_validator_requires_evidence_files(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_matrix(
        docs / "provider_matrix.md",
        evidence_file="docs/source_notes/missing.md",
    )

    result = validate_provider_matrix(tmp_path)

    assert not result.ok
    assert any("evidence file does not exist" in error for error in result.errors)


def test_validator_rejects_silent_claims_without_evidence(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    source_notes = docs / "source_notes"
    source_notes.mkdir(parents=True)
    (source_notes / "provider.md").write_text("# Provider\n", encoding="utf-8")
    _write_matrix(
        docs / "provider_matrix.md",
        release_policy="immediate_streaming",
        evidence_file="docs/source_notes/provider.md",
    )

    result = validate_provider_matrix(tmp_path)

    assert not result.ok
    assert any("filled without evidence status" in error for error in result.errors)


def test_parse_markdown_table_returns_rows(tmp_path: Path) -> None:
    matrix_path = tmp_path / "provider_matrix.md"
    _write_matrix(matrix_path, evidence_file="docs/source_notes/provider.md")

    rows = parse_markdown_table(matrix_path)

    assert rows[0]["provider_family"] == "Example Provider"
    assert rows[0]["evidence_status"] == "TODO(source needed)"


def _write_matrix(
    path: Path,
    *,
    release_policy: str = "TODO(source needed)",
    evidence_file: str,
) -> None:
    path.write_text(
        "\n".join(
            [
                "| provider_family | api_surface | response_mode | release_policy | moderation_timing | safety_signal_surface | validation_watermark | refusal_semantics | settlement_semantics | client_obligations | evidence_file | evidence_status |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                f"| Example Provider | unknown | unknown | {release_policy} | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | TODO(source needed) | {evidence_file} | TODO(source needed) |",
            ]
        ),
        encoding="utf-8",
    )
