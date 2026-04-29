"""Deterministic mock provider for Phase 2 harness validation."""

from __future__ import annotations

from enum import Enum
from typing import Iterable

from lssa.adapters.base import AdapterRequest
from lssa.schema.events import EventType, ResponseMode, StreamEvent, TerminalReasonType
from lssa.tracing.recorder import TraceRecorder


class MockScenario(str, Enum):
    NONSTREAMING_BENIGN = "nonstreaming_benign"
    STREAMING_BENIGN = "streaming_benign"
    STREAMING_LONG_BENIGN = "streaming_long_benign"
    STREAMING_ERROR = "streaming_error"
    STREAMING_CANCEL = "streaming_cancel"
    STREAMING_DELAYED_SETTLEMENT = "streaming_delayed_settlement"


class MockProviderAdapter:
    """Mock adapter that emits normalized deterministic events."""

    provider_family = "mock"
    api_surface = "mock_provider"
    model = "mock-model"

    def run(self, request: AdapterRequest) -> Iterable[StreamEvent]:
        scenario = MockScenario(request.metadata.get("scenario", "streaming_benign"))
        recorder = TraceRecorder(
            trace_id=request.trace_id,
            provider_family=self.provider_family,
            api_surface=self.api_surface,
            model=request.model,
            response_mode=request.response_mode,
        )
        _emit_common_start(recorder)

        if scenario == MockScenario.NONSTREAMING_BENIGN:
            _emit_nonstreaming(recorder)
        elif scenario == MockScenario.STREAMING_BENIGN:
            _emit_streaming(recorder, ["Hello", " world."])
        elif scenario == MockScenario.STREAMING_LONG_BENIGN:
            _emit_streaming(
                recorder,
                [
                    "This",
                    " mock",
                    " response",
                    " contains",
                    " several",
                    " harmless",
                    " chunks.",
                ],
            )
        elif scenario == MockScenario.STREAMING_ERROR:
            _emit_error(recorder)
        elif scenario == MockScenario.STREAMING_CANCEL:
            _emit_cancel(recorder)
        elif scenario == MockScenario.STREAMING_DELAYED_SETTLEMENT:
            _emit_streaming(recorder, ["Delayed", " settlement."], settlement_delay_ms=50)
        else:
            raise ValueError(f"unsupported mock scenario: {scenario}")

        return list(recorder.events)


def request_for_scenario(scenario: MockScenario) -> AdapterRequest:
    response_mode = (
        ResponseMode.NON_STREAMING
        if scenario == MockScenario.NONSTREAMING_BENIGN
        else ResponseMode.STREAMING
    )
    return AdapterRequest(
        trace_id=f"mock-{scenario.value}",
        prompt_id="short_text_generation",
        prompt="Write one harmless sentence.",
        response_mode=response_mode,
        model=MockProviderAdapter.model,
        provider_family=MockProviderAdapter.provider_family,
        api_surface=MockProviderAdapter.api_surface,
        metadata={"scenario": scenario.value},
    )


def _emit_common_start(recorder: TraceRecorder) -> None:
    recorder.append(
        EventType.REQUEST_START,
        timestamp_ms=0,
        monotonic_time_ns=0,
        raw_event_type="mock.request_start",
        payload_summary="request accepted by harness",
    )
    recorder.append(
        EventType.REQUEST_SENT,
        timestamp_ms=10,
        monotonic_time_ns=10_000_000,
        raw_event_type="mock.request_sent",
        payload_summary="request sent to mock provider",
    )
    recorder.append(
        EventType.FIRST_BYTE,
        timestamp_ms=20,
        monotonic_time_ns=20_000_000,
        raw_event_type="mock.first_byte",
        payload_summary="first response byte available",
    )


def _emit_nonstreaming(recorder: TraceRecorder) -> None:
    content = "Hello from a benign non-streaming mock response."
    recorder.append(
        EventType.FINAL_RESPONSE,
        timestamp_ms=30,
        monotonic_time_ns=30_000_000,
        content=content,
        char_count=len(content),
        raw_event_type="mock.final_response",
        payload_summary="complete benign response",
    )
    recorder.append(
        EventType.ITERATOR_END,
        timestamp_ms=40,
        monotonic_time_ns=40_000_000,
        raw_event_type="mock.iterator_end",
        payload_summary="non-streaming call returned",
    )
    recorder.append(
        EventType.SETTLED,
        timestamp_ms=50,
        monotonic_time_ns=50_000_000,
        terminal_reason=TerminalReasonType.COMPLETE,
        raw_event_type="mock.settled",
        payload_summary="trace settled",
    )


def _emit_streaming(
    recorder: TraceRecorder,
    chunks: list[str],
    *,
    settlement_delay_ms: int = 10,
) -> None:
    full_content = "".join(chunks)
    recorder.append(
        EventType.FIRST_TOKEN,
        timestamp_ms=30,
        monotonic_time_ns=30_000_000,
        content=chunks[0],
        token_count=1,
        char_count=len(chunks[0]),
        raw_event_type="mock.first_token",
        payload_summary="first text token available",
    )
    for offset, chunk in enumerate(chunks, start=1):
        recorder.append(
            EventType.CHUNK,
            timestamp_ms=30 + offset * 10,
            monotonic_time_ns=(30 + offset * 10) * 1_000_000,
            content=chunk,
            token_count=offset,
            char_count=len(chunk),
            raw_event_type="mock.chunk",
            payload_summary=f"text chunk {offset}",
        )
    terminal_ms = 40 + len(chunks) * 10
    recorder.append(
        EventType.STREAM_END,
        timestamp_ms=terminal_ms,
        monotonic_time_ns=terminal_ms * 1_000_000,
        raw_event_type="mock.stream_end",
        payload_summary="mock stream content ended",
    )
    recorder.append(
        EventType.FINAL_RESPONSE,
        timestamp_ms=terminal_ms + 10,
        monotonic_time_ns=(terminal_ms + 10) * 1_000_000,
        content=full_content,
        char_count=len(full_content),
        raw_event_type="mock.final_response",
        payload_summary="assembled final response",
    )
    recorder.append(
        EventType.ITERATOR_END,
        timestamp_ms=terminal_ms + 20,
        monotonic_time_ns=(terminal_ms + 20) * 1_000_000,
        raw_event_type="mock.iterator_end",
        payload_summary="mock iterator exhausted",
    )
    settled_ms = terminal_ms + 20 + settlement_delay_ms
    recorder.append(
        EventType.SETTLED,
        timestamp_ms=settled_ms,
        monotonic_time_ns=settled_ms * 1_000_000,
        terminal_reason=TerminalReasonType.COMPLETE,
        raw_event_type="mock.settled",
        payload_summary="trace settled after iterator cleanup",
    )


def _emit_error(recorder: TraceRecorder) -> None:
    recorder.append(
        EventType.ERROR,
        timestamp_ms=30,
        monotonic_time_ns=30_000_000,
        terminal_reason=TerminalReasonType.ERROR,
        raw_event_type="mock.error",
        payload_summary="non-recoverable mock transport error",
        metadata={"recoverable": False},
    )
    recorder.append(
        EventType.SETTLED,
        timestamp_ms=40,
        monotonic_time_ns=40_000_000,
        terminal_reason=TerminalReasonType.ERROR,
        raw_event_type="mock.settled",
        payload_summary="error trace settled",
    )


def _emit_cancel(recorder: TraceRecorder) -> None:
    recorder.append(
        EventType.FIRST_TOKEN,
        timestamp_ms=30,
        monotonic_time_ns=30_000_000,
        content="Cancel",
        raw_event_type="mock.first_token",
        payload_summary="first text token before cancel",
    )
    recorder.append(
        EventType.CHUNK,
        timestamp_ms=40,
        monotonic_time_ns=40_000_000,
        content="Cancel",
        raw_event_type="mock.chunk",
        payload_summary="visible text before cancel",
    )
    recorder.append(
        EventType.CANCEL,
        timestamp_ms=50,
        monotonic_time_ns=50_000_000,
        terminal_reason=TerminalReasonType.CANCEL,
        raw_event_type="mock.cancel",
        payload_summary="client requested cancellation",
    )
    recorder.append(
        EventType.STREAM_END,
        timestamp_ms=60,
        monotonic_time_ns=60_000_000,
        terminal_reason=TerminalReasonType.CANCEL,
        raw_event_type="mock.stream_end",
        payload_summary="stream ended after cancel",
    )
    recorder.append(
        EventType.ITERATOR_END,
        timestamp_ms=70,
        monotonic_time_ns=70_000_000,
        terminal_reason=TerminalReasonType.CANCEL,
        raw_event_type="mock.iterator_end",
        payload_summary="iterator cleanup after cancel",
    )
    recorder.append(
        EventType.SETTLED,
        timestamp_ms=80,
        monotonic_time_ns=80_000_000,
        terminal_reason=TerminalReasonType.CANCEL,
        raw_event_type="mock.settled",
        payload_summary="cancel trace settled",
    )
