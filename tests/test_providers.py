"""
Tests for LLM provider integrations.

Tests the provider factory and individual provider implementations
to ensure consistent behavior across different LLM APIs.
"""

import os
from unittest.mock import Mock, patch

import pytest

from praval.core.agent import AgentConfig
from praval.core.exceptions import ProviderError
from praval.model_runtime import ModelRuntime
from praval.models import (
    ModelMessage,
    ModelRequest,
    ReasoningConfig,
    SpeechRequest,
    StructuredOutputConfig,
    TranscriptionRequest,
)
from praval.providers.anthropic import AnthropicProvider
from praval.providers.cohere import CohereProvider
from praval.providers.factory import ProviderFactory
from praval.providers.openai import OpenAIProvider


class TestProviderFactory:
    """Test the provider factory functionality."""

    def test_create_openai_provider(self):
        """Test creating OpenAI provider through factory."""
        config = AgentConfig(provider="openai")

        with patch("praval.providers.openai.OpenAIProvider") as mock_provider:
            _ = ProviderFactory.create_provider("openai", config)
            mock_provider.assert_called_once_with(config)

    def test_create_anthropic_provider(self):
        """Test creating Anthropic provider through factory."""
        config = AgentConfig(provider="anthropic")

        with patch("praval.providers.anthropic.AnthropicProvider") as mock_provider:
            _ = ProviderFactory.create_provider("anthropic", config)
            mock_provider.assert_called_once_with(config)

    def test_create_cohere_provider(self):
        """Test creating Cohere provider through factory."""
        config = AgentConfig(provider="cohere")

        with patch("praval.providers.cohere.CohereProvider") as mock_provider:
            _ = ProviderFactory.create_provider("cohere", config)
            mock_provider.assert_called_once_with(config)

    def test_invalid_provider_raises_error(self):
        """Test that invalid provider name raises ProviderError."""
        config = AgentConfig()

        with pytest.raises(ProviderError, match="Unsupported provider"):
            ProviderFactory.create_provider("invalid_provider", config)


class TestOpenAIProvider:
    """Test OpenAI provider implementation."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_provider_initialization(self, mock_openai_class):
        """Test OpenAI provider initializes correctly."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        config = AgentConfig(temperature=0.8, max_tokens=500)
        provider = OpenAIProvider(config)

        assert provider.config == config
        assert provider.client == mock_client

    @patch.dict(os.environ, {}, clear=True)
    def test_openai_missing_api_key_raises_error(self):
        """Test that missing API key raises ProviderError."""
        # Ensure OPENAI_API_KEY is not set
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]

        config = AgentConfig()
        with pytest.raises(
            ProviderError, match="OPENAI_API_KEY environment variable not set"
        ):
            OpenAIProvider(config)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_client_initialization_error(self, mock_openai_class):
        """Test OpenAI client initialization error is wrapped properly."""
        mock_openai_class.side_effect = Exception("Connection failed")

        config = AgentConfig()
        with pytest.raises(ProviderError, match="Failed to initialize OpenAI client"):
            OpenAIProvider(config)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_generate_simple_message(self, mock_openai_class):
        """Test OpenAI provider generates response for simple message."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello! How can I help you?"
        mock_response.choices[0].message.tool_calls = None  # Explicitly set to None
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        config = AgentConfig()
        provider = OpenAIProvider(config)

        messages = [{"role": "user", "content": "Hello"}]
        response = provider.generate(messages)

        assert response == "Hello! How can I help you?"
        mock_client.chat.completions.create.assert_called_once()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_transcribe_normalizes_bytes_request(self, mock_openai_class):
        mock_client = Mock()
        transcription = Mock()
        transcription.text = "Hello from audio."
        mock_client.audio.transcriptions.create.return_value = transcription
        mock_openai_class.return_value = mock_client
        provider = OpenAIProvider(
            AgentConfig(provider_options={"transcription_model": "gpt-4o-transcribe"})
        )

        response = provider.transcribe(
            TranscriptionRequest(
                audio=b"RIFFdata",
                filename="sample.wav",
                mime_type="audio/wav",
                language="en",
                prompt="Praval",
                temperature=0.1,
                timeout=12,
                provider_options={"include": ["logprobs"]},
                metadata={"trace": "audio-test"},
            )
        )

        assert response.text == "Hello from audio."
        assert response.provider == "openai"
        assert response.model == "gpt-4o-transcribe"
        assert response.metadata == {"trace": "audio-test"}
        call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
        assert call_kwargs["file"] == ("sample.wav", b"RIFFdata", "audio/wav")
        assert call_kwargs["model"] == "gpt-4o-transcribe"
        assert call_kwargs["language"] == "en"
        assert call_kwargs["prompt"] == "Praval"
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["timeout"] == 12
        assert call_kwargs["include"] == ["logprobs"]

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_transcribe_closes_opened_path(self, mock_openai_class, tmp_path):
        audio_path = tmp_path / "sample.mp3"
        audio_path.write_bytes(b"audio")
        mock_client = Mock()
        mock_client.audio.transcriptions.create.return_value = {"text": "path text"}
        mock_openai_class.return_value = mock_client
        provider = OpenAIProvider(AgentConfig())

        response = provider.transcribe(
            TranscriptionRequest(audio=audio_path, response_format="json")
        )

        assert response.text == "path text"
        opened_file = mock_client.audio.transcriptions.create.call_args.kwargs["file"]
        assert opened_file.closed is True

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_speak_normalizes_binary_response(self, mock_openai_class):
        mock_client = Mock()
        speech_response = Mock()
        speech_response.content = b"generated-audio"
        mock_client.audio.speech.create.return_value = speech_response
        mock_openai_class.return_value = mock_client
        provider = OpenAIProvider(
            AgentConfig(provider_options={"speech_model": "tts-1-hd"})
        )

        response = provider.speak(
            SpeechRequest(
                input="Hello Praval",
                voice="nova",
                response_format="wav",
                speed=1.25,
                timeout=9,
                provider_options={"extra_headers": {"x-test": "voice"}},
            )
        )

        assert response.data == b"generated-audio"
        assert response.model == "tts-1-hd"
        assert response.mime_type == "audio/wav"
        call_kwargs = mock_client.audio.speech.create.call_args.kwargs
        assert call_kwargs == {
            "input": "Hello Praval",
            "model": "tts-1-hd",
            "voice": "nova",
            "response_format": "wav",
            "speed": 1.25,
            "timeout": 9,
            "extra_headers": {"x-test": "voice"},
        }

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_voice_helpers_reject_streaming_audio(self, mock_openai_class):
        mock_openai_class.return_value = Mock()
        provider = OpenAIProvider(AgentConfig())

        with pytest.raises(ProviderError, match="request-based voice API"):
            provider.transcribe(
                TranscriptionRequest(audio=b"audio", provider_options={"stream": True})
            )

        with pytest.raises(ProviderError, match="request-based voice API"):
            provider.speak(
                SpeechRequest(input="hello", provider_options={"stream": True})
            )

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_speak_validates_speed_and_model_instructions(
        self, mock_openai_class
    ):
        mock_openai_class.return_value = Mock()
        provider = OpenAIProvider(AgentConfig())

        with pytest.raises(ProviderError, match="speed must be between"):
            provider.speak(SpeechRequest(input="hello", speed=4.1))
        with pytest.raises(ProviderError, match="instructions are not supported"):
            provider.speak(
                SpeechRequest(input="hello", model="tts-1", instructions="Whisper")
            )

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_audio_config_options_do_not_leak_into_model_request(
        self, mock_openai_class
    ):
        mock_client = Mock()
        response = Mock()
        response.output_text = "hello"
        response.usage = None
        mock_client.responses.create.return_value = response
        mock_openai_class.return_value = mock_client
        provider = OpenAIProvider(
            AgentConfig(
                model="gpt-5.4-mini",
                provider_options={
                    "endpoint": "responses",
                    "transcription_model": "gpt-4o-transcribe",
                    "speech_model": "tts-1",
                },
            )
        )

        result = provider.invoke(
            ModelRequest(
                provider="openai",
                model="gpt-5.4-mini",
                messages=[ModelMessage(role="user", content="hello")],
                provider_options={
                    "endpoint": "responses",
                    "transcription_model": "gpt-4o-transcribe",
                    "speech_model": "tts-1",
                },
            )
        )

        assert result.content == "hello"
        call_kwargs = mock_client.responses.create.call_args.kwargs
        assert "transcription_model" not in call_kwargs
        assert "speech_model" not in call_kwargs

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_generate_gpt5_uses_supported_chat_params(self, mock_openai_class):
        """Test GPT-5 Chat Completions requests omit unsupported params."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello from GPT-5."
        mock_response.choices[0].message.tool_calls = None
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider(
            AgentConfig(model="gpt-5-mini", temperature=0.8, max_tokens=500)
        )

        response = provider.generate([{"role": "user", "content": "Hello"}])

        assert response == "Hello from GPT-5."
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-5-mini"
        assert call_kwargs["max_completion_tokens"] == 500
        assert "max_tokens" not in call_kwargs
        assert "temperature" not in call_kwargs

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_generate_gpt5_retries_empty_text(self, mock_openai_class):
        """Test GPT-5 empty Chat Completions text gets a larger retry budget."""
        mock_client = Mock()
        empty_choice = Mock()
        empty_choice.finish_reason = "length"
        empty_choice.message.content = ""
        empty_choice.message.tool_calls = None
        empty_response = Mock()
        empty_response.choices = [empty_choice]

        final_choice = Mock()
        final_choice.finish_reason = "stop"
        final_choice.message.content = "Recovered GPT-5 response."
        final_choice.message.tool_calls = None
        final_response = Mock()
        final_response.choices = [final_choice]

        mock_client.chat.completions.create.side_effect = [
            empty_response,
            final_response,
        ]
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider(
            AgentConfig(model="gpt-5-mini", temperature=0.8, max_tokens=500)
        )

        response = provider.generate([{"role": "user", "content": "Hello"}])

        assert response == "Recovered GPT-5 response."
        assert mock_client.chat.completions.create.call_count == 2
        first_kwargs = mock_client.chat.completions.create.call_args_list[0].kwargs
        retry_kwargs = mock_client.chat.completions.create.call_args_list[1].kwargs
        assert first_kwargs["max_completion_tokens"] == 500
        assert retry_kwargs["max_completion_tokens"] >= 4096
        for call_kwargs in (first_kwargs, retry_kwargs):
            assert call_kwargs["model"] == "gpt-5-mini"
            assert "max_tokens" not in call_kwargs
            assert "temperature" not in call_kwargs

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_generate_empty_choices(self, mock_openai_class):
        """Test OpenAI provider handles empty choices gracefully."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = []  # Empty choices
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        config = AgentConfig()
        provider = OpenAIProvider(config)

        messages = [{"role": "user", "content": "Hello"}]
        response = provider.generate(messages)

        assert response == ""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_generate_none_content(self, mock_openai_class):
        """Test OpenAI provider handles None content gracefully."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None  # None content
        mock_response.choices[0].message.tool_calls = None
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        config = AgentConfig()
        provider = OpenAIProvider(config)

        messages = [{"role": "user", "content": "Hello"}]
        response = provider.generate(messages)

        assert response == ""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_generate_with_tools(self, mock_openai_class):
        """Test OpenAI provider handles tool calls correctly."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "I'll calculate that for you."
        mock_response.choices[0].message.tool_calls = None
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        config = AgentConfig()
        provider = OpenAIProvider(config)

        messages = [{"role": "user", "content": "What is 2+2?"}]
        tools = [{"function": lambda x, y: x + y, "description": "Add numbers"}]
        response = provider.generate(messages, tools)

        assert response == "I'll calculate that for you."

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_handles_api_errors(self, mock_openai_class):
        """Test OpenAI provider handles API errors gracefully."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai_class.return_value = mock_client

        config = AgentConfig()
        provider = OpenAIProvider(config)

        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(ProviderError, match="OpenAI API error"):
            provider.generate(messages)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_invoke_responses_api(self, mock_openai_class):
        """Test OpenAI adapter maps reasoning to Responses API parameters."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.output_text = "reasoned answer"
        mock_response.usage = {
            "input_tokens": 4,
            "output_tokens": 5,
            "total_tokens": 9,
            "output_tokens_details": {"reasoning_tokens": 2},
        }
        mock_client.responses.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider(AgentConfig(model="gpt-test"))
        request = ModelRequest(
            provider="openai",
            model="gpt-test",
            messages=[ModelMessage(role="user", content="think")],
            reasoning=ReasoningConfig(effort="medium", summary="auto"),
            response_schema=StructuredOutputConfig(
                name="answer",
                schema={"type": "object", "properties": {"answer": {"type": "string"}}},
            ),
        )

        response = provider.invoke(request)

        assert response.content == "reasoned answer"
        assert response.usage is not None
        assert response.usage.reasoning_tokens == 2
        call_kwargs = mock_client.responses.create.call_args.kwargs
        assert call_kwargs["reasoning"] == {"effort": "medium", "summary": "auto"}
        assert call_kwargs["text"]["format"]["type"] == "json_schema"
        assert call_kwargs["text"]["format"]["name"] == "answer"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_responses_passes_explicit_experimental_tools(
        self, mock_openai_class
    ):
        mock_client = Mock()
        mock_response = Mock()
        mock_response.id = "resp-hosted-tool"
        mock_response.output_text = "searched"
        mock_response.output = []
        mock_response.usage = None
        mock_client.responses.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider(AgentConfig(model="gpt-test"))
        request = ModelRequest(
            provider="openai",
            model="gpt-test",
            messages=[ModelMessage(role="user", content="search")],
            provider_options={
                "endpoint": "responses",
                "allow_experimental_tools": True,
                "experimental_tools": [{"type": "web_search"}],
            },
        )

        response = provider.invoke(request)

        assert response.content == "searched"
        call_kwargs = mock_client.responses.create.call_args.kwargs
        assert call_kwargs["tools"] == [{"type": "web_search"}]
        assert "experimental_tools" not in call_kwargs
        assert "allow_experimental_tools" not in call_kwargs

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_invoke_chat_with_structured_output(self, mock_openai_class):
        """Test OpenAI adapter maps JSON schema to Chat Completions."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"answer":"ok"}'
        mock_response.usage = {"prompt_tokens": 3, "completion_tokens": 4}
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider(AgentConfig(model="gpt-test"))
        request = ModelRequest(
            provider="openai",
            model="gpt-test",
            messages=[ModelMessage(role="user", content="json")],
            response_schema=StructuredOutputConfig(
                name="answer",
                schema={"type": "object", "properties": {"answer": {"type": "string"}}},
            ),
        )

        response = provider.invoke(request)

        assert response.content == '{"answer":"ok"}'
        assert response.usage is not None
        assert response.usage.total_tokens == 7
        response_format = mock_client.chat.completions.create.call_args.kwargs[
            "response_format"
        ]
        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["name"] == "answer"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_adapter_defers_chat_tool_execution_to_runtime(
        self, mock_openai_class
    ):
        mock_client = Mock()
        tool_call = Mock()
        tool_call.type = "function"
        tool_call.id = "call-runtime"
        tool_call.function.name = "add"
        tool_call.function.arguments = '{"x": 2, "y": 3}'
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message.content = ""
        response.choices[0].message.tool_calls = [tool_call]
        response.choices[0].finish_reason = "tool_calls"
        response.usage = None
        mock_client.chat.completions.create.return_value = response
        mock_openai_class.return_value = mock_client
        calls = []

        def add(x: int, y: int) -> int:
            calls.append((x, y))
            return x + y

        provider = OpenAIProvider(AgentConfig(model="gpt-test"))
        result = provider.invoke(
            ModelRequest(
                provider="openai",
                model="gpt-test",
                messages=[ModelMessage(role="user", content="2+3?")],
            ),
            tools=[{"function": add, "description": "Add"}],
        )

        assert result.content == ""
        assert result.tool_calls[0].name == "add"
        assert calls == []

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_runtime_executes_chat_tool_and_submits_result(
        self, mock_openai_class
    ):
        mock_client = Mock()
        tool_call = Mock()
        tool_call.type = "function"
        tool_call.id = "call-runtime"
        tool_call.function.name = "add"
        tool_call.function.arguments = '{"x": 2, "y": 3}'
        initial = Mock()
        initial.choices = [Mock()]
        initial.choices[0].message.content = ""
        initial.choices[0].message.tool_calls = [tool_call]
        initial.choices[0].finish_reason = "tool_calls"
        initial.usage = None
        final = Mock()
        final.choices = [Mock()]
        final.choices[0].message.content = "5"
        final.choices[0].message.tool_calls = None
        final.choices[0].finish_reason = "stop"
        final.usage = None
        mock_client.chat.completions.create.side_effect = [initial, final]
        mock_openai_class.return_value = mock_client

        def add(x: int, y: int) -> int:
            return x + y

        config = AgentConfig(provider="openai", model="gpt-test")
        runtime = ModelRuntime(
            provider=OpenAIProvider(config),
            provider_name="openai",
            config=config,
        )
        result = runtime.invoke(
            messages=[{"role": "user", "content": "2+3?"}],
            tools=[{"function": add, "description": "Add"}],
        )

        assert result.content == "5"
        assert result.metadata["tool_results"][0]["content"] == "5"
        followup = mock_client.chat.completions.create.call_args_list[1].kwargs
        assert followup["messages"][-1] == {
            "role": "tool",
            "tool_call_id": "call-runtime",
            "content": "5",
        }

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_runtime_executes_responses_tool_and_submits_output(
        self, mock_openai_class
    ):
        mock_client = Mock()
        initial = Mock()
        initial.id = "resp-initial"
        initial.output_text = ""
        initial.output = [
            {
                "type": "function_call",
                "call_id": "call-responses",
                "name": "add",
                "arguments": '{"x": 2, "y": 3}',
            }
        ]
        initial.usage = None
        final = Mock()
        final.id = "resp-final"
        final.output_text = "5"
        final.output = []
        final.usage = None
        mock_client.responses.create.side_effect = [initial, final]
        mock_openai_class.return_value = mock_client

        def add(x: int, y: int) -> int:
            return x + y

        config = AgentConfig(provider="openai", model="gpt-test")
        runtime = ModelRuntime(
            provider=OpenAIProvider(config),
            provider_name="openai",
            config=config,
        )
        result = runtime.invoke(
            messages=[{"role": "user", "content": "2+3?"}],
            tools=[{"function": add, "description": "Add"}],
            provider_options={"endpoint": "responses"},
        )

        assert result.content == "5"
        assert result.tool_calls[0].id == "call-responses"
        followup = mock_client.responses.create.call_args_list[1].kwargs
        assert followup["previous_response_id"] == "resp-initial"
        assert followup["input"] == [
            {
                "type": "function_call_output",
                "call_id": "call-responses",
                "output": "5",
            }
        ]

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_invoke_gpt5_retries_empty_text(self, mock_openai_class):
        """Test runtime Chat Completions retry preserves final metadata."""
        mock_client = Mock()
        empty_choice = Mock()
        empty_choice.finish_reason = "length"
        empty_choice.message.content = None
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

        provider = OpenAIProvider(
            AgentConfig(model="gpt-5-mini", temperature=0.8, max_tokens=500)
        )
        request = ModelRequest(
            provider="openai",
            model="gpt-5-mini",
            messages=[ModelMessage(role="user", content="Hello")],
            temperature=0.8,
            max_output_tokens=500,
        )

        response = provider.invoke(request)

        assert response.content == "runtime retry response"
        assert response.finish_reason == "stop"
        assert response.usage is not None
        assert response.usage.output_tokens == 12
        assert mock_client.chat.completions.create.call_count == 2
        retry_kwargs = mock_client.chat.completions.create.call_args_list[1].kwargs
        assert retry_kwargs["max_completion_tokens"] >= 4096
        assert "temperature" not in retry_kwargs


class TestOpenAIToolFormatting:
    """Test OpenAI tool formatting methods."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_format_tools_basic(self, mock_openai_class):
        """Test basic tool formatting for OpenAI."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        def my_tool():
            pass

        tools = [{"function": my_tool, "description": "A test tool"}]
        formatted = provider._format_tools_for_openai(tools)

        assert len(formatted) == 1
        assert formatted[0]["type"] == "function"
        assert formatted[0]["function"]["name"] == "my_tool"
        assert formatted[0]["function"]["description"] == "A test tool"
        assert formatted[0]["function"]["parameters"]["type"] == "object"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_format_tools_with_parameters(self, mock_openai_class):
        """Test tool formatting with parameters."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        def calculator(x, y):
            return x + y

        tools = [
            {
                "function": calculator,
                "description": "Add two numbers",
                "parameters": {
                    "x": {"type": "int", "required": True},
                    "y": {"type": "int", "required": True},
                },
            }
        ]
        formatted = provider._format_tools_for_openai(tools)

        assert len(formatted) == 1
        params = formatted[0]["function"]["parameters"]
        assert "x" in params["properties"]
        assert params["properties"]["x"]["type"] == "integer"
        assert "y" in params["properties"]
        assert params["properties"]["y"]["type"] == "integer"
        assert "x" in params["required"]
        assert "y" in params["required"]

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_format_tools_with_optional_parameters(self, mock_openai_class):
        """Test tool formatting with optional parameters."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        def search(query, limit):
            pass

        tools = [
            {
                "function": search,
                "description": "Search for items",
                "parameters": {
                    "query": {"type": "str", "required": True},
                    "limit": {"type": "int", "required": False},
                },
            }
        ]
        formatted = provider._format_tools_for_openai(tools)

        params = formatted[0]["function"]["parameters"]
        assert "query" in params["required"]
        assert "limit" not in params["required"]

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_format_tools_skips_invalid_tools(self, mock_openai_class):
        """Test that tools without function or description are skipped."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        def valid_tool():
            pass

        tools = [
            {"function": valid_tool, "description": "Valid"},  # Valid
            {"function": valid_tool},  # Missing description
            {"description": "Missing function"},  # Missing function
            {},  # Empty
        ]
        formatted = provider._format_tools_for_openai(tools)

        assert len(formatted) == 1
        assert formatted[0]["function"]["name"] == "valid_tool"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_format_tools_empty_list(self, mock_openai_class):
        """Test formatting empty tool list."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        formatted = provider._format_tools_for_openai([])
        assert formatted == []


class TestOpenAITypeConversion:
    """Test Python type to JSON schema conversion."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_python_type_to_json_schema_str(self, mock_openai_class):
        """Test string type conversion."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        assert provider._python_type_to_json_schema("str") == "string"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_python_type_to_json_schema_int(self, mock_openai_class):
        """Test integer type conversion."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        assert provider._python_type_to_json_schema("int") == "integer"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_python_type_to_json_schema_float(self, mock_openai_class):
        """Test float type conversion."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        assert provider._python_type_to_json_schema("float") == "number"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_python_type_to_json_schema_bool(self, mock_openai_class):
        """Test boolean type conversion."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        assert provider._python_type_to_json_schema("bool") == "boolean"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_python_type_to_json_schema_list(self, mock_openai_class):
        """Test list type conversion."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        assert provider._python_type_to_json_schema("list") == "array"
        assert provider._python_type_to_json_schema("List") == "array"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_python_type_to_json_schema_dict(self, mock_openai_class):
        """Test dict type conversion."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        assert provider._python_type_to_json_schema("dict") == "object"
        assert provider._python_type_to_json_schema("Dict") == "object"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_python_type_to_json_schema_unknown(self, mock_openai_class):
        """Test unknown type defaults to string."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        assert provider._python_type_to_json_schema("UnknownType") == "string"
        assert provider._python_type_to_json_schema("CustomClass") == "string"


class TestOpenAIToolCallHandling:
    """Test OpenAI tool call handling."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_handle_tool_calls_executes_function(self, mock_openai_class):
        """Test that tool calls execute the correct function."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock the follow-up response
        mock_followup_response = Mock()
        mock_followup_response.choices = [Mock()]
        mock_followup_response.choices[0].message.content = "The result is 7."
        mock_client.chat.completions.create.return_value = mock_followup_response

        config = AgentConfig()
        provider = OpenAIProvider(config)

        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.type = "function"
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "add_numbers"
        mock_tool_call.function.arguments = '{"x": 3, "y": 4}'

        def add_numbers(x, y):
            return x + y

        tools = [{"function": add_numbers, "description": "Add two numbers"}]
        messages = [{"role": "user", "content": "Add 3 and 4"}]

        result = provider._handle_tool_calls([mock_tool_call], tools, messages)

        assert result == "The result is 7."
        # Verify the API was called with the tool results
        mock_client.chat.completions.create.assert_called()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_handle_tool_calls_unknown_function(self, mock_openai_class):
        """Test handling of unknown function in tool calls."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock the follow-up response
        mock_followup_response = Mock()
        mock_followup_response.choices = [Mock()]
        mock_followup_response.choices[0].message.content = (
            "I couldn't find that function."
        )
        mock_client.chat.completions.create.return_value = mock_followup_response

        config = AgentConfig()
        provider = OpenAIProvider(config)

        # Create mock tool call for unknown function
        mock_tool_call = Mock()
        mock_tool_call.type = "function"
        mock_tool_call.id = "call_456"
        mock_tool_call.function.name = "unknown_function"
        mock_tool_call.function.arguments = "{}"

        def known_function():
            return "known"

        tools = [{"function": known_function, "description": "A known function"}]
        messages = [{"role": "user", "content": "Do something"}]

        _ = provider._handle_tool_calls([mock_tool_call], tools, messages)

        # Should have called the API with unknown function error message
        mock_client.chat.completions.create.assert_called()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_handle_tool_calls_function_execution_error(self, mock_openai_class):
        """Test handling of function execution errors in tool calls."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock the follow-up response
        mock_followup_response = Mock()
        mock_followup_response.choices = [Mock()]
        mock_followup_response.choices[0].message.content = "There was an error."
        mock_client.chat.completions.create.return_value = mock_followup_response

        config = AgentConfig()
        provider = OpenAIProvider(config)

        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.type = "function"
        mock_tool_call.id = "call_789"
        mock_tool_call.function.name = "failing_function"
        mock_tool_call.function.arguments = "{}"

        def failing_function():
            raise ValueError("Function failed!")

        tools = [{"function": failing_function, "description": "A failing function"}]
        messages = [{"role": "user", "content": "Run the function"}]

        _ = provider._handle_tool_calls([mock_tool_call], tools, messages)

        # Should handle the error gracefully
        mock_client.chat.completions.create.assert_called()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_handle_tool_calls_follow_up_error_fallback(self, mock_openai_class):
        """Test fallback when follow-up API call fails."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock the follow-up to fail
        mock_client.chat.completions.create.side_effect = Exception("API error")

        config = AgentConfig()
        provider = OpenAIProvider(config)

        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.type = "function"
        mock_tool_call.id = "call_abc"
        mock_tool_call.function.name = "simple_function"
        mock_tool_call.function.arguments = "{}"

        def simple_function():
            return "result_value"

        tools = [{"function": simple_function, "description": "A simple function"}]
        messages = [{"role": "user", "content": "Run it"}]

        result = provider._handle_tool_calls([mock_tool_call], tools, messages)

        # Should fallback to returning tool results
        assert "result_value" in result

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_handle_tool_calls_multiple_calls(self, mock_openai_class):
        """Test handling of multiple tool calls."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock the follow-up response
        mock_followup_response = Mock()
        mock_followup_response.choices = [Mock()]
        mock_followup_response.choices[0].message.content = "Both functions executed."
        mock_client.chat.completions.create.return_value = mock_followup_response

        config = AgentConfig()
        provider = OpenAIProvider(config)

        # Create mock tool calls
        mock_tool_call1 = Mock()
        mock_tool_call1.type = "function"
        mock_tool_call1.id = "call_1"
        mock_tool_call1.function.name = "func_a"
        mock_tool_call1.function.arguments = "{}"

        mock_tool_call2 = Mock()
        mock_tool_call2.type = "function"
        mock_tool_call2.id = "call_2"
        mock_tool_call2.function.name = "func_b"
        mock_tool_call2.function.arguments = "{}"

        def func_a():
            return "A"

        def func_b():
            return "B"

        tools = [
            {"function": func_a, "description": "Function A"},
            {"function": func_b, "description": "Function B"},
        ]
        messages = [{"role": "user", "content": "Run both"}]

        result = provider._handle_tool_calls(
            [mock_tool_call1, mock_tool_call2], tools, messages
        )

        assert result == "Both functions executed."

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_handle_tool_calls_empty_follow_up_response(self, mock_openai_class):
        """Test handling of empty follow-up response."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock empty follow-up response
        mock_followup_response = Mock()
        mock_followup_response.choices = []
        mock_client.chat.completions.create.return_value = mock_followup_response

        config = AgentConfig()
        provider = OpenAIProvider(config)

        mock_tool_call = Mock()
        mock_tool_call.type = "function"
        mock_tool_call.id = "call_empty"
        mock_tool_call.function.name = "test_func"
        mock_tool_call.function.arguments = "{}"

        def test_func():
            return "test"

        tools = [{"function": test_func, "description": "Test function"}]
        messages = [{"role": "user", "content": "Test"}]

        result = provider._handle_tool_calls([mock_tool_call], tools, messages)

        assert result == "No response generated after tool execution"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_generate_with_actual_tool_calls(self, mock_openai_class):
        """Test generate method when API returns tool calls."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Create mock tool call object
        mock_tool_call = Mock()
        mock_tool_call.type = "function"
        mock_tool_call.id = "call_gen"
        mock_tool_call.function.name = "get_weather"
        mock_tool_call.function.arguments = '{"location": "Paris"}'

        # First response with tool calls
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [mock_tool_call]

        # Follow-up response
        mock_followup = Mock()
        mock_followup.choices = [Mock()]
        mock_followup.choices[0].message.content = "The weather in Paris is sunny."

        mock_client.chat.completions.create.side_effect = [mock_response, mock_followup]

        config = AgentConfig()
        provider = OpenAIProvider(config)

        def get_weather(location):
            return f"Sunny in {location}"

        messages = [{"role": "user", "content": "What's the weather in Paris?"}]
        tools = [{"function": get_weather, "description": "Get weather for a location"}]

        result = provider.generate(messages, tools)

        assert result == "The weather in Paris is sunny."
        assert mock_client.chat.completions.create.call_count == 2

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_gpt5_tool_follow_up_uses_supported_chat_params(self, mock_openai_class):
        """Test GPT-5 tool follow-up requests use supported Chat params."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_tool_call = Mock()
        mock_tool_call.type = "function"
        mock_tool_call.id = "call_gpt5_tool"
        mock_tool_call.function.name = "get_weather"
        mock_tool_call.function.arguments = '{"location": "Paris"}'

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [mock_tool_call]

        mock_followup = Mock()
        mock_followup.choices = [Mock()]
        mock_followup.choices[0].message.content = "The weather in Paris is sunny."

        mock_client.chat.completions.create.side_effect = [mock_response, mock_followup]

        provider = OpenAIProvider(
            AgentConfig(model="gpt-5-mini", temperature=0.8, max_tokens=500)
        )

        def get_weather(location):
            return f"Sunny in {location}"

        result = provider.generate(
            [{"role": "user", "content": "What's the weather in Paris?"}],
            [{"function": get_weather, "description": "Get weather for a location"}],
        )

        assert result == "The weather in Paris is sunny."
        initial_kwargs = mock_client.chat.completions.create.call_args_list[0].kwargs
        followup_kwargs = mock_client.chat.completions.create.call_args_list[1].kwargs
        for call_kwargs in (initial_kwargs, followup_kwargs):
            assert call_kwargs["model"] == "gpt-5-mini"
            assert call_kwargs["max_completion_tokens"] == 500
            assert "max_tokens" not in call_kwargs
            assert "temperature" not in call_kwargs

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_gpt5_tool_follow_up_retries_empty_text(self, mock_openai_class):
        """Test GPT-5 tool follow-up calls retry blank visible output."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_tool_call = Mock()
        mock_tool_call.type = "function"
        mock_tool_call.id = "call_gpt5_tool"
        mock_tool_call.function.name = "get_weather"
        mock_tool_call.function.arguments = '{"location": "Paris"}'

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [mock_tool_call]

        mock_empty_followup = Mock()
        mock_empty_followup.choices = [Mock()]
        mock_empty_followup.choices[0].finish_reason = "length"
        mock_empty_followup.choices[0].message.content = ""
        mock_empty_followup.choices[0].message.tool_calls = None

        mock_final_followup = Mock()
        mock_final_followup.choices = [Mock()]
        mock_final_followup.choices[0].finish_reason = "stop"
        mock_final_followup.choices[0].message.content = (
            "The weather in Paris is sunny."
        )
        mock_final_followup.choices[0].message.tool_calls = None

        mock_client.chat.completions.create.side_effect = [
            mock_response,
            mock_empty_followup,
            mock_final_followup,
        ]

        provider = OpenAIProvider(
            AgentConfig(model="gpt-5-mini", temperature=0.8, max_tokens=500)
        )

        def get_weather(location):
            return f"Sunny in {location}"

        result = provider.generate(
            [{"role": "user", "content": "What's the weather in Paris?"}],
            [{"function": get_weather, "description": "Get weather for a location"}],
        )

        assert result == "The weather in Paris is sunny."
        assert mock_client.chat.completions.create.call_count == 3
        retry_kwargs = mock_client.chat.completions.create.call_args_list[2].kwargs
        assert retry_kwargs["model"] == "gpt-5-mini"
        assert retry_kwargs["max_completion_tokens"] >= 4096
        assert "max_tokens" not in retry_kwargs
        assert "temperature" not in retry_kwargs


class TestAnthropicProvider:
    """Test Anthropic provider implementation."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    @patch("anthropic.Anthropic")
    def test_anthropic_provider_initialization(self, mock_anthropic_class):
        """Test Anthropic provider initializes correctly."""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        config = AgentConfig(temperature=0.8, max_tokens=500)
        provider = AnthropicProvider(config)

        assert provider.config == config
        assert provider.client == mock_client

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    @patch("anthropic.Anthropic")
    def test_anthropic_generate_simple_message(self, mock_anthropic_class):
        """Test Anthropic provider generates response for simple message."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "Hello! How can I assist you today?"
        mock_response.content[0].type = "text"  # Anthropic checks content type
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        config = AgentConfig()
        provider = AnthropicProvider(config)

        messages = [{"role": "user", "content": "Hello"}]
        response = provider.generate(messages)

        assert response == "Hello! How can I assist you today?"
        mock_client.messages.create.assert_called_once()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    @patch("anthropic.Anthropic")
    def test_anthropic_passes_explicit_experimental_tools(self, mock_anthropic_class):
        mock_client = Mock()
        block = Mock()
        block.type = "text"
        block.text = "searched"
        mock_response = Mock()
        mock_response.content = [block]
        mock_response.usage = None
        mock_response.stop_reason = "end_turn"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider(AgentConfig(model="claude-test"))
        request = ModelRequest(
            provider="anthropic",
            model="claude-test",
            messages=[ModelMessage(role="user", content="search")],
            provider_options={
                "allow_experimental_tools": True,
                "experimental_tools": [
                    {"type": "web_search_20250305", "name": "web_search"}
                ],
            },
        )

        response = provider.invoke(request)

        assert response.content == "searched"
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["tools"] == [
            {"type": "web_search_20250305", "name": "web_search"}
        ]
        assert "experimental_tools" not in call_kwargs
        assert "allow_experimental_tools" not in call_kwargs

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    @patch("anthropic.Anthropic")
    def test_anthropic_handles_system_messages(self, mock_anthropic_class):
        """Test Anthropic provider handles system messages correctly."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "I am a helpful assistant."
        mock_response.content[0].type = "text"  # Anthropic checks content type
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        config = AgentConfig()
        provider = AnthropicProvider(config)

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What are you?"},
        ]
        response = provider.generate(messages)

        assert response == "I am a helpful assistant."

        # Verify system message was passed correctly
        call_args = mock_client.messages.create.call_args
        assert "system" in call_args.kwargs

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    @patch("anthropic.Anthropic")
    def test_anthropic_handles_api_errors(self, mock_anthropic_class):
        """Test Anthropic provider handles API errors gracefully."""
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("API Error")
        mock_anthropic_class.return_value = mock_client

        config = AgentConfig()
        provider = AnthropicProvider(config)

        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(ProviderError, match="Anthropic API error"):
            provider.generate(messages)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    @patch("anthropic.Anthropic")
    def test_anthropic_generate_with_tools(self, mock_anthropic_class):
        """Test Anthropic provider passes tools to the API."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "Done"
        mock_response.content[0].type = "text"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        config = AgentConfig()
        provider = AnthropicProvider(config)

        def add(x: int, y: int) -> int:
            return x + y

        messages = [{"role": "user", "content": "Add 1 and 2"}]
        tools = [
            {
                "function": add,
                "description": "Add numbers",
                "parameters": {
                    "x": {"type": "int", "required": True},
                    "y": {"type": "int", "required": True},
                },
            }
        ]

        result = provider.generate(messages, tools)
        assert result == "Done"

        call_args = mock_client.messages.create.call_args
        assert "tools" in call_args.kwargs

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    @patch("anthropic.Anthropic")
    def test_anthropic_handles_tool_calls(self, mock_anthropic_class):
        """
        Test Anthropic provider executes tool calls and returns a follow-up response.
        """
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # First response includes a tool_use block
        tool_use = Mock()
        tool_use.type = "tool_use"
        tool_use.id = "tool_1"
        tool_use.name = "add"
        tool_use.input = {"x": 2, "y": 5}

        first_response = Mock()
        first_response.content = [tool_use]

        # Follow-up response returns text
        followup_response = Mock()
        followup_block = Mock()
        followup_block.type = "text"
        followup_block.text = "Result is 7"
        followup_response.content = [followup_block]

        mock_client.messages.create.side_effect = [first_response, followup_response]

        config = AgentConfig()
        provider = AnthropicProvider(config)

        def add(x: int, y: int) -> int:
            return x + y

        messages = [{"role": "user", "content": "Add"}]
        tools = [
            {
                "function": add,
                "description": "Add numbers",
                "parameters": {
                    "x": {"type": "int", "required": True},
                    "y": {"type": "int", "required": True},
                },
            }
        ]

        result = provider.generate(messages, tools)
        assert result == "Result is 7"
        assert mock_client.messages.create.call_count == 2

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    @patch("anthropic.Anthropic")
    def test_anthropic_adapter_defers_tool_execution_to_runtime(
        self, mock_anthropic_class
    ):
        mock_client = Mock()
        tool_use = Mock()
        tool_use.type = "tool_use"
        tool_use.id = "tool-runtime"
        tool_use.name = "add"
        tool_use.input = {"x": 2, "y": 5}
        response = Mock()
        response.content = [tool_use]
        response.usage = None
        response.stop_reason = "tool_use"
        mock_client.messages.create.return_value = response
        mock_anthropic_class.return_value = mock_client
        calls = []

        def add(x: int, y: int) -> int:
            calls.append((x, y))
            return x + y

        provider = AnthropicProvider(AgentConfig(model="claude-test"))
        result = provider.invoke(
            ModelRequest(
                provider="anthropic",
                model="claude-test",
                messages=[ModelMessage(role="user", content="Add")],
            ),
            tools=[{"function": add, "description": "Add"}],
        )

        assert result.content == ""
        assert result.tool_calls[0].name == "add"
        assert calls == []
        mock_client.messages.create.assert_called_once()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    @patch("anthropic.Anthropic")
    def test_anthropic_runtime_executes_tool_and_submits_tool_result(
        self, mock_anthropic_class
    ):
        mock_client = Mock()
        tool_use = Mock()
        tool_use.type = "tool_use"
        tool_use.id = "tool-runtime"
        tool_use.name = "add"
        tool_use.input = {"x": 2, "y": 5}
        initial = Mock()
        initial.content = [tool_use]
        initial.usage = None
        initial.stop_reason = "tool_use"
        text_block = Mock()
        text_block.type = "text"
        text_block.text = "Result is 7"
        final = Mock()
        final.content = [text_block]
        final.usage = None
        final.stop_reason = "end_turn"
        mock_client.messages.create.side_effect = [initial, final]
        mock_anthropic_class.return_value = mock_client

        def add(x: int, y: int) -> int:
            return x + y

        config = AgentConfig(provider="anthropic", model="claude-test")
        runtime = ModelRuntime(
            provider=AnthropicProvider(config),
            provider_name="anthropic",
            config=config,
        )
        result = runtime.invoke(
            messages=[{"role": "user", "content": "Add"}],
            tools=[{"function": add, "description": "Add"}],
        )

        assert result.content == "Result is 7"
        assert result.metadata["tool_results"][0]["content"] == "7"
        followup = mock_client.messages.create.call_args_list[1].kwargs
        assert followup["messages"][-1] == {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool-runtime",
                    "content": "7",
                }
            ],
        }

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    @patch("anthropic.Anthropic")
    def test_anthropic_invoke_with_thinking_and_structured_output(
        self, mock_anthropic_class
    ):
        """Test Anthropic adapter maps thinking and structured outputs."""
        mock_client = Mock()
        block = Mock()
        block.type = "text"
        block.text = '{"answer":"ok"}'
        mock_response = Mock()
        mock_response.content = [block]
        mock_response.usage = {"input_tokens": 6, "output_tokens": 7}
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider(AgentConfig(model="claude-test"))
        schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
        request = ModelRequest(
            provider="anthropic",
            model="claude-test",
            messages=[ModelMessage(role="user", content="json")],
            reasoning=ReasoningConfig(
                effort="medium",
                budget_tokens=1024,
                mode="enabled",
            ),
            response_schema=StructuredOutputConfig(name="answer", schema=schema),
        )

        response = provider.invoke(request)

        assert response.content == '{"answer":"ok"}'
        assert response.usage is not None
        assert response.usage.total_tokens == 13
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["thinking"] == {
            "type": "enabled",
            "budget_tokens": 1024,
        }
        assert call_kwargs["output_config"] == {
            "format": {"type": "json_schema", "schema": schema},
            "effort": "medium",
        }


class TestCohereProvider:
    """Test Cohere provider implementation."""

    @patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
    @patch("cohere.Client")
    def test_cohere_provider_initialization(self, mock_cohere_class):
        """Test Cohere provider initializes correctly."""
        mock_client = Mock()
        mock_cohere_class.return_value = mock_client

        config = AgentConfig(temperature=0.8, max_tokens=500)
        provider = CohereProvider(config)

        assert provider.config == config
        assert provider.client == mock_client

    @patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
    @patch("cohere.Client")
    def test_cohere_generate_with_tools(self, mock_cohere_class):
        """Test Cohere provider passes tools to the API."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "OK"
        mock_client.chat.return_value = mock_response
        mock_cohere_class.return_value = mock_client

        config = AgentConfig()
        provider = CohereProvider(config)

        def echo(text: str) -> str:
            return text

        messages = [{"role": "user", "content": "Hi"}]
        tools = [
            {
                "function": echo,
                "description": "Echo text",
                "parameters": {"text": {"type": "str", "required": True}},
            }
        ]

        result = provider.generate(messages, tools)
        assert result == "OK"

        call_args = mock_client.chat.call_args
        assert "tools" in call_args.kwargs

    @patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
    @patch("cohere.Client")
    def test_cohere_handles_tool_calls(self, mock_cohere_class):
        """Test Cohere provider executes tool calls and returns follow-up response."""
        mock_client = Mock()
        mock_cohere_class.return_value = mock_client

        # First response includes tool calls
        tool_call = {"name": "echo", "args": {"text": "hello"}}
        first_response = Mock()
        first_response.tool_calls = [tool_call]

        followup_response = Mock()
        followup_response.text = "hello"

        mock_client.chat.side_effect = [first_response, followup_response]

        config = AgentConfig()
        provider = CohereProvider(config)

        def echo(text: str) -> str:
            return text

        messages = [{"role": "user", "content": "Echo"}]
        tools = [
            {
                "function": echo,
                "description": "Echo text",
                "parameters": {"text": {"type": "str", "required": True}},
            }
        ]

        result = provider.generate(messages, tools)
        assert result == "hello"
        assert mock_client.chat.call_count == 2

    @patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
    @patch("cohere.Client")
    def test_cohere_adapter_defers_tool_execution_to_runtime(self, mock_cohere_class):
        mock_client = Mock()
        response = Mock()
        response.text = ""
        response.tool_calls = [{"name": "echo", "args": {"text": "hello"}}]
        mock_client.chat.return_value = response
        mock_cohere_class.return_value = mock_client
        calls = []

        def echo(text: str) -> str:
            calls.append(text)
            return text

        provider = CohereProvider(AgentConfig(model="command-test"))
        result = provider.invoke(
            ModelRequest(
                provider="cohere",
                model="command-test",
                messages=[ModelMessage(role="user", content="Echo")],
            ),
            tools=[{"function": echo, "description": "Echo"}],
        )

        assert result.content == ""
        assert result.tool_calls[0].name == "echo"
        assert calls == []
        mock_client.chat.assert_called_once()

    @patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
    @patch("cohere.Client")
    def test_cohere_runtime_executes_tool_and_submits_result(self, mock_cohere_class):
        mock_client = Mock()
        initial = Mock()
        initial.text = ""
        initial.tool_calls = [{"name": "echo", "args": {"text": "hello"}}]
        final = Mock()
        final.text = "hello"
        final.tool_calls = []
        mock_client.chat.side_effect = [initial, final]
        mock_cohere_class.return_value = mock_client

        def echo(text: str) -> str:
            return text

        config = AgentConfig(provider="cohere", model="command-test")
        runtime = ModelRuntime(
            provider=CohereProvider(config),
            provider_name="cohere",
            config=config,
        )
        result = runtime.invoke(
            messages=[{"role": "user", "content": "Echo"}],
            tools=[{"function": echo, "description": "Echo"}],
        )

        assert result.content == "hello"
        assert result.metadata["tool_results"][0]["content"] == "hello"
        followup = mock_client.chat.call_args_list[1].kwargs
        assert followup["tool_results"] == [{"name": "echo", "result": "hello"}]

    @patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
    @patch("cohere.Client")
    def test_cohere_generate_simple_message(self, mock_cohere_class):
        """Test Cohere provider generates response for simple message."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Hello! I'm here to help you with anything you need."
        mock_client.chat.return_value = mock_response
        mock_cohere_class.return_value = mock_client

        config = AgentConfig()
        provider = CohereProvider(config)

        messages = [{"role": "user", "content": "Hello"}]
        response = provider.generate(messages)

        assert response == "Hello! I'm here to help you with anything you need."
        mock_client.chat.assert_called_once()

    @patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
    @patch("cohere.Client")
    def test_cohere_handles_conversation_history(self, mock_cohere_class):
        """Test Cohere provider handles conversation history correctly."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "I remember our previous conversation."
        mock_client.chat.return_value = mock_response
        mock_cohere_class.return_value = mock_client

        config = AgentConfig()
        provider = CohereProvider(config)

        messages = [
            {"role": "user", "content": "My name is Alice"},
            {"role": "assistant", "content": "Nice to meet you, Alice!"},
            {"role": "user", "content": "What's my name?"},
        ]
        response = provider.generate(messages)

        assert response == "I remember our previous conversation."

        # Verify conversation history was passed correctly
        call_args = mock_client.chat.call_args
        assert "chat_history" in call_args.kwargs

    @patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
    @patch("cohere.Client")
    def test_cohere_handles_api_errors(self, mock_cohere_class):
        """Test Cohere provider handles API errors gracefully."""
        mock_client = Mock()
        mock_client.chat.side_effect = Exception("API Error")
        mock_cohere_class.return_value = mock_client

        config = AgentConfig()
        provider = CohereProvider(config)

        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(ProviderError, match="Cohere API error"):
            provider.generate(messages)


class TestProviderConfiguration:
    """Test provider configuration handling."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    def test_temperature_configuration_applied(self):
        """Test that temperature configuration is applied to providers."""
        config = AgentConfig(temperature=0.9)

        with patch("openai.OpenAI"):
            provider = OpenAIProvider(config)
            assert provider.config.temperature == 0.9

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    def test_max_tokens_configuration_applied(self):
        """Test that max_tokens configuration is applied to providers."""
        config = AgentConfig(max_tokens=2000)

        with patch("anthropic.Anthropic"):
            provider = AnthropicProvider(config)
            assert provider.config.max_tokens == 2000

    @patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
    def test_system_message_configuration_applied(self):
        """Test that system message configuration is handled correctly."""
        config = AgentConfig(system_message="You are a coding assistant.")

        with patch("cohere.Client"):
            provider = CohereProvider(config)
            assert provider.config.system_message == "You are a coding assistant."
