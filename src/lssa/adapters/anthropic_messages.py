"""Anthropic Messages adapter mapping for benign Phase 2 pilots.

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


@dataclass(frozen=True)
class AnthropicMessagesClient:
    """Thin lazy wrapper around the official Anthropic Python SDK."""

    api_key: str
    timeout_seconds: float = 30
    temperature: float = 0

    def stream_response(self, request: AdapterRequest) -> Iterable[Any]:
        client = self._client()
        with client.messages.stream(
            model=request.model,
            max_tokens=request.max_output_tokens,
            messages=[{"role": "user", "content": request.prompt}],
            temperature=self.temperature,
        ) as stream:
            for event in stream:
                yield event

    def create_response(self, request: AdapterRequest) -> Any:
        client = self._client()
        return client.messages.create(
            model=request.model,
            max_tokens=request.max_output_tokens,
            messages=[{"role": "user", "content": request.prompt}],
            temperature=self.temperature,
        )

    def _client(self) -> Any:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package is not installed; run python -m pip install '.[providers]'"
            ) from exc
        return Anthropic(api_key=self.api_key, timeout=self.timeout_seconds)


class AnthropicMessagesAdapter:
    """Map Anthropic Messages-style outputs into normalized StreamEvent objects."""

    provider_family = "Anthropic"
    api_surface = "Messages API"

    def __init__(self, client: Any | None = None) -> None:
        self.client = client

    def run(self, request: AdapterRequest) -> Iterable[StreamEvent]:
        if self.client is None:
            raise RuntimeError("Anthropic client is required for network execution")
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
            payload_summary="request sent to Anthropic Messages API",
        )
        try:
            raw_response = self.client.create_response(request)
        except Exception:
            recorder.append(
                EventType.ERROR,
                terminal_reason=TerminalReasonType.ERROR,
                raw_event_type="lssa.provider_exception",
                payload_summary="Anthropic non-streaming request failed",
                metadata={"recoverable": False},
            )
            recorder.append(
                EventType.SETTLED,
                terminal_reason=TerminalReasonType.ERROR,
                raw_event_type="lssa.settled",
                payload_summary="Anthropic non-streaming trace settled after error",
            )
            return list(recorder.events)

        content = _response_text(raw_response)
        provider_stop_reason = _stop_reason(raw_response)
        usage_metadata = _usage_metadata(raw_response, source="anthropic_messages.usage")
        recorder.append(
            EventType.FIRST_BYTE,
            raw_event_type="message.completed",
            payload_summary="non-streaming response received",
        )
        append_provider_safety_signal(
            recorder,
            provider_stop_reason,
            terminal_reason=_terminal_reason_from_provider_stop(provider_stop_reason),
            raw_event_type="message.completed",
            payload_summary="Anthropic non-streaming provider safety terminal signal",
        )
        recorder.append(
            EventType.FINAL_RESPONSE,
            content=content,
            token_count=output_token_count(usage_metadata),
            char_count=len(content) if content else None,
            raw_event_type="message.completed",
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
            payload_summary="Anthropic non-streaming trace settled",
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
            payload_summary="request sent to Anthropic Messages API",
        )

        saw_first_byte = False
        saw_first_token = False
        provider_stop_reason = "unknown"
        usage_metadata: dict[str, int | str] = {}
        chunks: list[str] = []
        for raw_event in raw_events:
            raw_type = _raw_event_type(raw_event)
            usage_metadata = merge_token_usage(
                usage_metadata,
                _usage_metadata(raw_event, source=f"anthropic_messages.{raw_type}.usage"),
            )
            if not saw_first_byte:
                recorder.append(
                    EventType.FIRST_BYTE,
                    raw_event_type=raw_type,
                    payload_summary="first Anthropic streaming event received",
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
                        payload_summary="first text_delta content block delta",
                    )
                    saw_first_token = True
                chunks.append(text_delta)
                recorder.append(
                    EventType.CHUNK,
                    content=text_delta,
                    char_count=len(text_delta),
                    raw_event_type=raw_type,
                    payload_summary="text_delta content block delta",
                )
                continue

            if raw_type == "message_delta":
                provider_stop_reason = _message_delta_stop_reason(raw_event)
                continue

            if raw_type == "message_stop":
                content = "".join(chunks)
                recorder.append(
                    EventType.STREAM_END,
                    raw_event_type=raw_type,
                    payload_summary="Anthropic message_stop event",
                )
                append_provider_safety_signal(
                    recorder,
                    provider_stop_reason,
                    terminal_reason=_terminal_reason_from_provider_stop(provider_stop_reason),
                    raw_event_type=raw_type,
                    payload_summary="Anthropic streaming provider safety terminal signal",
                )
                recorder.append(
                    EventType.FINAL_RESPONSE,
                    content=content or None,
                    token_count=output_token_count(usage_metadata),
                    char_count=len(content) if content else None,
                    raw_event_type=raw_type,
                    payload_summary="assembled final streaming response",
                    metadata={
                        "provider_stop_reason": provider_stop_reason,
                        **usage_metadata,
                    },
                )
                continue

            if raw_type == "error":
                recorder.append(
                    EventType.ERROR,
                    terminal_reason=TerminalReasonType.ERROR,
                    raw_event_type=raw_type,
                    payload_summary="Anthropic streaming error event",
                    metadata={"recoverable": False},
                )
                recorder.append(
                    EventType.SETTLED,
                    terminal_reason=TerminalReasonType.ERROR,
                    raw_event_type="lssa.settled",
                    payload_summary="Anthropic streaming trace settled after error",
                )
                return list(recorder.events)

        if not any(event.event_type == EventType.STREAM_END for event in recorder.events):
            recorder.append(
                EventType.STREAM_END,
                raw_event_type="lssa.synthetic_stream_end",
                payload_summary="stream exhausted without explicit message_stop event",
            )
        if not any(event.event_type == EventType.FINAL_RESPONSE for event in recorder.events):
            content = "".join(chunks)
            recorder.append(
                EventType.FINAL_RESPONSE,
                content=content or None,
                token_count=output_token_count(usage_metadata),
                char_count=len(content) if content else None,
                raw_event_type="lssa.synthetic_final_response",
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
            payload_summary="Anthropic streaming trace settled",
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
            payload_summary="request sent to Anthropic Messages API",
        )
        recorder.append(
            EventType.FIRST_BYTE,
            raw_event_type="message.completed",
            payload_summary="non-streaming response received",
        )
        content = _response_text(raw_response)
        provider_stop_reason = _stop_reason(raw_response)
        usage_metadata = _usage_metadata(raw_response, source="anthropic_messages.usage")
        append_provider_safety_signal(
            recorder,
            provider_stop_reason,
            terminal_reason=_terminal_reason_from_provider_stop(provider_stop_reason),
            raw_event_type="message.completed",
            payload_summary="Anthropic non-streaming provider safety terminal signal",
        )
        recorder.append(
            EventType.FINAL_RESPONSE,
            content=content,
            token_count=output_token_count(usage_metadata),
            char_count=len(content) if content else None,
            raw_event_type="message.completed",
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
            payload_summary="Anthropic non-streaming trace settled",
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
    if isinstance(raw_event, dict):
        return str(raw_event.get("type", "unknown"))
    return str(getattr(raw_event, "type", "unknown"))


def _text_delta(raw_event: Any) -> str | None:
    if _raw_event_type(raw_event) != "content_block_delta":
        return None
    delta = _field(raw_event, "delta")
    if _field(delta, "type") != "text_delta":
        return None
    text = _field(delta, "text")
    return text if isinstance(text, str) else None


def _message_delta_stop_reason(raw_event: Any) -> str:
    delta = _field(raw_event, "delta")
    stop_reason = _field(delta, "stop_reason")
    return stop_reason if isinstance(stop_reason, str) else "unknown"


def _response_text(raw_response: Any) -> str:
    content = _field(raw_response, "content")
    if not isinstance(content, list):
        return ""
    pieces: list[str] = []
    for block in content:
        block_type = _field(block, "type")
        text = _field(block, "text")
        if block_type == "text" and isinstance(text, str):
            pieces.append(text)
    return "".join(pieces)


def _stop_reason(raw_response: Any) -> str:
    stop_reason = _field(raw_response, "stop_reason")
    return stop_reason if isinstance(stop_reason, str) else "unknown"


def _usage_metadata(raw_response_or_event: Any, *, source: str) -> dict[str, int | str]:
    message = _field(raw_response_or_event, "message")
    usage = _field(raw_response_or_event, "usage") or _field(message, "usage")
    return token_usage_metadata(
        input_tokens=_field(usage, "input_tokens"),
        output_tokens=_field(usage, "output_tokens"),
        total_tokens=None,
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
    if provider_stop_reason == "refusal":
        return TerminalReasonType.REFUSAL
    if provider_stop_reason == "unknown":
        return TerminalReasonType.UNKNOWN
    return TerminalReasonType.UNKNOWN


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)
