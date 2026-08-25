# Praval v0.8.3 O4 Reef and Spore propagation design

## Status

Approved through the authoritative v0.8.3 plan, the O3 handoff, and the accepted
one-observation-per-agent/workflow decision. This document records the O4 design
boundary before implementation.

## Goal

Carry official W3C trace context across every Praval message boundary without
using the legacy convenience `trace_id` as a parent-context mechanism. Preserve
producer, delivery, consumer, handoff, and workflow relationships while keeping
the O2 observation schema and O3 aggregation semantics unchanged.

## Considered approaches

### 1. Versioned top-level carrier on `Spore` (selected)

Add `trace_context: Dict[str, str]` to the versioned Spore contract. Use the
configured OpenTelemetry propagator to inject at producer boundaries and extract
at delivery and consumer boundaries. Serialize the carrier in JSON, AMQP headers
and body, request/response helpers, and secure Spores.

This is explicit, transport-neutral, backward compatible through a default empty
mapping, and matches the release plan. It also allows baggage and `tracestate`
without overloading application metadata.

### 2. Store context in legacy `metadata`

This minimizes schema changes but mixes framework transport state with user
metadata, makes authentication policy ambiguous, and retains the legacy design
that O4 is intended to replace.

### 3. Store context only in transport headers

This is natural for AMQP but cannot survive ordinary Spore JSON round-trips or
in-memory and secure paths consistently. It would create transport-specific
parentage behavior.

## Contract and data flow

- `Spore.trace_context` is an independent string-to-string mapping with an empty
  default and defensive normalization.
- Producer send and broadcast boundaries inject the current configured
  propagator into the carrier. A caller-supplied valid carrier is preserved when
  no current span exists.
- The convenience `trace_id` is derived from the active or extracted span when
  available. It is never used to reconstruct a parent.
- JSON serialization includes the carrier as a top-level versioned field.
- AMQP serialization includes the carrier in the body envelope and maps
  `traceparent`, `tracestate`, and baggage to headers for interoperable brokers.
  Deserialization accepts either representation and rejects non-string values.
- Delivery and consumer boundaries extract a remote parent and attach it only
  for the bounded handler invocation. Context tokens are always detached in a
  `finally` block, preventing async task or concurrent-message leakage.
- Request helpers create a producer carrier. Responses inject from the request's
  extracted context so the response remains in the same trace even when helper
  work crosses an execution boundary.
- Secure Spores carry the same mapping. For encrypted targeted messages, the
  canonical carrier bytes are included in the Ed25519 authenticated material;
  tampering fails verification. Plaintext broadcasts preserve the carrier but
  cannot claim authenticated transport security.

## Telemetry and observations

O4 reuses existing runtime-observation contracts. It adds relationship facts at
stable Reef boundaries rather than creating per-fact observations. Agent and
workflow executions remain one observation each with aggregated facts. O4 does
not add metrics, logs, exporters, retention, or evaluation behavior.

## Error handling and compatibility

- Missing or empty carriers are valid and retain no-op behavior.
- Malformed W3C values are ignored by the official propagator rather than
  converted from `trace_id`.
- Serialization rejects carrier keys or values that are not strings.
- Handler and transport exceptions keep their current propagation behavior;
  context cleanup still runs.
- Existing spores, AMQP messages, and secure-spore payloads without a carrier
  continue to deserialize.

## Test strategy

- Unit tests: carrier validation, JSON round-trip, cloning/reference helpers,
  AMQP header/body round-trip, sampling, `tracestate`, baggage, and malformed
  input compatibility.
- In-memory integration tests: producer-to-consumer parentage, request/response
  continuity, errors, and concurrent async isolation.
- RabbitMQ black-box tests: the same trace and expected parent relationships
  through a real broker, with a deterministic skip only outside the mandatory
  O4 certification command.
- Secure tests: encrypted round-trip, carrier preservation, and carrier-tamper
  rejection.
- Package gates: focused tests, full suite, lint, mypy, coverage, and the plan's
  supported-Python checks. O4 is not green until its mandatory RabbitMQ run
  executes against a real local broker.
