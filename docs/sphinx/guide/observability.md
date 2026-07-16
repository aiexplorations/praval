# Observability

Praval's optional observability components record local spans, store them in
SQLite, render them in the console, and export OTLP/HTTP payloads.

```python
from praval.observability import get_tracer, show_recent_traces

tracer = get_tracer()
with tracer.start_as_current_span("prepare-report") as span:
    span.set_attribute("report.kind", "demo")

show_recent_traces(limit=5)
```

Install `praval[observability]` for OTLP HTTP export. Export failures return a
failure result and are recorded or logged; the exporter does not provide a
circuit breaker or a guaranteed delivery queue.

The package version attached to OTLP scope and SDK metadata comes from the
installed Praval distribution.
