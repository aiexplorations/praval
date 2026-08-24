# v0.8.3 E1 evaluation-contract handoff

E1 defines the provider-neutral records and async persistence boundary consumed
by the offline runner in E2. It does not authorize a v0.8.3 release.

## Public contracts

`praval.eval` exports immutable, extra-forbidden, schema-versioned contracts
for:

- `EvalCase`, `EvalSuite`, `EvaluationRun`, `EvaluationResult`, and
  `EvaluationSubject`
- `MetricResult`, `JudgeResult`, `Gate`, and `GateResult`
- `EvaluationBaseline`, `EvaluationJob`, and `EvaluationAttempt`
- their lifecycle, result, gate, job, attempt, aggregation, and operator enums
- `EvaluationStore`, `SQLiteEvaluationStore`, and
  `PostgresEvaluationStore`

One `EvaluationSubject` contains exactly one frozen `ExecutionObservation`.
The observation remains one agent or workflow boundary with its bounded facts
aggregated inside it. The mapping duplicates only query identities and validates
that they cannot drift from the embedded observation.

Metric, judge, gate, baseline, and subject constructors derive deterministic
identities from their natural keys. Repeating the same immutable record is a
no-op; reusing an identity with different data raises
`EvaluationConflictError`.

## Privacy boundary

Cases contain `ContentReference` values instead of raw prompts, expected
outputs, or reference contexts. Judge evidence also uses content references.
Judge explanations are absent by default and require an explicit non-metadata
`ObservationPrivacy` policy with a positive byte limit.

Neither `praval.eval` nor its SQLite store imports the OpenTelemetry SDK. The
base evaluation package imports when `asyncpg` is absent. Constructing the
PostgreSQL store without the storage extra returns an actionable diagnostic.

## Store contract

Both stores implement the same async methods for migrations, cases, suites,
runs, subjects, metric results, judge results, gate results, terminal run
summaries, explicit baselines, durable jobs, and attempts.

- SQLite uses WAL-compatible short connections, a bounded busy timeout,
  transactional migrations and baseline promotion, and thread-isolated async
  calls for local development and CI.
- PostgreSQL uses an owned `asyncpg` pool, JSONB payloads, transaction-scoped
  advisory locks for concurrent migrations and baseline promotion, and indexed
  query columns for shared deployments.

The shared behavioral assertions exercise record round trips, filters,
concurrent writes, duplicate-result conflicts, explicit baseline promotion,
and attempt-number idempotency against both implementations.

## Checkpoint evidence

Local results on 2026-08-24:

- Full repository: 1,942 passed, 139 skipped, 92.66 percent coverage, with all
  release coverage floors passing.
- Evaluation models: 100 percent line coverage.
- SQLite evaluation store: 97 percent line coverage.
- Evaluation store protocol declarations: 100 percent line coverage.
- Real PostgreSQL contract: 7 of 7 tests passed on Python 3.13 with
  `asyncpg 0.31`.
- PostgreSQL evaluation store: 95.48 percent line coverage on Python 3.12 with
  supported `asyncpg 0.30`.
- Flake8 and strict mypy checks pass on Python 3.13 and Python 3.10.

`asyncpg 0.31` segfaults in its compiled connection setup when any coverage
tracer is active on this macOS environment. The same real-database suite is
stable without tracing, and the traced suite passes with supported
`asyncpg 0.30`. PostgreSQL tests therefore skip only when a trace function is
active; behavior and coverage are certified in separate runs.

## Commands

```bash
pytest tests/eval -m "not integration" -q
pytest tests/eval/test_postgres_store.py -v
pytest tests/eval/test_models.py tests/eval/test_sqlite_store.py \
  --cov=praval.eval.models --cov=praval.eval.sqlite \
  --cov=praval.eval.store --cov-report=term-missing
make test-cov
make lint
make type-check
```

E2 may add the offline runner, JSONL suites, agent and model judges, retries,
timeouts, usage and cost recording, and public observability correlation. It
must use these records and store methods without importing OpenTelemetry SDK
internals or changing the frozen `ExecutionObservation` contract.
