"""Edge-case contracts for the provider-neutral 0.8 model runtime."""

import asyncio
from unittest.mock import Mock, patch

import pytest

from praval.core.agent import AgentConfig
from praval.core.exceptions import ProviderError
from praval.model_runtime import (
    ModelRuntime,
    _execute_tool_direct,
    _json_safe,
    _nested_unsafe_option_keys,
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
                raise ProviderError("retry")
            return "recovered"

    provider = FlakyProvider()
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
