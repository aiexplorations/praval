"""Deterministic, provider-free evaluation metrics."""

from __future__ import annotations

import inspect
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from importlib import metadata
from typing import TYPE_CHECKING, Any, Callable, Iterable, Protocol, cast

from praval.models import ObservationStatus

from .models import MetricResult, ResultStatus

if TYPE_CHECKING:
    from .runner import JudgeContext

METRIC_ENTRY_POINT_GROUP = "praval.eval.metrics"


class Metric(Protocol):  # pragma: no cover - structural declaration
    """Public contract implemented by deterministic and plugin metrics."""

    name: str
    version: str

    async def evaluate(self, context: "JudgeContext") -> MetricResult:
        """Evaluate one completed immutable subject."""
        ...


class MetricPluginError(ValueError):
    """A discovered metric plugin violates the public plugin contract."""


class _DeterministicMetric(ABC):
    name: str
    version = "1"

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @abstractmethod
    async def evaluate(self, context: "JudgeContext") -> MetricResult:
        """Evaluate one completed target subject."""

    def _result(
        self,
        context: "JudgeContext",
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

    async def evaluate(self, context: "JudgeContext") -> MetricResult:
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

    async def evaluate(self, context: "JudgeContext") -> MetricResult:
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

    async def evaluate(self, context: "JudgeContext") -> MetricResult:
        succeeded = context.subject.observation.status is ObservationStatus.OK
        return self._result(
            context,
            status=ResultStatus.PASSED if succeeded else ResultStatus.FAILED,
            score=1.0 if succeeded else 0.0,
            label="success" if succeeded else "not_successful",
        )


def builtin_metrics() -> dict[str, Metric]:
    """Return fresh stateless built-ins for runner or CLI composition."""
    metrics = (ExactMatchMetric(), TerminalSuccessMetric(), ToolCallMatchMetric())
    return {metric.name: metric for metric in metrics}


def _validate_plugin(entry_point_name: str, candidate: Any) -> Metric:
    metric = candidate
    if not hasattr(metric, "evaluate") and callable(metric):
        metric = metric()
    name = getattr(metric, "name", None)
    version = getattr(metric, "version", None)
    evaluate = getattr(metric, "evaluate", None)
    if name != entry_point_name:
        raise MetricPluginError(
            f"metric entry point {entry_point_name!r} returned name {name!r}"
        )
    if not isinstance(version, str) or not version.strip() or len(version) > 128:
        raise MetricPluginError(
            f"metric plugin {entry_point_name!r} requires a bounded version"
        )
    if not callable(evaluate) or not inspect.iscoroutinefunction(evaluate):
        raise MetricPluginError(
            f"metric plugin {entry_point_name!r} requires async evaluate()"
        )
    return cast(Metric, metric)


def discover_metric_plugins(
    entry_points: Iterable[Any] | None = None,
) -> dict[str, Metric]:
    """Load installed ``praval.eval.metrics`` entry points deterministically."""
    discovered = (
        tuple(entry_points)
        if entry_points is not None
        else tuple(metadata.entry_points(group=METRIC_ENTRY_POINT_GROUP))
    )
    plugins: dict[str, Metric] = {}
    for entry_point in sorted(discovered, key=lambda item: item.name):
        if entry_point.name in plugins:
            raise MetricPluginError(
                f"duplicate metric entry point: {entry_point.name!r}"
            )
        try:
            candidate = entry_point.load()
            plugins[entry_point.name] = _validate_plugin(entry_point.name, candidate)
        except MetricPluginError:
            raise
        except Exception as exc:
            raise MetricPluginError(
                f"unable to load metric plugin {entry_point.name!r}: "
                f"{type(exc).__name__}"
            ) from exc
    return plugins


def available_metrics(
    *, entry_points: Iterable[Any] | None = None
) -> dict[str, Metric]:
    """Combine built-ins and installed plugins without allowing shadowing."""
    available = builtin_metrics()
    for name, metric in discover_metric_plugins(entry_points).items():
        if name in available:
            raise MetricPluginError(f"metric plugin shadows a built-in: {name!r}")
        available[name] = metric
    return available


__all__ = [
    "ExactMatchMetric",
    "METRIC_ENTRY_POINT_GROUP",
    "Metric",
    "MetricPluginError",
    "TerminalSuccessMetric",
    "ToolCallMatchMetric",
    "available_metrics",
    "builtin_metrics",
    "discover_metric_plugins",
]
