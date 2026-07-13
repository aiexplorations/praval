"""Edge-case contracts for the OpenAI 0.8 provider adapter."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from praval.core.agent import AgentConfig
from praval.core.exceptions import ProviderError
from praval.models import (
    ContentPart,
    ModelMessage,
    ModelRequest,
    SpeechRequest,
    TranscriptionRequest,
)
from praval.providers.openai import OpenAIProvider, _redact_secrets


@pytest.fixture
def openai_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    client = Mock()
    with patch("praval.providers.openai.openai.OpenAI", return_value=client):
        provider = OpenAIProvider(
            AgentConfig(provider="openai", model="gpt-test", max_tokens=100)
        )
    return provider, client


def test_openai_initialization_options_close_and_secret_redaction(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-key")
    client = Mock()
    with patch(
        "praval.providers.openai.openai.OpenAI", return_value=client
    ) as constructor:
        provider = OpenAIProvider(
            AgentConfig(
                provider="openai",
                model="gpt-test",
                base_url="https://openai.test/v1",
                timeout=12,
            )
        )

    constructor.assert_called_once_with(
        api_key="secret-key", base_url="https://openai.test/v1", timeout=12
    )
    assert _redact_secrets("") == ""
    assert _redact_secrets("token=secret-key") == "token=***"
    provider.close()
    client.close.assert_called_once()


def test_openai_transcription_accepts_mapping_and_optional_fields(openai_provider):
    provider, client = openai_provider
    client.audio.transcriptions.create.return_value = "transcribed"

    response = provider.transcribe(
        {
            "audio": b"audio",
            "filename": "voice.ogg",
            "mime_type": "audio/ogg",
            "language": "en",
            "prompt": "Names: Praval",
            "temperature": 0.1,
            "timeout": 4,
            "provider_options": {"timestamp_granularities": ["word"]},
        }
    )

    assert response.text == "transcribed"
    kwargs = client.audio.transcriptions.create.call_args.kwargs
    assert kwargs["language"] == "en"
    assert kwargs["prompt"] == "Names: Praval"
    assert kwargs["temperature"] == 0.1
    assert kwargs["timeout"] == 4
    assert kwargs["timestamp_granularities"] == ["word"]


@pytest.mark.parametrize(
    "audio",
    [b"", None, Path("/definitely/missing/audio.wav"), object()],
)
def test_openai_transcription_rejects_invalid_audio(openai_provider, audio):
    provider, _ = openai_provider
    with pytest.raises(ProviderError):
        provider.transcribe(TranscriptionRequest(audio=audio))


def test_openai_transcription_accepts_file_object_and_sdk_tuple(openai_provider):
    provider, _ = openai_provider
    file_object = Mock()
    file_object.read = Mock(return_value=b"audio")
    assert provider._audio_file_value(TranscriptionRequest(audio=file_object)) == (
        file_object,
        False,
    )
    sdk_tuple = ("voice.wav", b"audio", "audio/wav")
    assert provider._audio_file_value(TranscriptionRequest(audio=sdk_tuple)) == (
        sdk_tuple,
        False,
    )


def test_openai_transcription_normalizes_response_shapes_and_errors(openai_provider):
    provider, client = openai_provider
    assert provider._transcription_text({"text": "dict"}) == "dict"
    assert provider._transcription_text(SimpleNamespace(text="object")) == "object"
    assert provider._transcription_text(SimpleNamespace(text=1)) == ""

    client.audio.transcriptions.create.return_value = {}
    with pytest.raises(ProviderError, match="returned no text"):
        provider.transcribe(TranscriptionRequest(audio=b"audio"))

    client.audio.transcriptions.create.side_effect = RuntimeError("transcribe failed")
    with pytest.raises(ProviderError, match="transcription error"):
        provider.transcribe(TranscriptionRequest(audio=b"audio"))


def test_openai_speech_accepts_mapping_instructions_and_read_response(openai_provider):
    provider, client = openai_provider
    speech_response = Mock()
    speech_response.content = None
    speech_response.read.return_value = bytearray(b"voice")
    client.audio.speech.create.return_value = speech_response

    response = provider.speak(
        {
            "input": "Hello",
            "model": "gpt-4o-mini-tts",
            "voice": "coral",
            "response_format": "opus",
            "speed": 1.25,
            "instructions": "Speak warmly",
            "timeout": 3,
            "provider_options": {"user": "test-user"},
        }
    )

    assert response.data == b"voice"
    assert response.mime_type == "audio/opus"
    kwargs = client.audio.speech.create.call_args.kwargs
    assert kwargs["instructions"] == "Speak warmly"
    assert kwargs["timeout"] == 3
    assert kwargs["user"] == "test-user"


def test_openai_speech_validates_empty_and_missing_audio(openai_provider):
    provider, client = openai_provider
    with pytest.raises(ProviderError, match="cannot be empty"):
        provider.speak(SpeechRequest(input="   "))

    client.audio.speech.create.return_value = Mock(
        content=None, read=Mock(return_value="x")
    )
    with pytest.raises(ProviderError, match="returned no audio"):
        provider.speak(SpeechRequest(input="Hello"))

    client.audio.speech.create.side_effect = RuntimeError("speech failed")
    with pytest.raises(ProviderError, match="speech generation error"):
        provider.speak(SpeechRequest(input="Hello"))


def test_openai_speech_byte_shapes_and_mime_fallback(openai_provider):
    provider, _ = openai_provider
    assert provider._speech_bytes(b"bytes") == b"bytes"
    assert provider._speech_bytes(bytearray(b"array")) == b"array"
    assert provider._speech_bytes(SimpleNamespace(content=bytearray(b"content"))) == (
        b"content"
    )
    assert provider._speech_bytes(SimpleNamespace(read=lambda: b"read")) == b"read"
    assert provider._speech_mime_type("unknown") == "application/octet-stream"


def test_openai_content_formatting_and_response_text_shapes(openai_provider):
    provider, _ = openai_provider
    parts = [
        ContentPart.text_part("describe"),
        ContentPart.image_base64("AAA", "image/jpeg"),
        ContentPart.image_url("https://image.test/a.png"),
    ]
    chat = provider._format_openai_content(parts, responses=False)
    responses = provider._format_openai_content(parts, responses=True)

    assert chat[1]["image_url"]["url"] == "data:image/jpeg;base64,AAA"
    assert responses[0] == {"type": "input_text", "text": "describe"}
    assert responses[2] == {
        "type": "input_image",
        "image_url": "https://image.test/a.png",
    }
    with pytest.raises(ProviderError, match="cannot serialize"):
        provider._format_openai_content(
            [ContentPart.audio_base64("AAA")], responses=True
        )

    nested = {
        "output": [
            {"content": [{"type": "output_text", "text": "one"}]},
            SimpleNamespace(content=[SimpleNamespace(type="text", text="two")]),
        ]
    }
    assert provider._extract_responses_text(nested) == "onetwo"
    assert provider._extract_content_text([{"text": "a"}, {"refusal": "b"}]) == "ab"


def test_openai_usage_and_tool_call_defensive_shapes(openai_provider):
    provider, _ = openai_provider
    usage = SimpleNamespace(
        prompt_tokens=2,
        completion_tokens=3,
        total_tokens=5,
        completion_tokens_details=SimpleNamespace(reasoning_tokens=1),
    )
    parsed = provider._extract_usage(SimpleNamespace(usage=usage))
    assert parsed.total_tokens == 5
    assert parsed.reasoning_tokens == 1
    assert provider._extract_usage({}) is None

    malformed = provider._tool_call(
        {"id": "item", "name": "tool", "arguments": "not-json"}
    )
    assert malformed.arguments == {"raw": "not-json"}
    non_mapping = provider._tool_call(
        {"call_id": "call", "name": "tool", "arguments": [1, 2]}
    )
    assert non_mapping.arguments == {"raw": [1, 2]}


def test_openai_chat_stream_normalizes_content_tool_usage_and_finish(openai_provider):
    provider, client = openai_provider
    chunks = [
        {"choices": []},
        {
            "choices": [
                {
                    "delta": {
                        "content": "hello",
                        "tool_calls": [{"index": 0, "function": {"name": "x"}}],
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    ]
    client.chat.completions.create.return_value = iter(chunks)
    events = list(
        provider.stream(
            ModelRequest(
                provider="openai",
                model="gpt-test",
                messages=[ModelMessage(role="user", content="hello")],
                stream=True,
                stream_options={"include_usage": True},
            )
        )
    )

    assert [event.type for event in events] == [
        "delta",
        "tool_call_delta",
        "usage",
        "final",
    ]
    assert events[-1].response.content == "hello"
    assert events[-1].response.finish_reason == "stop"


def test_openai_responses_stream_normalizes_all_event_types(openai_provider):
    provider, client = openai_provider
    client.responses.create.return_value = iter(
        [
            {"type": "response.output_text.delta", "delta": "hi"},
            {"type": "response.function_call_arguments.delta", "delta": "{}"},
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "function_call",
                    "call_id": "call-1",
                    "name": "lookup",
                    "arguments": "{}",
                },
            },
            {
                "type": "response.completed",
                "response": {
                    "output": [{"content": [{"type": "output_text", "text": "hi"}]}],
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            },
        ]
    )
    events = list(
        provider.stream(
            ModelRequest(
                provider="openai",
                model="gpt-test",
                messages=[ModelMessage(role="user", content="hello")],
                stream=True,
                provider_options={"endpoint": "responses"},
            )
        )
    )

    assert [event.type for event in events] == [
        "delta",
        "tool_call_delta",
        "tool_call",
        "usage",
        "final",
    ]
    assert events[2].tool_call.name == "lookup"


def test_openai_stream_redacts_provider_errors(openai_provider, monkeypatch):
    provider, client = openai_provider
    monkeypatch.setenv("OPENAI_API_KEY", "secret-key")
    client.chat.completions.create.side_effect = RuntimeError("bad secret-key")
    stream = provider.stream(
        ModelRequest(
            provider="openai",
            model="gpt-test",
            messages=[ModelMessage(role="user", content="hello")],
            stream=True,
        )
    )
    error_event = next(stream)
    assert error_event.type == "error"
    assert error_event.metadata["message"] == "bad ***"
    with pytest.raises(ProviderError, match=r"bad \*\*\*"):
        next(stream)


def test_openai_experimental_and_legacy_resume_validation(openai_provider):
    provider, _ = openai_provider
    request = ModelRequest(
        provider="openai",
        model="gpt-test",
        messages=[ModelMessage(role="user", content="x")],
        provider_options={"experimental_tools": [{}]},
    )
    with pytest.raises(ProviderError, match="allow_experimental_tools"):
        provider._responses_params(request)
    with pytest.raises(ProviderError, match="list of tool mappings"):
        provider._experimental_tools(
            request.model_copy(
                update={
                    "provider_options": {
                        "allow_experimental_tools": True,
                        "experimental_tools": "bad",
                    }
                }
            )
        )
    with pytest.raises(ProviderError, match="Invalid suspended state"):
        provider.resume_tool_flow({}, tools=[])
    with pytest.raises(ProviderError, match="Missing resume intervention"):
        provider.resume_tool_flow({"schema": "openai_tool_v1"}, tools=[])
