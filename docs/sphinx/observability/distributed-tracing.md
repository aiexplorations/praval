# Distributed tracing

Praval propagates W3C Trace Context (`traceparent` and optional `tracestate`)
inside the Spore wire metadata. Serialization, in-memory Reef delivery,
RabbitMQ delivery, request/reply helpers, and secure Spore carriers preserve
that context.

A send creates a producer span, broker or in-memory delivery creates a delivery
span, and agent execution creates a consumer-side span. The receiver extracts
the carrier before starting work, so it inherits the correct trace even when
the producer is in another process. Invalid or absent context starts a new
trace and never trusts arbitrary IDs as valid OpenTelemetry context.

For RabbitMQ certification, start a real broker and run:

```bash
pytest tests/integration/test_rabbitmq_trace_propagation.py -v
```

For multiple services, assign a distinct stable `service.name` to each process
and send all of them to the same Collector. Do not share a SQLite file across
containers.

## Propagation sequence

1. The producer injects the active official OpenTelemetry context into a
   bounded Spore metadata carrier and starts `praval.reef.producer`.
2. Serialization preserves `traceparent` and optional `tracestate`; secure
   Spore signing/encryption protects the complete carrier with the payload.
3. The receiving Reef extracts only a valid W3C carrier before it starts
   `praval.reef.delivery` and `praval.reef.consumer`.
4. The receiving agent root is created while that context is active, so it is
   in the same trace even in another process.
5. Request/reply helpers repeat injection on the reply Spore. Correlation and
   causation IDs remain application/message identity and do not substitute for
   trace context.

In-memory and RabbitMQ backends follow the same sequence. Custom serializers
must preserve the whole metadata carrier. Copying only `trace_id` loses trace
flags and state and is not accepted as valid parent context.

## Sampling and trust

Parent-based sampling means a remote sampled flag controls the consumer trace.
Invalid version, length, hexadecimal content, all-zero IDs, or malformed flags
are rejected by the OpenTelemetry propagator. An absent/invalid carrier starts
a new local root; it never creates a span with attacker-chosen raw IDs.

To diagnose broken parentage, compare the producer span context with the
serialized carrier at the process boundary, then the delivery/consumer parent
in Collector output. Do not enable content capture merely to debug propagation.
