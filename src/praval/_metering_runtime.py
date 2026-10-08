"""Internal per-request metering and per-invocation response aggregation."""

from __future__ import annotations

import inspect
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, Iterator, List, Optional, TypeVar, cast

from .metering import ModelCall, UsageMeter, _correlation, _tracked
from .models import ModelEvent, ModelResponse, Usage
from .runtime_observation import _active_states, record_model_facts

_F = TypeVar("_F", bound=Callable[..., Any])
_capture: ContextVar[Optional["RunCapture"]] = ContextVar(
    "praval_run_meter", default=None
)
_provider_scope: ContextVar[Optional["ProviderCallScope"]] = ContextVar(
    "praval_request_meter", default=None
)


def call_dict(call: ModelCall, *, compact: bool = False) -> Dict[str, Any]:
    """Serialize a content-free call for responses and HITL state."""
    data = {
        **vars(call),
        "usage": call.usage.model_dump() if call.usage is not None else None,
        "started_at": call.started_at.isoformat(),
    }
    if call.reported_cost_usd is None:
        data.pop("reported_cost_usd", None)
    return (
        {key: value for key, value in data.items() if value is not None}
        if compact
        else data
    )


def _restore_call(value: Dict[str, Any]) -> ModelCall:
    data = dict(value)
    for field in (
        "round_index",
        "usage",
        "agent_name",
        "run_id",
        "parent_run_id",
        "correlation_id",
        "response_id",
    ):
        data.setdefault(field, None)
    data["started_at"] = datetime.fromisoformat(data["started_at"])
    if data.get("usage") is not None:
        data["usage"] = Usage.model_validate(data["usage"])
    return ModelCall(**data)


class RunCapture:
    """Request-local aggregation, independent of lifetime and tracked meters."""

    def __init__(
        self,
        runtime: Any,
        previous: Optional[Dict[str, Any]] = None,
        resume_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.runtime = runtime
        self.meter = UsageMeter()
        self.has_reported_usage = False
        parent = _capture.get()
        states = _active_states()
        self.run_id = states[-1].run_id if states else str(uuid.uuid4())
        self.parent_run_id = (
            parent.run_id
            if parent is not None
            else (states[-2].run_id if len(states) > 1 else None)
        )
        self._resume_context = resume_context
        restored = self._restore_history(previous or {})
        self._historical_usage_unknown = previous is not None and (
            not restored or previous.get("model_call_history_complete") is False
        )
        if restored:
            self.run_id = restored[0].run_id or self.run_id
            self.parent_run_id = restored[0].parent_run_id
        elif resume_context and resume_context.get("run_id"):
            self.run_id = str(resume_context["run_id"])
        for call in restored:
            # Restoration is local to this logical response. Re-emitting would
            # bill lifetime/track meters and subscribers for old requests again.
            self.meter.record(call)
            if call.usage is not None:
                self.has_reported_usage = True

    @staticmethod
    def _restore_history(state: Dict[str, Any]) -> List[ModelCall]:
        values = list(state.get("model_calls") or [])
        saved = state.get("resume_results")
        if (
            isinstance(saved, dict)
            and saved.get("intervention_id") == state.get("intervention_id")
            and isinstance(saved.get("checkpoint"), dict)
            and saved["checkpoint"].get("schema") == "model_runtime_tool_v1"
        ):
            values.extend(saved["checkpoint"].get("model_calls") or [])
        unique = {value["call_id"]: _restore_call(value) for value in values}
        return sorted(unique.values(), key=lambda call: call.started_at)

    def persist_resume(self) -> None:
        """Save successful/failed attempts before Agent releases its claim."""
        context = self._resume_context or {}
        decision = context.get("resume_intervention")
        run_id = context.get("run_id")
        if not run_id or not isinstance(decision, dict):
            return
        from .hitl.store import get_hitl_store

        store = get_hitl_store(context.get("db_path"))
        stored = store.get_suspended_run(str(run_id))
        if (
            stored is None
            or stored.status != "resuming"
            or stored.state.get("intervention_id") != decision.get("id")
        ):
            return
        state = dict(stored.state)
        # Other ledger writers can add calls while an approved handler runs.
        calls = {call.call_id: call for call in self._restore_history(state)}
        calls.update({call.call_id: call for call in self.meter.calls})
        values = [
            call_dict(call, compact=True)
            for call in sorted(calls.values(), key=lambda call: call.started_at)
        ]
        state["model_calls"] = values
        history_complete = (
            not self._historical_usage_unknown
            and state.get("model_call_history_complete") is not False
        )
        state["model_call_history_complete"] = history_complete
        saved = state.get("resume_results")
        if (
            isinstance(saved, dict)
            and saved.get("intervention_id") == decision.get("id")
            and isinstance(saved.get("checkpoint"), dict)
        ):
            checkpoint = {
                **saved["checkpoint"],
                "model_calls": values,
                "model_call_history_complete": history_complete,
            }
            state["resume_results"] = {**saved, "checkpoint": checkpoint}
        store.update_suspended_run_state(str(run_id), state, expected_status="resuming")

    @contextmanager
    def activate(self) -> Iterator[None]:
        token = _capture.set(self)
        try:
            yield
        finally:
            _capture.reset(token)

    def finish(self, response: ModelResponse) -> ModelResponse:
        totals = self.meter.totals
        response.metadata = dict(response.metadata)
        response.metadata["model_calls"] = [
            call_dict(call) for call in self.meter.calls
        ]
        response.metadata["usage_complete"] = (
            totals.complete and not self._historical_usage_unknown
        )
        if totals.cost_reported_calls:
            response.metadata["reported_cost"] = {
                "amount": totals.reported_cost_usd,
                "currency": "USD",
                "complete": totals.cost_reported_calls == totals.calls
                and not self._historical_usage_unknown,
            }
        # Preserve None when no request reported usage, rather than inventing
        # a zero-token provider report.
        if self.has_reported_usage:
            response.usage = Usage(
                **{name: getattr(totals, name) for name in Usage.model_fields}
            )
        return response


def capture_calls() -> List[Dict[str, Any]]:
    capture = _capture.get()
    return (
        [call_dict(call, compact=True) for call in capture.meter.calls]
        if capture is not None
        else []
    )


def complete_metered_response(response: ModelResponse) -> ModelResponse:
    capture = _capture.get()
    return capture.finish(response) if capture is not None else response


def _emit(call: ModelCall, runtime: Any) -> None:
    capture = _capture.get()
    meters = list(_tracked.get())
    if runtime.usage not in meters:
        meters.append(runtime.usage)
    if capture is not None and capture.meter not in meters:
        meters.append(capture.meter)
    if capture is not None and call.usage is not None:
        capture.has_reported_usage = True
    for meter in meters:
        meter.record(call)
    record_model_facts(
        provider=call.provider,
        model=call.model,
        response_id=call.response_id,
        usage=call.usage,
        count_call=True,
    )
    try:
        from .observability.signals import emit_model_call

        emit_model_call(call)
    except Exception:
        # Metrics are optional and must not alter model execution.
        pass


class ProviderCallScope:
    """One request attempt; adapters can report individual nested requests."""

    def __init__(
        self,
        runtime: Any,
        operation: str,
        request: Any,
        attempt: int,
        round_index: Optional[int] = None,
    ) -> None:
        self.runtime, self.operation, self.request = runtime, operation, request
        self.attempt, self.round_index = attempt, round_index
        self.started_at = datetime.now(timezone.utc)
        self.started = time.perf_counter()
        self.reported = 0
        self.finished = False
        self.usage: Optional[Usage] = None
        self.response_id: Optional[str] = None
        self._lock = threading.RLock()
        self._children: List[ProviderCallScope] = []
        self._interrupted = False
        self._emitted = False
        self.model = str(request.model or getattr(runtime.config, "model", "") or "")
        # An initial provider failure still belongs to this provider/model,
        # even when no response object exists to enrich the observation later.
        record_model_facts(provider=runtime.provider_name, model=self.model)

    def register_request(self, child: "ProviderCallScope") -> None:
        """Delegate reporting before the worker starts its actual SDK request."""
        with self._lock:
            child._lock = self._lock
            self.reported += 1
            self._children.append(child)
            if self.finished:
                child._interrupted = self._interrupted
                if self._emitted and self.reported == 1:
                    # Cancellation can win before a worker enters its SDK
                    # reporter. The parent's record already owns that request.
                    child.finished = True

    def finish(self, result: Any = None, *, status: str = "ok") -> None:
        children: List[ProviderCallScope] = []
        call: Optional[ModelCall] = None
        with self._lock:
            if self.finished:
                return
            self.finished = True
            self._interrupted = self._interrupted or status == "error"
            if self.reported:
                if self._interrupted:
                    children = [child for child in self._children if not child.finished]
                    for child in children:
                        child._interrupted = True
            else:
                if isinstance(result, ModelResponse):
                    self.usage = result.usage
                    identifier = result.metadata.get(
                        "response_id"
                    ) or result.metadata.get("id")
                    self.response_id = (
                        str(identifier) if identifier is not None else None
                    )
                capture = _capture.get()
                call = ModelCall(
                    provider=self.runtime.provider_name,
                    model=self.model,
                    operation=cast(Any, self.operation),
                    round_index=self.round_index,
                    attempt=self.attempt,
                    status="error" if self._interrupted else cast(Any, status),
                    usage=self.usage,
                    duration_ms=max(0.0, (time.perf_counter() - self.started) * 1000),
                    started_at=self.started_at,
                    agent_name=self.runtime.agent_name,
                    call_id=str(uuid.uuid4()),
                    run_id=capture.run_id if capture else None,
                    parent_run_id=capture.parent_run_id if capture else None,
                    correlation_id=_correlation.get(),
                    response_id=self.response_id,
                    reported_cost_usd=(
                        result.metadata.get("reported_cost_usd")
                        if isinstance(result, ModelResponse)
                        else None
                    ),
                )
                self._emitted = True
        # Subscribers may execute application code. Do not hold the shared
        # ownership lock while notifying them or completing child reporters.
        for child in children:
            child.finish(status="error")
        if call is not None:
            _emit(call, self.runtime)

    @contextmanager
    def activate(self) -> Iterator[None]:
        token = _provider_scope.set(self)
        try:
            yield
        except BaseException:
            self.finish(status="error")
            raise
        finally:
            _provider_scope.reset(token)


@contextmanager
def provider_request() -> Iterator[Optional[ProviderCallScope]]:
    """Allow multi-request adapters to report each actual SDK request."""
    parent = _provider_scope.get()
    if parent is None:
        yield None
        return
    child = ProviderCallScope(
        parent.runtime,
        parent.operation,
        parent.request,
        parent.attempt,
        parent.round_index,
    )
    parent.register_request(child)
    try:
        yield child
    except BaseException:
        child.finish(status="error")
        raise
    finally:
        child.finish()


def metered_run(func: _F) -> _F:
    """Aggregate public runtime calls; activate generator contexts per pull.

    Meter state never leaks into caller code between yielded stream events.
    """

    def make_capture(runtime: Any, args: Any, kwargs: Any) -> RunCapture:
        previous = None
        resume_context = None
        if func.__name__.startswith("resume_tool_flow"):
            previous = args[0] if args else kwargs.get("suspended_state")
            resume_context = kwargs.get("hitl_context")
            if resume_context is None and len(args) > 2:
                resume_context = args[2]
        return RunCapture(runtime, previous, resume_context)

    if inspect.isasyncgenfunction(func):

        @wraps(func)
        async def async_stream(runtime: Any, *args: Any, **kwargs: Any) -> Any:
            capture = make_capture(runtime, args, kwargs)
            events = func(runtime, *args, **kwargs)
            emitted = 0
            try:
                while True:
                    try:
                        with capture.activate():
                            event = await events.__anext__()
                    except StopAsyncIteration:
                        for call in capture.meter.calls[emitted:]:
                            yield ModelEvent(
                                type="model_call",
                                usage=call.usage,
                                metadata=call_dict(call),
                            )
                        break
                    except Exception:
                        for call in capture.meter.calls[emitted:]:
                            yield ModelEvent(
                                type="model_call",
                                usage=call.usage,
                                metadata=call_dict(call),
                            )
                        raise
                    if event.type in ("usage", "final"):
                        for call in capture.meter.calls[emitted:]:
                            yield ModelEvent(
                                type="model_call",
                                usage=call.usage,
                                metadata=call_dict(call),
                            )
                        emitted = len(capture.meter.calls)
                        if event.type == "final" and event.response is not None:
                            event.response = capture.finish(event.response)
                            event.usage = event.response.usage
                        elif event.type == "usage" and capture.meter.totals.calls:
                            event.usage = capture.finish(ModelResponse()).usage
                    yield event
            finally:
                with capture.activate():
                    await events.aclose()

        return cast(_F, async_stream)
    if inspect.isgeneratorfunction(func):

        @wraps(func)
        def stream(runtime: Any, *args: Any, **kwargs: Any) -> Any:
            capture = make_capture(runtime, args, kwargs)
            events = func(runtime, *args, **kwargs)
            emitted = 0
            try:
                while True:
                    try:
                        with capture.activate():
                            event = next(events)
                    except StopIteration:
                        for call in capture.meter.calls[emitted:]:
                            yield ModelEvent(
                                type="model_call",
                                usage=call.usage,
                                metadata=call_dict(call),
                            )
                        break
                    except Exception:
                        for call in capture.meter.calls[emitted:]:
                            yield ModelEvent(
                                type="model_call",
                                usage=call.usage,
                                metadata=call_dict(call),
                            )
                        raise
                    if event.type in ("usage", "final"):
                        for call in capture.meter.calls[emitted:]:
                            yield ModelEvent(
                                type="model_call",
                                usage=call.usage,
                                metadata=call_dict(call),
                            )
                        emitted = len(capture.meter.calls)
                        if event.type == "final" and event.response is not None:
                            event.response = capture.finish(event.response)
                            event.usage = event.response.usage
                        elif event.type == "usage" and capture.meter.totals.calls:
                            event.usage = capture.finish(ModelResponse()).usage
                    yield event
            finally:
                with capture.activate():
                    events.close()

        return cast(_F, stream)
    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_call(runtime: Any, *args: Any, **kwargs: Any) -> Any:
            capture = make_capture(runtime, args, kwargs)
            with capture.activate():
                try:
                    return capture.finish(await func(runtime, *args, **kwargs))
                finally:
                    capture.persist_resume()

        return cast(_F, async_call)

    @wraps(func)
    def call(runtime: Any, *args: Any, **kwargs: Any) -> Any:
        capture = make_capture(runtime, args, kwargs)
        with capture.activate():
            try:
                return capture.finish(func(runtime, *args, **kwargs))
            finally:
                capture.persist_resume()

    return cast(_F, call)
