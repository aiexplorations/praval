"""
Integration tests for automatic instrumentation of Praval components.

Simplified tests that work with actual Praval APIs.
"""

import os

import pytest

# Set up environment for testing
os.environ["PRAVAL_OBSERVABILITY"] = "on"
os.environ["PRAVAL_SAMPLE_RATE"] = "1.0"


@pytest.fixture(autouse=True)
def initialize_observability(monkeypatch, tmp_path):
    """Initialize observability instrumentation for each test in this module.

    This is needed because the main conftest.py resets instrumentation between
    tests for isolation. The observability tests need instrumentation active.
    """
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from praval.config import AppConfig, ObservabilityConfig, OTLPConfig, PravalConfig
    from praval.observability import (
        configure_observability,
        initialize_instrumentation,
        shutdown_observability,
    )
    from praval.observability.config import reset_config
    from praval.observability.storage.sqlite_store import reset_trace_store

    monkeypatch.setenv("PRAVAL_TRACES_PATH", str(tmp_path / "traces.db"))
    reset_config()
    reset_trace_store()

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    configure_observability(
        PravalConfig(
            app=AppConfig(service_name="instrumentation-test"),
            observability=ObservabilityConfig(
                enabled=True,
                otlp=OTLPConfig(traces=True, metrics=False, logs=False),
            ),
        ),
        tracer_provider=provider,
    )
    initialize_instrumentation()
    yield exporter
    shutdown_observability()
    provider.shutdown()


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

    def test_reef_send_creates_span(self, initialize_observability):
        """Verify that reef.send creates trace spans."""
        from praval.core.reef import get_reef

        reef = get_reef()

        # Send a message
        reef.send(
            from_agent="sender", to_agent="receiver", knowledge={"message": "test"}
        )

        # Check for send span
        send_spans = initialize_observability.get_finished_spans()
        assert len(send_spans) == 1
        assert send_spans[0].name == "reef.send"
        assert send_spans[0].kind.name == "PRODUCER"

    def test_reef_broadcast_creates_span(self, initialize_observability):
        """Verify that reef.broadcast creates trace spans."""
        from praval.core.reef import get_reef

        reef = get_reef()

        # Broadcast a message
        reef.broadcast(from_agent="broadcaster", knowledge={"announcement": "test"})

        # Check for broadcast span
        broadcast_spans = [
            span
            for span in initialize_observability.get_finished_spans()
            if span.name == "reef.broadcast"
        ]
        assert len(broadcast_spans) == 1
        assert broadcast_spans[0].kind.name == "PRODUCER"


class TestManualSpanCreation:
    """Test manual span creation still works."""

    def test_manual_span_creation(self, initialize_observability):
        """Verify manual span creation with tracer."""
        from praval.observability import SpanKind
        from praval.observability.tracing import get_tracer

        tracer = get_tracer()

        # Create a span manually
        with tracer.start_as_current_span(
            "manual.test_operation", kind=SpanKind.INTERNAL
        ) as span:
            span.set_attribute("test_attr", "value")
            span.add_event("test_event")

        # Verify it was stored
        spans = initialize_observability.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "manual.test_operation"
        assert spans[0].kind.name == "INTERNAL"
        assert spans[0].attributes["test_attr"] == "value"


class TestErrorRecording:
    """Test error recording in spans."""

    def test_exception_recorded_in_span(self, initialize_observability):
        """Verify exceptions are recorded in spans."""
        from opentelemetry.trace import StatusCode

        from praval.observability import SpanKind
        from praval.observability.tracing import get_tracer

        tracer = get_tracer()

        # Create a span with an exception
        try:
            with tracer.start_as_current_span(
                "error.test_operation", kind=SpanKind.INTERNAL
            ):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify error was recorded
        error_spans = initialize_observability.get_finished_spans()
        assert len(error_spans) == 1
        assert error_spans[0].status.status_code is StatusCode.ERROR
        assert any(event.name == "exception" for event in error_spans[0].events)


class TestTraceContextPropagation:
    """Test trace context propagation."""

    def test_parent_child_spans(self, initialize_observability):
        """Verify parent-child span relationships."""
        from praval.observability import SpanKind
        from praval.observability.tracing import get_tracer

        tracer = get_tracer()

        # Create parent span
        with tracer.start_as_current_span(
            "parent.operation", kind=SpanKind.INTERNAL
        ) as parent_span:
            parent_trace_id = parent_span.get_span_context().trace_id
            parent_span_id = parent_span.get_span_context().span_id

            # Create child span
            with tracer.start_as_current_span(
                "child.operation", kind=SpanKind.INTERNAL
            ) as child_span:
                # Child should have same trace_id
                assert child_span.get_span_context().trace_id == parent_trace_id
                # Child's parent should be parent span
                assert child_span.parent.span_id == parent_span_id

        # Verify both spans stored
        spans = initialize_observability.get_finished_spans()
        assert len(spans) == 2

        # Find parent and child
        parent = next(span for span in spans if span.name == "parent.operation")
        child = next(span for span in spans if span.name == "child.operation")

        assert parent.context.trace_id == child.context.trace_id
        assert child.parent.span_id == parent.context.span_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
