# Praval v0.8.3 O5 handoff

## Status

O5 metrics, logs, exporters, and local diagnostics are implemented and
certified locally. O6 observability documentation, exact-wheel validation, API
manifests, migration material, and the final observability contract freeze are
next. Evaluation work must not start before O6 passes.

## Delivered contracts

### Metrics and logs

- Every completed agent or workflow `ExecutionObservation` emits one invocation
  count, one duration value, bounded usage/tool/retry/handoff measurements, and
  one correlated completion log.
- Metric dimensions use fixed keys and bounded values. Trace, run, observation,
  handoff, and tool-call IDs are excluded.
- Completion logs remain metadata-only and carry the active root trace and span
  identifiers through the OpenTelemetry log record.
- Export attempts, exported items, failures, exceptions, queue drops, live queue
  depth/capacity, and lifecycle failures are available as fixed-dimension health
  measurements per signal.

### Export pipelines

- Praval-owned OTLP pipelines use the official OpenTelemetry HTTP/protobuf and
  gRPC exporters, `BatchSpanProcessor`, `PeriodicExportingMetricReader`, and
  `BatchLogRecordProcessor`.
- Health wrappers normalize exporter failures and exceptions without allowing
  them to change application results.
- Batch wrappers observe the official bounded queues. Drop counters are
  cumulative; queue gauges read current queue state, including worker drains.
- gRPC endpoints beginning with `https://` use TLS. `http://` and conventional
  `host:port` endpoints are explicitly plaintext.
- The reproducible real-Collector runner is
  `./scripts/run_otel_collector_tests.sh`. The Collector image defaults to
  `otel/opentelemetry-collector-contrib:0.113.0` and can be overridden with
  `PRAVAL_OTEL_COLLECTOR_IMAGE`.

### Privacy

- `TelemetrySanitizer` applies metadata-first content filtering, exact content
  allowlists, case-insensitive credential redaction, UTF-8 byte bounds, and
  collection bounds before local persistence.
- `capture_content = true` without `content_allowlist` captures no content.
- OTLP headers and exception messages are not copied into Praval health or
  lifecycle logs.

### Local diagnostics

- `SQLiteSpanExporter` implements the official `SpanExporter` contract and is
  attached through an official batch processor, independently or beside OTLP.
- SQLite records resource attributes/schema, instrumentation scope, span
  identity/kind/timing, status, attributes, events, links, and trace state.
- Connections enable WAL and a bounded busy timeout. Legacy v0.8.2 span tables
  migrate in place.
- `cleanup_traces(max_age_days=..., keep_last_n=...)` selects and deletes whole
  trace IDs. Retention runs after successful local batches under the store lock.
- `get_trace_store()` succeeds only while an explicitly configured local
  exporter is active. SQLite remains a local, single-process diagnostic target
  and must not be shared by containers.

## Architecture invariants for O6

- Importing `praval` or `praval.observability` must not configure providers,
  start workers, create files, or require the optional OpenTelemetry SDK.
- Application-owned providers are never replaced, flushed, or shut down by
  Praval. Processors attached by Praval to host trace/log providers remain
  Praval-owned.
- An endpoint or local-store configuration must either attach a live pipeline or
  fail with `PravalConfigurationError`; configuration cannot be accepted and
  ignored.
- Export, queue, lifecycle, and local-store failures never replace an application
  result or exception.
- Metadata-only remains the default. Content requires both opt-in and an exact
  field allowlist.
- SQLite is not an OTLP retry queue or a production aggregation store.
- O6 must not redefine the frozen O2 `ExecutionObservation` fields or weaken O4
  W3C propagation.

## Certification evidence

Run on macOS with Python 3.13.15 and compatibility typing for Python 3.10:

- `make test-cov`: 1,904 passed, 132 skipped; total coverage 93.20%; release
  coverage floors passed.
- Focused O5 new-module coverage: health 99%, signals 99%, privacy 98%, lifecycle
  97%, SQLite exporter 100%, and SQLite store 97%.
- `make lint`: passed.
- `make type-check`: strict Python 3.13 and Python 3.10 compatibility passed.
- `./scripts/run_otel_collector_tests.sh`: two passed. A real Collector received
  traces, metrics, and logs over HTTP/protobuf and gRPC and wrote valid JSON
  export requests.
- `pytest tests/integration/test_rabbitmq_trace_propagation.py -v`: one passed
  against RabbitMQ 3.13.7 with no skip.
- `PRAVAL_RUN_PERFORMANCE_TESTS=1 pytest
  tests/performance/test_observability_overhead.py -q -s`: repeated release
  runs passed. The latest stable measurement was 1.31% no-op overhead and 1.42%
  enabled in-memory batched overhead, below the 2% and 5% limits.
- `bash -n scripts/run_otel_collector_tests.sh`: passed.

## Known limitations and deferred work

- The Collector fixture is a local certification dependency, not a runtime
  dependency. CI/O6 must choose and record the release certification image.
- Local SQLite queries intentionally require an active local exporter. Existing
  v0.8.2 documentation that implied an always-created default database must be
  replaced in O6.
- Health is aggregated per signal. It does not create high-cardinality exporter
  instance or destination dimensions.
- Full production aggregation remains the responsibility of the configured OTLP
  backend. Multi-container services must not mount one SQLite database.

## O6 starting boundary

O6 may change documentation, examples, API manifests, packaging diagnostics,
release notes, migration guidance, exact-wheel tests, and certification scripts.
It may fix contract defects found by those gates, with focused regressions. It
must not begin `praval.eval`, change observation identity semantics, or publish a
release.
