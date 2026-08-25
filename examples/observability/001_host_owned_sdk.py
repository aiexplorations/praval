#!/usr/bin/env python3
"""Attach Praval to application-owned OpenTelemetry providers."""

from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from praval.observability import (
    configure_observability,
    get_tracer,
    shutdown_observability,
)


def main() -> None:
    """Prove that Praval uses but does not own host providers."""
    exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider(shutdown_on_exit=False)
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    meter_provider = MeterProvider(shutdown_on_exit=False)
    logger_provider = LoggerProvider(shutdown_on_exit=False)

    handle = configure_observability(
        service_name="host-owned-example",
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        logger_provider=logger_provider,
    )
    with get_tracer().start_as_current_span("host-owned-operation"):
        pass
    shutdown_observability(1_000)

    names = [span.name for span in exporter.get_finished_spans()]
    print(f"owned_signals={sorted(handle.owned_signals)} spans={names}")

    # The application owns these providers and closes them itself.
    logger_provider.shutdown()
    meter_provider.shutdown()
    tracer_provider.shutdown()


if __name__ == "__main__":
    main()
