"""Contracts for provider-neutral evaluation records."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from praval.eval import (
    AttemptStatus,
    EvalCase,
    EvalSuite,
    EvaluationAttempt,
    EvaluationBaseline,
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
)
from praval.models import (
    ContentKind,
    ContentReference,
    ExecutionObservation,
    ObservationFactStatus,
    ObservationKind,
    ObservationStatus,
    ToolCallObservation,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def _reference(kind: ContentKind, digest: str = "a") -> ContentReference:
    return ContentReference(kind=kind, sha256=digest * 64, size_bytes=12)


def _observation(kind: ObservationKind = ObservationKind.AGENT) -> ExecutionObservation:
    identity = (
        {"agent_id": "agent-1", "agent_name": "researcher"}
        if kind is ObservationKind.AGENT
        else {"workflow_id": "workflow-1", "workflow_name": "research-flow"}
    )
    return ExecutionObservation(
        observation_id="obs-1",
        run_id="execution-1",
        kind=kind,
        response_id="response-1",
        started_at=NOW,
        ended_at=NOW + timedelta(milliseconds=25),
        duration_ms=25,
        status=ObservationStatus.OK,
        tool_calls=(
            ToolCallObservation(
                tool_call_id="tool-1",
                name="search",
                status=ObservationFactStatus.OK,
                duration_ms=4,
            ),
        ),
        content_references=(_reference(ContentKind.RESPONSE),),
        **identity,
    )


def test_case_and_suite_round_trip_without_raw_content() -> None:
    case = EvalCase(
        case_id="case-1",
        name="Answers from supplied evidence",
        input=_reference(ContentKind.PROMPT),
        expected_output=_reference(ContentKind.RESPONSE, "b"),
        reference_contexts=(_reference(ContentKind.CONTEXT, "c"),),
        expected_tool_calls=("search",),
        tags=("smoke",),
    )
    gate = Gate(
        gate_id="quality",
        metric="correctness",
        aggregation=GateAggregation.MEAN,
        operator=GateOperator.GREATER_THAN_OR_EQUAL,
        threshold=0.8,
    )
    suite = EvalSuite(
        suite_id="suite-1",
        name="Smoke suite",
        target="researcher",
        case_ids=(case.case_id,),
        judges=("quality-judge",),
        metrics=("correctness",),
        gates=(gate,),
    )

    assert EvalCase.model_validate_json(case.model_dump_json()) == case
    assert EvalSuite.model_validate_json(suite.model_dump_json()) == suite
    assert "prompt text" not in case.model_dump_json()


@pytest.mark.parametrize("kind", [ObservationKind.AGENT, ObservationKind.WORKFLOW])
def test_subject_maps_exactly_one_aggregated_observation(kind: ObservationKind) -> None:
    observation = _observation(kind)

    subject = EvaluationSubject.from_observation(
        evaluation_run_id="eval-run-1",
        case_id="case-1",
        observation=observation,
    )

    assert subject.observation == observation
    assert subject.observation_id == "obs-1"
    assert subject.execution_run_id == "execution-1"
    assert subject.kind.value == kind.value
    assert subject.response_id == "response-1"
    assert subject.observation.tool_calls[0].name == "search"
    assert EvaluationSubject.model_validate_json(subject.model_dump_json()) == subject


def test_subject_identity_is_deterministic_for_store_idempotency() -> None:
    first = EvaluationSubject.from_observation(
        evaluation_run_id="eval-run-1",
        case_id="case-1",
        observation=_observation(),
    )
    second = EvaluationSubject.from_observation(
        evaluation_run_id="eval-run-1",
        case_id="case-1",
        observation=_observation(),
    )

    assert first.subject_id == second.subject_id


def test_result_identities_are_deterministic() -> None:
    metric = MetricResult.create(
        evaluation_run_id="eval-run-1",
        case_id="case-1",
        subject_id="subject-1",
        metric="correctness",
        metric_version="1",
        status=ResultStatus.PASSED,
        score=0.9,
        created_at=NOW,
    )
    duplicate_metric = MetricResult.create(
        evaluation_run_id="eval-run-1",
        case_id="case-1",
        subject_id="subject-1",
        metric="correctness",
        metric_version="1",
        status=ResultStatus.PASSED,
        score=0.9,
        created_at=NOW,
    )
    judge = JudgeResult.create(
        evaluation_run_id="eval-run-1",
        case_id="case-1",
        subject_id="subject-1",
        judge="quality-judge",
        judge_version="2",
        prompt_sha256="d" * 64,
        rubric_version="3",
        status=ResultStatus.PASSED,
        score=0.9,
        label="pass",
        created_at=NOW,
    )

    assert metric.metric_result_id == duplicate_metric.metric_result_id
    assert metric.metric_result_id != judge.judge_result_id


def test_run_result_gate_baseline_job_and_attempt_round_trip() -> None:
    run = EvaluationRun(
        evaluation_run_id="eval-run-1",
        suite_id="suite-1",
        target="researcher",
        status=EvaluationRunStatus.RUNNING,
        started_at=NOW,
    )
    gate_result = GateResult.create(
        evaluation_run_id=run.evaluation_run_id,
        gate_id="quality",
        metric="correctness",
        status=GateStatus.PASSED,
        observed_value=0.9,
        threshold=0.8,
        created_at=NOW,
    )
    result = EvaluationResult(
        evaluation_run_id=run.evaluation_run_id,
        status=EvaluationRunStatus.COMPLETED,
        total_cases=1,
        passed_cases=1,
        failed_cases=0,
        metric_result_ids=("metric-1",),
        judge_result_ids=("judge-1",),
        gate_result_ids=(gate_result.gate_result_id,),
        completed_at=NOW + timedelta(seconds=1),
    )
    baseline = EvaluationBaseline.create(
        suite_id="suite-1",
        source_evaluation_run_id=run.evaluation_run_id,
        promoted_at=NOW,
        promoted_by="ci-admin",
    )
    job = EvaluationJob(
        job_id="job-1",
        evaluation_run_id=run.evaluation_run_id,
        suite_id="suite-1",
        case_id="case-1",
        subject_id="subject-1",
        status=JobStatus.PENDING,
        available_at=NOW,
        max_attempts=3,
        created_at=NOW,
        updated_at=NOW,
    )
    attempt = EvaluationAttempt(
        attempt_id="attempt-1",
        job_id=job.job_id,
        attempt_number=1,
        status=AttemptStatus.SUCCEEDED,
        started_at=NOW,
        ended_at=NOW + timedelta(milliseconds=10),
        duration_ms=10,
    )

    for record in (run, gate_result, result, baseline, job, attempt):
        assert type(record).model_validate_json(record.model_dump_json()) == record


def test_contracts_are_frozen_and_reject_unknown_fields() -> None:
    run = EvaluationRun(
        evaluation_run_id="eval-run-1",
        suite_id="suite-1",
        target="researcher",
        status=EvaluationRunStatus.PENDING,
        started_at=NOW,
    )

    with pytest.raises(ValidationError, match="frozen"):
        run.status = EvaluationRunStatus.COMPLETED
    with pytest.raises(ValidationError, match="Extra inputs"):
        EvaluationRun.model_validate({**run.model_dump(), "raw_prompt": "secret"})


def test_eval_contracts_do_not_import_opentelemetry_sdk() -> None:
    package = Path(__file__).parents[2] / "src" / "praval" / "eval"

    imports = "\n".join(path.read_text() for path in package.glob("*.py"))

    assert "opentelemetry" not in imports


@pytest.mark.parametrize(
    ("record", "message"),
    [
        (
            EvaluationRun,
            "completed runs require completed_at",
        ),
        (
            EvaluationAttempt,
            "finished attempts require ended_at",
        ),
        (
            EvaluationJob,
            "lease_owner and lease_expires_at must be supplied together",
        ),
    ],
)
def test_lifecycle_invariants(record: type, message: str) -> None:
    if record is EvaluationRun:
        values = dict(
            evaluation_run_id="eval-run-1",
            suite_id="suite-1",
            target="researcher",
            status=EvaluationRunStatus.COMPLETED,
            started_at=NOW,
        )
    elif record is EvaluationAttempt:
        values = dict(
            attempt_id="attempt-1",
            job_id="job-1",
            attempt_number=1,
            status=AttemptStatus.FAILED,
            started_at=NOW,
        )
    else:
        values = dict(
            job_id="job-1",
            evaluation_run_id="eval-run-1",
            suite_id="suite-1",
            case_id="case-1",
            subject_id="subject-1",
            status=JobStatus.LEASED,
            available_at=NOW,
            lease_owner="worker-1",
            created_at=NOW,
            updated_at=NOW,
        )

    with pytest.raises(ValidationError, match=message):
        record(**values)
