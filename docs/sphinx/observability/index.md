# Observability

Praval emits OpenTelemetry traces, metrics, and logs from the same completed
`ExecutionObservation`. Observability is disabled by default and importing
Praval never installs an SDK, starts a worker, opens SQLite, or replaces a
provider. The base package contains OpenTelemetry API instrumentation. Install
`praval[observability]` only when Praval should own SDK pipelines.

The runtime produces one observation per agent or workflow and aggregates
bounded facts for model use, tools, retries, HITL decisions, and Reef handoffs.
That provider-neutral observation is offered independently to telemetry and to
evaluation consumers. Evaluation therefore does not need to query a tracing
backend.

```{toctree}
:maxdepth: 2

quickstart
configuration
instrumentation
distributed-tracing
signals
collectors
sampling-performance
privacy-security
local-diagnostics
lifecycle-troubleshooting
api-migration
```

## Ownership model

- With no configuration, OpenTelemetry API calls are safe no-ops.
- In host-owned mode, the application constructs providers and remains
  responsible for their processors, exporters, flush, and shutdown.
- In Praval-owned mode, `configure_observability()` constructs selected SDK
  providers and returns an `ObservabilityHandle`. Praval flushes and shuts down
  only the components recorded in `handle.owned_signals`.
- A Collector is the recommended deployment boundary. Use HTTP/protobuf or
  gRPC rather than adding vendor SDK dependencies to Praval.

## Executed tutorial matrix

Each recipe is backed by an executable release test.

| Recipe | Guide | Executable evidence |
|---|---|---|
| Local development | [Quickstart](quickstart.md) | `tests/observability/test_sqlite_exporter.py` |
| Host-owned SDK | [Quickstart](quickstart.md#host-owned-sdk) | `tests/observability/test_lifecycle.py` |
| Praval-owned SDK | [Quickstart](quickstart.md#praval-owned-sdk) | `tests/observability/test_lifecycle.py` |
| Collector | [Collectors](collectors.md) | `tests/integration/test_otel_collector.py` |
| Multi-container | [Collectors](collectors.md#multiple-containers) | `tests/integration/test_otel_collector.py` |
| RabbitMQ | [Distributed tracing](distributed-tracing.md) | `tests/integration/test_rabbitmq_trace_propagation.py` |
| Privacy | [Privacy and security](privacy-security.md) | `tests/observability/test_privacy.py` |
| Failure isolation | [Lifecycle and troubleshooting](lifecycle-troubleshooting.md) | `tests/observability/test_health.py` |
| Shutdown | [Lifecycle and troubleshooting](lifecycle-troubleshooting.md#graceful-shutdown) | `tests/observability/test_lifecycle.py` |

The external-service tests are explicit gates. Run
`./scripts/run_otel_collector_tests.sh` for a real Collector and the RabbitMQ
integration test against a real broker before a release.
