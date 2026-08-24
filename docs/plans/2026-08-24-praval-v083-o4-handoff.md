# Praval v0.8.3 O4 handoff

## Completed package

Work package O4, Reef and Spore propagation, is complete.

Spores now carry an explicit W3C text-map carrier through JSON, in-memory Reef,
RabbitMQ, request and response helpers, and secure Spore paths. Reef creates
producer, delivery, and consumer spans with distributed parentage, while each
handoff remains an aggregated fact in the active agent or workflow observation.
O4 does not create standalone observations for transport facts.

## Contracts and invariants

- `Spore.trace_context` is a defensive string-to-string mapping with an empty
  backward-compatible default. It is serialized as a top-level JSON field and
  in the versioned AMQP body envelope.
- RabbitMQ messages also expose `traceparent`, `tracestate`, and `baggage` as
  interoperable AMQP headers. Valid headers override the matching body carrier
  entry at the transport boundary.
- Injection and extraction use the configured OpenTelemetry propagator. Reef
  does not reconstruct parents from the convenience `trace_id` field.
- `Reef.send()` accepts an explicit carrier for adapters forwarding an already
  extracted context. An active context takes precedence; otherwise the supplied
  carrier is retained.
- Producer spans inject the outgoing carrier. Delivery and consumer spans use
  the extracted remote parent and keep the carrier attached only for the
  bounded handler call.
- Context attachment is detached in `finally` blocks. Concurrent sync and async
  deliveries cannot inherit another Spore's context, including failure paths.
- Sampling flags, `tracestate`, and baggage survive injection, serialization,
  extraction, and handler activation.
- Derived request responses preserve the request carrier even when the response
  helper runs after the request handler's active scope has ended.
- Both ordinary and precise RabbitMQ subscriptions activate the received
  carrier. The latter covers request waiters and other exact-subscription
  consumers.
- Encrypted targeted `SecureSpore` messages sign the canonical carrier bytes in
  addition to the encrypted payload and nonce. Carrier tampering fails Ed25519
  verification.
- Legacy encrypted Spores without a carrier field continue to verify using the
  pre-O4 authenticated material. Removing the carrier field from a new message
  does not bypass authentication because its signature includes the new
  canonical bytes.
- Plaintext secure broadcasts preserve the carrier but do not claim carrier
  authentication without an authenticated transport.
- Successful and failed Reef sends append one `ReefHandoffObservation` fact to
  the active observation. Application and authorization errors retain their
  original propagation behavior.
- The obsolete opt-in Reef monkey-patch was removed from the legacy
  instrumentation manager. Native Reef boundaries now produce one producer
  span instead of duplicate legacy and native spans.

## Test matrix

- Spore validation, defensive copying, JSON round trips, reference helpers, and
  explicit public carrier forwarding.
- Official W3C propagation of sampled and unsampled flags, `tracestate`, and
  baggage.
- AMQP body and header round trips plus stable rejection of malformed carriers.
- In-memory producer-to-consumer parentage, stable Reef boundary names, and
  concurrent async isolation.
- Request and derived-response continuity outside an active handler scope.
- RabbitMQ normal subscriptions, precise subscriptions, handler failures,
  cleanup, and unsampled parents with a transport callback double.
- A mandatory black-box test through a real RabbitMQ 3.13 broker proving
  `workflow root -> producer -> delivery -> consumer` parentage.
- Secure MessagePack round trips, authenticated-carrier verification, tamper
  rejection, handler parentage, secure delivery spans, and legacy signature
  compatibility.
- One-observation aggregation for successful and failed handoffs.
- Existing Reef, backend, request/reply, secure transport, serialization, and
  observability regression suites.

## Verification

- Final repository coverage suite: 1,873 passed and 129 skipped.
- Total source coverage: 92.94 percent, above the 90 percent release floor.
- Per-file coverage release floors pass.
- New propagation helper coverage is 100 percent. Secure Reef and Secure Spore
  coverage are 99 percent.
- Repository-wide flake8 passes.
- Strict source typing passes for Python 3.13 and the repository's Python 3.10
  compatibility target.
- Focused O4 propagation suite: 23 tests pass.
- Mandatory live RabbitMQ black-box certification: 1 test passes and does not
  skip.
- The full sandboxed suite skips RabbitMQ and optional external-service tests;
  the RabbitMQ requirement is satisfied by the separate mandatory live run.

Commands used for the final gate:

```text
source venv/bin/activate && make lint
source venv/bin/activate && make type-check
source venv/bin/activate && make test-cov
source venv/bin/activate && pytest \
  tests/integration/test_rabbitmq_trace_propagation.py -q -rs
```

## Known limitations and deferred work

- O4 records trace relationships and observation handoff facts only. Metrics,
  structured logs, exporter queues, live OTLP delivery, local retention, and
  exporter health belong to O5.
- The base package uses the OpenTelemetry API but remains functional without the
  OpenTelemetry SDK. Exact-wheel and documented-import certification remains an
  O6 release gate.
- Plaintext secure broadcasts cannot authenticate carrier metadata by
  themselves. Deployments requiring that property must use authenticated
  transport or targeted encrypted Spores.
- The package version remains 0.8.2 during staged development. No v0.8.3 release
  is authorized until O1 through O6, E1 through E6, and the combined release
  gates in the authoritative plan all pass.
- Evaluation implementation remains blocked until O5 and O6 complete the
  observability foundation checkpoint.

## Next package

Proceed with O5, metrics, logs, exporters, and local diagnostics. Start from
this handoff, the O5 section of the authoritative release plan, and the frozen
O2 through O4 observation and propagation contracts.

O5 must add bounded OpenTelemetry metrics, correlated structured logs, live
batched OTLP HTTP/protobuf and gRPC exporters, optional SQLite batch export,
retention, privacy filtering, exporter health, queue bounds, and drop counters.
It must not begin `praval.eval`, change the one-observation-per-agent/workflow
contract, or weaken the O4 distributed and authenticated carrier guarantees.
