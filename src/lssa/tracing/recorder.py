"""Trace recorder for normalized stream events."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic_ns
from typing import Any
from uuid import uuid4

from lssa.schema.events import (
    EventType,
    Layer,
    ReleasePolicy,
    ResponseMode,
    SafetySignal,
    StreamEvent,
    TerminalReasonType,
    TraceIdentity,
    TraceSummary,
    ValidationRange,
)


@dataclass
class TraceRecorder:
    """Collect, sequence, and persist normalized stream events."""

    provider_family: str
    api_surface: str
    model: str
    response_mode: ResponseMode
    trace_id: str = field(default_factory=lambda: f"trace-{uuid4().hex}")
    layer: Layer = Layer.PROVIDER
    release_policy: ReleasePolicy = ReleasePolicy.UNKNOWN
    started_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    events: list[StreamEvent] = field(default_factory=list)
    _last_monotonic_time_ns: int | None = None

    def append(
        self,
        event_type: EventType,
        *,
        timestamp_ms: float | None = None,
        monotonic_time_ns: int | None = None,
        wall_time_iso: str | None = None,
        content: str | None = None,
        token_count: int | None = None,
        char_count: int | None = None,
        byte_count: int | None = None,
        safety_signal: SafetySignal | None = None,
        validation_range: ValidationRange | None = None,
        terminal_reason: TerminalReasonType | None = None,
        raw_event_type: str | None = None,
        payload_summary: str | None = None,
        payload_redacted: bool = True,
        raw_payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StreamEvent:
        """Append one event and assign a contiguous sequence index."""

        sequence_index = len(self.events)
        if monotonic_time_ns is None:
            monotonic_time_ns = monotonic_ns()
        if self._last_monotonic_time_ns is not None:
            monotonic_time_ns = max(monotonic_time_ns, self._last_monotonic_time_ns)
        self._last_monotonic_time_ns = monotonic_time_ns

        if timestamp_ms is None:
            timestamp_ms = monotonic_time_ns / 1_000_000
        if wall_time_iso is None:
            wall_time_iso = datetime.now(timezone.utc).isoformat()

        event_metadata = {
            "provider_family": self.provider_family,
            "api_surface": self.api_surface,
            "model": self.model,
            "monotonic_time_ns": monotonic_time_ns,
            "wall_time_iso": wall_time_iso,
            "payload_redacted": payload_redacted,
        }
        if raw_event_type is not None:
            event_metadata["raw_event_type"] = raw_event_type
        if payload_summary is not None:
            event_metadata["payload_summary"] = payload_summary
        if metadata:
            event_metadata.update(metadata)

        event = StreamEvent(
            trace_id=self.trace_id,
            event_type=event_type,
            layer=self.layer,
            timestamp_ms=timestamp_ms,
            sequence_index=sequence_index,
            content=content,
            token_count=token_count,
            char_count=char_count,
            byte_count=byte_count,
            safety_signal=safety_signal,
            validation_range=validation_range,
            terminal_reason=terminal_reason,
            raw_payload=raw_payload or {},
            metadata=event_metadata,
        )
        self.events.append(event)
        return event

    def extend(self, events: list[StreamEvent]) -> None:
        """Append already-normalized events while preserving their content."""

        for event in events:
            copied = StreamEvent(
                trace_id=self.trace_id,
                event_type=event.event_type,
                layer=event.layer,
                timestamp_ms=event.timestamp_ms,
                sequence_index=len(self.events),
                content=event.content,
                token_count=event.token_count,
                char_count=event.char_count,
                byte_count=event.byte_count,
                safety_signal=event.safety_signal,
                validation_range=event.validation_range,
                terminal_reason=event.terminal_reason,
                tool_call_id=event.tool_call_id,
                raw_payload=event.raw_payload,
                metadata=dict(event.metadata),
            )
            self.events.append(copied)

    def summary(self) -> TraceSummary:
        identity = TraceIdentity(
            trace_id=self.trace_id,
            provider_family=self.provider_family,
            provider_model=self.model,
            response_mode=self.response_mode,
            release_policy=self.release_policy,
            started_at_utc=self.started_at_utc,
            metadata={"api_surface": self.api_surface},
        )
        settled = any(event.event_type == EventType.SETTLED for event in self.events)
        terminal_reason = _last_terminal_reason(self.events)
        return TraceSummary(
            identity=identity,
            events=list(self.events),
            terminal_reason=terminal_reason,
            settled=settled,
            metadata={"event_count": len(self.events)},
        )

    def write_jsonl(self, path: Path, *, redact_content: bool = False) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for event in self.events:
                handle.write(
                    json.dumps(_event_to_dict(event, redact_content), sort_keys=True)
                    + "\n"
                )
        return path

    def write_summary_json(self, path: Path, *, redact_content: bool = False) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        summary = self.summary().to_dict()
        if redact_content:
            for event in summary["events"]:
                _redact_event_content(event)
            summary["metadata"]["content_redacted"] = True
        path.write_text(
            json.dumps(summary, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return path


def _event_to_dict(event: StreamEvent, redact_content: bool) -> dict[str, Any]:
    data = event.to_dict()
    if redact_content:
        _redact_event_content(data)
    return data


def _redact_event_content(event: dict[str, Any]) -> None:
    if event.get("content") is not None:
        event["content"] = None
        metadata = dict(event.get("metadata") or {})
        metadata["content_redacted"] = True
        event["metadata"] = metadata


def _last_terminal_reason(events: list[StreamEvent]) -> TerminalReasonType | None:
    for event in reversed(events):
        if event.terminal_reason is not None:
            return event.terminal_reason
    return None
