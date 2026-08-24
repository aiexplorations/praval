"""Evaluate one correlated workflow observation with aggregated facts."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from praval.eval import (
    EvalRunner,
    SQLiteEvaluationStore,
    TargetResult,
    TerminalSuccessMetric,
    ToolCallMatchMetric,
    load_jsonl_suite,
)
from praval.models import (
    ExecutionObservation,
    ObservationFactStatus,
    ObservationKind,
    ObservationStatus,
    ReefHandoffObservation,
    ToolCallObservation,
)


class WorkflowTarget:
    """Return one workflow subject containing tool and handoff facts."""

    async def evaluate(self, case):
        now = datetime.now(timezone.utc)
        observation = ExecutionObservation(
            observation_id=f"workflow-observation-{case.case.case_id}",
            run_id=f"workflow-run-{case.case.case_id}",
            kind=ObservationKind.WORKFLOW,
            workflow_id="research-workflow-v1",
            workflow_name="research-workflow",
            started_at=now,
            ended_at=now + timedelta(milliseconds=12),
            duration_ms=12,
            status=ObservationStatus.OK,
            terminal_outcome="completed",
            tool_calls=(
                ToolCallObservation(
                    tool_call_id="tool-1",
                    name="policy_lookup",
                    status=ObservationFactStatus.OK,
                    duration_ms=2,
                ),
            ),
            handoffs=(
                ReefHandoffObservation(
                    handoff_id="handoff-1",
                    source_agent_id="researcher",
                    target_agent_id="reviewer",
                    spore_id="spore-1",
                    channel="review",
                    status=ObservationFactStatus.OK,
                    duration_ms=1,
                ),
            ),
            trace_id="1" * 32,
            span_id="2" * 16,
        )
        return TargetResult(
            observation=observation,
            output={"answer": "Paris", "reviewed": True},
        )


async def run(db_path: Path) -> dict[str, object]:
    dataset = Path(__file__).with_name("data") / "workflow.jsonl"
    suite = load_jsonl_suite(
        dataset,
        suite_id="workflow-quality-v1",
        name="Workflow quality",
        target="workflow:research-workflow",
        metrics=("terminal_success", "tool_call_match"),
    )
    store = SQLiteEvaluationStore(db_path)
    await store.migrate()
    try:
        result = await EvalRunner(
            store=store,
            target=WorkflowTarget(),
            judges={},
            metrics={
                "terminal_success": TerminalSuccessMetric(),
                "tool_call_match": ToolCallMatchMetric(),
            },
        ).run(suite, evaluation_run_id=f"workflow-{uuid.uuid4()}")
        subjects = await store.list_subjects(evaluation_run_id=result.evaluation_run_id)
        metrics = await store.list_metric_results(
            evaluation_run_id=result.evaluation_run_id
        )
        observation = subjects[0].observation
        return {
            "run_status": result.status.value,
            "passed_cases": result.passed_cases,
            "subject_count": len(subjects),
            "subject_kind": observation.kind.value,
            "tool_facts": len(observation.tool_calls),
            "handoff_facts": len(observation.handoffs),
            "metric_statuses": {
                metric.metric: metric.status.value for metric in metrics
            },
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
