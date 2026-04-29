"""External safety prompt inventory and loading helpers.

Raw safety prompt text must remain outside this repository. The default helpers
return redacted metadata unless a caller explicitly requests prompt text for a
network run.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SAFETY_PROMPT_ROOT_ENV = "LSSA_SAFETY_PROMPT_ROOT"
LEGACY_PROJECT_PATH_ENV = "LEGACY_STREAMING_PROJECT_PATH"
DEFAULT_LEGACY_SAFETY_PROMPT_ROOT = Path(
    "/Users/guanjie/Documents/llm_api/streaming_or_not/"
    "streaming-vs-nonstreaming/data/safety"
)
PROMPT_TEXT_FIELDS = ("prompt", "instruction", "text", "goal", "behavior")
CATEGORY_FIELDS = ("semantic_category", "functional_category", "category", "prompt_set")


@dataclass(frozen=True)
class SafetyPromptRecord:
    prompt_id: str
    source_file: str
    line_number: int
    benchmark: str
    category: str
    language: str
    prompt_text: str | None = None

    def to_redacted_dict(self) -> dict[str, object]:
        return {
            "prompt_id": self.prompt_id,
            "source_file": self.source_file,
            "line_number": self.line_number,
            "benchmark": self.benchmark,
            "category": self.category,
            "language": self.language,
            "raw_text_committed": False,
            "raw_text_loaded": self.prompt_text is not None,
        }


@dataclass(frozen=True)
class SafetyPromptInventory:
    root: Path
    file_count: int
    prompt_record_count: int
    unsupported_record_count: int
    benchmarks: dict[str, int]
    categories: dict[str, int]
    languages: dict[str, int]

    def to_redacted_dict(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "file_count": self.file_count,
            "prompt_record_count": self.prompt_record_count,
            "unsupported_record_count": self.unsupported_record_count,
            "benchmarks": dict(sorted(self.benchmarks.items())),
            "categories": dict(sorted(self.categories.items())),
            "languages": dict(sorted(self.languages.items())),
            "raw_text_committed": False,
        }


def resolve_safety_prompt_root(root: Path | None = None) -> Path:
    if root is not None:
        return root.expanduser().resolve()
    configured = os.environ.get(SAFETY_PROMPT_ROOT_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    legacy_project = os.environ.get(LEGACY_PROJECT_PATH_ENV)
    if legacy_project:
        return (Path(legacy_project).expanduser() / "data" / "safety").resolve()
    return DEFAULT_LEGACY_SAFETY_PROMPT_ROOT


def inventory_safety_prompt_root(root: Path | None = None) -> SafetyPromptInventory:
    resolved = resolve_safety_prompt_root(root)
    if not resolved.exists():
        raise ValueError(f"safety prompt root does not exist: {resolved}")
    files = sorted(resolved.rglob("*.jsonl"))
    benchmarks: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    languages: Counter[str] = Counter()
    prompt_record_count = 0
    unsupported_record_count = 0
    for path in files:
        for record in _iter_jsonl(path):
            if _prompt_text_from_mapping(record) is None:
                unsupported_record_count += 1
                continue
            prompt_record_count += 1
            benchmarks[_string_field(record, "benchmark", default="unknown")] += 1
            categories[_category_from_mapping(record)] += 1
            languages[_string_field(record, "language", default="unknown")] += 1
    return SafetyPromptInventory(
        root=resolved,
        file_count=len(files),
        prompt_record_count=prompt_record_count,
        unsupported_record_count=unsupported_record_count,
        benchmarks=dict(benchmarks),
        categories=dict(categories),
        languages=dict(languages),
    )


def iter_safety_prompt_records(
    root: Path | None = None,
    *,
    include_text: bool = False,
    limit: int | None = None,
    source_glob: str = "*.jsonl",
    include_attack_prompt_files: bool = True,
) -> list[SafetyPromptRecord]:
    resolved = resolve_safety_prompt_root(root)
    if not resolved.exists():
        raise ValueError(f"safety prompt root does not exist: {resolved}")
    records: list[SafetyPromptRecord] = []
    for path in sorted(resolved.rglob(source_glob)):
        relative = path.relative_to(resolved)
        if not include_attack_prompt_files and "attack_prompt_files" in relative.parts:
            continue
        for line_number, payload in _iter_jsonl_with_line_numbers(path):
            prompt_text = _prompt_text_from_mapping(payload)
            if prompt_text is None:
                continue
            record = SafetyPromptRecord(
                prompt_id=_prompt_id_from_mapping(payload, relative, line_number),
                source_file=str(relative),
                line_number=line_number,
                benchmark=_string_field(payload, "benchmark", default="unknown"),
                category=_category_from_mapping(payload),
                language=_string_field(payload, "language", default="unknown"),
                prompt_text=prompt_text if include_text else None,
            )
            records.append(record)
            if limit is not None and len(records) >= limit:
                return records
    return records


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    return [payload for _, payload in _iter_jsonl_with_line_numbers(path)]


def _iter_jsonl_with_line_numbers(path: Path) -> list[tuple[int, dict[str, Any]]]:
    records: list[tuple[int, dict[str, Any]]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            payload = json.loads(raw_line)
            if isinstance(payload, dict):
                records.append((line_number, payload))
    return records


def _prompt_id_from_mapping(
    payload: dict[str, Any],
    relative_path: Path,
    line_number: int,
) -> str:
    prompt_id = payload.get("prompt_id") or payload.get("source_sample_id")
    if isinstance(prompt_id, str) and prompt_id:
        return prompt_id
    return f"{relative_path.as_posix()}:{line_number}"


def _prompt_text_from_mapping(payload: dict[str, Any]) -> str | None:
    for field_name in PROMPT_TEXT_FIELDS:
        value = payload.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _category_from_mapping(payload: dict[str, Any]) -> str:
    for field_name in CATEGORY_FIELDS:
        value = payload.get(field_name)
        if isinstance(value, str) and value:
            return value
    return "unknown"


def _string_field(payload: dict[str, Any], field_name: str, *, default: str) -> str:
    value = payload.get(field_name)
    return value if isinstance(value, str) and value else default
