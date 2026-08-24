"""W3C trace-context propagation contracts for Spores and Reef delivery."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import msgpack
import pytest
from opentelemetry import baggage
from opentelemetry.trace import (
    NonRecordingSpan,
    SpanContext,
    TraceFlags,
    TraceState,
    get_current_span,
    set_span_in_context,
)

from praval.config import AppConfig, ObservabilityConfig, OTLPConfig, PravalConfig
from praval.core.reef import Spore, SporeType, SporeValidationError
from praval.core.reef_backend import RabbitMQBackend
from praval.core.secure_reef import KeyRegistry, SecureReef
from praval.core.secure_spore import SecureSpore, SecureSporeFactory, SporeKeyManager
from praval.models.observation import ExecutionObservation, ObservationKind
from praval.observability import configure_observability, shutdown_observability
from praval.observability.tracing import get_tracer
from praval.observability.tracing.context import (
    extract_trace_context,
    inject_trace_context,
)
from praval.runtime_observation import ObservationScope, use_observation_recorder

sdk_trace = pytest.importorskip("opentelemetry.sdk.trace")
sdk_export = pytest.importorskip("opentelemetry.sdk.trace.export")
in_memory_export = pytest.importorskip(
    "opentelemetry.sdk.trace.export.in_memory_span_exporter"
)


class _SubscriptionTransport:
    """Minimal transport that exposes the real RabbitMQ backend callback."""

    def __init__(self) -> None:
        self.callback: Any = None

    async def initialize(self, config: dict[str, Any]) -> None:
        return None

    async def subscribe(self, topic: str, callback: Any) -> tuple[str, str]:
        self.callback = callback
        return ("topic", topic)

    async def unsubscribe_handler(self, handle: Any) -> None:
        return None

    async def close(self) -> None:
        return None


class _ObservationRecorder:
    """Collect completed execution observations for handoff assertions."""

    def __init__(self) -> None:
        self.observations: list[ExecutionObservation] = []

    def record(self, observation: ExecutionObservation) -> None:
        self.observations.append(observation)


def test_spore_trace_context_round_trips_through_json() -> None:
    """The versioned carrier is a top-level JSON Spore field."""
    carrier = {
        "traceparent": "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
        "tracestate": "vendor=value",
        "baggage": "tenant=example",
    }
    spore = Spore(
        id="trace-spore",
        spore_type=SporeType.KNOWLEDGE,
        from_agent="producer",
        to_agent="consumer",
        knowledge={"message": "hello"},
        created_at=datetime.now(),
        trace_context=carrier,
    )

    restored = Spore.from_json(spore.to_json())

    assert restored.trace_context == carrier
    assert restored.trace_context is not carrier


def test_spore_reference_helpers_preserve_trace_context() -> None:
    """Immutable-style Spore helpers retain a defensive carrier copy."""
    spore = Spore(
        id="trace-spore",
        spore_type=SporeType.KNOWLEDGE,
        from_agent="producer",
        to_agent="consumer",
        knowledge={"message": "hello"},
        created_at=datetime.now(),
        trace_context={"traceparent": "parent"},
    )

    with_reference = spore.add_knowledge_reference("memory://fact")

    assert with_reference.trace_context == spore.trace_context
    assert with_reference.trace_context is not spore.trace_context


def test_public_send_preserves_an_explicit_carrier_when_no_span_is_active() -> None:
    """Framework adapters can forward an already-extracted carrier explicitly."""
    from praval.core.reef import Reef

    carrier = {
        "traceparent": "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
        "tracestate": "vendor=value",
    }
    reef = Reef()
    try:
        spore_id = reef.send(
            "producer",
            "consumer",
            {"message": "forwarded"},
            trace_context=carrier,
        )
        sent = next(
            spore for spore in reef.get_channel("main").spores if spore.id == spore_id
        )
    finally:
        reef.shutdown(wait=False)

    assert sent.trace_context == carrier


@pytest.mark.parametrize(
    "carrier",
    [{1: "value"}, {"traceparent": 1}],
)
def test_spore_rejects_non_string_trace_carrier_entries(
    carrier: dict[Any, Any],
) -> None:
    """Only text carrier keys and values enter JSON or AMQP boundaries."""
    with pytest.raises(SporeValidationError, match="trace_context"):
        Spore(
            id="invalid-carrier",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="producer",
            to_agent="consumer",
            knowledge={},
            created_at=datetime.now(),
            trace_context=carrier,
        )


def test_official_propagator_preserves_sampling_tracestate_and_baggage() -> None:
    """Injection and extraction use the configured OpenTelemetry propagator."""
    source = SpanContext(
        trace_id=int("1" * 32, 16),
        span_id=int("2" * 16, 16),
        is_remote=False,
        trace_flags=TraceFlags.SAMPLED,
        trace_state=TraceState([("vendor", "value")]),
    )
    source_context = set_span_in_context(NonRecordingSpan(source))
    source_context = baggage.set_baggage("tenant", "example", context=source_context)

    carrier = inject_trace_context(source_context)
    extracted = extract_trace_context(carrier)
    remote = get_current_span(extracted).get_span_context()

    assert carrier == {
        "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
        "tracestate": "vendor=value",
        "baggage": "tenant=example",
    }
    assert remote.trace_id == source.trace_id
    assert remote.span_id == source.span_id
    assert remote.trace_flags.sampled
    assert remote.trace_state.get("vendor") == "value"
    assert baggage.get_baggage("tenant", context=extracted) == "example"


def test_trace_context_round_trips_through_amqp_headers_and_body() -> None:
    """AMQP transports preserve interoperable headers and the Spore envelope."""
    carrier = {
        "traceparent": "00-0123456789abcdef0123456789abcdef-0123456789abcdef-00",
        "tracestate": "vendor=value",
        "baggage": "tenant=example",
    }
    spore = Spore(
        id="amqp-trace-spore",
        spore_type=SporeType.KNOWLEDGE,
        from_agent="producer",
        to_agent="consumer",
        knowledge={"message": "hello"},
        created_at=datetime.now(),
        trace_context=carrier,
    )

    message = spore.to_amqp_message()
    body = message.body.decode("utf-8")
    restored = Spore.from_amqp_message(message)

    assert message.headers["traceparent"] == carrier["traceparent"]
    assert message.headers["tracestate"] == carrier["tracestate"]
    assert message.headers["baggage"] == carrier["baggage"]
    assert '"trace_context"' in body
    assert restored.trace_context == carrier


def test_amqp_rejects_malformed_body_carrier_at_the_spore_boundary() -> None:
    """Bad envelope carriers raise the stable validation error, not TypeError."""
    aio_pika = pytest.importorskip("aio_pika")
    body = {
        "_praval_spore_envelope": "2.0",
        "knowledge": {"message": "hello"},
        "trace_context": ["not", "a", "mapping"],
    }
    message = aio_pika.Message(
        body=__import__("json").dumps(body).encode("utf-8"),
        headers={
            "spore_id": "malformed-carrier",
            "spore_type": SporeType.KNOWLEDGE.value,
            "from_agent": "producer",
            "to_agent": "consumer",
            "traceparent": ("00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"),
        },
    )

    with pytest.raises(SporeValidationError, match="trace_context"):
        Spore.from_amqp_message(message)


def test_in_memory_reef_consumer_inherits_producer_context() -> None:
    """A local consumer span is a child of the sending producer span."""
    from praval.core.reef import Reef

    provider = sdk_trace.TracerProvider(shutdown_on_exit=False)
    exporter = in_memory_export.InMemorySpanExporter()
    provider.add_span_processor(sdk_export.SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("praval.tests.spore-propagation")
    reef = Reef()

    def consume(spore: Spore) -> None:
        assert "traceparent" in spore.trace_context
        with tracer.start_as_current_span("consumer"):
            pass

    reef.subscribe("consumer", consume)
    try:
        with tracer.start_as_current_span("producer"):
            reef.send("producer", "consumer", {"message": "hello"})
        assert reef.get_channel("main").wait_for_completion(timeout=2.0)
    finally:
        reef.shutdown(wait=False)
        provider.shutdown()

    spans = {span.name: span for span in exporter.get_finished_spans()}
    assert spans["consumer"].context.trace_id == spans["producer"].context.trace_id
    assert spans["consumer"].parent.span_id == spans["producer"].context.span_id


@pytest.mark.asyncio
async def test_concurrent_async_messages_do_not_leak_trace_context() -> None:
    """Overlapping async handlers retain only their own remote parent."""
    from praval.core.reef import Reef

    provider = sdk_trace.TracerProvider(shutdown_on_exit=False)
    exporter = in_memory_export.InMemorySpanExporter()
    provider.add_span_processor(sdk_export.SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("praval.tests.spore-concurrency")
    reef = Reef()
    seen: dict[str, tuple[int, int]] = {}

    async def consume(spore: Spore) -> None:
        token = str(spore.knowledge["token"])
        with tracer.start_as_current_span(f"consumer-{token}") as span:
            before = span.get_span_context().trace_id
            await asyncio.sleep(0.01)
            after = get_current_span().get_span_context().trace_id
            seen[token] = (before, after)

    async def produce(token: str) -> None:
        with tracer.start_as_current_span(f"producer-{token}"):
            reef.send("producer", "consumer", {"token": token})
            await asyncio.sleep(0)

    reef.subscribe("consumer", consume)
    try:
        await asyncio.gather(produce("a"), produce("b"))
        channel = reef.get_channel("main")
        assert channel is not None
        assert await asyncio.to_thread(channel.wait_for_completion, 2.0)
    finally:
        reef.shutdown(wait=False)
        provider.shutdown()

    spans = {span.name: span for span in exporter.get_finished_spans()}
    for token in ("a", "b"):
        producer = spans[f"producer-{token}"]
        consumer = spans[f"consumer-{token}"]
        assert consumer.context.trace_id == producer.context.trace_id
        assert consumer.parent.span_id == producer.context.span_id
        assert seen[token] == (producer.context.trace_id, producer.context.trace_id)
    assert spans["producer-a"].context.trace_id != spans["producer-b"].context.trace_id


def test_derived_response_preserves_request_context_outside_active_scope() -> None:
    """Response helpers retain the request trace after an execution handoff."""
    from praval.core.reef import Reef

    provider = sdk_trace.TracerProvider(shutdown_on_exit=False)
    tracer = provider.get_tracer("praval.tests.spore-response")
    reef = Reef()
    try:
        with tracer.start_as_current_span("request-producer"):
            reef.request("client", "service", {"question": "ready"})
        request_spore = reef.get_channel("main").spores[-1]

        reef.reply_to_request(request_spore, {"answer": "yes"})
        response_spore = reef.get_channel("main").spores[-1]
    finally:
        reef.shutdown(wait=False)
        provider.shutdown()

    assert response_spore.reply_to == request_spore.id
    assert response_spore.trace_context == request_spore.trace_context


@pytest.mark.asyncio
async def test_rabbitmq_backend_consumer_uses_extracted_remote_parent() -> None:
    """The distributed backend activates the carrier around its callback."""
    provider = sdk_trace.TracerProvider(shutdown_on_exit=False)
    exporter = in_memory_export.InMemorySpanExporter()
    provider.add_span_processor(sdk_export.SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("praval.tests.rabbitmq-propagation")
    transport = _SubscriptionTransport()
    backend = RabbitMQBackend(transport=transport)
    await backend.initialize({})

    async def consume(spore: Spore) -> None:
        with tracer.start_as_current_span("rabbit-consumer"):
            await asyncio.sleep(0)

    try:
        await backend.subscribe("agent.consumer", consume)
        with tracer.start_as_current_span("rabbit-producer"):
            spore = Spore(
                id="rabbit-spore",
                spore_type=SporeType.KNOWLEDGE,
                from_agent="producer",
                to_agent="consumer",
                knowledge={"message": "hello"},
                created_at=datetime.now(),
                trace_context=inject_trace_context(),
            )
        await transport.callback(spore)
    finally:
        await backend.shutdown()
        provider.shutdown()

    spans = {span.name: span for span in exporter.get_finished_spans()}
    assert (
        spans["rabbit-consumer"].context.trace_id
        == spans["rabbit-producer"].context.trace_id
    )
    assert (
        spans["rabbit-consumer"].parent.span_id
        == spans["rabbit-producer"].context.span_id
    )


@pytest.mark.asyncio
async def test_rabbitmq_precise_subscription_uses_extracted_remote_parent() -> None:
    """Request waiters receive the same propagation as normal subscriptions."""
    provider = sdk_trace.TracerProvider(shutdown_on_exit=False)
    exporter = in_memory_export.InMemorySpanExporter()
    provider.add_span_processor(sdk_export.SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("praval.tests.rabbitmq-precise-propagation")
    transport = _SubscriptionTransport()
    backend = RabbitMQBackend(transport=transport)
    await backend.initialize({})

    async def consume(spore: Spore) -> None:
        with tracer.start_as_current_span("rabbit-precise-consumer"):
            await asyncio.sleep(0)

    try:
        await backend.subscribe_handler("agent.consumer", consume)
        with tracer.start_as_current_span("rabbit-precise-producer"):
            spore = Spore(
                id="rabbit-precise-spore",
                spore_type=SporeType.KNOWLEDGE,
                from_agent="producer",
                to_agent="consumer",
                knowledge={"message": "hello"},
                created_at=datetime.now(),
                trace_context=inject_trace_context(),
            )
        await transport.callback(spore)
    finally:
        await backend.shutdown()
        provider.shutdown()

    spans = {span.name: span for span in exporter.get_finished_spans()}
    consumer = spans["rabbit-precise-consumer"]
    producer = spans["rabbit-precise-producer"]
    assert consumer.context.trace_id == producer.context.trace_id
    assert consumer.parent.span_id == producer.context.span_id


@pytest.mark.asyncio
async def test_rabbitmq_callback_detaches_context_when_handler_fails() -> None:
    """A failed distributed handler cannot leak its remote parent."""
    transport = _SubscriptionTransport()
    backend = RabbitMQBackend(transport=transport)
    await backend.initialize({})
    source = SpanContext(
        trace_id=int("3" * 32, 16),
        span_id=int("4" * 16, 16),
        is_remote=False,
        trace_flags=TraceFlags.SAMPLED,
        trace_state=TraceState(),
    )
    carrier = inject_trace_context(set_span_in_context(NonRecordingSpan(source)))
    spore = Spore(
        id="failed-handler-spore",
        spore_type=SporeType.KNOWLEDGE,
        from_agent="producer",
        to_agent="consumer",
        knowledge={},
        created_at=datetime.now(),
        trace_context=carrier,
    )

    async def fail(received: Spore) -> None:
        assert get_current_span().get_span_context().trace_id == source.trace_id
        raise LookupError("handler failed")

    try:
        await backend.subscribe("agent.consumer", fail)
        with pytest.raises(LookupError, match="handler failed"):
            await transport.callback(spore)
        assert not get_current_span().get_span_context().is_valid
    finally:
        await backend.shutdown()


@pytest.mark.asyncio
async def test_rabbitmq_consumer_preserves_unsampled_parent_decision() -> None:
    """A remote unsampled W3C parent remains unsampled in the consumer."""
    transport = _SubscriptionTransport()
    backend = RabbitMQBackend(transport=transport)
    await backend.initialize({})
    source = SpanContext(
        trace_id=int("5" * 32, 16),
        span_id=int("6" * 16, 16),
        is_remote=False,
        trace_flags=TraceFlags.DEFAULT,
        trace_state=TraceState(),
    )
    carrier = inject_trace_context(set_span_in_context(NonRecordingSpan(source)))
    seen: list[SpanContext] = []

    async def consume(spore: Spore) -> None:
        seen.append(get_current_span().get_span_context())

    try:
        await backend.subscribe("agent.consumer", consume)
        await transport.callback(
            Spore(
                id="unsampled-spore",
                spore_type=SporeType.KNOWLEDGE,
                from_agent="producer",
                to_agent="consumer",
                knowledge={},
                created_at=datetime.now(),
                trace_context=carrier,
            )
        )
    finally:
        await backend.shutdown()

    assert seen[0].trace_id == source.trace_id
    assert not seen[0].trace_flags.sampled


def test_secure_spore_authenticates_trace_carrier_and_rejects_tampering() -> None:
    """An encrypted Spore signature covers its canonical W3C carrier."""
    sender = SporeKeyManager("sender")
    recipient = SporeKeyManager("recipient")
    carrier = {
        "traceparent": "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
        "baggage": "tenant=example",
    }
    secure = SecureSporeFactory(sender).create_secure_spore(
        to_agent="recipient",
        knowledge={"message": "secret"},
        recipient_public_keys=recipient.get_public_keys(),
        trace_context=carrier,
    )
    restored = SecureSpore.from_bytes(secure.to_bytes())

    assert restored.trace_context == carrier
    assert recipient.decrypt_and_verify(
        restored.encrypted_knowledge,
        restored.nonce,
        restored.knowledge_signature,
        restored.sender_public_key,
        bytes(sender.verify_key),
        authenticated_data=restored.authenticated_trace_context(),
    ) == {"message": "secret"}

    restored.trace_context["baggage"] = "tenant=attacker"
    with pytest.raises(ValueError, match="Cryptographic verification failed"):
        recipient.decrypt_and_verify(
            restored.encrypted_knowledge,
            restored.nonce,
            restored.knowledge_signature,
            restored.sender_public_key,
            bytes(sender.verify_key),
            authenticated_data=restored.authenticated_trace_context(),
        )


def test_secure_spore_accepts_legacy_signature_without_carrier_material() -> None:
    """Pre-O4 targeted messages still verify when the carrier field is absent."""
    sender = SporeKeyManager("sender")
    recipient = SporeKeyManager("recipient")
    encrypted, nonce, signature = sender.encrypt_and_sign(
        {"message": "legacy"}, bytes(recipient.public_key)
    )
    legacy_payload = {
        "id": "legacy-secure-spore",
        "spore_type": SporeType.KNOWLEDGE.value,
        "from_agent": "sender",
        "to_agent": "recipient",
        "created_at": datetime.now().timestamp(),
        "expires_at": None,
        "priority": 5,
        "encrypted_knowledge": encrypted,
        "knowledge_signature": signature,
        "sender_public_key": bytes(sender.public_key),
        "nonce": nonce,
        "encrypted_references": None,
        "version": "1.0",
    }

    restored = SecureSpore.from_bytes(msgpack.packb(legacy_payload, use_bin_type=True))
    forwarded = SecureSpore.from_bytes(restored.to_bytes())

    assert restored.trace_context == {}
    assert restored.authenticated_trace_context() == b""
    assert forwarded.authenticated_trace_context() == b""
    assert recipient.decrypt_and_verify(
        forwarded.encrypted_knowledge,
        forwarded.nonce,
        forwarded.knowledge_signature,
        forwarded.sender_public_key,
        bytes(sender.verify_key),
        authenticated_data=forwarded.authenticated_trace_context(),
    ) == {"message": "legacy"}


@pytest.mark.asyncio
async def test_secure_reef_verifies_authenticated_trace_carrier() -> None:
    """SecureReef supplies carrier bytes to its verification boundary."""
    sender = SporeKeyManager("sender")
    recipient = SporeKeyManager("recipient")
    registry = KeyRegistry()
    await registry.register_agent("sender", sender.get_public_keys())
    secure = SecureSporeFactory(sender).create_secure_spore(
        to_agent="recipient",
        knowledge={"message": "secret"},
        recipient_public_keys=recipient.get_public_keys(),
        trace_context={"traceparent": "parent"},
    )
    reef = SecureReef.__new__(SecureReef)
    reef.key_manager = recipient
    reef.key_registry = registry

    assert await reef._decrypt_spore(secure) == {"message": "secret"}


@pytest.mark.asyncio
async def test_secure_reef_handler_inherits_authenticated_parent() -> None:
    """The verified secure carrier reaches and parents the application handler."""
    provider = sdk_trace.TracerProvider(shutdown_on_exit=False)
    exporter = in_memory_export.InMemorySpanExporter()
    provider.add_span_processor(sdk_export.SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("praval.tests.secure-reef-propagation")
    sender = SporeKeyManager("sender")
    recipient = SporeKeyManager("recipient")
    registry = KeyRegistry()
    await registry.register_agent("sender", sender.get_public_keys())

    with tracer.start_as_current_span("secure-producer"):
        secure = SecureSporeFactory(sender).create_secure_spore(
            to_agent="recipient",
            knowledge={"message": "secret"},
            recipient_public_keys=recipient.get_public_keys(),
        )

    reef = SecureReef.__new__(SecureReef)
    reef.agent_name = "recipient"
    reef.key_manager = recipient
    reef.key_registry = registry
    reef.stats = {"spores_received": 0, "encryption_errors": 0}

    def consume(spore: Spore) -> None:
        assert spore.trace_context == secure.trace_context
        with tracer.start_as_current_span("secure-consumer"):
            pass

    reef.message_handlers = {SporeType.KNOWLEDGE.value: [consume]}
    try:
        await reef._handle_incoming_message(secure.to_bytes())
    finally:
        provider.shutdown()

    spans = {span.name: span for span in exporter.get_finished_spans()}
    assert (
        spans["secure-consumer"].context.trace_id
        == spans["secure-producer"].context.trace_id
    )
    assert (
        spans["secure-consumer"].parent.span_id
        == spans["secure-producer"].context.span_id
    )
    assert reef.stats["encryption_errors"] == 0


@pytest.mark.asyncio
async def test_secure_reef_records_delivery_and_consumer_spans() -> None:
    """Verified secure delivery uses the same Reef span boundaries."""
    shutdown_observability()
    handle = configure_observability(
        PravalConfig(
            app=AppConfig(service_name="secure-reef-propagation-test"),
            observability=ObservabilityConfig(
                enabled=True,
                sampling="always_on",
                otlp=OTLPConfig(traces=True, metrics=False, logs=False),
            ),
        )
    )
    exporter = in_memory_export.InMemorySpanExporter()
    handle.tracer_provider.add_span_processor(sdk_export.SimpleSpanProcessor(exporter))
    tracer = get_tracer("praval.tests.secure-reef-boundaries")
    sender = SporeKeyManager("sender")
    recipient = SporeKeyManager("recipient")
    registry = KeyRegistry()
    await registry.register_agent("sender", sender.get_public_keys())
    with tracer.start_as_current_span("secure-workflow-root"):
        secure = SecureSporeFactory(sender).create_secure_spore(
            to_agent="recipient",
            knowledge={"message": "secret"},
            recipient_public_keys=recipient.get_public_keys(),
        )

    reef = SecureReef.__new__(SecureReef)
    reef.agent_name = "recipient"
    reef.key_manager = recipient
    reef.key_registry = registry
    reef.stats = {"spores_received": 0, "encryption_errors": 0}
    reef.message_handlers = {SporeType.KNOWLEDGE.value: [lambda spore: None]}
    try:
        await reef._handle_incoming_message(secure.to_bytes())
    finally:
        shutdown_observability()

    spans = {span.name: span for span in exporter.get_finished_spans()}
    delivery = spans["praval.reef.delivery"]
    consumer = spans["praval.reef.consumer"]
    root = spans["secure-workflow-root"]
    assert delivery.parent.span_id == root.context.span_id
    assert consumer.parent.span_id == delivery.context.span_id


def test_in_memory_reef_records_producer_delivery_and_consumer_spans() -> None:
    """Stable Reef boundaries form one distributed parentage chain."""
    from praval.core.reef import Reef

    shutdown_observability()
    handle = configure_observability(
        PravalConfig(
            app=AppConfig(service_name="reef-propagation-test"),
            observability=ObservabilityConfig(
                enabled=True,
                sampling="always_on",
                otlp=OTLPConfig(traces=True, metrics=False, logs=False),
            ),
        )
    )
    exporter = in_memory_export.InMemorySpanExporter()
    handle.tracer_provider.add_span_processor(sdk_export.SimpleSpanProcessor(exporter))
    tracer = get_tracer("praval.tests.reef-boundaries")
    reef = Reef()
    reef.subscribe("consumer", lambda spore: None)
    try:
        with tracer.start_as_current_span("workflow-root"):
            reef.send("producer", "consumer", {"message": "hello"})
        channel = reef.get_channel("main")
        assert channel is not None
        assert channel.wait_for_completion(timeout=2.0)
    finally:
        reef.shutdown(wait=False)
        shutdown_observability()

    spans = {span.name: span for span in exporter.get_finished_spans()}
    assert (
        spans["praval.reef.producer"].parent.span_id
        == spans["workflow-root"].context.span_id
    )
    assert (
        spans["praval.reef.delivery"].parent.span_id
        == spans["praval.reef.producer"].context.span_id
    )
    assert (
        spans["praval.reef.consumer"].parent.span_id
        == spans["praval.reef.delivery"].context.span_id
    )
    assert (
        spans["praval.reef.consumer"].context.trace_id
        == spans["workflow-root"].context.trace_id
    )


def test_reef_handoff_is_aggregated_into_the_active_agent_observation() -> None:
    """A send adds one bounded handoff fact, not another observation."""
    from praval.core.reef import Reef

    recorder = _ObservationRecorder()
    reef = Reef()
    try:
        with use_observation_recorder(recorder):
            with ObservationScope(kind=ObservationKind.AGENT, agent_name="producer"):
                spore_id = reef.send(
                    "producer", "consumer", {"message": "hello"}, channel="main"
                )
    finally:
        reef.shutdown(wait=False)

    assert len(recorder.observations) == 1
    observation = recorder.observations[0]
    assert len(observation.handoffs) == 1
    handoff = observation.handoffs[0]
    assert handoff.handoff_id == spore_id
    assert handoff.source_agent_id == "producer"
    assert handoff.target_agent_id == "consumer"
    assert handoff.channel == "main"
    assert handoff.status.value == "ok"


def test_failed_reef_handoff_is_aggregated_and_error_propagates() -> None:
    """Handoff telemetry reports authorization failure without swallowing it."""
    from praval.core.reef import Reef

    recorder = _ObservationRecorder()
    reef = Reef(auth_provider=lambda action, context: False)
    try:
        with use_observation_recorder(recorder):
            with ObservationScope(kind=ObservationKind.AGENT, agent_name="producer"):
                with pytest.raises(PermissionError, match="Unauthorized"):
                    reef.send("producer", "consumer", {"message": "blocked"})
    finally:
        reef.shutdown(wait=False)

    assert len(recorder.observations) == 1
    handoff = recorder.observations[0].handoffs[0]
    assert handoff.status.value == "error"
    assert handoff.error_type == "PermissionError"
