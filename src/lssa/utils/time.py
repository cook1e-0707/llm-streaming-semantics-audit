"""Time helpers for trace collection."""

from __future__ import annotations

from datetime import datetime, timezone
from time import monotonic_ns


def utc_now() -> datetime:
    """Return the current UTC datetime."""

    return datetime.now(timezone.utc)


def monotonic_ms() -> float:
    """Return a monotonic timestamp in milliseconds."""

    return monotonic_ns() / 1_000_000
