import json
from pathlib import Path

from scripts.check_phase1_ready import (
    check_phase1_ready,
    forbidden_tracked_paths,
    main,
)


def test_repository_phase1_quality_gate_passes() -> None:
    root = Path(__file__).resolve().parents[1]

    result = check_phase1_ready(root)

    assert result.ready, result.checks


def test_phase1_quality_gate_json_output(capsys) -> None:
    root = Path(__file__).resolve().parents[1]

    exit_code = main(["--root", str(root), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["ready"] is True
    assert any(
        check["name"] == "provider_matrix_evidence_backed"
        for check in payload["checks"]
    )


def test_phase1_quality_gate_fails_without_evidence_registry(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()

    result = check_phase1_ready(tmp_path)

    assert result.ready is False
    assert any(
        check.name == "provider_evidence_exists" and not check.ok
        for check in result.checks
    )


def test_forbidden_tracked_paths_detects_local_outputs() -> None:
    forbidden = forbidden_tracked_paths(
        [
            "docs/provider_matrix.md",
            "results/raw.jsonl",
            "data/raw/prompts.jsonl",
            "data/processed/events.jsonl",
            "keys/provider.pem",
        ]
    )

    assert forbidden == [
        "results/raw.jsonl",
        "data/raw/prompts.jsonl",
        "data/processed/events.jsonl",
        "keys/provider.pem",
    ]
