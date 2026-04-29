import json
from pathlib import Path

from scripts.check_p3_mock_safety_ready import check_p3_mock_safety_ready, main as check_main
from scripts.run_mock_safety_pilot import main, run_scenario
from lssa.schema.events import EventType
from lssa.schema.metrics import time_to_first_safety_signal_ms, validation_lag_chars
from lssa.tracing.safety_fixtures import MockSafetyScenario, safety_trace_for_scenario
from lssa.tracing.validator import validate_trace


def test_all_mock_safety_scenarios_emit_valid_redacted_traces() -> None:
    for scenario in MockSafetyScenario:
        events = safety_trace_for_scenario(scenario)
        validation = validate_trace(events)

        assert validation.ok, (scenario, validation.errors)
        assert any(
            event.event_type
            in {EventType.SAFETY_ANNOTATION, EventType.REFUSAL, EventType.CONTENT_FILTER}
            for event in events
        )
        assert all(event.content is None for event in events if event.event_type == EventType.CHUNK)


def test_mock_safety_metrics_are_computed_for_delayed_annotation() -> None:
    events = safety_trace_for_scenario(MockSafetyScenario.STREAMING_DELAYED_ANNOTATION)

    assert time_to_first_safety_signal_ms(events) == 80
    assert validation_lag_chars(events) == 10


def test_run_mock_safety_pilot_writes_redacted_outputs(tmp_path: Path) -> None:
    status_line = run_scenario(
        MockSafetyScenario.STREAMING_CONTENT_FILTER,
        tmp_path,
    )

    assert "status=ok" in status_line
    metrics_path = tmp_path / "streaming_content_filter" / "metrics.json"
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert payload["TTFSS_ms"] == 55
    trace_text = (tmp_path / "streaming_content_filter" / "trace.jsonl").read_text(
        encoding="utf-8"
    )
    assert "raw_prompt" not in trace_text


def test_run_mock_safety_pilot_all(tmp_path: Path) -> None:
    assert main(["--all", "--output-dir", str(tmp_path)]) == 0


def test_p3_mock_safety_ready_check_passes(capsys) -> None:
    root = Path(__file__).resolve().parents[1]

    result = check_p3_mock_safety_ready(root)
    exit_code = check_main(["--root", str(root), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result.ready
    assert result.real_safety_calls_allowed is False
    assert exit_code == 0
    assert payload["real_safety_calls_allowed"] is False
