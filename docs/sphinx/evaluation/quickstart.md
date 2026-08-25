# Install and five-minute quickstart

## Install

Core evaluation contracts, deterministic metrics, SQLite storage, runners,
judges, gates, and the CLI are in the base package:

```bash
python -m pip install praval
```

Install optional integrations only when needed:

```bash
python -m pip install "praval[eval-ragas]"  # RAGAS 0.4 adapter
python -m pip install "praval[storage]"     # shared PostgreSQL deployments
```

## Define a dataset

Create `evals/answers.jsonl`:

```json
{"id":"capital-france","input":"Capital of France?","expected_output":"Paris","tags":["smoke"]}
```

The loader keeps the input and expected output only in the active
`LoadedEvalCase`. Persisted `EvalCase` records contain content references.

## Run one deterministic suite

```python
import asyncio
from datetime import datetime, timedelta, timezone

from praval.eval import (
    EvalRunner,
    ExactMatchMetric,
    Gate,
    SQLiteEvaluationStore,
    TargetResult,
    evaluate_gate,
    load_jsonl_suite,
)
from praval.models import ExecutionObservation, ObservationKind, ObservationStatus


class Target:
    async def evaluate(self, case):
        now = datetime.now(timezone.utc)
        return TargetResult(
            observation=ExecutionObservation(
                observation_id=f"observation-{case.case.case_id}",
                run_id=f"run-{case.case.case_id}",
                kind=ObservationKind.AGENT,
                agent_name="answerer",
                started_at=now,
                ended_at=now + timedelta(milliseconds=1),
                duration_ms=1,
                status=ObservationStatus.OK,
            ),
            output="Paris",
        )


async def main():
    gate = Gate(
        gate_id="exact-pass-rate",
        metric="exact_match",
        aggregation="pass_rate",
        operator=">=",
        threshold=1.0,
    )
    suite = load_jsonl_suite(
        "evals/answers.jsonl",
        suite_id="answers-v1",
        name="Answer quality",
        target="agent:answerer",
        metrics=("exact_match",),
        gates=(gate,),
    )
    store = SQLiteEvaluationStore(".praval/evaluations.db")
    await store.migrate()
    result = await EvalRunner(
        store=store,
        target=Target(),
        judges={},
        metrics={"exact_match": ExactMatchMetric()},
    ).run(suite, evaluation_run_id="local-smoke-1")
    metric_results = await store.list_metric_results(
        evaluation_run_id=result.evaluation_run_id
    )
    decision = evaluate_gate(gate, metric_results)
    print(result.status.value, decision.status.value)
    await store.close()


asyncio.run(main())
```

Expected output is `completed passed`. Reusing the same run ID with different
immutable data raises `EvaluationConflictError`; choose a new ID for a new run.

## CLI configuration

For a registered `Agent`, `praval eval run` builds the target, metrics, judges,
and gates from `praval.toml`:

```toml
schema_version = 1

[eval]
enabled = true
store = "sqlite"
offline_concurrency = 4

[eval.stores.sqlite]
path = ".praval/evaluations.db"

[eval.suites.answers]
dataset = "evals/answers.jsonl"
target = "agent:answerer"
metrics = ["exact_match"]

[[eval.suites.answers.gates]]
gate_id = "exact-pass-rate"
metric = "exact_match"
aggregation = "pass_rate"
operator = ">="
threshold = 1.0
```

Register the target agent from a module, then run:

```bash
praval eval run answers --module myapp.agents --json
```

Exit codes are 0 for success, 1 for a failed gate or regression, and 2 for
configuration, dataset, store, target, judge, or execution errors. Continue
with {doc}`patterns`, then {doc}`gates-ci` before adding a paid judge.
