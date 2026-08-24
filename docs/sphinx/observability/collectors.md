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

## Multiple containers

Each application container should use a distinct stable service name and send
to the Collector's network address, for example `http://otel-collector:4318`
or `otel-collector:4317`. A Compose deployment normally runs one Collector
service on the application network. In Kubernetes, use a sidecar for strong
failure isolation or a gateway Deployment for shared policy. Mount TLS trust
material read-only and terminate or originate TLS according to the platform's
network policy.

The Collector is the aggregation layer. SQLite diagnostics are single-process
and must not be placed on a shared container volume. Collector downtime is
bounded by the SDK queue and export timeouts; drops and failures are visible in
telemetry health metrics.

