# Praval 0.8.3

> Release-candidate notes. Do not publish, tag, or cut this release until the
> evaluation workstream and all combined observability and evaluation gates
> are complete.

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

The release candidate must be installed from the exact wheel. CI executes its
documented imports and observability examples, validates API and feature-claim
manifests, builds documentation with warnings as errors, sends traces, metrics,
and logs to a real Collector over both transports, checks RabbitMQ parentage,
and runs privacy, failure, shutdown, coverage, and performance gates.

Test totals, coverage percentages, timings, and hashes belong in generated
evidence rather than these notes.

## Remaining release scope

The evaluation contracts, stores, runners, judges, gates, plugins, sampled
online evaluation, documentation, and combined release certification remain
required. This file is not authorization to publish 0.8.3.
