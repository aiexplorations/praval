"""
Tracing module for Praval observability.

Provides OpenTelemetry-compatible tracing infrastructure.
"""

from .context import (
    TraceContext,
    clear_current_span,
    get_current_span,
    set_current_span,
)
from .span import NoOpSpan, Span, SpanEvent, SpanKind, SpanStatus
from .tracer import Tracer, get_tracer

__all__ = [
    # Span
    "Span",
    "SpanKind",
    "SpanStatus",
    "SpanEvent",
    "NoOpSpan",
    # Context
    "TraceContext",
    "get_current_span",
    "set_current_span",
    "clear_current_span",
    # Tracer
    "Tracer",
    "get_tracer",
]
