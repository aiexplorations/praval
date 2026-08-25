"""Credential-free deterministic evaluation quickstart.

Run:
    python examples/evaluation/000_quickstart.py --db /tmp/praval-eval.db
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from praval.eval import (
    EvalRunner,
    ExactMatchMetric,
    Gate,
    SQLiteEvaluationStore,
    TargetResult,
    load_jsonl_suite,
)
from praval.models import ExecutionObservation, ObservationKind, ObservationStatus


class AnswerTarget:
    """Deterministic target standing in for an application agent."""

    async def evaluate(self, case):
        now = datetime.now(timezone.utc)
        return TargetResult(
            observation=ExecutionObservation(
                observation_id=f"observation-{case.case.case_id}",
                run_id=f"execution-{case.case.case_id}",
                kind=ObservationKind.AGENT,
                agent_name="answerer",
                started_at=now,
                ended_at=now + timedelta(milliseconds=1),
                duration_ms=1,
                status=ObservationStatus.OK,
            ),
            output={"answer": "Paris"},
        )


async def run(db_path: Path) -> dict[str, object]:
    dataset = Path(__file__).with_name("data") / "answers.jsonl"
    gate = Gate(
        gate_id="exact-pass-rate",
        metric="exact_match",
        aggregation="pass_rate",
        operator=">=",
        threshold=1.0,
    )
    suite = load_jsonl_suite(
        dataset,
        suite_id="answers-v1",
        name="Answer quality",
        target="agent:answerer",
        metrics=("exact_match",),
        gates=(gate,),
    )
    store = SQLiteEvaluationStore(db_path)
    await store.migrate()
    try:
        result = await EvalRunner(
            store=store,
            target=AnswerTarget(),
            judges={},
            metrics={"exact_match": ExactMatchMetric()},
        ).run(suite, evaluation_run_id=f"quickstart-{uuid.uuid4()}")
        gates = await store.list_gate_results(
            evaluation_run_id=result.evaluation_run_id
        )
        subjects = await store.list_subjects(evaluation_run_id=result.evaluation_run_id)
        return {
            "run_status": result.status.value,
            "passed_cases": result.passed_cases,
            "gate_status": gates[0].status.value,
            "subject_count": len(subjects),
            "observation_kind": subjects[0].kind.value,
        }
    finally:
        await store.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.db)), sort_keys=True))


if __name__ == "__main__":
    main()
