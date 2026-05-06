import json
import shutil
import time
from pathlib import Path

from lssa.adapters.aws_bedrock_converse import AwsBedrockConverseAdapter
from lssa.adapters.base import AdapterRequest
from lssa.schema.events import EventType, ResponseMode, TerminalReasonType
from lssa.schema.metrics import time_to_first_byte_ms, time_to_first_safety_signal_ms
from lssa.tracing.validator import validate_trace
from scripts.run_real_benign_pilot import main


def test_bedrock_real_pilot_defaults_to_dry_run(capsys) -> None:
    exit_code = main(["--provider", "aws_bedrock_converse"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "dry-run" in captured.out
    assert "provider=aws_bedrock_converse" in captured.out
    assert "network=disabled" in captured.out


def test_bedrock_real_pilot_refuses_network_without_key(monkeypatch, capsys) -> None:
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)

    exit_code = main(["--provider", "aws_bedrock_converse", "--allow-network"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "AWS_BEARER_TOKEN_BEDROCK is required" in captured.err
    assert "bearer-token" not in captured.err


def test_bedrock_network_uses_injected_fake_client(monkeypatch, capsys) -> None:
    class FakeClient:
        def stream_response(self, request):
            return [
                {"messageStart": {"role": "assistant"}},
                {"contentBlockDelta": {"delta": {"text": "Hello"}}},
                {"messageStop": {"stopReason": "end_turn"}},
            ]

        def create_response(self, request):
            return {
                "output": {
                    "message": {
                        "content": [{"text": "Hello"}],
                    }
                },
                "stopReason": "end_turn",
            }

    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "bearer-token-not-printed")
    monkeypatch.setattr(
        "scripts.run_real_benign_pilot.AwsBedrockConverseClient",
        lambda **kwargs: FakeClient(),
    )

    output_dir = Path("artifacts/test_bedrock_fake")
    shutil.rmtree(output_dir, ignore_errors=True)

    try:
        exit_code = main(
            [
                "--provider",
                "aws_bedrock_converse",
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
    assert "bearer-token-not-printed" not in captured.out
    assert "bearer-token-not-printed" not in captured.err
    assert all(event["content"] is None for event in trace_events)
    assert all(event["content"] is None for event in summary["events"])
    assert summary["metadata"]["content_redacted"] is True


def test_bedrock_network_returns_failure_for_terminal_error_trace(monkeypatch, capsys) -> None:
    class FailingClient:
        def stream_response(self, request):
            raise RuntimeError("provider failed")

        def create_response(self, request):
            raise RuntimeError("provider failed")

    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "bearer-token-not-printed")
    monkeypatch.setattr(
        "scripts.run_real_benign_pilot.AwsBedrockConverseClient",
        lambda **kwargs: FailingClient(),
    )

    output_dir = Path("artifacts/test_bedrock_failure")
    shutil.rmtree(output_dir, ignore_errors=True)

    try:
        exit_code = main(
            [
                "--provider",
                "aws_bedrock_converse",
                "--allow-network",
                "--output-dir",
                str(output_dir),
            ]
        )
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "status=error" in captured.err
    assert "bearer-token-not-printed" not in captured.out
    assert "bearer-token-not-printed" not in captured.err


def test_bedrock_streaming_mapping_from_fake_events() -> None:
    request = AdapterRequest(
        trace_id="fake-bedrock-streaming",
        prompt_id="short_text_generation",
        prompt="Write one harmless sentence.",
        response_mode=ResponseMode.STREAMING,
        model="fake-model",
    )
    adapter = AwsBedrockConverseAdapter()

    events = adapter.map_streaming_events(
        request,
        [
            {"messageStart": {"role": "assistant"}},
            {"contentBlockStart": {"contentBlockIndex": 0}},
            {
                "contentBlockDelta": {
                    "contentBlockIndex": 0,
                    "delta": {"text": "Hello"},
                }
            },
            {
                "contentBlockDelta": {
                    "contentBlockIndex": 0,
                    "delta": {"text": " world"},
                }
            },
            {"contentBlockStop": {"contentBlockIndex": 0}},
            {"messageStop": {"stopReason": "end_turn"}},
            {"metadata": {"usage": {"inputTokens": 6, "outputTokens": 2, "totalTokens": 8}}},
        ],
    )

    assert validate_trace(events).ok
    assert [event.event_type for event in events].count(EventType.CHUNK) == 2
    assert events[-1].terminal_reason == TerminalReasonType.COMPLETE
    assert any(
        event.metadata.get("raw_event_type") == "contentBlockDelta"
        for event in events
    )
    final_response = next(event for event in events if event.event_type == EventType.FINAL_RESPONSE)
    assert final_response.token_count == 2
    assert final_response.metadata["provider_input_tokens"] == 6
    assert final_response.metadata["provider_output_tokens"] == 2
    assert final_response.metadata["provider_total_tokens"] == 8


def test_bedrock_streaming_error_mapping_is_terminal() -> None:
    request = AdapterRequest(
        trace_id="fake-bedrock-streaming-error",
        prompt_id="short_text_generation",
        prompt="Write one harmless sentence.",
        response_mode=ResponseMode.STREAMING,
        model="fake-model",
    )
    adapter = AwsBedrockConverseAdapter()

    events = adapter.map_streaming_events(
        request,
        [
            {"messageStart": {"role": "assistant"}},
            {"modelStreamErrorException": {"message": "overloaded"}},
        ],
    )

    assert validate_trace(events).ok
    assert [event.event_type for event in events][-2:] == [
        EventType.ERROR,
        EventType.SETTLED,
    ]


def test_bedrock_nonstreaming_mapping_from_fake_response() -> None:
    request = AdapterRequest(
        trace_id="fake-bedrock-nonstreaming",
        prompt_id="short_text_generation",
        prompt="Write one harmless sentence.",
        response_mode=ResponseMode.NON_STREAMING,
        model="fake-model",
    )
    adapter = AwsBedrockConverseAdapter()

    events = adapter.map_nonstreaming_response(
        request,
        {
            "output": {
                "message": {
                    "content": [{"text": "A careful trace records events."}],
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 9, "outputTokens": 6, "totalTokens": 15},
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
    final_response = next(event for event in events if event.event_type == EventType.FINAL_RESPONSE)
    assert final_response.token_count == 6
    assert final_response.metadata["provider_total_tokens"] == 15


def test_bedrock_content_filtered_maps_to_content_filter_terminal_reason() -> None:
    request = AdapterRequest(
        trace_id="fake-bedrock-filtered",
        prompt_id="short_text_generation",
        prompt="Write one harmless sentence.",
        response_mode=ResponseMode.NON_STREAMING,
        model="fake-model",
    )
    adapter = AwsBedrockConverseAdapter()

    events = adapter.map_nonstreaming_response(
        request,
        {
            "output": {"message": {"content": []}},
            "stopReason": "content_filtered",
        },
    )

    assert validate_trace(events).ok
    safety_event = next(event for event in events if event.event_type == EventType.CONTENT_FILTER)
    assert safety_event.safety_signal is not None
    assert safety_event.safety_signal.is_terminal is True
    assert safety_event.metadata["provider_stop_reason"] == "content_filtered"
    assert safety_event.terminal_reason == TerminalReasonType.CONTENT_FILTER
    assert time_to_first_safety_signal_ms(events) is not None
    assert events[-1].terminal_reason == TerminalReasonType.CONTENT_FILTER


def test_bedrock_guardrail_intervened_maps_to_content_filter_event() -> None:
    request = AdapterRequest(
        trace_id="fake-bedrock-guardrail",
        prompt_id="safety-test",
        prompt="redacted safety prompt",
        response_mode=ResponseMode.STREAMING,
        model="fake-model",
    )
    adapter = AwsBedrockConverseAdapter()

    events = adapter.map_streaming_events(
        request,
        [
            {"messageStart": {"role": "assistant"}},
            {"messageStop": {"stopReason": "guardrail_intervened"}},
        ],
    )

    assert validate_trace(events).ok
    safety_event = next(event for event in events if event.event_type == EventType.CONTENT_FILTER)
    assert safety_event.safety_signal is not None
    assert safety_event.safety_signal.is_terminal is True
    assert safety_event.metadata["provider_stop_reason"] == "guardrail_intervened"
    assert safety_event.terminal_reason == TerminalReasonType.CONTENT_FILTER
    assert time_to_first_safety_signal_ms(events) is not None
    assert events[-1].terminal_reason == TerminalReasonType.CONTENT_FILTER


def test_bedrock_nonstreaming_run_measures_client_latency() -> None:
    class SlowFakeClient:
        def create_response(self, request):
            time.sleep(0.002)
            return {
                "output": {
                    "message": {
                        "content": [{"text": "A careful trace records events."}],
                    }
                },
                "stopReason": "end_turn",
            }

    request = AdapterRequest(
        trace_id="fake-bedrock-nonstreaming-run",
        prompt_id="short_text_generation",
        prompt="Write one harmless sentence.",
        response_mode=ResponseMode.NON_STREAMING,
        model="fake-model",
    )
    adapter = AwsBedrockConverseAdapter(client=SlowFakeClient())

    events = list(adapter.run(request))

    assert validate_trace(events).ok
    assert (time_to_first_byte_ms(events) or 0) >= 1
