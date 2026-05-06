import json
import shutil
from pathlib import Path

from lssa.adapters.base import AdapterRequest
from lssa.adapters.xiaomi_mimo import (
    DEFAULT_XIAOMI_MIMO_ANTHROPIC_BASE_URL,
    DEFAULT_XIAOMI_MIMO_OPENAI_BASE_URL,
    MIMO_API_KEY_ENV,
    XIAOMI_MIMO_API_KEY_ENV,
    XiaomiMimoAnthropicAdapter,
    XiaomiMimoOpenAIAdapter,
    xiaomi_mimo_anthropic_base_url,
    xiaomi_mimo_api_key_from_env,
    xiaomi_mimo_openai_base_url,
)
from lssa.schema.events import EventType, ResponseMode, TerminalReasonType
from lssa.tracing.validator import validate_trace
from scripts.run_real_benign_pilot import main


def test_xiaomi_mimo_env_defaults_and_key_fallback(monkeypatch) -> None:
    monkeypatch.delenv(XIAOMI_MIMO_API_KEY_ENV, raising=False)
    monkeypatch.delenv(MIMO_API_KEY_ENV, raising=False)

    api_key, api_key_env = xiaomi_mimo_api_key_from_env()
    assert api_key is None
    assert XIAOMI_MIMO_API_KEY_ENV in api_key_env
    assert MIMO_API_KEY_ENV in api_key_env
    assert xiaomi_mimo_openai_base_url() == DEFAULT_XIAOMI_MIMO_OPENAI_BASE_URL
    assert xiaomi_mimo_anthropic_base_url() == DEFAULT_XIAOMI_MIMO_ANTHROPIC_BASE_URL

    monkeypatch.setenv(MIMO_API_KEY_ENV, "mimo-key-not-printed")
    api_key, api_key_env = xiaomi_mimo_api_key_from_env()
    assert api_key == "mimo-key-not-printed"
    assert api_key_env == MIMO_API_KEY_ENV

    monkeypatch.setenv(XIAOMI_MIMO_API_KEY_ENV, "xiaomi-key-not-printed")
    api_key, api_key_env = xiaomi_mimo_api_key_from_env()
    assert api_key == "xiaomi-key-not-printed"
    assert api_key_env == XIAOMI_MIMO_API_KEY_ENV


def test_xiaomi_mimo_openai_real_pilot_defaults_to_dry_run(capsys) -> None:
    exit_code = main(["--provider", "xiaomi_mimo_openai"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "dry-run" in captured.out
    assert "provider=xiaomi_mimo_openai" in captured.out
    assert "network=disabled" in captured.out


def test_xiaomi_mimo_anthropic_real_pilot_defaults_to_dry_run(capsys) -> None:
    exit_code = main(["--provider", "xiaomi_mimo_anthropic"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "dry-run" in captured.out
    assert "provider=xiaomi_mimo_anthropic" in captured.out
    assert "network=disabled" in captured.out


def test_xiaomi_mimo_refuses_network_without_key(monkeypatch, capsys) -> None:
    monkeypatch.delenv(XIAOMI_MIMO_API_KEY_ENV, raising=False)
    monkeypatch.delenv(MIMO_API_KEY_ENV, raising=False)

    exit_code = main(["--provider", "xiaomi_mimo_openai", "--allow-network"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert XIAOMI_MIMO_API_KEY_ENV in captured.err
    assert MIMO_API_KEY_ENV in captured.err
    assert "tp-" not in captured.err


def test_xiaomi_mimo_openai_network_uses_injected_fake_client(monkeypatch, capsys) -> None:
    class FakeClient:
        def stream_response(self, request):
            return [
                {
                    "object": "chat.completion.chunk",
                    "choices": [{"delta": {"content": "Hello"}, "finish_reason": None}],
                },
                {
                    "object": "chat.completion.chunk",
                    "choices": [{"delta": {}, "finish_reason": "stop"}],
                    "usage": {
                        "prompt_tokens": 7,
                        "completion_tokens": 1,
                        "total_tokens": 8,
                    },
                },
            ]

        def create_response(self, request):
            return {
                "object": "chat.completion",
                "choices": [
                    {
                        "message": {"content": "Hello"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 7, "completion_tokens": 1, "total_tokens": 8},
            }

    monkeypatch.setenv(XIAOMI_MIMO_API_KEY_ENV, "tp-not-printed")
    monkeypatch.setattr(
        "scripts.run_real_benign_pilot.XiaomiMimoOpenAIClient",
        lambda **kwargs: FakeClient(),
    )

    output_dir = Path("artifacts/test_xiaomi_mimo_openai_fake")
    shutil.rmtree(output_dir, ignore_errors=True)

    try:
        exit_code = main(
            [
                "--provider",
                "xiaomi_mimo_openai",
                "--allow-network",
                "--output-dir",
                str(output_dir),
            ]
        )
        trace_path = next(output_dir.rglob("*.jsonl"))
        trace_events = [
            json.loads(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
        ]
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "status=ok" in captured.out
    assert "tp-not-printed" not in captured.out
    assert "tp-not-printed" not in captured.err
    assert all(event["content"] is None for event in trace_events)


def test_xiaomi_mimo_anthropic_network_uses_injected_fake_client(monkeypatch, capsys) -> None:
    class FakeClient:
        def stream_response(self, request):
            return [
                {"type": "message_start"},
                {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "Hello"},
                },
                {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
                {"type": "message_stop"},
            ]

        def create_response(self, request):
            return {
                "content": [{"type": "text", "text": "Hello"}],
                "stop_reason": "end_turn",
            }

    monkeypatch.setenv(XIAOMI_MIMO_API_KEY_ENV, "tp-not-printed")
    monkeypatch.setattr(
        "scripts.run_real_benign_pilot.XiaomiMimoAnthropicClient",
        lambda **kwargs: FakeClient(),
    )

    output_dir = Path("artifacts/test_xiaomi_mimo_anthropic_fake")
    shutil.rmtree(output_dir, ignore_errors=True)

    try:
        exit_code = main(
            [
                "--provider",
                "xiaomi_mimo_anthropic",
                "--allow-network",
                "--output-dir",
                str(output_dir),
            ]
        )
        trace_path = next(output_dir.rglob("*.jsonl"))
        trace_events = [
            json.loads(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
        ]
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "status=ok" in captured.out
    assert "tp-not-printed" not in captured.out
    assert "tp-not-printed" not in captured.err
    assert all(event["content"] is None for event in trace_events)


def test_xiaomi_mimo_openai_chat_streaming_mapping_from_fake_events() -> None:
    request = AdapterRequest(
        trace_id="fake-xiaomi-openai-streaming",
        prompt_id="short_text_generation",
        prompt="Write one harmless sentence.",
        response_mode=ResponseMode.STREAMING,
        model="mimo-test-model",
    )
    adapter = XiaomiMimoOpenAIAdapter()

    events = adapter.map_streaming_events(
        request,
        [
            {
                "object": "chat.completion.chunk",
                "choices": [{"delta": {"content": "Hello"}, "finish_reason": None}],
            },
            {
                "object": "chat.completion.chunk",
                "choices": [{"delta": {"content": " world"}, "finish_reason": None}],
            },
            {
                "object": "chat.completion.chunk",
                "choices": [{"delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
            },
        ],
    )

    assert validate_trace(events).ok
    assert [event.event_type for event in events].count(EventType.CHUNK) == 2
    assert events[-1].terminal_reason == TerminalReasonType.COMPLETE
    final_response = next(event for event in events if event.event_type == EventType.FINAL_RESPONSE)
    assert final_response.metadata["provider_family"] == "Xiaomi MiMo"
    assert final_response.metadata["api_surface"] == "OpenAI-compatible API"
    assert final_response.metadata["provider_stop_reason"] == "stop"
    assert final_response.token_count == 2


def test_xiaomi_mimo_anthropic_mapping_uses_xiaomi_surface_metadata() -> None:
    request = AdapterRequest(
        trace_id="fake-xiaomi-anthropic-nonstreaming",
        prompt_id="short_text_generation",
        prompt="Write one harmless sentence.",
        response_mode=ResponseMode.NON_STREAMING,
        model="mimo-test-model",
    )
    adapter = XiaomiMimoAnthropicAdapter()

    events = adapter.map_nonstreaming_response(
        request,
        {
            "content": [{"type": "text", "text": "A careful trace records events."}],
            "stop_reason": "end_turn",
        },
    )

    assert validate_trace(events).ok
    final_response = next(event for event in events if event.event_type == EventType.FINAL_RESPONSE)
    assert final_response.metadata["provider_family"] == "Xiaomi MiMo"
    assert final_response.metadata["api_surface"] == "Anthropic-compatible API"
