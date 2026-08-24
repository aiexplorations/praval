"""SQLite implementation of the shared async evaluation-store contract."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from pydantic import ValidationError

from praval.eval import (
    AttemptStatus,
    EvalCase,
    EvalSuite,
    EvaluationAttempt,
    EvaluationBaseline,
    EvaluationConflictError,
    EvaluationJob,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
    EvaluationSubject,
    Gate,
    GateAggregation,
    GateOperator,
    GateResult,
    GateStatus,
    JobStatus,
    JudgeResult,
    MetricResult,
    ResultStatus,
    SQLiteEvaluationStore,
)
from praval.models import (
    ContentKind,
    ContentReference,
    ExecutionObservation,
    ObservationKind,
    ObservationStatus,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def _records() -> dict[str, object]:
    prompt = ContentReference(kind=ContentKind.PROMPT, sha256="a" * 64, size_bytes=8)
    case = EvalCase(case_id="case-1", name="Case one", input=prompt)
    gate = Gate(
        gate_id="quality",
        metric="correctness",
        aggregation=GateAggregation.MEAN,
        operator=GateOperator.GREATER_THAN_OR_EQUAL,
        threshold=0.8,
    )
    suite = EvalSuite(
        suite_id="suite-1",
        name="Suite one",
        target="researcher",
        case_ids=(case.case_id,),
        metrics=("correctness",),
        gates=(gate,),
    )
    run = EvaluationRun(
        evaluation_run_id="eval-run-1",
        suite_id=suite.suite_id,
        target=suite.target,
        status=EvaluationRunStatus.RUNNING,
        started_at=NOW,
    )
    observation = ExecutionObservation(
        observation_id="obs-1",
        run_id="execution-1",
        kind=ObservationKind.AGENT,
        agent_name="researcher",
        response_id="response-1",
        started_at=NOW,
        ended_at=NOW + timedelta(milliseconds=20),
        duration_ms=20,
        status=ObservationStatus.OK,
    )
    subject = EvaluationSubject.from_observation(
        evaluation_run_id=run.evaluation_run_id,
        case_id=case.case_id,
        observation=observation,
    )
    metric = MetricResult.create(
        evaluation_run_id=run.evaluation_run_id,
        case_id=case.case_id,
        subject_id=subject.subject_id,
        metric="correctness",
        metric_version="1",
        status=ResultStatus.PASSED,
        score=0.9,
        created_at=NOW,
    )
    judge = JudgeResult.create(
        evaluation_run_id=run.evaluation_run_id,
        case_id=case.case_id,
        subject_id=subject.subject_id,
        judge="judge-1",
        judge_version="1",
        prompt_sha256="b" * 64,
        rubric_version="1",
        status=ResultStatus.PASSED,
        score=0.9,
        label="pass",
        created_at=NOW,
    )
    gate_result = GateResult.create(
        evaluation_run_id=run.evaluation_run_id,
        gate_id=gate.gate_id,
        metric=gate.metric,
        status=GateStatus.PASSED,
        observed_value=0.9,
        threshold=gate.threshold,
        created_at=NOW,
    )
    result = EvaluationResult(
        evaluation_run_id=run.evaluation_run_id,
        status=EvaluationRunStatus.COMPLETED,
        total_cases=1,
        passed_cases=1,
        failed_cases=0,
        metric_result_ids=(metric.metric_result_id,),
        judge_result_ids=(judge.judge_result_id,),
        gate_result_ids=(gate_result.gate_result_id,),
        completed_at=NOW + timedelta(seconds=1),
    )
    baseline = EvaluationBaseline.create(
        suite_id=suite.suite_id,
        source_evaluation_run_id=run.evaluation_run_id,
        promoted_at=NOW + timedelta(seconds=2),
        promoted_by="maintainer",
    )
    job = EvaluationJob(
        job_id="job-1",
        evaluation_run_id=run.evaluation_run_id,
        suite_id=suite.suite_id,
        case_id=case.case_id,
        subject_id=subject.subject_id,
        status=JobStatus.PENDING,
        available_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    attempt = EvaluationAttempt(
        attempt_id="attempt-1",
        job_id=job.job_id,
        attempt_number=1,
        status=AttemptStatus.SUCCEEDED,
        started_at=NOW,
        ended_at=NOW + timedelta(milliseconds=5),
        duration_ms=5,
    )
    return {
        "case": case,
        "suite": suite,
        "run": run,
        "subject": subject,
        "metric": metric,
        "judge": judge,
        "gate_result": gate_result,
        "result": result,
        "baseline": baseline,
        "job": job,
        "attempt": attempt,
    }


@pytest_asyncio.fixture
async def store(tmp_path):
    value = SQLiteEvaluationStore(tmp_path / "evaluation.db")
    await value.migrate()
    yield value
    await value.close()


@pytest.mark.asyncio
async def test_migrations_are_idempotent_and_versioned(tmp_path) -> None:
    store = SQLiteEvaluationStore(tmp_path / "evaluation.db")

    await asyncio.gather(store.migrate(), store.migrate(), store.migrate())

    assert await store.schema_version() == 1
    await store.close()


@pytest.mark.asyncio
async def test_all_e1_records_round_trip(store: SQLiteEvaluationStore) -> None:
    records = _records()

    assert await store.put_case(records["case"]) == records["case"]
    assert await store.put_suite(records["suite"]) == records["suite"]
    assert await store.put_run(records["run"]) == records["run"]
    assert await store.put_subject(records["subject"]) == records["subject"]
    assert await store.put_metric_result(records["metric"]) == records["metric"]
    assert await store.put_judge_result(records["judge"]) == records["judge"]
    assert await store.put_gate_result(records["gate_result"]) == records["gate_result"]
    assert await store.put_evaluation_result(records["result"]) == records["result"]
    assert await store.promote_baseline(records["baseline"]) == records["baseline"]
    assert await store.put_job(records["job"]) == records["job"]
    assert await store.put_attempt(records["attempt"]) == records["attempt"]

    assert await store.get_case("case-1") == records["case"]
    assert await store.get_suite("suite-1") == records["suite"]
    assert await store.get_run("eval-run-1") == records["run"]
    assert await store.get_subject(records["subject"].subject_id) == records["subject"]
    assert await store.get_evaluation_result("eval-run-1") == records["result"]
    assert await store.get_active_baseline("suite-1") == records["baseline"]
    assert await store.get_job("job-1") == records["job"]


@pytest.mark.asyncio
async def test_query_filters_return_only_matching_records(
    store: SQLiteEvaluationStore,
) -> None:
    records = _records()
    await store.put_case(records["case"])
    await store.put_suite(records["suite"])
    await store.put_run(records["run"])
    await store.put_subject(records["subject"])
    await store.put_metric_result(records["metric"])
    await store.put_judge_result(records["judge"])
    await store.put_gate_result(records["gate_result"])
    await store.put_job(records["job"])
    await store.put_attempt(records["attempt"])

    assert await store.list_runs(suite_id="suite-1") == [records["run"]]
    assert await store.list_runs(suite_id="missing") == []
    assert await store.list_subjects(evaluation_run_id="eval-run-1") == [
        records["subject"]
    ]
    assert await store.list_metric_results(
        evaluation_run_id="eval-run-1", metric="correctness"
    ) == [records["metric"]]
    assert await store.list_judge_results(evaluation_run_id="eval-run-1") == [
        records["judge"]
    ]
    assert await store.list_gate_results(evaluation_run_id="eval-run-1") == [
        records["gate_result"]
    ]
    assert await store.list_jobs(status=JobStatus.PENDING) == [records["job"]]
    assert await store.list_attempts(job_id="job-1") == [records["attempt"]]


@pytest.mark.asyncio
async def test_duplicate_result_is_idempotent_but_conflict_is_rejected(
    store: SQLiteEvaluationStore,
) -> None:
    metric = _records()["metric"]

    first, second = await asyncio.gather(
        store.put_metric_result(metric), store.put_metric_result(metric)
    )
    assert first == second == metric

    changed = metric.model_copy(update={"score": 0.1})
    with pytest.raises(EvaluationConflictError, match="metric result"):
        await store.put_metric_result(changed)


@pytest.mark.asyncio
async def test_concurrent_distinct_writes_are_not_lost(
    store: SQLiteEvaluationStore,
) -> None:
    base = _records()["case"]
    cases = [
        base.model_copy(update={"case_id": f"case-{index}", "name": f"Case {index}"})
        for index in range(25)
    ]

    await asyncio.gather(*(store.put_case(case) for case in cases))

    assert {case.case_id for case in await store.list_cases(limit=100)} == {
        case.case_id for case in cases
    }


@pytest.mark.asyncio
async def test_baseline_changes_only_through_explicit_promotion(
    store: SQLiteEvaluationStore,
) -> None:
    first = _records()["baseline"]
    second = EvaluationBaseline.create(
        suite_id="suite-1",
        source_evaluation_run_id="eval-run-2",
        promoted_at=NOW + timedelta(seconds=3),
        promoted_by="maintainer",
    )

    await store.promote_baseline(first)
    assert await store.get_active_baseline("suite-1") == first
    await store.promote_baseline(second)

    assert await store.get_active_baseline("suite-1") == second
    baselines = await store.list_baselines(suite_id="suite-1")
    assert [baseline.active for baseline in baselines] == [True, False]


@pytest.mark.asyncio
async def test_attempt_number_is_idempotent_per_job(
    store: SQLiteEvaluationStore,
) -> None:
    attempt = _records()["attempt"]
    await store.put_attempt(attempt)

    conflicting = attempt.model_copy(update={"attempt_id": "different-id"})
    with pytest.raises(EvaluationConflictError, match="attempt number"):
        await store.put_attempt(conflicting)


def test_models_still_validate_data_loaded_from_store() -> None:
    """Guard against tests bypassing model validation with ``model_construct``."""
    with pytest.raises(ValidationError):
        EvaluationRun.model_validate(
            {
                "evaluation_run_id": "run",
                "suite_id": "suite",
                "target": "agent",
                "status": "completed",
                "started_at": NOW,
            }
        )
