import json
from pathlib import Path

from scripts import run_p3_overnight_batch as batch


def test_p3_overnight_dry_run_builds_redacted_manifest(tmp_path: Path) -> None:
    prompt_root = tmp_path / "source"
    _write_safety_jsonl(prompt_root / "sample.jsonl")
    output_root = Path("artifacts/test_p3_overnight")

    exit_code = batch.main(
        [
            "--providers",
            "openai_responses",
            "--modes",
            "streaming",
            "--prompt-root",
            str(prompt_root),
            "--limit-per-provider-mode",
            "1",
            "--judge-limit",
            "1",
            "--output-root",
            str(output_root),
            "--run-id",
            "unit-dry-run",
        ]
    )

    assert exit_code == 0
    manifest = json.loads((output_root / "unit-dry-run" / "manifest.json").read_text(encoding="utf-8"))
    serialized = json.dumps(manifest)
    assert manifest["allow_network"] is False
    assert manifest["raw_text_committed"] is False
    assert manifest["tasks"][0]["name"] == "safety_openai_responses_streaming"
    assert "redacted test prompt body" not in serialized


def test_p3_overnight_large_run_requires_force(tmp_path: Path) -> None:
    prompt_root = tmp_path / "source"
    _write_safety_jsonl(prompt_root / "sample.jsonl")

    exit_code = batch.main(
        [
            "--providers",
            "openai_responses",
            "--modes",
            "streaming",
            "--prompt-root",
            str(prompt_root),
            "--limit-per-provider-mode",
            "4",
            "--judge-limit",
            "0",
        ]
    )

    assert exit_code == 2


def test_p3_overnight_summary_counts_redacted_outputs(tmp_path: Path) -> None:
    run_root = Path("artifacts/test_p3_overnight_summary")
    summary_dir = run_root / "safety_signal" / "openai_responses" / "prompt" / "streaming"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "trace.summary.json").write_text(
        json.dumps(
            {
                "terminal_reason": "completed",
                "events": [
                    {"event_type": "request_start"},
                    {
                        "event_type": "final_response",
                        "metadata": {"provider_stop_reason": "stop"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    judge_dir = run_root / "judge_adjudication"
    judge_dir.mkdir(parents=True, exist_ok=True)
    (judge_dir / "judge-a.json").write_text(
        json.dumps({"label": "unsafe", "raw_response_committed": False}),
        encoding="utf-8",
    )

    path = batch._write_summary(run_root)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["raw_text_committed"] is False
    assert payload["safety_trace_count"] == 1
    assert payload["judge_result_count"] == 1
    assert payload["trace_terminal_reasons"] == {"completed": 1}
    assert payload["terminal_reasons"] == {"completed": 1}
    assert payload["event_terminal_reason_counts"] == {}
    assert payload["provider_stop_reasons"] == {"stop": 1}
    assert payload["judge_labels"] == {"unsafe": 1}


def test_p3_overnight_summary_counts_response_judges(tmp_path: Path) -> None:
    run_root = Path("artifacts/test_p3_response_judge_summary")
    response_judge_dir = run_root / "response_judge" / "openai_responses" / "prompt" / "streaming"
    response_judge_dir.mkdir(parents=True, exist_ok=True)
    (response_judge_dir / "response-judge-a.json").write_text(
        json.dumps(
            {
                "judge_subject": "provider_final_response",
                "judge_profile": "a",
                "label": "unsafe",
                "raw_provider_output_committed": False,
            }
        ),
        encoding="utf-8",
    )

    path = batch._write_summary(run_root)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["response_judge_result_count"] == 1
    assert payload["response_judge_labels"] == {"unsafe": 1}


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
