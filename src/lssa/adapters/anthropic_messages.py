"""Anthropic Messages adapter placeholder for a later benign pilot."""

from __future__ import annotations

from collections.abc import Iterable

from lssa.adapters.base import AdapterRequest
from lssa.schema.events import StreamEvent


class AnthropicMessagesAdapter:
    """Skeleton only. Network execution is intentionally not implemented."""

    provider_family = "Anthropic"
    api_surface = "Messages API"

    def run(self, request: AdapterRequest) -> Iterable[StreamEvent]:
        raise NotImplementedError(
            "Anthropic Messages real adapter is deferred until after the first "
            "benign OpenAI pilot validates the harness."
        )
