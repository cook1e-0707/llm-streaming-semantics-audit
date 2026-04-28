#!/usr/bin/env python3
"""Update generated README status sections."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_TREE_START = "<!-- PROJECT_TREE_START -->"
PROJECT_TREE_END = "<!-- PROJECT_TREE_END -->"
METRICS_REGISTRY_START = "<!-- METRICS_REGISTRY_START -->"
METRICS_REGISTRY_END = "<!-- METRICS_REGISTRY_END -->"

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "results",
    "artifacts",
    "logs",
}
SKIP_RELATIVE_DIRS = {
    Path("data/raw"),
    Path("data/processed"),
}


@dataclass(frozen=True)
class MetricEntry:
    name: str
    status: str
    definition: str
    required_events: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ()
    applicable_layers: tuple[str, ...] = ()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if README is stale")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    readme_path = root / "README.md"
    current = readme_path.read_text(encoding="utf-8")
    updated = update_readme_text(current, root)

    if args.check:
        if current != updated:
            print("README.md is stale; run python scripts/update_readme_status.py")
            return 1
        print("README.md is up to date")
        return 0

    readme_path.write_text(updated, encoding="utf-8")
    print("Updated README.md")
    return 0


def update_readme_text(text: str, root: Path) -> str:
    text = replace_section(
        text,
        PROJECT_TREE_START,
        PROJECT_TREE_END,
        generate_project_tree(root),
    )
    text = replace_section(
        text,
        METRICS_REGISTRY_START,
        METRICS_REGISTRY_END,
        generate_metrics_registry(root),
    )
    return text


def replace_section(text: str, start_marker: str, end_marker: str, body: str) -> str:
    pattern = re.compile(
        rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}",
        flags=re.DOTALL,
    )
    replacement = f"{start_marker}\n{body.rstrip()}\n{end_marker}"
    updated, count = pattern.subn(replacement, text)
    if count != 1:
        raise ValueError(f"Expected exactly one section for {start_marker}")
    return updated


def generate_project_tree(root: Path) -> str:
    lines = [root.name + "/"]
    _append_tree_lines(root, root, lines, prefix="", depth=0, max_depth=4)
    return "```text\n" + "\n".join(lines) + "\n```"


def generate_metrics_registry(root: Path) -> str:
    entries = load_metrics_registry(root)
    rows = [
        "| Metric | Status | Layers | Definition |",
        "| --- | --- | --- | --- |",
    ]
    for entry in entries:
        layers = ", ".join(f"`{layer}`" for layer in entry.applicable_layers) or "unknown"
        rows.append(
            f"| `{entry.name}` | {entry.status} | {layers} | {entry.definition} |"
        )
    return "\n".join(rows)


def load_metrics_registry(root: Path) -> list[MetricEntry]:
    registry_path = root / "docs" / "metrics_registry.yaml"
    if registry_path.exists():
        return parse_metrics_registry_yaml(registry_path)
    return parse_metrics_markdown(root / "docs" / "metrics.md")


def parse_metrics_registry_yaml(path: Path) -> list[MetricEntry]:
    """Parse the repository's constrained metrics registry YAML format."""

    entries: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    current_list_key: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line == "metrics:":
            continue
        if raw_line.startswith("  - name: "):
            if current is not None:
                entries.append(current)
            current = {"name": raw_line.split(": ", 1)[1].strip()}
            current_list_key = None
            continue
        if current is None:
            raise ValueError(f"Unexpected line before first metric: {raw_line}")
        if raw_line.startswith("    ") and raw_line.strip().endswith(":"):
            current_list_key = raw_line.strip()[:-1]
            current[current_list_key] = []
            continue
        if raw_line.startswith("      - "):
            if current_list_key is None:
                raise ValueError(f"List item without list key: {raw_line}")
            values = current[current_list_key]
            if not isinstance(values, list):
                raise ValueError(f"List key reused as scalar: {current_list_key}")
            values.append(raw_line.split("- ", 1)[1].strip())
            continue
        if raw_line.startswith("    ") and ": " in raw_line:
            key, value = raw_line.strip().split(": ", 1)
            current[key] = value.strip()
            current_list_key = None
            continue
        raise ValueError(f"Unsupported metrics registry line: {raw_line}")

    if current is not None:
        entries.append(current)

    return [_metric_entry_from_mapping(entry) for entry in entries]


def parse_metrics_markdown(path: Path) -> list[MetricEntry]:
    text = path.read_text(encoding="utf-8")
    sections = re.split(r"^##\s+", text, flags=re.MULTILINE)[1:]
    entries: list[MetricEntry] = []
    for section in sections:
        lines = section.strip().splitlines()
        if not lines:
            continue
        name = lines[0].strip()
        body = "\n".join(lines[1:])
        status = _extract_bullet_value(body, "Status") or "unknown"
        definition = _extract_bullet_value(body, "Definition") or "unknown"
        entries.append(MetricEntry(name=name, status=status, definition=definition))
    return entries


def _metric_entry_from_mapping(entry: dict[str, object]) -> MetricEntry:
    required_keys = {
        "name",
        "definition",
        "required_events",
        "required_fields",
        "applicable_layers",
        "status",
    }
    missing = required_keys - set(entry)
    if missing:
        raise ValueError(f"Metric entry missing keys: {sorted(missing)}")
    status = str(entry["status"])
    if status not in {"defined", "implemented", "stub", "deprecated"}:
        raise ValueError(f"Invalid metric status for {entry['name']}: {status}")
    return MetricEntry(
        name=str(entry["name"]),
        status=status,
        definition=str(entry["definition"]),
        required_events=tuple(_as_string_list(entry["required_events"])),
        required_fields=tuple(_as_string_list(entry["required_fields"])),
        applicable_layers=tuple(_as_string_list(entry["applicable_layers"])),
    )


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"Expected list value, got {type(value).__name__}")
    return [str(item) for item in value]


def _extract_bullet_value(text: str, key: str) -> str | None:
    match = re.search(rf"^-\s+{re.escape(key)}:\s+(.+)$", text, flags=re.MULTILINE)
    if match is None:
        return None
    return match.group(1).strip()


def _append_tree_lines(
    root: Path,
    directory: Path,
    lines: list[str],
    prefix: str,
    depth: int,
    max_depth: int,
) -> None:
    if depth >= max_depth:
        return

    children = sorted(
        [child for child in directory.iterdir() if not _should_skip(root, child)],
        key=lambda child: (not child.is_dir(), child.name.lower()),
    )
    for index, child in enumerate(children):
        is_last = index == len(children) - 1
        connector = "`-- " if is_last else "|-- "
        lines.append(f"{prefix}{connector}{child.name}{'/' if child.is_dir() else ''}")
        if child.is_dir():
            next_prefix = prefix + ("    " if is_last else "|   ")
            _append_tree_lines(root, child, lines, next_prefix, depth + 1, max_depth)


def _should_skip(root: Path, path: Path) -> bool:
    if path.is_dir() and path.name in SKIP_DIR_NAMES:
        return True
    relative = path.relative_to(root)
    return path.is_dir() and relative in SKIP_RELATIVE_DIRS


if __name__ == "__main__":
    sys.exit(main())
