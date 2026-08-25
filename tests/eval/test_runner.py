"""Offline evaluation runner tests with deterministic fake participants."""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

import pytest

from praval.eval import (
    EvalRunner,
    EvaluationExecutionError,
    EvaluationRunStatus,
    EvaluationSubject,
    ExactMatchMetric,
    Gate,
    GateAggregation,
    GateOperator,
    GateStatus,
    JudgeContext,
    JudgeResult,
    ResultStatus,
    SQLiteEvaluationStore,
    TargetResult,
    load_jsonl_suite,
    promote_evaluation_baseline,
)
from praval.models import (
    ExecutionObservation,
    ObservationFactStatus,
    ObservationKind,
    ObservationStatus,
    ReefHandoffObservation,
    ToolCallObservation,
)

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

    def __init__(self, *, failed_case: str | None = None, score: float = 0.9) -> None:
        self.failed_case = failed_case
        self.score = score

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
            score=0.1 if failed else self.score,
            label="fail" if failed else "pass",
            created_at=NOW,
        )


class FakeWorkflowTarget:
    async def evaluate(self, case) -> TargetResult:
        return TargetResult(
            observation=ExecutionObservation(
                observation_id=f"workflow-observation-{case.case.case_id}",
                run_id=f"workflow-execution-{case.case.case_id}",
                kind=ObservationKind.WORKFLOW,
                workflow_name="research-workflow",
                response_id=f"workflow-response-{case.case.case_id}",
                started_at=NOW,
                ended_at=NOW + timedelta(milliseconds=20),
                duration_ms=20,
                status=ObservationStatus.OK,
                terminal_outcome="answer_ready",
                tool_calls=(
                    ToolCallObservation(
                        tool_call_id="tool-1",
                        name="lookup",
                        status=ObservationFactStatus.OK,
                        duration_ms=2,
                    ),
                ),
                handoffs=(
                    ReefHandoffObservation(
                        handoff_id="handoff-1",
                        source_agent_id="researcher",
                        target_agent_id="writer",
                        channel="drafts",
                        status=ObservationFactStatus.OK,
                        duration_ms=3,
                    ),
                ),
            ),
            output={"answer": case.input},
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
async def test_runner_emits_the_persisted_judge_and_subject_identities(
    tmp_path, monkeypatch
) -> None:
    emitted = []

    def capture(result, subject) -> bool:
        emitted.append((result, subject))
        return True

    monkeypatch.setattr("praval.eval.runner.emit_evaluation_result", capture)
    store = SQLiteEvaluationStore(tmp_path / "evaluation.db")
    await store.migrate()
    runner = EvalRunner(
        store=store,
        target=FakeTarget(),
        judges={"quality": FakeJudge()},
        concurrency=1,
        clock=lambda: NOW,
    )

    await runner.run(_suite(tmp_path, 1), evaluation_run_id="eval-run-1")

    persisted = await store.list_judge_results(evaluation_run_id="eval-run-1")
    assert len(emitted) == len(persisted) == 1
    emitted_result, emitted_subject = emitted[0]
    assert emitted_result == persisted[0]
    assert emitted_result.subject_id == emitted_subject.subject_id
    assert emitted_subject.observation_id == "obs-case-0"
    assert emitted_subject.response_id == "response-case-0"
    await store.close()


@pytest.mark.asyncio
async def test_runner_isolates_evaluation_telemetry_failures(
    tmp_path, monkeypatch
) -> None:
    def fail_emission(result, subject) -> bool:
        raise RuntimeError("telemetry unavailable")

    monkeypatch.setattr("praval.eval.runner.emit_evaluation_result", fail_emission)
    store = SQLiteEvaluationStore(tmp_path / "evaluation.db")
    await store.migrate()
    runner = EvalRunner(
        store=store,
        target=FakeTarget(),
        judges={"quality": FakeJudge()},
        concurrency=1,
        clock=lambda: NOW,
    )

    result = await runner.run(_suite(tmp_path, 1), evaluation_run_id="eval-run-1")

    assert result.status is EvaluationRunStatus.COMPLETED
    assert len(await store.list_judge_results(evaluation_run_id="eval-run-1")) == 1
    await store.close()


@pytest.mark.asyncio
async def test_runner_evaluates_one_aggregated_workflow_observation(tmp_path) -> None:
    store = SQLiteEvaluationStore(tmp_path / "workflow.db")
    await store.migrate()
    loaded_suite = _suite(tmp_path, 1)
    workflow_suite = replace(
        loaded_suite,
        suite=loaded_suite.suite.model_copy(
            update={
                "target": "research-workflow",
                "gates": (
                    Gate(
                        gate_id="workflow-quality",
                        metric="quality",
                        aggregation=GateAggregation.MEAN,
                        operator=GateOperator.GREATER_THAN_OR_EQUAL,
                        threshold=0.8,
                    ),
                ),
            }
        ),
    )
    runner = EvalRunner(
        store=store,
        target=FakeWorkflowTarget(),
        judges={"quality": FakeJudge()},
        concurrency=1,
        clock=lambda: NOW,
    )

    result = await runner.run(workflow_suite, evaluation_run_id="workflow-eval-1")

    subjects = await store.list_subjects(evaluation_run_id="workflow-eval-1")
    gates = await store.list_gate_results(evaluation_run_id="workflow-eval-1")
    assert result.passed_cases == 1
    assert len(gates) == 1 and gates[0].status is GateStatus.PASSED
    assert len(subjects) == 1
    observation = subjects[0].observation
    assert observation.kind is ObservationKind.WORKFLOW
    assert observation.workflow_name == "research-workflow"
    assert observation.terminal_outcome == "answer_ready"
    assert [fact.name for fact in observation.tool_calls] == ["lookup"]
    assert [fact.target_agent_id for fact in observation.handoffs] == ["writer"]
    await store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("metric", "expected_status", "expected_error"),
    [
        ("quality", GateStatus.PASSED, None),
        ("missing", GateStatus.ERROR, "RequiredMetricMissing"),
    ],
)
async def test_runner_persists_quality_gate_decisions(
    tmp_path,
    metric: str,
    expected_status: GateStatus,
    expected_error: str | None,
) -> None:
    store = SQLiteEvaluationStore(tmp_path / f"{metric}.db")
    await store.migrate()
    loaded_suite = _suite(tmp_path, 1)
    gate = Gate(
        gate_id="release-quality",
        metric=metric,
        aggregation=GateAggregation.MEAN,
        operator=GateOperator.GREATER_THAN_OR_EQUAL,
        threshold=0.8,
    )
    gated_suite = replace(
        loaded_suite,
        suite=loaded_suite.suite.model_copy(update={"gates": (gate,)}),
    )
    runner = EvalRunner(
        store=store,
        target=FakeTarget(),
        judges={"quality": FakeJudge()},
        concurrency=1,
        clock=lambda: NOW,
    )

    result = await runner.run(gated_suite, evaluation_run_id="gated-eval-1")

    gates = await store.list_gate_results(evaluation_run_id="gated-eval-1")
    assert len(gates) == 1
    assert result.gate_result_ids == (gates[0].gate_result_id,)
    assert gates[0].status is expected_status
    assert gates[0].error_type == expected_error
    await store.close()


@pytest.mark.asyncio
async def test_runner_applies_only_explicit_active_baseline_to_regression_gate(
    tmp_path,
) -> None:
    store = SQLiteEvaluationStore(tmp_path / "baseline.db")
    await store.migrate()
    loaded_suite = _suite(tmp_path, 1)
    gate = Gate(
        gate_id="quality-regression",
        metric="quality",
        aggregation=GateAggregation.MEAN,
        operator=GateOperator.GREATER_THAN_OR_EQUAL,
        threshold=0,
        baseline_max_regression=0.1,
    )
    gated_suite = replace(
        loaded_suite,
        suite=loaded_suite.suite.model_copy(update={"gates": (gate,)}),
    )
    baseline_runner = EvalRunner(
        store=store,
        target=FakeTarget(),
        judges={"quality": FakeJudge(score=0.9)},
        concurrency=1,
        clock=lambda: NOW,
    )
    await baseline_runner.run(gated_suite, evaluation_run_id="baseline-run")
    await promote_evaluation_baseline(
        store,
        suite_id="suite-1",
        evaluation_run_id="baseline-run",
        promoted_by="release-owner",
        promoted_at=NOW,
    )
    current_runner = EvalRunner(
        store=store,
        target=FakeTarget(),
        judges={"quality": FakeJudge(score=0.7)},
        concurrency=1,
        clock=lambda: NOW,
    )

    await current_runner.run(gated_suite, evaluation_run_id="current-run")

    results = await store.list_gate_results(evaluation_run_id="current-run")
    assert len(results) == 1
    assert results[0].status is GateStatus.FAILED
    assert results[0].observed_value == pytest.approx(0.7)
    assert results[0].baseline_value == pytest.approx(0.9)
    assert results[0].regression_delta == pytest.approx(-0.2)
    await store.close()


@pytest.mark.asyncio
async def test_runner_executes_persists_and_gates_deterministic_metrics(
    tmp_path,
) -> None:
    dataset = tmp_path / "metric-cases.jsonl"
    dataset.write_text(
        '{"id":"case-1","input":"question",'
        '"expected_output":{"answer":"question"}}\n',
        encoding="utf-8",
    )
    gate = Gate(
        gate_id="exact",
        metric="exact_match",
        aggregation=GateAggregation.MEAN,
        operator=GateOperator.EQUAL,
        threshold=1,
    )
    suite = load_jsonl_suite(
        dataset,
        suite_id="metric-suite",
        name="Metric Suite",
        target="fake-target",
        metrics=("exact_match",),
        gates=(gate,),
    )
    store = SQLiteEvaluationStore(tmp_path / "metrics.db")
    await store.migrate()
    runner = EvalRunner(
        store=store,
        target=FakeTarget(),
        judges={},
        metrics={"exact_match": ExactMatchMetric(clock=lambda: NOW)},
        concurrency=1,
        clock=lambda: NOW,
    )

    result = await runner.run(suite, evaluation_run_id="metric-run")

    metrics = await store.list_metric_results(evaluation_run_id="metric-run")
    gates = await store.list_gate_results(evaluation_run_id="metric-run")
    assert result.passed_cases == 1
    assert result.metric_result_ids == (metrics[0].metric_result_id,)
    assert metrics[0].status is ResultStatus.PASSED
    assert gates[0].status is GateStatus.PASSED
    await store.close()


@pytest.mark.asyncio
async def test_runner_persists_metric_failures_and_rejects_identity_drift(
    tmp_path,
) -> None:
    class BrokenMetric:
        name = "broken"
        version = "1"

        async def evaluate(self, context):
            raise TimeoutError("private metric detail")

    loaded = _suite(tmp_path, 1)
    metric_suite = replace(
        loaded,
        suite=loaded.suite.model_copy(update={"judges": (), "metrics": ("broken",)}),
    )
    store = SQLiteEvaluationStore(tmp_path / "broken.db")
    await store.migrate()
    runner = EvalRunner(
        store=store,
        target=FakeTarget(),
        judges={},
        metrics={"broken": BrokenMetric()},
        concurrency=1,
        clock=lambda: NOW,
    )

    result = await runner.run(metric_suite, evaluation_run_id="broken-run")

    metrics = await store.list_metric_results(evaluation_run_id="broken-run")
    assert result.errored_cases == 1
    assert metrics[0].error_type == "TimeoutError"
    assert "private metric detail" not in metrics[0].model_dump_json()

    class DriftMetric(BrokenMetric):
        async def evaluate(self, context):
            metric = await ExactMatchMetric(clock=lambda: NOW).evaluate(context)
            return metric.model_copy(update={"metric": "wrong"})

    drift_runner = EvalRunner(
        store=store,
        target=FakeTarget(),
        judges={},
        metrics={"broken": DriftMetric()},
        concurrency=1,
        clock=lambda: NOW,
    )
    with pytest.raises(EvaluationExecutionError, match="metric result evaluator"):
        await drift_runner.run(metric_suite, evaluation_run_id="drift-run")
    await store.close()


@pytest.mark.asyncio
async def test_runner_rejects_unknown_metric_before_execution(tmp_path) -> None:
    loaded = _suite(tmp_path, 1)
    metric_suite = replace(
        loaded,
        suite=loaded.suite.model_copy(update={"judges": (), "metrics": ("missing",)}),
    )
    store = SQLiteEvaluationStore(tmp_path / "unknown-metric.db")
    await store.migrate()
    runner = EvalRunner(store=store, target=FakeTarget(), judges={}, metrics={})

    with pytest.raises(EvaluationExecutionError, match="unknown metrics"):
        await runner.run(metric_suite, evaluation_run_id="metric-run")

    assert await store.get_run("metric-run") is None
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
