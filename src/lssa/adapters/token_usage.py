"""Helpers for recording provider-reported token usage.

The project treats provider usage counters as metadata, not tokenizer-derived
ground truth. If a provider does not expose usage, callers should leave these
fields absent instead of estimating tokens from text.
"""

from __future__ import annotations

from typing import Any


def token_usage_metadata(
    *,
    input_tokens: Any = None,
    output_tokens: Any = None,
    total_tokens: Any = None,
    source: str,
) -> dict[str, int | str]:
    """Return normalized provider token metadata with absent values omitted."""

    normalized_input = _int_or_none(input_tokens)
    normalized_output = _int_or_none(output_tokens)
    normalized_total = _int_or_none(total_tokens)
    if normalized_total is None and (
        normalized_input is not None or normalized_output is not None
    ):
        normalized_total = (normalized_input or 0) + (normalized_output or 0)

    metadata: dict[str, int | str] = {}
    if normalized_input is not None:
        metadata["provider_input_tokens"] = normalized_input
    if normalized_output is not None:
        metadata["provider_output_tokens"] = normalized_output
    if normalized_total is not None:
        metadata["provider_total_tokens"] = normalized_total
    if metadata:
        metadata["provider_token_usage_source"] = source
    return metadata


def output_token_count(metadata: dict[str, Any]) -> int | None:
    """Return the provider output token count stored in normalized metadata."""

    return _int_or_none(metadata.get("provider_output_tokens"))


def merge_token_usage(
    existing: dict[str, int | str],
    update: dict[str, int | str],
) -> dict[str, int | str]:
    """Merge partial provider usage metadata, preserving known values."""

    merged = dict(existing)
    for key, value in update.items():
        if key not in merged or merged[key] in {None, "unknown"}:
            merged[key] = value
        elif key == "provider_output_tokens":
            # Some streaming providers report cumulative output tokens near the
            # end of the stream. Keep the largest observed value.
            current = _int_or_none(merged[key])
            incoming = _int_or_none(value)
            if current is None or (incoming is not None and incoming > current):
                merged[key] = value
        elif key == "provider_total_tokens":
            current = _int_or_none(merged[key])
            incoming = _int_or_none(value)
            if current is None or (incoming is not None and incoming > current):
                merged[key] = value
    return merged


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None
