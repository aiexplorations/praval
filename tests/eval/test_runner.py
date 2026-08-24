"""Offline evaluation runner tests with deterministic fake participants."""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from praval.eval import (
    EvalRunner,
    EvaluationExecutionError,
    EvaluationRunStatus,
    EvaluationSubject,
    JudgeContext,
    JudgeResult,
    ResultStatus,
    SQLiteEvaluationStore,
    TargetResult,
    load_jsonl_suite,
)
from praval.models import ExecutionObservation, ObservationKind, ObservationStatus

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


class FakeTarget:
    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0

    async def evaluate(self, case) -> TargetResult:
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return TargetResult(
            observation=ExecutionObservation(
                observation_id=f"obs-{case.case.case_id}",
                run_id=f"execution-{case.case.case_id}",
                kind=ObservationKind.AGENT,
                agent_name="fake-target",
                response_id=f"response-{case.case.case_id}",
                started_at=NOW,
                ended_at=NOW + timedelta(milliseconds=10),
                duration_ms=10,
                status=ObservationStatus.OK,
            ),
            output={"answer": case.input},
        )


class FakeJudge:
    name = "quality"

    def __init__(self, *, failed_case: str | None = None) -> None:
        self.failed_case = failed_case

    async def evaluate(self, context: JudgeContext) -> JudgeResult:
        failed = context.case.case.case_id == self.failed_case
        return JudgeResult.create(
            evaluation_run_id=context.evaluation_run_id,
            case_id=context.case.case.case_id,
            subject_id=context.subject.subject_id,
            judge=self.name,
            judge_version="1",
            prompt_sha256="a" * 64,
            rubric_version="1",
            status=ResultStatus.FAILED if failed else ResultStatus.PASSED,
            score=0.1 if failed else 0.9,
            label="fail" if failed else "pass",
            created_at=NOW,
        )


def _suite(tmp_path, count: int = 6):
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(
        "".join(
            f'{{"id":"case-{index}","input":"question-{index}"}}\n'
            for index in range(count)
        ),
        encoding="utf-8",
    )
    return load_jsonl_suite(
        dataset,
        suite_id="suite-1",
        name="Suite",
        target="fake-target",
        judges=("quality",),
    )


@pytest.mark.asyncio
async def test_runner_bounds_concurrency_and_persists_linked_results(tmp_path) -> None:
    store = SQLiteEvaluationStore(tmp_path / "evaluation.db")
    await store.migrate()
    target = FakeTarget()
    runner = EvalRunner(
        store=store,
        target=target,
        judges={"quality": FakeJudge()},
        concurrency=2,
        clock=lambda: NOW,
    )

    result = await runner.run(_suite(tmp_path), evaluation_run_id="eval-run-1")

    assert result.status is EvaluationRunStatus.COMPLETED
    assert result.total_cases == 6
    assert result.passed_cases == 6
    assert result.failed_cases == 0
    assert target.maximum_active == 2
    run = await store.get_run("eval-run-1")
    assert run is not None and run.status is EvaluationRunStatus.COMPLETED
    subjects = await store.list_subjects(evaluation_run_id="eval-run-1")
    judges = await store.list_judge_results(evaluation_run_id="eval-run-1")
    assert len(subjects) == len(judges) == 6
    assert result.judge_result_ids == tuple(judge.judge_result_id for judge in judges)
    assert {subject.observation_id for subject in subjects} == {
        f"obs-case-{index}" for index in range(6)
    }
    await store.close()


@pytest.mark.asyncio
async def test_failed_judgment_fails_only_its_case(tmp_path) -> None:
    store = SQLiteEvaluationStore(tmp_path / "evaluation.db")
    await store.migrate()
    runner = EvalRunner(
        store=store,
        target=FakeTarget(),
        judges={"quality": FakeJudge(failed_case="case-1")},
        concurrency=3,
        clock=lambda: NOW,
    )

    result = await runner.run(_suite(tmp_path, 3), evaluation_run_id="eval-run-1")

    assert result.passed_cases == 2
    assert result.failed_cases == 1
    assert result.errored_cases == 0
    await store.close()


@pytest.mark.asyncio
async def test_runner_rejects_unknown_configured_judge_before_execution(
    tmp_path,
) -> None:
    store = SQLiteEvaluationStore(tmp_path / "evaluation.db")
    await store.migrate()
    runner = EvalRunner(store=store, target=FakeTarget(), judges={}, concurrency=1)

    with pytest.raises(EvaluationExecutionError, match="unknown judges"):
        await runner.run(_suite(tmp_path), evaluation_run_id="eval-run-1")

    assert await store.get_run("eval-run-1") is None
    await store.close()


@pytest.mark.asyncio
async def test_runner_rejects_judge_identity_drift_and_marks_run_failed(
    tmp_path,
) -> None:
    class InvalidJudge(FakeJudge):
        async def evaluate(self, context: JudgeContext) -> JudgeResult:
            result = await super().evaluate(context)
            return result.model_copy(update={"subject_id": "wrong-subject"})

    store = SQLiteEvaluationStore(tmp_path / "evaluation.db")
    await store.migrate()
    runner = EvalRunner(
        store=store,
        target=FakeTarget(),
        judges={"quality": InvalidJudge()},
        concurrency=1,
        clock=lambda: NOW,
    )

    with pytest.raises(EvaluationExecutionError, match="subject identity"):
        await runner.run(_suite(tmp_path, 1), evaluation_run_id="eval-run-1")

    run = await store.get_run("eval-run-1")
    assert run is not None
    assert run.status is EvaluationRunStatus.FAILED
    assert run.error_type == "EvaluationExecutionError"
    await store.close()


def test_target_result_and_judge_context_are_frozen() -> None:
    target = TargetResult(
        observation=ExecutionObservation(
            observation_id="obs",
            run_id="execution",
            kind=ObservationKind.AGENT,
            agent_name="target",
            started_at=NOW,
            ended_at=NOW,
            duration_ms=0,
            status=ObservationStatus.OK,
        ),
        output="answer",
    )
    assert target.output == "answer"
    with pytest.raises(FrozenInstanceError):
        target.output = "changed"
    assert EvaluationSubject.__name__ == "EvaluationSubject"


def test_runner_rejects_invalid_concurrency() -> None:
    with pytest.raises(ValueError, match="concurrency"):
        EvalRunner(store=None, target=FakeTarget(), judges={}, concurrency=0)


@pytest.mark.asyncio
async def test_runner_wraps_target_failure_and_marks_run_failed(tmp_path) -> None:
    class BrokenTarget:
        async def evaluate(self, case) -> TargetResult:
            raise TimeoutError("private failure detail")

    store = SQLiteEvaluationStore(tmp_path / "evaluation.db")
    await store.migrate()
    runner = EvalRunner(
        store=store,
        target=BrokenTarget(),
        judges={"quality": FakeJudge()},
        concurrency=1,
        clock=lambda: NOW,
    )

    with pytest.raises(EvaluationExecutionError, match="TimeoutError"):
        await runner.run(_suite(tmp_path, 1), evaluation_run_id="eval-run-1")

    run = await store.get_run("eval-run-1")
    assert run is not None and run.error_type == "EvaluationExecutionError"
    assert "private failure detail" not in run.model_dump_json()
    await store.close()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("evaluation_run_id", "wrong", "run identity"),
        ("case_id", "wrong", "case identity"),
        ("judge", "wrong", "evaluator identity"),
    ],
)
@pytest.mark.asyncio
async def test_runner_rejects_all_judge_identity_drift(
    tmp_path, field: str, value: str, message: str
) -> None:
    class InvalidJudge(FakeJudge):
        async def evaluate(self, context: JudgeContext) -> JudgeResult:
            result = await super().evaluate(context)
            return result.model_copy(update={field: value})

    store = SQLiteEvaluationStore(tmp_path / f"{field}.db")
    await store.migrate()
    runner = EvalRunner(
        store=store,
        target=FakeTarget(),
        judges={"quality": InvalidJudge()},
        concurrency=1,
        clock=lambda: NOW,
    )

    with pytest.raises(EvaluationExecutionError, match=message):
        await runner.run(_suite(tmp_path, 1), evaluation_run_id="eval-run-1")
    await store.close()


@pytest.mark.parametrize(
    ("status", "expected_field"),
    [(ResultStatus.ERROR, "errored_cases"), (ResultStatus.SKIPPED, "skipped_cases")],
)
@pytest.mark.asyncio
async def test_runner_aggregates_error_and_skipped_judgments(
    tmp_path, status: ResultStatus, expected_field: str
) -> None:
    class StatusJudge(FakeJudge):
        async def evaluate(self, context: JudgeContext) -> JudgeResult:
            values = dict(
                evaluation_run_id=context.evaluation_run_id,
                case_id=context.case.case.case_id,
                subject_id=context.subject.subject_id,
                judge=self.name,
                judge_version="1",
                prompt_sha256="a" * 64,
                rubric_version="1",
                status=status,
                created_at=NOW,
            )
            if status is ResultStatus.ERROR:
                values["error_type"] = "JudgeUnavailable"
            return JudgeResult.create(**values)

    store = SQLiteEvaluationStore(tmp_path / f"{status.value}.db")
    await store.migrate()
    runner = EvalRunner(
        store=store,
        target=FakeTarget(),
        judges={"quality": StatusJudge()},
        concurrency=1,
        clock=lambda: NOW,
    )

    result = await runner.run(_suite(tmp_path, 1), evaluation_run_id="eval-run-1")

    assert getattr(result, expected_field) == 1
    await store.close()


@pytest.mark.asyncio
async def test_runner_rejects_naive_clock_before_persisting_run(tmp_path) -> None:
    store = SQLiteEvaluationStore(tmp_path / "evaluation.db")
    await store.migrate()
    runner = EvalRunner(
        store=store,
        target=FakeTarget(),
        judges={"quality": FakeJudge()},
        clock=lambda: NOW.replace(tzinfo=None),
    )

    with pytest.raises(EvaluationExecutionError, match="aware timestamp"):
        await runner.run(_suite(tmp_path, 1), evaluation_run_id="eval-run-1")
    assert await store.get_run("eval-run-1") is None
    await store.close()
