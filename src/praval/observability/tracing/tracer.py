"""
OpenTelemetry-compatible Tracer implementation.
"""

import logging
import uuid
from typing import Optional

from ..config import get_config
from .context import TraceContext, get_current_span, set_current_span
from .span import NoOpSpan, Span, SpanKind

logger = logging.getLogger(__name__)


def generate_trace_id() -> str:
    """Generate a trace ID (32-character hex string).

    Returns:
        Trace ID string
    """
    return uuid.uuid4().hex  # Returns 32 hex characters


def generate_span_id() -> str:
    """Generate a span ID (16-character hex string).

    Returns:
        Span ID string
    """
    return uuid.uuid4().hex[:16]


class Tracer:
    """OpenTelemetry-compatible tracer for Praval.

    Creates and manages spans for distributed tracing.
    """

    def __init__(self, name: str = "praval"):
        """Initialize tracer.

        Args:
            name: Tracer name
        """
        self.name = name
        self._enabled = True

    def start_span(
        self,
        name: str,
        parent: Optional[TraceContext] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[dict] = None,
    ) -> Span:
        """Start a new span.

        Args:
            name: Span name
            parent: Parent trace context (optional)
            kind: Span kind (default: INTERNAL)
            attributes: Initial attributes (optional)

        Returns:
            New Span instance or NoOpSpan if disabled
        """
        config = get_config()

        # Check if observability is enabled
        if not config.is_enabled():
            return NoOpSpan()

        # Check sampling
        if not config.should_sample():
            return NoOpSpan()

        # Generate IDs
        if parent:
            trace_id = parent.trace_id
            parent_span_id = parent.span_id
        else:
            trace_id = generate_trace_id()
            parent_span_id = None

        span_id = generate_span_id()

        # Create span
        span = Span(
            name=name,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            kind=kind,
            attributes=attributes or {},
        )

        return span

    def start_as_current_span(
        self,
        name: str,
        parent: Optional[TraceContext] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[dict] = None,
    ):
        """Start a new span and set it as current.

        This is a context manager that automatically sets the span as current
        and clears it when done.

        Args:
            name: Span name
            parent: Parent trace context (optional)
            kind: Span kind (default: INTERNAL)
            attributes: Initial attributes (optional)

        Returns:
            Context manager for the span
        """
        parent_context = parent if parent is not None else TraceContext.current()
        span = self.start_span(name, parent_context, kind, attributes)

        class SpanContextManager:
            def __init__(self, span_obj):
                self.span = span_obj
                self.previous_span = None

            def __enter__(self):
                self.previous_span = get_current_span()
                set_current_span(self.span)
                return self.span

            def __exit__(self, exc_type, exc_val, exc_tb):
                try:
                    # Span's own __exit__ records errors and finalizes timing.
                    self.span.__exit__(exc_type, exc_val, exc_tb)
                finally:
                    # Restore context before exporting the completed span.
                    set_current_span(self.previous_span)

                if isinstance(self.span, Span):
                    try:
                        # Import lazily to avoid a tracing/storage import cycle.
                        from ..storage import get_trace_store

                        get_trace_store().store_span(self.span)
                    except Exception:
                        # Observability must not change application behavior.
                        logger.exception("Failed to store completed trace span")
                return False

        return SpanContextManager(span)

    def get_current_span(self) -> Optional[Span]:
        """Get the currently active span.

        Returns:
            Current span or None
        """
        return get_current_span()


# Global tracer instance
_global_tracer: Optional[Tracer] = None


def get_tracer(name: str = "praval") -> Tracer:
    """Get the global tracer instance.

    Args:
        name: Tracer name (default: "praval")

    Returns:
        Tracer instance
    """
    global _global_tracer

    if _global_tracer is None:
        _global_tracer = Tracer(name)

    return _global_tracer


def reset_tracer() -> None:
    """Reset the global tracer to None.

    This is primarily used for testing to ensure test isolation.
    """
    global _global_tracer
    _global_tracer = None
