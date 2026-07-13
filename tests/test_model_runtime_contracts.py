"""Tests for provider-neutral model contracts and runtime."""

import asyncio
from unittest.mock import Mock

import pytest

from praval.core.agent import AgentConfig
from praval.core.exceptions import ProviderError
from praval.model_runtime import (
    ModelRuntime,
    execute_legacy_tool_call,
    legacy_tool_to_spec,
)
from praval.models import (
    AudioResponse,
    ContentPart,
    ModelEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ProviderCapabilities,
    ReasoningConfig,
    SpeechRequest,
    ToolCall,
    ToolResult,
    TranscriptionRequest,
)
from praval.providers.registry import get_provider_registry, reset_provider_registry


def test_content_part_text_constructor():
    part = ContentPart.text_part("hello")

    assert part.type == "text"
    assert part.text == "hello"


def test_content_part_image_and_file_constructors():
    image = ContentPart.image_base64("abc", "image/jpeg")
    file_part = ContentPart.file_data("ZGF0YQ==", "application/pdf", name="a.pdf")
    file_url = ContentPart.file_url(
        "https://example.com/a.pdf", "application/pdf", name="a.pdf"
    )

    assert image.type == "image_base64"
    assert image.mime_type == "image/jpeg"
    assert file_part.type == "file"
    assert file_part.metadata["name"] == "a.pdf"
    assert file_url.type == "file_url"
    assert file_url.url == "https://example.com/a.pdf"


def test_content_part_audio_and_video_constructors():
    audio = ContentPart.audio_base64("abc", "audio/mpeg")
    audio_url = ContentPart.audio_url("https://example.com/a.mp3", "audio/mpeg")
    video = ContentPart.video_base64("def", "video/mp4")
    video_url = ContentPart.video_url("https://example.com/v.mp4", "video/mp4")

    assert audio.type == "audio_base64"
    assert audio.mime_type == "audio/mpeg"
    assert audio_url.type == "audio_url"
    assert video.type == "video_base64"
    assert video_url.type == "video_url"


def test_request_based_audio_contracts():
    transcription = TranscriptionRequest(
        audio=b"wav",
        model="gpt-4o-transcribe",
        filename="sample.wav",
        language="en",
    )
    speech = SpeechRequest(
        input="Hello",
        model="tts-1",
        voice="alloy",
        response_format="wav",
    )
    response = AudioResponse(
        data=b"audio",
        provider="openai",
        model="tts-1",
        format="wav",
        mime_type="audio/wav",
    )

    assert transcription.audio == b"wav"
    assert transcription.filename == "sample.wav"
    assert speech.input == "Hello"
    assert speech.voice == "alloy"
    assert response.data == b"audio"
    assert response.mime_type == "audio/wav"


def test_model_request_serializes_messages():
    request = ModelRequest(
        provider="openai",
        model="gpt-test",
        messages=[ModelMessage(role="user", content="hello")],
    )

    dumped = request.model_dump()
    assert dumped["provider"] == "openai"
    assert dumped["messages"][0]["content"] == "hello"


def test_legacy_tool_to_spec_preserves_approval_metadata():
    def search(query: str) -> str:
        return query

    spec = legacy_tool_to_spec(
        {
            "function": search,
            "description": "Search",
            "parameters": {"query": {"type": "str", "required": True}},
            "requires_approval": True,
            "risk_level": "medium",
            "approval_reason": "External lookup",
        },
        strict=True,
    )

    assert spec is not None
    assert spec.name == "search"
    assert spec.parameters["required"] == ["query"]
    assert spec.strict is True
    assert spec.requires_approval is True
    assert spec.risk_level == "medium"


def test_model_runtime_uses_legacy_provider_generate_when_no_adapter_method():
    provider = Mock()
    provider.generate.return_value = "runtime response"
    runtime = ModelRuntime(
        provider=provider,
        provider_name="fake",
        config=AgentConfig(provider="fake", model="fake-model"),
    )

    response = runtime.invoke(messages=[{"role": "user", "content": "hello"}])

    assert isinstance(response, ModelResponse)
    assert response.content == "runtime response"
    assert response.provider == "fake"
    assert response.model == "fake-model"
    provider.generate.assert_called_once()


def test_model_runtime_rejects_unsupported_declared_capability():
    class BasicProvider:
        capabilities = ProviderCapabilities()

        def generate(self, **_: object) -> str:
            return "not reached"

    runtime = ModelRuntime(
        provider=BasicProvider(),
        provider_name="basic",
        config=AgentConfig(provider="basic", model="basic-model"),
    )

    with pytest.raises(ProviderError, match="does not support reasoning config"):
        runtime.invoke(
            messages=[{"role": "user", "content": "hello"}],
            reasoning=ReasoningConfig(effort="low"),
        )


def test_runtime_rejects_unsafe_provider_options():
    provider = Mock()
    provider.generate.return_value = "not reached"
    runtime = ModelRuntime(
        provider=provider,
        provider_name="openai",
        config=AgentConfig(provider="openai", model="gpt-test"),
    )

    with pytest.raises(ProviderError, match="Unsafe provider option"):
        runtime.invoke(
            messages=[{"role": "user", "content": "hello"}],
            provider_options={"api_key": "secret"},
        )


def test_runtime_requires_explicit_opt_in_for_experimental_provider_tools():
    provider = Mock()
    provider.generate.return_value = "not reached"
    runtime = ModelRuntime(
        provider=provider,
        provider_name="openai",
        config=AgentConfig(provider="openai", model="gpt-test"),
    )

    with pytest.raises(ProviderError, match="allow_experimental_tools"):
        runtime.invoke(
            messages=[{"role": "user", "content": "search"}],
            provider_options={
                "endpoint": "responses",
                "experimental_tools": [{"type": "web_search"}],
            },
        )


def test_runtime_rejects_credentials_nested_in_experimental_provider_tools():
    provider = Mock()
    provider.generate.return_value = "not reached"
    runtime = ModelRuntime(
        provider=provider,
        provider_name="openai",
        config=AgentConfig(provider="openai", model="gpt-test"),
    )

    with pytest.raises(ProviderError, match="Unsafe experimental tool option"):
        runtime.invoke(
            messages=[{"role": "user", "content": "search"}],
            provider_options={
                "endpoint": "responses",
                "allow_experimental_tools": True,
                "experimental_tools": [
                    {
                        "type": "mcp",
                        "server_url": "https://example.com/mcp",
                        "headers": {"Authorization": "Bearer secret"},
                    }
                ],
            },
        )


def test_runtime_resolves_conservative_local_capabilities():
    provider = Mock()
    provider.generate.return_value = "not reached"
    runtime = ModelRuntime(
        provider=provider,
        provider_name="ollama",
        config=AgentConfig(provider="ollama", model="llama3"),
    )

    with pytest.raises(ProviderError, match="structured outputs"):
        runtime.invoke(
            messages=[{"role": "user", "content": "hello"}],
            response_schema={"type": "object", "properties": {}},
        )


def test_runtime_capability_override_allows_local_structured_output():
    provider = Mock()
    provider.generate.return_value = "ok"
    runtime = ModelRuntime(
        provider=provider,
        provider_name="ollama",
        config=AgentConfig(provider="ollama", model="llama3"),
    )

    response = runtime.invoke(
        messages=[{"role": "user", "content": "hello"}],
        response_schema={"type": "object", "properties": {}},
        provider_options={"capabilities": {"structured_outputs": True}},
    )

    assert response.content == "ok"


def test_runtime_accepts_openai_image_parts_and_rejects_local_image_parts():
    openai_provider = Mock()
    openai_provider.generate.return_value = "vision"
    openai_runtime = ModelRuntime(
        provider=openai_provider,
        provider_name="openai",
        config=AgentConfig(provider="openai", model="gpt-5.4-mini"),
    )

    response = openai_runtime.invoke(
        messages=[
            {
                "role": "user",
                "content": [
                    ContentPart.text_part("describe"),
                    ContentPart.image_url("https://example.com/image.png"),
                ],
            }
        ]
    )

    assert response.content == "vision"

    local_runtime = ModelRuntime(
        provider=Mock(),
        provider_name="ollama",
        config=AgentConfig(provider="ollama", model="llama3"),
    )
    with pytest.raises(ProviderError, match="image input"):
        local_runtime.invoke(
            messages=[
                {
                    "role": "user",
                    "content": [ContentPart.image_url("https://example.com/a.png")],
                }
            ]
        )


def test_runtime_rejects_unsupported_file_part():
    provider = Mock()
    runtime = ModelRuntime(
        provider=provider,
        provider_name="openai",
        config=AgentConfig(provider="openai", model="gpt-5.4-mini"),
    )

    with pytest.raises(ProviderError, match="file input"):
        runtime.invoke(
            messages=[
                {
                    "role": "user",
                    "content": [
                        ContentPart.file_data("ZGF0YQ==", "application/pdf"),
                    ],
                }
            ]
        )


def test_runtime_accepts_gemini_audio_video_parts_and_rejects_local_video_parts():
    gemini_provider = Mock()
    gemini_provider.generate.return_value = "multimodal"
    gemini_runtime = ModelRuntime(
        provider=gemini_provider,
        provider_name="gemini",
        config=AgentConfig(provider="gemini", model="gemini-3.5-flash"),
    )

    response = gemini_runtime.invoke(
        messages=[
            {
                "role": "user",
                "content": [
                    ContentPart.text_part("summarize"),
                    ContentPart.audio_base64("abc", "audio/mpeg"),
                    ContentPart.video_url("https://example.com/v.mp4", "video/mp4"),
                ],
            }
        ]
    )

    assert response.content == "multimodal"

    local_runtime = ModelRuntime(
        provider=Mock(),
        provider_name="ollama",
        config=AgentConfig(provider="ollama", model="llama3"),
    )
    with pytest.raises(ProviderError, match="video input"):
        local_runtime.invoke(
            messages=[
                {
                    "role": "user",
                    "content": [ContentPart.video_base64("abc", "video/mp4")],
                }
            ]
        )


def test_runtime_rejects_native_streaming_without_adapter():
    class StreamingProvider:
        capabilities = ProviderCapabilities(streaming=True, native_streaming=True)

        def generate(self, **_: object) -> str:
            return "not reached"

    runtime = ModelRuntime(
        provider=StreamingProvider(),
        provider_name="streaming",
        config=AgentConfig(provider="streaming", model="stream-model"),
    )

    with pytest.raises(ProviderError, match="native streaming"):
        list(runtime.stream(messages=[{"role": "user", "content": "hello"}]))


def test_runtime_stream_emits_start_before_provider_events():
    class StreamingProvider:
        capabilities = ProviderCapabilities(streaming=True, native_streaming=True)

        def stream(self, request):
            del request
            yield ModelEvent(type="delta", delta="hi")
            yield ModelEvent(type="final", response=ModelResponse(content="hi"))

    runtime = ModelRuntime(
        provider=StreamingProvider(),
        provider_name="streaming",
        config=AgentConfig(provider="streaming", model="stream-model"),
    )

    events = list(runtime.stream(messages=[{"role": "user", "content": "hello"}]))

    assert [event.type for event in events] == ["start", "delta", "final"]
    assert events[0].metadata["native_streaming"] is True


@pytest.mark.asyncio
async def test_runtime_ainvoke_uses_native_async_and_forwards_options():
    class AsyncProvider:
        capabilities = ProviderCapabilities(structured_outputs=True, reasoning=True)

        def __init__(self):
            self.request = None

        async def ainvoke(self, request):
            self.request = request
            return ModelResponse(content="async")

    provider = AsyncProvider()
    runtime = ModelRuntime(
        provider=provider,
        provider_name="async",
        config=AgentConfig(provider="async", model="async-model"),
    )

    response = await runtime.ainvoke(
        messages=[{"role": "user", "content": "hello"}],
        response_schema={"type": "object"},
        reasoning={"mode": "enabled"},
        provider_options={"seed": 7},
        timeout=3,
        metadata={"request_id": "abc"},
        stream_options={"include_usage": True},
    )

    assert response.content == "async"
    assert provider.request.provider_options["seed"] == 7
    assert provider.request.timeout == 3
    assert provider.request.metadata["request_id"] == "abc"
    assert provider.request.stream_options["include_usage"] is True


def test_runtime_applies_provider_profile_options_before_invoke():
    class RecordingProvider:
        def __init__(self):
            self.request = None

        def invoke(self, request):
            self.request = request
            return ModelResponse(content="ok")

    provider = RecordingProvider()
    runtime = ModelRuntime(
        provider=provider,
        provider_name="openai",
        config=AgentConfig(provider="openai", model="gpt-5.4-mini"),
    )

    response = runtime.invoke(messages=[{"role": "user", "content": "hello"}])

    assert response.content == "ok"
    assert provider.request.provider_options["endpoint"] == "responses"


def test_runtime_provider_options_override_profile_options():
    class RecordingProvider:
        def __init__(self):
            self.request = None

        def invoke(self, request):
            self.request = request
            return ModelResponse(content="ok")

    provider = RecordingProvider()
    runtime = ModelRuntime(
        provider=provider,
        provider_name="openai",
        config=AgentConfig(provider="openai", model="gpt-5.4-mini"),
    )

    runtime.invoke(
        messages=[{"role": "user", "content": "hello"}],
        provider_options={"endpoint": "chat.completions"},
    )

    assert provider.request.provider_options["endpoint"] == "chat.completions"


def test_execute_legacy_tool_call_supports_async_tools():
    async def lookup(query: str) -> str:
        return f"found:{query}"

    result = execute_legacy_tool_call(
        hitl_context=None,
        tool_call_id="tool-1",
        function_name="lookup",
        raw_args={"query": "praval"},
        available_tools=[{"function": lookup, "description": "Lookup"}],
    )

    assert result == "found:praval"


def test_runtime_owns_client_tool_execution_and_continuation():
    class ToolProvider:
        capabilities = ProviderCapabilities(tools=True)

        def __init__(self):
            self.continuations = []

        def invoke(self, request):
            return ModelResponse(
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="add",
                        arguments={"x": 2, "y": 3},
                    )
                ]
            )

        def continue_with_tool_results(self, request, response, tool_results):
            self.continuations.append((request, response, tool_results))
            return ModelResponse(content=f"The answer is {tool_results[0].content}.")

    def add(x: int, y: int) -> int:
        return x + y

    provider = ToolProvider()
    runtime = ModelRuntime(
        provider=provider,
        provider_name="fake",
        config=AgentConfig(provider="fake", model="fake-model"),
    )

    response = runtime.invoke(
        messages=[{"role": "user", "content": "Add 2 and 3"}],
        tools=[
            {
                "function": add,
                "description": "Add two integers",
                "parameters": {
                    "x": {"type": "int", "required": True},
                    "y": {"type": "int", "required": True},
                },
            }
        ],
    )

    assert response.content == "The answer is 5."
    assert [call.name for call in response.tool_calls] == ["add"]
    assert response.metadata["tool_results"] == [
        ToolResult(tool_call_id="call-1", name="add", content="5").model_dump()
    ]
    assert provider.continuations[0][2][0].content == "5"


def test_runtime_tool_loop_supports_multiple_rounds_and_stops_at_limit():
    class MultiRoundProvider:
        capabilities = ProviderCapabilities(tools=True)

        def __init__(self):
            self.round = 0

        def invoke(self, request):
            return self._tool_response()

        def continue_with_tool_results(self, request, response, tool_results):
            self.round += 1
            if self.round < 2:
                return self._tool_response()
            return ModelResponse(content="done")

        def _tool_response(self):
            return ModelResponse(
                tool_calls=[
                    ToolCall(id=f"call-{self.round}", name="ping", arguments={})
                ]
            )

    def ping() -> str:
        return "pong"

    runtime = ModelRuntime(
        provider=MultiRoundProvider(),
        provider_name="fake",
        config=AgentConfig(provider="fake", model="fake-model"),
    )
    response = runtime.invoke(
        messages=[{"role": "user", "content": "ping twice"}],
        tools=[{"function": ping, "description": "Ping"}],
    )

    assert response.content == "done"
    assert [call.id for call in response.tool_calls] == ["call-0", "call-1"]
    assert len(response.metadata["tool_results"]) == 2

    class EndlessProvider(MultiRoundProvider):
        def continue_with_tool_results(self, request, response, tool_results):
            self.round += 1
            return self._tool_response()

    endless_runtime = ModelRuntime(
        provider=EndlessProvider(),
        provider_name="fake",
        config=AgentConfig(provider="fake", model="fake-model"),
    )
    with pytest.raises(ProviderError, match="maximum tool rounds"):
        endless_runtime.invoke(
            messages=[{"role": "user", "content": "never stop"}],
            tools=[{"function": ping, "description": "Ping"}],
        )


def test_runtime_tool_stream_emits_normalized_call_and_result_events():
    class ToolProvider:
        capabilities = ProviderCapabilities(tools=True, streaming=True)

        def invoke(self, request):
            return ModelResponse(
                tool_calls=[ToolCall(id="call-1", name="echo", arguments={"x": "hi"})]
            )

        def continue_with_tool_results(self, request, response, tool_results):
            return ModelResponse(content=tool_results[0].content)

    def echo(x: str) -> str:
        return x

    runtime = ModelRuntime(
        provider=ToolProvider(),
        provider_name="fake",
        config=AgentConfig(provider="fake", model="fake-model"),
    )

    events = list(
        runtime.stream(
            messages=[{"role": "user", "content": "echo"}],
            tools=[{"function": echo, "description": "Echo"}],
        )
    )

    assert [event.type for event in events] == [
        "start",
        "tool_call",
        "tool_result",
        "delta",
        "final",
    ]
    assert events[1].tool_call.name == "echo"
    assert events[2].tool_result.content == "hi"
    assert events[-1].response.content == "hi"


@pytest.mark.asyncio
async def test_runtime_async_tool_stream_emits_normalized_events():
    class ToolProvider:
        capabilities = ProviderCapabilities(tools=True, streaming=True)

        def invoke(self, request):
            return ModelResponse(
                tool_calls=[ToolCall(id="call-1", name="echo", arguments={"x": "hi"})]
            )

        def continue_with_tool_results(self, request, response, tool_results):
            return ModelResponse(content=tool_results[0].content)

    def echo(x: str) -> str:
        return x

    runtime = ModelRuntime(
        provider=ToolProvider(),
        provider_name="fake",
        config=AgentConfig(provider="fake", model="fake-model"),
    )
    events = [
        event
        async for event in runtime.astream(
            messages=[{"role": "user", "content": "echo"}],
            tools=[{"function": echo, "description": "Echo"}],
        )
    ]

    assert [event.type for event in events] == [
        "start",
        "tool_call",
        "tool_result",
        "delta",
        "final",
    ]


@pytest.mark.asyncio
async def test_runtime_native_async_invoke_still_owns_tool_execution():
    class AsyncToolProvider:
        capabilities = ProviderCapabilities(tools=True)

        async def ainvoke(self, request):
            return ModelResponse(
                tool_calls=[ToolCall(id="call-1", name="echo", arguments={"x": "hi"})]
            )

        def continue_with_tool_results(self, request, response, tool_results):
            return ModelResponse(content=tool_results[0].content)

    def echo(x: str) -> str:
        return x

    runtime = ModelRuntime(
        provider=AsyncToolProvider(),
        provider_name="fake",
        config=AgentConfig(provider="fake", model="fake-model"),
    )
    response = await runtime.ainvoke(
        messages=[{"role": "user", "content": "echo"}],
        tools=[{"function": echo, "description": "Echo"}],
    )

    assert response.content == "hi"
    assert response.metadata["tool_results"][0]["content"] == "hi"


@pytest.mark.asyncio
async def test_runtime_executes_async_only_tool_on_callers_loop():
    caller_loop = asyncio.get_running_loop()

    class AsyncToolProvider:
        capabilities = ProviderCapabilities(tools=True)

        async def ainvoke(self, request):
            return ModelResponse(
                tool_calls=[
                    ToolCall(id="call-1", name="remote__echo", arguments={"x": "hi"})
                ]
            )

        def continue_with_tool_results(self, request, response, tool_results):
            return ModelResponse(content=tool_results[0].content)

    async def remote_echo(x: str) -> ToolResult:
        assert asyncio.get_running_loop() is caller_loop
        return ToolResult(
            tool_call_id="mcp-internal",
            name="remote__echo",
            content=x,
            metadata={"structured_content": {"echo": x}},
        )

    runtime = ModelRuntime(
        provider=AsyncToolProvider(),
        provider_name="fake",
        config=AgentConfig(provider="fake", model="fake-model"),
    )
    response = await runtime.ainvoke(
        messages=[{"role": "user", "content": "echo"}],
        tools=[
            {
                "name": "remote__echo",
                "function": remote_echo,
                "description": "Echo remotely",
                "parameters": {
                    "type": "object",
                    "properties": {"x": {"type": "string"}},
                    "required": ["x"],
                },
                "async_only": True,
            }
        ],
    )

    result = response.metadata["tool_results"][0]
    assert response.content == "hi"
    assert result["tool_call_id"] == "call-1"
    assert result["metadata"]["structured_content"] == {"echo": "hi"}


def test_runtime_sync_tool_call_rejects_async_only_tool():
    class ToolProvider:
        capabilities = ProviderCapabilities(tools=True)

        def invoke(self, request):
            return ModelResponse(
                tool_calls=[ToolCall(id="call-1", name="remote__echo", arguments={})]
            )

        def continue_with_tool_results(self, request, response, tool_results):
            return ModelResponse(content=tool_results[0].content)

    async def remote_echo() -> str:
        return "hi"

    runtime = ModelRuntime(
        provider=ToolProvider(),
        provider_name="fake",
        config=AgentConfig(provider="fake", model="fake-model"),
    )
    with pytest.raises(ProviderError, match="Agent.agenerate.*Agent.astream"):
        runtime.invoke(
            messages=[{"role": "user", "content": "echo"}],
            tools=[
                {
                    "name": "remote__echo",
                    "function": remote_echo,
                    "async_only": True,
                }
            ],
        )


def test_provider_registry_includes_modern_and_local_providers():
    registry = reset_provider_registry()

    assert "openai" in registry.list_providers()
    assert "anthropic" in registry.list_providers()
    assert "gemini" in registry.list_providers()
    assert "openai-compatible" in registry.list_providers()
    assert registry.get_registration("ollama").name == "openai-compatible"
    assert registry.default_model_for("openai") == "gpt-5.4-mini"
    assert get_provider_registry().get_profile("gemini", "gemini-3.5-flash") is not None
    assert registry.get_profile("openai", "gpt-5.4-nano") is not None
    assert registry.get_profile("anthropic", "claude-fable-5") is not None
    assert registry.get_profile("gemini", "gemini-3.1-flash-lite") is not None
    openai_capabilities = registry.resolve_capabilities("openai", "gpt-5.4-mini")
    anthropic_capabilities = registry.resolve_capabilities(
        "anthropic", "claude-sonnet-5"
    )
    assert openai_capabilities.server_tools is False
    assert openai_capabilities.mcp is False
    assert anthropic_capabilities.server_tools is False
    assert anthropic_capabilities.mcp is False
    assert anthropic_capabilities.computer_use is False


def test_registry_profile_lookup_resolves_local_aliases():
    registry = reset_provider_registry()

    profile = registry.resolve_profile("ollama", "llama3")
    capabilities = registry.resolve_capabilities("ollama", "llama3")

    assert profile is not None
    assert profile.local_preset == "ollama"
    assert capabilities.local is True
    assert capabilities.structured_outputs is False
