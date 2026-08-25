"""Compatibility context values backed by OpenTelemetry context propagation.

The v0.8.2 ``TraceContext`` name remains available for existing Spore helpers.
Current-span storage and async isolation are provided entirely by the official
OpenTelemetry context API. W3C Spore propagation replaces the legacy metadata
keys in work package O4.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any, Dict, Optional

from opentelemetry import propagate
from opentelemetry.context import Context
from opentelemetry.trace import (
    NonRecordingSpan,
    Span,
    SpanContext,
    TraceFlags,
    TraceState,
    get_current_span,
    set_span_in_context,
)


@dataclass(frozen=True)
class TraceContext:
    """Hex-encoded trace and parent-span identity for legacy Spore metadata."""

    trace_id: str
    span_id: str
    trace_flags: int = int(TraceFlags.SAMPLED)

    def __post_init__(self) -> None:
        """Require identifiers accepted by the OpenTelemetry API."""
        if not _valid_identifier(self.trace_id, 32):
            raise ValueError("trace_id must be 32 lowercase hexadecimal characters")
        if not _valid_identifier(self.span_id, 16):
            raise ValueError("span_id must be 16 lowercase hexadecimal characters")
        supported_flags = int(TraceFlags.SAMPLED) | int(TraceFlags.RANDOM_TRACE_ID)
        if self.trace_flags < 0 or self.trace_flags & ~supported_flags:
            raise ValueError("trace_flags contains unsupported bits")

    @classmethod
    def from_span(cls, span: Span) -> "TraceContext":
        """Create a compatibility value from an official span."""
        context = span.get_span_context()
        if not context.is_valid:
            raise ValueError("cannot create TraceContext from an invalid span")
        return cls(
            trace_id=f"{context.trace_id:032x}",
            span_id=f"{context.span_id:016x}",
            trace_flags=int(context.trace_flags),
        )

    @classmethod
    def from_spore(cls, spore: Any) -> "TraceContext | None":
        """Read supported v0.8.2 trace fields from Spore metadata."""
        metadata = getattr(spore, "metadata", None)
        if not isinstance(metadata, Mapping):
            return None
        trace_id = metadata.get("trace_id")
        span_id = metadata.get("span_id")
        flags = metadata.get("trace_flags", int(TraceFlags.SAMPLED))
        if not isinstance(trace_id, str) or not isinstance(span_id, str):
            return None
        if not isinstance(flags, int):
            return None
        try:
            return cls(trace_id=trace_id, span_id=span_id, trace_flags=flags)
        except ValueError:
            return None

    @classmethod
    def current(cls) -> "TraceContext | None":
        """Return the current valid OpenTelemetry span context, if one exists."""
        span = get_current_span()
        if not span.get_span_context().is_valid:
            return None
        return cls.from_span(span)

    def as_context(self) -> Context:
        """Return an official remote-parent context for span creation."""
        span_context = SpanContext(
            trace_id=int(self.trace_id, 16),
            span_id=int(self.span_id, 16),
            is_remote=True,
            trace_flags=TraceFlags(self.trace_flags),
            trace_state=TraceState(),
        )
        return set_span_in_context(NonRecordingSpan(span_context))

    def inject_into_spore(self, spore: Any) -> None:
        """Write supported v0.8.2 trace fields to mutable Spore metadata."""
        if not hasattr(spore, "metadata"):
            return
        metadata = getattr(spore, "metadata", None)
        if not isinstance(metadata, MutableMapping):
            metadata = {}
            spore.metadata = metadata
        metadata["trace_id"] = self.trace_id
        metadata["span_id"] = self.span_id
        metadata["trace_flags"] = self.trace_flags


def inject_trace_context(context: Optional[Context] = None) -> Dict[str, str]:
    """Inject the configured OpenTelemetry propagator into a text carrier."""
    carrier: Dict[str, str] = {}
    propagate.inject(carrier, context=context)
    return carrier


def extract_trace_context(carrier: Mapping[str, str]) -> Context:
    """Extract a remote parent with the configured OpenTelemetry propagator."""
    return propagate.extract(dict(carrier))


def _valid_identifier(value: str, length: int) -> bool:
    if len(value) != length or value == "0" * length:
        return False
    return all(character in "0123456789abcdef" for character in value)


__all__ = [
    "TraceContext",
    "extract_trace_context",
    "get_current_span",
    "inject_trace_context",
]
