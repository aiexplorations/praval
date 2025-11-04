"""
Integration tests for automatic instrumentation of Praval components.

Simplified tests that work with actual Praval APIs.
"""

import os
import pytest
import time

# Set up environment for testing
os.environ["PRAVAL_OBSERVABILITY"] = "on"
os.environ["PRAVAL_SAMPLE_RATE"] = "1.0"


class TestBasicInstrumentation:
    """Test that basic instrumentation is working."""

    def test_observability_is_enabled(self):
        """Verify observability is enabled for tests."""
        from praval.observability import get_config, is_instrumented

        config = get_config()
        assert config.is_enabled()
        assert is_instrumented()

    def test_trace_store_is_available(self):
        """Verify trace store is accessible."""
        from praval.observability import get_trace_store

        store = get_trace_store()
        assert store is not None

        # Can query for traces
        recent = store.get_recent_traces(limit=10)
        assert isinstance(recent, list)


class TestReefInstrumentation:
    """Test automatic instrumentation of Reef communication."""

    def test_reef_send_creates_span(self):
        """Verify that reef.send creates trace spans."""
        from praval.core.reef import get_reef
        from praval.observability import get_trace_store

        store = get_trace_store()
        store.cleanup_old_traces(days=0)

        reef = get_reef()

        # Send a message
        reef.send(
            from_agent="sender",
            to_agent="receiver",
            knowledge={"message": "test"}
        )

        time.sleep(0.3)

        # Check for send span
        send_spans = store.find_spans(agent_name="reef.send")
        assert len(send_spans) > 0

        span = send_spans[0]
        assert "reef.send" in span["name"]
        assert span["kind"] == "PRODUCER"

    def test_reef_broadcast_creates_span(self):
        """Verify that reef.broadcast creates trace spans."""
        from praval.core.reef import get_reef
        from praval.observability import get_trace_store

        store = get_trace_store()
        store.cleanup_old_traces(days=0)

        reef = get_reef()

        # Broadcast a message
        reef.broadcast(
            from_agent="broadcaster",
            knowledge={"announcement": "test"}
        )

        time.sleep(0.3)

        # Check for broadcast span
        broadcast_spans = store.find_spans(agent_name="reef.broadcast")
        assert len(broadcast_spans) > 0

        span = broadcast_spans[0]
        assert "reef.broadcast" in span["name"]
        assert span["kind"] == "PRODUCER"


class TestManualSpanCreation:
    """Test manual span creation still works."""

    def test_manual_span_creation(self):
        """Verify manual span creation with tracer."""
        from praval.observability import get_tracer, get_trace_store, SpanKind

        store = get_trace_store()
        store.cleanup_old_traces(days=0)

        tracer = get_tracer()

        # Create a span manually
        with tracer.start_as_current_span(
            "manual.test_operation",
            kind=SpanKind.INTERNAL
        ) as span:
            span.set_attribute("test_attr", "value")
            span.add_event("test_event")

        time.sleep(0.2)

        # Verify it was stored
        spans = store.find_spans(agent_name="manual.test")
        assert len(spans) > 0

        span_dict = spans[0]
        assert "manual.test_operation" in span_dict["name"]
        assert span_dict["kind"] == "INTERNAL"
        assert "test_attr" in span_dict["attributes"]


class TestErrorRecording:
    """Test error recording in spans."""

    def test_exception_recorded_in_span(self):
        """Verify exceptions are recorded in spans."""
        from praval.observability import get_tracer, get_trace_store, SpanKind

        store = get_trace_store()
        store.cleanup_old_traces(days=0)

        tracer = get_tracer()

        # Create a span with an exception
        try:
            with tracer.start_as_current_span(
                "error.test_operation",
                kind=SpanKind.INTERNAL
            ) as span:
                raise ValueError("Test error")
        except ValueError:
            pass

        time.sleep(0.2)

        # Verify error was recorded
        error_spans = store.find_spans(status="error")
        assert len(error_spans) > 0

        span = error_spans[0]
        assert span["status"] == "error"
        assert len(span["events"]) > 0


class TestTraceContextPropagation:
    """Test trace context propagation."""

    def test_parent_child_spans(self):
        """Verify parent-child span relationships."""
        from praval.observability import get_tracer, get_trace_store, SpanKind

        store = get_trace_store()
        store.cleanup_old_traces(days=0)

        tracer = get_tracer()

        # Create parent span
        with tracer.start_as_current_span(
            "parent.operation",
            kind=SpanKind.INTERNAL
        ) as parent_span:
            parent_trace_id = parent_span.trace_id
            parent_span_id = parent_span.span_id

            # Create child span
            with tracer.start_as_current_span(
                "child.operation",
                kind=SpanKind.INTERNAL
            ) as child_span:
                # Child should have same trace_id
                assert child_span.trace_id == parent_trace_id
                # Child's parent should be parent span
                assert child_span.parent_span_id == parent_span_id

        time.sleep(0.2)

        # Verify both spans stored
        spans = store.find_spans(limit=10)
        assert len(spans) >= 2

        # Find parent and child
        parent = next(s for s in spans if "parent.operation" in s["name"])
        child = next(s for s in spans if "child.operation" in s["name"])

        assert parent["trace_id"] == child["trace_id"]
        assert child["parent_span_id"] == parent["span_id"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
