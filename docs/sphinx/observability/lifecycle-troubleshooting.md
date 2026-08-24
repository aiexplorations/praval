# Lifecycle and troubleshooting

`configure_observability()` is explicit and process-scoped. Calling it again
with the same effective configuration is idempotent. Calling it with different
settings while the prior handle is active raises `PravalConfigurationError`.

## Graceful shutdown

```python
from praval.observability import force_flush, shutdown_observability

flushed = force_flush(5_000)
closed = shutdown_observability(5_000)
if not (flushed and closed):
    # Report degraded telemetry without failing an already completed request.
    pass
```

The timeout is a total bound. Praval makes a bounded attempt for each component
it owns, isolates exceptions, and returns `False` for timeout or failure. It
does not shut down host-owned providers. Batch workers are daemon threads and
shutdown is safe to call more than once.

## Diagnosis

- **No spans:** verify `observability.enabled`, signal enablement, sampling,
  endpoint reachability, and that shutdown/flush occurs after work.
- **No local traces:** enable `observability.local.enabled`, retain traces, and
  flush before querying.
- **Collector gaps:** inspect export failures, drops, queue depth, and Collector
  logs. Collector downtime never becomes an unbounded application wait.
- **Broken parentage:** preserve Spore metadata through custom serialization and
  extract before starting consumer work.
- **Async cross-talk:** create tasks normally; Praval uses context variables and
  OpenTelemetry context rather than process-global current span IDs.
- **Configuration error:** ensure an endpoint has at least one signal, local
  storage has traces enabled, batch size does not exceed queue capacity, and a
  named header environment variable exists.

## Provider ownership

With host-owned providers, construct processors, exporters, and metric readers
before passing providers to `configure_observability()`. The returned handle
has an empty `owned_signals` set and Praval will neither replace globals nor
shut those providers down. In particular, an OTLP metric reader cannot be
attached after a host-owned `MeterProvider` is constructed.

With Praval-owned providers, the observability extra must be installed and the
enabled topology must have a usable local or OTLP destination. The handle
records each owned signal. Reconfiguration with an identical effective config
returns the active handle; a different config fails until shutdown resets the
process lifecycle.

## Failure sequence

For a missing signal, diagnose in this order:

1. configuration precedence and selected service resource;
2. signal enablement and parent-based sampling;
3. instrumentation active before the operation;
4. SDK queue depth/drops and export failure type;
5. endpoint/protocol/headers/TLS and Collector receiver;
6. Collector processor/exporter logs and backend ingestion;
7. bounded flush/shutdown result.

Do not repeatedly reconfigure to recover an exporter. Fix the external state or
restart the owned lifecycle cleanly. A failed flush means delivery is unknown;
it does not mean agent execution failed.

## Async and process boundaries

Context variables follow normal asyncio task creation. If custom code clears
context, starts work in a raw thread/process, or manually serializes a Spore,
it owns context handoff. Extract remote context before creating consumer work,
and detach it afterward so later tasks cannot inherit the wrong trace.
