"""Bounded metrics and correlated logs derived from execution observations."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import Any, Mapping

from opentelemetry._logs import SeverityNumber

from praval.models.observation import ExecutionObservation, ObservationStatus

from .lifecycle import get_logger, get_meter

_SECRET_VALUE = re.compile(r"(?i)(?:bearer\s+\S+|sk-[a-z0-9_-]{8,}|api[_-]?key\s*[=:])")
_MAX_DIMENSION_BYTES = 256
_signal_lock = threading.RLock()
_instruments: "_SignalInstruments | None" = None


@dataclass(frozen=True)
class _SignalInstruments:
    """Cached official API instruments for one configured provider set."""

    execution_invocations: Any
    execution_duration: Any
    execution_failures: Any
    token_usage: Any
    tool_invocations: Any
    tool_duration: Any
    retry_count: Any
    handoff_count: Any
    handoff_duration: Any


def reset_signal_state() -> None:
    """Forget provider-bound instruments after lifecycle reconfiguration."""
    global _instruments
    with _signal_lock:
        _instruments = None


def _get_instruments() -> _SignalInstruments:
    global _instruments
    with _signal_lock:
        if _instruments is None:
            meter = get_meter("praval.execution")
            _instruments = _SignalInstruments(
                execution_invocations=meter.create_counter(
                    "praval.execution.invocations",
                    unit="{invocation}",
                    description="Completed Praval agent and workflow invocations",
                ),
                execution_duration=meter.create_histogram(
                    "praval.execution.duration",
                    unit="ms",
                    description="Completed Praval execution duration",
                ),
                execution_failures=meter.create_counter(
                    "praval.execution.failures",
                    unit="{failure}",
                    description="Non-successful Praval executions",
                ),
                token_usage=meter.create_counter(
                    "praval.gen_ai.token.usage",
                    unit="{token}",
                    description="Model tokens used by completed Praval executions",
                ),
                tool_invocations=meter.create_counter(
                    "praval.tool.invocations",
                    unit="{invocation}",
                    description="Tool invocations within Praval executions",
                ),
                tool_duration=meter.create_histogram(
                    "praval.tool.duration",
                    unit="ms",
                    description="Tool invocation duration",
                ),
                retry_count=meter.create_counter(
                    "praval.retry.count",
                    unit="{retry}",
                    description="Retry decisions within Praval executions",
                ),
                handoff_count=meter.create_counter(
                    "praval.reef.handoff.count",
                    unit="{handoff}",
                    description="Reef handoffs within Praval executions",
                ),
                handoff_duration=meter.create_histogram(
                    "praval.reef.handoff.duration",
                    unit="ms",
                    description="Reef handoff duration",
                ),
            )
        return _instruments


def _bounded_dimension(value: str | None) -> str | None:
    if value is None:
        return None
    if _SECRET_VALUE.search(value):
        return "[REDACTED]"
    encoded = value.encode("utf-8")
    if len(encoded) <= _MAX_DIMENSION_BYTES:
        return value
    return encoded[:_MAX_DIMENSION_BYTES].decode("utf-8", errors="ignore")


def _base_attributes(observation: ExecutionObservation) -> dict[str, str]:
    attributes = {
        "praval.observation.kind": observation.kind.value,
        "praval.status": observation.status.value,
    }
    for key, value in (
        ("praval.agent.name", observation.agent_name),
        ("praval.workflow.name", observation.workflow_name),
        ("gen_ai.provider.name", observation.provider),
        ("gen_ai.request.model", observation.model),
        ("praval.request.mode", observation.request_mode),
    ):
        bounded = _bounded_dimension(value)
        if bounded is not None:
            attributes[key] = bounded
    return attributes


def _fact_attributes(
    base: Mapping[str, str],
    **values: str | None,
) -> dict[str, str]:
    attributes = dict(base)
    for key, value in values.items():
        bounded = _bounded_dimension(value)
        if bounded is not None:
            attributes[key] = bounded
    return attributes


def _record_metrics(observation: ExecutionObservation) -> None:
    instruments = _get_instruments()
    base = _base_attributes(observation)
    instruments.execution_invocations.add(1, base)
    instruments.execution_duration.record(observation.duration_ms, base)
    if observation.status is not ObservationStatus.OK:
        instruments.execution_failures.add(1, base)

    if observation.usage is not None:
        usage = observation.usage
        for token_type, value in (
            ("input", usage.input_tokens),
            ("output", usage.output_tokens),
            ("reasoning", usage.reasoning_tokens),
            ("cache_read", usage.cache_read_tokens),
            ("cache_write", usage.cache_write_tokens),
            ("total", usage.total_tokens),
        ):
            attributes = {**base, "gen_ai.token.type": token_type}
            instruments.token_usage.add(value, attributes)

    for tool in observation.tool_calls:
        attributes = _fact_attributes(
            base,
            **{
                "gen_ai.tool.name": tool.name,
                "praval.tool.status": tool.status.value,
            },
        )
        instruments.tool_invocations.add(1, attributes)
        instruments.tool_duration.record(tool.duration_ms, attributes)

    for retry in observation.retries:
        attributes = _fact_attributes(base, **{"praval.operation": retry.operation})
        instruments.retry_count.add(1, attributes)

    for handoff in observation.handoffs:
        attributes = _fact_attributes(
            base,
            **{
                "messaging.destination.name": handoff.channel,
                "praval.handoff.status": handoff.status.value,
            },
        )
        instruments.handoff_count.add(1, attributes)
        if handoff.duration_ms is not None:
            instruments.handoff_duration.record(handoff.duration_ms, attributes)


def _log_attributes(observation: ExecutionObservation) -> dict[str, Any]:
    attributes: dict[str, Any] = {
        **_base_attributes(observation),
        "praval.duration_ms": observation.duration_ms,
        "praval.tool.count": len(observation.tool_calls),
        "praval.retry.count": len(observation.retries),
        "praval.hitl.count": len(observation.hitl_decisions),
        "praval.reef.handoff.count": len(observation.handoffs),
    }
    if observation.error_type is not None:
        attributes["error.type"] = _bounded_dimension(observation.error_type)
    if observation.usage is not None:
        attributes.update(
            {
                "gen_ai.usage.input_tokens": observation.usage.input_tokens,
                "gen_ai.usage.output_tokens": observation.usage.output_tokens,
                "praval.usage.total_tokens": observation.usage.total_tokens,
            }
        )
    return attributes


def _record_log(observation: ExecutionObservation) -> None:
    severity = (
        SeverityNumber.INFO
        if observation.status is ObservationStatus.OK
        else SeverityNumber.ERROR
    )
    get_logger("praval.execution").emit(
        body="Praval execution completed",
        event_name="praval.execution.completed",
        severity_number=severity,
        severity_text=observation.status.value.upper(),
        attributes=_log_attributes(observation),
    )


def emit_execution_observation(observation: ExecutionObservation) -> None:
    """Emit bounded metrics and one correlated log for an observation."""
    _record_metrics(observation)
    _record_log(observation)


__all__ = ["emit_execution_observation"]
