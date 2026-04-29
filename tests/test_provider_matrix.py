from pathlib import Path

from scripts.generate_provider_matrix import generate_provider_matrix, main as generate_main
from scripts.provider_evidence import (
    parse_provider_evidence_yaml,
    validate_provider_evidence,
)
from scripts.validate_provider_matrix import (
    parse_markdown_table,
    validate_provider_matrix,
)


def test_repository_provider_matrix_is_valid() -> None:
    root = Path(__file__).resolve().parents[1]

    result = validate_provider_matrix(root)

    assert result.ok, result.errors


def test_parse_provider_evidence_yaml_supports_placeholder_sources(
    tmp_path: Path,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_evidence_registry(docs / "provider_evidence.yaml", claims="")

    sources = parse_provider_evidence_yaml(docs / "provider_evidence.yaml")

    assert sources[0].source_id == "example_source"
    assert sources[0].evidence_status == "TODO(source needed)"
    assert sources[0].claims == ()


def test_provider_evidence_rejects_invalid_status_and_confidence(
    tmp_path: Path,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_evidence_registry(
        docs / "provider_evidence.yaml",
        evidence_status="unsupported",
        claims=_claim_yaml(confidence="unsupported"),
    )

    sources = parse_provider_evidence_yaml(docs / "provider_evidence.yaml")
    errors = validate_provider_evidence(sources)

    assert any("invalid evidence_status" in error for error in errors)
    assert any("invalid confidence" in error for error in errors)


def test_generate_provider_matrix_renders_supported_and_unknown_fields(
    tmp_path: Path,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_evidence_registry(
        docs / "provider_evidence.yaml",
        evidence_status="partial",
        claims=_claim_yaml(),
    )

    matrix = generate_provider_matrix(tmp_path)

    assert "immediate_streaming" in matrix
    assert "unknown_from_official_docs" in matrix
    assert "| Example Provider | Example API |" in matrix


def test_generate_provider_matrix_check_fails_when_stale(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_evidence_registry(docs / "provider_evidence.yaml", claims="")
    (docs / "provider_matrix.md").write_text("stale\n", encoding="utf-8")

    exit_code = generate_main(["--root", str(tmp_path), "--check"])

    assert exit_code == 1


def test_validator_rejects_non_unknown_field_without_support(
    tmp_path: Path,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_evidence_registry(docs / "provider_evidence.yaml", claims="")
    _write_matrix(
        docs / "provider_matrix.md",
        release_policy="immediate_streaming",
    )

    result = validate_provider_matrix(tmp_path)

    assert not result.ok
    assert any("lacks supporting evidence" in error for error in result.errors)


def test_validator_accepts_explicit_unknown_fields(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_evidence_registry(docs / "provider_evidence.yaml", claims="")
    _write_matrix(docs / "provider_matrix.md")

    result = validate_provider_matrix(tmp_path)

    assert result.ok, result.errors


def test_parse_markdown_table_returns_rows(tmp_path: Path) -> None:
    matrix_path = tmp_path / "provider_matrix.md"
    _write_matrix(matrix_path)

    rows = parse_markdown_table(matrix_path)

    assert rows[0]["provider_family"] == "Example Provider"
    assert rows[0]["evidence_status"] == "TODO(source needed)"
    assert rows[0]["source_id"] == "example_source"


def _write_matrix(
    path: Path,
    *,
    release_policy: str = "unknown_from_official_docs",
) -> None:
    path.write_text(
        "\n".join(
            [
                "| provider_family | api_surface | response_mode | release_policy | moderation_timing | safety_signal_surface | validation_watermark | refusal_semantics | settlement_semantics | client_obligations | documented_limit_or_bound | source_id | evidence_status | confidence |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                f"| Example Provider | Example API | unknown_from_official_docs | {release_policy} | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | unknown_from_official_docs | example_source | TODO(source needed) | unknown |",
            ]
        ),
        encoding="utf-8",
    )


def _write_evidence_registry(
    path: Path,
    *,
    evidence_status: str = "TODO(source needed)",
    claims: str,
) -> None:
    path.write_text(
        "\n".join(
            [
                "sources:",
                "  - source_id: example_source",
                "    provider_family: Example Provider",
                "    api_surface: Example API",
                "    source_title: Example Source",
                "    source_url: https://example.com/docs",
                '    access_date: "2026-04-29"',
                "    source_last_updated: unknown",
                "    source_type: official_docs",
                f"    evidence_status: {evidence_status}",
                "    claims: []" if not claims else "    claims:",
                claims.rstrip(),
            ]
        ).rstrip()
        + "\n",
        encoding="utf-8",
    )


def _claim_yaml(confidence: str = "high") -> str:
    return "\n".join(
        [
            "      - claim_id: example_claim",
            "        claim_scope:",
            "          - release_policy",
            "        short_excerpt: short official excerpt",
            "        paraphrase: official source says immediate streaming is used",
            "        extracted_semantics:",
            "          release_policy: immediate_streaming",
            f"        confidence: {confidence}",
            "        open_questions: []",
        ]
    )
