"""Provider-neutral adapter contract."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

from lssa.schema.events import ResponseMode, StreamEvent


@dataclass(frozen=True)
class AdapterRequest:
    """Provider-neutral request passed to an adapter."""

    trace_id: str
    prompt_id: str
    prompt: str
    response_mode: ResponseMode
    model: str = "mock-model"
    provider_family: str = "mock"
    api_surface: str = "mock"
    max_output_tokens: int = 128
    metadata: dict[str, str] = field(default_factory=dict)


class ProviderAdapter(Protocol):
    """Adapter interface that emits normalized trace events."""

    provider_family: str
    api_surface: str

    def run(self, request: AdapterRequest) -> Iterable[StreamEvent]:
        """Return normalized StreamEvent objects for one request."""
