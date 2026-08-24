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

from .store_contract import (
    assert_all_records_round_trip,
    assert_attempt_idempotency,
    assert_concurrent_writes,
    assert_explicit_baseline_promotion,
    assert_query_filters,
    assert_result_idempotency,
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
    await assert_all_records_round_trip(store, _records())


@pytest.mark.asyncio
async def test_query_filters_return_only_matching_records(
    store: SQLiteEvaluationStore,
) -> None:
    await assert_query_filters(store, _records())


@pytest.mark.asyncio
async def test_duplicate_result_is_idempotent_but_conflict_is_rejected(
    store: SQLiteEvaluationStore,
) -> None:
    await assert_result_idempotency(store, _records())


@pytest.mark.asyncio
async def test_concurrent_distinct_writes_are_not_lost(
    store: SQLiteEvaluationStore,
) -> None:
    await assert_concurrent_writes(store, _records())


@pytest.mark.asyncio
async def test_baseline_changes_only_through_explicit_promotion(
    store: SQLiteEvaluationStore,
) -> None:
    await assert_explicit_baseline_promotion(store, _records())


@pytest.mark.asyncio
async def test_attempt_number_is_idempotent_per_job(
    store: SQLiteEvaluationStore,
) -> None:
    await assert_attempt_idempotency(store, _records())


@pytest.mark.asyncio
async def test_terminal_result_and_attempt_conflicts_are_rejected(
    store: SQLiteEvaluationStore,
) -> None:
    records = _records()
    result = records["result"]
    attempt = records["attempt"]
    await store.put_evaluation_result(result)
    await store.put_attempt(attempt)

    with pytest.raises(EvaluationConflictError, match="evaluation result"):
        await store.put_evaluation_result(
            result.model_copy(update={"metric_result_ids": ("different",)})
        )
    with pytest.raises(EvaluationConflictError, match="attempt identity"):
        await store.put_attempt(attempt.model_copy(update={"duration_ms": 6}))


@pytest.mark.asyncio
async def test_store_rejects_invalid_configuration_and_inactive_promotion(
    store: SQLiteEvaluationStore,
) -> None:
    with pytest.raises(ValueError, match="busy_timeout_ms"):
        SQLiteEvaluationStore(":memory:", busy_timeout_ms=0)

    inactive = _records()["baseline"].model_copy(update={"active": False})
    with pytest.raises(ValueError, match="must be active"):
        await store.promote_baseline(inactive)


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
