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

| Instrument | Unit | Use |
|---|---|---|
| `praval.execution.invocations` | invocation | completed agent/workflow count |
| `praval.execution.duration` | ms | end-to-end target latency |
| `praval.execution.failures` | failure | non-successful terminal outcomes |
| `praval.gen_ai.token.usage` | token | input/output/total token types |
| `praval.tool.invocations` | invocation | bounded tool status count |
| `praval.tool.duration` | ms | tool latency distribution |
| `praval.retry.count` | retry | retry decisions by operation |
| `praval.reef.handoff.count` | handoff | inter-agent delivery outcomes |
| `praval.reef.handoff.duration` | ms | handoff latency distribution |
| `praval.evaluation.results` | result | judge and metric outcomes |
| `praval.evaluation.score` | 1 | finite normalized score distribution |
| `praval.evaluation.failures` | failure | errored judge/metric results |

Health instruments are `praval.telemetry.export.attempts`,
`praval.telemetry.exported.items`, `praval.telemetry.export.failures`,
`praval.telemetry.export.exceptions`, `praval.telemetry.dropped.items`,
`praval.telemetry.lifecycle.failures`, `praval.telemetry.queue.depth`, and
`praval.telemetry.queue.capacity`, separated by signal.

## Logs

Praval emits a correlated completion log for each observation through the
OpenTelemetry logger provider. Application logs remain application-owned.
Praval neither installs a standard-library logging handler nor captures
arbitrary application messages.

Trace, metric, and log export failures are isolated from the agent request path
and recorded in bounded health state. They do not include payloads or secrets.

## Attribute policy

Stable low-cardinality dimensions include observation kind/status, agent or
workflow name, provider, model, request mode, token type, tool name/status,
operation, handoff status, evaluator name/version, and structured error type.
Run, case, subject, observation, response, trace, and span IDs belong on spans
and log events for correlation; do not group metrics by them in backend
dashboards.

## Backend queries

Backend syntax differs, but the questions should remain portable:

- execution failure ratio: failures divided by invocations, grouped by service
  and agent/workflow;
- p95 duration: the execution-duration histogram by target and status;
- exporter loss: rate of dropped items and export failures by signal;
- tool regression: tool error count and duration by bounded tool name;
- evaluation drift: score distribution and result status by evaluator version.

For Prometheus-compatible backends, prefer `rate()` over counters and
`histogram_quantile()` over the exported histogram buckets. Keep service name
and deployment environment in the OpenTelemetry resource rather than copying
them into every custom application attribute.
