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

## Fields and defaults

| Field | Type | Default | Validation/meaning |
|---|---|---|---|
| `observability.enabled` | bool | `false` | no SDK pipeline when false |
| `capture_content` | bool | `false` | also requires exact allowlist |
| `content_allowlist` | string array | `[]` | supported content-kind names only |
| `sampling` | enum | `parentbased_traceidratio` | always on/off or parent ratio |
| `sample_ratio` | float | `1.0` | 0 through 1 |
| `flush_timeout_millis` | int | `5000` | positive total bound |
| `otlp.endpoint` | string/null | null | required for enabled OTLP signals |
| `otlp.protocol` | enum | `http/protobuf` | or `grpc` |
| `otlp.traces` | bool | `true` | signal selection |
| `otlp.metrics` | bool | `true` | signal selection |
| `otlp.logs` | bool | `true` | signal selection |
| `otlp.headers_env` | string/null | null | bounded environment-variable name |
| `otlp.max_queue_size` | int | `2048` | positive |
| `otlp.max_export_batch_size` | int | `512` | positive and no larger than queue |
| `otlp.schedule_delay_millis` | int | `5000` | positive |
| `otlp.export_timeout_millis` | int | `30000` | positive |
| `otlp.metric_export_interval_millis` | int | `60000` | positive |
| `local.enabled` | bool | `false` | traces must be enabled |
| `local.path` | string | user diagnostic DB | expanded at runtime |
| `local.max_traces` | int | `10000` | positive whole-trace retention |
| `local.max_age_days` | int | `7` | non-negative; zero disables age pruning |

Resource fields are `app.service_name` (default `praval`), optional
`app.service_version`, and optional `app.deployment_environment`. An enabled
pipeline requires a non-blank service name.

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

`PRAVAL_CONFIG_FILE` selects an explicit TOML file before discovery. If absent,
Praval searches the working directory and its parents for `praval.toml`; it
does not read a hidden home-directory default. `PRAVAL_DEFAULT_PROVIDER` and
`PRAVAL_DEFAULT_MODEL` configure the default model profile, not observability.

Only the standard OpenTelemetry variables listed above are part of Praval's
typed merge contract. Signal-specific endpoints, arbitrary sampler arguments,
or vendor-specific variables may still affect host-owned SDKs, but Praval does
not claim to parse or validate them.

`headers_env` names an environment variable whose value is a comma-separated
`name=value` list. Keep tokens out of TOML and source control. Missing or
malformed header variables fail configuration.

The older `sample_rate`, `otlp_endpoint`, and `storage_path` constructor fields
and `PRAVAL_SAMPLE_RATE`, `PRAVAL_OTLP_ENDPOINT`, and `PRAVAL_TRACES_PATH`
environment variables remain migration-compatible for v0.8.2 applications.
