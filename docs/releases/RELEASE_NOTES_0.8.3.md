# Praval 0.8.3

Released on August 25, 2026.

Praval 0.8.3 replaces the former implicit, trace-only diagnostics with an
explicit OpenTelemetry foundation and a provider-neutral observation contract
that evaluation can consume without importing SDK internals.

## Observability foundation

- One immutable, versioned `ExecutionObservation` is recorded for each agent
  or workflow. Model, tool, retry, HITL, and Reef facts are aggregated and
  bounded.
- Base-package instrumentation works with the OpenTelemetry API and remains a
  safe no-op until configured.
- Applications may supply host-owned providers, or install
  `praval[observability]` and let Praval own selected trace, metric, and log
  pipelines.
- Official exporters send all three signals over OTLP HTTP/protobuf or gRPC.
- W3C context follows Spores through serialization, in-memory Reef, RabbitMQ,
  request/reply helpers, and secure carriers.
- SQLite is an explicit local diagnostic exporter with batching, WAL,
  migrations, whole-trace retention, and metadata-only privacy defaults.
- Export attempts, failures, exceptions, drops, queue state, and lifecycle
  failures are observable without exposing payloads or credentials.

## Evaluation capabilities

- JSONL datasets keep candidate/reference material ephemeral while immutable
  cases and subjects persist content identities and one aggregated
  `ExecutionObservation` per agent or workflow.
- SQLite and PostgreSQL share one store contract for runs, results, gates,
  baselines, durable jobs, leasing, retry, recovery, attempts, and idempotency.
- Offline runners compose deterministic metrics, metric plugins, direct model
  judges, and least-privilege ordinary evaluator agents with strict versioned
  output, time, token, cost, tool, memory, HITL, and self-evaluation policy.
- Gates support explicit aggregation/threshold policy. Baselines are promoted
  explicitly and regression comparison is available through `praval eval`.
- The optional `eval-ragas` extra adds the tested RAGAS 0.4 metrics through
  configured Praval model and embedding runtimes without exposing RAGAS types
  in the core API.
- Sampled online evaluation is disabled by default. When explicitly started
  with PostgreSQL, request work is limited to deterministic sampling and a
  bounded enqueue; durable workers perform all evaluator calls and link their
  telemetry to the original completed trace.

## Documentation and patterns

Observability and Evaluation are top-level documentation areas. The Evaluation
patterns guide recommends stable identities, structured outcomes, bounded
execution, deterministic dependency seams, and exactly one immutable
observation with aggregated facts per evaluated agent or workflow. It pairs
targets with separate least-privilege evaluator agents and explicitly rejects
shared target state, unversioned rubrics, unsafe tools, automatic baselines,
and request-path judging.

Python 3.9 support ends with v0.8.2. v0.8.3 supports Python 3.10 through 3.14.
See the complete migration guide under `docs/sphinx/guide/v083-migration.md`.

## Migration from v0.8.2

Observability is disabled by default. Call `configure_observability()` during
application startup and `shutdown_observability()` during graceful shutdown.
Install the observability extra only when Praval owns SDK providers. Enable
SQLite explicitly and never share its file between containers.

The legacy flat `sample_rate`, `otlp_endpoint`, and `storage_path` fields map to
the typed nested configuration with deprecation warnings. Compatibility
tracing, local viewing, and export helpers remain available during this
migration window. The complete replacement table is in
[`docs/sphinx/observability/api-migration.md`](../sphinx/observability/api-migration.md).

## Certification evidence

The published release was installed from the exact wheel. CI executed its
documented imports and observability examples, validated API and feature-claim
manifests, built documentation with warnings as errors, sent traces, metrics,
and logs to a real Collector over both transports, checked RabbitMQ parentage,
and ran privacy, failure, shutdown, coverage, and performance gates.

Test totals, coverage percentages, timings, and hashes belong in generated
evidence rather than these notes.

## Release status

The implementation, documentation, and local combined certification are
complete through sampled online workers. The release passed exact-wheel,
example/tutorial, real Collector, PostgreSQL, RabbitMQ, RAGAS, privacy,
performance, shutdown, API inventory, Sphinx warnings-as-errors, and link
checks together. Praval 0.8.3 is published from the tagged release commit.
