# Install and five-minute quickstart

## Base-package instrumentation

```bash
python -m pip install praval
```

The base install includes the OpenTelemetry API and Praval's provider-neutral
observation contracts. It does not include the SDK or exporters. Existing
agent code works unchanged and telemetry is a no-op until a provider is
configured.

Check the installed API, SDK, OTLP transports, and tested OpenTelemetry minor
without printing credentials:

```bash
praval doctor --json
```

## Local development

Install the managed pipelines and opt in to local SQLite diagnostics:

```bash
python -m pip install "praval[observability]"
```

```python
from praval.observability import (
    ObservabilityConfig,
    configure_observability,
    force_flush,
    get_trace_store,
    shutdown_observability,
)

config = ObservabilityConfig(
    enabled=True,
    local={"enabled": True, "path": ".praval/telemetry.db"},
    otlp={"traces": True, "metrics": False, "logs": False},
)
handle = configure_observability(config, service_name="local-demo")

# Run agents or workflows here. Their completed observations create spans.
force_flush(5_000)
recent_trace_ids = get_trace_store().get_recent_traces(limit=10)
shutdown_observability(5_000)
```

SQLite is explicit, local, and single-process. It is not a shared backend for
multiple containers.

## Host-owned SDK

An application that already owns OpenTelemetry can pass its providers. Praval
uses them without replacing global providers and does not shut them down.

```python
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider

from praval.observability import configure_observability

handle = configure_observability(
    service_name="host-owned-demo",
    tracer_provider=TracerProvider(shutdown_on_exit=False),
    meter_provider=MeterProvider(shutdown_on_exit=False),
    logger_provider=LoggerProvider(shutdown_on_exit=False),
)
assert handle.owned_signals == set()
```

Configure processors and readers on those providers in the host application.
A Praval OTLP endpoint cannot be attached to a host-owned meter provider because
the OpenTelemetry SDK requires metric readers at provider construction time.

## Praval-owned SDK

Point all three signals at a local Collector:

```python
from praval.observability import configure_observability, shutdown_observability

handle = configure_observability(
    service_name="orders-agent",
    service_version="0.8.3",
    deployment_environment="development",
    otlp_endpoint="http://127.0.0.1:4318",
    otlp_protocol="http/protobuf",
)
assert handle.owned_signals == {"traces", "metrics", "logs"}

try:
    # Run the application.
    pass
finally:
    shutdown_observability(5_000)
```

For gRPC use `otlp_protocol="grpc"` and an endpoint such as
`127.0.0.1:4317`. See [Collectors and deployment](collectors.md).
