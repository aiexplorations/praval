# API reference and v0.8.2 migration

The supported module is `praval.observability`. The provider-neutral contracts
used by both telemetry and evaluation are in `praval.models`.

## Lifecycle API

| Symbol | Contract |
|---|---|
| `ObservabilityConfig` | Immutable validated signal, sampling, privacy, OTLP, and local configuration. |
| `ObservabilityHandle` | Active configuration, providers, optional local store, ownership set, bounded `force_flush()` and `shutdown()`. |
| `configure_observability()` | Configure host-owned or Praval-owned providers; raises `PravalConfigurationError` for conflicts, missing extras, or invalid topology. |
| `configure_tracing()` | Compatibility helper for a Praval-owned trace-only OTLP pipeline. |
| `get_tracer()`, `get_meter()`, `get_logger()` | Official OpenTelemetry API objects; safe no-ops without configuration. |
| `force_flush()` | Flush Praval-owned components within the configured or supplied millisecond bound; returns success. |
| `shutdown_observability()` | Flush and close Praval-owned components; idempotent and bounded. |

## Observation API

`ExecutionObservation` is immutable and versioned with `schema_version = 1`.
It contains run and subject identity, UTC timing, terminal status, structured
error type, provider/model/request metadata, bounded usage, tool, retry, HITL,
handoff and content-reference facts, privacy state, and optional trace/span
correlation.

`ObservationRecorder` is a structural protocol with
`record(observation: ExecutionObservation) -> None`. Use
`configure_observation_recorder()` for the process default,
`use_observation_recorder()` for one sync or async context, and
`CompositeObservationRecorder` to isolate and fan out to consumers. Recorder
failure is logged and cannot fail the agent request.

## Compatibility surface

`Tracer`, `Span`, `SpanKind`, `SpanStatus`, `TraceContext`,
`get_current_span()`, `SQLiteTraceStore`, `get_trace_store()`, console viewing,
and instrumentation helpers remain available. `SpanKind` and the tracer facade
map to official OpenTelemetry objects.

The old hand-built `OTLPExporter` and `export_traces_to_otlp()` remain only for
compatibility. New applications configure official OTLP HTTP/protobuf or gRPC
pipelines with `configure_observability()`. A compatibility export helper may
flush a matching active pipeline; it must not silently redirect an already
configured process.

## Migration from v0.8.2

1. Install `praval[observability]` when Praval owns SDK providers.
2. Replace implicit or import-time setup with `configure_observability()`.
3. Enable SQLite explicitly and treat it as local, single-process diagnostics.
4. Replace flat `sample_rate`, `otlp_endpoint`, and `storage_path` fields with
   `sample_ratio`, `otlp`, and `local`; compatibility aliases emit deprecation
   warnings.
5. Send all three signals to a Collector and call bounded shutdown during
   application termination.
6. Keep content capture off unless an exact allowlist and retention policy have
   been reviewed.
