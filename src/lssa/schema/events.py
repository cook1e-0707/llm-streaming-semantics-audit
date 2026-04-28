"""Typed trace schemas for streaming semantics audits."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Self


class Layer(str, Enum):
    """Observable layer where an event was captured."""

    PROVIDER = "provider"
    SDK = "sdk"
    FRAMEWORK = "framework"
    APPLICATION = "application"
    USER_VISIBLE = "user_visible"


class ResponseMode(str, Enum):
    """High-level response transport mode."""

    STREAMING = "streaming"
    NON_STREAMING = "non_streaming"
    UNKNOWN = "unknown"


class ReleasePolicy(str, Enum):
    """Policy controlling when content is released downstream."""

    BLOCKING = "blocking"
    BUFFERED_STREAMING = "buffered_streaming"
    IMMEDIATE_STREAMING = "immediate_streaming"
    UNKNOWN = "unknown"


class EventType(str, Enum):
    """Trace event kinds supported by the Phase 0 schema."""

    REQUEST_START = "request_start"
    REQUEST_SENT = "request_sent"
    FIRST_BYTE = "first_byte"
    FIRST_TOKEN = "first_token"
    CHUNK = "chunk"
    SAFETY_ANNOTATION = "safety_annotation"
    REFUSAL = "refusal"
    CONTENT_FILTER = "content_filter"
    TOOL_CALL_DELTA = "tool_call_delta"
    TOOL_CALL_COMMIT = "tool_call_commit"
    STREAM_END = "stream_end"
    FINAL_RESPONSE = "final_response"
    ITERATOR_END = "iterator_end"
    SETTLED = "settled"
    CANCEL = "cancel"
    ERROR = "error"


class SafetySignalType(str, Enum):
    """Safety-relevant signal kinds."""

    ANNOTATION = "annotation"
    REFUSAL = "refusal"
    CONTENT_FILTER = "content_filter"
    BLOCK = "block"
    WARNING = "warning"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


class TerminalReasonType(str, Enum):
    """Normalized terminal reasons for trace summaries and terminal events."""

    COMPLETE = "complete"
    STOP = "stop"
    LENGTH = "length"
    REFUSAL = "refusal"
    CONTENT_FILTER = "content_filter"
    TOOL_CALL = "tool_call"
    CANCEL = "cancel"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TraceIdentity:
    """Stable identifiers and declared response semantics for one trace."""

    trace_id: str
    provider_family: str = "unknown"
    provider_model: str = "unknown"
    response_mode: ResponseMode = ResponseMode.UNKNOWN
    release_policy: ReleasePolicy = ReleasePolicy.UNKNOWN
    started_at_utc: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        payload = dict(data)
        payload["response_mode"] = ResponseMode(payload["response_mode"])
        payload["release_policy"] = ReleasePolicy(payload["release_policy"])
        if payload.get("started_at_utc") is not None:
            payload["started_at_utc"] = _parse_datetime(payload["started_at_utc"])
        return cls(**payload)


@dataclass(frozen=True)
class SafetySignal:
    """Safety signal attached to a trace event."""

    signal_type: SafetySignalType
    layer: Layer
    category: str | None = None
    severity: str | None = None
    message: str | None = None
    is_terminal: bool = False
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        payload = dict(data)
        payload["signal_type"] = SafetySignalType(payload["signal_type"])
        payload["layer"] = Layer(payload["layer"])
        return cls(**payload)


@dataclass(frozen=True)
class ValidationRange:
    """Observable content span covered by validation or invalidation."""

    start_char: int | None = None
    end_char: int | None = None
    start_token: int | None = None
    end_token: int | None = None
    start_byte: int | None = None
    end_byte: int | None = None
    validated_at_ms: float | None = None
    watermark_event_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(**data)


@dataclass(frozen=True)
class StreamEvent:
    """One ordered observable event in a trace."""

    trace_id: str
    event_type: EventType
    layer: Layer
    timestamp_ms: float
    sequence_index: int
    content: str | None = None
    token_count: int | None = None
    char_count: int | None = None
    byte_count: int | None = None
    safety_signal: SafetySignal | None = None
    validation_range: ValidationRange | None = None
    terminal_reason: TerminalReasonType | None = None
    tool_call_id: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp_ms < 0:
            raise ValueError("timestamp_ms must be non-negative")
        if self.sequence_index < 0:
            raise ValueError("sequence_index must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        payload = dict(data)
        payload["event_type"] = EventType(payload["event_type"])
        payload["layer"] = Layer(payload["layer"])
        if payload.get("safety_signal") is not None:
            payload["safety_signal"] = SafetySignal.from_dict(payload["safety_signal"])
        if payload.get("validation_range") is not None:
            payload["validation_range"] = ValidationRange.from_dict(
                payload["validation_range"]
            )
        if payload.get("terminal_reason") is not None:
            payload["terminal_reason"] = TerminalReasonType(payload["terminal_reason"])
        return cls(**payload)


@dataclass(frozen=True)
class TraceSummary:
    """Summary object for one completed or partial trace."""

    identity: TraceIdentity
    events: list[StreamEvent]
    terminal_reason: TerminalReasonType | None = None
    settled: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def sorted_events(self) -> list[StreamEvent]:
        return sorted(self.events, key=lambda event: event.sequence_index)

    def to_dict(self) -> dict[str, Any]:
        return _to_serializable_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        payload = dict(data)
        payload["identity"] = TraceIdentity.from_dict(payload["identity"])
        payload["events"] = [
            StreamEvent.from_dict(event_data) for event_data in payload["events"]
        ]
        if payload.get("terminal_reason") is not None:
            payload["terminal_reason"] = TerminalReasonType(payload["terminal_reason"])
        return cls(**payload)


def _to_serializable_dict(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, list):
        return [_to_serializable_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_serializable_dict(item) for key, item in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return _to_serializable_dict(asdict(value))
    return value


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
