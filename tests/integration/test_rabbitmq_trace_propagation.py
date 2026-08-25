"""Black-box W3C propagation through a real RabbitMQ broker."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from praval.config import AppConfig, ObservabilityConfig, OTLPConfig, PravalConfig
from praval.core.reef import Reef, Spore
from praval.core.reef_backend import RabbitMQBackend
from praval.observability import configure_observability, shutdown_observability
from praval.observability.tracing import get_tracer

pytest.importorskip("aio_pika")
sdk_export = pytest.importorskip("opentelemetry.sdk.trace.export")
in_memory_export = pytest.importorskip(
    "opentelemetry.sdk.trace.export.in_memory_span_exporter"
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rabbitmq_preserves_producer_delivery_consumer_parentage() -> None:
    """A broker round trip retains one trace and its messaging span chain."""
    exchange_name = f"praval.test.trace.{uuid.uuid4().hex}"
    config = {
        "url": "amqp://guest:guest@localhost:5672/",
        "exchange_name": exchange_name,
        "verify_tls": False,
    }
    sender = Reef(backend=RabbitMQBackend())
    receiver = RabbitMQBackend()
    delivered = asyncio.Event()
    received: list[Spore] = []

    shutdown_observability()
    handle = configure_observability(
        PravalConfig(
            app=AppConfig(service_name="rabbitmq-trace-propagation-test"),
            observability=ObservabilityConfig(
                enabled=True,
                sampling="always_on",
                otlp=OTLPConfig(traces=True, metrics=False, logs=False),
            ),
        )
    )
    exporter = in_memory_export.InMemorySpanExporter()
    handle.tracer_provider.add_span_processor(sdk_export.SimpleSpanProcessor(exporter))
    tracer = get_tracer("praval.tests.rabbitmq-black-box")

    async def consume(spore: Spore) -> None:
        received.append(spore)
        delivered.set()

    try:
        try:
            await sender.initialize_backend(config)
            await receiver.initialize(config)
        except RuntimeError as exc:
            pytest.skip(f"RabbitMQ unavailable: {exc}")
        await receiver.subscribe("agent.consumer", consume)

        with tracer.start_as_current_span("rabbitmq-workflow-root"):
            spore_id = sender.send(
                "producer", "consumer", {"message": "through-the-broker"}
            )

        await asyncio.wait_for(delivered.wait(), timeout=5.0)
        await asyncio.sleep(0)
    finally:
        await sender.close_backend()
        await receiver.shutdown()
        sender.shutdown(wait=False)
        shutdown_observability()

    assert [spore.id for spore in received] == [spore_id]
    spans = {span.name: span for span in exporter.get_finished_spans()}
    root = spans["rabbitmq-workflow-root"]
    producer = spans["praval.reef.producer"]
    delivery = spans["praval.reef.delivery"]
    consumer = spans["praval.reef.consumer"]
    assert producer.parent.span_id == root.context.span_id
    assert delivery.parent.span_id == producer.context.span_id
    assert consumer.parent.span_id == delivery.context.span_id
    assert consumer.context.trace_id == root.context.trace_id
