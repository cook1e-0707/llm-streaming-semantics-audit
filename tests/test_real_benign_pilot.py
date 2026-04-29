from pathlib import Path

from lssa.adapters.base import AdapterRequest
from lssa.adapters.openai_responses import OpenAIResponsesAdapter
from lssa.schema.events import EventType, ResponseMode
from lssa.tracing.validator import validate_trace
from scripts.run_real_benign_pilot import (
    load_benign_prompts,
    main,
    run_fake_openai_pilot,
)


def test_real_pilot_defaults_to_dry_run(capsys) -> None:
    exit_code = main(["--provider", "openai_responses"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "dry-run" in captured.out
    assert "network=disabled" in captured.out


def test_real_pilot_refuses_unknown_prompt(capsys) -> None:
    exit_code = main(
        [
            "--provider",
            "openai_responses",
            "--prompt-id",
            "unknown_prompt",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "unknown benign prompt id" in captured.err


def test_real_pilot_refuses_network_without_key(monkeypatch, capsys) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    exit_code = main(["--provider", "openai_responses", "--allow-network"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "OPENAI_API_KEY is required" in captured.err
    assert "sk-" not in captured.err


def test_openai_streaming_mapping_from_fake_events() -> None:
    request = AdapterRequest(
        trace_id="fake-openai-streaming",
        prompt_id="short_text_generation",
        prompt="Write one harmless sentence.",
        response_mode=ResponseMode.STREAMING,
        model="fake-model",
    )
    adapter = OpenAIResponsesAdapter()

    events = adapter.map_streaming_events(
        request,
        [
            {"type": "response.created"},
            {"type": "response.output_text.delta", "delta": "Hello"},
            {"type": "response.output_text.delta", "delta": " world"},
            {"type": "response.completed"},
        ],
    )

    assert validate_trace(events).ok
    assert [event.event_type for event in events].count(EventType.CHUNK) == 2
    assert any(
        event.metadata.get("raw_event_type") == "response.output_text.delta"
        for event in events
    )


def test_openai_nonstreaming_mapping_from_fake_response() -> None:
    request = AdapterRequest(
        trace_id="fake-openai-nonstreaming",
        prompt_id="short_text_generation",
        prompt="Write one harmless sentence.",
        response_mode=ResponseMode.NON_STREAMING,
        model="fake-model",
    )
    adapter = OpenAIResponsesAdapter()

    events = adapter.map_nonstreaming_response(
        request,
        {"output_text": "A careful trace records events in order."},
    )

    assert validate_trace(events).ok
    assert [event.event_type for event in events] == [
        EventType.REQUEST_START,
        EventType.REQUEST_SENT,
        EventType.FIRST_BYTE,
        EventType.FINAL_RESPONSE,
        EventType.ITERATOR_END,
        EventType.SETTLED,
    ]


def test_fake_openai_pilot_writes_valid_trace(tmp_path: Path) -> None:
    prompt = load_benign_prompts()["short_text_generation"]

    ok, trace_path, summary_path = run_fake_openai_pilot(
        prompt=prompt,
        mode=ResponseMode.STREAMING,
        raw_events_or_response=[
            {"type": "response.output_text.delta", "delta": "Hello"},
            {"type": "response.completed"},
        ],
        output_dir=tmp_path,
    )

    assert ok
    assert trace_path.exists()
    assert summary_path.exists()
