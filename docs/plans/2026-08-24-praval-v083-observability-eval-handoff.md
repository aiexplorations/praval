# v0.8.3 observability-to-evaluation handoff

This handoff is the fresh-context boundary between O6 and E1. Evaluation must
consume the provider-neutral observation contract and must not read an
OpenTelemetry backend or import OpenTelemetry SDK internals.

## Frozen contracts

- Model: `praval.models.ExecutionObservation`
- Recorder protocol: `praval.models.ObservationRecorder`
- Schema version: `1`
- Machine-checked inventory: `docs/observation-contract.toml`
- Runtime facade: `praval.observability.configure_observation_recorder()`,
  `use_observation_recorder()`, and `CompositeObservationRecorder`
- Granularity: one completed observation per agent or workflow, with bounded
  facts aggregated inside it

Changing a required field, meaning, enum value, bound, or recorder behavior is
not permitted during E1 through E6. If evaluation exposes a missing fact, add
an optional field with an observability compatibility test before consuming it.

## Supported observation fields

Identity and correlation:

- `observation_id`, `run_id`, `kind`
- `conversation_id`, `response_id`
- `agent_id`, `agent_name`, `workflow_id`, `workflow_name`
- optional W3C-derived `trace_id` and `span_id`, which must appear together

Outcome and timing:

- UTC `started_at`, `ended_at`, and non-negative `duration_ms`
- `status`, structured `error_type`, and `terminal_outcome`

Execution facts:

- `provider`, `model`, and `request_mode`
- aggregate `TokenUsageObservation`
- bounded tuples of `ToolCallObservation`, `RetryObservation`,
  `HITLDecisionObservation`, and `ReefHandoffObservation`
- bounded `ContentReference` values and one `ObservationPrivacy` policy

Raw prompts, responses, contexts, tool payloads, retrieved documents, media,
judge evidence, exception messages, and stack traces are not observation
fields. Evaluation records may resolve content references only under their own
explicit privacy and access policy.

## Fixtures and executable examples

- Complete JSON round trip and validation: `tests/test_execution_observation.py`
- Agent/workflow aggregation and recorder isolation:
  `tests/observability/test_runtime_observation.py`
- Tool and HITL fact sources:
  `tests/observability/test_runtime_fact_sources.py`
- Reef handoff aggregation and W3C propagation:
  `tests/observability/test_spore_propagation.py`
- Metrics/log derivation: `tests/observability/test_signals.py`
- Exact public and documentation surface:
  `tests/observability/test_observability_documentation_contracts.py`

E1 store contract fixtures should build `ExecutionObservation` directly from
these public models and round-trip `model_dump(mode="json")` data. Do not use
private `_ObservationState`, span objects, exporter records, or SQLite trace
rows as evaluation inputs.

## Recorder semantics

`ObservationRecorder.record()` is synchronous and must return quickly. Runtime
code isolates recorder exceptions so a consumer cannot fail an agent request.
`CompositeObservationRecorder` fans out independently. The process-default
recorder can be replaced, while `use_observation_recorder()` applies to the
current synchronous or asynchronous context. Online evaluation must enqueue
bounded work in `record()` and perform no judge network call there.

## Known limitations

- The schema records structured metadata and content references, not complete
  execution transcripts.
- Fact tuple bounds intentionally truncate unbounded histories.
- Trace correlation is absent when no recording span exists.
- SQLite telemetry is local diagnostics and is not an evaluation store.
- Application logs are not captured by Praval.
- Evaluation-specific runs, cases, metrics, judges, gates, baselines, jobs, and
  attempts do not exist yet; E1 owns those contracts.

## Checkpoint commands

Run from the repository root with the development environment active:

```bash
pytest tests/test_execution_observation.py \
  tests/observability/test_runtime_observation.py \
  tests/observability/test_runtime_fact_sources.py \
  tests/observability/test_spore_propagation.py \
  tests/observability/test_signals.py -v
pytest tests/observability/test_observability_documentation_contracts.py -v
PRAVAL_DOCS_OFFLINE=1 sphinx-build -b html -W --keep-going \
  docs/sphinx /tmp/praval-v083-observability-docs
./scripts/run_otel_collector_tests.sh
pytest tests/integration/test_rabbitmq_trace_propagation.py -v
PRAVAL_RUN_PERFORMANCE_TESTS=1 \
  pytest tests/performance/test_observability_overhead.py -v
make test-cov
make lint
make type-check
```

The exact-wheel smoke must additionally run
`python scripts/smoke_install.py dist --extra observability`. O6 is complete
only after that wheel, the real Collector, RabbitMQ, documentation, privacy,
failure, shutdown, performance, coverage, lint, and type gates pass. Passing
O6 authorizes E1 development; it does not authorize a v0.8.3 release.

## O6 checkpoint result

O6 passed locally on 2026-08-24. The certified candidate artifact is
`praval-0.8.3-py3-none-any.whl` with SHA-256
`10360905c355ac20a6bfde5d5554dfb417babb107565142f87daf55de61eb67f`.

- The full suite passed with 1,913 tests, 132 skips, and 93.20 percent total
  coverage.
- Black, isort, flake8, and mypy checks passed for the supported local Python
  environments.
- Real OpenTelemetry Collector HTTP and gRPC tests, RabbitMQ propagation, and
  observability performance gates passed.
- Minimal and `observability` clean-environment smoke tests passed against the
  exact wheel.
- The exact-wheel Sphinx build completed without warnings and recorded the
  same wheel hash in its documentation manifest.

This result opens E1 implementation locally. Evaluation work remains
unreleased until E1 through E6 and the combined release gates pass.
