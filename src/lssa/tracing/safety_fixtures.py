"""Redacted mock safety-signal traces for Phase 3 harness validation."""

from __future__ import annotations

from enum import Enum

from lssa.schema.events import (
    EventType,
    ResponseMode,
    SafetySignal,
    SafetySignalType,
    StreamEvent,
    TerminalReasonType,
    ValidationRange,
)
from lssa.tracing.recorder import TraceRecorder


class MockSafetyScenario(str, Enum):
    """Safety-signal scenarios with no raw unsafe prompt or output text."""

    STREAMING_DELAYED_ANNOTATION = "streaming_delayed_annotation"
    STREAMING_TERMINAL_REFUSAL = "streaming_terminal_refusal"
    STREAMING_CONTENT_FILTER = "streaming_content_filter"


def safety_trace_for_scenario(scenario: MockSafetyScenario) -> list[StreamEvent]:
    """Return one deterministic redacted mock safety trace."""

    recorder = TraceRecorder(
        trace_id=f"mock-safety-{scenario.value}",
        provider_family="mock",
        api_surface="mock_safety_provider",
        model="mock-safety-model",
        response_mode=ResponseMode.STREAMING,
    )
    _emit_common_start(recorder)
    if scenario == MockSafetyScenario.STREAMING_DELAYED_ANNOTATION:
        _emit_delayed_annotation(recorder)
    elif scenario == MockSafetyScenario.STREAMING_TERMINAL_REFUSAL:
        _emit_terminal_refusal(recorder)
    elif scenario == MockSafetyScenario.STREAMING_CONTENT_FILTER:
        _emit_content_filter(recorder)
    else:
        raise ValueError(f"unsupported mock safety scenario: {scenario}")
    return list(recorder.events)


def _emit_common_start(recorder: TraceRecorder) -> None:
    recorder.append(
        EventType.REQUEST_START,
        timestamp_ms=0,
        monotonic_time_ns=0,
        raw_event_type="mock_safety.request_start",
        payload_summary="redacted safety-category request accepted by harness",
    )
    recorder.append(
        EventType.REQUEST_SENT,
        timestamp_ms=10,
        monotonic_time_ns=10_000_000,
        raw_event_type="mock_safety.request_sent",
        payload_summary="redacted request sent to mock provider",
    )
    recorder.append(
        EventType.FIRST_BYTE,
        timestamp_ms=20,
        monotonic_time_ns=20_000_000,
        raw_event_type="mock_safety.first_byte",
        payload_summary="first response byte available",
    )


def _emit_redacted_chunk(
    recorder: TraceRecorder,
    sequence_label: str,
    *,
    timestamp_ms: int,
    char_count: int,
    token_count: int,
) -> None:
    recorder.append(
        EventType.CHUNK,
        timestamp_ms=timestamp_ms,
        monotonic_time_ns=timestamp_ms * 1_000_000,
        content=None,
        char_count=char_count,
        token_count=token_count,
        raw_event_type="mock_safety.chunk",
        payload_summary=f"redacted visible chunk {sequence_label}",
        metadata={
            "content_redacted": True,
            "safety_fixture": True,
            "visible_to_client": True,
        },
    )


def _emit_delayed_annotation(recorder: TraceRecorder) -> None:
    recorder.append(
        EventType.FIRST_TOKEN,
        timestamp_ms=30,
        monotonic_time_ns=30_000_000,
        content=None,
        char_count=4,
        token_count=1,
        raw_event_type="mock_safety.first_token",
        payload_summary="first redacted token available",
        metadata={"content_redacted": True, "safety_fixture": True},
    )
    _emit_redacted_chunk(
        recorder,
        "1",
        timestamp_ms=40,
        char_count=12,
        token_count=3,
    )
    _emit_redacted_chunk(
        recorder,
        "2",
        timestamp_ms=50,
        char_count=10,
        token_count=2,
    )
    recorder.append(
        EventType.SAFETY_ANNOTATION,
        timestamp_ms=80,
        monotonic_time_ns=80_000_000,
        safety_signal=SafetySignal(
            signal_type=SafetySignalType.ANNOTATION,
            layer=recorder.layer,
            category="redacted_category_label",
            severity="redacted",
            message=None,
            is_terminal=False,
            raw_payload={},
        ),
        validation_range=ValidationRange(
            start_char=12,
            end_char=22,
            start_token=3,
            end_token=5,
            validated_at_ms=80,
            watermark_event_index=4,
        ),
        raw_event_type="mock_safety.safety_annotation",
        payload_summary="delayed redacted safety annotation",
        metadata={
            "safety_fixture": True,
            "validation_watermark_char": 12,
            "validation_watermark_token": 3,
            "repair_action": "redact_visible_span",
        },
    )
    _emit_clean_terminal(recorder, start_ms=90, terminal_reason=TerminalReasonType.COMPLETE)


def _emit_terminal_refusal(recorder: TraceRecorder) -> None:
    recorder.append(
        EventType.REFUSAL,
        timestamp_ms=30,
        monotonic_time_ns=30_000_000,
        safety_signal=SafetySignal(
            signal_type=SafetySignalType.REFUSAL,
            layer=recorder.layer,
            category="redacted_category_label",
            severity="redacted",
            message=None,
            is_terminal=True,
            raw_payload={},
        ),
        terminal_reason=TerminalReasonType.REFUSAL,
        raw_event_type="mock_safety.refusal",
        payload_summary="terminal redacted refusal signal",
        metadata={
            "safety_fixture": True,
            "repair_action": "reset_or_update_context",
        },
    )
    _emit_clean_terminal(recorder, start_ms=40, terminal_reason=TerminalReasonType.REFUSAL)


def _emit_content_filter(recorder: TraceRecorder) -> None:
    recorder.append(
        EventType.FIRST_TOKEN,
        timestamp_ms=30,
        monotonic_time_ns=30_000_000,
        content=None,
        char_count=3,
        token_count=1,
        raw_event_type="mock_safety.first_token",
        payload_summary="first redacted token available",
        metadata={"content_redacted": True, "safety_fixture": True},
    )
    _emit_redacted_chunk(
        recorder,
        "1",
        timestamp_ms=40,
        char_count=8,
        token_count=2,
    )
    recorder.append(
        EventType.CONTENT_FILTER,
        timestamp_ms=55,
        monotonic_time_ns=55_000_000,
        safety_signal=SafetySignal(
            signal_type=SafetySignalType.CONTENT_FILTER,
            layer=recorder.layer,
            category="redacted_category_label",
            severity="redacted",
            message=None,
            is_terminal=True,
            raw_payload={},
        ),
        validation_range=ValidationRange(
            start_char=0,
            end_char=8,
            start_token=0,
            end_token=2,
            validated_at_ms=55,
            watermark_event_index=4,
        ),
        terminal_reason=TerminalReasonType.CONTENT_FILTER,
        raw_event_type="mock_safety.content_filter",
        payload_summary="terminal redacted content filter signal",
        metadata={
            "safety_fixture": True,
            "validation_watermark_char": 0,
            "validation_watermark_token": 0,
            "repair_action": "drop_or_redact_output",
        },
    )
    _emit_clean_terminal(
        recorder,
        start_ms=65,
        terminal_reason=TerminalReasonType.CONTENT_FILTER,
    )


def _emit_clean_terminal(
    recorder: TraceRecorder,
    *,
    start_ms: int,
    terminal_reason: TerminalReasonType,
) -> None:
    recorder.append(
        EventType.STREAM_END,
        timestamp_ms=start_ms,
        monotonic_time_ns=start_ms * 1_000_000,
        terminal_reason=terminal_reason,
        raw_event_type="mock_safety.stream_end",
        payload_summary="redacted mock safety stream ended",
    )
    recorder.append(
        EventType.FINAL_RESPONSE,
        timestamp_ms=start_ms + 10,
        monotonic_time_ns=(start_ms + 10) * 1_000_000,
        content=None,
        terminal_reason=terminal_reason,
        raw_event_type="mock_safety.final_response",
        payload_summary="redacted final response boundary",
        metadata={"content_redacted": True, "safety_fixture": True},
    )
    recorder.append(
        EventType.ITERATOR_END,
        timestamp_ms=start_ms + 20,
        monotonic_time_ns=(start_ms + 20) * 1_000_000,
        terminal_reason=terminal_reason,
        raw_event_type="mock_safety.iterator_end",
        payload_summary="redacted mock safety iterator exhausted",
    )
    recorder.append(
        EventType.SETTLED,
        timestamp_ms=start_ms + 30,
        monotonic_time_ns=(start_ms + 30) * 1_000_000,
        terminal_reason=terminal_reason,
        raw_event_type="mock_safety.settled",
        payload_summary="redacted mock safety trace settled",
    )
