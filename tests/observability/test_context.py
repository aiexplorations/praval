"""
Tests for trace context propagation.
"""

import pytest

from praval.observability.tracing.context import (
    TraceContext,
    get_current_span,
    set_current_span,
    clear_current_span
)
from praval.observability.tracing.span import Span


class MockSpore:
    """Mock Spore for testing."""

    def __init__(self, metadata=None):
        self.metadata = metadata or {}


class TestTraceContext:
    """Tests for TraceContext."""

    def test_context_creation(self):
        """Test creating trace context."""
        context = TraceContext(trace_id="abc123", span_id="def456")

        assert context.trace_id == "abc123"
        assert context.span_id == "def456"

    def test_from_span(self):
        """Test creating context from span."""
        span = Span(
            name="test",
            trace_id="trace123",
            span_id="span456"
        )

        context = TraceContext.from_span(span)

        assert context.trace_id == "trace123"
        assert context.span_id == "span456"

    def test_from_spore_with_context(self):
        """Test extracting context from spore with metadata."""
        spore = MockSpore(metadata={
            "trace_id": "trace123",
            "span_id": "span456"
        })

        context = TraceContext.from_spore(spore)

        assert context is not None
        assert context.trace_id == "trace123"
        assert context.span_id == "span456"

    def test_from_spore_without_context(self):
        """Test extracting context from spore without metadata."""
        spore = MockSpore()

        context = TraceContext.from_spore(spore)

        assert context is None

    def test_from_spore_partial_metadata(self):
        """Test extracting context from spore with partial metadata."""
        spore = MockSpore(metadata={"trace_id": "trace123"})

        context = TraceContext.from_spore(spore)

        assert context is None  # Need both trace_id and span_id

    def test_inject_into_spore(self):
        """Test injecting context into spore."""
        context = TraceContext(trace_id="trace123", span_id="span456")
        spore = MockSpore()

        context.inject_into_spore(spore)

        assert spore.metadata["trace_id"] == "trace123"
        assert spore.metadata["span_id"] == "span456"

    def test_inject_into_spore_preserves_other_metadata(self):
        """Test that injection preserves existing metadata."""
        context = TraceContext(trace_id="trace123", span_id="span456")
        spore = MockSpore(metadata={"other_key": "other_value"})

        context.inject_into_spore(spore)

        assert spore.metadata["trace_id"] == "trace123"
        assert spore.metadata["span_id"] == "span456"
        assert spore.metadata["other_key"] == "other_value"

    def test_current_context_from_span(self):
        """Test getting current context from active span."""
        span = Span(name="test", trace_id="trace123", span_id="span456")
        set_current_span(span)

        context = TraceContext.current()

        assert context is not None
        assert context.trace_id == "trace123"
        assert context.span_id == "span456"

        clear_current_span()

    def test_current_context_no_span(self):
        """Test getting current context when no span is active."""
        clear_current_span()

        context = TraceContext.current()

        assert context is None


class TestThreadLocalSpanStorage:
    """Tests for thread-local span storage."""

    def setup_method(self):
        """Clear span before each test."""
        clear_current_span()

    def teardown_method(self):
        """Clear span after each test."""
        clear_current_span()

    def test_get_current_span_empty(self):
        """Test getting current span when none set."""
        span = get_current_span()
        assert span is None

    def test_set_and_get_current_span(self):
        """Test setting and getting current span."""
        test_span = Span(name="test", trace_id="123", span_id="456")

        set_current_span(test_span)
        current = get_current_span()

        assert current is test_span

    def test_clear_current_span(self):
        """Test clearing current span."""
        test_span = Span(name="test", trace_id="123", span_id="456")

        set_current_span(test_span)
        assert get_current_span() is test_span

        clear_current_span()
        assert get_current_span() is None

    def test_set_current_span_overwrites(self):
        """Test that setting span overwrites previous."""
        span1 = Span(name="span1", trace_id="123", span_id="456")
        span2 = Span(name="span2", trace_id="789", span_id="abc")

        set_current_span(span1)
        set_current_span(span2)

        current = get_current_span()
        assert current is span2

    def test_set_none_clears_span(self):
        """Test that setting None clears the span."""
        test_span = Span(name="test", trace_id="123", span_id="456")

        set_current_span(test_span)
        set_current_span(None)

        assert get_current_span() is None


class TestEndToEndContextPropagation:
    """Integration tests for context propagation."""

    def setup_method(self):
        """Clear span before each test."""
        clear_current_span()

    def teardown_method(self):
        """Clear span after each test."""
        clear_current_span()

    def test_parent_child_propagation(self):
        """Test propagating context from parent to child via spore."""
        # Create parent span
        parent_span = Span(
            name="parent",
            trace_id="trace123",
            span_id="parent456"
        )

        # Get context from parent
        parent_context = TraceContext.from_span(parent_span)

        # Inject into spore
        spore = MockSpore()
        parent_context.inject_into_spore(spore)

        # Extract from spore (simulates receiving spore in another agent)
        extracted_context = TraceContext.from_spore(spore)

        # Create child span using extracted context
        child_span = Span(
            name="child",
            trace_id=extracted_context.trace_id,
            span_id="child789",
            parent_span_id=extracted_context.span_id
        )

        # Verify parent-child relationship
        assert child_span.trace_id == parent_span.trace_id
        assert child_span.parent_span_id == parent_span.span_id

    def test_multiple_agents_chain(self):
        """Test context propagation through multiple agents."""
        # Agent 1 creates root span
        agent1_span = Span(name="agent1", trace_id="trace123", span_id="span1")
        context1 = TraceContext.from_span(agent1_span)

        # Agent 1 sends to Agent 2
        spore12 = MockSpore()
        context1.inject_into_spore(spore12)

        # Agent 2 receives and creates span
        context2 = TraceContext.from_spore(spore12)
        agent2_span = Span(
            name="agent2",
            trace_id=context2.trace_id,
            span_id="span2",
            parent_span_id=context2.span_id
        )

        # Agent 2 sends to Agent 3
        context2_out = TraceContext.from_span(agent2_span)
        spore23 = MockSpore()
        context2_out.inject_into_spore(spore23)

        # Agent 3 receives and creates span
        context3 = TraceContext.from_spore(spore23)
        agent3_span = Span(
            name="agent3",
            trace_id=context3.trace_id,
            span_id="span3",
            parent_span_id=context3.span_id
        )

        # Verify the chain
        assert agent2_span.trace_id == agent1_span.trace_id
        assert agent3_span.trace_id == agent1_span.trace_id
        assert agent2_span.parent_span_id == agent1_span.span_id
        assert agent3_span.parent_span_id == agent2_span.span_id
