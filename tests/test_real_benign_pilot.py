import shutil
from pathlib import Path

from lssa.adapters.base import AdapterRequest
from lssa.adapters.openai_responses import OpenAIResponsesAdapter, OpenAIResponsesClient
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


def test_real_pilot_network_uses_injected_fake_client(monkeypatch, capsys) -> None:
    class FakeClient:
        def stream_response(self, request):
            return [
                {"type": "response.output_text.delta", "delta": "Hello"},
                {"type": "response.completed"},
            ]

        def create_response(self, request):
            return {"output_text": "Hello"}

    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-printed")
    monkeypatch.setattr(
        "scripts.run_real_benign_pilot.OpenAIResponsesClient",
        lambda **kwargs: FakeClient(),
    )

    output_dir = Path("artifacts/test_real_fake")
    shutil.rmtree(output_dir, ignore_errors=True)

    try:
        exit_code = main(
            [
                "--provider",
                "openai_responses",
                "--allow-network",
                "--output-dir",
                str(output_dir),
            ]
        )
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "status=ok" in captured.out
    assert "sk-not-printed" not in captured.out
    assert "sk-not-printed" not in captured.err


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


def test_openai_streaming_error_mapping_is_terminal() -> None:
    request = AdapterRequest(
        trace_id="fake-openai-streaming-error",
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
            {"type": "error"},
        ],
    )

    assert validate_trace(events).ok
    assert [event.event_type for event in events][-2:] == [
        EventType.ERROR,
        EventType.SETTLED,
    ]


def test_openai_responses_client_lazily_imports_sdk(monkeypatch) -> None:
    def blocked_import(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    original_import = __import__
    monkeypatch.setattr("builtins.__import__", blocked_import)

    client = OpenAIResponsesClient(api_key="sk-not-printed")

    try:
        client.create_response(
            AdapterRequest(
                trace_id="trace",
                prompt_id="short_text_generation",
                prompt="Hello",
                response_mode=ResponseMode.NON_STREAMING,
            )
        )
    except RuntimeError as exc:
        assert "openai package is not installed" in str(exc)
    else:
        raise AssertionError("missing SDK should raise RuntimeError")


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
