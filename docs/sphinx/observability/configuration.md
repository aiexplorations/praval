# Configuration reference

Configuration precedence is: typed defaults, discovered or explicit
`praval.toml`, environment variables, then explicit
`configure_observability()` arguments. Unknown fields and invalid bounds fail
with `PravalConfigurationError`; endpoints are never silently ignored.

## `praval.toml`

```toml
[app]
service_name = "orders-agent"
service_version = "0.8.3"
deployment_environment = "production"

[observability]
enabled = true
capture_content = false
content_allowlist = []
sampling = "parentbased_traceidratio"
sample_ratio = 0.10
flush_timeout_millis = 5000

[observability.otlp]
endpoint = "http://otel-collector:4318"
protocol = "http/protobuf"
traces = true
metrics = true
logs = true
headers_env = "PRAVAL_OTLP_HEADERS"
max_queue_size = 2048
max_export_batch_size = 512
schedule_delay_millis = 5000
export_timeout_millis = 30000
metric_export_interval_millis = 60000

[observability.local]
enabled = false
path = ".praval/telemetry.db"
max_traces = 10000
max_age_days = 7
```

`sampling` accepts `always_on`, `always_off`, or
`parentbased_traceidratio`. Ratios are between 0 and 1. Queue sizes, batch
sizes, delays, timeouts, and retention counts are bounded and validated; a
batch cannot exceed its queue.

## Environment variables

| Variable | Target | Notes |
|---|---|---|
| `PRAVAL_SERVICE_NAME`, `OTEL_SERVICE_NAME` | `app.service_name` | Praval takes precedence when both are set. |
| `PRAVAL_SERVICE_VERSION` | `app.service_version` | Optional resource value. |
| `PRAVAL_ENVIRONMENT` | `app.deployment_environment` | Resource value and legacy `auto` input. |
| `PRAVAL_OBSERVABILITY` | `observability.enabled` | `on`, `off`, or legacy `auto`; default remains disabled. |
| `PRAVAL_SAMPLE_RATE` | `observability.sample_ratio` | Float from 0 through 1. |
| `PRAVAL_CAPTURE_CONTENT` | `observability.capture_content` | Boolean; still requires an allowlist. |
| `PRAVAL_TRACES_PATH` | `observability.local.path` | Does not enable SQLite by itself. |
| `PRAVAL_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_ENDPOINT` | `observability.otlp.endpoint` | Base URL or signal URL. |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `observability.otlp.protocol` | `http/protobuf` or `grpc`. |
| `OTEL_TRACES_EXPORTER`, `OTEL_METRICS_EXPORTER`, `OTEL_LOGS_EXPORTER` | signal enablement | The supported value `none` disables that signal. |

`headers_env` names an environment variable whose value is a comma-separated
`name=value` list. Keep tokens out of TOML and source control. Missing or
malformed header variables fail configuration.

The older `sample_rate`, `otlp_endpoint`, and `storage_path` constructor fields
and `PRAVAL_SAMPLE_RATE`, `PRAVAL_OTLP_ENDPOINT`, and `PRAVAL_TRACES_PATH`
environment variables remain migration-compatible for v0.8.2 applications.

