"""Bounded metric and correlated log contracts for completed observations."""

from __future__ import annotations

from collections.abc import Iterator
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
from praval.models.observation import (
    ContentKind,
    ObservationFactStatus,
    ObservationKind,
    ReefHandoffObservation,
    RetryObservation,
    ToolCallObservation,
)
from praval.observability import configure_observability, shutdown_observability
from praval.runtime_observation import (
    ObservationScope,
    record_content_reference,
    record_handoff,
    record_model_facts,
    record_retry,
    record_tool_call,
)


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
