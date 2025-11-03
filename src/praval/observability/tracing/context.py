"""
Trace context propagation.

Handles propagation of trace context through Spore metadata and thread-local storage.
"""

import threading
from typing import Optional

from .span import Span


# Thread-local storage for current span
_current_span = threading.local()


class TraceContext:
    """Trace context for propagation across agent boundaries."""

    def __init__(self, trace_id: str, span_id: str):
        """Initialize trace context.

        Args:
            trace_id: Trace identifier
            span_id: Span identifier (parent for new spans)
        """
        self.trace_id = trace_id
        self.span_id = span_id

    @classmethod
    def from_span(cls, span: Span) -> 'TraceContext':
        """Create trace context from a span.

        Args:
            span: Span to extract context from

        Returns:
            TraceContext instance
        """
        return cls(trace_id=span.trace_id, span_id=span.span_id)

    @classmethod
    def from_spore(cls, spore) -> Optional['TraceContext']:
        """Extract trace context from Spore metadata.

        Args:
            spore: Spore object

        Returns:
            TraceContext if found in metadata, None otherwise
        """
        if not hasattr(spore, 'metadata') or not spore.metadata:
            return None

        metadata = spore.metadata
        if "trace_id" in metadata and "span_id" in metadata:
            return cls(
                trace_id=metadata["trace_id"],
                span_id=metadata["span_id"]
            )

        return None

    def inject_into_spore(self, spore) -> None:
        """Inject trace context into Spore metadata.

        Args:
            spore: Spore object to inject context into
        """
        if not hasattr(spore, 'metadata'):
            return

        if spore.metadata is None:
            spore.metadata = {}

        spore.metadata["trace_id"] = self.trace_id
        spore.metadata["span_id"] = self.span_id

    @classmethod
    def current(cls) -> Optional['TraceContext']:
        """Get current trace context from thread-local storage.

        Returns:
            TraceContext if available, None otherwise
        """
        span = get_current_span()
        if span:
            return cls.from_span(span)
        return None


def get_current_span() -> Optional[Span]:
    """Get the currently active span from thread-local storage.

    Returns:
        Current Span if available, None otherwise
    """
    return getattr(_current_span, 'span', None)


def set_current_span(span: Optional[Span]) -> None:
    """Set the currently active span in thread-local storage.

    Args:
        span: Span to set as current, or None to clear
    """
    _current_span.span = span


def clear_current_span() -> None:
    """Clear the currently active span from thread-local storage."""
    _current_span.span = None
