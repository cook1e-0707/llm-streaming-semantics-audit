import json
from pathlib import Path

from lssa.experiments.manifest import build_planned_runs, load_benign_batch_manifest
from scripts.check_scaled_benign_ready import check_scaled_benign_ready, main as check_main
from scripts.run_benign_batch import main, write_plan


def test_example_benign_batch_manifest_builds_expected_plan() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = load_benign_batch_manifest(
        root / "docs" / "benign_experiment_manifest.example.toml"
    )
    runs = build_planned_runs(manifest)

    assert len(runs) == 12
    assert {run.provider for run in runs} == {
        "openai_responses",
        "anthropic_messages",
        "aws_bedrock_converse",
    }
    assert {run.mode for run in runs} == {"streaming", "nonstreaming"}


def test_stop_reason_probe_manifest_uses_larger_bounded_output_budget() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = load_benign_batch_manifest(
        root / "docs" / "stop_reason_probe_manifest.example.toml"
    )
    runs = build_planned_runs(manifest)

    assert len(runs) == 6
    assert manifest.max_output_tokens == 12048
    assert manifest.timeout_seconds == 900
    assert {run.prompt_id for run in runs} == {"stop_reason_probe_long_generation"}


def test_benign_batch_dry_run_writes_redacted_plan(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "docs" / "benign_experiment_manifest.example.toml"
    plan_dir = root / "artifacts" / "test_benign_batch"

    exit_code = main(["--manifest", str(manifest_path), "--plan-dir", str(plan_dir)])

    assert exit_code == 0
    plan_files = sorted(plan_dir.glob("*.plan.json"))
    assert plan_files
    payload = json.loads(plan_files[-1].read_text(encoding="utf-8"))
    assert payload["planned_calls"] == 12
    serialized = json.dumps(payload).lower()
    assert "prompt_text" not in serialized
    assert '"text"' not in serialized


def test_benign_batch_rejects_call_count_above_cap() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "docs" / "benign_experiment_manifest.example.toml"

    exit_code = main(
        [
            "--manifest",
            str(manifest_path),
            "--plan-dir",
            str(root / "artifacts" / "test_benign_batch_cap"),
            "--max-total-calls",
            "1",
        ]
    )

    assert exit_code == 2


def test_write_plan_does_not_include_prompt_text(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = load_benign_batch_manifest(
        root / "docs" / "benign_experiment_manifest.example.toml"
    )
    runs = build_planned_runs(manifest)

    plan_path = write_plan(tmp_path, Path("manifest.toml"), runs, allow_network=False)

    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    assert payload["allow_network"] is False
    assert all("prompt_id" in run and "text" not in run for run in payload["runs"])


def test_scaled_benign_ready_check_passes(capsys) -> None:
    root = Path(__file__).resolve().parents[1]

    result = check_scaled_benign_ready(
        root,
        root / "docs" / "benign_experiment_manifest.example.toml",
    )
    exit_code = check_main(
        [
            "--root",
            str(root),
            "--manifest",
            str(root / "docs" / "benign_experiment_manifest.example.toml"),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result.ready
    assert result.real_network_allowed_by_default is False
    assert exit_code == 0
    assert payload["real_network_allowed_by_default"] is False
