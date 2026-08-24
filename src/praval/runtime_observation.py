"""Runtime observation scopes shared by Praval execution boundaries.

This module deliberately depends only on the OpenTelemetry API and the frozen
provider-neutral observation models.  Runtime instrumentation remains useful
with no configured telemetry SDK, exporter, or evaluation consumer.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Iterator, Literal, Mapping

from opentelemetry.trace import INVALID_SPAN, Span, SpanKind, Status, StatusCode

from praval.models.observation import (
    NOOP_OBSERVATION_RECORDER,
    ContentKind,
    ContentReference,
    ExecutionObservation,
    HITLDecisionObservation,
    ObservationFactStatus,
    ObservationKind,
    ObservationPrivacy,
    ObservationRecorder,
    ObservationStatus,
    ReefHandoffObservation,
    RetryObservation,
    TokenUsageObservation,
    ToolCallObservation,
)

logger = logging.getLogger(__name__)

_recorder_override: ContextVar[ObservationRecorder | None] = ContextVar(
    "praval_observation_recorder", default=None
)
_state_stack: ContextVar[tuple["_ObservationState", ...]] = ContextVar(
    "praval_observation_states", default=()
)
_tool_call_depth: ContextVar[int] = ContextVar("praval_tool_call_depth", default=0)
_default_recorder: ObservationRecorder = NOOP_OBSERVATION_RECORDER
_recorder_lock = threading.RLock()


def _bounded_string(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    normalized = str(value)
    return normalized[:limit] or None


class CompositeObservationRecorder:
    """Fan completed observations out to independent consumers safely."""

    def __init__(self, *recorders: ObservationRecorder) -> None:
        self._recorders = tuple(recorders)

    def record(self, observation: ExecutionObservation) -> None:
        """Offer the observation to every recorder, isolating each failure."""
        for recorder in self._recorders:
            _safe_record(recorder, observation)


def configure_observation_recorder(
    recorder: ObservationRecorder | None,
) -> ObservationRecorder:
    """Set the process-default observation consumer and return its predecessor."""
    global _default_recorder
    replacement = recorder or NOOP_OBSERVATION_RECORDER
    with _recorder_lock:
        previous = _default_recorder
        _default_recorder = replacement
    return previous


@contextmanager
def use_observation_recorder(
    recorder: ObservationRecorder,
) -> Iterator[ObservationRecorder]:
    """Use a recorder for the current synchronous or asynchronous context."""
    token = _recorder_override.set(recorder)
    try:
        yield recorder
    finally:
        _recorder_override.reset(token)


def _current_recorder() -> ObservationRecorder:
    return _recorder_override.get() or _default_recorder


def _safe_record(
    recorder: ObservationRecorder, observation: ExecutionObservation
) -> None:
    try:
        recorder.record(observation)
    except Exception as exc:  # observation consumers cannot break applications
        logger.warning("Observation recorder failed: %s", exc)


def _get_tracer() -> Any:
    """Resolve telemetry lazily so core runtime imports remain acyclic."""
    from praval.observability.lifecycle import get_tracer

    return get_tracer("praval.runtime")


def _emit_observation_signals(observation: ExecutionObservation) -> None:
    """Offer one completed observation to bounded telemetry signals safely."""
    try:
        from praval.observability.signals import emit_execution_observation

        emit_execution_observation(observation)
    except Exception as telemetry_error:
        logger.warning("Observation signal emission failed: %s", telemetry_error)


@dataclass
class _ObservationState:
    observation_id: str
    run_id: str
    kind: ObservationKind
    started_at: datetime
    started_monotonic: float
    recorder: ObservationRecorder
    agent_id: str | None = None
    agent_name: str | None = None
    workflow_id: str | None = None
    workflow_name: str | None = None
    conversation_id: str | None = None
    response_id: str | None = None
    provider: str | None = None
    model: str | None = None
    request_mode: str | None = None
    terminal_outcome: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int = 0
    has_usage: bool = False
    tool_calls: list[ToolCallObservation] = field(default_factory=list)
    retries: list[RetryObservation] = field(default_factory=list)
    hitl_decisions: list[HITLDecisionObservation] = field(default_factory=list)
    handoffs: list[ReefHandoffObservation] = field(default_factory=list)
    content_references: list[ContentReference] = field(default_factory=list)
    privacy: ObservationPrivacy = field(default_factory=ObservationPrivacy)
    forced_status: ObservationStatus | None = None
    forced_error_type: str | None = None
    span: Span | None = None
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def matches(
        self,
        kind: ObservationKind,
        *,
        agent_id: str | None,
        agent_name: str | None,
        workflow_id: str | None,
        workflow_name: str | None,
    ) -> bool:
        if self.kind is not kind:
            return False
        if kind is ObservationKind.AGENT:
            return bool(
                (agent_id and self.agent_id == agent_id)
                or (agent_name and self.agent_name == agent_name)
            )
        return bool(
            (workflow_id and self.workflow_id == workflow_id)
            or (workflow_name and self.workflow_name == workflow_name)
        )


class ObservationScope:
    """Create or join one real agent/workflow observation boundary."""

    def __init__(
        self,
        *,
        kind: ObservationKind,
        run_id: str | None = None,
        agent_id: str | None = None,
        agent_name: str | None = None,
        workflow_id: str | None = None,
        workflow_name: str | None = None,
        conversation_id: str | None = None,
        request_mode: str | None = None,
        privacy: ObservationPrivacy | None = None,
    ) -> None:
        if kind is ObservationKind.AGENT and not (agent_id or agent_name):
            raise ValueError("agent observation scopes require agent identity")
        if kind is ObservationKind.WORKFLOW and not (workflow_id or workflow_name):
            raise ValueError("workflow observation scopes require workflow identity")
        self._kind = kind
        self._run_id = run_id or str(uuid.uuid4())
        self._run_id = _bounded_string(self._run_id, 256) or str(uuid.uuid4())
        self._agent_id = _bounded_string(agent_id, 256)
        self._agent_name = _bounded_string(agent_name, 256)
        self._workflow_id = _bounded_string(workflow_id, 256)
        self._workflow_name = _bounded_string(workflow_name, 256)
        self._conversation_id = _bounded_string(conversation_id, 256)
        self._request_mode = _bounded_string(request_mode, 128)
        self._privacy = privacy or ObservationPrivacy()
        self._state: _ObservationState | None = None
        self._token: Token[tuple[_ObservationState, ...]] | None = None
        self._span_manager: Any = None
        self._owns_scope = False

    @property
    def run_id(self) -> str:
        """Return the effective run identity, including when joining a scope."""
        return self._state.run_id if self._state else self._run_id

    @property
    def owns_scope(self) -> bool:
        """Return whether this instance created the observation."""
        return self._owns_scope

    def __enter__(self) -> "ObservationScope":
        stack = _state_stack.get()
        for state in reversed(stack):
            if state.matches(
                self._kind,
                agent_id=self._agent_id,
                agent_name=self._agent_name,
                workflow_id=self._workflow_id,
                workflow_name=self._workflow_name,
            ):
                self._state = state
                return self

        now = datetime.now(timezone.utc)
        state = _ObservationState(
            observation_id=str(uuid.uuid4()),
            run_id=self._run_id,
            kind=self._kind,
            started_at=now,
            started_monotonic=time.perf_counter(),
            recorder=_current_recorder(),
            agent_id=self._agent_id,
            agent_name=self._agent_name,
            workflow_id=self._workflow_id,
            workflow_name=self._workflow_name,
            conversation_id=self._conversation_id,
            request_mode=self._request_mode,
            privacy=self._privacy,
        )
        span_name = (
            "praval.agent.invoke"
            if self._kind is ObservationKind.AGENT
            else "praval.workflow.invoke"
        )
        attributes = _identity_attributes(state)
        try:
            self._span_manager = _get_tracer().start_as_current_span(
                span_name,
                kind=SpanKind.INTERNAL,
                attributes=attributes,
                record_exception=True,
                set_status_on_exception=True,
            )
            state.span = self._span_manager.__enter__()
        except Exception as telemetry_error:
            logger.warning("Observation root span failed: %s", telemetry_error)
            self._span_manager = _NoOpSpanManager()
            state.span = self._span_manager.__enter__()
        self._state = state
        self._token = _state_stack.set((*stack, state))
        self._owns_scope = True
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> Literal[False]:
        if not self._owns_scope or self._state is None:
            return False
        state = self._state
        if self._token is not None:
            _state_stack.reset(self._token)

        ended_at = datetime.now(timezone.utc)
        duration_ms = max(0.0, (time.perf_counter() - state.started_monotonic) * 1000)
        status, error_type = _terminal_status(exc)
        if state.forced_status is not None:
            status = state.forced_status
            error_type = state.forced_error_type
        try:
            observation = _freeze_observation(
                state,
                ended_at=ended_at,
                duration_ms=duration_ms,
                status=status,
                error_type=error_type,
            )
            _finish_span(state.span, observation)
            _emit_observation_signals(observation)
            _safe_record(state.recorder, observation)
        except Exception as observation_error:
            logger.warning("Observation finalization failed: %s", observation_error)
        if self._span_manager is not None:
            try:
                self._span_manager.__exit__(exc_type, exc, traceback)
            except Exception as telemetry_error:
                logger.warning(
                    "Observation root span close failed: %s", telemetry_error
                )
        return False


def _identity_attributes(state: _ObservationState) -> dict[str, str]:
    attributes = {
        "praval.observation.id": state.observation_id,
        "praval.run.id": state.run_id,
        "praval.observation.kind": state.kind.value,
    }
    for key, value in (
        ("praval.agent.id", state.agent_id),
        ("praval.agent.name", state.agent_name),
        ("praval.workflow.id", state.workflow_id),
        ("praval.workflow.name", state.workflow_name),
        ("praval.conversation.id", state.conversation_id),
        ("praval.request.mode", state.request_mode),
    ):
        if value is not None:
            attributes[key] = value
    return attributes


def _terminal_status(exc: BaseException | None) -> tuple[ObservationStatus, str | None]:
    if exc is None:
        return ObservationStatus.OK, None
    if isinstance(exc, (asyncio.CancelledError, GeneratorExit)):
        return ObservationStatus.CANCELLED, type(exc).__name__
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return ObservationStatus.TIMEOUT, type(exc).__name__
    return ObservationStatus.ERROR, type(exc).__name__


def _freeze_observation(
    state: _ObservationState,
    *,
    ended_at: datetime,
    duration_ms: float,
    status: ObservationStatus,
    error_type: str | None,
) -> ExecutionObservation:
    with state.lock:
        usage = None
        if state.has_usage:
            total = max(state.total_tokens, state.input_tokens + state.output_tokens)
            usage = TokenUsageObservation(
                input_tokens=state.input_tokens,
                output_tokens=state.output_tokens,
                reasoning_tokens=state.reasoning_tokens,
                cache_read_tokens=state.cache_read_tokens,
                cache_write_tokens=state.cache_write_tokens,
                total_tokens=total,
            )
        trace_id, span_id = _span_ids(state.span)
        return ExecutionObservation(
            observation_id=state.observation_id,
            run_id=state.run_id,
            kind=state.kind,
            conversation_id=state.conversation_id,
            response_id=state.response_id,
            agent_id=state.agent_id,
            agent_name=state.agent_name,
            workflow_id=state.workflow_id,
            workflow_name=state.workflow_name,
            started_at=state.started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
            status=status,
            error_type=error_type,
            terminal_outcome=state.terminal_outcome,
            provider=state.provider,
            model=state.model,
            request_mode=state.request_mode,
            usage=usage,
            tool_calls=tuple(state.tool_calls[:128]),
            retries=tuple(state.retries[:32]),
            hitl_decisions=tuple(state.hitl_decisions[:32]),
            handoffs=tuple(state.handoffs[:128]),
            content_references=tuple(state.content_references[:128]),
            privacy=state.privacy,
            trace_id=trace_id,
            span_id=span_id,
        )


def _span_ids(span: Span | None) -> tuple[str | None, str | None]:
    if span is None:
        return None, None
    try:
        context = span.get_span_context()
    except Exception as telemetry_error:
        logger.warning("Observation span identity failed: %s", telemetry_error)
        return None, None
    if not context.is_valid:
        return None, None
    return f"{context.trace_id:032x}", f"{context.span_id:016x}"


def _finish_span(span: Span | None, observation: ExecutionObservation) -> None:
    try:
        _finish_span_unisolated(span, observation)
    except Exception as telemetry_error:
        logger.warning("Observation span enrichment failed: %s", telemetry_error)


def _finish_span_unisolated(
    span: Span | None, observation: ExecutionObservation
) -> None:
    if span is None or not span.is_recording():
        return
    span.set_attribute("praval.observation.status", observation.status.value)
    span.set_attribute("praval.duration_ms", observation.duration_ms)
    if observation.error_type:
        span.set_attribute("error.type", observation.error_type)
    if observation.provider:
        span.set_attribute("gen_ai.provider.name", observation.provider)
    if observation.model:
        span.set_attribute("gen_ai.request.model", observation.model)
    if observation.response_id:
        span.set_attribute("gen_ai.response.id", observation.response_id)
    if observation.terminal_outcome:
        span.set_attribute(
            "gen_ai.response.finish_reasons", (observation.terminal_outcome,)
        )
    if observation.usage:
        span.set_attribute("gen_ai.usage.input_tokens", observation.usage.input_tokens)
        span.set_attribute(
            "gen_ai.usage.output_tokens", observation.usage.output_tokens
        )
        span.set_attribute("praval.usage.total_tokens", observation.usage.total_tokens)
    if observation.status is ObservationStatus.OK:
        span.set_status(Status(StatusCode.OK))
    else:
        span.set_status(Status(StatusCode.ERROR, observation.error_type or "failure"))


def _active_states() -> tuple[_ObservationState, ...]:
    return _state_stack.get()


def has_active_observation() -> bool:
    """Return whether the current context is aggregating an observation."""
    return bool(_active_states())


def mark_observation_error(error: BaseException) -> None:
    """Mark active boundaries failed when an application policy handles an error."""
    status, error_type = _terminal_status(error)
    for state in _active_states():
        with state.lock:
            state.forced_status = status
            state.forced_error_type = error_type


def record_model_facts(
    *,
    provider: str | None = None,
    model: str | None = None,
    response_id: str | None = None,
    request_mode: str | None = None,
    terminal_outcome: str | None = None,
    usage: Any = None,
) -> None:
    """Aggregate one model call into every active agent/workflow boundary."""
    try:
        normalized_usage = _normalize_usage(usage)
    except Exception as normalization_error:
        logger.warning("Model usage normalization failed: %s", normalization_error)
        normalized_usage = None
    for state in _active_states():
        with state.lock:
            state.provider = _merge_identity(state.provider, provider, 256)
            state.model = _merge_identity(state.model, model, 512)
            state.response_id = _bounded_string(response_id, 256) or state.response_id
            state.request_mode = (
                _bounded_string(request_mode, 128) or state.request_mode
            )
            state.terminal_outcome = (
                _bounded_string(terminal_outcome, 256) or state.terminal_outcome
            )
            if normalized_usage is not None:
                state.has_usage = True
                state.input_tokens += normalized_usage.input_tokens
                state.output_tokens += normalized_usage.output_tokens
                state.reasoning_tokens += normalized_usage.reasoning_tokens
                state.cache_read_tokens += normalized_usage.cache_read_tokens
                state.cache_write_tokens += normalized_usage.cache_write_tokens
                state.total_tokens += normalized_usage.total_tokens


def _merge_identity(
    current: str | None, incoming: str | None, limit: int
) -> str | None:
    normalized = _bounded_string(incoming, limit)
    if normalized is None:
        return current
    if current is None or current == normalized:
        return normalized
    return "multiple"


def _normalize_usage(usage: Any) -> TokenUsageObservation | None:
    if usage is None:
        return None
    if isinstance(usage, TokenUsageObservation):
        return usage
    if hasattr(usage, "model_dump"):
        data = usage.model_dump()
    elif isinstance(usage, Mapping):
        data = dict(usage)
    else:
        data = {
            name: getattr(usage, name)
            for name in (
                "input_tokens",
                "prompt_tokens",
                "output_tokens",
                "completion_tokens",
                "reasoning_tokens",
                "cache_read_tokens",
                "cache_write_tokens",
                "total_tokens",
            )
            if hasattr(usage, name)
        }
    aliases = {
        "input_tokens": ("input_tokens", "prompt_tokens"),
        "output_tokens": ("output_tokens", "completion_tokens"),
        "reasoning_tokens": ("reasoning_tokens",),
        "cache_read_tokens": ("cache_read_tokens",),
        "cache_write_tokens": ("cache_write_tokens",),
        "total_tokens": ("total_tokens",),
    }
    normalized: dict[str, int] = {}
    for target, names in aliases.items():
        value = next((data[name] for name in names if data.get(name) is not None), 0)
        normalized[target] = max(0, int(value))
    normalized["total_tokens"] = max(
        normalized["total_tokens"],
        normalized["input_tokens"] + normalized["output_tokens"],
    )
    return TokenUsageObservation(**normalized)


def record_tool_call(fact: ToolCallObservation) -> None:
    """Aggregate a bounded tool/MCP call fact into active observations."""
    for state in _active_states():
        with state.lock:
            if len(state.tool_calls) < 128:
                state.tool_calls.append(fact)


class ToolCallScope:
    """Trace one tool boundary and aggregate only the outer real invocation."""

    def __init__(
        self,
        *,
        tool_call_id: str,
        name: str,
        arguments: Any = None,
        span_name: str = "tool.invoke",
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        self.tool_call_id = _bounded_string(tool_call_id, 256) or str(uuid.uuid4())
        self.name = _bounded_string(name, 256) or "unknown_tool"
        self.arguments = arguments
        self.span_name = span_name
        self.attributes = attributes
        self._started = 0.0
        self._token: Token[int] | None = None
        self._span_manager: Any = None
        self._span: Span | None = None
        self._owns_fact = False
        self._result: Any = None
        self._is_error = False
        self._error_type: str | None = None
        self._skip = False

    def __enter__(self) -> "ToolCallScope":
        depth = _tool_call_depth.get()
        self._owns_fact = depth == 0
        self._token = _tool_call_depth.set(depth + 1)
        self._started = time.perf_counter()
        span_attributes = {
            "gen_ai.tool.name": self.name,
            "gen_ai.tool.call.id": self.tool_call_id,
            **dict(self.attributes or {}),
        }
        self._span_manager = operation_span(
            self.span_name,
            attributes=span_attributes,
        )
        self._span = self._span_manager.__enter__()
        if self._owns_fact and self.arguments is not None:
            record_content_reference(ContentKind.TOOL_ARGUMENTS, self.arguments)
        return self

    def set_result(
        self,
        result: Any,
        *,
        is_error: bool = False,
        error_type: str | None = None,
        tool_call_id: str | None = None,
    ) -> None:
        """Attach the normalized result before leaving the scope."""
        self._result = result
        self._is_error = is_error
        self._error_type = error_type
        if tool_call_id:
            self.tool_call_id = _bounded_string(tool_call_id, 256) or self.tool_call_id

    def skip_fact(self) -> None:
        """Skip completion facts for a suspended call that did not execute."""
        self._skip = True

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> Literal[False]:
        if self._token is not None:
            _tool_call_depth.reset(self._token)
        if self._owns_fact and not self._skip:
            try:
                duration_ms = max(0.0, (time.perf_counter() - self._started) * 1000)
                status, derived_error_type = _tool_status(exc, self._is_error)
                error_type = self._error_type or derived_error_type
                record_tool_call(
                    ToolCallObservation(
                        tool_call_id=self.tool_call_id,
                        name=self.name,
                        status=status,
                        duration_ms=duration_ms,
                        error_type=_bounded_string(error_type, 256),
                    )
                )
                if self._result is not None:
                    record_content_reference(ContentKind.TOOL_RESULT, self._result)
                if self._span is not None and self._span.is_recording():
                    self._span.set_attribute("praval.tool.status", status.value)
                    self._span.set_attribute("praval.duration_ms", duration_ms)
                    if error_type:
                        self._span.set_attribute("error.type", error_type)
                    if status is ObservationFactStatus.OK:
                        self._span.set_status(Status(StatusCode.OK))
                    else:
                        self._span.set_status(
                            Status(StatusCode.ERROR, error_type or status.value)
                        )
            except Exception as observation_error:
                logger.warning("Tool observation failed: %s", observation_error)
        if self._span_manager is not None:
            try:
                self._span_manager.__exit__(exc_type, exc, traceback)
            except Exception as telemetry_error:
                logger.warning("Tool span close failed: %s", telemetry_error)
        return False


def _tool_status(
    exc: BaseException | None, is_error: bool
) -> tuple[ObservationFactStatus, str | None]:
    if isinstance(exc, (asyncio.CancelledError, GeneratorExit)):
        return ObservationFactStatus.CANCELLED, type(exc).__name__
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return ObservationFactStatus.TIMEOUT, type(exc).__name__
    if exc is not None:
        return ObservationFactStatus.ERROR, type(exc).__name__
    if is_error:
        return ObservationFactStatus.ERROR, "ToolResultError"
    return ObservationFactStatus.OK, None


def record_retry(fact: RetryObservation) -> None:
    """Aggregate a retry fact into active observations."""
    for state in _active_states():
        with state.lock:
            if len(state.retries) < 32:
                state.retries.append(fact)


def record_hitl_decision(fact: HITLDecisionObservation) -> None:
    """Aggregate a human decision into active observations."""
    for state in _active_states():
        with state.lock:
            if len(state.hitl_decisions) < 32:
                state.hitl_decisions.append(fact)


def record_handoff(fact: ReefHandoffObservation) -> None:
    """Aggregate a Reef handoff into active observations."""
    for state in _active_states():
        with state.lock:
            if len(state.handoffs) < 128:
                state.handoffs.append(fact)


def record_content_reference(
    kind: ContentKind,
    content: Any,
    *,
    media_type: str | None = None,
    reference: str | None = None,
) -> ContentReference:
    """Hash sensitive content and attach only its safe reference and size."""
    payload = _content_bytes(content)
    fact = ContentReference(
        kind=kind,
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        reference=_bounded_string(reference, 2048),
        media_type=_bounded_string(media_type, 256),
    )
    for state in _active_states():
        with state.lock:
            if len(state.content_references) < 128:
                state.content_references.append(fact)
    return fact


def _content_bytes(content: Any) -> bytes:
    try:
        return _content_bytes_unchecked(content)
    except Exception as content_error:
        logger.warning("Content reference serialization failed: %s", content_error)
        return f"<unavailable:{type(content).__name__}>".encode("utf-8")


def _content_bytes_unchecked(content: Any) -> bytes:
    if isinstance(content, bytes):
        return content
    if isinstance(content, bytearray):
        return bytes(content)
    if isinstance(content, str):
        return content.encode("utf-8")
    if hasattr(content, "model_dump"):
        content = content.model_dump(mode="json")
    return json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


@contextmanager
def operation_span(
    name: str,
    *,
    attributes: Mapping[str, Any] | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
) -> Iterator[Span]:
    """Trace a lower-level runtime operation without creating an observation."""
    clean_attributes = {
        key: value for key, value in (attributes or {}).items() if value is not None
    }
    try:
        manager = _get_tracer().start_as_current_span(
            name,
            kind=kind,
            attributes=clean_attributes,
            record_exception=True,
            set_status_on_exception=True,
        )
        span = manager.__enter__()
    except Exception as telemetry_error:
        logger.warning("Operation span start failed: %s", telemetry_error)
        yield INVALID_SPAN
        return
    try:
        yield span
    except BaseException:
        exception_info = sys.exc_info()
        try:
            manager.__exit__(*exception_info)
        except Exception as telemetry_error:
            logger.warning("Operation span close failed: %s", telemetry_error)
        raise
    else:
        try:
            manager.__exit__(None, None, None)
        except Exception as telemetry_error:
            logger.warning("Operation span close failed: %s", telemetry_error)


class _NoOpSpanManager:
    def __enter__(self) -> Span:
        return INVALID_SPAN

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> Literal[False]:
        return False


def trace_operation(name: str) -> Any:
    """Decorate a sync or async lower-level runtime operation with a span."""

    def decorator(func: Any) -> Any:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with operation_span(name):
                    return await func(*args, **kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with operation_span(name):
                return func(*args, **kwargs)

        return sync_wrapper

    return decorator


__all__ = [
    "CompositeObservationRecorder",
    "ObservationScope",
    "ToolCallScope",
    "configure_observation_recorder",
    "has_active_observation",
    "mark_observation_error",
    "operation_span",
    "record_content_reference",
    "record_handoff",
    "record_hitl_decision",
    "record_model_facts",
    "record_retry",
    "record_tool_call",
    "trace_operation",
    "use_observation_recorder",
]
