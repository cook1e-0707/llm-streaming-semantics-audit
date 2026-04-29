import json
from pathlib import Path

from lssa.prompts.safety_external import (
    inventory_safety_prompt_root,
    iter_safety_prompt_records,
)
from scripts.check_p3_safety_pilot_ready import check_p3_safety_pilot_ready, main as check_main
from scripts.inspect_external_safety_prompts import main as inspect_main
from scripts.run_safety_signal_pilot import main as pilot_main


def test_external_safety_inventory_is_redacted(tmp_path: Path) -> None:
    _write_safety_jsonl(tmp_path / "sample.jsonl")

    inventory = inventory_safety_prompt_root(tmp_path)
    records = iter_safety_prompt_records(tmp_path, include_text=False, limit=1)

    assert inventory.file_count == 1
    assert inventory.prompt_record_count == 1
    assert records[0].prompt_text is None
    assert records[0].to_redacted_dict()["raw_text_committed"] is False


def test_external_safety_loader_can_load_text_only_when_requested(tmp_path: Path) -> None:
    _write_safety_jsonl(tmp_path / "sample.jsonl")

    redacted = iter_safety_prompt_records(tmp_path, include_text=False, limit=1)
    loaded = iter_safety_prompt_records(tmp_path, include_text=True, limit=1)

    assert redacted[0].prompt_text is None
    assert loaded[0].prompt_text == "redacted test prompt body"


def test_inspect_external_safety_prompts_does_not_print_prompt_text(
    tmp_path: Path,
    capsys,
) -> None:
    _write_safety_jsonl(tmp_path / "sample.jsonl")

    exit_code = inspect_main(["--root", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "raw_prompt_text_printed=no" in captured.out
    assert "redacted test prompt body" not in captured.out


def test_safety_signal_pilot_dry_run_writes_redacted_plan(tmp_path: Path) -> None:
    prompt_root = tmp_path / "source"
    plan_dir = Path("artifacts/test_safety_signal_plan")
    _write_safety_jsonl(prompt_root / "sample.jsonl")

    exit_code = pilot_main(
        [
            "--provider",
            "openai_responses",
            "--prompt-root",
            str(prompt_root),
            "--limit",
            "1",
            "--max-calls",
            "1",
            "--plan-dir",
            str(plan_dir),
        ]
    )

    assert exit_code == 0
    plan_path = sorted(plan_dir.glob("*.json"))[-1]
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    serialized = json.dumps(payload)
    assert payload["raw_text_in_plan"] is False
    assert "redacted test prompt body" not in serialized


def test_safety_signal_pilot_requires_safety_opt_in_for_network(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    prompt_root = tmp_path / "source"
    _write_safety_jsonl(prompt_root / "sample.jsonl")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-printed")

    exit_code = pilot_main(
        [
            "--provider",
            "openai_responses",
            "--prompt-root",
            str(prompt_root),
            "--limit",
            "1",
            "--max-calls",
            "1",
            "--allow-network",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--allow-safety-prompts" in captured.err
    assert "sk-not-printed" not in captured.err


def test_safety_signal_pilot_requires_review_before_loading_prompt_text(
    tmp_path: Path,
    monkeypatch,
) -> None:
    prompt_root = tmp_path / "source"
    _write_safety_jsonl(prompt_root / "sample.jsonl")
    include_text_values = []

    real_loader = __import__(
        "scripts.run_safety_signal_pilot",
        fromlist=["iter_safety_prompt_records"],
    ).iter_safety_prompt_records

    def wrapped_loader(*args, **kwargs):
        include_text_values.append(kwargs.get("include_text"))
        return real_loader(*args, **kwargs)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-printed")
    monkeypatch.setattr(
        "scripts.run_safety_signal_pilot.iter_safety_prompt_records",
        wrapped_loader,
    )

    exit_code = pilot_main(
        [
            "--provider",
            "openai_responses",
            "--prompt-root",
            str(prompt_root),
            "--limit",
            "1",
            "--max-calls",
            "1",
            "--allow-network",
            "--allow-safety-prompts",
        ]
    )

    assert exit_code == 2
    assert include_text_values == [False]


def test_p3_safety_pilot_ready_with_temp_prompt_root(tmp_path: Path, capsys) -> None:
    prompt_root = tmp_path / "source"
    _write_safety_jsonl(prompt_root / "sample.jsonl")
    repo_root = Path(__file__).resolve().parents[1]

    result = check_p3_safety_pilot_ready(repo_root, prompt_root)
    exit_code = check_main(
        [
            "--root",
            str(repo_root),
            "--prompt-root",
            str(prompt_root),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result.ready
    assert result.real_safety_calls_allowed_by_default is False
    assert exit_code == 0
    assert payload["real_safety_calls_allowed_by_default"] is False


def _write_safety_jsonl(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "prompt_id": "safety-test-1",
                "prompt": "redacted test prompt body",
                "benchmark": "unit_test",
                "semantic_category": "redacted_category",
                "language": "en",
            }
        )
        + "\n",
        encoding="utf-8",
    )
