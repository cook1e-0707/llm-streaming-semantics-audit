"""Helpers for mapping provider terminal safety reasons to normalized events."""

from __future__ import annotations

from lssa.schema.events import (
    EventType,
    Layer,
    SafetySignal,
    SafetySignalType,
    StreamEvent,
    TerminalReasonType,
)
from lssa.tracing.recorder import TraceRecorder

_CONTENT_FILTER_REASONS = {
    "content_filter",
    "content_filtered",
    "guardrail_intervened",
}
_REFUSAL_REASONS = {"refusal"}


def safety_event_type_from_provider_stop(
    provider_stop_reason: str,
) -> EventType | None:
    """Return the normalized safety event type for a provider stop reason."""

    normalized = provider_stop_reason.strip().lower()
    if normalized in _CONTENT_FILTER_REASONS:
        return EventType.CONTENT_FILTER
    if normalized in _REFUSAL_REASONS:
        return EventType.REFUSAL
    return None


def safety_signal_from_provider_stop(
    provider_stop_reason: str,
) -> SafetySignal | None:
    """Return the normalized safety signal for a provider stop reason."""

    event_type = safety_event_type_from_provider_stop(provider_stop_reason)
    if event_type == EventType.CONTENT_FILTER:
        signal_type = SafetySignalType.CONTENT_FILTER
    elif event_type == EventType.REFUSAL:
        signal_type = SafetySignalType.REFUSAL
    else:
        return None

    return SafetySignal(
        signal_type=signal_type,
        layer=Layer.PROVIDER,
        category=provider_stop_reason,
        is_terminal=True,
        raw_payload={"provider_stop_reason": provider_stop_reason},
    )


def append_provider_safety_signal(
    recorder: TraceRecorder,
    provider_stop_reason: str,
    *,
    terminal_reason: TerminalReasonType,
    raw_event_type: str,
    payload_summary: str,
) -> StreamEvent | None:
    """Append a normalized safety event when a provider stop reason warrants it."""

    event_type = safety_event_type_from_provider_stop(provider_stop_reason)
    safety_signal = safety_signal_from_provider_stop(provider_stop_reason)
    if event_type is None or safety_signal is None:
        return None

    return recorder.append(
        event_type,
        safety_signal=safety_signal,
        terminal_reason=terminal_reason,
        raw_event_type=raw_event_type,
        payload_summary=payload_summary,
        metadata={"provider_stop_reason": provider_stop_reason},
    )
