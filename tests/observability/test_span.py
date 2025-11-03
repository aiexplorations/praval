"""
Tests for Span implementation.
"""

import time
import pytest

from praval.observability.tracing.span import (
    Span,
    SpanKind,
    SpanStatus,
    SpanEvent,
    NoOpSpan
)


class TestSpan:
    """Tests for Span."""

    def test_span_creation(self):
        """Test creating a span."""
        span = Span(
            name="test.operation",
            trace_id="abc123",
            span_id="def456"
        )

        assert span.name == "test.operation"
        assert span.trace_id == "abc123"
        assert span.span_id == "def456"
        assert span.parent_span_id is None
        assert span.kind == SpanKind.INTERNAL
        assert span.status == SpanStatus.UNSET
        assert span.is_recording() is True

    def test_span_with_parent(self):
        """Test span with parent."""
        span = Span(
            name="child.operation",
            trace_id="abc123",
            span_id="child456",
            parent_span_id="parent789"
        )

        assert span.parent_span_id == "parent789"
        assert span.trace_id == "abc123"  # Inherits trace ID

    def test_set_attribute(self):
        """Test setting attributes."""
        span = Span(name="test", trace_id="123", span_id="456")

        span.set_attribute("key1", "value1")
        span.set_attribute("key2", 42)

        assert span.attributes["key1"] == "value1"
        assert span.attributes["key2"] == 42

    def test_add_event(self):
        """Test adding events."""
        span = Span(name="test", trace_id="123", span_id="456")

        span.add_event("event1", {"detail": "test"})

        assert len(span.events) == 1
        assert span.events[0].name == "event1"
        assert span.events[0].attributes["detail"] == "test"

    def test_record_exception(self):
        """Test recording exceptions."""
        span = Span(name="test", trace_id="123", span_id="456")

        try:
            raise ValueError("Test error")
        except ValueError as e:
            span.record_exception(e)

        assert len(span.events) == 1
        assert span.events[0].name == "exception"
        assert "ValueError" in span.events[0].attributes["exception.type"]
        assert "Test error" in span.events[0].attributes["exception.message"]

    def test_set_status(self):
        """Test setting span status."""
        span = Span(name="test", trace_id="123", span_id="456")

        span.set_status("ok")
        assert span.status == SpanStatus.OK

        span.set_status("error", "Something went wrong")
        assert span.status == SpanStatus.ERROR
        assert span.status_message == "Something went wrong"

    def test_span_end(self):
        """Test ending a span."""
        span = Span(name="test", trace_id="123", span_id="456")
        start_time = span.start_time

        time.sleep(0.01)  # Small delay
        span.end()

        assert span.end_time is not None
        assert span.end_time > start_time
        assert span.is_recording() is False

    def test_span_duration(self):
        """Test calculating span duration."""
        span = Span(name="test", trace_id="123", span_id="456")

        time.sleep(0.01)  # 10ms delay
        span.end()

        duration = span.duration_ms()
        assert duration > 0
        assert duration >= 10  # At least 10ms

    def test_context_manager_success(self):
        """Test span as context manager (success case)."""
        span = Span(name="test", trace_id="123", span_id="456")

        with span:
            span.set_attribute("operation", "test")
            time.sleep(0.01)

        assert span.end_time is not None
        assert span.status == SpanStatus.UNSET  # No exception
        assert span.is_recording() is False

    def test_context_manager_exception(self):
        """Test span as context manager (exception case)."""
        span = Span(name="test", trace_id="123", span_id="456")

        with pytest.raises(ValueError):
            with span:
                raise ValueError("Test error")

        assert span.end_time is not None
        assert span.status == SpanStatus.ERROR
        assert len(span.events) == 1  # Exception recorded
        assert "ValueError" in span.events[0].attributes["exception.type"]

    def test_span_to_dict(self):
        """Test converting span to dictionary."""
        span = Span(
            name="test",
            trace_id="abc123",
            span_id="def456",
            kind=SpanKind.CLIENT
        )
        span.set_attribute("key", "value")
        span.end()

        span_dict = span.to_dict()

        assert span_dict["name"] == "test"
        assert span_dict["trace_id"] == "abc123"
        assert span_dict["span_id"] == "def456"
        assert span_dict["kind"] == "CLIENT"
        assert span_dict["attributes"]["key"] == "value"
        assert span_dict["duration_ms"] > 0

    def test_span_to_otlp(self):
        """Test converting span to OTLP format."""
        span = Span(
            name="test",
            trace_id="abc123",
            span_id="def456"
        )
        span.set_attribute("key", "value")
        span.end()

        otlp = span.to_otlp()

        assert otlp["name"] == "test"
        assert otlp["traceId"] == "abc123"
        assert otlp["spanId"] == "def456"
        assert otlp["status"]["code"] == "UNSET"
        # Attributes in OTLP format
        assert any(
            attr["key"] == "key" and attr["value"]["stringValue"] == "value"
            for attr in otlp["attributes"]
        )


class TestNoOpSpan:
    """Tests for NoOpSpan."""

    def test_noop_span_methods(self):
        """Test that NoOpSpan methods do nothing."""
        span = NoOpSpan()

        # All methods should be no-ops (no exceptions)
        span.set_attribute("key", "value")
        span.add_event("event")
        span.record_exception(Exception("test"))
        span.set_status("ok")
        span.end()

        assert span.is_recording() is False

    def test_noop_span_context_manager(self):
        """Test NoOpSpan as context manager."""
        span = NoOpSpan()

        with span:
            pass  # No-op

        # Should not raise exceptions
        assert True


class TestSpanKind:
    """Tests for SpanKind enum."""

    def test_span_kinds(self):
        """Test all span kinds."""
        assert SpanKind.INTERNAL.value == "INTERNAL"
        assert SpanKind.CLIENT.value == "CLIENT"
        assert SpanKind.SERVER.value == "SERVER"
        assert SpanKind.PRODUCER.value == "PRODUCER"
        assert SpanKind.CONSUMER.value == "CONSUMER"


class TestSpanStatus:
    """Tests for SpanStatus enum."""

    def test_span_statuses(self):
        """Test all span statuses."""
        assert SpanStatus.UNSET.value == "UNSET"
        assert SpanStatus.OK.value == "OK"
        assert SpanStatus.ERROR.value == "ERROR"
