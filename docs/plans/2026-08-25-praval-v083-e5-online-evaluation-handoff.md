# v0.8.3 E5 sampled-online-evaluation handoff

E5 adds opt-in sampled online evaluation with a bounded request-path handoff,
durable jobs, and post-hoc observability. It does not authorize a v0.8.3
release. E6 documentation and certification, documentation-site publication,
and every combined observability and evaluation release gate remain required.

## Delivered contracts

### Request-path isolation

- Online evaluation is disabled by default and starts no tasks or storage when
  disabled.
- Sampling is deterministic for a 128-bit trace ID. One trace is either
  selected or skipped consistently.
- The observation recorder performs target matching, sampling, bounded JSON
  sizing, and a non-blocking bounded queue insertion only. It performs no
  storage operation and invokes no judge, metric, model, or network provider.
- Queue saturation, invalid trace IDs, oversized subjects, persistence loss,
  and retry saturation are counted and exposed without retaining candidate
  content or exception messages.
- Recursive judge activity is excluded with the evaluation-call context
  marker.

### Durable delivery and lifecycle

- `EvaluationJob` and `EvaluationAttempt` have stable natural identities.
- SQLite and PostgreSQL implement the same atomic job contract for creation,
  leasing, expired-lease recovery, completion, retry, and dead-lettering.
- PostgreSQL leasing uses `FOR UPDATE SKIP LOCKED`; duplicate delivery does not
  revert a completed or failed lifecycle.
- Enqueue persistence and processor retries are bounded. Processor timeouts,
  missing subjects, cancellation, retry exhaustion, and shutdown are recorded
  as bounded attempts or terminal job state.
- Explicit service start and shutdown own all scheduler and worker tasks. A
  bounded shutdown releases interrupted leases for later process recovery.

### Evaluator composition and telemetry

- `OnlineSubjectEvaluator` composes the same public asynchronous judges and
  metric plugins used offline. Candidate content is resolved by an application
  context loader only inside the worker.
- Context and result identities are validated before results are accepted.
  Metric exceptions become bounded `MetricResult` errors; raw exception text
  is not persisted.
- A completed online job produces the same immutable judge, metric, attempt,
  run, and terminal summary records as offline evaluation.
- Worker spans are linked post hoc to the original execution span rather than
  parented beneath an already-completed request.
- Metadata-only scheduled, dropped, retry, failure, completion, duration, queue
  depth, result-count, and score signals are emitted through the existing
  OpenTelemetry foundation. Export failure cannot fail evaluation processing.
- `praval.observability` does not import `praval.eval`, and the evaluation
  package does not import the OpenTelemetry SDK.

## Checkpoint evidence

Local results on 2026-08-25:

- Focused online, evaluation, configuration, and signal suite: 207 passed and
  2 expected trace-environment skips.
- New online scheduler/worker module coverage: 96 percent. New post-hoc
  evaluation telemetry module coverage: 96 percent.
- Complete direct suite excluding the separately run database fixture: 2,113
  passed and 132 skipped.
- Real Docker-backed PostgreSQL 15 evaluation-store, leasing, recovery, and
  outage contract: 10 of 10 passed.
- The request scheduling regression test enqueues 300 observations and keeps
  p95 latency below 2 milliseconds while processor work is blocked.
- Queue saturation, worker restart, PostgreSQL downtime, duplicate delivery,
  timeout, retry exhaustion, missing subject, telemetry failure, and bounded
  shutdown tests pass.
- Black, isort, focused flake8, strict mypy across 20 source files, API-surface
  documentation contracts, and the eval-to-OpenTelemetry layering contract
  pass.

## Commands

```bash
pytest -q tests/eval/test_online.py
pytest -q tests/eval tests/observability/test_signals.py \
  tests/test_praval_config_edges.py \
  --ignore=tests/eval/test_postgres_store.py \
  --cov=praval.eval.online \
  --cov=praval.observability.evaluation \
  --cov-report=term-missing
pytest -q tests --ignore=tests/eval/test_postgres_store.py
pytest -q tests/eval/test_postgres_store.py
mypy src/praval/config.py src/praval/eval \
  src/praval/observability/evaluation.py \
  src/praval/observability/signals.py --disallow-untyped-defs
```

## E6 starting boundary

E6 must document and execute the complete evaluator-agent, local, CI,
PostgreSQL, workflow, RAGAS, online, privacy, cost, failure, and observability
correlation paths. The recommended patterns must preserve one immutable
observation with aggregated facts per evaluated agent or workflow. E6 must
also update the API manifest, installation scopes, doctor checks, release
notes, migration guide, exact-wheel examples, and the separately published
`praval-ai` documentation site. No release or push is authorized until all
observability and evaluation gates pass together.
