"""Provider documentation evidence parsing and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALLOWED_CONFIDENCE = {"high", "medium", "low", "unknown"}
ALLOWED_EVIDENCE_STATUS = {"complete", "partial", "TODO(source needed)", "unknown"}
ALLOWED_SOURCE_TYPES = {"official_docs"}
UNKNOWN_FIELD_VALUES = {"unknown_from_official_docs", "not_documented_in_source"}
MATRIX_SEMANTIC_COLUMNS = [
    "response_mode",
    "release_policy",
    "moderation_timing",
    "safety_signal_surface",
    "validation_watermark",
    "refusal_semantics",
    "settlement_semantics",
    "client_obligations",
    "documented_limit_or_bound",
]
CLAIM_SCOPE_VALUES = set(MATRIX_SEMANTIC_COLUMNS)
REQUIRED_SOURCE_FIELDS = {
    "source_id",
    "provider_family",
    "api_surface",
    "source_title",
    "source_url",
    "access_date",
    "source_last_updated",
    "source_type",
    "evidence_status",
    "claims",
}
REQUIRED_CLAIM_FIELDS = {
    "claim_id",
    "claim_scope",
    "short_excerpt",
    "paraphrase",
    "extracted_semantics",
    "confidence",
    "open_questions",
}


@dataclass(frozen=True)
class EvidenceClaim:
    claim_id: str
    claim_scope: tuple[str, ...]
    short_excerpt: str
    paraphrase: str
    extracted_semantics: dict[str, str]
    confidence: str
    open_questions: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    provider_family: str
    api_surface: str
    source_title: str
    source_url: str
    access_date: str
    source_last_updated: str
    source_type: str
    evidence_status: str
    claims: tuple[EvidenceClaim, ...]


def load_provider_evidence(root: Path) -> list[EvidenceSource]:
    return parse_provider_evidence_yaml(root / "docs" / "provider_evidence.yaml")


def parse_provider_evidence_yaml(path: Path) -> list[EvidenceSource]:
    """Parse the repository's constrained provider evidence YAML format."""

    raw_sources = _parse_sources(path)
    return [_source_from_mapping(source) for source in raw_sources]


def validate_provider_evidence(sources: list[EvidenceSource]) -> list[str]:
    errors: list[str] = []
    source_ids: set[str] = set()
    claim_ids: set[str] = set()

    for source in sources:
        if source.source_id in source_ids:
            errors.append(f"duplicate source_id: {source.source_id}")
        source_ids.add(source.source_id)

        if source.source_type not in ALLOWED_SOURCE_TYPES:
            errors.append(
                f"{source.source_id}: invalid source_type {source.source_type!r}"
            )
        if source.evidence_status not in ALLOWED_EVIDENCE_STATUS:
            errors.append(
                f"{source.source_id}: invalid evidence_status "
                f"{source.evidence_status!r}"
            )
        for field_name in REQUIRED_SOURCE_FIELDS - {"claims"}:
            if not getattr(source, field_name).strip():
                errors.append(f"{source.source_id}: blank source field {field_name}")

        for claim in source.claims:
            claim_key = f"{source.source_id}:{claim.claim_id}"
            if claim_key in claim_ids:
                errors.append(f"duplicate claim_id in source: {claim_key}")
            claim_ids.add(claim_key)

            if claim.confidence not in ALLOWED_CONFIDENCE:
                errors.append(
                    f"{claim_key}: invalid confidence {claim.confidence!r}"
                )
            if not claim.claim_scope:
                errors.append(f"{claim_key}: empty claim_scope")
            unsupported_scope = set(claim.claim_scope) - CLAIM_SCOPE_VALUES
            if unsupported_scope:
                errors.append(
                    f"{claim_key}: unsupported claim_scope "
                    f"{sorted(unsupported_scope)}"
                )
            unsupported_semantics = (
                set(claim.extracted_semantics) - set(MATRIX_SEMANTIC_COLUMNS)
            )
            if unsupported_semantics:
                errors.append(
                    f"{claim_key}: unsupported extracted_semantics "
                    f"{sorted(unsupported_semantics)}"
                )
            for field_name in claim.claim_scope:
                value = claim.extracted_semantics.get(field_name, "")
                if not value.strip():
                    errors.append(
                        f"{claim_key}: claim_scope field lacks extracted value "
                        f"{field_name}"
                    )

    return errors


def supported_semantics_by_source(
    sources: list[EvidenceSource],
) -> dict[str, dict[str, set[str]]]:
    supported: dict[str, dict[str, set[str]]] = {}
    for source in sources:
        source_support: dict[str, set[str]] = {
            column: set() for column in MATRIX_SEMANTIC_COLUMNS
        }
        for claim in source.claims:
            for column in claim.claim_scope:
                value = claim.extracted_semantics.get(column, "").strip()
                if value and value not in UNKNOWN_FIELD_VALUES:
                    source_support[column].add(value)
        supported[source.source_id] = source_support
    return supported


def _parse_sources(path: Path) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    current_source: dict[str, Any] | None = None
    current_claim: dict[str, Any] | None = None
    current_list_key: str | None = None
    in_extracted_semantics = False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line == "sources:":
            continue
        if raw_line.startswith("  - source_id: "):
            current_source = {
                "source_id": _parse_scalar(raw_line.split(": ", 1)[1])
            }
            sources.append(current_source)
            current_claim = None
            current_list_key = None
            in_extracted_semantics = False
            continue
        if current_source is None:
            raise ValueError(f"Unexpected line before first source: {raw_line}")

        if raw_line.startswith("    claims:"):
            current_source["claims"] = []
            current_claim = None
            current_list_key = None
            in_extracted_semantics = False
            continue

        if raw_line.startswith("    ") and not raw_line.startswith("      "):
            key, value = _split_key_value(raw_line.strip())
            current_source[key] = _parse_scalar(value)
            current_claim = None
            current_list_key = None
            in_extracted_semantics = False
            continue

        if raw_line.startswith("      - claim_id: "):
            current_claim = {
                "claim_id": _parse_scalar(raw_line.split(": ", 1)[1])
            }
            current_source.setdefault("claims", []).append(current_claim)
            current_list_key = None
            in_extracted_semantics = False
            continue
        if current_claim is None:
            raise ValueError(f"Unexpected line before first claim: {raw_line}")

        if raw_line.startswith("        extracted_semantics:"):
            current_claim["extracted_semantics"] = {}
            current_list_key = None
            in_extracted_semantics = True
            continue

        if raw_line.startswith("        ") and not raw_line.startswith("          "):
            stripped = raw_line.strip()
            if stripped.endswith(":"):
                current_list_key = stripped[:-1]
                current_claim[current_list_key] = []
                in_extracted_semantics = False
                continue
            key, value = _split_key_value(stripped)
            current_claim[key] = _parse_scalar(value)
            current_list_key = None
            in_extracted_semantics = False
            continue

        if raw_line.startswith("          - "):
            if current_list_key is None:
                raise ValueError(f"List item without list key: {raw_line}")
            values = current_claim[current_list_key]
            if not isinstance(values, list):
                raise ValueError(f"List key reused as scalar: {current_list_key}")
            values.append(_parse_scalar(raw_line.split("- ", 1)[1]))
            continue

        if raw_line.startswith("          ") and in_extracted_semantics:
            key, value = _split_key_value(raw_line.strip())
            semantics = current_claim["extracted_semantics"]
            if not isinstance(semantics, dict):
                raise ValueError("extracted_semantics must be a mapping")
            semantics[key] = _parse_scalar(value)
            continue

        raise ValueError(f"Unsupported provider evidence line: {raw_line}")

    return sources


def _source_from_mapping(entry: dict[str, Any]) -> EvidenceSource:
    missing = REQUIRED_SOURCE_FIELDS - set(entry)
    if missing:
        raise ValueError(f"Provider evidence source missing keys: {sorted(missing)}")
    return EvidenceSource(
        source_id=str(entry["source_id"]),
        provider_family=str(entry["provider_family"]),
        api_surface=str(entry["api_surface"]),
        source_title=str(entry["source_title"]),
        source_url=str(entry["source_url"]),
        access_date=str(entry["access_date"]),
        source_last_updated=str(entry["source_last_updated"]),
        source_type=str(entry["source_type"]),
        evidence_status=str(entry["evidence_status"]),
        claims=tuple(_claim_from_mapping(claim) for claim in _as_mapping_list(entry["claims"])),
    )


def _claim_from_mapping(entry: dict[str, Any]) -> EvidenceClaim:
    missing = REQUIRED_CLAIM_FIELDS - set(entry)
    if missing:
        raise ValueError(f"Provider evidence claim missing keys: {sorted(missing)}")
    extracted = entry["extracted_semantics"]
    if not isinstance(extracted, dict):
        raise ValueError("extracted_semantics must be a mapping")
    return EvidenceClaim(
        claim_id=str(entry["claim_id"]),
        claim_scope=tuple(_as_string_list(entry["claim_scope"])),
        short_excerpt=str(entry["short_excerpt"]),
        paraphrase=str(entry["paraphrase"]),
        extracted_semantics={str(key): str(value) for key, value in extracted.items()},
        confidence=str(entry["confidence"]),
        open_questions=tuple(_as_string_list(entry["open_questions"])),
    )


def _split_key_value(value: str) -> tuple[str, str]:
    if ": " not in value:
        raise ValueError(f"Expected key/value line: {value}")
    return value.split(": ", 1)


def _parse_scalar(value: str) -> Any:
    stripped = value.strip()
    if stripped == "[]":
        return []
    if (
        (stripped.startswith('"') and stripped.endswith('"'))
        or (stripped.startswith("'") and stripped.endswith("'"))
    ):
        return stripped[1:-1]
    return stripped


def _as_mapping_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"Expected list value, got {type(value).__name__}")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError("Expected list of mappings")
    return value


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"Expected list value, got {type(value).__name__}")
    return [str(item) for item in value]
