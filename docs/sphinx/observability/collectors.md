# Collectors and deployment

Run an OpenTelemetry Collector near Praval services and let it handle routing,
retries, authentication, TLS, and vendor-specific backends. Praval supports
OTLP HTTP/protobuf and gRPC for traces, metrics, and logs.

The repository's executable local configuration is
`tests/integration/fixtures/otel-collector-config.yaml`. Run it and its
black-box assertions with:

```bash
./scripts/run_otel_collector_tests.sh
```

The script starts a Collector, sends all three signals over HTTP/protobuf and
gRPC, verifies Collector output, and cleans up. Export credentials belong in
the environment variable named by `observability.otlp.headers_env`.

## Local Collector

A minimal development pipeline receives both OTLP transports and writes
structured signal output. The release fixture adds assertions and bounded
batching around this shape:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 256
  batch: {}

exporters:
  debug:
    verbosity: detailed

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [debug]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [debug]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [debug]
```

Point Praval at `http://127.0.0.1:4318` with protocol `http/protobuf`, or at
`127.0.0.1:4317` with protocol `grpc`. For HTTP, the SDK appends the standard
signal paths when a base endpoint is supplied.

## Multiple containers

Each application container should use a distinct stable service name and send
to the Collector's network address, for example `http://otel-collector:4318`
or `otel-collector:4317`. A Compose deployment normally runs one Collector
service on the application network. In Kubernetes, use a sidecar for strong
failure isolation or a gateway Deployment for shared policy. Mount TLS trust
material read-only and terminate or originate TLS according to the platform's
network policy.

```yaml
# Docker Compose fragment
services:
  app:
    environment:
      PRAVAL_OBSERVABILITY: "on"
      PRAVAL_SERVICE_NAME: "orders-agent"
      PRAVAL_OTLP_ENDPOINT: "http://otel-collector:4318"
      OTEL_EXPORTER_OTLP_PROTOCOL: "http/protobuf"
    depends_on: [otel-collector]
  otel-collector:
    image: otel/opentelemetry-collector-contrib:<pinned-version>
    command: ["--config=/etc/otelcol/config.yaml"]
    volumes:
      - ./otel-collector.yaml:/etc/otelcol/config.yaml:ro
```

Pin the Collector image and validate its configuration in CI. The repository
does not embed a vendor exporter in Praval: add vendor authentication, routing,
resource processing, and export at the Collector. For Kubernetes, a sidecar
keeps one application's queue/failure domain local; a gateway centralizes
tail-sampling and credentials. Do not run both without a clear routing reason.

## Headers and TLS

Set `observability.otlp.headers_env` to a variable name such as
`PRAVAL_OTLP_HEADERS`, then store a comma-separated `name=value` string in that
environment variable. The named variable must exist and parse correctly.
Never place its value in `praval.toml`, command output, or documentation
artifacts.

Use an HTTPS endpoint and platform trust roots outside a trusted development
network. Private CA distribution, mutual TLS termination, certificate rotation,
and Collector-to-backend identity remain deployment responsibilities. A bad
certificate or authentication response is an exporter failure, not permission
to fall back to an unencrypted endpoint.

The Collector is the aggregation layer. SQLite diagnostics are single-process
and must not be placed on a shared container volume. Collector downtime is
bounded by the SDK queue and export timeouts; drops and failures are visible in
telemetry health metrics.

During a Collector outage, the OpenTelemetry SDK retries only within its own
bounded exporter behavior and batch queue. Praval request execution does not
wait indefinitely. Alert on queue utilization before capacity, and treat drops
as lost telemetry rather than silently reconstructing them from evaluation or
application databases.
