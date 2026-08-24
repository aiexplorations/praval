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

