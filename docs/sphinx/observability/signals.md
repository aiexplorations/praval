# Traces, metrics, and logs

## Traces

Agent and workflow root spans carry stable identity and terminal status.
Producer, delivery, and consumer spans reveal Reef transit. Tool, retry, HITL,
usage, and handoff facts remain bounded on the completed observation.

## Metrics

Praval derives metrics from the same observation: execution invocation,
duration, failure, token usage, tool invocation and duration, retry count, and
Reef handoff count and duration. Dimensions are bounded to low-cardinality
status, kind, agent or workflow name, provider, model, request mode, token type,
tool name, and structured error type.

Pipeline health exposes export attempts, exported items, failures, exceptions,
drops, queue depth and capacity, and lifecycle failures per signal. Inspect
these counters when a backend has gaps; they distinguish application absence
from exporter loss.

## Logs

Praval emits a correlated completion log for each observation through the
OpenTelemetry logger provider. Application logs remain application-owned.
Praval neither installs a standard-library logging handler nor captures
arbitrary application messages.

Trace, metric, and log export failures are isolated from the agent request path
and recorded in bounded health state. They do not include payloads or secrets.

