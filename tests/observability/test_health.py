"""Exporter and processor health contracts for bounded telemetry pipelines."""

from __future__ import annotations

from collections import deque
from typing import Any

import pytest
from opentelemetry.sdk._logs.export import LogRecordExportResult
from opentelemetry.sdk.metrics.export import MetricExportResult
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace import TraceFlags

from praval.observability.health import (
    TrackingLogExporter,
    TrackingLogRecordProcessor,
    TrackingMetricExporter,
    TrackingSpanExporter,
    TrackingSpanProcessor,
    get_telemetry_health,
    reset_telemetry_health,
    tracking_exporter,
)


class _SpanExporter:
    def __init__(self, result: SpanExportResult | BaseException) -> None:
        self.result = result

    def export(self, spans: Any) -> SpanExportResult:
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    def shutdown(self) -> None:
        return None


class _MetricExporter:
    _preferred_temporality = None
    _preferred_aggregation = None

    def export(
        self,
        metrics_data: Any,
        timeout_millis: float = 10000,
        **kwargs: Any,
    ) -> MetricExportResult:
        return MetricExportResult.SUCCESS

    def force_flush(self, timeout_millis: float = 10000) -> bool:
        return True

    def shutdown(self, timeout_millis: float = 30000, **kwargs: Any) -> None:
        return None


class _LogExporter:
    def export(self, batch: Any) -> LogRecordExportResult:
        return LogRecordExportResult.FAILURE

    def force_flush(self, timeout_millis: int = 10000) -> bool:
        return True

    def shutdown(self) -> None:
        return None


def setup_function() -> None:
    reset_telemetry_health()


def test_tracking_exporters_normalize_success_failure_and_exception() -> None:
    successful = TrackingSpanExporter("traces", _SpanExporter(SpanExportResult.SUCCESS))
    failed = TrackingLogExporter("logs", _LogExporter())
    exceptional = TrackingSpanExporter(
        "traces", _SpanExporter(RuntimeError("collector unavailable"))
    )
    metrics = TrackingMetricExporter("metrics", _MetricExporter())

    assert successful.export([object(), object()]) is SpanExportResult.SUCCESS
    assert failed.export([object()]) is LogRecordExportResult.FAILURE
    assert exceptional.export([object()]) is SpanExportResult.FAILURE
    assert metrics.export(object()) is MetricExportResult.SUCCESS

    health = get_telemetry_health()
    assert health["traces"].export_attempts == 2
    assert health["traces"].exported_items == 2
    assert health["traces"].export_failures == 1
    assert health["traces"].export_exceptions == 1
    assert health["logs"].export_attempts == 1
    assert health["logs"].export_failures == 1
    assert health["metrics"].exported_items == 1


def test_tracking_exporters_normalize_invalid_results_to_failure() -> None:
    class InvalidExporter:
        _preferred_temporality = None
        _preferred_aggregation = None

        def export(self, data: Any, **kwargs: Any) -> None:
            return None

    assert (
        TrackingSpanExporter("traces", InvalidExporter()).export([object()])
        is SpanExportResult.FAILURE
    )
    assert (
        TrackingMetricExporter("metrics", InvalidExporter()).export(object())
        is MetricExportResult.FAILURE
    )
    assert (
        TrackingLogExporter("logs", InvalidExporter()).export([object()])
        is LogRecordExportResult.FAILURE
    )


def test_tracking_processor_observes_bounded_queue_drop_and_depth() -> None:
    class BatchState:
        def __init__(self) -> None:
            self._queue: deque[object] = deque([object(), object()], maxlen=2)
            self._max_queue_size = 2

    class Processor:
        def __init__(self) -> None:
            self._batch_processor = BatchState()

        def on_start(self, span: object, parent_context: object = None) -> None:
            return None

        def on_end(self, span: object) -> None:
            self._batch_processor._queue.appendleft(span)

        def force_flush(self, timeout_millis: int | None = None) -> bool:
            return True

        def shutdown(self) -> None:
            return None

    processor = TrackingSpanProcessor("traces", Processor())
    processor.on_end(object())

    health = get_telemetry_health()["traces"]
    assert health.dropped_items == 1
    assert health.queue_depth == 2
    assert health.queue_capacity == 2


def test_tracking_span_processor_does_not_count_unsampled_span_as_drop() -> None:
    class BatchState:
        def __init__(self) -> None:
            self._queue: deque[object] = deque([object()], maxlen=1)
            self._max_queue_size = 1

    class Processor:
        def __init__(self) -> None:
            self._batch_processor = BatchState()

        def on_end(self, span: object) -> None:
            return None

    class Context:
        trace_flags = TraceFlags(0)

    class Span:
        context = Context()

    TrackingSpanProcessor("traces", Processor()).on_end(Span())

    health = get_telemetry_health()["traces"]
    assert health.dropped_items == 0
    assert health.queue_depth == 0


def test_health_snapshots_are_immutable_copies() -> None:
    exporter = TrackingSpanExporter("traces", _SpanExporter(SpanExportResult.SUCCESS))
    before = get_telemetry_health()["traces"]
    exporter.export([object()])
    after = get_telemetry_health()["traces"]

    assert before.export_attempts == 0
    assert after.export_attempts == 1


def test_each_exporter_isolates_export_and_lifecycle_exceptions() -> None:
    class BrokenExporter:
        _preferred_temporality = None
        _preferred_aggregation = None

        def export(self, data: Any, **kwargs: Any) -> Any:
            raise RuntimeError("export failed")

        def force_flush(self, timeout_millis: float = 10000) -> bool:
            raise RuntimeError("flush failed")

        def shutdown(self, **kwargs: Any) -> None:
            raise RuntimeError("shutdown failed")

    span = TrackingSpanExporter("traces", BrokenExporter())
    metric = TrackingMetricExporter("metrics", BrokenExporter())
    log = TrackingLogExporter("logs", BrokenExporter())

    assert span.export([object()]) is SpanExportResult.FAILURE
    assert metric.export(object()) is MetricExportResult.FAILURE
    assert log.export([object()]) is LogRecordExportResult.FAILURE
    assert span.force_flush() is False
    assert metric.force_flush() is False
    assert log.force_flush() is False
    span.shutdown()
    metric.shutdown()
    log.shutdown()

    health = get_telemetry_health()
    assert all(snapshot.export_exceptions == 1 for snapshot in health.values())
    assert all(snapshot.lifecycle_failures == 2 for snapshot in health.values())


def test_tracking_exporter_factory_rejects_unknown_signals() -> None:
    assert isinstance(
        tracking_exporter("traces", _SpanExporter(SpanExportResult.SUCCESS)),
        TrackingSpanExporter,
    )
    assert isinstance(
        tracking_exporter("metrics", _MetricExporter()), TrackingMetricExporter
    )
    assert isinstance(tracking_exporter("logs", _LogExporter()), TrackingLogExporter)
    with pytest.raises(ValueError, match="unsupported telemetry signal"):
        tracking_exporter("profiles", object())


def test_tracking_processors_delegate_lifecycle_and_span_hooks() -> None:
    class BatchState:
        def __init__(self) -> None:
            self._queue: deque[object] = deque(maxlen=2)
            self._max_queue_size = 2

    class Processor:
        def __init__(self) -> None:
            self._batch_processor = BatchState()
            self.calls: list[str] = []

        def on_start(self, span: object, parent_context: object = None) -> None:
            self.calls.append("start")

        def _on_ending(self, span: object) -> None:
            self.calls.append("ending")

        def on_end(self, span: object) -> None:
            self.calls.append("end")
            self._batch_processor._queue.appendleft(span)

        def on_emit(self, record: object) -> None:
            self.calls.append("emit")
            self._batch_processor._queue.appendleft(record)

        def force_flush(self, timeout_millis: int | None = None) -> bool:
            self.calls.append("flush")
            self._batch_processor._queue.clear()
            return True

        def shutdown(self) -> None:
            self.calls.append("shutdown")

    delegate = Processor()
    spans = TrackingSpanProcessor("traces", delegate)
    spans.on_start(object())
    spans._on_ending(object())
    spans.on_end(object())
    assert spans.force_flush(50) is True
    spans.shutdown()

    logs = TrackingLogRecordProcessor("logs", delegate)
    logs.on_emit(object())

    assert delegate.calls == ["start", "ending", "end", "flush", "shutdown", "emit"]
    assert get_telemetry_health()["traces"].queue_depth == 0
    assert get_telemetry_health()["logs"].queue_depth == 1


def test_health_registry_rejects_unknown_signal() -> None:
    with pytest.raises(ValueError, match="unsupported telemetry signal"):
        TrackingSpanExporter(
            "profiles", _SpanExporter(SpanExportResult.SUCCESS)
        ).export([object()])
