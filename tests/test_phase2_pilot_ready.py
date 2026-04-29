import json
from pathlib import Path

from scripts.check_phase2_pilot_ready import check_phase2_pilot_ready, main
from scripts.run_mock_pilot import main as mock_pilot_main


def test_repository_phase2_pilot_ready_gate_passes() -> None:
    root = Path(__file__).resolve().parents[1]

    result = check_phase2_pilot_ready(root)

    assert result.ready, result.checks


def test_phase2_pilot_ready_json_output(capsys) -> None:
    root = Path(__file__).resolve().parents[1]

    exit_code = main(["--root", str(root), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["ready"] is True
    assert any(
        check["name"] == "mock_pilot_scenarios_pass"
        for check in payload["checks"]
    )


def test_run_mock_pilot_all_scenarios(tmp_path: Path) -> None:
    exit_code = mock_pilot_main(["--all", "--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "streaming_benign" / "trace.jsonl").exists()
    assert (tmp_path / "streaming_cancel" / "summary.json").exists()
