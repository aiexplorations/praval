"""Bounded metric and correlated log contracts for completed observations."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

import pytest
from opentelemetry._logs import SeverityNumber
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import (
    InMemoryLogRecordExporter,
    SimpleLogRecordProcessor,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from praval.config import AppConfig, ObservabilityConfig, PravalConfig
from praval.eval import EvaluationSubject, JudgeResult, MetricResult, ResultStatus
from praval.models import ExecutionObservation, ObservationStatus
from praval.models.observation import (
    ContentKind,
    ObservationFactStatus,
    ObservationKind,
    ObservationPrivacy,
    PrivacyMode,
    ReefHandoffObservation,
    RetryObservation,
    ToolCallObservation,
)
from praval.observability import (
    configure_observability,
    emit_evaluation_result,
    shutdown_observability,
)
from praval.observability.evaluation import OnlineEvaluationTelemetry
from praval.observability.health import TrackingSpanExporter, TrackingSpanProcessor
from praval.runtime_observation import (
    ObservationScope,
    record_content_reference,
    record_handoff,
    record_model_facts,
    record_retry,
    record_tool_call,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def _evaluation_pair(
    *,
    status: ResultStatus = ResultStatus.PASSED,
    explanation: str | None = None,
) -> tuple[JudgeResult, EvaluationSubject]:
    observation = ExecutionObservation(
        observation_id="observation-1",
        run_id="execution-1",
        kind=ObservationKind.AGENT,
        agent_name="researcher",
        response_id="response-1",
        started_at=NOW,
        ended_at=NOW,
        duration_ms=0,
        status=ObservationStatus.OK,
    )
    subject = EvaluationSubject.from_observation(
        evaluation_run_id="evaluation-1",
        case_id="case-1",
        observation=observation,
    )
    values: dict[str, Any] = {
        "evaluation_run_id": "evaluation-1",
        "case_id": "case-1",
        "subject_id": subject.subject_id,
        "judge": "quality",
        "judge_version": "1",
        "prompt_sha256": "a" * 64,
        "rubric_version": "1",
        "status": status,
        "created_at": NOW,
    }
    if status is ResultStatus.ERROR:
        values["error_type"] = "JudgeTimeoutError"
    else:
        values.update({"score": 0.95, "label": "pass"})
    if explanation is not None:
        values.update(
            {
                "explanation": explanation,
                "privacy": ObservationPrivacy(
                    mode=PrivacyMode.FULL,
                    content_captured=True,
                    byte_limit=1024,
                ),
            }
        )
    return JudgeResult.create(**values), subject


@pytest.fixture
def signal_pipeline() -> Iterator[dict[str, Any]]:
    """Configure application-owned in-memory providers for every signal."""
    trace_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider(shutdown_on_exit=False)
    tracer_provider.add_span_processor(SimpleSpanProcessor(trace_exporter))
    metric_reader = InMemoryMetricReader()
    meter_provider = MeterProvider(
        metric_readers=[metric_reader], shutdown_on_exit=False
    )
    log_exporter = InMemoryLogRecordExporter()
    logger_provider = LoggerProvider(shutdown_on_exit=False)
    logger_provider.add_log_record_processor(SimpleLogRecordProcessor(log_exporter))
    configure_observability(
        PravalConfig(
            app=AppConfig(service_name="signal-contract-test"),
            observability=ObservabilityConfig(enabled=True),
        ),
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        logger_provider=logger_provider,
    )
    try:
        yield {
            "traces": trace_exporter,
            "metrics": metric_reader,
            "logs": log_exporter,
        }
    finally:
        shutdown_observability()
        tracer_provider.shutdown()
        meter_provider.shutdown()
        logger_provider.shutdown()


def _metric_points(reader: InMemoryMetricReader) -> dict[str, list[Any]]:
    data = reader.get_metrics_data()
    assert data is not None
    points: dict[str, list[Any]] = {}
    for resource_metrics in data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                points.setdefault(metric.name, []).extend(metric.data.data_points)
    return points


def test_completed_observation_emits_bounded_metrics_and_correlated_log(
    signal_pipeline: dict[str, Any],
) -> None:
    """One aggregate observation drives matching low-cardinality signals."""
    with ObservationScope(kind=ObservationKind.AGENT, agent_name="researcher"):
        record_model_facts(
            provider="openai",
            model="gpt-test",
            request_mode="chat",
            usage={
                "input_tokens": 3,
                "output_tokens": 5,
                "reasoning_tokens": 2,
                "total_tokens": 8,
            },
        )
        record_tool_call(
            ToolCallObservation(
                tool_call_id="call-private-id",
                name="search",
                status=ObservationFactStatus.OK,
                duration_ms=4.0,
            )
        )
        record_retry(
            RetryObservation(attempt=2, operation="model.generate", backoff_ms=10)
        )
        record_handoff(
            ReefHandoffObservation(
                handoff_id="handoff-private-id",
                source_agent_id="researcher",
                target_agent_id="writer",
                channel="main",
                status=ObservationFactStatus.OK,
                duration_ms=1.5,
            )
        )

    points = _metric_points(signal_pipeline["metrics"])
    invocation = points["praval.execution.invocations"][0]
    assert invocation.value == 1
    assert invocation.attributes == {
        "praval.observation.kind": "agent",
        "praval.agent.name": "researcher",
        "gen_ai.provider.name": "openai",
        "gen_ai.request.model": "gpt-test",
        "praval.request.mode": "chat",
        "praval.status": "ok",
    }
    assert points["praval.execution.duration"][0].count == 1
    token_values = {
        point.attributes["gen_ai.token.type"]: point.value
        for point in points["praval.gen_ai.token.usage"]
    }
    assert token_values == {
        "input": 3,
        "output": 5,
        "reasoning": 2,
        "cache_read": 0,
        "cache_write": 0,
        "total": 8,
    }
    assert points["praval.tool.invocations"][0].value == 1
    assert points["praval.retry.count"][0].value == 1
    assert points["praval.reef.handoff.count"][0].value == 1

    logs = signal_pipeline["logs"].get_finished_logs()
    assert len(logs) == 1
    record = logs[0].log_record
    root = signal_pipeline["traces"].get_finished_spans()[0]
    assert record.event_name == "praval.execution.completed"
    assert record.body == "Praval execution completed"
    assert record.severity_number is SeverityNumber.INFO
    assert record.trace_id == root.context.trace_id
    assert record.span_id == root.context.span_id
    assert record.attributes["praval.status"] == "ok"
    assert record.attributes["praval.tool.count"] == 1
    assert record.attributes["praval.retry.count"] == 1
    assert record.attributes["praval.reef.handoff.count"] == 1
    assert "praval.observation.id" not in record.attributes
    assert "praval.run.id" not in record.attributes


def test_evaluation_result_event_preserves_subject_correlation(
    signal_pipeline: dict[str, Any],
) -> None:
    result, subject = _evaluation_pair()

    assert emit_evaluation_result(result, subject) is True

    record = signal_pipeline["logs"].get_finished_logs()[0].log_record
    assert record.event_name == "gen_ai.evaluation.result"
    assert record.attributes["gen_ai.evaluation.name"] == "quality"
    assert record.attributes["gen_ai.evaluation.score.value"] == 0.95
    assert record.attributes["gen_ai.evaluation.score.label"] == "pass"
    assert record.attributes["gen_ai.response.id"] == "response-1"
    assert record.attributes["praval.observation.id"] == "observation-1"
    assert record.attributes["praval.evaluation.run.id"] == "evaluation-1"
    assert record.attributes["praval.evaluation.case.id"] == "case-1"
    assert record.attributes["praval.evaluation.subject.id"] == subject.subject_id
    assert "gen_ai.evaluation.explanation" not in record.attributes

    points = _metric_points(signal_pipeline["metrics"])
    assert points["praval.evaluation.results"][0].value == 1
    assert points["praval.evaluation.score"][0].sum == 0.95


def test_metric_result_uses_the_same_event_and_score_contract(
    signal_pipeline: dict[str, Any],
) -> None:
    _, subject = _evaluation_pair()
    result = MetricResult.create(
        evaluation_run_id=subject.evaluation_run_id,
        case_id=subject.case_id,
        subject_id=subject.subject_id,
        metric="ragas.faithfulness",
        metric_version="ragas-0.4.3",
        status=ResultStatus.PASSED,
        score=0.9,
        label="measured",
        created_at=NOW,
    )

    assert emit_evaluation_result(result, subject) is True

    record = signal_pipeline["logs"].get_finished_logs()[0].log_record
    assert record.event_name == "gen_ai.evaluation.result"
    assert record.attributes["gen_ai.evaluation.name"] == "ragas.faithfulness"
    assert record.attributes["gen_ai.evaluation.score.value"] == 0.9
    points = _metric_points(signal_pipeline["metrics"])
    assert points["praval.evaluation.results"][0].value == 1
    assert points["praval.evaluation.score"][0].sum == 0.9


def test_online_evaluation_emits_queue_failure_and_post_hoc_link_signals(
    signal_pipeline: dict[str, Any],
) -> None:
    _, subject = _evaluation_pair()
    observation = subject.observation.model_copy(
        update={"trace_id": "0" * 31 + "7", "span_id": "0" * 15 + "9"}
    )
    telemetry = OnlineEvaluationTelemetry(
        suite_id="online-quality", queue_depth=lambda: 3
    )

    with telemetry.start_post_hoc_span(observation, {"praval.test": "online"}):
        pass
    telemetry.scheduled()
    telemetry.retry()
    telemetry.dropped("queue_saturated")
    telemetry.failed("JudgeTimeout")
    telemetry.completed(12.5)

    span = signal_pipeline["traces"].get_finished_spans()[0]
    assert span.parent is None
    assert len(span.links) == 1
    assert span.links[0].context.trace_id == 7
    assert span.links[0].context.span_id == 9
    events = [
        item.log_record.event_name
        for item in signal_pipeline["logs"].get_finished_logs()
    ]
    assert events == [
        "praval.evaluation.online.scheduled",
        "praval.evaluation.online.dropped",
        "praval.evaluation.online.failed",
        "praval.evaluation.online.completed",
    ]
    points = _metric_points(signal_pipeline["metrics"])
    assert points["praval.evaluation.online.scheduled"][0].value == 1
    assert points["praval.evaluation.online.retries"][0].value == 1
    assert points["praval.evaluation.online.dropped"][0].value == 1
    assert points["praval.evaluation.online.failures"][0].value == 1
    assert points["praval.evaluation.online.duration"][0].sum == 12.5
    assert points["praval.evaluation.online.queue.depth"][0].value == 3


def test_evaluation_result_is_a_noop_until_observability_is_configured() -> None:
    result, subject = _evaluation_pair()

    assert emit_evaluation_result(result, subject) is False


@pytest.mark.parametrize(
    ("result_update", "subject_update", "message"),
    [
        ({"subject_id": "wrong"}, {}, "subject identity"),
        ({"evaluation_run_id": "wrong"}, {}, "run identity"),
        ({"case_id": "wrong"}, {}, "case identity"),
    ],
)
def test_evaluation_result_rejects_correlation_drift(
    signal_pipeline: dict[str, Any],
    result_update: dict[str, Any],
    subject_update: dict[str, Any],
    message: str,
) -> None:
    result, subject = _evaluation_pair()

    with pytest.raises(ValueError, match=message):
        emit_evaluation_result(
            result.model_copy(update=result_update),
            subject.model_copy(update=subject_update),
        )


def test_evaluation_error_event_and_opted_in_explanation(
    signal_pipeline: dict[str, Any],
) -> None:
    error, subject = _evaluation_pair(status=ResultStatus.ERROR)
    explained, _ = _evaluation_pair(explanation="bounded explanation")

    emit_evaluation_result(error, subject)
    emit_evaluation_result(explained, subject)

    records = signal_pipeline["logs"].get_finished_logs()
    assert records[0].log_record.severity_number is SeverityNumber.ERROR
    assert records[0].log_record.attributes["error.type"] == "JudgeTimeoutError"
    assert (
        records[1].log_record.attributes["gen_ai.evaluation.explanation"]
        == "bounded explanation"
    )


def test_error_signals_remain_metadata_only(
    signal_pipeline: dict[str, Any],
) -> None:
    """Raw content and private IDs never enter metrics or completion logs."""
    secret = "prompt secret sk-live-do-not-export"
    with pytest.raises(ValueError, match="application failed"):
        with ObservationScope(kind=ObservationKind.AGENT, agent_name="safe-agent"):
            record_content_reference(ContentKind.PROMPT, secret)
            raise ValueError("application failed")

    points = _metric_points(signal_pipeline["metrics"])
    assert points["praval.execution.failures"][0].value == 1
    logs = signal_pipeline["logs"].get_finished_logs()
    assert len(logs) == 1
    record = logs[0].log_record
    assert record.severity_number is SeverityNumber.ERROR
    assert record.attributes["praval.status"] == "error"
    assert record.attributes["error.type"] == "ValueError"
    exported = repr(points) + repr(logs)
    assert secret not in exported
    assert "sk-live-do-not-export" not in exported


def test_export_health_uses_fixed_signal_dimensions(
    signal_pipeline: dict[str, Any],
) -> None:
    """Exporter failures and queue drops become bounded health measurements."""
    from collections import deque

    from opentelemetry.sdk.trace.export import SpanExportResult

    class Exporter:
        def export(self, spans: Any) -> SpanExportResult:
            return SpanExportResult.FAILURE

    class BatchState:
        def __init__(self) -> None:
            self._queue: deque[object] = deque([object()], maxlen=1)
            self._max_queue_size = 1

    class Processor:
        def __init__(self) -> None:
            self._batch_processor = BatchState()

        def on_end(self, span: object) -> None:
            self._batch_processor._queue.appendleft(span)

    TrackingSpanExporter("traces", Exporter()).export([object()])
    processor = TrackingSpanProcessor("traces", Processor())
    processor.on_end(object())

    points = _metric_points(signal_pipeline["metrics"])

    def trace_value(name: str) -> int:
        return next(
            point.value
            for point in points[name]
            if point.attributes == {"praval.telemetry.signal": "traces"}
        )

    assert trace_value("praval.telemetry.export.attempts") == 1
    assert trace_value("praval.telemetry.export.failures") == 1
    assert trace_value("praval.telemetry.dropped.items") == 1
    assert trace_value("praval.telemetry.queue.depth") == 1
    assert trace_value("praval.telemetry.queue.capacity") == 1
