"""Xiaomi MiMo compatible API adapters.

This module is safe to import in tests. It performs no network calls unless a
caller constructs an adapter with a real client and explicitly invokes it.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Mapping

from lssa.adapters.anthropic_messages import AnthropicMessagesAdapter
from lssa.adapters.base import AdapterRequest
from lssa.adapters.safety_mapping import append_provider_safety_signal
from lssa.adapters.token_usage import (
    merge_token_usage,
    output_token_count,
    token_usage_metadata,
)
from lssa.schema.events import EventType, ResponseMode, StreamEvent, TerminalReasonType
from lssa.tracing.recorder import TraceRecorder

XIAOMI_MIMO_API_KEY_ENV = "XIAOMI_MIMO_API_KEY"
MIMO_API_KEY_ENV = "MIMO_API_KEY"
XIAOMI_MIMO_OPENAI_BASE_URL_ENV = "XIAOMI_MIMO_OPENAI_BASE_URL"
XIAOMI_MIMO_ANTHROPIC_BASE_URL_ENV = "XIAOMI_MIMO_ANTHROPIC_BASE_URL"
XIAOMI_MIMO_MODEL_ENV = "XIAOMI_MIMO_MODEL"
DEFAULT_XIAOMI_MIMO_OPENAI_BASE_URL = "https://token-plan-sgp.xiaomimimo.com/v1"
DEFAULT_XIAOMI_MIMO_ANTHROPIC_BASE_URL = (
    "https://token-plan-sgp.xiaomimimo.com/anthropic"
)
DEFAULT_XIAOMI_MIMO_MODEL = "mimo-v2-omni"


def xiaomi_mimo_api_key_from_env(
    environ: Mapping[str, str] | None = None,
) -> tuple[str | None, str]:
    """Return a configured Xiaomi MiMo key and the env var that supplied it."""

    env = os.environ if environ is None else environ
    if env.get(XIAOMI_MIMO_API_KEY_ENV):
        return env[XIAOMI_MIMO_API_KEY_ENV], XIAOMI_MIMO_API_KEY_ENV
    if env.get(MIMO_API_KEY_ENV):
        return env[MIMO_API_KEY_ENV], MIMO_API_KEY_ENV
    return None, f"{XIAOMI_MIMO_API_KEY_ENV} or {MIMO_API_KEY_ENV}"


def xiaomi_mimo_openai_base_url(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    return env.get(XIAOMI_MIMO_OPENAI_BASE_URL_ENV, DEFAULT_XIAOMI_MIMO_OPENAI_BASE_URL)


def xiaomi_mimo_anthropic_base_url(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    return env.get(
        XIAOMI_MIMO_ANTHROPIC_BASE_URL_ENV,
        DEFAULT_XIAOMI_MIMO_ANTHROPIC_BASE_URL,
    )


def xiaomi_mimo_model(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    return env.get(XIAOMI_MIMO_MODEL_ENV, DEFAULT_XIAOMI_MIMO_MODEL)


@dataclass(frozen=True)
class XiaomiMimoOpenAIClient:
    """OpenAI-compatible Xiaomi MiMo client for the `/v1` endpoint."""

    api_key: str
    base_url: str = DEFAULT_XIAOMI_MIMO_OPENAI_BASE_URL
    timeout_seconds: float = 30
    temperature: float = 0

    def stream_response(self, request: AdapterRequest) -> Iterable[Any]:
        client = self._client()
        stream = client.chat.completions.create(
            model=request.model,
            messages=[{"role": "user", "content": request.prompt}],
            max_tokens=request.max_output_tokens,
            temperature=self.temperature,
            stream=True,
        )
        for event in stream:
            yield event

    def create_response(self, request: AdapterRequest) -> Any:
        client = self._client()
        return client.chat.completions.create(
            model=request.model,
            messages=[{"role": "user", "content": request.prompt}],
            max_tokens=request.max_output_tokens,
            temperature=self.temperature,
        )

    def _client(self) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai package is not installed; run python -m pip install '.[providers]'"
            ) from exc
        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_seconds,
        )


@dataclass(frozen=True)
class XiaomiMimoAnthropicClient:
    """Anthropic-compatible Xiaomi MiMo client for the `/anthropic` endpoint."""

    api_key: str
    base_url: str = DEFAULT_XIAOMI_MIMO_ANTHROPIC_BASE_URL
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
        return Anthropic(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_seconds,
        )


class XiaomiMimoOpenAIAdapter:
    """Map Xiaomi MiMo OpenAI-compatible chat outputs into normalized events."""

    provider_family = "Xiaomi MiMo"
    api_surface = "OpenAI-compatible API"

    def __init__(self, client: Any | None = None) -> None:
        self.client = client

    def run(self, request: AdapterRequest) -> Iterable[StreamEvent]:
        if self.client is None:
            raise RuntimeError("Xiaomi MiMo OpenAI-compatible client is required")
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
            payload_summary="request sent to Xiaomi MiMo OpenAI-compatible API",
        )
        try:
            raw_response = self.client.create_response(request)
        except Exception:
            recorder.append(
                EventType.ERROR,
                terminal_reason=TerminalReasonType.ERROR,
                raw_event_type="lssa.provider_exception",
                payload_summary="Xiaomi MiMo OpenAI-compatible request failed",
                metadata={"recoverable": False},
            )
            recorder.append(
                EventType.SETTLED,
                terminal_reason=TerminalReasonType.ERROR,
                raw_event_type="lssa.settled",
                payload_summary="Xiaomi MiMo OpenAI-compatible trace settled after error",
            )
            return list(recorder.events)

        return self.map_nonstreaming_response(request, raw_response)

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
            payload_summary="request sent to Xiaomi MiMo OpenAI-compatible API",
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
                _usage_metadata(raw_event, source="xiaomi_mimo_openai.streaming.usage"),
            )
            if not saw_first_byte:
                recorder.append(
                    EventType.FIRST_BYTE,
                    raw_event_type=raw_type,
                    payload_summary="first Xiaomi MiMo OpenAI-compatible event received",
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

            finish_reason = _finish_reason(raw_event)
            if finish_reason is not None:
                provider_stop_reason = finish_reason
                content = "".join(chunks)
                recorder.append(
                    EventType.STREAM_END,
                    raw_event_type=raw_type,
                    payload_summary="Xiaomi MiMo OpenAI-compatible stream finished",
                )
                append_provider_safety_signal(
                    recorder,
                    provider_stop_reason,
                    terminal_reason=_terminal_reason_from_provider_stop(provider_stop_reason),
                    raw_event_type=raw_type,
                    payload_summary="Xiaomi MiMo OpenAI-compatible provider terminal signal",
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
                    payload_summary="Xiaomi MiMo OpenAI-compatible streaming error event",
                    metadata={"recoverable": False},
                )
                recorder.append(
                    EventType.SETTLED,
                    terminal_reason=TerminalReasonType.ERROR,
                    raw_event_type="lssa.settled",
                    payload_summary="Xiaomi MiMo OpenAI-compatible trace settled after error",
                )
                return list(recorder.events)

        if not any(event.event_type == EventType.STREAM_END for event in recorder.events):
            recorder.append(
                EventType.STREAM_END,
                raw_event_type="lssa.synthetic_stream_end",
                payload_summary="stream exhausted without explicit finish reason",
            )
        if not any(event.event_type == EventType.FINAL_RESPONSE for event in recorder.events):
            content = "".join(chunks)
            recorder.append(
                EventType.FINAL_RESPONSE,
                content=content or None,
                token_count=output_token_count(usage_metadata),
                char_count=len(content) if content else None,
                raw_event_type="lssa.synthetic_final_response",
                payload_summary="assembled final response from deltas",
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
            payload_summary="Xiaomi MiMo OpenAI-compatible trace settled",
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
            payload_summary="request sent to Xiaomi MiMo OpenAI-compatible API",
        )
        recorder.append(
            EventType.FIRST_BYTE,
            raw_event_type="chat.completion",
            payload_summary="non-streaming response received",
        )
        content = _response_text(raw_response)
        provider_stop_reason = _finish_reason(raw_response) or "unknown"
        usage_metadata = _usage_metadata(
            raw_response,
            source="xiaomi_mimo_openai.usage",
        )
        append_provider_safety_signal(
            recorder,
            provider_stop_reason,
            terminal_reason=_terminal_reason_from_provider_stop(provider_stop_reason),
            raw_event_type="chat.completion",
            payload_summary="Xiaomi MiMo OpenAI-compatible provider terminal signal",
        )
        recorder.append(
            EventType.FINAL_RESPONSE,
            content=content,
            token_count=output_token_count(usage_metadata),
            char_count=len(content) if content else None,
            raw_event_type="chat.completion",
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
            payload_summary="Xiaomi MiMo OpenAI-compatible trace settled",
        )
        return list(recorder.events)


class XiaomiMimoAnthropicAdapter(AnthropicMessagesAdapter):
    """Map Xiaomi MiMo Anthropic-compatible outputs into normalized events."""

    provider_family = "Xiaomi MiMo"
    api_surface = "Anthropic-compatible API"


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
        event_type = raw_event.get("type") or raw_event.get("object")
        return str(event_type or "chat.completion.chunk")
    event_type = getattr(raw_event, "type", None) or getattr(raw_event, "object", None)
    return str(event_type or "chat.completion.chunk")


def _text_delta(raw_event: Any) -> str | None:
    choice = _first_choice(raw_event)
    delta = _field(choice, "delta")
    content = _field(delta, "content")
    return content if isinstance(content, str) else None


def _response_text(raw_response: Any) -> str:
    choice = _first_choice(raw_response)
    message = _field(choice, "message")
    content = _field(message, "content")
    return content if isinstance(content, str) else ""


def _finish_reason(raw_response_or_event: Any) -> str | None:
    choice = _first_choice(raw_response_or_event)
    finish_reason = _field(choice, "finish_reason")
    return finish_reason if isinstance(finish_reason, str) and finish_reason else None


def _usage_metadata(raw_response_or_event: Any, *, source: str) -> dict[str, int | str]:
    usage = _field(raw_response_or_event, "usage")
    return token_usage_metadata(
        input_tokens=_field(usage, "prompt_tokens") or _field(usage, "input_tokens"),
        output_tokens=_field(usage, "completion_tokens")
        or _field(usage, "output_tokens"),
        total_tokens=_field(usage, "total_tokens"),
        source=source,
    )


def _first_choice(raw_response_or_event: Any) -> Any:
    choices = _field(raw_response_or_event, "choices")
    if isinstance(choices, list) and choices:
        return choices[0]
    return None


def _terminal_reason_from_provider_stop(provider_stop_reason: str) -> TerminalReasonType:
    if provider_stop_reason in {"stop", "completed", "complete"}:
        return TerminalReasonType.COMPLETE
    if provider_stop_reason in {"length", "max_tokens", "max_output_tokens"}:
        return TerminalReasonType.LENGTH
    if provider_stop_reason in {"content_filter", "content_filtered"}:
        return TerminalReasonType.CONTENT_FILTER
    if provider_stop_reason in {"tool_calls", "function_call"}:
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
