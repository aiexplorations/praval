"""Edge-case contracts for the provider-neutral 0.8 model runtime."""

import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

from praval.core.agent import AgentConfig
from praval.core.exceptions import (
    InterventionRequired,
    ProviderAuthenticationError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTransportError,
    ProviderUnavailableError,
    ToolRoundLimitError,
)
from praval.hitl.service import HITLService
from praval.model_runtime import (
    ModelRuntime,
    _execute_tool_direct,
    _json_safe,
    _nested_unsafe_option_keys,
    _retry_backoff_seconds,
    _safe_model_dump,
    _tool_parameter_schema,
    execute_legacy_tool_call,
    legacy_tool_to_spec,
    normalize_content_parts,
    normalize_reasoning_config,
    normalize_structured_output_config,
)
from praval.models import (
    ContentPart,
    ModelEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ProviderCapabilities,
    ReasoningConfig,
    StructuredOutputConfig,
    ToolCall,
    Usage,
)


def _runtime(provider, *, capabilities=None, retries=0):
    if capabilities is not None:
        provider.capabilities = capabilities
    return ModelRuntime(
        provider=provider,
        provider_name="edge-provider",
        config=AgentConfig(
            provider="edge-provider",
            model="edge-model",
            retries=retries,
        ),
    )


def test_runtime_normalizers_cover_supported_and_invalid_values():
    schema = StructuredOutputConfig(schema={"type": "object"})
    reasoning = ReasoningConfig(effort="low")

    assert normalize_structured_output_config(None) is None
    assert normalize_structured_output_config(schema) is schema
    assert normalize_structured_output_config({"schema": {"type": "string"}})
    assert normalize_structured_output_config({"type": "array"}).json_schema == {
        "type": "array"
    }
    assert normalize_reasoning_config(None) is None
    assert normalize_reasoning_config(reasoning) is reasoning
    assert normalize_reasoning_config({"effort": "high"}).effort == "high"
    with pytest.raises(TypeError, match="response_schema"):
        normalize_structured_output_config("invalid")
    with pytest.raises(TypeError, match="reasoning"):
        normalize_reasoning_config("invalid")


def test_runtime_content_and_tool_schema_normalizers_cover_mixed_inputs():
    existing = ContentPart.text_part("one")
    parts = normalize_content_parts(
        [existing, "two", {"type": "image_url", "url": "https://image"}]
    )
    assert parts[0] is existing
    assert parts[1].text == "two"
    assert parts[2].url == "https://image"
    assert normalize_content_parts(existing) == [existing]
    assert normalize_content_parts("plain") == "plain"
    with pytest.raises(TypeError, match="content parts"):
        normalize_content_parts([object()])

    ready = {"type": "object", "properties": {"x": {"type": "string"}}}
    assert _tool_parameter_schema(ready) is ready
    normalized = _tool_parameter_schema(
        {"x": "unknown", "flag": {"type": "bool", "required": True}}
    )
    assert normalized["properties"]["x"] == {"type": "string"}
    assert normalized["properties"]["flag"] == {"type": "boolean"}
    assert normalized["required"] == ["flag"]


def test_runtime_serialization_helpers_drop_opaque_sdk_objects():
    message = ModelMessage(role="user", content="hello")
    assert _safe_model_dump(message)["content"] == "hello"
    assert _safe_model_dump({"x": 1}) == {"x": 1}
    assert _safe_model_dump(object()) == {}
    assert _json_safe((message, object())) == [
        {"role": "user", "content": "hello", "metadata": {}},
        None,
    ]
    assert _nested_unsafe_option_keys(
        [{"config": {"Authorization": "secret", "api_key": "secret"}}]
    ) == ["Authorization", "api_key"]


def test_legacy_tool_conversion_and_direct_execution_errors():
    assert legacy_tool_to_spec({"function": "not-callable"}) is None
    unnamed = Mock()
    unnamed.__name__ = ""
    assert legacy_tool_to_spec({"function": unnamed}) is None
    assert _execute_tool_direct({"function": None}, {}) == (
        "Error: Tool function is not callable"
    )

    def explode() -> None:
        raise RuntimeError("boom")

    assert _execute_tool_direct({"function": explode}, {}) == "Error: boom"
    with pytest.raises(ProviderError, match="Agent.agenerate.*Agent.astream"):
        _execute_tool_direct({"function": explode, "async_only": True}, {})
    assert (
        execute_legacy_tool_call(
            hitl_context=None,
            tool_call_id="missing",
            function_name="missing",
            raw_args={},
            available_tools=[],
        )
        == "Unknown function: missing"
    )


@pytest.mark.asyncio
async def test_direct_async_tool_executes_inside_running_event_loop():
    async def async_tool(value: str) -> str:
        await asyncio.sleep(0)
        return value.upper()

    result = _execute_tool_direct({"function": async_tool}, {"value": "ok"})
    assert result == "OK"


@pytest.mark.parametrize(
    ("model_request", "message"),
    [
        (
            ModelRequest(
                messages=[ModelMessage(role="user", content="x")],
                reasoning=ReasoningConfig(effort="high"),
            ),
            "reasoning effort",
        ),
        (
            ModelRequest(
                messages=[ModelMessage(role="user", content="x")],
                reasoning=ReasoningConfig(budget_tokens=10),
            ),
            "reasoning budgets",
        ),
        (
            ModelRequest(
                messages=[ModelMessage(role="user", content="x")],
                tools=[],
                provider_options={"endpoint": "responses"},
            ),
            "Responses API",
        ),
        (
            ModelRequest(
                messages=[ModelMessage(role="user", content="x")], stream=True
            ),
            "streaming",
        ),
    ],
)
def test_runtime_validation_rejects_unsupported_feature_details(model_request, message):
    capabilities = ProviderCapabilities(reasoning=True)
    runtime = _runtime(Mock(), capabilities=capabilities)

    with pytest.raises(ProviderError, match=message):
        runtime.validate_request(model_request)


def test_runtime_validation_rejects_large_schema_and_unsupported_tools():
    runtime = _runtime(
        Mock(),
        capabilities=ProviderCapabilities(structured_outputs=True),
    )
    large = ModelRequest(
        messages=[ModelMessage(role="user", content="x")],
        response_schema=StructuredOutputConfig(
            schema={"type": "string", "description": "x" * 65536}
        ),
    )
    with pytest.raises(ProviderError, match="response_schema exceeds"):
        runtime.validate_request(large)

    def tool() -> str:
        return "ok"

    tool_request = runtime._build_request(
        messages=[{"role": "user", "content": "x"}],
        tools=[{"function": tool}],
        hitl_context=None,
    )
    with pytest.raises(ProviderError, match="does not support tools"):
        runtime.validate_request(tool_request)


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (
            {"allow_experimental_tools": True, "experimental_tools": "bad"},
            "list of tool mappings",
        ),
        (
            {"allow_experimental_tools": True, "experimental_tools": [{}]},
            "does not support experimental tools",
        ),
    ],
)
def test_runtime_validation_rejects_invalid_experimental_tools(options, message):
    runtime = _runtime(Mock())
    request = ModelRequest(
        provider="edge-provider",
        messages=[ModelMessage(role="user", content="x")],
        provider_options=options,
    )
    with pytest.raises(ProviderError, match=message):
        runtime.validate_request(request)


def test_openai_experimental_tools_require_responses_endpoint():
    runtime = ModelRuntime(
        provider=Mock(),
        provider_name="openai",
        config=AgentConfig(provider="openai", model="gpt-test"),
    )
    request = ModelRequest(
        provider="openai",
        model="gpt-test",
        messages=[ModelMessage(role="user", content="x")],
        provider_options={
            "allow_experimental_tools": True,
            "experimental_tools": [{"type": "web_search"}],
        },
    )
    with pytest.raises(ProviderError, match="Responses API endpoint"):
        runtime.validate_request(request)


def test_runtime_multimodal_validation_rejects_audio_unknown_and_invalid_shapes():
    runtime = _runtime(Mock())
    with pytest.raises(ProviderError, match="audio input"):
        runtime.validate_request(
            ModelRequest(
                messages=[
                    ModelMessage(
                        role="user",
                        content=[ContentPart.audio_base64("AAA")],
                    )
                ]
            )
        )
    with pytest.raises(ProviderError, match="Unsupported content part"):
        runtime.validate_request(
            ModelRequest(
                messages=[
                    ModelMessage(role="user", content=[ContentPart(type="unknown")])
                ]
            )
        )
    with pytest.raises(ProviderError, match="message content must"):
        runtime.validate_request(
            ModelRequest(messages=[ModelMessage(role="user", content=object())])
        )
    request = ModelRequest(messages=[ModelMessage(role="user", content="x")])
    request.messages[0].content = [object()]
    with pytest.raises(ProviderError, match="content parts must"):
        runtime.validate_request(request)


def test_runtime_retries_provider_errors_and_wraps_unexpected_errors():
    class FlakyProvider:
        capabilities = ProviderCapabilities()

        def __init__(self):
            self.calls = 0

        def invoke(self, request):
            self.calls += 1
            if self.calls == 1:
                raise ProviderUnavailableError("retry")
            return "recovered"

    provider = FlakyProvider()
    with patch("praval.model_runtime._sleep"):
        response = _runtime(provider, retries=1).invoke(
            messages=[{"role": "user", "content": "x"}]
        )
    assert response.content == "recovered"
    assert provider.calls == 2

    class BrokenProvider:
        capabilities = ProviderCapabilities()

        def invoke(self, request):
            raise RuntimeError("unexpected")

    with pytest.raises(ProviderError, match="unexpected"):
        _runtime(BrokenProvider()).invoke(messages=[{"role": "user", "content": "x"}])


@pytest.mark.asyncio
async def test_runtime_native_async_accepts_plain_values_and_typeerror_fallback():
    class AsyncProvider:
        capabilities = ProviderCapabilities()

        async def ainvoke(self, request):
            return "async-value"

    response = await _runtime(AsyncProvider()).ainvoke(
        messages=[{"role": "user", "content": "x"}]
    )
    assert response.content == "async-value"
    assert response.provider == "edge-provider"


def test_runtime_non_native_stream_fallback_emits_usage_and_final():
    class Provider:
        capabilities = ProviderCapabilities(streaming=True)

        def invoke(self, request):
            return ModelResponse(
                content="fallback",
                usage=Usage(input_tokens=1, output_tokens=2, total_tokens=3),
            )

    events = list(
        _runtime(Provider()).stream(messages=[{"role": "user", "content": "x"}])
    )
    assert [event.type for event in events] == ["start", "delta", "usage", "final"]


@pytest.mark.asyncio
async def test_runtime_native_and_fallback_async_streams():
    class NativeProvider:
        capabilities = ProviderCapabilities(streaming=True, native_streaming=True)

        async def astream(self, request):
            yield ModelEvent(type="delta", delta="native")
            yield ModelEvent(type="final", response=ModelResponse(content="native"))

    native = [
        event
        async for event in _runtime(NativeProvider()).astream(
            messages=[{"role": "user", "content": "x"}]
        )
    ]
    assert [event.type for event in native] == ["start", "delta", "final"]

    class FallbackProvider:
        capabilities = ProviderCapabilities(streaming=True)

        def invoke(self, request):
            return ModelResponse(content="fallback")

    fallback = [
        event
        async for event in _runtime(FallbackProvider()).astream(
            messages=[{"role": "user", "content": "x"}]
        )
    ]
    assert [event.type for event in fallback] == ["start", "delta", "final"]


def test_runtime_resume_rejects_corrupted_continuation_state():
    runtime = _runtime(Mock())
    with pytest.raises(ProviderError, match="Unsupported"):
        runtime.resume_tool_flow({}, tools=[])
    with pytest.raises(ProviderError, match="intervention decision"):
        runtime.resume_tool_flow(
            {"schema": "model_runtime_tool_v1"}, tools=[], hitl_context={}
        )
    state = {
        "schema": "model_runtime_tool_v1",
        "request": {"messages": [{"role": "user", "content": "x"}]},
        "response": {},
        "round_calls": [],
        "current_index": 0,
    }
    with pytest.raises(ProviderError, match="index is invalid"):
        runtime.resume_tool_flow(
            state,
            tools=[],
            hitl_context={"resume_intervention": {"decision": "APPROVE"}},
        )


def test_runtime_restore_helpers_reject_missing_state_and_span_falls_back():
    runtime = _runtime(Mock())
    with pytest.raises(ProviderError, match="request state"):
        runtime._restore_runtime_request(None, tools=[], hitl_context=None)
    with pytest.raises(ProviderError, match="response state"):
        runtime._restore_runtime_response(None)

    request = ModelRequest(messages=[ModelMessage(role="user", content="x")])
    with patch("praval.observability.tracing.get_tracer", side_effect=RuntimeError):
        with runtime._span(request):
            pass


# --- Per-request retry (v0.8.4) ------------------------------------------


class _TwoRoundProvider:
    """Round 1 calls ``record_a``, round 2 calls ``record_b``, then answers.

    The round-2 continuation (the request that carries ``record_b``'s result)
    fails ``failures`` times with ``error_factory()`` before succeeding.
    """

    capabilities = ProviderCapabilities(tools=True, streaming=True)

    def __init__(self, failures=1, error_factory=None):
        self.invoke_calls = 0
        self.continuation_calls = 0
        self.failures = failures
        self.error_factory = error_factory or (
            lambda: ProviderUnavailableError("overloaded")
        )

    def invoke(self, request):
        self.invoke_calls += 1
        return ModelResponse(
            tool_calls=[ToolCall(id="call-a", name="record_a", arguments={})]
        )

    def continue_with_tool_results(self, request, response, tool_results):
        self.continuation_calls += 1
        if tool_results[0].name == "record_a":
            return ModelResponse(
                tool_calls=[ToolCall(id="call-b", name="record_b", arguments={})]
            )
        if self.failures:
            self.failures -= 1
            raise self.error_factory()
        return ModelResponse(content="done")


def _counting_tools(counter, *, approve_b=False):
    def record_a() -> str:
        counter["a"] += 1
        return "a recorded"

    def record_b() -> str:
        counter["b"] += 1
        return "b recorded"

    return [
        {"function": record_a, "description": "Record A"},
        {
            "function": record_b,
            "description": "Record B",
            "requires_approval": approve_b,
        },
    ]


def _run_mode(runtime, mode, tools):
    messages = [{"role": "user", "content": "record both"}]
    if mode == "invoke":
        return runtime.invoke(messages=messages, tools=tools).content
    if mode == "stream":
        events = list(runtime.stream(messages=messages, tools=tools))
        return events[-1].response.content

    async def _async_run():
        if mode == "ainvoke":
            return (await runtime.ainvoke(messages=messages, tools=tools)).content
        events = [
            event async for event in runtime.astream(messages=messages, tools=tools)
        ]
        return events[-1].response.content

    return asyncio.run(_async_run())


@pytest.mark.parametrize("mode", ["invoke", "ainvoke", "stream", "astream"])
def test_failed_continuation_retry_never_repeats_earlier_tools(mode):
    counter = {"a": 0, "b": 0}
    provider = _TwoRoundProvider(failures=1)
    runtime = _runtime(provider, retries=2)
    with (
        patch("praval.model_runtime._sleep") as sleep,
        patch("praval.model_runtime._async_sleep", new=AsyncMock()) as async_sleep,
    ):
        content = _run_mode(runtime, mode, _counting_tools(counter))

    assert content == "done"
    assert counter == {"a": 1, "b": 1}
    assert provider.invoke_calls == 1
    assert provider.continuation_calls == 3
    assert sleep.call_count + async_sleep.await_count == 1


@pytest.mark.parametrize("use_async", [False, True])
def test_hitl_resume_retries_only_the_failed_continuation(tmp_path, use_async):
    counter = {"a": 0, "b": 0}
    tools = _counting_tools(counter, approve_b=True)
    provider = _TwoRoundProvider(failures=1)
    runtime = _runtime(provider, retries=1)
    db_path = str(tmp_path / "hitl.db")
    hitl_context = {
        "enabled": True,
        "run_id": f"run-retry-{use_async}",
        "agent_name": "retry-agent",
        "provider_name": "edge-provider",
        "db_path": db_path,
    }
    with pytest.raises(InterventionRequired):
        runtime.invoke(
            messages=[{"role": "user", "content": "record both"}],
            tools=tools,
            hitl_context=hitl_context,
        )
    assert counter == {"a": 1, "b": 0}

    service = HITLService(db_path=db_path)
    pending = service.get_pending_interventions(run_id=hitl_context["run_id"])
    approved = service.approve_intervention(pending[0].id, reviewer="qa")
    suspended = service.get_suspended_run(hitl_context["run_id"])
    resume_context = {**hitl_context, "resume_intervention": approved.to_dict()}

    with (
        patch("praval.model_runtime._sleep") as sleep,
        patch("praval.model_runtime._async_sleep", new=AsyncMock()) as async_sleep,
    ):
        if use_async:
            response = asyncio.run(
                runtime.resume_tool_flow_async(suspended.state, tools, resume_context)
            )
        else:
            response = runtime.resume_tool_flow(suspended.state, tools, resume_context)

    assert response.content == "done"
    assert counter == {"a": 1, "b": 1}
    assert provider.invoke_calls == 1
    assert provider.continuation_calls == 3
    assert sleep.call_count + async_sleep.await_count == 1


@pytest.mark.parametrize("use_async", [False, True])
def test_retryable_failures_stop_after_configured_retries(use_async):
    class AlwaysOverloaded:
        capabilities = ProviderCapabilities()

        def __init__(self):
            self.calls = 0

        def invoke(self, request):
            self.calls += 1
            raise ProviderUnavailableError(f"overloaded {self.calls}")

    provider = AlwaysOverloaded()
    runtime = _runtime(provider, retries=2)
    messages = [{"role": "user", "content": "x"}]
    with patch("praval.model_runtime._jitter", side_effect=lambda upper: upper):
        with (
            patch("praval.model_runtime._sleep") as sleep,
            patch("praval.model_runtime._async_sleep", new=AsyncMock()) as async_sleep,
        ):
            with pytest.raises(ProviderUnavailableError, match="overloaded 3") as info:
                if use_async:
                    asyncio.run(runtime.ainvoke(messages=messages))
                else:
                    runtime.invoke(messages=messages)

    assert provider.calls == 3
    delays = [call.args[0] for call in (sleep.call_args_list or [])] + [
        call.args[0] for call in async_sleep.await_args_list
    ]
    assert delays == [0.5, 1.0]
    assert info.value.operation == "invoke"
    assert info.value.provider == "edge-provider"
    assert info.value.model == "edge-model"


def test_non_retryable_continuation_error_raises_immediately():
    counter = {"a": 0, "b": 0}
    provider = _TwoRoundProvider(
        failures=5,
        error_factory=lambda: ProviderInvalidRequestError("bad tool result"),
    )
    runtime = _runtime(provider, retries=3)
    with patch("praval.model_runtime._sleep") as sleep:
        with pytest.raises(
            ProviderInvalidRequestError, match="bad tool result"
        ) as info:
            runtime.invoke(
                messages=[{"role": "user", "content": "x"}],
                tools=_counting_tools(counter),
            )
    sleep.assert_not_called()
    assert provider.continuation_calls == 2
    assert counter == {"a": 1, "b": 1}
    assert info.value.operation == "continue"


def test_unrecognised_adapter_exception_is_wrapped_and_not_retried():
    cause = RuntimeError("socket closed by peer")
    provider = _TwoRoundProvider(failures=5, error_factory=lambda: cause)
    runtime = _runtime(provider, retries=3)
    with patch("praval.model_runtime._sleep") as sleep:
        with pytest.raises(ProviderError, match="socket closed by peer") as info:
            runtime.invoke(
                messages=[{"role": "user", "content": "x"}],
                tools=_counting_tools({"a": 0, "b": 0}),
            )
    sleep.assert_not_called()
    assert type(info.value) is ProviderError
    assert info.value.retryable is False
    assert info.value.__cause__ is cause
    assert provider.continuation_calls == 2


@pytest.mark.parametrize(("hint", "expected"), [(5.0, 5.0), (600.0, 60.0), (0, 0)])
def test_retry_after_hint_is_honoured_and_capped(hint, expected):
    provider = _TwoRoundProvider(
        failures=1,
        error_factory=lambda: ProviderRateLimitError(
            "slow down", retry_after_seconds=hint
        ),
    )
    with patch("praval.model_runtime._sleep") as sleep:
        response = _runtime(provider, retries=1).invoke(
            messages=[{"role": "user", "content": "x"}],
            tools=_counting_tools({"a": 0, "b": 0}),
        )
    assert response.content == "done"
    sleep.assert_called_once_with(expected)


def test_backoff_uses_full_jitter_with_exponential_cap():
    error = ProviderUnavailableError("x")
    with patch("praval.model_runtime._jitter", side_effect=lambda upper: upper):
        ceilings = [_retry_backoff_seconds(attempt, error) for attempt in (1, 2, 3, 7)]
        assert ceilings == [0.5, 1.0, 2.0, 30.0]
        assert _retry_backoff_seconds(10_000, error) == 30.0
    for attempt in (1, 4):
        delay = _retry_backoff_seconds(attempt, error)
        assert 0.0 <= delay <= 0.5 * 2 ** (attempt - 1)


def test_retry_is_recorded_with_operation_and_real_backoff():
    provider = _TwoRoundProvider(failures=1)
    runtime = _runtime(provider, retries=1)
    with (
        patch("praval.model_runtime.record_retry") as record,
        patch("praval.model_runtime._jitter", return_value=0.125),
        patch("praval.model_runtime._sleep"),
    ):
        runtime.invoke(
            messages=[{"role": "user", "content": "x"}],
            tools=_counting_tools({"a": 0, "b": 0}),
        )
    fact = record.call_args.args[0]
    assert fact.attempt == 1
    assert fact.operation == "model.continue"
    assert fact.reason_type == "ProviderUnavailableError"
    assert fact.backoff_ms == 125.0


@pytest.mark.parametrize("use_async", [False, True])
def test_tool_round_limit_raises_typed_error_without_retry(use_async):
    class EndlessProvider(_TwoRoundProvider):
        def continue_with_tool_results(self, request, response, tool_results):
            self.continuation_calls += 1
            return ModelResponse(
                tool_calls=[ToolCall(id="call-a", name="record_a", arguments={})]
            )

    provider = EndlessProvider()
    runtime = _runtime(provider, retries=3)
    tools = _counting_tools({"a": 0, "b": 0})
    messages = [{"role": "user", "content": "x"}]
    with (
        patch("praval.model_runtime._sleep") as sleep,
        patch("praval.model_runtime._async_sleep", new=AsyncMock()) as async_sleep,
    ):
        with pytest.raises(
            ToolRoundLimitError, match=r"maximum tool rounds \(2\)"
        ) as info:
            if use_async:
                asyncio.run(
                    runtime.ainvoke(messages=messages, tools=tools, max_tool_rounds=2)
                )
            else:
                runtime.invoke(messages=messages, tools=tools, max_tool_rounds=2)
    assert isinstance(info.value, ProviderError)
    assert info.value.limit == 2 and info.value.retryable is False
    assert provider.invoke_calls == 1
    assert provider.continuation_calls == 2
    sleep.assert_not_called()
    async_sleep.assert_not_awaited()


def test_async_native_continuation_gets_a_fresh_coroutine_per_attempt():
    class AsyncContinuationProvider(_TwoRoundProvider):
        async def continue_with_tool_results(self, request, response, tool_results):
            return _TwoRoundProvider.continue_with_tool_results(
                self, request, response, tool_results
            )

    counter = {"a": 0, "b": 0}
    provider = AsyncContinuationProvider(failures=2)
    runtime = _runtime(provider, retries=2)
    with patch("praval.model_runtime._async_sleep", new=AsyncMock()) as async_sleep:
        response = asyncio.run(
            runtime.ainvoke(
                messages=[{"role": "user", "content": "x"}],
                tools=_counting_tools(counter),
            )
        )
    assert response.content == "done"
    assert counter == {"a": 1, "b": 1}
    assert provider.continuation_calls == 4
    assert async_sleep.await_count == 2


def test_hitl_exceptions_pass_through_without_retry():
    class PausingProvider:
        capabilities = ProviderCapabilities()

        def __init__(self):
            self.calls = 0

        def invoke(self, request):
            self.calls += 1
            raise InterventionRequired("int-1", "run-1", "agent", "tool")

    provider = PausingProvider()
    with patch("praval.model_runtime._sleep") as sleep:
        with pytest.raises(InterventionRequired):
            _runtime(provider, retries=3).invoke(
                messages=[{"role": "user", "content": "x"}]
            )
    assert provider.calls == 1
    sleep.assert_not_called()


def test_adapter_error_mapping_hook_is_used_and_failures_fall_back():
    class SdkThrottle(Exception):
        pass

    class MappingProvider:
        capabilities = ProviderCapabilities()

        def __init__(self):
            self.calls = 0

        def invoke(self, request):
            self.calls += 1
            if self.calls == 1:
                raise SdkThrottle("429 from sdk")
            return "recovered"

        def map_provider_error(self, exc):
            return ProviderRateLimitError(str(exc), status_code=429)

    provider = MappingProvider()
    with patch("praval.model_runtime._sleep"):
        response = _runtime(provider, retries=1).invoke(
            messages=[{"role": "user", "content": "x"}]
        )
    assert response.content == "recovered"
    assert provider.calls == 2

    class BrokenMappingProvider(MappingProvider):
        def map_provider_error(self, exc):
            raise ValueError("mapper bug")

    broken = BrokenMappingProvider()
    with pytest.raises(ProviderError, match="429 from sdk") as info:
        _runtime(broken, retries=1).invoke(messages=[{"role": "user", "content": "x"}])
    assert type(info.value) is ProviderError
    assert broken.calls == 1


@contextmanager
def _patched_sleeps():
    with (
        patch("praval.model_runtime._sleep") as sleep,
        patch("praval.model_runtime._async_sleep", new=AsyncMock()) as async_sleep,
    ):
        yield sleep, async_sleep


class _FlakyStreamProvider:
    capabilities = ProviderCapabilities(streaming=True, native_streaming=True)

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def stream(self, request):
        self.calls += 1
        failure, deltas = self.script.pop(0)
        for delta in deltas:
            yield ModelEvent(type="delta", delta=delta)
        if failure is not None:
            yield ModelEvent(type="error", metadata={"message": str(failure)})
            raise failure
        yield ModelEvent(type="final", response=ModelResponse(content="".join(deltas)))


class _FlakyAsyncStreamProvider(_FlakyStreamProvider):
    async def astream(self, request):
        for event in self.stream(request):
            yield event


def _collect_stream(runtime, use_async):
    events = []
    messages = [{"role": "user", "content": "x"}]

    async def _consume_async():
        async for event in runtime.astream(messages=messages):
            events.append(event)

    try:
        if use_async:
            asyncio.run(_consume_async())
        else:
            for event in runtime.stream(messages=messages):
                events.append(event)
    except ProviderError as exc:
        return [event.type for event in events], exc
    return [event.type for event in events], None


@pytest.mark.parametrize(
    "provider_class", [_FlakyStreamProvider, _FlakyAsyncStreamProvider]
)
def test_native_stream_retries_only_before_first_event(provider_class):
    use_async = provider_class is _FlakyAsyncStreamProvider

    provider = provider_class(
        [(ProviderTransportError("connect failed"), []), (None, ["he", "llo"])]
    )
    with _patched_sleeps():
        types, error = _collect_stream(_runtime(provider, retries=1), use_async)
    assert error is None
    assert types == ["start", "delta", "delta", "final"]
    assert provider.calls == 2

    provider = provider_class(
        [(ProviderTransportError("dropped"), ["he"]), (None, ["hello"])]
    )
    with _patched_sleeps() as (sleep, async_sleep):
        types, error = _collect_stream(_runtime(provider, retries=3), use_async)
    assert isinstance(error, ProviderTransportError)
    assert types == ["start", "delta", "error"]
    assert provider.calls == 1
    sleep.assert_not_called()
    async_sleep.assert_not_awaited()

    provider = provider_class([(ProviderAuthenticationError("bad key"), [])])
    with _patched_sleeps():
        types, error = _collect_stream(_runtime(provider, retries=3), use_async)
    assert isinstance(error, ProviderAuthenticationError)
    assert error.operation == "stream"
    assert types == ["start", "error"]
    assert provider.calls == 1

    provider = provider_class(
        [(ProviderTransportError("a"), []), (ProviderTransportError("b"), [])]
    )
    with _patched_sleeps():
        types, error = _collect_stream(_runtime(provider, retries=1), use_async)
    assert isinstance(error, ProviderTransportError) and str(error) == "b"
    assert types == ["start", "error"]
    assert provider.calls == 2


def test_native_stream_wraps_unrecognised_errors_and_passes_lone_error_events():
    class OddStreamProvider:
        capabilities = ProviderCapabilities(streaming=True, native_streaming=True)

        def __init__(self, fail):
            self.fail = fail

        def stream(self, request):
            yield ModelEvent(type="error", metadata={"message": "warning only"})
            if self.fail:
                raise KeyError("missing field")

    types, error = _collect_stream(_runtime(OddStreamProvider(False)), False)
    assert error is None
    assert types == ["start", "error"]

    types, error = _collect_stream(_runtime(OddStreamProvider(True), retries=2), False)
    assert type(error) is ProviderError
    assert isinstance(error.__cause__, KeyError)
    assert types == ["start", "error"]
