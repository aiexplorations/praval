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

