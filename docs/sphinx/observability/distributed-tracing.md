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

