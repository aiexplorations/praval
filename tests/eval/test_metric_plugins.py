"""Public metric plugin discovery and reference-extension tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from praval.eval import (
    METRIC_ENTRY_POINT_GROUP,
    MetricPluginError,
    available_metrics,
    discover_metric_plugins,
)
from praval.eval.reference_plugin import ReferenceWordOverlapMetric, create_metric

from .test_metrics import _context


@dataclass
class FakeEntryPoint:
    name: str
    value: object

    def load(self):
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


def test_reference_factory_implements_public_metric_contract() -> None:
    metric = create_metric()

    assert isinstance(metric, ReferenceWordOverlapMetric)
    assert metric.name == "reference.word_overlap"
    assert metric.version == "1"
    assert METRIC_ENTRY_POINT_GROUP == "praval.eval.metrics"


@pytest.mark.asyncio
async def test_reference_plugin_scores_through_the_public_context_contract() -> None:
    result = await create_metric().evaluate(
        _context(output="Paris is France", expected="Paris is France")
    )

    assert result.metric == "reference.word_overlap"
    assert result.status.value == "passed"
    assert result.score == 1.0

    json_result = await create_metric().evaluate(
        _context(output={"answer": "ok"}, expected={"answer": "ok"})
    )
    skipped = await create_metric().evaluate(_context(expected=None))
    assert json_result.score == 1.0
    assert skipped.status.value == "skipped"
    assert skipped.score is None


def test_discovery_accepts_factories_and_metric_instances() -> None:
    factory = FakeEntryPoint("reference.word_overlap", create_metric)
    instance = FakeEntryPoint("another.metric", create_metric())
    instance.value.name = "another.metric"

    discovered = discover_metric_plugins((instance, factory))

    assert list(discovered) == ["another.metric", "reference.word_overlap"]
    assert discovered["reference.word_overlap"].version == "1"


@pytest.mark.parametrize(
    ("entry_points", "message"),
    [
        (
            (
                FakeEntryPoint("reference.word_overlap", create_metric),
                FakeEntryPoint("reference.word_overlap", create_metric),
            ),
            "duplicate",
        ),
        (
            (FakeEntryPoint("wrong.name", create_metric),),
            "returned name",
        ),
    ],
)
def test_discovery_rejects_ambiguous_or_misnamed_plugins(
    entry_points, message: str
) -> None:
    with pytest.raises(MetricPluginError, match=message):
        discover_metric_plugins(entry_points)


def test_discovery_bounds_load_errors_without_exposing_details() -> None:
    with pytest.raises(MetricPluginError, match="RuntimeError") as raised:
        discover_metric_plugins(
            (FakeEntryPoint("unsafe", RuntimeError("secret token")),)
        )

    assert "secret token" not in str(raised.value)


def test_discovery_rejects_synchronous_metric_contract() -> None:
    class SynchronousMetric:
        name = "sync.metric"
        version = "1"

        def evaluate(self, context):
            del context
            return None

    with pytest.raises(MetricPluginError, match="async evaluate"):
        discover_metric_plugins((FakeEntryPoint("sync.metric", SynchronousMetric()),))


def test_available_metrics_prevents_builtin_shadowing() -> None:
    shadow = ReferenceWordOverlapMetric()
    shadow.name = "exact_match"

    with pytest.raises(MetricPluginError, match="shadows"):
        available_metrics(entry_points=(FakeEntryPoint("exact_match", shadow),))
