# Migrate from v0.8.2 to v0.8.3

v0.8.3 adds an explicit OpenTelemetry foundation and a provider-neutral
evaluation system. Agent, ModelRuntime, Reef, Spore, tool, storage, memory,
HITL, and MCP application contracts remain compatible unless noted here.

## Runtime support

Python 3.9 support ends with v0.8.2. v0.8.3 supports Python 3.10 through 3.14.
Upgrade the application interpreter and rebuild environments before installing
the wheel. The MCP extra no longer needs a separate Python-version caveat.

## Observability

Observability is disabled by default. Importing Praval no longer implies a
local trace database or SDK lifecycle.

1. Install `praval[observability]` only when Praval should construct SDK
   providers and OTLP exporters.
2. Call `configure_observability()` once at process startup.
3. Give each deployable service a stable name and send OTLP to a Collector.
4. Enable local SQLite explicitly for single-process diagnosis only.
5. Call bounded `force_flush()`/`shutdown_observability()` during graceful
   termination.

The old flat `sample_rate`, `otlp_endpoint`, and `storage_path` inputs map to
`sample_ratio`, `otlp`, and `local` with deprecation warnings. Compatibility
`Tracer`, local viewer, and export helpers remain, but new code should use the
official APIs described in {doc}`../observability/api-migration`.

Do not move prompts, responses, tool payloads, or exception messages into span
or metric attributes. The default `ExecutionObservation` is metadata-only and
aggregates bounded facts into one record per agent/workflow.

## Evaluation

Evaluation is additive and disabled until configured or explicitly constructed.
Core datasets, SQLite, deterministic metrics, judges, runners, gates, baselines,
CLI, and online contracts are in the base wheel. Install `eval-ragas` only for
the optional RAGAS adapter and `storage` for shared PostgreSQL deployments.

Start with an offline deterministic suite:

```bash
praval eval run <suite> --module <agent-registration-module> --json
```

Targets must be registered as `agent:<name>` for the v0.8.3 CLI.
`AgentEvaluationTarget` rejects persistent conversation state and requires one
agent observation per case. Model and agent judges use separate versioned
profiles and strict outputs. Baseline promotion is explicit.

Online evaluation remains disabled by default and requires PostgreSQL. It
samples by trace, enqueues bounded observations without storage/judge work on
the request path, and runs judges from explicitly owned durable workers.

## Configuration

The complete schema is version 1. Configuration precedence is defaults,
nearest/explicit `praval.toml`, supported environment variables, then explicit
API overrides. Unknown fields and bad cross-references now fail rather than
being ignored. Keep DSNs, provider keys, and OTLP headers in named environment
variables.

Run after migration:

```bash
praval doctor --json
```

The report includes core/SQLite evaluation availability plus installed
PostgreSQL, RAGAS, and OpenTelemetry components. It reports secret presence,
never secret values.

## Removed or nonexistent claims

v0.8.3 does not provide `praval.explainability`, `praval.security`, or a
`get_metrics()` convenience API. Use `praval.observability` for signals,
`praval.eval` for quality records/gates, and the existing secure Spore/transport
modules for message security.

## Validation checklist

- Run application tests on Python 3.10 through 3.14.
- Run `praval doctor --json` and check optional extras.
- Execute observability quickstarts against a Collector and bounded shutdown.
- Run offline suites from the exact wheel; explicitly promote an approved
  baseline and verify CI exit codes.
- Validate privacy with content capture off.
- If using online eval, test saturation, database outage, restart, duplicate
  delivery, timeout, dead letter, and shutdown before enabling sampling.

See {doc}`../evaluation/index` and {doc}`../observability/index` for complete
operational guidance.
