# Praval v0.8.3 O5 metrics, logs, exporters, and diagnostics design

## Status

Approved through the authoritative v0.8.3 plan and the completed O4 handoff.
This document fixes the O5 implementation boundary before code changes.

## Goal

Turn the O1 through O4 execution facts and spans into bounded production
signals. A configured Praval-owned pipeline must export traces, metrics, and
logs directly through the official OpenTelemetry SDK, while an optional local
SQLite exporter provides single-process diagnostics with complete-trace
retention. Telemetry failures must remain visible without changing application
results.

## Considered approaches

### 1. Observation-driven signals with official SDK pipelines (selected)

Convert each completed `ExecutionObservation` into bounded metric updates and
one correlated structured completion log. Keep spans on the existing runtime
path. Wrap official exporters and batch processors only to expose health,
queue-depth, export-failure, and drop facts that the SDK otherwise keeps
internal. Attach a separate SQLite `SpanExporter` to an official
`BatchSpanProcessor` when local diagnostics are enabled.

This keeps one source of truth for status, duration, usage, tools, retries, and
handoffs. It also preserves application-owned provider behavior and avoids
recreating OpenTelemetry transport or worker implementations.

### 2. Emit metrics independently at every runtime call site

This can report events immediately, but it duplicates O3 instrumentation,
risks disagreement with completed observations, and makes cancellation and
stream-finalization accounting difficult.

### 3. Persist spans first and poll SQLite for every export

This resembles the v0.8.2 design but makes SQLite a production queue, delays
signals, complicates multi-container operation, and directly contradicts the
approved plan.

## Signal contracts

- One completed agent or workflow observation increments a bounded invocation
  counter and records one duration histogram value.
- Usage records input, output, reasoning, cache-read, cache-write, and total
  tokens with `token.type` as a fixed vocabulary.
- Tool calls and Reef handoffs record bounded count and duration instruments.
- Retries, errors, timeouts, and cancellations use counters with fixed status
  vocabularies.
- Attributes may include service identity, observation kind, agent or workflow
  name, provider, model, request mode, operation, and status. They must not
  include trace IDs, run IDs, observation IDs, arbitrary user tags, prompts,
  responses, tool payloads, media, or case IDs.
- One correlated completion log is emitted while the observation root span is
  current. It includes the same status, identities, duration, usage totals, and
  bounded fact counts as the observation, but no captured content.
- Lifecycle, export failure, queue drop, and shutdown failure logs use the same
  privacy filter and fixed event names.

## Privacy boundary

- Metadata-only remains the default regardless of exporter type.
- A single sanitizer applies allowlisted keys, case-insensitive secret-key
  redaction, UTF-8 byte limits, collection limits, and deterministic truncation
  before values reach spans, logs, or SQLite.
- Content capture requires `capture_content = true` and an explicit field
  allowlist. Enabling capture without an allowlist captures nothing.
- Default redaction covers authorization, cookies, API keys, tokens, passwords,
  secrets, private keys, and common credential variants.
- Exporter configuration headers are never copied into telemetry attributes or
  logs.

## Export pipelines and health

- HTTP/protobuf and gRPC use the official OTLP trace, metric, and log exporters.
- Traces and logs use official bounded batch processors. Metrics use the
  official periodic reader.
- Tracking wrappers normalize success, failure, timeout, and exception results
  into a thread-safe health registry without allowing exporter errors onto the
  application path.
- Processor wrappers observe queue capacity immediately before delegation and
  count a drop when the official bounded queue is full. The official processor
  remains responsible for scheduling, batching, and worker lifecycle.
- Health snapshots expose only bounded per-signal counters and queue depth.
  Health instruments are emitted through the active meter without recursive
  log or trace generation.
- `force_flush()` and shutdown retain one shared deadline and one attempt per
  owned component. Timeout or failure returns `False` and updates health; it
  does not hang a non-daemon application worker.

## Local diagnostics

- `SQLiteSpanExporter` implements the official `SpanExporter` contract and is
  connected through `BatchSpanProcessor`.
- The schema stores trace and span identity, resource attributes,
  instrumentation scope, kind, timestamps, status, attributes, events, and
  links. WAL and a bounded busy timeout are enabled on every connection.
- Existing local viewer/query functions read the same database, but fail with a
  configuration error when the local exporter is disabled.
- `cleanup_traces(max_age_days, keep_last_n)` selects whole trace IDs and deletes
  all their spans in one transaction. Age and count retention never leave a
  partial retained trace.
- Retention runs after successful local batches under the same store lock.
- SQLite remains a local, single-process diagnostic target and is never used as
  the OTLP retry queue.

## Implementation tranches

1. Add observation-driven metrics and correlated logs with bounded attributes,
   privacy tests, and host-owned provider tests.
2. Add exporter and processor health tracking, bounded queue/drop behavior,
   downtime isolation, and lifecycle tests.
3. Convert SQLite storage to an official batch exporter, migrate its schema,
   and add whole-trace age/count retention tests.
4. Wire HTTP/protobuf and gRPC end to end and prove all three signals against a
   real OpenTelemetry Collector.
5. Measure no-op and enabled in-memory overhead, finish documentation handoff,
   and run the full O5 certification gates.

Each tranche begins with failing contract tests. No O5 change may redefine the
O2 observation schema, weaken O4 propagation, or begin evaluation work.

## Exit tests

- Deterministic metric values and bounded dimensions for success, error,
  timeout, cancellation, tools, retries, handoffs, usage, and limits.
- Correlated logs carry matching trace/span identity and never contain supplied
  prompts, responses, secrets, tool arguments, or credential headers by
  default.
- HTTP/protobuf and gRPC exporter construction and real Collector receipt for
  traces, metrics, and logs.
- Queue overflow, collector downtime, exporter exception, retry, force-flush,
  partial shutdown, and bounded timeout behavior.
- SQLite official exporter batches, resource/scope/event/link preservation,
  WAL/busy-timeout behavior, concurrent batches, and complete-trace retention
  by age and count.
- No-SDK and disabled paths create no workers or files.
- No-op end-to-end overhead stays below 2 percent; enabled in-memory batched
  telemetry stays below 5 percent, excluding network time.
- Full suite, coverage floors, lint, typing, exact supported-Python checks, and
  the O4 RabbitMQ propagation regression remain green.
