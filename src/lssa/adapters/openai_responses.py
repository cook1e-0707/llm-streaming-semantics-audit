"""OpenAI Responses adapter mapping for benign Phase 2 pilots.

This module is safe to import in tests. It performs no network calls unless a
caller constructs the adapter with a real client and explicitly invokes it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from lssa.adapters.base import AdapterRequest
from lssa.schema.events import EventType, ResponseMode, StreamEvent, TerminalReasonType
from lssa.tracing.recorder import TraceRecorder


@dataclass(frozen=True)
class OpenAIResponsesClient:
    """Thin lazy wrapper around the official OpenAI Python SDK."""

    api_key: str
    timeout_seconds: float = 30
    temperature: float = 0

    def stream_response(self, request: AdapterRequest) -> Iterable[Any]:
        client = self._client()
        with client.responses.stream(
            model=request.model,
            input=request.prompt,
            max_output_tokens=request.max_output_tokens,
            temperature=self.temperature,
        ) as stream:
            for event in stream:
                yield event

    def create_response(self, request: AdapterRequest) -> Any:
        client = self._client()
        return client.responses.create(
            model=request.model,
            input=request.prompt,
            max_output_tokens=request.max_output_tokens,
            temperature=self.temperature,
        )

    def _client(self) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai package is not installed; run python -m pip install '.[providers]'"
            ) from exc
        return OpenAI(api_key=self.api_key, timeout=self.timeout_seconds)


class OpenAIResponsesAdapter:
    """Map OpenAI Responses-style outputs into normalized StreamEvent objects."""

    provider_family = "OpenAI"
    api_surface = "Responses API"

    def __init__(self, client: Any | None = None) -> None:
        self.client = client

    def run(self, request: AdapterRequest) -> Iterable[StreamEvent]:
        if self.client is None:
            raise RuntimeError("OpenAI client is required for network execution")
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
        )
        recorder.append(
            EventType.REQUEST_SENT,
            raw_event_type="lssa.request_sent",
            payload_summary="request sent to OpenAI Responses API",
        )
        try:
            raw_response = self.client.create_response(request)
        except Exception:
            recorder.append(
                EventType.ERROR,
                terminal_reason=TerminalReasonType.ERROR,
                raw_event_type="lssa.provider_exception",
                payload_summary="OpenAI non-streaming request failed",
                metadata={"recoverable": False},
            )
            recorder.append(
                EventType.SETTLED,
                terminal_reason=TerminalReasonType.ERROR,
                raw_event_type="lssa.settled",
                payload_summary="OpenAI non-streaming trace settled after error",
            )
            return list(recorder.events)

        content = _response_text(raw_response)
        provider_stop_reason = _provider_stop_reason(raw_response)
        recorder.append(
            EventType.FIRST_BYTE,
            raw_event_type="response.completed",
            payload_summary="non-streaming response received",
        )
        recorder.append(
            EventType.FINAL_RESPONSE,
            content=content,
            char_count=len(content) if content else None,
            raw_event_type="response.completed",
            payload_summary="complete non-streaming response",
            metadata={"provider_stop_reason": provider_stop_reason},
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
            payload_summary="OpenAI non-streaming trace settled",
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
        )
        recorder.append(
            EventType.REQUEST_SENT,
            raw_event_type="lssa.request_sent",
            payload_summary="request sent to OpenAI Responses API",
        )

        saw_first_byte = False
        saw_first_token = False
        provider_stop_reason = "unknown"
        chunks: list[str] = []
        for raw_event in raw_events:
            raw_type = _raw_event_type(raw_event)
            if not saw_first_byte:
                recorder.append(
                    EventType.FIRST_BYTE,
                    raw_event_type=raw_type,
                    payload_summary="first OpenAI streaming event received",
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
                        payload_summary="first output text delta",
                    )
                    saw_first_token = True
                chunks.append(text_delta)
                recorder.append(
                    EventType.CHUNK,
                    content=text_delta,
                    char_count=len(text_delta),
                    raw_event_type=raw_type,
                    payload_summary="output text delta",
                )
                continue

            if raw_type == "response.completed":
                provider_stop_reason = _provider_stop_reason(raw_event)
                content = "".join(chunks)
                recorder.append(
                    EventType.STREAM_END,
                    raw_event_type=raw_type,
                    payload_summary="OpenAI response completed event",
                )
                recorder.append(
                    EventType.FINAL_RESPONSE,
                    content=content or None,
                    char_count=len(content) if content else None,
                    raw_event_type=raw_type,
                    payload_summary="assembled final streaming response",
                    metadata={"provider_stop_reason": provider_stop_reason},
                )
                continue

            if raw_type == "error":
                recorder.append(
                    EventType.ERROR,
                    terminal_reason=TerminalReasonType.ERROR,
                    raw_event_type=raw_type,
                    payload_summary="OpenAI streaming error event",
                    metadata={"recoverable": False},
                )
                recorder.append(
                    EventType.SETTLED,
                    terminal_reason=TerminalReasonType.ERROR,
                    raw_event_type="lssa.settled",
                    payload_summary="OpenAI streaming trace settled after error",
                )
                return list(recorder.events)

        if not any(event.event_type == EventType.STREAM_END for event in recorder.events):
            recorder.append(
                EventType.STREAM_END,
                raw_event_type="lssa.synthetic_stream_end",
                payload_summary="stream exhausted without explicit completed event",
            )
        if not any(event.event_type == EventType.FINAL_RESPONSE for event in recorder.events):
            content = "".join(chunks)
            recorder.append(
                EventType.FINAL_RESPONSE,
                content=content or None,
                char_count=len(content) if content else None,
                raw_event_type="lssa.synthetic_final_response",
                payload_summary="assembled final response from deltas",
                metadata={"provider_stop_reason": provider_stop_reason},
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
            payload_summary="OpenAI streaming trace settled",
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
        )
        recorder.append(
            EventType.REQUEST_SENT,
            raw_event_type="lssa.request_sent",
            payload_summary="request sent to OpenAI Responses API",
        )
        recorder.append(
            EventType.FIRST_BYTE,
            raw_event_type="response.completed",
            payload_summary="non-streaming response received",
        )
        content = _response_text(raw_response)
        provider_stop_reason = _provider_stop_reason(raw_response)
        recorder.append(
            EventType.FINAL_RESPONSE,
            content=content,
            char_count=len(content) if content else None,
            raw_event_type="response.completed",
            payload_summary="complete non-streaming response",
            metadata={"provider_stop_reason": provider_stop_reason},
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
            payload_summary="OpenAI non-streaming trace settled",
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


def _raw_event_type(raw_event: Any) -> str:
    if isinstance(raw_event, dict):
        return str(raw_event.get("type", "unknown"))
    return str(getattr(raw_event, "type", "unknown"))


def _text_delta(raw_event: Any) -> str | None:
    if isinstance(raw_event, dict):
        delta = raw_event.get("delta")
        if isinstance(delta, str):
            return delta
        text = raw_event.get("text")
        if isinstance(text, str) and raw_event.get("type") == "response.output_text.delta":
            return text
        return None
    delta = getattr(raw_event, "delta", None)
    if isinstance(delta, str):
        return delta
    return None


def _response_text(raw_response: Any) -> str:
    if isinstance(raw_response, dict):
        output_text = raw_response.get("output_text")
        if isinstance(output_text, str):
            return output_text
        text = raw_response.get("text")
        if isinstance(text, str):
            return text
        return ""
    output_text = getattr(raw_response, "output_text", None)
    if isinstance(output_text, str):
        return output_text
    return ""


def _provider_stop_reason(raw_response_or_event: Any) -> str:
    response = _field(raw_response_or_event, "response") or raw_response_or_event
    incomplete_details = _field(response, "incomplete_details")
    incomplete_reason = _field(incomplete_details, "reason")
    if isinstance(incomplete_reason, str):
        return incomplete_reason
    status = _field(response, "status")
    if isinstance(status, str):
        return status
    finish_reason = _field(response, "finish_reason")
    if isinstance(finish_reason, str):
        return finish_reason
    return "unknown"


def _terminal_reason_from_provider_stop(provider_stop_reason: str) -> TerminalReasonType:
    if provider_stop_reason in {"completed", "complete", "stop", "unknown"}:
        return TerminalReasonType.COMPLETE
    if provider_stop_reason in {"max_output_tokens", "max_tokens", "length"}:
        return TerminalReasonType.LENGTH
    if provider_stop_reason in {"content_filter", "content_filtered"}:
        return TerminalReasonType.CONTENT_FILTER
    if provider_stop_reason == "refusal":
        return TerminalReasonType.REFUSAL
    return TerminalReasonType.UNKNOWN


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)
