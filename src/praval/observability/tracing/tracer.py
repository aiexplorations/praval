"""Official OpenTelemetry tracer compatibility facade."""

from __future__ import annotations

import secrets

from opentelemetry.trace import Tracer

from ..lifecycle import get_tracer


def generate_trace_id() -> str:
    """Generate a valid non-zero OpenTelemetry trace identifier."""
    return f"{secrets.randbits(128) or 1:032x}"


def generate_span_id() -> str:
    """Generate a valid non-zero OpenTelemetry span identifier."""
    return f"{secrets.randbits(64) or 1:016x}"


def reset_tracer() -> None:
    """Retain the old test hook; tracer ownership now lives in lifecycle."""


__all__ = [
    "Tracer",
    "generate_span_id",
    "generate_trace_id",
    "get_tracer",
    "reset_tracer",
]
