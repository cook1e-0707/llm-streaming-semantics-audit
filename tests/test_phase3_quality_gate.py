import json
from pathlib import Path

from scripts.check_phase3_ready import (
    check_phase3_ready,
    main,
    _forbidden_tracked_files_check,
    _safety_prompt_registry_check,
)


def test_repository_phase3_policy_gate_passes_but_p3m2_remains_blocked() -> None:
    root = Path(__file__).resolve().parents[1]

    result = check_phase3_ready(root)

    assert result.ready, result.checks
    assert result.p3m2_allowed is False
    assert any(check.name == "phase3_progress_state" for check in result.checks)


def test_phase3_policy_gate_json_output(capsys) -> None:
    root = Path(__file__).resolve().parents[1]

    exit_code = main(["--root", str(root), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["ready"] is True
    assert payload["p3m2_allowed"] is False


def test_safety_prompt_registry_rejects_raw_text_fields(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "safety_prompt_registry.example.yaml").write_text(
        "prompts:\n  - prompt_id: x\n    raw_prompt: redacted-placeholder\n",
        encoding="utf-8",
    )

    check = _safety_prompt_registry_check(tmp_path)

    assert check.ok is False
    assert "raw_prompt:" in check.detail


def test_forbidden_tracked_files_detects_safety_prompt_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class FakeProc:
        stdout = "safety_prompts/raw/example.txt\n"

    def fake_run(*args, **kwargs):
        return FakeProc()

    monkeypatch.setattr("subprocess.run", fake_run)

    check = _forbidden_tracked_files_check(tmp_path)

    assert check.ok is False
    assert "safety_prompts/raw/example.txt" in check.detail
