import json
from pathlib import Path

from lssa.judging.nvidia import (
    NvidiaGuardJudge,
    NvidiaJudgeConfig,
    parse_guard_label,
)
from scripts.check_judge_ready import check_judge_ready, main as check_main
from scripts.run_judge_adjudication import main as judge_main


def test_parse_guard_label() -> None:
    assert parse_guard_label("safe") == "safe"
    assert parse_guard_label("unsafe: violence") == "unsafe"
    assert parse_guard_label("policy violation") == "unsafe"
    assert parse_guard_label("") == "unknown"


def test_nvidia_judge_with_fake_client_returns_redacted_result() -> None:
    class FakeCompletions:
        def create(self, **kwargs):
            return {"choices": [{"message": {"content": "unsafe: redacted_category"}}]}

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    judge = NvidiaGuardJudge(
        config=NvidiaJudgeConfig(model="fake-guard-model"),
        client=FakeClient(),
    )

    result = judge.classify_prompt(
        prompt_id="safety-test-1",
        prompt_text="redacted test prompt body",
    )
    payload = result.to_redacted_dict()

    assert payload["label"] == "unsafe"
    assert payload["judge_model"] == "fake-guard-model"
    assert "redacted test prompt body" not in json.dumps(payload)


def test_judge_dry_run_writes_redacted_plan(tmp_path: Path) -> None:
    prompt_root = tmp_path / "source"
    plan_dir = Path("artifacts/test_judge_plan")
    _write_safety_jsonl(prompt_root / "sample.jsonl")

    exit_code = judge_main(
        [
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
    assert payload["judge_api_key_env"] == "NVIDIA_API_KEY_A"
    assert "redacted test prompt body" not in serialized


def test_judge_requires_network_opt_in_before_loading_text(
    tmp_path: Path,
    monkeypatch,
) -> None:
    prompt_root = tmp_path / "source"
    _write_safety_jsonl(prompt_root / "sample.jsonl")
    include_text_values = []

    real_loader = __import__(
        "scripts.run_judge_adjudication",
        fromlist=["iter_safety_prompt_records"],
    ).iter_safety_prompt_records

    def wrapped_loader(*args, **kwargs):
        include_text_values.append(kwargs.get("include_text"))
        return real_loader(*args, **kwargs)

    monkeypatch.setenv("NVIDIA_API_KEY_A", "nvapi-not-printed")
    monkeypatch.setattr(
        "scripts.run_judge_adjudication.iter_safety_prompt_records",
        wrapped_loader,
    )

    exit_code = judge_main(
        [
            "--prompt-root",
            str(prompt_root),
            "--limit",
            "1",
            "--max-calls",
            "1",
            "--allow-judge-network",
            "--allow-safety-prompts",
        ]
    )

    assert exit_code == 2
    assert include_text_values == [False]


def test_judge_ready_with_temp_prompt_root(tmp_path: Path, capsys) -> None:
    prompt_root = tmp_path / "source"
    _write_safety_jsonl(prompt_root / "sample.jsonl")
    repo_root = Path(__file__).resolve().parents[1]

    result = check_judge_ready(repo_root, prompt_root)
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
    assert result.judge_network_allowed_by_default is False
    assert exit_code == 0
    assert payload["judge_network_allowed_by_default"] is False


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
