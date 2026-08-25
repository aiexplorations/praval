"""Deterministic gate, regression, comparison, and baseline tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from praval.eval import (
    EvalSuite,
    EvaluationBaseline,
    EvaluationExecutionError,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
    Gate,
    GateAggregation,
    GateEvaluationError,
    GateOperator,
    GateStatus,
    JudgeResult,
    MetricResult,
    ResultStatus,
    SQLiteEvaluationStore,
    compare_evaluation_runs,
    evaluate_gate,
    promote_evaluation_baseline,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def _metric(
    case_id: str,
    score: float | None,
    *,
    run_id: str = "run-current",
    status: ResultStatus = ResultStatus.PASSED,
    metric: str = "quality",
    version: str = "1",
) -> MetricResult:
    values = dict(
        evaluation_run_id=run_id,
        case_id=case_id,
        subject_id=f"subject-{case_id}",
        metric=metric,
        metric_version=version,
        status=status,
        score=score,
        created_at=NOW,
    )
    if status is ResultStatus.ERROR:
        values["error_type"] = "MetricUnavailable"
    return MetricResult.create(**values)


def _judge(case_id: str, score: float, *, run_id: str) -> JudgeResult:
    return JudgeResult.create(
        evaluation_run_id=run_id,
        case_id=case_id,
        subject_id=f"subject-{case_id}",
        judge="quality",
        judge_version="1",
        prompt_sha256="0" * 64,
        rubric_version="1",
        status=ResultStatus.PASSED,
        score=score,
        label="pass",
        created_at=NOW,
    )


@pytest.mark.parametrize(
    ("aggregation", "percentile", "expected"),
    [
        (GateAggregation.MEAN, None, 2 / 3),
        (GateAggregation.MINIMUM, None, 0.2),
        (GateAggregation.MAXIMUM, None, 1.0),
        (GateAggregation.PERCENTILE, 50.0, 0.8),
        (GateAggregation.COUNT, None, 3.0),
        (GateAggregation.PASS_RATE, None, 2 / 3),
    ],
)
def test_gate_aggregations_are_deterministic(
    aggregation: GateAggregation, percentile: float | None, expected: float
) -> None:
    results = (
        _metric("a", 0.2, status=ResultStatus.FAILED),
        _metric("b", 0.8),
        _metric("c", 1.0),
    )
    gate = Gate(
        gate_id=f"quality-{aggregation.value}",
        metric="quality",
        aggregation=aggregation,
        operator=GateOperator.GREATER_THAN_OR_EQUAL,
        threshold=0,
        percentile=percentile,
    )

    evaluated = evaluate_gate("run-current", gate, results, created_at=NOW)

    assert evaluated is not None
    assert evaluated.status is GateStatus.PASSED
    assert evaluated.observed_value == pytest.approx(expected)


@pytest.mark.parametrize(
    ("operator", "threshold", "expected"),
    [
        (GateOperator.GREATER_THAN_OR_EQUAL, 0.8, GateStatus.PASSED),
        (GateOperator.GREATER_THAN, 0.8, GateStatus.FAILED),
        (GateOperator.LESS_THAN_OR_EQUAL, 0.8, GateStatus.PASSED),
        (GateOperator.LESS_THAN, 0.8, GateStatus.FAILED),
        (GateOperator.EQUAL, 0.8, GateStatus.PASSED),
    ],
)
def test_gate_operators_have_stable_boundary_behavior(
    operator: GateOperator, threshold: float, expected: GateStatus
) -> None:
    gate = Gate(
        gate_id="quality-boundary",
        metric="quality",
        aggregation=GateAggregation.MEAN,
        operator=operator,
        threshold=threshold,
    )

    result = evaluate_gate("run-current", gate, (_metric("a", 0.8),), created_at=NOW)

    assert result is not None and result.status is expected


def test_required_gate_errors_on_missing_or_errored_metric() -> None:
    required = Gate(
        gate_id="required",
        metric="quality",
        aggregation=GateAggregation.MEAN,
        operator=GateOperator.GREATER_THAN_OR_EQUAL,
        threshold=0.8,
    )
    optional = required.model_copy(update={"gate_id": "optional", "required": False})

    missing = evaluate_gate("run-current", required, (), created_at=NOW)
    errored = evaluate_gate(
        "run-current",
        required,
        (_metric("a", None, status=ResultStatus.ERROR),),
        created_at=NOW,
    )

    assert missing is not None and missing.error_type == "RequiredMetricMissing"
    assert errored is not None and errored.error_type == "RequiredMetricError"
    assert evaluate_gate("run-current", optional, (), created_at=NOW) is None
    assert (
        evaluate_gate(
            "run-current",
            optional,
            (_metric("a", None, status=ResultStatus.ERROR),),
            created_at=NOW,
        )
        is None
    )


def test_gate_rejects_non_finite_and_ambiguous_score_versions() -> None:
    gate = Gate(
        gate_id="quality",
        metric="quality",
        aggregation=GateAggregation.MEAN,
        operator=GateOperator.GREATER_THAN_OR_EQUAL,
        threshold=0.8,
    )
    non_finite = _metric("nan", 0.9).model_copy(update={"score": float("nan")})
    with pytest.raises(GateEvaluationError, match="finite"):
        evaluate_gate("run-current", gate, (non_finite,), created_at=NOW)
    with pytest.raises(GateEvaluationError, match="multiple result versions"):
        evaluate_gate(
            "run-current",
            gate,
            (_metric("a", 0.9), _metric("b", 0.9, version="2")),
            created_at=NOW,
        )


def test_percentile_single_value_and_empty_pass_rate_policy() -> None:
    percentile = Gate(
        gate_id="percentile",
        metric="quality",
        aggregation=GateAggregation.PERCENTILE,
        operator=GateOperator.GREATER_THAN_OR_EQUAL,
        threshold=0.8,
        percentile=95,
    )
    pass_rate = percentile.model_copy(
        update={
            "gate_id": "pass-rate",
            "aggregation": GateAggregation.PASS_RATE,
        }
    )

    result = evaluate_gate(
        "run-current", percentile, (_metric("a", 0.9),), created_at=NOW
    )
    missing = evaluate_gate("run-current", pass_rate, (), created_at=NOW)

    assert result is not None and result.observed_value == 0.9
    assert missing is not None and missing.error_type == "RequiredMetricMissing"


@pytest.mark.parametrize(
    ("operator", "current", "baseline", "expected"),
    [
        (GateOperator.GREATER_THAN_OR_EQUAL, 0.75, 0.80, GateStatus.PASSED),
        (GateOperator.GREATER_THAN_OR_EQUAL, 0.69, 0.80, GateStatus.FAILED),
        (GateOperator.LESS_THAN_OR_EQUAL, 0.25, 0.20, GateStatus.PASSED),
        (GateOperator.LESS_THAN_OR_EQUAL, 0.31, 0.20, GateStatus.FAILED),
        (GateOperator.EQUAL, 0.85, 0.80, GateStatus.PASSED),
        (GateOperator.EQUAL, 0.91, 0.80, GateStatus.FAILED),
    ],
)
def test_gate_applies_directional_baseline_regression_limit(
    operator: GateOperator,
    current: float,
    baseline: float,
    expected: GateStatus,
) -> None:
    gate = Gate(
        gate_id="regression",
        metric="quality",
        aggregation=GateAggregation.MEAN,
        operator=operator,
        threshold=current,
        baseline_max_regression=0.1,
    )

    result = evaluate_gate(
        "run-current",
        gate,
        (_metric("current", current),),
        baseline_results=(_metric("baseline", baseline, run_id="run-base"),),
        created_at=NOW,
    )

    assert result is not None and result.status is expected
    assert result.baseline_value == pytest.approx(baseline)
    assert result.regression_delta == pytest.approx(current - baseline)


def test_regression_gate_requires_baseline_according_to_missing_policy() -> None:
    required = Gate(
        gate_id="regression",
        metric="quality",
        aggregation=GateAggregation.MEAN,
        operator=GateOperator.GREATER_THAN_OR_EQUAL,
        threshold=0.8,
        baseline_max_regression=0.1,
    )
    optional = required.model_copy(update={"gate_id": "optional", "required": False})

    missing = evaluate_gate(
        "run-current",
        required,
        (_metric("a", 0.9),),
        created_at=NOW,
    )

    assert missing is not None and missing.error_type == "RequiredBaselineMissing"
    assert (
        evaluate_gate(
            "run-current",
            optional,
            (_metric("a", 0.9),),
            created_at=NOW,
        )
        is None
    )


def test_regression_gate_rejects_incompatible_baseline_identity() -> None:
    gate = Gate(
        gate_id="regression",
        metric="quality",
        aggregation=GateAggregation.MEAN,
        operator=GateOperator.GREATER_THAN_OR_EQUAL,
        threshold=0.8,
        baseline_max_regression=0.1,
    )

    with pytest.raises(GateEvaluationError, match="baseline identity"):
        evaluate_gate(
            "run-current",
            gate,
            (_metric("current", 0.9),),
            baseline_results=(
                _metric("baseline", 0.9, run_id="run-base", version="2"),
            ),
            created_at=NOW,
        )


@pytest.mark.asyncio
async def test_baseline_promotion_is_explicit_and_validates_completed_source(
    tmp_path,
) -> None:
    store = SQLiteEvaluationStore(tmp_path / "evaluation.db")
    await store.migrate()
    suite = EvalSuite(
        suite_id="suite-1",
        name="Suite",
        target="agent:target",
        case_ids=("case-1",),
    )
    await store.put_suite(suite)
    running = EvaluationRun(
        evaluation_run_id="run-current",
        suite_id="suite-1",
        target="agent:target",
        status=EvaluationRunStatus.RUNNING,
        started_at=NOW,
    )
    await store.put_run(running)
    assert await store.get_active_baseline("suite-1") is None

    with pytest.raises(EvaluationExecutionError, match="completed"):
        await promote_evaluation_baseline(
            store,
            suite_id="suite-1",
            evaluation_run_id="run-current",
            promoted_by="release-owner",
            promoted_at=NOW,
        )

    completed_at = NOW + timedelta(seconds=1)
    await store.put_run(
        running.model_copy(
            update={
                "status": EvaluationRunStatus.COMPLETED,
                "completed_at": completed_at,
            }
        )
    )
    await store.put_evaluation_result(
        EvaluationResult(
            evaluation_run_id="run-current",
            status=EvaluationRunStatus.COMPLETED,
            total_cases=1,
            passed_cases=1,
            failed_cases=0,
            completed_at=completed_at,
        )
    )

    baseline = await promote_evaluation_baseline(
        store,
        suite_id="suite-1",
        evaluation_run_id="run-current",
        promoted_by="release-owner",
        promoted_at=completed_at,
    )

    assert isinstance(baseline, EvaluationBaseline)
    assert await store.get_active_baseline("suite-1") == baseline
    with pytest.raises(EvaluationExecutionError, match="another suite"):
        await promote_evaluation_baseline(
            store,
            suite_id="suite-2",
            evaluation_run_id="run-current",
            promoted_by="release-owner",
            promoted_at=completed_at,
        )
    await store.close()


@pytest.mark.asyncio
async def test_run_comparison_reports_metric_regression_without_mutating_baseline(
    tmp_path,
) -> None:
    store = SQLiteEvaluationStore(tmp_path / "evaluation.db")
    await store.migrate()
    for run_id in ("run-base", "run-current"):
        await store.put_run(
            EvaluationRun(
                evaluation_run_id=run_id,
                suite_id="suite-1",
                target="agent:target",
                status=EvaluationRunStatus.COMPLETED,
                started_at=NOW,
                completed_at=NOW + timedelta(seconds=1),
            )
        )
    await store.put_metric_result(_metric("base", 0.9, run_id="run-base"))
    await store.put_metric_result(_metric("current", 0.7))
    await store.put_judge_result(_judge("base-judge", 0.8, run_id="run-base"))
    await store.put_judge_result(_judge("current-judge", 0.8, run_id="run-current"))

    comparison = await compare_evaluation_runs(
        store,
        current_run_id="run-current",
        baseline_run_id="run-base",
        max_regression=0.1,
    )

    assert comparison.regressed is True
    by_kind = {item.kind: item for item in comparison.metrics}
    assert by_kind["metric"].name == "quality"
    assert by_kind["metric"].delta == pytest.approx(-0.2)
    assert by_kind["judge"].delta == 0
    assert await store.get_active_baseline("suite-1") is None
    await store.close()


@pytest.mark.asyncio
async def test_run_comparison_validates_inputs_and_handles_direction_and_gaps(
    tmp_path,
) -> None:
    store = SQLiteEvaluationStore(tmp_path / "comparison.db")
    await store.migrate()
    completed = {
        "status": EvaluationRunStatus.COMPLETED,
        "started_at": NOW,
        "completed_at": NOW + timedelta(seconds=1),
        "target": "agent:target",
    }
    for run_id, suite_id in (
        ("base", "suite-1"),
        ("current", "suite-1"),
        ("other", "suite-2"),
    ):
        await store.put_run(
            EvaluationRun(
                evaluation_run_id=run_id,
                suite_id=suite_id,
                **completed,
            )
        )
    await store.put_run(
        EvaluationRun(
            evaluation_run_id="running",
            suite_id="suite-1",
            target="agent:target",
            status=EvaluationRunStatus.RUNNING,
            started_at=NOW,
        )
    )
    await store.put_metric_result(_metric("base", 0.2, run_id="base"))
    await store.put_metric_result(_metric("current", 0.4, run_id="current"))
    await store.put_metric_result(
        _metric("new", 0.9, run_id="current", metric="new-metric")
    )
    await store.put_metric_result(
        _metric("removed", 0.8, run_id="base", metric="removed-metric")
    )

    lower = await compare_evaluation_runs(
        store,
        current_run_id="current",
        baseline_run_id="base",
        max_regression=0.1,
        direction="lower",
    )

    by_name = {item.name: item for item in lower.metrics}
    assert by_name["quality"].regressed is True
    assert by_name["new-metric"].regressed is False
    assert by_name["removed-metric"].regressed is True
    with pytest.raises(ValueError, match="max_regression"):
        await compare_evaluation_runs(
            store,
            current_run_id="current",
            baseline_run_id="base",
            max_regression=-1,
        )
    with pytest.raises(ValueError, match="direction"):
        await compare_evaluation_runs(
            store,
            current_run_id="current",
            baseline_run_id="base",
            direction="sideways",
        )
    with pytest.raises(EvaluationExecutionError, match="must exist"):
        await compare_evaluation_runs(
            store,
            current_run_id="missing",
            baseline_run_id="base",
        )
    with pytest.raises(EvaluationExecutionError, match="must be completed"):
        await compare_evaluation_runs(
            store,
            current_run_id="running",
            baseline_run_id="base",
        )
    with pytest.raises(EvaluationExecutionError, match="different suites"):
        await compare_evaluation_runs(
            store,
            current_run_id="other",
            baseline_run_id="base",
        )
    await store.close()
