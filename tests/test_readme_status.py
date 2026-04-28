from pathlib import Path

from scripts.update_readme_status import (
    METRICS_REGISTRY_END,
    METRICS_REGISTRY_START,
    PROJECT_TREE_END,
    PROJECT_TREE_START,
    generate_metrics_registry,
    generate_project_tree,
    parse_metrics_markdown,
    replace_section,
    update_readme_text,
)


def test_parse_metrics_markdown_extracts_registry_entries(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.md"
    metrics_path.write_text(
        "\n".join(
            [
                "# Metrics",
                "",
                "## TTFB_ms",
                "",
                "- Status: implemented",
                "- Definition: elapsed milliseconds from request start.",
            ]
        ),
        encoding="utf-8",
    )

    entries = parse_metrics_markdown(metrics_path)

    assert entries[0].name == "TTFB_ms"
    assert entries[0].status == "implemented"
    assert entries[0].definition == "elapsed milliseconds from request start."


def test_generate_project_tree_skips_local_outputs(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "metrics.md").write_text("# Metrics\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".venv").mkdir()
    (tmp_path / "results").mkdir()
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "src").mkdir()

    tree = generate_project_tree(tmp_path)

    assert ".git" not in tree
    assert ".venv" not in tree
    assert "results" not in tree
    assert "raw" not in tree
    assert "docs/" in tree
    assert "src/" in tree


def test_generate_metrics_registry_renders_table(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "metrics.md").write_text(
        "\n".join(
            [
                "# Metrics",
                "",
                "## TTFT_ms",
                "",
                "- Status: implemented",
                "- Definition: elapsed milliseconds to first token.",
            ]
        ),
        encoding="utf-8",
    )

    registry = generate_metrics_registry(tmp_path)

    assert "| Metric | Status | Definition |" in registry
    assert "`TTFT_ms`" in registry
    assert "elapsed milliseconds to first token." in registry


def test_update_readme_text_replaces_generated_sections(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "metrics.md").write_text(
        "\n".join(
            [
                "# Metrics",
                "",
                "## settlement_lag_ms",
                "",
                "- Status: implemented",
                "- Definition: elapsed milliseconds to settlement.",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Example\n", encoding="utf-8")
    stale = "\n".join(
        [
            "# Example",
            "",
            PROJECT_TREE_START,
            "stale tree",
            PROJECT_TREE_END,
            "",
            METRICS_REGISTRY_START,
            "stale metrics",
            METRICS_REGISTRY_END,
            "",
        ]
    )

    updated = update_readme_text(stale, tmp_path)

    assert "stale tree" not in updated
    assert "stale metrics" not in updated
    assert "settlement_lag_ms" in updated


def test_replace_section_requires_exactly_one_marker_pair() -> None:
    text = "no generated sections"

    try:
        replace_section(text, PROJECT_TREE_START, PROJECT_TREE_END, "body")
    except ValueError as exc:
        assert "Expected exactly one section" in str(exc)
    else:
        raise AssertionError("replace_section should reject missing markers")
