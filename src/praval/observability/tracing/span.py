"""Compatibility names backed by the official OpenTelemetry trace API."""

from opentelemetry.trace import NonRecordingSpan, Span, SpanKind, StatusCode

# v0.8.2 exposed these names from ``praval.observability.tracing.span``. Keep
# them as direct mappings; Praval no longer owns a second span implementation.
NoOpSpan = NonRecordingSpan
SpanStatus = StatusCode

__all__ = ["NoOpSpan", "Span", "SpanKind", "SpanStatus"]
