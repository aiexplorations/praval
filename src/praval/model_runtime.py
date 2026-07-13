"""Provider-neutral model runtime.

The runtime is the stable execution boundary between agents and providers. It
keeps the legacy string API working while exposing neutral request/response
objects for newer provider features.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import json
from typing import Any, AsyncIterator, Dict, Iterator, List, Literal, Optional

from .core.exceptions import HITLConfigurationError, InterventionRequired, ProviderError
from .hitl.runtime import HITLRuntime
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

UNSAFE_PROVIDER_OPTION_KEYS = {
    "api_key",
    "authorization",
    "default_headers",
    "headers",
    "organization",
}
EXPERIMENTAL_TOOL_PROVIDERS = {"openai", "anthropic"}
MAX_SCHEMA_BYTES = 65536
MAX_TOOL_ROUNDS = 8


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
    if isinstance(value, dict):
        return ReasoningConfig(**value)
    raise TypeError("reasoning must be a dict or ReasoningConfig")


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
    """Execute a legacy provider tool call with optional HITL gating."""
    tool_def = _tool_map(available_tools or []).get(function_name)
    if tool_def is not None and tool_def.get("async_only"):
        raise ProviderError(
            "This tool is async-only; use Agent.agenerate() or Agent.astream()."
        )
    runtime = _build_hitl_runtime(hitl_context)
    if resume_intervention is not None and runtime is not None:
        return runtime.execute_with_decision(
            intervention=resume_intervention,
            available_tools=available_tools or [],
        )
    if runtime is not None and continuation_state is not None:
        return runtime.execute_or_interrupt(
            tool_call_id=tool_call_id,
            function_name=function_name,
            raw_args=raw_args,
            available_tools=available_tools or [],
            continuation_state=continuation_state,
        )

    if tool_def is None:
        return f"Unknown function: {function_name}"
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
) -> Any:
    """Execute a tool on the caller's event loop with optional HITL gating."""
    runtime = _build_hitl_runtime(hitl_context)
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
        return f"Unknown function: {function_name}"
    return await _execute_tool_direct_async(tool_def, HITLRuntime._parse_args(raw_args))


def _build_hitl_runtime(
    hitl_context: Optional[Dict[str, Any]],
) -> Optional[HITLRuntime]:
    if not hitl_context:
        return None
    run_id = hitl_context.get("run_id")
    agent_name = hitl_context.get("agent_name")
    provider_name = hitl_context.get("provider_name")
    if not run_id or not agent_name or not provider_name:
        return None
    return HITLRuntime(
        run_id=run_id,
        agent_name=agent_name,
        provider_name=provider_name,
        hitl_enabled=bool(hitl_context.get("enabled", False)),
        db_path=hitl_context.get("db_path"),
        trace_id=hitl_context.get("trace_id"),
    )


def _tool_map(available_tools: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    mapping: Dict[str, Dict[str, Any]] = {}
    for tool in available_tools or []:
        func = tool.get("function")
        if callable(func):
            mapping[str(tool.get("name") or func.__name__)] = tool
    return mapping


def _execute_tool_direct(tool_def: Dict[str, Any], args: Dict[str, Any]) -> str:
    if tool_def.get("async_only"):
        raise ProviderError(
            "This tool is async-only; use Agent.agenerate() or Agent.astream()."
        )
    tool_func = tool_def.get("function")
    if not callable(tool_func):
        return "Error: Tool function is not callable"
    try:
        result = tool_func(**args)
        if inspect.iscoroutine(result):
            result = _run_coroutine_sync(result)
        return str(result)
    except Exception as exc:
        return f"Error: {str(exc)}"


async def _execute_tool_direct_async(
    tool_def: Dict[str, Any], args: Dict[str, Any]
) -> Any:
    tool_func = tool_def.get("function")
    if not callable(tool_func):
        return "Error: Tool function is not callable"
    try:
        result = tool_func(**args)
        if inspect.isawaitable(result):
            result = await result
        return result
    except Exception as exc:
        return f"Error: {str(exc)}"


def _run_coroutine_sync(coroutine: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda: asyncio.run(coroutine))
        return future.result()


class ModelRuntime:
    """Runtime wrapper for provider-neutral model execution."""

    def __init__(
        self,
        *,
        provider: Any,
        provider_name: str,
        config: Any,
    ) -> None:
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

    def invoke(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        hitl_context: Optional[Dict[str, Any]] = None,
        response_schema: Optional[StructuredOutputConfig] = None,
        reasoning: Optional[ReasoningConfig] = None,
        provider_options: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stream_options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
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
        )
        with self._span(request):
            self.validate_request(request)
            response = self._invoke_with_retries(request, tools=tools)
            if not response.provider:
                response.provider = self.provider_name
            if not response.model:
                response.model = request.model
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

    async def ainvoke(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        hitl_context: Optional[Dict[str, Any]] = None,
        response_schema: Optional[StructuredOutputConfig] = None,
        reasoning: Optional[ReasoningConfig] = None,
        provider_options: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stream_options: Optional[Dict[str, Any]] = None,
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
        )
        with self._span(request):
            self.validate_request(request)
            return await self._ainvoke_with_retries(request, tools=tools)

    def stream(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        hitl_context: Optional[Dict[str, Any]] = None,
        response_schema: Optional[StructuredOutputConfig] = None,
        reasoning: Optional[ReasoningConfig] = None,
        provider_options: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stream_options: Optional[Dict[str, Any]] = None,
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
        )
        self.validate_request(request)
        yield ModelEvent(
            type="start",
            metadata={
                "provider": self.provider_name,
                "model": request.model,
                "native_streaming": self.resolve_capabilities(request).native_streaming,
            },
        )
        if tools:
            with self._span(request):
                response = self._invoke_with_retries(request, tools=tools)
            yield from self._response_events(response)
            return
        provider_stream = self._get_concrete_provider_method("stream")
        if provider_stream is not None:
            try:
                yield from provider_stream(request, tools=tools)
            except TypeError:
                yield from provider_stream(request)
            return

        response = self.invoke(
            messages=messages,
            tools=tools,
            hitl_context=hitl_context,
            response_schema=response_schema,
            reasoning=reasoning,
            provider_options=provider_options,
            timeout=timeout,
            metadata=metadata,
            stream_options=stream_options,
        )
        if response.content:
            yield ModelEvent(type="delta", delta=response.content)
        if response.usage:
            yield ModelEvent(type="usage", usage=response.usage)
        yield ModelEvent(type="final", response=response, usage=response.usage)

    async def astream(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        hitl_context: Optional[Dict[str, Any]] = None,
        response_schema: Optional[StructuredOutputConfig] = None,
        reasoning: Optional[ReasoningConfig] = None,
        provider_options: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stream_options: Optional[Dict[str, Any]] = None,
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
        )
        self.validate_request(request)
        if tools:
            yield ModelEvent(
                type="start",
                metadata={
                    "provider": self.provider_name,
                    "model": request.model,
                    "native_streaming": False,
                },
            )
            response = await self.ainvoke(
                messages=messages,
                tools=tools,
                hitl_context=hitl_context,
                response_schema=response_schema,
                reasoning=reasoning,
                provider_options=provider_options,
                timeout=timeout,
                metadata=metadata,
                stream_options=stream_options,
            )
            for event in self._response_events(response):
                yield event
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
            try:
                events = concrete_astream(request, tools=tools)
            except TypeError:
                events = concrete_astream(request)
            async for event in events:
                yield event
            return

        for event in self.stream(
            messages=messages,
            tools=tools,
            hitl_context=hitl_context,
            response_schema=response_schema,
            reasoning=reasoning,
            provider_options=provider_options,
            timeout=timeout,
            metadata=metadata,
            stream_options=stream_options,
        ):
            yield event

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
        reasoning: Optional[ReasoningConfig] = None,
        provider_options: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stream_options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
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
        unsafe = UNSAFE_PROVIDER_OPTION_KEYS.intersection(request.provider_options)
        if unsafe:
            blocked = ", ".join(sorted(unsafe))
            raise ProviderError(f"Unsafe provider option(s): {blocked}")
        self._validate_experimental_tools(request)
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
        retries = int(getattr(self.config, "retries", 0) or 0)
        last_error: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                response = self._complete_response(
                    self._invoke_provider(request, tools=tools),
                    request,
                )
                return self._orchestrate_tool_calls(
                    request,
                    response,
                    tools=tools or [],
                )
            except ProviderError as exc:
                last_error = exc
                if attempt >= retries:
                    raise
            except (InterventionRequired, HITLConfigurationError):
                raise
            except Exception as exc:
                last_error = exc
                if attempt >= retries:
                    raise ProviderError(str(exc)) from exc
        if last_error is not None:
            raise ProviderError(str(last_error)) from last_error
        raise ProviderError("Provider did not return a response")

    async def _ainvoke_with_retries(
        self,
        request: ModelRequest,
        *,
        tools: Optional[List[Dict[str, Any]]],
    ) -> ModelResponse:
        """Async provider invocation and tool orchestration with retries."""
        retries = int(getattr(self.config, "retries", 0) or 0)
        last_error: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                raw_response = await self._invoke_provider_async(request, tools=tools)
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
            except ProviderError as exc:
                last_error = exc
                if attempt >= retries:
                    raise
            except (InterventionRequired, HITLConfigurationError):
                raise
            except Exception as exc:
                last_error = exc
                if attempt >= retries:
                    raise ProviderError(str(exc)) from exc
        if last_error is not None:
            raise ProviderError(str(last_error)) from last_error
        raise ProviderError("Provider did not return a response")

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
        return await loop.run_in_executor(
            None,
            lambda: self._invoke_provider(request, tools=tools),
        )

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
        for round_index in range(start_round, MAX_TOOL_ROUNDS):
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
            continued = continuation(request, current, round_results)
            if isinstance(continued, ModelResponse):
                current = self._complete_response(continued, request)
            else:
                current = self._complete_response(
                    ModelResponse(content=str(continued or ""), raw=continued),
                    request,
                )
        else:
            if current.tool_calls:
                raise ProviderError(
                    f"Provider exceeded maximum tool rounds ({MAX_TOOL_ROUNDS})"
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
        for round_index in range(start_round, MAX_TOOL_ROUNDS):
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
            continued = await self._continue_with_tool_results_async(
                continuation, request, current, round_results
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
                raise ProviderError(
                    f"Provider exceeded maximum tool rounds ({MAX_TOOL_ROUNDS})"
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
        continued = await loop.run_in_executor(
            None,
            lambda: continuation(request, response, results),
        )
        if inspect.isawaitable(continued):
            return await continued
        return continued

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
        content = execute_legacy_tool_call(
            hitl_context=hitl_context,
            tool_call_id=blocked_call.id,
            function_name=blocked_call.name,
            raw_args=blocked_call.arguments,
            available_tools=available_tools,
            resume_intervention=resume_intervention,
        )
        round_results.append(self._tool_result(blocked_call, content))

        for next_index in range(current_index + 1, len(round_calls)):
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

        continuation = self._get_concrete_provider_method("continue_with_tool_results")
        if continuation is None:
            raise ProviderError(
                f"Provider '{self.provider_name}' does not support tool continuation"
            )
        continued = continuation(request, current, round_results)
        if isinstance(continued, ModelResponse):
            next_response = self._complete_response(continued, request)
        else:
            next_response = self._complete_response(
                ModelResponse(content=str(continued or ""), raw=continued),
                request,
            )
        return self._orchestrate_tool_calls(
            request,
            next_response,
            tools=available_tools,
            initial_calls=all_calls,
            initial_results=all_results + round_results,
            start_round=round_index + 1,
        )

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
        content = await execute_legacy_tool_call_async(
            hitl_context=hitl_context,
            tool_call_id=blocked_call.id,
            function_name=blocked_call.name,
            raw_args=blocked_call.arguments,
            available_tools=available_tools,
            resume_intervention=resume_intervention,
        )
        if isinstance(content, ToolResult):
            round_results.append(
                content.model_copy(
                    update={
                        "tool_call_id": blocked_call.id,
                        "name": blocked_call.name,
                    }
                )
            )
        else:
            round_results.append(self._tool_result(blocked_call, str(content)))

        for next_index in range(current_index + 1, len(round_calls)):
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

        continuation = self._get_concrete_provider_method("continue_with_tool_results")
        if continuation is None:
            raise ProviderError(
                f"Provider '{self.provider_name}' does not support tool continuation"
            )
        continued = await self._continue_with_tool_results_async(
            continuation, request, current, round_results
        )
        if isinstance(continued, ModelResponse):
            next_response = self._complete_response(continued, request)
        else:
            next_response = self._complete_response(
                ModelResponse(content=str(continued or ""), raw=continued),
                request,
            )
        return await self._orchestrate_tool_calls_async(
            request,
            next_response,
            tools=available_tools,
            initial_calls=all_calls,
            initial_results=all_results + round_results,
            start_round=round_index + 1,
        )

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
            "provider": self.provider_name,
            "model": request.model,
            "round": round_index,
            "tool_call": tool_call.model_dump(exclude_none=True),
            "tool_results": [
                result.model_dump(exclude_none=True) for result in previous_results
            ],
        }
        content = execute_legacy_tool_call(
            hitl_context=request.hitl_context,
            tool_call_id=tool_call.id,
            function_name=tool_call.name,
            raw_args=tool_call.arguments,
            available_tools=tools,
            continuation_state=state,
        )
        return self._tool_result(tool_call, content)

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
        content = await execute_legacy_tool_call_async(
            hitl_context=request.hitl_context,
            tool_call_id=tool_call.id,
            function_name=tool_call.name,
            raw_args=tool_call.arguments,
            available_tools=tools,
            continuation_state=state,
        )
        if isinstance(content, ToolResult):
            return content.model_copy(
                update={"tool_call_id": tool_call.id, "name": tool_call.name}
            )
        return self._tool_result(tool_call, str(content))

    def _tool_result(self, tool_call: ToolCall, content: str) -> ToolResult:
        return ToolResult(
            tool_call_id=tool_call.id,
            name=tool_call.name,
            content=content,
            is_error=content.startswith("Error:")
            or content.startswith("Unknown function:"),
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
            "metadata": _json_safe(response.metadata),
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
        return response

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
        try:
            from .observability.tracing import SpanKind, get_tracer

            tracer = get_tracer()
            return tracer.start_as_current_span(
                "model.invoke",
                kind=SpanKind.CLIENT,
                attributes={
                    "provider": self.provider_name,
                    "model": request.model or "",
                    "stream": request.stream,
                    "tool_count": len(request.tools),
                },
            )
        except Exception:
            return _NoOpSpan()


class _NoOpSpan:
    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        return False
