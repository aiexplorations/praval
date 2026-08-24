"""Deterministic quality gates, run comparison, and explicit baselines."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Sequence

from .errors import EvaluationExecutionError
from .models import (
    EvaluationBaseline,
    EvaluationRunStatus,
    Gate,
    GateAggregation,
    GateOperator,
    GateResult,
    GateStatus,
    JudgeResult,
    MetricResult,
    ResultStatus,
)
from .store import EvaluationStore

ScoredResult = MetricResult | JudgeResult
ResultKind = Literal["metric", "judge"]
ResultIdentity = tuple[ResultKind, str, str]


class GateEvaluationError(ValueError):
    """Gate input is ambiguous or violates deterministic evaluation policy."""


@dataclass(frozen=True)
class MetricComparison:
    """One metric or judge score comparison between two completed runs."""

    kind: Literal["metric", "judge"]
    name: str
    version: str
    current_value: float | None
    baseline_value: float | None
    delta: float | None
    regressed: bool


@dataclass(frozen=True)
class RunComparison:
    """Deterministic score comparison that never promotes a baseline."""

    current_run_id: str
    baseline_run_id: str
    max_regression: float
    direction: Literal["higher", "lower"]
    metrics: tuple[MetricComparison, ...]

    @property
    def regressed(self) -> bool:
        """Return whether any comparable score exceeded the regression bound."""
        return any(metric.regressed for metric in self.metrics)


def _name(result: ScoredResult) -> str:
    return result.metric if isinstance(result, MetricResult) else result.judge


def _version(result: ScoredResult) -> str:
    return (
        result.metric_version
        if isinstance(result, MetricResult)
        else result.judge_version
    )


def _kind(result: ScoredResult) -> ResultKind:
    return "metric" if isinstance(result, MetricResult) else "judge"


def _matching(gate: Gate, results: Sequence[ScoredResult]) -> list[ScoredResult]:
    matching = [result for result in results if _name(result) == gate.metric]
    identities = {(_kind(result), _version(result)) for result in matching}
    if len(identities) > 1:
        raise GateEvaluationError(
            f"gate metric {gate.metric!r} resolves to multiple result versions"
        )
    return matching


def _scores(results: Sequence[ScoredResult]) -> list[float]:
    values = [
        result.score
        for result in results
        if result.status in {ResultStatus.PASSED, ResultStatus.FAILED}
        and result.score is not None
    ]
    scores = [float(value) for value in values]
    if any(not math.isfinite(value) for value in scores):
        raise GateEvaluationError("gate scores must be finite")
    return scores


def _percentile(scores: Sequence[float], percentile: float) -> float:
    ordered = sorted(scores)
    if len(ordered) == 1:
        return ordered[0]
    rank = (percentile / 100.0) * (len(ordered) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] + ((ordered[upper] - ordered[lower]) * weight)


def _aggregate(gate: Gate, results: Sequence[ScoredResult]) -> float | None:
    scored = _scores(results)
    if gate.aggregation is GateAggregation.COUNT:
        return float(len(scored)) if scored else None
    if gate.aggregation is GateAggregation.PASS_RATE:
        decided = [
            result
            for result in results
            if result.status in {ResultStatus.PASSED, ResultStatus.FAILED}
        ]
        if not decided:
            return None
        passed = sum(result.status is ResultStatus.PASSED for result in decided)
        return passed / len(decided)
    if not scored:
        return None
    if gate.aggregation is GateAggregation.MEAN:
        return math.fsum(scored) / len(scored)
    if gate.aggregation is GateAggregation.MINIMUM:
        return min(scored)
    if gate.aggregation is GateAggregation.MAXIMUM:
        return max(scored)
    if gate.aggregation is GateAggregation.PERCENTILE:
        assert gate.percentile is not None
        return _percentile(scored, gate.percentile)
    raise GateEvaluationError(f"unsupported aggregation: {gate.aggregation}")


def _compare(value: float, operator: GateOperator, threshold: float) -> bool:
    if operator is GateOperator.GREATER_THAN_OR_EQUAL:
        return value >= threshold
    if operator is GateOperator.GREATER_THAN:
        return value > threshold
    if operator is GateOperator.LESS_THAN_OR_EQUAL:
        return value <= threshold
    if operator is GateOperator.LESS_THAN:
        return value < threshold
    return value == threshold


def _within_regression(
    value: float,
    baseline: float,
    operator: GateOperator,
    maximum: float,
) -> bool:
    if operator in {
        GateOperator.GREATER_THAN_OR_EQUAL,
        GateOperator.GREATER_THAN,
    }:
        return value >= baseline - maximum
    if operator in {GateOperator.LESS_THAN_OR_EQUAL, GateOperator.LESS_THAN}:
        return value <= baseline + maximum
    return abs(value - baseline) <= maximum


def _error_result(
    evaluation_run_id: str,
    gate: Gate,
    *,
    created_at: datetime,
    error_type: str,
) -> GateResult:
    return GateResult.create(
        evaluation_run_id=evaluation_run_id,
        gate_id=gate.gate_id,
        metric=gate.metric,
        status=GateStatus.ERROR,
        threshold=gate.threshold,
        error_type=error_type,
        created_at=created_at,
    )


def evaluate_gate(
    evaluation_run_id: str,
    gate: Gate,
    results: Sequence[ScoredResult],
    *,
    baseline_results: Sequence[ScoredResult] = (),
    created_at: datetime | None = None,
) -> GateResult | None:
    """Apply one absolute and optional baseline-relative gate."""
    timestamp = created_at or datetime.now(timezone.utc)
    matching = _matching(gate, results)
    if any(result.status is ResultStatus.ERROR for result in matching):
        if not gate.required:
            return None
        return _error_result(
            evaluation_run_id,
            gate,
            created_at=timestamp,
            error_type="RequiredMetricError",
        )
    observed = _aggregate(gate, matching)
    if observed is None:
        if not gate.required:
            return None
        return _error_result(
            evaluation_run_id,
            gate,
            created_at=timestamp,
            error_type="RequiredMetricMissing",
        )

    baseline_value = None
    regression_delta = None
    regression_passed = True
    if gate.baseline_max_regression is not None:
        baseline_matching = _matching(gate, baseline_results)
        if baseline_matching and {
            (_kind(result), _version(result)) for result in baseline_matching
        } != {(_kind(result), _version(result)) for result in matching}:
            raise GateEvaluationError(
                f"gate metric {gate.metric!r} baseline identity does not match "
                "the current result"
            )
        baseline_value = _aggregate(gate, baseline_matching)
        if baseline_value is None:
            if not gate.required:
                return None
            return _error_result(
                evaluation_run_id,
                gate,
                created_at=timestamp,
                error_type="RequiredBaselineMissing",
            )
        regression_delta = observed - baseline_value
        regression_passed = _within_regression(
            observed,
            baseline_value,
            gate.operator,
            gate.baseline_max_regression,
        )

    status = (
        GateStatus.PASSED
        if _compare(observed, gate.operator, gate.threshold) and regression_passed
        else GateStatus.FAILED
    )
    return GateResult.create(
        evaluation_run_id=evaluation_run_id,
        gate_id=gate.gate_id,
        metric=gate.metric,
        status=status,
        observed_value=observed,
        threshold=gate.threshold,
        baseline_value=baseline_value,
        regression_delta=regression_delta,
        created_at=timestamp,
    )


async def promote_evaluation_baseline(
    store: EvaluationStore,
    *,
    suite_id: str,
    evaluation_run_id: str,
    promoted_by: str,
    promoted_at: datetime | None = None,
) -> EvaluationBaseline:
    """Explicitly promote one completed run after validating its suite."""
    run = await store.get_run(evaluation_run_id)
    terminal = await store.get_evaluation_result(evaluation_run_id)
    if (
        run is None
        or run.status is not EvaluationRunStatus.COMPLETED
        or terminal is None
    ):
        raise EvaluationExecutionError("baseline source run must be completed")
    if run.suite_id != suite_id:
        raise EvaluationExecutionError("baseline source run belongs to another suite")
    baseline = EvaluationBaseline.create(
        suite_id=suite_id,
        source_evaluation_run_id=evaluation_run_id,
        promoted_at=promoted_at or datetime.now(timezone.utc),
        promoted_by=promoted_by,
    )
    return await store.promote_baseline(baseline)


def _grouped_means(
    results: Sequence[ScoredResult],
) -> dict[ResultIdentity, float]:
    groups: dict[ResultIdentity, list[float]] = {}
    for result in results:
        if result.status not in {ResultStatus.PASSED, ResultStatus.FAILED}:
            continue
        if result.score is None or not math.isfinite(result.score):
            continue
        key = (_kind(result), _name(result), _version(result))
        groups.setdefault(key, []).append(result.score)
    return {key: math.fsum(values) / len(values) for key, values in groups.items()}


async def compare_evaluation_runs(
    store: EvaluationStore,
    *,
    current_run_id: str,
    baseline_run_id: str,
    max_regression: float = 0.0,
    direction: Literal["higher", "lower"] = "higher",
) -> RunComparison:
    """Compare mean scores without mutating the active baseline."""
    if not math.isfinite(max_regression) or max_regression < 0:
        raise ValueError("max_regression must be finite and non-negative")
    if direction not in {"higher", "lower"}:
        raise ValueError("direction must be higher or lower")
    current_run = await store.get_run(current_run_id)
    baseline_run = await store.get_run(baseline_run_id)
    if current_run is None or baseline_run is None:
        raise EvaluationExecutionError("comparison runs must exist")
    if (
        current_run.status is not EvaluationRunStatus.COMPLETED
        or baseline_run.status is not EvaluationRunStatus.COMPLETED
    ):
        raise EvaluationExecutionError("comparison runs must be completed")
    if current_run.suite_id != baseline_run.suite_id:
        raise EvaluationExecutionError("comparison runs belong to different suites")

    async def load(run_id: str) -> list[ScoredResult]:
        metrics = await store.list_metric_results(
            evaluation_run_id=run_id, limit=100_000
        )
        judges = await store.list_judge_results(evaluation_run_id=run_id, limit=100_000)
        return [*metrics, *judges]

    current = _grouped_means(await load(current_run_id))
    baseline = _grouped_means(await load(baseline_run_id))
    comparisons = []
    for kind, name, version in sorted(set(current) | set(baseline)):
        current_value = current.get((kind, name, version))
        baseline_value = baseline.get((kind, name, version))
        delta = (
            current_value - baseline_value
            if current_value is not None and baseline_value is not None
            else None
        )
        if baseline_value is None:
            regressed = False
        elif current_value is None:
            regressed = True
        elif direction == "higher":
            regressed = current_value < baseline_value - max_regression
        else:
            regressed = current_value > baseline_value + max_regression
        comparisons.append(
            MetricComparison(
                kind=kind,
                name=name,
                version=version,
                current_value=current_value,
                baseline_value=baseline_value,
                delta=delta,
                regressed=regressed,
            )
        )
    return RunComparison(
        current_run_id=current_run_id,
        baseline_run_id=baseline_run_id,
        max_regression=max_regression,
        direction=direction,
        metrics=tuple(comparisons),
    )


__all__ = [
    "GateEvaluationError",
    "MetricComparison",
    "RunComparison",
    "compare_evaluation_runs",
    "evaluate_gate",
    "promote_evaluation_baseline",
]
