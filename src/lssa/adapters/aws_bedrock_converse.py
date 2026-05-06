"""AWS Bedrock Converse adapter mapping for benign Phase 2 pilots.

This module is safe to import in tests. It performs no network calls unless a
caller constructs the adapter with a real client and explicitly invokes it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from lssa.adapters.base import AdapterRequest
from lssa.adapters.safety_mapping import append_provider_safety_signal
from lssa.adapters.token_usage import (
    merge_token_usage,
    output_token_count,
    token_usage_metadata,
)
from lssa.schema.events import EventType, ResponseMode, StreamEvent, TerminalReasonType
from lssa.tracing.recorder import TraceRecorder
from lssa.utils.aws_bedrock import BedrockRuntimeSdkConfig


@dataclass(frozen=True)
class AwsBedrockConverseClient:
    """Thin lazy wrapper around Boto3 Bedrock Runtime Converse APIs."""

    region_name: str = "us-east-1"
    temperature: float = 0

    def stream_response(self, request: AdapterRequest) -> Iterable[Any]:
        client = self._client()
        response = client.converse_stream(**self._request_payload(request))
        for event in response.get("stream", []):
            yield event

    def create_response(self, request: AdapterRequest) -> Any:
        client = self._client()
        return client.converse(**self._request_payload(request))

    def _client(self) -> Any:
        config = BedrockRuntimeSdkConfig(region_name=self.region_name)
        return config.create_client()

    def _request_payload(self, request: AdapterRequest) -> dict[str, Any]:
        return {
            "modelId": request.model,
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": request.prompt}],
                }
            ],
            "inferenceConfig": {
                "maxTokens": request.max_output_tokens,
                "temperature": self.temperature,
            },
        }


class AwsBedrockConverseAdapter:
    """Map Bedrock Converse outputs into normalized StreamEvent objects."""

    provider_family = "AWS Bedrock"
    api_surface = "Converse API"

    def __init__(self, client: Any | None = None) -> None:
        self.client = client

    def run(self, request: AdapterRequest) -> Iterable[StreamEvent]:
        if self.client is None:
            raise RuntimeError("AWS Bedrock client is required for network execution")
        if request.response_mode == ResponseMode.STREAMING:
            raw_events = self.client.stream_response(request)
            return self.map_streaming_events(request, raw_events)
        return self._run_nonstreaming_request(request)

    def _run_nonstreaming_request(self, request: AdapterRequest) -> list[StreamEvent]:
        recorder = _recorder_for_request(request, self.provider_family, self.api_surface)
        recorder.append(
            EventType.REQUEST_START,
            raw_event_type="lssa.request_start",
            payload_summary="request accepted by local harness",
            metadata=_request_metadata(request),
        )
        recorder.append(
            EventType.REQUEST_SENT,
            raw_event_type="lssa.request_sent",
            payload_summary="request sent to AWS Bedrock Converse API",
        )
        try:
            raw_response = self.client.create_response(request)
        except Exception:
            recorder.append(
                EventType.ERROR,
                terminal_reason=TerminalReasonType.ERROR,
                raw_event_type="lssa.provider_exception",
                payload_summary="AWS Bedrock non-streaming request failed",
                metadata={"recoverable": False},
            )
            recorder.append(
                EventType.SETTLED,
                terminal_reason=TerminalReasonType.ERROR,
                raw_event_type="lssa.settled",
                payload_summary="AWS Bedrock non-streaming trace settled after error",
            )
            return list(recorder.events)

        content = _response_text(raw_response)
        provider_stop_reason = _stop_reason(raw_response)
        usage_metadata = _usage_metadata(raw_response, source="aws_bedrock_converse.usage")
        recorder.append(
            EventType.FIRST_BYTE,
            raw_event_type="converse.completed",
            payload_summary="non-streaming response received",
        )
        append_provider_safety_signal(
            recorder,
            provider_stop_reason,
            terminal_reason=_terminal_reason_from_provider_stop(provider_stop_reason),
            raw_event_type="converse.completed",
            payload_summary="AWS Bedrock non-streaming provider safety terminal signal",
        )
        recorder.append(
            EventType.FINAL_RESPONSE,
            content=content,
            token_count=output_token_count(usage_metadata),
            char_count=len(content) if content else None,
            raw_event_type="converse.completed",
            payload_summary="complete non-streaming response",
            metadata={"provider_stop_reason": provider_stop_reason, **usage_metadata},
        )
        recorder.append(
            EventType.ITERATOR_END,
            raw_event_type="lssa.iterator_end",
            payload_summary="non-streaming call returned",
        )
        recorder.append(
            EventType.SETTLED,
            terminal_reason=_terminal_reason_from_provider_stop(provider_stop_reason),
            raw_event_type="lssa.settled",
            payload_summary="AWS Bedrock non-streaming trace settled",
        )
        return list(recorder.events)

    def map_streaming_events(
        self,
        request: AdapterRequest,
        raw_events: Iterable[Any],
    ) -> list[StreamEvent]:
        recorder = _recorder_for_request(request, self.provider_family, self.api_surface)
        recorder.append(
            EventType.REQUEST_START,
            raw_event_type="lssa.request_start",
            payload_summary="request accepted by local harness",
            metadata=_request_metadata(request),
        )
        recorder.append(
            EventType.REQUEST_SENT,
            raw_event_type="lssa.request_sent",
            payload_summary="request sent to AWS Bedrock ConverseStream API",
        )

        saw_first_byte = False
        saw_first_token = False
        saw_message_stop = False
        provider_stop_reason = "unknown"
        usage_metadata: dict[str, int | str] = {}
        chunks: list[str] = []
        for raw_event in raw_events:
            raw_type = _raw_event_type(raw_event)
            usage_metadata = merge_token_usage(
                usage_metadata,
                _usage_metadata(raw_event, source=f"aws_bedrock_converse.{raw_type}.usage"),
            )
            if not saw_first_byte:
                recorder.append(
                    EventType.FIRST_BYTE,
                    raw_event_type=raw_type,
                    payload_summary="first AWS Bedrock streaming event received",
                )
                saw_first_byte = True

            text_delta = _text_delta(raw_event)
            if text_delta is not None:
                if not saw_first_token:
                    recorder.append(
                        EventType.FIRST_TOKEN,
                        content=text_delta,
                        char_count=len(text_delta),
                        raw_event_type=raw_type,
                        payload_summary="first ConverseStream contentBlockDelta text",
                    )
                    saw_first_token = True
                chunks.append(text_delta)
                recorder.append(
                    EventType.CHUNK,
                    content=text_delta,
                    char_count=len(text_delta),
                    raw_event_type=raw_type,
                    payload_summary="ConverseStream contentBlockDelta text",
                )
                continue

            if raw_type == "messageStop":
                saw_message_stop = True
                provider_stop_reason = _message_stop_reason(raw_event)
                recorder.append(
                    EventType.STREAM_END,
                    raw_event_type=raw_type,
                    payload_summary="AWS Bedrock messageStop event",
                )
                append_provider_safety_signal(
                    recorder,
                    provider_stop_reason,
                    terminal_reason=_terminal_reason_from_provider_stop(provider_stop_reason),
                    raw_event_type=raw_type,
                    payload_summary="AWS Bedrock streaming provider safety terminal signal",
                )
                continue

            if _is_error_event(raw_event):
                recorder.append(
                    EventType.ERROR,
                    terminal_reason=TerminalReasonType.ERROR,
                    raw_event_type=raw_type,
                    payload_summary="AWS Bedrock streaming error event",
                    metadata={"recoverable": False},
                )
                recorder.append(
                    EventType.SETTLED,
                    terminal_reason=TerminalReasonType.ERROR,
                    raw_event_type="lssa.settled",
                    payload_summary="AWS Bedrock streaming trace settled after error",
                )
                return list(recorder.events)

        if not any(event.event_type == EventType.STREAM_END for event in recorder.events):
            recorder.append(
                EventType.STREAM_END,
                raw_event_type="lssa.synthetic_stream_end",
                payload_summary="stream exhausted without explicit messageStop event",
            )
        if not any(event.event_type == EventType.FINAL_RESPONSE for event in recorder.events):
            content = "".join(chunks)
            recorder.append(
                EventType.FINAL_RESPONSE,
                content=content or None,
                token_count=output_token_count(usage_metadata),
                char_count=len(content) if content else None,
                raw_event_type="messageStop" if saw_message_stop else "lssa.synthetic_final_response",
                payload_summary="assembled final response from text deltas",
                metadata={"provider_stop_reason": provider_stop_reason, **usage_metadata},
            )
        recorder.append(
            EventType.ITERATOR_END,
            raw_event_type="lssa.iterator_end",
            payload_summary="stream iterator exhausted",
        )
        recorder.append(
            EventType.SETTLED,
            terminal_reason=_terminal_reason_from_provider_stop(provider_stop_reason),
            raw_event_type="lssa.settled",
            payload_summary="AWS Bedrock streaming trace settled",
        )
        return list(recorder.events)

    def map_nonstreaming_response(
        self,
        request: AdapterRequest,
        raw_response: Any,
    ) -> list[StreamEvent]:
        recorder = _recorder_for_request(request, self.provider_family, self.api_surface)
        recorder.append(
            EventType.REQUEST_START,
            raw_event_type="lssa.request_start",
            payload_summary="request accepted by local harness",
            metadata=_request_metadata(request),
        )
        recorder.append(
            EventType.REQUEST_SENT,
            raw_event_type="lssa.request_sent",
            payload_summary="request sent to AWS Bedrock Converse API",
        )
        recorder.append(
            EventType.FIRST_BYTE,
            raw_event_type="converse.completed",
            payload_summary="non-streaming response received",
        )
        content = _response_text(raw_response)
        provider_stop_reason = _stop_reason(raw_response)
        usage_metadata = _usage_metadata(raw_response, source="aws_bedrock_converse.usage")
        append_provider_safety_signal(
            recorder,
            provider_stop_reason,
            terminal_reason=_terminal_reason_from_provider_stop(provider_stop_reason),
            raw_event_type="converse.completed",
            payload_summary="AWS Bedrock non-streaming provider safety terminal signal",
        )
        recorder.append(
            EventType.FINAL_RESPONSE,
            content=content,
            token_count=output_token_count(usage_metadata),
            char_count=len(content) if content else None,
            raw_event_type="converse.completed",
            payload_summary="complete non-streaming response",
            metadata={"provider_stop_reason": provider_stop_reason, **usage_metadata},
        )
        recorder.append(
            EventType.ITERATOR_END,
            raw_event_type="lssa.iterator_end",
            payload_summary="non-streaming call returned",
        )
        recorder.append(
            EventType.SETTLED,
            terminal_reason=_terminal_reason_from_provider_stop(provider_stop_reason),
            raw_event_type="lssa.settled",
            payload_summary="AWS Bedrock non-streaming trace settled",
        )
        return list(recorder.events)


def _recorder_for_request(
    request: AdapterRequest,
    provider_family: str,
    api_surface: str,
) -> TraceRecorder:
    return TraceRecorder(
        trace_id=request.trace_id,
        provider_family=provider_family,
        api_surface=api_surface,
        model=request.model,
        response_mode=request.response_mode,
    )


def _request_metadata(request: AdapterRequest) -> dict[str, str]:
    return {"prompt_id": request.prompt_id, **request.metadata}


def _raw_event_type(raw_event: Any) -> str:
    if not isinstance(raw_event, dict):
        return str(getattr(raw_event, "type", "unknown"))
    if "SDK_UNKNOWN_MEMBER" in raw_event:
        unknown = raw_event.get("SDK_UNKNOWN_MEMBER")
        if isinstance(unknown, dict):
            return str(unknown.get("name", "SDK_UNKNOWN_MEMBER"))
        return "SDK_UNKNOWN_MEMBER"
    if not raw_event:
        return "unknown"
    return str(next(iter(raw_event)))


def _text_delta(raw_event: Any) -> str | None:
    if _raw_event_type(raw_event) != "contentBlockDelta":
        return None
    delta_event = _field(raw_event, "contentBlockDelta")
    delta = _field(delta_event, "delta")
    text = _field(delta, "text")
    return text if isinstance(text, str) else None


def _message_stop_reason(raw_event: Any) -> str:
    message_stop = _field(raw_event, "messageStop")
    stop_reason = _field(message_stop, "stopReason")
    return stop_reason if isinstance(stop_reason, str) else "unknown"


def _response_text(raw_response: Any) -> str:
    output = _field(raw_response, "output")
    message = _field(output, "message")
    content = _field(message, "content")
    if not isinstance(content, list):
        return ""
    pieces: list[str] = []
    for block in content:
        text = _field(block, "text")
        if isinstance(text, str):
            pieces.append(text)
    return "".join(pieces)


def _stop_reason(raw_response: Any) -> str:
    stop_reason = _field(raw_response, "stopReason")
    return stop_reason if isinstance(stop_reason, str) else "unknown"


def _usage_metadata(raw_response_or_event: Any, *, source: str) -> dict[str, int | str]:
    metadata = _field(raw_response_or_event, "metadata")
    usage = _field(raw_response_or_event, "usage") or _field(metadata, "usage")
    return token_usage_metadata(
        input_tokens=_field(usage, "inputTokens") or _field(usage, "input_tokens"),
        output_tokens=_field(usage, "outputTokens") or _field(usage, "output_tokens"),
        total_tokens=_field(usage, "totalTokens") or _field(usage, "total_tokens"),
        source=source,
    )


def _terminal_reason_from_provider_stop(provider_stop_reason: str) -> TerminalReasonType:
    if provider_stop_reason == "end_turn":
        return TerminalReasonType.COMPLETE
    if provider_stop_reason == "stop_sequence":
        return TerminalReasonType.STOP
    if provider_stop_reason == "max_tokens":
        return TerminalReasonType.LENGTH
    if provider_stop_reason == "tool_use":
        return TerminalReasonType.TOOL_CALL
    if provider_stop_reason in {"guardrail_intervened", "content_filtered"}:
        return TerminalReasonType.CONTENT_FILTER
    if provider_stop_reason == "refusal":
        return TerminalReasonType.REFUSAL
    if provider_stop_reason == "unknown":
        return TerminalReasonType.UNKNOWN
    return TerminalReasonType.UNKNOWN


def _is_error_event(raw_event: Any) -> bool:
    raw_type = _raw_event_type(raw_event)
    return raw_type.endswith("Exception") or raw_type in {
        "internalServerException",
        "modelStreamErrorException",
        "modelTimeoutException",
        "serviceUnavailableException",
        "throttlingException",
        "validationException",
    }


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)
