# Local SQLite diagnostics

SQLite is an opt-in trace diagnostic for local development and CI. Enable
`observability.local.enabled`, keep traces enabled, and set an explicit path.
`get_trace_store()` raises `PravalConfigurationError` unless that exporter is
active.

The exporter uses the official `SpanExporter` contract behind an official
batch processor. It preserves resource and instrumentation scope, span kind and
status, events, links, trace state, and privacy-filtered attributes. WAL mode,
a bounded busy timeout, and batched writes support concurrent activity within
one process.

Count and age retention delete whole old traces, never isolated spans from a
retained trace. Existing legacy databases are migrated when opened. Call
`force_flush()` before reading immediately after work because export is
batched.

SQLite is not a production aggregation service, durable delivery queue, or
multi-container store. Use a Collector and an observability backend for those
roles.

## Inspecting traces

```python
from praval.observability import (
    force_flush,
    get_trace_store,
    print_traces,
    show_recent_traces,
)

force_flush(5_000)
store = get_trace_store()
trace_ids = store.get_recent_traces(limit=20)
show_recent_traces(limit=5)
if trace_ids:
    print_traces(trace_id=trace_ids[0])
```

The viewer renders privacy-filtered stored spans; it does not contact an OTLP
backend. Query only after a successful bounded flush when immediate visibility
matters. Concurrent threads in one process are supported through WAL and busy
timeouts, but multiple service instances still need a Collector.

## Retention behavior

`max_traces` keeps the newest complete traces by trace identity.
`max_age_days=0` disables age pruning while leaving count pruning active.
Pruning removes an entire selected trace transactionally so a retained trace
does not lose arbitrary children. Back up or export traces that must outlive
the local diagnostic window; SQLite retention is not an audit archive.

Common failures are an unexpanded/unwritable parent directory, local export
enabled while traces are disabled, reading before batch flush, or opening an
unsupported/corrupt database. Configuration and migration failures are
explicit; Praval does not silently switch to a different path.
