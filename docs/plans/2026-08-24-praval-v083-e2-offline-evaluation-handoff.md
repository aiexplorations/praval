# v0.8.3 E2 offline-evaluation handoff

E2 implements the bounded offline runner, direct-model and ordinary-agent
judges, and evaluation-result correlation. It does not authorize a v0.8.3
release. E3 through E6 and the combined release gates remain required.

## Delivered contracts

### Offline execution

- `EvalRunner` validates configured judges before execution, runs selected JSONL
  cases with bounded concurrency, persists every subject and result, aggregates
  case status, and records a terminal run summary.
- Agent and workflow targets return exactly one immutable
  `ExecutionObservation`. Workflow observations retain tool and Reef handoff
  facts as bounded aggregates rather than creating one observation per fact.
- Result identity is validated against the evaluation run, case, subject, and
  configured evaluator before persistence.
- Target and identity failures mark the run failed without persisting private
  exception messages. Cancellation remains cancellation and is never converted
  into an ordinary judge result.

### Judges

- `ModelJudge` resolves a validated model profile, forces temperature zero,
  disables hidden runtime retries, and uses strict structured output.
- `AgentJudge` resolves an ordinary registered Praval agent and invokes its
  normal async runtime. It narrows tools to the judge allowlist, rejects tools
  that are not read-only or `evaluation_safe`, bounds tool rounds, restores
  ephemeral conversation history, and rejects persistent evaluator history.
- Both judges separate the trusted versioned rubric from untrusted candidate
  content, hash the exact prompt deterministically, reject malformed or
  non-finite output, and return metadata-only `JudgeResult` records.
- Attempts, timeouts, token use, cost, and terminal error type are bounded and
  recorded. Aggregate input-token and cost budgets stop further judge work.
- Evaluation calls carry a context-local marker. Self-evaluation is rejected by
  default so online sampling cannot recursively evaluate judge calls.

### Observability correlation

- `emit_evaluation_result` is part of the public `praval.observability` facade.
  It is a no-op until observability is explicitly configured.
- After a judge record is persisted, `EvalRunner` passes that exact immutable
  record and its subject to the facade. Exporter failures are isolated from
  evaluation outcomes.
- The emitted `gen_ai.evaluation.result` event carries the standard evaluation
  name, score, label, error type, and response ID plus the Praval evaluation
  run, case, subject, and observation IDs. Identity drift is rejected.
- Explanations remain absent under metadata-only privacy and are emitted only
  when content capture was explicitly authorized.

## Public API added in E2

`praval.eval` now exports:

- `ModelJudge`, `AgentJudge`
- `JudgeConfigurationError`, `JudgeResponseError`
- `evaluation_call_scope`, `is_evaluation_call`

`praval.observability` now exports:

- `emit_evaluation_result`
- `is_observability_configured`

## Checkpoint evidence

Local results on 2026-08-24:

- Judge, runner, evaluation-signal, and public-manifest focus: 52 passed.
- Complete evaluation suite under coverage: 89 passed and 7 PostgreSQL tests
  skipped while tracing; E2 judge modules are 99 percent covered, runner 100
  percent, context 100 percent, and SQLite 97 percent.
- Real PostgreSQL store contract without coverage tracing: 7 of 7 passed through
  a Docker-backed PostgreSQL 15 fixture.
- Complete observability suite: 182 passed.
- Evaluation signal module: 98 percent line coverage.
- Agent/runtime/evaluation/observation regression selection excluding the
  separately certified Docker fixture: 212 passed.
- Black, isort, focused flake8, and strict mypy checks pass.

## Commands

```bash
pytest tests/eval -q --cov=praval.eval --cov-report=term-missing
pytest tests/eval/test_postgres_store.py -q
pytest tests/observability -q
pytest tests/eval/test_judges.py tests/eval/test_runner.py \
  tests/observability/test_signals.py \
  tests/observability/test_observability_documentation_contracts.py -q
mypy src/praval/eval/context.py src/praval/eval/judges.py \
  src/praval/eval/runner.py src/praval/observability/lifecycle.py \
  src/praval/observability/signals.py src/praval/core/agent.py
```

## E3 starting boundary

E3 may add deterministic metric execution, workflow-specific selectors, gate
aggregations and thresholds, explicit baseline comparison and promotion, and
the `praval eval` CLI. It must preserve E1 record identities, the frozen
`ExecutionObservation` schema, metadata-only defaults, ordinary-agent evaluator
semantics, and exact persisted-to-emitted correlation. Automatic baseline
promotion remains forbidden.
