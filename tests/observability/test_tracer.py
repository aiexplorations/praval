"""
Tests for Tracer implementation.
"""

import os
import pytest

from praval.observability.tracing.tracer import (
    Tracer,
    get_tracer,
    generate_trace_id,
    generate_span_id
)
from praval.observability.tracing.span import Span, SpanKind, NoOpSpan
from praval.observability.tracing.context import TraceContext
from praval.observability.config import reset_config


class TestTracer:
    """Tests for Tracer."""

    def setup_method(self):
        """Reset config before each test."""
        reset_config()
        # Enable observability
        os.environ["PRAVAL_OBSERVABILITY"] = "on"

    def teardown_method(self):
        """Clean up after each test."""
        reset_config()
        if "PRAVAL_OBSERVABILITY" in os.environ:
            del os.environ["PRAVAL_OBSERVABILITY"]

    def test_tracer_creation(self):
        """Test creating a tracer."""
        tracer = Tracer("test-tracer")
        assert tracer.name == "test-tracer"

    def test_start_span_basic(self):
        """Test starting a basic span."""
        tracer = Tracer()
        span = tracer.start_span("test.operation")

        assert isinstance(span, Span)
        assert span.name == "test.operation"
        assert span.trace_id is not None
        assert span.span_id is not None
        assert span.parent_span_id is None
        assert span.kind == SpanKind.INTERNAL

    def test_start_span_with_parent(self):
        """Test starting a span with parent context."""
        tracer = Tracer()

        # Create parent span
        parent_span = tracer.start_span("parent")
        parent_context = TraceContext.from_span(parent_span)

        # Create child span
        child_span = tracer.start_span("child", parent=parent_context)

        assert child_span.trace_id == parent_span.trace_id
        assert child_span.parent_span_id == parent_span.span_id
        assert child_span.span_id != parent_span.span_id

    def test_start_span_with_kind(self):
        """Test starting span with specific kind."""
        tracer = Tracer()
        span = tracer.start_span("client.operation", kind=SpanKind.CLIENT)

        assert span.kind == SpanKind.CLIENT

    def test_start_span_with_attributes(self):
        """Test starting span with initial attributes."""
        tracer = Tracer()
        span = tracer.start_span(
            "test",
            attributes={"key1": "value1", "key2": 42}
        )

        assert span.attributes["key1"] == "value1"
        assert span.attributes["key2"] == 42

    def test_start_span_disabled(self):
        """Test starting span when observability is disabled."""
        os.environ["PRAVAL_OBSERVABILITY"] = "off"
        reset_config()

        tracer = Tracer()
        span = tracer.start_span("test")

        assert isinstance(span, NoOpSpan)

    def test_start_span_sampling(self):
        """Test span sampling."""
        os.environ["PRAVAL_SAMPLE_RATE"] = "0.0"  # Never sample
        reset_config()

        tracer = Tracer()
        span = tracer.start_span("test")

        assert isinstance(span, NoOpSpan)

    def test_start_as_current_span(self):
        """Test starting span as current."""
        # Ensure sampling is enabled
        os.environ["PRAVAL_SAMPLE_RATE"] = "1.0"
        reset_config()

        tracer = Tracer()

        with tracer.start_as_current_span("test") as span:
            # Span should be current
            assert tracer.get_current_span() is span
            assert isinstance(span, Span)
            assert span.name == "test"

        # Span should no longer be current
        assert tracer.get_current_span() is None

    def test_start_as_current_span_nested(self):
        """Test nested current spans."""
        tracer = Tracer()

        with tracer.start_as_current_span("parent") as parent:
            assert tracer.get_current_span() is parent

            with tracer.start_as_current_span("child") as child:
                assert tracer.get_current_span() is child

            # Should restore parent as current
            assert tracer.get_current_span() is parent

        # Should clear current span
        assert tracer.get_current_span() is None

    def test_start_as_current_span_with_exception(self):
        """Test current span with exception."""
        tracer = Tracer()

        with pytest.raises(ValueError):
            with tracer.start_as_current_span("test") as span:
                raise ValueError("Test error")

        # Span should be ended and cleared
        assert tracer.get_current_span() is None

    def test_global_tracer(self):
        """Test global tracer singleton."""
        tracer1 = get_tracer()
        tracer2 = get_tracer()

        assert tracer1 is tracer2
        assert tracer1.name == "praval"

    def test_global_tracer_with_name(self):
        """Test global tracer with custom name."""
        tracer = get_tracer("custom-name")
        assert tracer.name == "praval"  # Still uses same instance


class TestIDGeneration:
    """Tests for ID generation."""

    def test_generate_trace_id(self):
        """Test trace ID generation."""
        trace_id = generate_trace_id()

        assert isinstance(trace_id, str)
        assert len(trace_id) == 32  # 32 hex characters
        assert all(c in "0123456789abcdef" for c in trace_id)

    def test_generate_trace_id_unique(self):
        """Test that trace IDs are unique."""
        ids = [generate_trace_id() for _ in range(100)]
        assert len(set(ids)) == 100  # All unique

    def test_generate_span_id(self):
        """Test span ID generation."""
        span_id = generate_span_id()

        assert isinstance(span_id, str)
        assert len(span_id) == 16  # 16 hex characters
        assert all(c in "0123456789abcdef" for c in span_id)

    def test_generate_span_id_unique(self):
        """Test that span IDs are unique."""
        ids = [generate_span_id() for _ in range(100)]
        assert len(set(ids)) == 100  # All unique
