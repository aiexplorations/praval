"""Deterministic, provider-free evaluation metrics."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Callable

from praval.models import ObservationStatus

from .models import MetricResult, ResultStatus
from .runner import JudgeContext


class _DeterministicMetric(ABC):
    name: str
    version = "1"

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @abstractmethod
    async def evaluate(self, context: JudgeContext) -> MetricResult:
        """Evaluate one completed target subject."""

    def _result(
        self,
        context: JudgeContext,
        *,
        status: ResultStatus,
        score: float | None = None,
        label: str | None = None,
        error_type: str | None = None,
    ) -> MetricResult:
        return MetricResult.create(
            evaluation_run_id=context.evaluation_run_id,
            case_id=context.case.case.case_id,
            subject_id=context.subject.subject_id,
            metric=self.name,
            metric_version=self.version,
            status=status,
            score=score,
            label=label,
            error_type=error_type,
            created_at=self._clock(),
        )


def _normalized_json(value: object) -> str:
    normalized = value
    if isinstance(value, str):
        try:
            normalized = json.loads(value)
        except json.JSONDecodeError:
            normalized = value
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class ExactMatchMetric(_DeterministicMetric):
    """Compare canonical JSON values without model calls."""

    name = "exact_match"

    async def evaluate(self, context: JudgeContext) -> MetricResult:
        if context.case.case.expected_output is None:
            return self._result(context, status=ResultStatus.SKIPPED)
        try:
            matched = _normalized_json(
                context.target_result.output
            ) == _normalized_json(context.case.expected_output)
        except (TypeError, ValueError):
            return self._result(
                context,
                status=ResultStatus.ERROR,
                error_type="MetricInputError",
            )
        return self._result(
            context,
            status=ResultStatus.PASSED if matched else ResultStatus.FAILED,
            score=1.0 if matched else 0.0,
            label="match" if matched else "mismatch",
        )


class ToolCallMatchMetric(_DeterministicMetric):
    """Require the observed ordered tool names to match the case exactly."""

    name = "tool_call_match"

    async def evaluate(self, context: JudgeContext) -> MetricResult:
        expected = context.case.case.expected_tool_calls
        if not expected:
            return self._result(context, status=ResultStatus.SKIPPED)
        observed = tuple(tool.name for tool in context.subject.observation.tool_calls)
        matched = observed == expected
        return self._result(
            context,
            status=ResultStatus.PASSED if matched else ResultStatus.FAILED,
            score=1.0 if matched else 0.0,
            label="match" if matched else "mismatch",
        )


class TerminalSuccessMetric(_DeterministicMetric):
    """Score the immutable target observation's terminal status."""

    name = "terminal_success"

    async def evaluate(self, context: JudgeContext) -> MetricResult:
        succeeded = context.subject.observation.status is ObservationStatus.OK
        return self._result(
            context,
            status=ResultStatus.PASSED if succeeded else ResultStatus.FAILED,
            score=1.0 if succeeded else 0.0,
            label="success" if succeeded else "not_successful",
        )


def builtin_metrics() -> dict[str, _DeterministicMetric]:
    """Return fresh stateless built-ins for runner or CLI composition."""
    metrics = (ExactMatchMetric(), TerminalSuccessMetric(), ToolCallMatchMetric())
    return {metric.name: metric for metric in metrics}


__all__ = [
    "ExactMatchMetric",
    "TerminalSuccessMetric",
    "ToolCallMatchMetric",
    "builtin_metrics",
]
