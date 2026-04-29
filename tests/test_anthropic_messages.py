import json
import shutil
import time
from pathlib import Path

from lssa.adapters.anthropic_messages import (
    AnthropicMessagesAdapter,
    AnthropicMessagesClient,
)
from lssa.adapters.base import AdapterRequest
from lssa.schema.events import EventType, ResponseMode, TerminalReasonType
from lssa.schema.metrics import time_to_first_byte_ms
from lssa.tracing.validator import validate_trace
from scripts.run_real_benign_pilot import main


def test_anthropic_real_pilot_defaults_to_dry_run(capsys) -> None:
    exit_code = main(["--provider", "anthropic_messages"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "dry-run" in captured.out
    assert "provider=anthropic_messages" in captured.out
    assert "network=disabled" in captured.out


def test_anthropic_real_pilot_refuses_network_without_key(monkeypatch, capsys) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    exit_code = main(["--provider", "anthropic_messages", "--allow-network"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "ANTHROPIC_API_KEY is required" in captured.err
    assert "sk-ant-" not in captured.err


def test_anthropic_network_uses_injected_fake_client(monkeypatch, capsys) -> None:
    class FakeClient:
        def stream_response(self, request):
            return [
                {"type": "message_start"},
                {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "Hello"},
                },
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn"},
                },
                {"type": "message_stop"},
            ]

        def create_response(self, request):
            return {
                "content": [{"type": "text", "text": "Hello"}],
                "stop_reason": "end_turn",
            }

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-printed")
    monkeypatch.setattr(
        "scripts.run_real_benign_pilot.AnthropicMessagesClient",
        lambda **kwargs: FakeClient(),
    )

    output_dir = Path("artifacts/test_anthropic_fake")
    shutil.rmtree(output_dir, ignore_errors=True)

    try:
        exit_code = main(
            [
                "--provider",
                "anthropic_messages",
                "--allow-network",
                "--output-dir",
                str(output_dir),
            ]
        )
        trace_path = next(output_dir.rglob("*.jsonl"))
        summary_path = next(output_dir.rglob("*.summary.json"))
        trace_events = [
            json.loads(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
        ]
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "status=ok" in captured.out
    assert "sk-ant-not-printed" not in captured.out
    assert "sk-ant-not-printed" not in captured.err
    assert all(event["content"] is None for event in trace_events)
    assert all(event["content"] is None for event in summary["events"])
    assert summary["metadata"]["content_redacted"] is True


def test_anthropic_streaming_mapping_from_fake_events() -> None:
    request = AdapterRequest(
        trace_id="fake-anthropic-streaming",
        prompt_id="short_text_generation",
        prompt="Write one harmless sentence.",
        response_mode=ResponseMode.STREAMING,
        model="fake-model",
    )
    adapter = AnthropicMessagesAdapter()

    events = adapter.map_streaming_events(
        request,
        [
            {"type": "message_start"},
            {"type": "content_block_start", "index": 0},
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "Hello"},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": " world"},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
            },
            {"type": "message_stop"},
        ],
    )

    assert validate_trace(events).ok
    assert [event.event_type for event in events].count(EventType.CHUNK) == 2
    assert events[-1].terminal_reason == TerminalReasonType.COMPLETE
    assert any(
        event.metadata.get("raw_event_type") == "content_block_delta"
        for event in events
    )


def test_anthropic_streaming_error_mapping_is_terminal() -> None:
    request = AdapterRequest(
        trace_id="fake-anthropic-streaming-error",
        prompt_id="short_text_generation",
        prompt="Write one harmless sentence.",
        response_mode=ResponseMode.STREAMING,
        model="fake-model",
    )
    adapter = AnthropicMessagesAdapter()

    events = adapter.map_streaming_events(
        request,
        [
            {"type": "message_start"},
            {"type": "error", "error": {"type": "overloaded_error"}},
        ],
    )

    assert validate_trace(events).ok
    assert [event.event_type for event in events][-2:] == [
        EventType.ERROR,
        EventType.SETTLED,
    ]


def test_anthropic_client_lazily_imports_sdk(monkeypatch) -> None:
    def blocked_import(name, *args, **kwargs):
        if name == "anthropic":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    original_import = __import__
    monkeypatch.setattr("builtins.__import__", blocked_import)

    client = AnthropicMessagesClient(api_key="sk-ant-not-printed")

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
        assert "anthropic package is not installed" in str(exc)
    else:
        raise AssertionError("missing SDK should raise RuntimeError")


def test_anthropic_nonstreaming_mapping_from_fake_response() -> None:
    request = AdapterRequest(
        trace_id="fake-anthropic-nonstreaming",
        prompt_id="short_text_generation",
        prompt="Write one harmless sentence.",
        response_mode=ResponseMode.NON_STREAMING,
        model="fake-model",
    )
    adapter = AnthropicMessagesAdapter()

    events = adapter.map_nonstreaming_response(
        request,
        {
            "content": [{"type": "text", "text": "A careful trace records events."}],
            "stop_reason": "end_turn",
        },
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
    assert events[-1].terminal_reason == TerminalReasonType.COMPLETE


def test_anthropic_stop_sequence_maps_to_stop_terminal_reason() -> None:
    request = AdapterRequest(
        trace_id="fake-anthropic-stop-sequence",
        prompt_id="short_text_generation",
        prompt="Write one harmless sentence.",
        response_mode=ResponseMode.NON_STREAMING,
        model="fake-model",
    )
    adapter = AnthropicMessagesAdapter()

    events = adapter.map_nonstreaming_response(
        request,
        {
            "content": [{"type": "text", "text": "A careful trace records events."}],
            "stop_reason": "stop_sequence",
        },
    )

    assert validate_trace(events).ok
    assert events[-1].terminal_reason == TerminalReasonType.STOP


def test_anthropic_nonstreaming_run_measures_client_latency() -> None:
    class SlowFakeClient:
        def create_response(self, request):
            time.sleep(0.002)
            return {
                "content": [{"type": "text", "text": "A careful trace records events."}],
                "stop_reason": "end_turn",
            }

    request = AdapterRequest(
        trace_id="fake-anthropic-nonstreaming-run",
        prompt_id="short_text_generation",
        prompt="Write one harmless sentence.",
        response_mode=ResponseMode.NON_STREAMING,
        model="fake-model",
    )
    adapter = AnthropicMessagesAdapter(client=SlowFakeClient())

    events = list(adapter.run(request))

    assert validate_trace(events).ok
    assert (time_to_first_byte_ms(events) or 0) >= 1
