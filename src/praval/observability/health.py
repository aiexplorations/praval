"""Thread-safe health accounting around official OpenTelemetry pipelines."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from opentelemetry.sdk._logs.export import (
    LogRecordExporter,
    LogRecordExportResult,
)
from opentelemetry.sdk.metrics.export import MetricExporter, MetricExportResult
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

logger = logging.getLogger(__name__)

_SIGNALS = ("traces", "metrics", "logs")
_health_lock = threading.RLock()


@dataclass(frozen=True)
class TelemetryHealth:
    """One immutable, bounded health snapshot for an OTel signal."""

    export_attempts: int = 0
    exported_items: int = 0
    export_failures: int = 0
    export_exceptions: int = 0
    dropped_items: int = 0
    queue_depth: int = 0
    queue_capacity: int = 0
    lifecycle_failures: int = 0


@dataclass
class _MutableTelemetryHealth:
    export_attempts: int = 0
    exported_items: int = 0
    export_failures: int = 0
    export_exceptions: int = 0
    dropped_items: int = 0
    queue_depth: int = 0
    queue_capacity: int = 0
    lifecycle_failures: int = 0

    def snapshot(self) -> TelemetryHealth:
        return TelemetryHealth(**vars(self))


_health = {signal: _MutableTelemetryHealth() for signal in _SIGNALS}


def _signal_health(signal: str) -> _MutableTelemetryHealth:
    if signal not in _health:
        raise ValueError(f"unsupported telemetry signal: {signal}")
    return _health[signal]


def reset_telemetry_health() -> None:
    """Reset counters when an explicit Praval pipeline is reconfigured."""
    with _health_lock:
        for signal in _SIGNALS:
            _health[signal] = _MutableTelemetryHealth()


def get_telemetry_health() -> Mapping[str, TelemetryHealth]:
    """Return immutable copies of current per-signal health counters."""
    with _health_lock:
        return {signal: _health[signal].snapshot() for signal in _SIGNALS}


def _record_export(
    signal: str,
    item_count: int,
    *,
    success: bool,
    exception: bool = False,
) -> None:
    with _health_lock:
        health = _signal_health(signal)
        health.export_attempts += 1
        if success:
            health.exported_items += max(0, item_count)
        else:
            health.export_failures += 1
        if exception:
            health.export_exceptions += 1


def _record_queue(signal: str, depth: int, capacity: int, *, dropped: bool) -> None:
    with _health_lock:
        health = _signal_health(signal)
        health.queue_depth = max(0, depth)
        health.queue_capacity = max(0, capacity)
        if dropped:
            health.dropped_items += 1


def record_lifecycle_failure(signal: str) -> None:
    """Record a failed flush or shutdown without raising on the app path."""
    with _health_lock:
        _signal_health(signal).lifecycle_failures += 1


def _warn_export_failure(signal: str, *, exception: bool) -> None:
    logger.warning(
        "OpenTelemetry export failed",
        extra={
            "event_name": "praval.telemetry.export.failed",
            "praval.telemetry.signal": signal,
            "praval.telemetry.exception": exception,
        },
    )


class TrackingSpanExporter(SpanExporter):
    """Count and isolate results from an official span exporter."""

    def __init__(self, signal: str, exporter: Any) -> None:
        self._signal = signal
        self._exporter = exporter

    def export(self, spans: Sequence[Any]) -> SpanExportResult:
        try:
            result = self._exporter.export(spans)
        except Exception:
            _record_export(self._signal, len(spans), success=False, exception=True)
            _warn_export_failure(self._signal, exception=True)
            return SpanExportResult.FAILURE
        success = result is SpanExportResult.SUCCESS
        _record_export(self._signal, len(spans), success=success)
        if not success:
            _warn_export_failure(self._signal, exception=False)
            return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        try:
            return bool(self._exporter.force_flush(timeout_millis))
        except Exception:
            record_lifecycle_failure(self._signal)
            return False

    def shutdown(self) -> None:
        try:
            self._exporter.shutdown()
        except Exception:
            record_lifecycle_failure(self._signal)


class TrackingMetricExporter(MetricExporter):
    """Count and isolate results from an official metric exporter."""

    def __init__(self, signal: str, exporter: Any) -> None:
        super().__init__(
            preferred_temporality=getattr(exporter, "_preferred_temporality", None),
            preferred_aggregation=getattr(exporter, "_preferred_aggregation", None),
        )
        self._signal = signal
        self._exporter = exporter

    def export(
        self,
        metrics_data: Any,
        timeout_millis: float = 10000,
        **kwargs: Any,
    ) -> MetricExportResult:
        try:
            result = self._exporter.export(
                metrics_data, timeout_millis=timeout_millis, **kwargs
            )
        except Exception:
            _record_export(self._signal, 1, success=False, exception=True)
            _warn_export_failure(self._signal, exception=True)
            return MetricExportResult.FAILURE
        success = result is MetricExportResult.SUCCESS
        _record_export(self._signal, 1, success=success)
        if not success:
            _warn_export_failure(self._signal, exception=False)
            return MetricExportResult.FAILURE
        return MetricExportResult.SUCCESS

    def force_flush(self, timeout_millis: float = 10000) -> bool:
        try:
            return bool(self._exporter.force_flush(timeout_millis))
        except Exception:
            record_lifecycle_failure(self._signal)
            return False

    def shutdown(self, timeout_millis: float = 30000, **kwargs: Any) -> None:
        try:
            self._exporter.shutdown(timeout_millis=timeout_millis, **kwargs)
        except Exception:
            record_lifecycle_failure(self._signal)


class TrackingLogExporter(LogRecordExporter):
    """Count and isolate results from an official log exporter."""

    def __init__(self, signal: str, exporter: Any) -> None:
        self._signal = signal
        self._exporter = exporter

    def export(self, batch: Sequence[Any]) -> LogRecordExportResult:
        try:
            result = self._exporter.export(batch)
        except Exception:
            _record_export(self._signal, len(batch), success=False, exception=True)
            _warn_export_failure(self._signal, exception=True)
            return LogRecordExportResult.FAILURE
        success = result is LogRecordExportResult.SUCCESS
        _record_export(self._signal, len(batch), success=success)
        if not success:
            _warn_export_failure(self._signal, exception=False)
            return LogRecordExportResult.FAILURE
        return LogRecordExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 10000) -> bool:
        try:
            return bool(self._exporter.force_flush(timeout_millis))
        except Exception:
            record_lifecycle_failure(self._signal)
            return False

    def shutdown(self) -> None:
        try:
            self._exporter.shutdown()
        except Exception:
            record_lifecycle_failure(self._signal)


def tracking_exporter(signal: str, exporter: Any) -> Any:
    """Wrap an exporter using the signal-specific official SDK contract."""
    if signal == "traces":
        return TrackingSpanExporter(signal, exporter)
    if signal == "metrics":
        return TrackingMetricExporter(signal, exporter)
    if signal == "logs":
        return TrackingLogExporter(signal, exporter)
    raise ValueError(f"unsupported telemetry signal: {signal}")


class _TrackingProcessor:
    """Observe an official batch processor's bounded queue before delegation."""

    def __init__(self, signal: str, processor: Any) -> None:
        self._signal = signal
        self._processor = processor

    def _queue_state(self) -> tuple[int, int]:
        batch = self._processor._batch_processor
        return len(batch._queue), int(batch._max_queue_size)

    def _before_emit(self) -> None:
        depth, capacity = self._queue_state()
        batch = self._processor._batch_processor
        _record_queue(
            self._signal,
            depth,
            capacity,
            dropped=(
                not getattr(batch, "_shutdown", False)
                and capacity > 0
                and depth >= capacity
            ),
        )

    def _after_emit(self) -> None:
        depth, capacity = self._queue_state()
        _record_queue(self._signal, depth, capacity, dropped=False)

    def force_flush(self, timeout_millis: int | None = None) -> bool:
        result = bool(self._processor.force_flush(timeout_millis))
        self._after_emit()
        return result

    def shutdown(self) -> Any:
        return self._processor.shutdown()


class TrackingSpanProcessor(_TrackingProcessor):
    """Track queue pressure while delegating to ``BatchSpanProcessor``."""

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        self._processor.on_start(span, parent_context=parent_context)

    def _on_ending(self, span: Any) -> None:
        callback = getattr(self._processor, "_on_ending", None)
        if callback is not None:
            callback(span)

    def on_end(self, span: Any) -> None:
        context = getattr(span, "context", ...)
        if context is None or (context is not ... and not context.trace_flags.sampled):
            self._processor.on_end(span)
            return
        self._before_emit()
        self._processor.on_end(span)
        self._after_emit()


class TrackingLogRecordProcessor(_TrackingProcessor):
    """Track queue pressure while delegating to ``BatchLogRecordProcessor``."""

    def on_emit(self, log_record: Any) -> None:
        self._before_emit()
        self._processor.on_emit(log_record)
        self._after_emit()


__all__ = [
    "TelemetryHealth",
    "TrackingLogExporter",
    "TrackingLogRecordProcessor",
    "TrackingMetricExporter",
    "TrackingSpanExporter",
    "TrackingSpanProcessor",
    "get_telemetry_health",
    "reset_telemetry_health",
    "tracking_exporter",
]
