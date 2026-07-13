"""Compatibility tests for Agent runtime wiring."""

import os
from unittest.mock import Mock, patch

import pytest

from praval.core.agent import Agent, AgentConfig
from praval.core.exceptions import ProviderError
from praval.models import AudioResponse, ContentPart, ModelEvent, ModelResponse


def test_agent_config_parses_compact_model_string():
    config = AgentConfig(model="openai:gpt-test")

    assert config.provider == "openai"
    assert config.model == "gpt-test"


@patch.dict(
    os.environ,
    {"PRAVAL_DEFAULT_PROVIDER": "openai", "PRAVAL_DEFAULT_MODEL": "gpt-env"},
)
@patch("praval.core.agent.ProviderFactory")
def test_agent_uses_environment_provider_and_model_defaults(mock_factory):
    provider = Mock()
    provider.generate.return_value = "hello"
    mock_factory.create_provider.return_value = provider

    agent = Agent("assistant")

    assert agent.provider_name == "openai"
    assert agent.config.model == "gpt-env"
    assert agent.chat("Hello") == "hello"
    provider.generate.assert_called_once()


@patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
@patch("openai.OpenAI")
def test_agent_chat_gpt5_uses_supported_openai_chat_params(mock_openai_class):
    mock_client = Mock()
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "runtime response"
    mock_response.choices[0].message.tool_calls = None
    mock_response.usage = None
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_class.return_value = mock_client

    agent = Agent(
        "assistant",
        provider="openai",
        model="gpt-5-mini",
        config={"temperature": 0.8, "max_tokens": 500},
    )

    response = agent.chat("Hello")

    assert response == "runtime response"
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-5-mini"
    assert call_kwargs["max_completion_tokens"] == 500
    assert "max_tokens" not in call_kwargs
    assert "temperature" not in call_kwargs


@patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
@patch("openai.OpenAI")
def test_agent_chat_gpt5_retries_empty_openai_response(mock_openai_class):
    mock_client = Mock()
    empty_choice = Mock()
    empty_choice.finish_reason = "length"
    empty_choice.message.content = ""
    empty_choice.message.tool_calls = None
    empty_response = Mock()
    empty_response.choices = [empty_choice]
    empty_response.usage = {"prompt_tokens": 3, "completion_tokens": 500}

    final_choice = Mock()
    final_choice.finish_reason = "stop"
    final_choice.message.content = "runtime retry response"
    final_choice.message.tool_calls = None
    final_response = Mock()
    final_response.choices = [final_choice]
    final_response.usage = {"prompt_tokens": 3, "completion_tokens": 12}

    mock_client.chat.completions.create.side_effect = [
        empty_response,
        final_response,
    ]
    mock_openai_class.return_value = mock_client

    agent = Agent(
        "assistant",
        provider="openai",
        model="gpt-5-mini",
        config={"temperature": 0.8, "max_tokens": 500},
    )

    response = agent.chat("Hello")

    assert response == "runtime retry response"
    assert mock_client.chat.completions.create.call_count == 2
    retry_kwargs = mock_client.chat.completions.create.call_args_list[1].kwargs
    assert retry_kwargs["model"] == "gpt-5-mini"
    assert retry_kwargs["max_completion_tokens"] >= 4096
    assert "max_tokens" not in retry_kwargs
    assert "temperature" not in retry_kwargs


@patch("praval.core.agent.ProviderFactory")
def test_agent_generate_returns_model_response(mock_factory):
    provider = Mock()
    provider.generate.return_value = "rich response"
    mock_factory.create_provider.return_value = provider

    agent = Agent("assistant", provider="openai", model="gpt-test")
    response = agent.generate("Hello")

    assert response.content == "rich response"
    assert response.provider == "openai"
    assert response.model == "gpt-test"


@patch("praval.core.agent.ProviderFactory")
def test_agent_request_based_voice_helpers_use_provider_contracts(mock_factory):
    class VoiceProvider:
        def __init__(self):
            self.transcription_request = None
            self.speech_request = None

        def transcribe(self, request):
            self.transcription_request = request
            return AudioResponse(text="transcribed", provider="openai")

        def speak(self, request):
            self.speech_request = request
            return AudioResponse(data=b"speech", provider="openai")

    provider = VoiceProvider()
    mock_factory.create_provider.return_value = provider
    agent = Agent("voice", provider="openai", model="gpt-test")
    original_history = list(agent.conversation_history)

    text = agent.transcribe(
        b"audio",
        model="gpt-4o-transcribe",
        filename="message.wav",
        language="en",
        provider_options={"include": ["logprobs"]},
    )
    audio = agent.speak(
        "Reply",
        model="tts-1",
        voice="alloy",
        response_format="wav",
        speed=1.1,
    )

    assert text == "transcribed"
    assert audio == b"speech"
    assert provider.transcription_request.filename == "message.wav"
    assert provider.transcription_request.model == "gpt-4o-transcribe"
    assert provider.speech_request.model == "tts-1"
    assert provider.speech_request.response_format == "wav"
    assert agent.conversation_history == original_history


@patch("praval.core.agent.ProviderFactory")
def test_agent_voice_helpers_report_unsupported_provider(mock_factory):
    class TextOnlyProvider:
        pass

    mock_factory.create_provider.return_value = TextOnlyProvider()
    agent = Agent("text", provider="cohere", model="command-r")

    with pytest.raises(ProviderError, match="audio transcription"):
        agent.transcribe(b"audio")
    with pytest.raises(ProviderError, match="speech generation"):
        agent.speak("hello")


@patch("praval.core.agent.ProviderFactory")
def test_agent_generate_forwards_runtime_options(mock_factory):
    class Provider:
        def __init__(self):
            self.request = None

        def invoke(self, request, tools=None):
            del tools
            self.request = request
            return ModelResponse(content="rich response")

    provider = Provider()
    mock_factory.create_provider.return_value = provider

    agent = Agent("assistant", provider="openai", model="gpt-test")
    response = agent.generate(
        "Hello",
        response_schema={"type": "object"},
        provider_options={"seed": 1},
        timeout=5,
        metadata={"trace": "abc"},
        stream_options={"include_usage": True},
    )

    assert response.content == "rich response"
    assert provider.request.provider_options["seed"] == 1
    assert provider.request.timeout == 5
    assert provider.request.metadata["trace"] == "abc"
    assert provider.request.stream_options["include_usage"] is True


@patch("praval.core.agent.ProviderFactory")
def test_agent_generate_accepts_multimodal_content_parts(mock_factory):
    class Provider:
        def __init__(self):
            self.request = None

        def invoke(self, request, tools=None):
            del tools
            self.request = request
            return ModelResponse(content="vision response")

    provider = Provider()
    mock_factory.create_provider.return_value = provider

    agent = Agent("vision", provider="openai", model="gpt-test")
    response = agent.generate(
        [
            ContentPart.text_part("describe"),
            ContentPart.image_url("https://example.com/image.png"),
        ]
    )

    assert response.content == "vision response"
    assert provider.request.messages[-1].content[0].type == "text"
    assert provider.request.messages[-1].content[1].type == "image_url"


@pytest.mark.asyncio
@patch("praval.core.agent.ProviderFactory")
async def test_agent_agenerate_forwards_runtime_options(mock_factory):
    class Provider:
        def __init__(self):
            self.request = None

        async def ainvoke(self, request, tools=None):
            del tools
            self.request = request
            return ModelResponse(content="async response")

    provider = Provider()
    mock_factory.create_provider.return_value = provider

    agent = Agent("assistant", provider="openai", model="gpt-test")
    response = await agent.agenerate(
        "Hello",
        response_schema={"type": "object"},
        provider_options={"seed": 2},
        timeout=6,
        metadata={"trace": "def"},
        stream_options={"include_usage": True},
    )

    assert response.content == "async response"
    assert provider.request.provider_options["seed"] == 2
    assert provider.request.timeout == 6
    assert provider.request.metadata["trace"] == "def"
    assert provider.request.stream_options["include_usage"] is True


@patch("praval.core.agent.ProviderFactory")
def test_agent_stream_forwards_runtime_options(mock_factory):
    class Provider:
        def __init__(self):
            self.request = None

        def stream(self, request, tools=None):
            del tools
            self.request = request
            yield ModelEvent(type="delta", delta="hi")
            yield ModelEvent(type="final", response=ModelResponse(content="hi"))

    provider = Provider()
    mock_factory.create_provider.return_value = provider

    agent = Agent("assistant", provider="openai", model="gpt-test")
    events = list(
        agent.stream(
            "Hello",
            provider_options={"seed": 3},
            timeout=7,
            metadata={"trace": "ghi"},
            stream_options={"include_usage": True},
        )
    )

    assert [event.type for event in events] == ["start", "delta", "final"]
    assert provider.request.provider_options["seed"] == 3
    assert provider.request.timeout == 7
    assert provider.request.metadata["trace"] == "ghi"
    assert provider.request.stream_options["include_usage"] is True
