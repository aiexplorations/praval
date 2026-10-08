"""Provider-neutral model runtime.

The runtime is the stable execution boundary between agents and providers. It
keeps the legacy string API working while exposing neutral request/response
objects for newer provider features.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import random
import time
from contextvars import copy_context
from functools import partial
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

from opentelemetry import trace
from referencing.exceptions import Unresolvable

from ._metering_runtime import (
    ProviderCallScope,
    capture_calls,
    complete_metered_response,
    metered_run,
)
from .core.exceptions import (
    HITLConfigurationError,
    InterventionRequired,
    ProviderError,
    ProviderInvalidResponseError,
    ToolRoundLimitError,
)
from .hitl.policy import requires_approval
from .hitl.runtime import HITLRuntime
from .hitl.store import get_hitl_store
from .metering import UsageMeter
from .models import (
    ContentPart,
    ModelEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ProviderCapabilities,
    ReasoningConfig,
    StructuredOutputConfig,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from .models.observation import RetryObservation
from .providers.errors import fill_provider_error_fields, map_provider_exception
from .runtime_observation import (
    ToolCallScope,
    operation_span,
    record_model_facts,
    record_retry,
)
from .tool_execution import (
    arun_tool,
    cached_schema_validator,
    error_result,
    json_schema_errors,
    run_tool,
    tool_result,
)

UNSAFE_PROVIDER_OPTION_KEYS = {
    "api_key",
    "api-key",
    "authorization",
    "default_headers",
    "headers",
    "organization",
    "x-api-key",
    "x-goog-api-key",
}
EXPERIMENTAL_TOOL_PROVIDERS = {"openai", "anthropic"}
MAX_SCHEMA_BYTES = 65536
RETRY_BASE_SECONDS = 0.5
RETRY_CAP_SECONDS = 30.0
RETRY_AFTER_CAP_SECONDS = 60.0
# Suspended-state key holding the round results a resume already executed.
RESUME_RESULTS_KEY = "resume_results"

logger = logging.getLogger(__name__)
_T = TypeVar("_T")


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


async def _async_sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


def _jitter(upper: float) -> float:
    return random.uniform(0.0, upper)


def _retry_backoff_seconds(attempt: int, error: ProviderError) -> float:
    """Delay before retry ``attempt``: provider hint, else full-jitter backoff."""
    if error.retry_after_seconds is not None:
        return min(max(0.0, float(error.retry_after_seconds)), RETRY_AFTER_CAP_SECONDS)
    exponent = min(max(attempt - 1, 0), 16)
    return _jitter(min(RETRY_CAP_SECONDS, RETRY_BASE_SECONDS * (2**exponent)))


def max_provider_retries(config: Any) -> int:
    """Retries Praval allows for one provider request (``config.retries``)."""
    return max(0, int(getattr(config, "retries", 0) or 0))


def record_provider_retry(
    attempt: int,
    error: BaseException,
    *,
    operation: str = "invoke",
    backoff_seconds: float = 0.0,
) -> None:
    """Log a provider retry and record it as a fact and a span event.

    Only the error type is recorded, never its message.
    """
    backoff_ms = max(0.0, backoff_seconds * 1000.0)
    logger.info(
        "Retrying provider %s request (retry %d) after %s; waiting %.0f ms",
        operation,
        attempt,
        type(error).__name__,
        backoff_ms,
    )
    fact = RetryObservation(
        attempt=attempt,
        operation=f"model.{operation}",
        reason_type=type(error).__name__,
        backoff_ms=backoff_ms,
    )
    record_retry(fact)
    span = trace.get_current_span()
    if span.is_recording():
        span.add_event(
            "praval.retry",
            {
                "praval.retry.attempt": attempt,
                "praval.retry.operation": operation,
                "praval.retry.reason_type": type(error).__name__,
                "praval.retry.backoff_ms": backoff_ms,
            },
        )


def call_with_retries(
    operation: str,
    fn: Callable[[], _T],
    *,
    retries: int,
    map_error: Callable[[Exception], ProviderError],
    on_retry: Optional[Callable[..., None]] = None,
) -> _T:
    """Call ``fn`` (one provider request), retrying it while it is retryable.

    ``map_error`` turns any exception from ``fn`` into a typed
    ``ProviderError``. A retryable error is retried up to ``retries`` times
    after ``_retry_backoff_seconds``; anything else is raised at once, with
    the original exception as its cause when it was mapped. HITL signals pass
    through unchanged. ``fn`` must be safe to repeat: it should send one
    request and must not run tools.
    """
    attempt = 1
    while True:
        try:
            return fn()
        except (InterventionRequired, HITLConfigurationError):
            raise
        except Exception as exc:
            error = map_error(exc)
            if not error.retryable or attempt > retries:
                if error is exc:
                    raise
                raise error from exc
            delay = _retry_backoff_seconds(attempt, error)
            (on_retry or record_provider_retry)(
                attempt, error, operation=operation, backoff_seconds=delay
            )
            _sleep(delay)
        attempt += 1


async def acall_with_retries(
    operation: str,
    fn: Callable[[], Awaitable[_T]],
    *,
    retries: int,
    map_error: Callable[[Exception], ProviderError],
    on_retry: Optional[Callable[..., None]] = None,
) -> _T:
    """Async ``call_with_retries``: ``fn`` is awaited afresh for each attempt."""
    attempt = 1
    while True:
        try:
            return await fn()
        except (InterventionRequired, HITLConfigurationError):
            raise
        except Exception as exc:
            error = map_error(exc)
            if not error.retryable or attempt > retries:
                if error is exc:
                    raise
                raise error from exc
            delay = _retry_backoff_seconds(attempt, error)
            (on_retry or record_provider_retry)(
                attempt, error, operation=operation, backoff_seconds=delay
            )
            await _async_sleep(delay)
        attempt += 1


def _tool_parameter_schema(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize legacy tool parameters to JSON Schema shape."""
    if parameters.get("type") == "object" and "properties" in parameters:
        return parameters

    properties: Dict[str, Any] = {}
    required: List[str] = []
    for name, param in (parameters or {}).items():
        if not isinstance(param, dict):
            properties[name] = {"type": "string"}
            continue
        json_type = _python_type_to_json_schema(str(param.get("type", "str")))
        properties[name] = {"type": json_type}
        if param.get("required", False):
            required.append(name)

    return {"type": "object", "properties": properties, "required": required}


def _python_type_to_json_schema(python_type: str) -> str:
    mapping = {
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "list": "array",
        "dict": "object",
        "List": "array",
        "Dict": "object",
    }
    return mapping.get(python_type, "string")


def normalize_structured_output_config(
    value: Any,
) -> Optional[StructuredOutputConfig]:
    """Normalize public structured-output config values."""
    if value is None:
        return None
    if isinstance(value, StructuredOutputConfig):
        return value
    if isinstance(value, dict):
        if "schema" in value or "json_schema" in value:
            return StructuredOutputConfig(**value)
        return StructuredOutputConfig(schema=value)
    raise TypeError("response_schema must be a dict or StructuredOutputConfig")


def normalize_reasoning_config(value: Any) -> Optional[ReasoningConfig]:
    """Normalize public reasoning config values."""
    if value is None:
        return None
    if isinstance(value, ReasoningConfig):
        return value
    if isinstance(value, str):
        if value not in {"none", "low", "medium", "high"}:
            raise TypeError("reasoning level must be none, low, medium or high")
        return ReasoningConfig.model_validate({"level": value})
    if isinstance(value, dict):
        return ReasoningConfig(**value)
    raise TypeError("reasoning must be a level string, dict or ReasoningConfig")


def normalize_content_parts(value: Any) -> Any:
    """Normalize public multimodal content input to `ContentPart` instances."""
    if isinstance(value, ContentPart):
        return [value]
    if isinstance(value, list):
        parts: List[ContentPart] = []
        for item in value:
            if isinstance(item, ContentPart):
                parts.append(item)
            elif isinstance(item, str):
                parts.append(ContentPart.text_part(item))
            elif isinstance(item, dict):
                parts.append(ContentPart(**item))
            else:
                raise TypeError("message content parts must be strings or ContentPart")
        return parts
    return value


def _safe_model_dump(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(exclude_none=True)
        return dict(dumped) if isinstance(dumped, dict) else {}
    if isinstance(value, dict):
        return value
    return {}


def _json_safe(value: Any) -> Any:
    """Return a JSON-compatible representation without retaining SDK objects."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump(exclude_none=True))
    return None


def _nested_unsafe_option_keys(value: Any) -> List[str]:
    """Return unsafe credential-bearing keys found in a nested option value."""
    found: List[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in UNSAFE_PROVIDER_OPTION_KEYS:
                found.append(str(key))
            found.extend(_nested_unsafe_option_keys(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(_nested_unsafe_option_keys(item))
    return found


def legacy_tool_to_spec(
    tool: Dict[str, Any],
    *,
    strict: bool = False,
) -> Optional[ToolSpec]:
    """Convert a legacy Praval tool dict to a neutral `ToolSpec`."""
    func = tool.get("function")
    if not callable(func):
        return None
    name = str(tool.get("name") or getattr(func, "__name__", ""))
    if not name:
        return None
    return ToolSpec(
        name=name,
        description=str(tool.get("description", "") or ""),
        parameters=_tool_parameter_schema(dict(tool.get("parameters") or {})),
        strict=strict,
        requires_approval=bool(tool.get("requires_approval", False)),
        risk_level=str(tool.get("risk_level", "low") or "low"),
        approval_reason=str(tool.get("approval_reason", "") or ""),
        metadata={"legacy_tool": tool},
    )


def execute_legacy_tool_call(
    *,
    hitl_context: Optional[Dict[str, Any]],
    tool_call_id: str,
    function_name: str,
    raw_args: Any,
    available_tools: List[Dict[str, Any]],
    continuation_state: Optional[Dict[str, Any]] = None,
    resume_intervention: Optional[Dict[str, Any]] = None,
) -> str:
    """Execute a legacy provider tool call and return the result content.

    Provider adapters place the returned text directly in their tool messages.
    The runtime tool loop uses the typed ``ToolResult`` instead.
    """
    return _execute_legacy_tool_call_result(
        hitl_context=hitl_context,
        tool_call_id=tool_call_id,
        function_name=function_name,
        raw_args=raw_args,
        available_tools=available_tools,
        continuation_state=continuation_state,
        resume_intervention=resume_intervention,
    ).content


def _execute_legacy_tool_call_result(
    *,
    hitl_context: Optional[Dict[str, Any]],
    tool_call_id: str,
    function_name: str,
    raw_args: Any,
    available_tools: List[Dict[str, Any]],
    continuation_state: Optional[Dict[str, Any]] = None,
    resume_intervention: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """Execute a tool call with optional HITL gating and return a `ToolResult`."""
    with ToolCallScope(
        tool_call_id=tool_call_id,
        name=function_name,
        arguments=raw_args,
    ) as observed:
        try:
            outcome = _execute_legacy_tool_call_impl(
                hitl_context=hitl_context,
                tool_call_id=tool_call_id,
                function_name=function_name,
                raw_args=raw_args,
                available_tools=available_tools,
                continuation_state=continuation_state,
                resume_intervention=resume_intervention,
            )
        except InterventionRequired:
            observed.skip_fact()
            raise
        result = tool_result(outcome, tool_call_id=tool_call_id, name=function_name)
        observed.set_result(result.content, is_error=result.is_error)
        return result


def _execute_legacy_tool_call_impl(
    *,
    hitl_context: Optional[Dict[str, Any]],
    tool_call_id: str,
    function_name: str,
    raw_args: Any,
    available_tools: List[Dict[str, Any]],
    continuation_state: Optional[Dict[str, Any]] = None,
    resume_intervention: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """Execute a synchronous tool after observation setup."""
    tool_def = _tool_map(available_tools or []).get(function_name)
    if tool_def is not None and tool_def.get("async_only"):
        raise ProviderError(
            "This tool is async-only; use Agent.agenerate() or Agent.astream()."
        )
    runtime = _build_hitl_runtime(
        hitl_context, for_resume=resume_intervention is not None
    )
    if resume_intervention is not None and runtime is not None:
        return runtime.execute_with_decision_result(
            intervention=resume_intervention,
            available_tools=available_tools or [],
        )
    if runtime is not None and continuation_state is not None:
        return runtime.execute_or_interrupt_result(
            tool_call_id=tool_call_id,
            function_name=function_name,
            raw_args=raw_args,
            available_tools=available_tools or [],
            continuation_state=continuation_state,
        )

    if tool_def is None:
        return error_result(f"Unknown function: {function_name}")
    if continuation_state is not None:
        _require_hitl_for_gated_tool(hitl_context, function_name, tool_def)
    return _execute_tool_direct(tool_def, HITLRuntime._parse_args(raw_args))


async def execute_legacy_tool_call_async(
    *,
    hitl_context: Optional[Dict[str, Any]],
    tool_call_id: str,
    function_name: str,
    raw_args: Any,
    available_tools: List[Dict[str, Any]],
    continuation_state: Optional[Dict[str, Any]] = None,
    resume_intervention: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """Execute a tool on the caller's event loop with optional HITL gating."""
    with ToolCallScope(
        tool_call_id=tool_call_id,
        name=function_name,
        arguments=raw_args,
    ) as observed:
        try:
            outcome = await _execute_legacy_tool_call_async_impl(
                hitl_context=hitl_context,
                tool_call_id=tool_call_id,
                function_name=function_name,
                raw_args=raw_args,
                available_tools=available_tools,
                continuation_state=continuation_state,
                resume_intervention=resume_intervention,
            )
        except InterventionRequired:
            observed.skip_fact()
            raise
        result = tool_result(outcome, tool_call_id=tool_call_id, name=function_name)
        observed.set_result(result.content, is_error=result.is_error)
        return result


async def _execute_legacy_tool_call_async_impl(
    *,
    hitl_context: Optional[Dict[str, Any]],
    tool_call_id: str,
    function_name: str,
    raw_args: Any,
    available_tools: List[Dict[str, Any]],
    continuation_state: Optional[Dict[str, Any]] = None,
    resume_intervention: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """Execute an asynchronous tool after observation setup."""
    runtime = _build_hitl_runtime(
        hitl_context, for_resume=resume_intervention is not None
    )
    if resume_intervention is not None and runtime is not None:
        return await runtime.execute_with_decision_async(
            intervention=resume_intervention,
            available_tools=available_tools or [],
        )
    if runtime is not None and continuation_state is not None:
        return await runtime.execute_or_interrupt_async(
            tool_call_id=tool_call_id,
            function_name=function_name,
            raw_args=raw_args,
            available_tools=available_tools or [],
            continuation_state=continuation_state,
        )

    tool_def = _tool_map(available_tools or []).get(function_name)
    if tool_def is None:
        return error_result(f"Unknown function: {function_name}")
    if continuation_state is not None:
        _require_hitl_for_gated_tool(hitl_context, function_name, tool_def)
    return await _execute_tool_direct_async(tool_def, HITLRuntime._parse_args(raw_args))


def _hitl_identity(
    hitl_context: Optional[Dict[str, Any]],
) -> Optional[Tuple[str, str, str]]:
    """Return ``(run_id, agent_name, provider_name)`` when all are present."""
    if not hitl_context:
        return None
    run_id = hitl_context.get("run_id")
    agent_name = hitl_context.get("agent_name")
    provider_name = hitl_context.get("provider_name")
    if not run_id or not agent_name or not provider_name:
        return None
    return str(run_id), str(agent_name), str(provider_name)


def _build_hitl_runtime(
    hitl_context: Optional[Dict[str, Any]],
    *,
    for_resume: bool = False,
) -> Optional[HITLRuntime]:
    """Build the HITL runtime for a tool call, or ``None`` without HITL.

    A runtime (and with it the HITL store) is only built when HITL is enabled,
    or to apply a recorded decision during a resume, so agents without HITL
    never open the HITL database.
    """
    identity = _hitl_identity(hitl_context)
    if identity is None or hitl_context is None:
        return None
    enabled = bool(hitl_context.get("enabled", False))
    if not enabled and not for_resume:
        return None
    run_id, agent_name, provider_name = identity
    return HITLRuntime(
        run_id=run_id,
        agent_name=agent_name,
        provider_name=provider_name,
        hitl_enabled=enabled,
        db_path=hitl_context.get("db_path"),
        trace_id=hitl_context.get("trace_id"),
    )


def _require_hitl_for_gated_tool(
    hitl_context: Optional[Dict[str, Any]],
    function_name: str,
    tool_def: Dict[str, Any],
) -> None:
    """Refuse an approval-gated tool on a run that has HITL disabled.

    Raises:
        HITLConfigurationError: If the tool requires approval and the run's
            HITL context identifies an agent with HITL disabled.
    """
    identity = _hitl_identity(hitl_context)
    if identity is None or not requires_approval(tool_def):
        return
    raise HITLConfigurationError(
        f"Tool '{function_name}' requires approval but agent "
        f"'{identity[1]}' has hitl=False"
    )


def _saved_resume_results(
    suspended_state: Dict[str, Any], intervention_id: str
) -> Optional[List[ToolResult]]:
    """Return the round results an earlier resume of this decision stored.

    ``None`` means the approved tool has not run yet for this intervention.
    """
    saved = suspended_state.get(RESUME_RESULTS_KEY)
    if (
        not intervention_id
        or not isinstance(saved, dict)
        or saved.get("intervention_id") != intervention_id
        or not isinstance(saved.get("round_results"), list)
    ):
        return None
    return [ToolResult.model_validate(result) for result in saved["round_results"]]


def _save_resume_results(
    suspended_state: Dict[str, Any],
    hitl_context: Optional[Dict[str, Any]],
    intervention_id: str,
    round_results: List[ToolResult],
) -> None:
    """Store the round results executed by a resume with its suspended run.

    A resume whose continuation then fails returns the run to ``pending``;
    the next resume reuses these results instead of running the tools again.
    The write only applies while the run is claimed (``resuming``).
    """
    context = hitl_context or {}
    run_id = context.get("run_id")
    if not run_id or not intervention_id:
        return
    state = dict(suspended_state)
    state[RESUME_RESULTS_KEY] = {
        "intervention_id": intervention_id,
        "round_results": [
            _json_safe(result.model_dump(exclude_none=True)) for result in round_results
        ],
    }
    stored = get_hitl_store(context.get("db_path")).update_suspended_run_state(
        str(run_id), state, expected_status="resuming"
    )
    if not stored:
        logger.debug(
            "Suspended run %s is not claimed; resume results were not stored",
            run_id,
        )


def _tool_map(available_tools: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    mapping: Dict[str, Dict[str, Any]] = {}
    for tool in available_tools or []:
        func = tool.get("function")
        if callable(func):
            mapping[str(tool.get("name") or func.__name__)] = tool
    return mapping


def _execute_tool_direct(tool_def: Dict[str, Any], args: Dict[str, Any]) -> ToolResult:
    """Validate arguments and run a tool synchronously without HITL gating."""
    if tool_def.get("async_only"):
        raise ProviderError(
            "This tool is async-only; use Agent.agenerate() or Agent.astream()."
        )
    return run_tool(tool_def, args)


async def _execute_tool_direct_async(
    tool_def: Dict[str, Any], args: Dict[str, Any]
) -> ToolResult:
    """Validate arguments and run a tool on the caller's event loop."""
    return await arun_tool(tool_def, args)


def _validate_structured_content(
    content: str,
    config: StructuredOutputConfig,
    *,
    provider: Optional[str],
    model: Optional[str],
) -> None:
    """Check final content against the requested schema.

    Raises:
        ProviderInvalidResponseError: If the content is not JSON or does not
            match the schema.
    """
    source = f"provider '{provider or 'unknown'}' model '{model or 'unknown'}'"
    try:
        payload = json.loads(content)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ProviderInvalidResponseError(
            f"Response from {source} is not valid JSON: {exc}"
        ) from exc
    validator = cached_schema_validator(config.json_schema or {})
    if validator is None:
        raise ProviderInvalidResponseError(
            f"response_schema for {source} is not a valid JSON Schema"
        )
    try:
        errors = json_schema_errors(validator, payload)
    except Unresolvable as exc:
        raise ProviderInvalidResponseError(
            f"response_schema for {source} has an unresolvable $ref: {exc}"
        ) from exc
    except RecursionError as exc:
        raise ProviderInvalidResponseError(
            f"Response from {source} is nested too deeply to validate"
        ) from exc
    if errors:
        raise ProviderInvalidResponseError(
            f"Response from {source} does not match response_schema: "
            + "; ".join(errors)
        )


class ModelRuntime:
    """Runtime wrapper for provider-neutral model execution."""

    def __init__(
        self,
        *,
        provider: Any,
        provider_name: str,
        config: Any,
        usage: Optional[UsageMeter] = None,
        agent_name: Optional[str] = None,
    ) -> None:
        self.usage = usage if usage is not None else UsageMeter()
        self.agent_name = agent_name
        self.provider = provider
        self.provider_name = provider_name
        self.config = config

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return provider capabilities if exposed."""
        capabilities = getattr(self.provider, "capabilities", None)
        if isinstance(capabilities, ProviderCapabilities):
            return capabilities
        return ProviderCapabilities()

    @metered_run
    def invoke(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        hitl_context: Optional[Dict[str, Any]] = None,
        response_schema: Optional[StructuredOutputConfig] = None,
        reasoning: Optional[Union[str, Dict[str, Any], ReasoningConfig]] = None,
        provider_options: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stream_options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        max_tool_rounds: Optional[int] = None,
    ) -> ModelResponse:
        """Execute a model request and return a neutral response."""
        request = self._build_request(
            messages=messages,
            tools=tools,
            hitl_context=hitl_context,
            response_schema=response_schema,
            reasoning=reasoning,
            provider_options=provider_options,
            timeout=timeout,
            metadata=metadata,
            stream_options=stream_options,
            stream=stream,
            max_tool_rounds=max_tool_rounds,
        )
        with self._span(request):
            self.validate_request(request)
            response = self._invoke_with_retries(request, tools=tools)
            if not response.provider:
                response.provider = self.provider_name
            if not response.model:
                response.model = request.model
            self._record_response_facts(response)
            self._validate_final_response(request, response)
            return response

    def generate_text(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        hitl_context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Execute a request and return text for legacy callers."""
        return self.invoke(
            messages=messages,
            tools=tools,
            hitl_context=hitl_context,
            **kwargs,
        ).content

    @metered_run
    async def ainvoke(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        hitl_context: Optional[Dict[str, Any]] = None,
        response_schema: Optional[StructuredOutputConfig] = None,
        reasoning: Optional[Union[str, Dict[str, Any], ReasoningConfig]] = None,
        provider_options: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stream_options: Optional[Dict[str, Any]] = None,
        max_tool_rounds: Optional[int] = None,
    ) -> ModelResponse:
        """Execute providers and tools without moving async tools across loops."""
        request = self._build_request(
            messages=messages,
            tools=tools,
            hitl_context=hitl_context,
            response_schema=response_schema,
            reasoning=reasoning,
            provider_options=provider_options,
            timeout=timeout,
            metadata=metadata,
            stream_options=stream_options,
            max_tool_rounds=max_tool_rounds,
        )
        with self._span(request):
            self.validate_request(request)
            response = await self._ainvoke_with_retries(request, tools=tools)
            self._record_response_facts(response)
            self._validate_final_response(request, response)
            return response

    @metered_run
    def stream(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        hitl_context: Optional[Dict[str, Any]] = None,
        response_schema: Optional[StructuredOutputConfig] = None,
        reasoning: Optional[Union[str, Dict[str, Any], ReasoningConfig]] = None,
        provider_options: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stream_options: Optional[Dict[str, Any]] = None,
        max_tool_rounds: Optional[int] = None,
    ) -> Iterator[ModelEvent]:
        """Stream normalized model events."""
        request = self._build_request(
            messages=messages,
            tools=tools,
            hitl_context=hitl_context,
            response_schema=response_schema,
            reasoning=reasoning,
            provider_options=provider_options,
            timeout=timeout,
            metadata=metadata,
            stream_options=stream_options,
            stream=True,
            max_tool_rounds=max_tool_rounds,
        )
        self.validate_request(request)
        record_model_facts(provider=self.provider_name, model=request.model)
        started = time.perf_counter()
        yield ModelEvent(
            type="start",
            metadata={
                "provider": self.provider_name,
                "model": request.model,
                "native_streaming": self.resolve_capabilities(request).native_streaming,
            },
        )
        if tools:
            with self._span(request) as span:
                response = self._invoke_with_retries(request, tools=tools)
                stream_state = self._new_stream_state()
                for event in self._response_events(response):
                    self._record_stream_event(event, span, started, stream_state)
                    yield event
                self._finish_stream_facts(stream_state)
            return
        provider_stream = self._get_concrete_provider_method("stream")
        if provider_stream is not None:
            with self._span(request) as span:
                stream_state = self._new_stream_state()
                for event in self._stream_provider_events(
                    request, provider_stream, tools
                ):
                    self._record_stream_event(event, span, started, stream_state)
                    yield event
                self._finish_stream_facts(stream_state)
            return

        with self._span(request) as span:
            response = self._invoke_with_retries(request, tools=tools)
            stream_state = self._new_stream_state()
            for event in self._response_events(response):
                self._record_stream_event(event, span, started, stream_state)
                yield event
            self._finish_stream_facts(stream_state)

    @metered_run
    async def astream(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        hitl_context: Optional[Dict[str, Any]] = None,
        response_schema: Optional[StructuredOutputConfig] = None,
        reasoning: Optional[Union[str, Dict[str, Any], ReasoningConfig]] = None,
        provider_options: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stream_options: Optional[Dict[str, Any]] = None,
        max_tool_rounds: Optional[int] = None,
    ) -> AsyncIterator[ModelEvent]:
        """Asynchronously stream normalized model events."""
        request = self._build_request(
            messages=messages,
            tools=tools,
            hitl_context=hitl_context,
            response_schema=response_schema,
            reasoning=reasoning,
            provider_options=provider_options,
            timeout=timeout,
            metadata=metadata,
            stream_options=stream_options,
            stream=True,
            max_tool_rounds=max_tool_rounds,
        )
        self.validate_request(request)
        record_model_facts(provider=self.provider_name, model=request.model)
        started = time.perf_counter()
        if tools:
            yield ModelEvent(
                type="start",
                metadata={
                    "provider": self.provider_name,
                    "model": request.model,
                    "native_streaming": False,
                },
            )
            with self._span(request) as span:
                response = await self._ainvoke_with_retries(request, tools=tools)
                stream_state = self._new_stream_state()
                for event in self._response_events(response):
                    self._record_stream_event(event, span, started, stream_state)
                    yield event
                self._finish_stream_facts(stream_state)
            return
        concrete_astream = self._get_concrete_provider_method("astream")
        if concrete_astream is not None:
            yield ModelEvent(
                type="start",
                metadata={
                    "provider": self.provider_name,
                    "model": request.model,
                    "native_streaming": self.resolve_capabilities(
                        request
                    ).native_streaming,
                },
            )
            with self._span(request) as span:
                stream_state = self._new_stream_state()
                async for event in self._astream_provider_events(
                    request, concrete_astream, tools
                ):
                    self._record_stream_event(event, span, started, stream_state)
                    yield event
                self._finish_stream_facts(stream_state)
            return

        yield ModelEvent(
            type="start",
            metadata={
                "provider": self.provider_name,
                "model": request.model,
                "native_streaming": False,
            },
        )
        with self._span(request) as span:
            response = await self._ainvoke_with_retries(request, tools=tools)
            stream_state = self._new_stream_state()
            for event in self._response_events(response):
                self._record_stream_event(event, span, started, stream_state)
                yield event
            self._finish_stream_facts(stream_state)

    def _new_stream_state(self) -> Dict[str, Any]:
        return {"first_token": False, "usage": None, "final": False}

    def _record_stream_event(
        self,
        event: ModelEvent,
        span: Any,
        started: float,
        stream_state: Dict[str, Any],
    ) -> None:
        """Aggregate streaming usage/final facts and record time to first token."""
        if event.type == "delta" and span.is_recording():
            if not stream_state["first_token"]:
                span.set_attribute(
                    "gen_ai.server.time_to_first_token",
                    max(0.0, time.perf_counter() - started),
                )
                stream_state["first_token"] = True
        if event.type == "usage" and event.usage is not None:
            stream_state["usage"] = event.usage
        if event.type == "final" and event.response is not None:
            self._record_response_facts(event.response)
            stream_state["final"] = True
            return

    def _finish_stream_facts(self, stream_state: Dict[str, Any]) -> None:
        if not stream_state["final"]:
            record_model_facts(
                provider=self.provider_name,
                model=getattr(self.config, "model", None),
            )

    def _record_response_facts(self, response: ModelResponse) -> None:
        """Map a neutral model response to observation-safe aggregate facts."""
        metadata = response.metadata or {}
        response_id = metadata.get("response_id") or metadata.get("id")
        if response_id is not None:
            response_id = str(response_id)
        record_model_facts(
            provider=response.provider or self.provider_name,
            model=response.model or getattr(self.config, "model", None),
            response_id=response_id,
            terminal_outcome=response.finish_reason,
        )
        try:
            span = trace.get_current_span()
            if not span.is_recording():
                return
            if response_id:
                span.set_attribute("gen_ai.response.id", response_id)
            if response.finish_reason:
                span.set_attribute(
                    "gen_ai.response.finish_reasons", (response.finish_reason,)
                )
            if response.usage:
                span.set_attribute(
                    "gen_ai.usage.input_tokens", response.usage.input_tokens
                )
                span.set_attribute(
                    "gen_ai.usage.output_tokens", response.usage.output_tokens
                )
                span.set_attribute(
                    "praval.usage.total_tokens", response.usage.total_tokens
                )
        except Exception:
            # Telemetry enrichment must not affect provider results.
            return

    def _response_events(self, response: ModelResponse) -> Iterator[ModelEvent]:
        raw_results = response.metadata.get("tool_results") or []
        tool_results = [
            (
                result
                if isinstance(result, ToolResult)
                else ToolResult.model_validate(result)
            )
            for result in raw_results
        ]
        for index, tool_call in enumerate(response.tool_calls):
            yield ModelEvent(type="tool_call", tool_call=tool_call)
            if index < len(tool_results):
                yield ModelEvent(
                    type="tool_result",
                    tool_result=tool_results[index],
                )
        if response.content:
            yield ModelEvent(type="delta", delta=response.content)
        if response.usage:
            yield ModelEvent(type="usage", usage=response.usage)
        yield ModelEvent(type="final", response=response, usage=response.usage)

    def _build_request(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        hitl_context: Optional[Dict[str, Any]],
        response_schema: Optional[StructuredOutputConfig] = None,
        reasoning: Optional[Union[str, Dict[str, Any], ReasoningConfig]] = None,
        provider_options: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stream_options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        max_tool_rounds: Optional[int] = None,
    ) -> ModelRequest:
        model = getattr(self.config, "model", None)
        provider_options_with_profile = self._merge_dicts(
            self._profile_provider_options(self.provider_name, model),
            getattr(self.config, "provider_options", None),
        )
        provider_options_with_profile = self._merge_dicts(
            provider_options_with_profile,
            provider_options,
        )
        tool_specs = [
            spec
            for spec in (
                legacy_tool_to_spec(
                    tool,
                    strict=bool(getattr(self.config, "strict_tools", False)),
                )
                for tool in tools or []
            )
            if spec is not None
        ]
        return ModelRequest(
            messages=[
                ModelMessage(
                    role=str(message.get("role", "")),
                    content=normalize_content_parts(message.get("content")),
                )
                for message in messages
            ],
            provider=self.provider_name,
            model=model,
            tools=tool_specs,
            temperature=getattr(self.config, "temperature", None),
            max_output_tokens=getattr(self.config, "max_output_tokens", None),
            max_tool_rounds=(
                max_tool_rounds
                if max_tool_rounds is not None
                else getattr(self.config, "max_tool_rounds", 8)
            ),
            stream=stream,
            response_schema=normalize_structured_output_config(response_schema)
            or normalize_structured_output_config(
                getattr(self.config, "response_schema", None)
            ),
            reasoning=normalize_reasoning_config(reasoning)
            or normalize_reasoning_config(getattr(self.config, "reasoning", None)),
            provider_options=provider_options_with_profile,
            stream_options=self._merge_dicts(
                getattr(self.config, "stream_options", None),
                stream_options,
            ),
            timeout=timeout or getattr(self.config, "timeout", None),
            metadata=dict(metadata or {}),
            hitl_context=hitl_context,
        )

    def _profile_provider_options(
        self, provider: str, model: Optional[str]
    ) -> Dict[str, Any]:
        """Return provider options implied by a registered provider profile."""
        try:
            from .providers.registry import get_provider_registry

            profile = get_provider_registry().resolve_profile(provider, model)
        except ProviderError:
            return {}
        if profile is None:
            return {}
        options = dict(profile.default_parameters or {})
        if profile.endpoint and "endpoint" not in options and "api" not in options:
            options["endpoint"] = profile.endpoint
        if profile.local_preset and "local_preset" not in options:
            options["local_preset"] = profile.local_preset
        return options

    def resolve_capabilities(self, request: ModelRequest) -> ProviderCapabilities:
        """Resolve effective capabilities for a request."""
        overrides = request.provider_options.get("capabilities")
        if overrides is not None and not isinstance(overrides, dict):
            raise ProviderError("provider_options.capabilities must be a dict")
        try:
            from .providers.registry import get_provider_registry

            return get_provider_registry().resolve_capabilities(
                request.provider or self.provider_name,
                request.model,
                overrides=overrides,
            )
        except ProviderError:
            if self._provider_declares_capabilities():
                capabilities = self.capabilities.model_copy(deep=True)
                for key, value in (overrides or {}).items():
                    if hasattr(capabilities, key):
                        setattr(capabilities, key, value)
                return capabilities
            return ProviderCapabilities()

    def validate_request(self, request: ModelRequest) -> None:
        """Validate a model request before provider execution."""
        capabilities = self.resolve_capabilities(request)
        # Case-insensitive and at any depth: options such as ``extra_headers``
        # and ``extra_query`` are forwarded to the SDK call as given.
        # ``experimental_tools`` is checked, with its own message, below.
        unsafe = _nested_unsafe_option_keys(
            {
                key: value
                for key, value in request.provider_options.items()
                if key != "experimental_tools"
            }
        )
        if unsafe:
            blocked = ", ".join(sorted(set(unsafe)))
            raise ProviderError(f"Unsafe provider option(s): {blocked}")
        self._validate_experimental_tools(request)
        if request.reasoning is not None and request.reasoning.level is not None:
            from .providers.registry import reasoning_parameters

            reasoning_parameters(request)
        if request.reasoning is not None and not capabilities.reasoning:
            raise ProviderError(
                f"Provider '{self.provider_name}' does not support reasoning config"
            )
        if (
            request.reasoning is not None
            and request.reasoning.effort
            and not capabilities.reasoning_effort
        ):
            raise ProviderError(
                f"Provider '{self.provider_name}' does not support reasoning effort"
            )
        if (
            request.reasoning is not None
            and request.reasoning.budget_tokens is not None
            and not capabilities.reasoning_budget
        ):
            raise ProviderError(
                f"Provider '{self.provider_name}' does not support reasoning budgets"
            )
        if request.response_schema is not None and not capabilities.structured_outputs:
            raise ProviderError(
                f"Provider '{self.provider_name}' does not support structured outputs"
            )
        if request.response_schema is not None:
            schema_size = len(
                json.dumps(request.response_schema.json_schema or {}).encode("utf-8")
            )
            if schema_size > MAX_SCHEMA_BYTES:
                raise ProviderError("response_schema exceeds maximum supported size")
        if request.tools and not capabilities.tools:
            raise ProviderError(
                f"Provider '{self.provider_name}' does not support tools"
            )
        if self._requests_responses_api(request) and not capabilities.responses_api:
            raise ProviderError(
                f"Provider '{self.provider_name}' does not support the Responses API"
            )
        if request.stream and not capabilities.streaming:
            raise ProviderError(
                f"Provider '{self.provider_name}' does not support streaming"
            )
        if request.stream and capabilities.native_streaming:
            if (
                self._get_concrete_provider_method("stream") is None
                and self._get_concrete_provider_method("astream") is None
            ):
                raise ProviderError(
                    f"Provider '{self.provider_name}' advertises native streaming "
                    "but does not implement a streaming adapter"
                )
        self._validate_multimodal_content(request, capabilities)

    def _validate_experimental_tools(self, request: ModelRequest) -> None:
        experimental_tools = request.provider_options.get("experimental_tools")
        if experimental_tools is None:
            return
        if request.provider_options.get("allow_experimental_tools") is not True:
            raise ProviderError(
                "experimental_tools requires allow_experimental_tools=True"
            )
        if not isinstance(experimental_tools, list) or not all(
            isinstance(tool, dict) for tool in experimental_tools
        ):
            raise ProviderError("experimental_tools must be a list of tool mappings")
        provider_name = request.provider or self.provider_name
        if provider_name not in EXPERIMENTAL_TOOL_PROVIDERS:
            raise ProviderError(
                f"Provider '{provider_name}' does not support experimental tools"
            )
        if provider_name == "openai" and not self._requests_responses_api(request):
            raise ProviderError(
                "OpenAI experimental tools require the Responses API endpoint"
            )
        unsafe = sorted(set(_nested_unsafe_option_keys(experimental_tools)))
        if unsafe:
            blocked = ", ".join(unsafe)
            raise ProviderError(
                f"Unsafe experimental tool option(s): {blocked}. "
                "Configure credentials outside request payloads."
            )

    def _provider_declares_capabilities(self) -> bool:
        return isinstance(
            getattr(self.provider, "capabilities", None), ProviderCapabilities
        )

    def _requests_responses_api(self, request: ModelRequest) -> bool:
        endpoint = str(
            request.provider_options.get("endpoint")
            or request.provider_options.get("api")
            or ""
        ).lower()
        if endpoint in {"chat.completions", "chat", "chat_completions"}:
            return False
        return endpoint == "responses" or bool(
            request.provider_options.get("use_responses", False)
        )

    def _validate_multimodal_content(
        self,
        request: ModelRequest,
        capabilities: ProviderCapabilities,
    ) -> None:
        for part in self._content_parts(request):
            if part.type == "text":
                continue
            if part.type in {"image_url", "image_base64", "image"}:
                if not (capabilities.multimodal and capabilities.image_input):
                    raise ProviderError(
                        f"Provider '{self.provider_name}' does not support image input"
                    )
                continue
            if part.type in {"file", "file_url"}:
                if not capabilities.file_input:
                    raise ProviderError(
                        f"Provider '{self.provider_name}' does not support file input"
                    )
                continue
            if part.type in {"audio", "audio_url", "audio_base64"}:
                if not capabilities.audio_input:
                    raise ProviderError(
                        f"Provider '{self.provider_name}' does not support audio input"
                    )
                continue
            if part.type in {"video", "video_url", "video_base64"}:
                if not capabilities.video_input:
                    raise ProviderError(
                        f"Provider '{self.provider_name}' does not support video input"
                    )
                continue
            raise ProviderError(
                f"Unsupported content part type for provider '{self.provider_name}': "
                f"{part.type}"
            )

    def _content_parts(self, request: ModelRequest) -> Iterator[ContentPart]:
        for message in request.messages:
            content = message.content
            if isinstance(content, ContentPart):
                yield content
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, ContentPart):
                        yield item
                    elif isinstance(item, dict):
                        yield ContentPart(**item)
                    elif isinstance(item, str):
                        yield ContentPart.text_part(item)
                    else:
                        raise ProviderError(
                            "message content parts must be strings, dicts, "
                            "or ContentPart instances"
                        )
            elif isinstance(content, (str, type(None))):
                continue
            else:
                raise ProviderError(
                    "message content must be a string or a list of content parts"
                )

    def _merge_dicts(
        self,
        base: Optional[Dict[str, Any]],
        overlay: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        if base:
            merged.update(base)
        if overlay:
            merged.update(overlay)
        return merged

    def _invoke_with_retries(
        self,
        request: ModelRequest,
        *,
        tools: Optional[List[Dict[str, Any]]],
    ) -> ModelResponse:
        """Send the initial request, then run the tool loop.

        Retries happen per provider request inside ``_call_provider``, so a
        failed continuation never re-runs tools from earlier rounds.
        """
        try:
            response = self._call_provider(
                "invoke", request, self._invoke_provider, request, tools=tools
            )
            return self._orchestrate_tool_calls(
                request,
                self._complete_response(response, request),
                tools=tools or [],
            )
        except (ProviderError, InterventionRequired, HITLConfigurationError):
            raise
        except Exception as exc:
            raise ProviderError(str(exc)) from exc

    async def _ainvoke_with_retries(
        self,
        request: ModelRequest,
        *,
        tools: Optional[List[Dict[str, Any]]],
    ) -> ModelResponse:
        """Async initial request and tool loop with per-request retries."""
        try:
            raw_response = await self._acall_provider(
                "invoke", request, self._invoke_provider_async, request, tools=tools
            )
            if not isinstance(raw_response, ModelResponse):
                raw_response = ModelResponse(
                    content=str(raw_response or ""), raw=raw_response
                )
            response = self._complete_response(raw_response, request)
            return await self._orchestrate_tool_calls_async(
                request,
                response,
                tools=tools or [],
            )
        except (ProviderError, InterventionRequired, HITLConfigurationError):
            raise
        except Exception as exc:
            raise ProviderError(str(exc)) from exc

    def _call_provider(
        self,
        operation: str,
        request: ModelRequest,
        fn: Callable[..., _T],
        *args: Any,
        _round_index: Optional[int] = None,
        **kwargs: Any,
    ) -> _T:
        """Send one provider request, retrying only that request.

        Every provider request passes through here (or ``_acall_provider``):
        the initial invoke, each tool-round continuation, the HITL resume
        continuation and the start of a native stream. A failure that maps to
        a retryable ``ProviderError`` is retried up to ``config.retries``
        times; anything else is raised at once.
        """

        attempt_number = 0

        def attempt() -> _T:
            nonlocal attempt_number
            attempt_number += 1
            call_scope = ProviderCallScope(
                self, operation, request, attempt_number, _round_index
            )
            with call_scope.activate(), self._provider_span(request, operation):
                try:
                    result = fn(*args, **kwargs)
                    call_scope.finish(result)
                    return result
                except (InterventionRequired, HITLConfigurationError):
                    raise
                except Exception as exc:
                    # Map inside the span, so the span records the typed,
                    # redacted error rather than raw SDK text.
                    error = self._provider_error(exc, operation, request)
                    if error is exc:
                        raise
                    raise error from exc

        return call_with_retries(
            operation,
            attempt,
            retries=self._max_provider_retries(),
            map_error=lambda exc: self._provider_error(exc, operation, request),
            on_retry=self._record_retry,
        )

    async def _acall_provider(
        self,
        operation: str,
        request: ModelRequest,
        fn: Callable[..., Awaitable[_T]],
        *args: Any,
        _round_index: Optional[int] = None,
        **kwargs: Any,
    ) -> _T:
        """Async ``_call_provider``: ``fn`` is called afresh for each attempt."""

        attempt_number = 0

        async def attempt() -> _T:
            nonlocal attempt_number
            attempt_number += 1
            call_scope = ProviderCallScope(
                self, operation, request, attempt_number, _round_index
            )
            with call_scope.activate(), self._provider_span(request, operation):
                try:
                    result = await fn(*args, **kwargs)
                    call_scope.finish(result)
                    return result
                except (InterventionRequired, HITLConfigurationError):
                    raise
                except Exception as exc:
                    # Map inside the span, so the span records the typed,
                    # redacted error rather than raw SDK text.
                    error = self._provider_error(exc, operation, request)
                    if error is exc:
                        raise
                    raise error from exc

        return await acall_with_retries(
            operation,
            attempt,
            retries=self._max_provider_retries(),
            map_error=lambda exc: self._provider_error(exc, operation, request),
            on_retry=self._record_retry,
        )

    def _stream_provider_events(
        self,
        request: ModelRequest,
        provider_stream: Callable[..., Iterator[ModelEvent]],
        tools: Optional[List[Dict[str, Any]]],
    ) -> Iterator[ModelEvent]:
        """Run a native provider stream, retrying only before its first event.

        Adapters yield an ``error`` event before raising, so a leading error
        event is held back until the outcome is known: it is dropped when the
        stream is retried and yielded before the exception otherwise.
        """
        retries = self._max_provider_retries()
        attempt = 1
        while True:
            emitted = False
            held_error: Optional[ModelEvent] = None
            call_scope = ProviderCallScope(self, "stream", request, attempt)
            try:
                with self._provider_span(request, "stream"):
                    try:
                        events = provider_stream(request, tools=tools)
                    except TypeError:
                        events = provider_stream(request)
                    for event in events:
                        if not emitted and held_error is None and event.type == "error":
                            held_error = event
                            continue
                        if held_error is not None:
                            yield held_error
                            held_error = None
                        emitted = True
                        if event.usage is not None:
                            call_scope.usage = event.usage
                        if event.type == "final" and event.response is not None:
                            if event.response.usage is None:
                                event.response.usage = call_scope.usage
                            call_scope.finish(event.response)
                        yield event
                if held_error is not None:
                    yield held_error
                call_scope.finish()
                return
            except (InterventionRequired, HITLConfigurationError):
                raise
            except Exception as exc:
                call_scope.finish(status="error")
                error = self._provider_error(exc, "stream", request)
                if emitted or not error.retryable or attempt > retries:
                    if held_error is not None:
                        yield held_error
                    if error is exc:
                        raise
                    raise error from exc
                delay = _retry_backoff_seconds(attempt, error)
                self._record_retry(
                    attempt, error, operation="stream", backoff_seconds=delay
                )
                _sleep(delay)
            finally:
                if not call_scope.finished:
                    call_scope.finish(status="error")
            attempt += 1

    async def _astream_provider_events(
        self,
        request: ModelRequest,
        provider_astream: Callable[..., AsyncIterator[ModelEvent]],
        tools: Optional[List[Dict[str, Any]]],
    ) -> AsyncIterator[ModelEvent]:
        """Async ``_stream_provider_events``."""
        retries = self._max_provider_retries()
        attempt = 1
        while True:
            emitted = False
            held_error: Optional[ModelEvent] = None
            call_scope = ProviderCallScope(self, "stream", request, attempt)
            try:
                with self._provider_span(request, "stream"):
                    try:
                        events = provider_astream(request, tools=tools)
                    except TypeError:
                        events = provider_astream(request)
                    async for event in events:
                        if not emitted and held_error is None and event.type == "error":
                            held_error = event
                            continue
                        if held_error is not None:
                            yield held_error
                            held_error = None
                        emitted = True
                        if event.usage is not None:
                            call_scope.usage = event.usage
                        if event.type == "final" and event.response is not None:
                            if event.response.usage is None:
                                event.response.usage = call_scope.usage
                            call_scope.finish(event.response)
                        yield event
                if held_error is not None:
                    yield held_error
                call_scope.finish()
                return
            except (InterventionRequired, HITLConfigurationError):
                raise
            except Exception as exc:
                call_scope.finish(status="error")
                error = self._provider_error(exc, "stream", request)
                if emitted or not error.retryable or attempt > retries:
                    if held_error is not None:
                        yield held_error
                    if error is exc:
                        raise
                    raise error from exc
                delay = _retry_backoff_seconds(attempt, error)
                self._record_retry(
                    attempt, error, operation="stream", backoff_seconds=delay
                )
                await _async_sleep(delay)
            finally:
                if not call_scope.finished:
                    call_scope.finish(status="error")
            attempt += 1

    def _max_provider_retries(self) -> int:
        return max_provider_retries(self.config)

    def _provider_error(
        self,
        exc: Exception,
        operation: str,
        request: ModelRequest,
    ) -> ProviderError:
        """Return the typed ``ProviderError`` for an exception from a provider.

        Adapters may expose ``map_provider_error(exc)`` to translate their SDK
        exceptions; anything still unmapped is classified generically, and an
        unrecognised exception becomes a non-retryable ``ProviderError``.
        """
        error: Optional[ProviderError] = exc if isinstance(exc, ProviderError) else None
        mapper = self._get_concrete_provider_method("map_provider_error")
        if error is None and mapper is not None:
            try:
                mapped = mapper(exc)
            except Exception as mapping_error:
                logger.warning("Provider error mapping failed: %s", mapping_error)
                mapped = None
            if isinstance(mapped, ProviderError):
                error = mapped
        if error is None:
            error = map_provider_exception(exc)
        return fill_provider_error_fields(
            error,
            provider=self.provider_name,
            model=request.model,
            operation=operation,
        )

    async def _invoke_provider_async(
        self,
        request: ModelRequest,
        *,
        tools: Optional[List[Dict[str, Any]]],
    ) -> Any:
        concrete_ainvoke = self._get_concrete_provider_method("ainvoke")
        if concrete_ainvoke is not None:
            try:
                response = concrete_ainvoke(request, tools=tools)
            except TypeError:
                response = concrete_ainvoke(request)
            if inspect.isawaitable(response):
                response = await response
            return response

        loop = asyncio.get_running_loop()
        context = copy_context()
        provider_call = partial(self._invoke_provider, request, tools=tools)
        return await loop.run_in_executor(None, context.run, provider_call)

    def _orchestrate_tool_calls(
        self,
        request: ModelRequest,
        response: ModelResponse,
        *,
        tools: List[Dict[str, Any]],
        initial_calls: Optional[List[ToolCall]] = None,
        initial_results: Optional[List[ToolResult]] = None,
        start_round: int = 0,
    ) -> ModelResponse:
        continuation = self._get_concrete_provider_method("continue_with_tool_results")
        if continuation is None:
            return response

        all_calls = list(initial_calls or [])
        all_results = list(initial_results or [])
        current = response
        round_limit = self._tool_round_limit(request)
        for round_index in range(start_round, round_limit):
            if not current.tool_calls:
                break
            round_calls = list(current.tool_calls)
            all_calls.extend(round_calls)
            round_results: List[ToolResult] = []
            for current_index, tool_call in enumerate(round_calls):
                continuation_state = self._runtime_continuation_state(
                    request,
                    current,
                    round_index=round_index,
                    round_calls=round_calls,
                    current_index=current_index,
                    round_results=round_results,
                    all_calls=all_calls,
                    all_results=all_results,
                )
                round_results.append(
                    self._execute_runtime_tool_call(
                        request,
                        tool_call,
                        tools=tools,
                        round_index=round_index,
                        previous_results=all_results + round_results,
                        continuation_state=continuation_state,
                    )
                )
            all_results.extend(round_results)
            continued = self._call_provider(
                "continue",
                request,
                continuation,
                request,
                current,
                round_results,
                _round_index=round_index,
            )
            if isinstance(continued, ModelResponse):
                current = self._complete_response(continued, request)
            else:
                current = self._complete_response(
                    ModelResponse(content=str(continued or ""), raw=continued),
                    request,
                )
        else:
            if current.tool_calls:
                self._record_limit_reached("tool_rounds", round_limit)
                raise ToolRoundLimitError(
                    f"Provider exceeded maximum tool rounds ({round_limit})",
                    limit=round_limit,
                    provider=self.provider_name,
                    model=request.model,
                )

        current.tool_calls = all_calls
        current.metadata = dict(current.metadata)
        current.metadata["tool_results"] = [
            result.model_dump(exclude_none=True) for result in all_results
        ]
        return current

    async def _orchestrate_tool_calls_async(
        self,
        request: ModelRequest,
        response: ModelResponse,
        *,
        tools: List[Dict[str, Any]],
        initial_calls: Optional[List[ToolCall]] = None,
        initial_results: Optional[List[ToolResult]] = None,
        start_round: int = 0,
    ) -> ModelResponse:
        continuation = self._get_concrete_provider_method("continue_with_tool_results")
        if continuation is None:
            return response

        all_calls = list(initial_calls or [])
        all_results = list(initial_results or [])
        current = response
        round_limit = self._tool_round_limit(request)
        for round_index in range(start_round, round_limit):
            if not current.tool_calls:
                break
            round_calls = list(current.tool_calls)
            all_calls.extend(round_calls)
            round_results: List[ToolResult] = []
            for current_index, tool_call in enumerate(round_calls):
                continuation_state = self._runtime_continuation_state(
                    request,
                    current,
                    round_index=round_index,
                    round_calls=round_calls,
                    current_index=current_index,
                    round_results=round_results,
                    all_calls=all_calls,
                    all_results=all_results,
                )
                round_results.append(
                    await self._execute_runtime_tool_call_async(
                        request,
                        tool_call,
                        tools=tools,
                        round_index=round_index,
                        previous_results=all_results + round_results,
                        continuation_state=continuation_state,
                    )
                )
            all_results.extend(round_results)
            continued = await self._acall_provider(
                "continue",
                request,
                self._continue_with_tool_results_async,
                continuation,
                request,
                current,
                round_results,
                _round_index=round_index,
            )
            if isinstance(continued, ModelResponse):
                current = self._complete_response(continued, request)
            else:
                current = self._complete_response(
                    ModelResponse(content=str(continued or ""), raw=continued),
                    request,
                )
        else:
            if current.tool_calls:
                self._record_limit_reached("tool_rounds", round_limit)
                raise ToolRoundLimitError(
                    f"Provider exceeded maximum tool rounds ({round_limit})",
                    limit=round_limit,
                    provider=self.provider_name,
                    model=request.model,
                )

        current.tool_calls = all_calls
        current.metadata = dict(current.metadata)
        current.metadata["tool_results"] = [
            result.model_dump(exclude_none=True) for result in all_results
        ]
        return current

    async def _continue_with_tool_results_async(
        self,
        continuation: Any,
        request: ModelRequest,
        response: ModelResponse,
        results: List[ToolResult],
    ) -> Any:
        if inspect.iscoroutinefunction(continuation):
            return await continuation(request, response, results)
        loop = asyncio.get_running_loop()
        context = copy_context()
        provider_call = partial(continuation, request, response, results)
        continued = await loop.run_in_executor(
            None,
            context.run,
            provider_call,
        )
        if inspect.isawaitable(continued):
            return await continued
        return continued

    @metered_run
    def resume_tool_flow(
        self,
        suspended_state: Dict[str, Any],
        tools: Optional[List[Dict[str, Any]]],
        hitl_context: Optional[Dict[str, Any]] = None,
    ) -> ModelResponse:
        """Resume a runtime-owned tool loop after a HITL decision."""
        if suspended_state.get("schema") != "model_runtime_tool_v1":
            raise ProviderError("Unsupported model runtime continuation state")
        resume_intervention = (hitl_context or {}).get("resume_intervention")
        if not isinstance(resume_intervention, dict):
            raise ProviderError("Runtime tool resume requires an intervention decision")

        available_tools = list(tools or [])
        request = self._restore_runtime_request(
            suspended_state.get("request"),
            tools=available_tools,
            hitl_context=hitl_context,
        )
        current = self._restore_runtime_response(suspended_state.get("response"))
        round_calls = [
            ToolCall.model_validate(call)
            for call in suspended_state.get("round_calls", [])
        ]
        current_index = int(suspended_state.get("current_index", 0))
        if current_index < 0 or current_index >= len(round_calls):
            raise ProviderError("Runtime tool continuation index is invalid")

        round_index = int(suspended_state.get("round", 0))
        round_results = [
            ToolResult.model_validate(result)
            for result in suspended_state.get("round_results", [])
        ]
        all_calls = [
            ToolCall.model_validate(call)
            for call in suspended_state.get("all_calls", [])
        ]
        all_results = [
            ToolResult.model_validate(result)
            for result in suspended_state.get("all_results", [])
        ]

        blocked_call = round_calls[current_index]
        intervention_id = str(resume_intervention.get("id") or "")
        saved = _saved_resume_results(suspended_state, intervention_id)
        if saved is None:
            blocked_result = _execute_legacy_tool_call_result(
                hitl_context=hitl_context,
                tool_call_id=blocked_call.id,
                function_name=blocked_call.name,
                raw_args=blocked_call.arguments,
                available_tools=available_tools,
                resume_intervention=resume_intervention,
            )
            round_results.append(self._tool_result(blocked_call, blocked_result))
            _save_resume_results(
                suspended_state, hitl_context, intervention_id, round_results
            )
            next_start = current_index + 1
        else:
            next_start = current_index + len(saved) - len(round_results)
            round_results = saved

        for next_index in range(next_start, len(round_calls)):
            tool_call = round_calls[next_index]
            continuation_state = self._runtime_continuation_state(
                request,
                current,
                round_index=round_index,
                round_calls=round_calls,
                current_index=next_index,
                round_results=round_results,
                all_calls=all_calls,
                all_results=all_results,
            )
            round_results.append(
                self._execute_runtime_tool_call(
                    request,
                    tool_call,
                    tools=available_tools,
                    round_index=round_index,
                    previous_results=all_results + round_results,
                    continuation_state=continuation_state,
                )
            )
            _save_resume_results(
                suspended_state, hitl_context, intervention_id, round_results
            )

        continuation = self._get_concrete_provider_method("continue_with_tool_results")
        if continuation is None:
            raise ProviderError(
                f"Provider '{self.provider_name}' does not support tool continuation"
            )
        continued = self._call_provider(
            "resume",
            request,
            continuation,
            request,
            current,
            round_results,
            _round_index=round_index,
        )
        if isinstance(continued, ModelResponse):
            next_response = self._complete_response(continued, request)
        else:
            next_response = self._complete_response(
                ModelResponse(content=str(continued or ""), raw=continued),
                request,
            )
        resumed = self._orchestrate_tool_calls(
            request,
            next_response,
            tools=available_tools,
            initial_calls=all_calls,
            initial_results=all_results + round_results,
            start_round=round_index + 1,
        )
        self._validate_final_response(request, resumed)
        return resumed

    @metered_run
    async def resume_tool_flow_async(
        self,
        suspended_state: Dict[str, Any],
        tools: Optional[List[Dict[str, Any]]],
        hitl_context: Optional[Dict[str, Any]] = None,
    ) -> ModelResponse:
        """Resume a runtime-owned tool loop while preserving the event loop."""
        if suspended_state.get("schema") != "model_runtime_tool_v1":
            raise ProviderError("Unsupported model runtime continuation state")
        resume_intervention = (hitl_context or {}).get("resume_intervention")
        if not isinstance(resume_intervention, dict):
            raise ProviderError("Runtime tool resume requires an intervention decision")

        available_tools = list(tools or [])
        request = self._restore_runtime_request(
            suspended_state.get("request"),
            tools=available_tools,
            hitl_context=hitl_context,
        )
        current = self._restore_runtime_response(suspended_state.get("response"))
        round_calls = [
            ToolCall.model_validate(call)
            for call in suspended_state.get("round_calls", [])
        ]
        current_index = int(suspended_state.get("current_index", 0))
        if current_index < 0 or current_index >= len(round_calls):
            raise ProviderError("Runtime tool continuation index is invalid")

        round_index = int(suspended_state.get("round", 0))
        round_results = [
            ToolResult.model_validate(result)
            for result in suspended_state.get("round_results", [])
        ]
        all_calls = [
            ToolCall.model_validate(call)
            for call in suspended_state.get("all_calls", [])
        ]
        all_results = [
            ToolResult.model_validate(result)
            for result in suspended_state.get("all_results", [])
        ]

        blocked_call = round_calls[current_index]
        intervention_id = str(resume_intervention.get("id") or "")
        saved = _saved_resume_results(suspended_state, intervention_id)
        if saved is None:
            blocked_result = await execute_legacy_tool_call_async(
                hitl_context=hitl_context,
                tool_call_id=blocked_call.id,
                function_name=blocked_call.name,
                raw_args=blocked_call.arguments,
                available_tools=available_tools,
                resume_intervention=resume_intervention,
            )
            round_results.append(self._tool_result(blocked_call, blocked_result))
            _save_resume_results(
                suspended_state, hitl_context, intervention_id, round_results
            )
            next_start = current_index + 1
        else:
            next_start = current_index + len(saved) - len(round_results)
            round_results = saved

        for next_index in range(next_start, len(round_calls)):
            tool_call = round_calls[next_index]
            continuation_state = self._runtime_continuation_state(
                request,
                current,
                round_index=round_index,
                round_calls=round_calls,
                current_index=next_index,
                round_results=round_results,
                all_calls=all_calls,
                all_results=all_results,
            )
            round_results.append(
                await self._execute_runtime_tool_call_async(
                    request,
                    tool_call,
                    tools=available_tools,
                    round_index=round_index,
                    previous_results=all_results + round_results,
                    continuation_state=continuation_state,
                )
            )
            _save_resume_results(
                suspended_state, hitl_context, intervention_id, round_results
            )

        continuation = self._get_concrete_provider_method("continue_with_tool_results")
        if continuation is None:
            raise ProviderError(
                f"Provider '{self.provider_name}' does not support tool continuation"
            )
        continued = await self._acall_provider(
            "resume",
            request,
            self._continue_with_tool_results_async,
            continuation,
            request,
            current,
            round_results,
            _round_index=round_index,
        )
        if isinstance(continued, ModelResponse):
            next_response = self._complete_response(continued, request)
        else:
            next_response = self._complete_response(
                ModelResponse(content=str(continued or ""), raw=continued),
                request,
            )
        resumed = await self._orchestrate_tool_calls_async(
            request,
            next_response,
            tools=available_tools,
            initial_calls=all_calls,
            initial_results=all_results + round_results,
            start_round=round_index + 1,
        )
        self._validate_final_response(request, resumed)
        return resumed

    def _execute_runtime_tool_call(
        self,
        request: ModelRequest,
        tool_call: ToolCall,
        *,
        tools: List[Dict[str, Any]],
        round_index: int,
        previous_results: List[ToolResult],
        continuation_state: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        state = continuation_state or {
            "schema": "model_runtime_tool_v1",
            "model_calls": capture_calls(),
            "provider": self.provider_name,
            "model": request.model,
            "round": round_index,
            "tool_call": tool_call.model_dump(exclude_none=True),
            "tool_results": [
                result.model_dump(exclude_none=True) for result in previous_results
            ],
        }
        result = _execute_legacy_tool_call_result(
            hitl_context=request.hitl_context,
            tool_call_id=tool_call.id,
            function_name=tool_call.name,
            raw_args=tool_call.arguments,
            available_tools=tools,
            continuation_state=state,
        )
        return self._tool_result(tool_call, result)

    async def _execute_runtime_tool_call_async(
        self,
        request: ModelRequest,
        tool_call: ToolCall,
        *,
        tools: List[Dict[str, Any]],
        round_index: int,
        previous_results: List[ToolResult],
        continuation_state: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        state = continuation_state or {
            "schema": "model_runtime_tool_v1",
            "provider": self.provider_name,
            "model": request.model,
            "round": round_index,
            "tool_call": tool_call.model_dump(exclude_none=True),
            "tool_results": [
                result.model_dump(exclude_none=True) for result in previous_results
            ],
        }
        result = await execute_legacy_tool_call_async(
            hitl_context=request.hitl_context,
            tool_call_id=tool_call.id,
            function_name=tool_call.name,
            raw_args=tool_call.arguments,
            available_tools=tools,
            continuation_state=state,
        )
        return self._tool_result(tool_call, result)

    def _tool_result(
        self, tool_call: ToolCall, outcome: Union[ToolResult, str]
    ) -> ToolResult:
        """Bind a tool outcome to the model's call id and tool name."""
        return tool_result(outcome, tool_call_id=tool_call.id, name=tool_call.name)

    def _validate_final_response(
        self, request: ModelRequest, response: ModelResponse
    ) -> None:
        """Validate final content locally when the request asks for it."""
        config = request.response_schema
        if config is None or not config.validate_locally:
            return
        _validate_structured_content(
            response.content,
            config,
            provider=response.provider or self.provider_name,
            model=response.model or request.model,
        )

    def _runtime_continuation_state(
        self,
        request: ModelRequest,
        response: ModelResponse,
        *,
        round_index: int,
        round_calls: List[ToolCall],
        current_index: int,
        round_results: List[ToolResult],
        all_calls: List[ToolCall],
        all_results: List[ToolResult],
    ) -> Dict[str, Any]:
        return {
            "schema": "model_runtime_tool_v1",
            "model_calls": capture_calls(),
            "provider": self.provider_name,
            "model": request.model,
            "round": round_index,
            "current_index": current_index,
            "request": self._serialize_runtime_request(request),
            "response": self._serialize_runtime_response(response),
            "round_calls": [
                self._serialize_tool_call(tool_call) for tool_call in round_calls
            ],
            "round_results": [
                result.model_dump(exclude_none=True) for result in round_results
            ],
            "all_calls": [
                self._serialize_tool_call(tool_call) for tool_call in all_calls
            ],
            "all_results": [
                result.model_dump(exclude_none=True) for result in all_results
            ],
        }

    def _serialize_runtime_request(self, request: ModelRequest) -> Dict[str, Any]:
        dumped = request.model_dump(exclude={"tools"}, exclude_none=True)
        serialized = _json_safe(dumped)
        return serialized if isinstance(serialized, dict) else {}

    def _restore_runtime_request(
        self,
        value: Any,
        *,
        tools: List[Dict[str, Any]],
        hitl_context: Optional[Dict[str, Any]],
    ) -> ModelRequest:
        if not isinstance(value, dict):
            raise ProviderError("Runtime tool request state is missing")
        request_data = dict(value)
        request_data["tools"] = [
            spec
            for spec in (
                legacy_tool_to_spec(
                    tool,
                    strict=bool(getattr(self.config, "strict_tools", False)),
                )
                for tool in tools
            )
            if spec is not None
        ]
        request_data["hitl_context"] = hitl_context
        return ModelRequest.model_validate(request_data)

    def _serialize_runtime_response(self, response: ModelResponse) -> Dict[str, Any]:
        return {
            "content": response.content,
            "provider": response.provider,
            "model": response.model,
            "messages": [
                _json_safe(message.model_dump(exclude_none=True))
                for message in response.messages
            ],
            "tool_calls": [
                self._serialize_tool_call(tool_call)
                for tool_call in response.tool_calls
            ],
            "usage": (
                _json_safe(response.usage.model_dump(exclude_none=True))
                if response.usage is not None
                else None
            ),
            "finish_reason": response.finish_reason,
            # Request accounting is stored once in the outer continuation
            # state; copying it into the response duplicates every record.
            "metadata": _json_safe(
                {
                    key: value
                    for key, value in response.metadata.items()
                    if key not in {"model_calls", "usage_complete"}
                }
            ),
        }

    def _restore_runtime_response(self, value: Any) -> ModelResponse:
        if not isinstance(value, dict):
            raise ProviderError("Runtime tool response state is missing")
        return ModelResponse.model_validate(value)

    def _serialize_tool_call(self, tool_call: ToolCall) -> Dict[str, Any]:
        return {
            "id": tool_call.id,
            "name": tool_call.name,
            "arguments": _json_safe(tool_call.arguments),
        }

    def _complete_response(
        self,
        response: ModelResponse,
        request: ModelRequest,
    ) -> ModelResponse:
        if not response.provider:
            response.provider = self.provider_name
        if not response.model:
            response.model = request.model
        return complete_metered_response(response)

    def _tool_round_limit(self, request: ModelRequest) -> int:
        """Resolve the validated request override or typed agent default."""
        value: Any = request.max_tool_rounds
        if value is None:
            value = getattr(self.config, "max_tool_rounds", 8)
        if value is None:
            value = 8
        return int(value)

    def _record_retry(
        self,
        attempt: int,
        error: BaseException,
        *,
        operation: str = "invoke",
        backoff_seconds: float = 0.0,
    ) -> None:
        record_provider_retry(
            attempt, error, operation=operation, backoff_seconds=backoff_seconds
        )

    def _record_limit_reached(self, limit_name: str, limit: int) -> None:
        span = trace.get_current_span()
        if span.is_recording():
            span.add_event(
                "praval.limit.reached",
                {
                    "praval.limit.name": limit_name,
                    "praval.limit.value": limit,
                },
            )

    def _invoke_provider(
        self,
        request: ModelRequest,
        *,
        tools: Optional[List[Dict[str, Any]]],
    ) -> ModelResponse:
        concrete_invoke = self._get_concrete_provider_method("invoke")
        if concrete_invoke is not None:
            try:
                response = concrete_invoke(request, tools=tools)
            except TypeError:
                response = concrete_invoke(request)
            if isinstance(response, ModelResponse):
                return response
            return ModelResponse(content=str(response or ""), raw=response)

        response_text = self.provider.generate(
            messages=[_safe_model_dump(message) for message in request.messages],
            tools=tools,
            hitl_context=request.hitl_context,
        )
        return ModelResponse(
            content=str(response_text or ""),
            provider=self.provider_name,
            model=request.model,
            raw=response_text,
        )

    def _get_concrete_provider_method(self, name: str) -> Optional[Any]:
        method = getattr(type(self.provider), name, None)
        if callable(method):
            return getattr(self.provider, name)
        return None

    def _span(self, request: ModelRequest) -> Any:
        return operation_span(
            "model.invoke",
            kind=trace.SpanKind.CLIENT,
            attributes={
                "gen_ai.provider.name": self.provider_name,
                "gen_ai.request.model": request.model or "",
                "gen_ai.request.streaming": request.stream,
                "praval.tool.count": len(request.tools),
                "praval.max_tool_rounds": self._tool_round_limit(request),
            },
        )

    def _provider_span(self, request: ModelRequest, operation: str) -> Any:
        return operation_span(
            f"provider.{operation}",
            kind=trace.SpanKind.CLIENT,
            attributes={
                "gen_ai.provider.name": self.provider_name,
                "gen_ai.request.model": request.model or "",
                "gen_ai.operation.name": operation,
            },
        )
