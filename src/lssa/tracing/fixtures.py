"""Synthetic trace fixture helpers for Phase 2."""

from __future__ import annotations

from dataclasses import replace

from lssa.schema.events import (
    EventType,
    Layer,
    ResponseMode,
    StreamEvent,
    TerminalReasonType,
)


def make_event(
    event_type: EventType,
    sequence_index: int,
    *,
    trace_id: str = "trace-fixture",
    timestamp_ms: float | None = None,
    layer: Layer = Layer.PROVIDER,
    content: str | None = None,
    terminal_reason: TerminalReasonType | None = None,
    recoverable: bool | None = None,
) -> StreamEvent:
    if timestamp_ms is None:
        timestamp_ms = float(sequence_index * 10)
    metadata = {
        "provider_family": "mock",
        "api_surface": "mock",
        "model": "mock-model",
        "monotonic_time_ns": sequence_index * 10_000_000,
        "wall_time_iso": f"2026-04-29T00:00:{sequence_index:02d}+00:00",
        "raw_event_type": f"mock.{event_type.value}",
        "payload_summary": event_type.value,
        "payload_redacted": True,
    }
    if recoverable is not None:
        metadata["recoverable"] = recoverable
    return StreamEvent(
        trace_id=trace_id,
        event_type=event_type,
        layer=layer,
        timestamp_ms=timestamp_ms,
        sequence_index=sequence_index,
        content=content,
        terminal_reason=terminal_reason,
        metadata=metadata,
    )


def reindex_events(events: list[StreamEvent]) -> list[StreamEvent]:
    return [
        replace(event, sequence_index=index)
        for index, event in enumerate(events)
    ]


def benign_streaming_trace(trace_id: str = "trace-streaming") -> list[StreamEvent]:
    events = [
        make_event(EventType.REQUEST_START, 0, trace_id=trace_id),
        make_event(EventType.REQUEST_SENT, 1, trace_id=trace_id),
        make_event(EventType.FIRST_BYTE, 2, trace_id=trace_id),
        make_event(EventType.FIRST_TOKEN, 3, trace_id=trace_id, content="Hello"),
        make_event(EventType.CHUNK, 4, trace_id=trace_id, content="Hello"),
        make_event(EventType.CHUNK, 5, trace_id=trace_id, content=" world."),
        make_event(EventType.STREAM_END, 6, trace_id=trace_id),
        make_event(EventType.FINAL_RESPONSE, 7, trace_id=trace_id, content="Hello world."),
        make_event(EventType.ITERATOR_END, 8, trace_id=trace_id),
        make_event(
            EventType.SETTLED,
            9,
            trace_id=trace_id,
            terminal_reason=TerminalReasonType.COMPLETE,
        ),
    ]
    return events


def benign_nonstreaming_trace(trace_id: str = "trace-nonstreaming") -> list[StreamEvent]:
    return [
        make_event(EventType.REQUEST_START, 0, trace_id=trace_id),
        make_event(EventType.REQUEST_SENT, 1, trace_id=trace_id),
        make_event(EventType.FIRST_BYTE, 2, trace_id=trace_id),
        make_event(EventType.FINAL_RESPONSE, 3, trace_id=trace_id, content="Hello world."),
        make_event(EventType.ITERATOR_END, 4, trace_id=trace_id),
        make_event(
            EventType.SETTLED,
            5,
            trace_id=trace_id,
            terminal_reason=TerminalReasonType.COMPLETE,
        ),
    ]


def response_mode_for_scenario(scenario: str) -> ResponseMode:
    if scenario.startswith("nonstreaming"):
        return ResponseMode.NON_STREAMING
    return ResponseMode.STREAMING
