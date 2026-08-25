#!/usr/bin/env python3
"""Verify W3C context continuity through an in-memory Reef delivery."""

from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from praval.core.reef import Reef, Spore
from praval.observability import (
    configure_observability,
    get_tracer,
    shutdown_observability,
)


def main() -> None:
    """Send one Spore and assert that its consumer inherits the producer."""
    exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider(shutdown_on_exit=False)
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    meter_provider = MeterProvider(shutdown_on_exit=False)
    logger_provider = LoggerProvider(shutdown_on_exit=False)
    configure_observability(
        service_name="reef-context-example",
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        logger_provider=logger_provider,
    )

    reef = Reef()

    def consume(spore: Spore) -> None:
        assert "traceparent" in spore.trace_context
        with get_tracer().start_as_current_span("example.consumer"):
            pass

    reef.subscribe("consumer", consume)
    try:
        with get_tracer().start_as_current_span("example.producer"):
            reef.send("producer", "consumer", {"message": "hello"})
        if not reef.get_channel("main").wait_for_completion(timeout=2):
            raise RuntimeError("Reef delivery did not complete")
    finally:
        reef.shutdown(wait=False)
        shutdown_observability(1_000)

    spans = {span.name: span for span in exporter.get_finished_spans()}
    producer = spans["example.producer"]
    consumer = spans["example.consumer"]
    assert consumer.context.trace_id == producer.context.trace_id
    spans_by_id = {span.context.span_id: span for span in spans.values()}
    ancestor_id = consumer.parent.span_id if consumer.parent is not None else None
    ancestor_ids = set()
    while ancestor_id is not None and ancestor_id not in ancestor_ids:
        ancestor_ids.add(ancestor_id)
        ancestor = spans_by_id.get(ancestor_id)
        ancestor_id = (
            ancestor.parent.span_id
            if ancestor is not None and ancestor.parent is not None
            else None
        )
    assert producer.context.span_id in ancestor_ids
    print(f"trace_id={producer.context.trace_id:032x} parentage=ok")

    logger_provider.shutdown()
    meter_provider.shutdown()
    tracer_provider.shutdown()


if __name__ == "__main__":
    main()
