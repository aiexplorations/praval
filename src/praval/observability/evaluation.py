"""OpenTelemetry API signals for offline and sampled online evaluation."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from typing import Any

from opentelemetry._logs import SeverityNumber
from opentelemetry.metrics import Observation as MetricObservation
from opentelemetry.trace import Link, SpanContext, TraceFlags, TraceState

from praval.models import ExecutionObservation

from .lifecycle import get_logger, get_meter, get_tracer

logger = logging.getLogger(__name__)


def post_hoc_evaluation_links(observation: ExecutionObservation) -> list[Link]:
    """Build a link to the immutable subject's original execution span."""
    if observation.trace_id is None or observation.span_id is None:
        return []
    context = SpanContext(
        trace_id=int(observation.trace_id, 16),
        span_id=int(observation.span_id, 16),
        is_remote=True,
        trace_flags=TraceFlags(0),
        trace_state=TraceState(),
    )
    return [Link(context)] if context.is_valid else []


class OnlineEvaluationTelemetry:
    """Metadata-only online evaluation instruments and post-hoc spans."""

    def __init__(
        self,
        *,
        suite_id: str,
        queue_depth: Callable[[], int],
    ) -> None:
        self.suite_id = suite_id
        meter = get_meter("praval.evaluation.online")
        self._scheduled = meter.create_counter(
            "praval.evaluation.online.scheduled", unit="{job}"
        )
        self._dropped = meter.create_counter(
            "praval.evaluation.online.dropped", unit="{job}"
        )
        self._failures = meter.create_counter(
            "praval.evaluation.online.failures", unit="{failure}"
        )
        self._retries = meter.create_counter(
            "praval.evaluation.online.retries", unit="{retry}"
        )
        self._duration = meter.create_histogram(
            "praval.evaluation.online.duration", unit="ms"
        )

        def observe_queue(options: object) -> Iterator[MetricObservation]:
            del options
            yield MetricObservation(
                queue_depth(),
                {"praval.evaluation.suite.id": self.suite_id},
            )

        self._queue_gauge = meter.create_observable_gauge(
            "praval.evaluation.online.queue.depth",
            callbacks=[observe_queue],
            unit="{job}",
        )

    def dropped(self, reason: str) -> None:
        self._dropped.add(
            1,
            {
                "praval.evaluation.suite.id": self.suite_id,
                "praval.evaluation.drop.reason": reason,
            },
        )
        self._event("praval.evaluation.online.dropped", "dropped", reason)

    def scheduled(self) -> None:
        self._scheduled.add(1, self._suite_attributes())
        self._event("praval.evaluation.online.scheduled", "scheduled")

    def retry(self) -> None:
        self._retries.add(1, self._suite_attributes())

    def failed(self, error_type: str) -> None:
        self._failures.add(
            1,
            {
                **self._suite_attributes(),
                "error.type": error_type[:256],
            },
        )
        self._event("praval.evaluation.online.failed", "failed", error_type)

    def completed(self, duration_ms: float) -> None:
        self._duration.record(
            duration_ms,
            {
                **self._suite_attributes(),
                "praval.evaluation.status": "completed",
            },
        )
        self._event("praval.evaluation.online.completed", "completed")

    def start_post_hoc_span(
        self,
        observation: ExecutionObservation,
        attributes: dict[str, str],
    ) -> Any:
        """Start a worker span linked, not parented, to the original request."""
        return get_tracer("praval.evaluation.online").start_as_current_span(
            "praval.evaluation.online",
            links=post_hoc_evaluation_links(observation),
            attributes=attributes,
        )

    def _suite_attributes(self) -> dict[str, str]:
        return {"praval.evaluation.suite.id": self.suite_id}

    def _event(
        self, event_name: str, status: str, error_type: str | None = None
    ) -> None:
        attributes = {
            **self._suite_attributes(),
            "praval.evaluation.status": status,
        }
        if error_type is not None:
            attributes["error.type"] = error_type[:256]
        try:
            get_logger("praval.evaluation.online").emit(
                body="Praval sampled online evaluation lifecycle",
                event_name=event_name,
                severity_number=(
                    SeverityNumber.ERROR
                    if error_type is not None
                    else SeverityNumber.INFO
                ),
                severity_text=status.upper(),
                attributes=attributes,
            )
        except Exception as exc:
            logger.warning(
                "Online evaluation event emission failed: %s",
                type(exc).__name__,
            )


__all__ = ["OnlineEvaluationTelemetry", "post_hoc_evaluation_links"]
