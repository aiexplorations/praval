"""Tests for local OpenAI-compatible and Gemini providers."""

import json
import os
from unittest.mock import Mock, patch

from praval.core.agent import AgentConfig
from praval.model_runtime import ModelRuntime
from praval.models import ModelMessage, ModelRequest
from praval.providers.gemini import GeminiProvider
from praval.providers.openai_compatible import OpenAICompatibleProvider


def _mock_gemini_response(payload):
    response = Mock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    return response


@patch.dict(os.environ, {}, clear=True)
@patch("openai.OpenAI")
def test_openai_compatible_ollama_preset_uses_local_base_url(mock_openai):
    config = AgentConfig(provider="ollama", model="llama3")

    provider = OpenAICompatibleProvider(config)

    mock_openai.assert_called_once()
    kwargs = mock_openai.call_args.kwargs
    assert kwargs["api_key"] == "local"
    assert kwargs["base_url"] == "http://localhost:11434/v1"
    assert provider._model_name() == "llama3"


def test_gemini_build_payload_maps_messages_and_tools():
    config = AgentConfig(provider="gemini", model="gemini-test", base_url="http://test")
    provider = GeminiProvider(config)

    def lookup(query: str) -> str:
        return query

    payload = provider._build_payload(
        [
            {"role": "system", "content": "You are concise."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ],
        [{"function": lookup, "description": "Lookup", "parameters": {"query": {}}}],
    )

    assert payload["systemInstruction"]["parts"][0]["text"] == "You are concise."
    assert payload["contents"][0]["role"] == "user"
    assert payload["contents"][1]["role"] == "model"
    assert payload["tools"][0]["functionDeclarations"][0]["name"] == "lookup"


def test_gemini_build_payload_serializes_audio_video_and_file_parts():
    config = AgentConfig(provider="gemini", model="gemini-test", base_url="http://test")
    provider = GeminiProvider(config)

    payload = provider._build_payload(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze these."},
                    {
                        "type": "audio_base64",
                        "data": "AAA",
                        "mime_type": "audio/mpeg",
                    },
                    {
                        "type": "video_url",
                        "url": "https://example.com/video.mp4",
                        "mime_type": "video/mp4",
                    },
                    {
                        "type": "file_url",
                        "url": "https://example.com/paper.pdf",
                        "mime_type": "application/pdf",
                    },
                ],
            }
        ],
        tools=None,
    )

    parts = payload["contents"][0]["parts"]
    assert parts[0] == {"text": "Analyze these."}
    assert parts[1] == {"inlineData": {"mimeType": "audio/mpeg", "data": "AAA"}}
    assert parts[2] == {
        "fileData": {
            "mimeType": "video/mp4",
            "fileUri": "https://example.com/video.mp4",
        }
    }
    assert parts[3] == {
        "fileData": {
            "mimeType": "application/pdf",
            "fileUri": "https://example.com/paper.pdf",
        }
    }


@patch("urllib.request.urlopen")
def test_gemini_generate_extracts_text(mock_urlopen):
    mock_urlopen.return_value = _mock_gemini_response(
        {"candidates": [{"content": {"parts": [{"text": "hello"}]}}]}
    )
    config = AgentConfig(provider="gemini", model="gemini-test", base_url="http://test")
    provider = GeminiProvider(config)

    text = provider.generate([{"role": "user", "content": "Hello"}])

    assert text == "hello"
    mock_urlopen.assert_called_once()


@patch("urllib.request.urlopen")
def test_gemini_generate_handles_function_call_round_trip(mock_urlopen):
    mock_urlopen.side_effect = [
        _mock_gemini_response(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": "lookup",
                                        "args": {"query": "praval"},
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        ),
        _mock_gemini_response(
            {
                "candidates": [
                    {"content": {"parts": [{"text": "Praval is a framework."}]}}
                ]
            }
        ),
    ]
    config = AgentConfig(provider="gemini", model="gemini-test", base_url="http://test")
    provider = GeminiProvider(config)

    def lookup(query: str) -> str:
        return f"found:{query}"

    text = provider.generate(
        [{"role": "user", "content": "What is Praval?"}],
        tools=[
            {
                "function": lookup,
                "description": "Lookup",
                "parameters": {"query": {"type": "str", "required": True}},
            }
        ],
    )

    assert text == "Praval is a framework."
    assert mock_urlopen.call_count == 2
    followup_request = mock_urlopen.call_args_list[1].args[0]
    followup_payload = json.loads(followup_request.data.decode("utf-8"))
    assert followup_payload["contents"][-2]["parts"][0]["functionCall"] == {
        "name": "lookup",
        "args": {"query": "praval"},
    }
    assert followup_payload["contents"][-1]["parts"][0]["functionResponse"] == {
        "name": "lookup",
        "response": {"result": "found:praval"},
    }


@patch("urllib.request.urlopen")
def test_gemini_invoke_returns_tool_call_metadata(mock_urlopen):
    mock_urlopen.return_value = _mock_gemini_response(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "add",
                                    "args": {"x": 2, "y": 3},
                                }
                            }
                        ]
                    }
                }
            ]
        }
    )
    config = AgentConfig(provider="gemini", model="gemini-test", base_url="http://test")
    provider = GeminiProvider(config)

    def add(x: int, y: int) -> int:
        return x + y

    response = provider.invoke(
        ModelRequest(
            provider="gemini",
            model="gemini-test",
            messages=[ModelMessage(role="user", content="2+3?")],
        ),
        tools=[
            {
                "function": add,
                "description": "Add",
                "parameters": {
                    "x": {"type": "int", "required": True},
                    "y": {"type": "int", "required": True},
                },
            }
        ],
    )

    assert response.content == ""
    assert response.tool_calls[0].name == "add"
    assert response.tool_calls[0].arguments == {"x": 2, "y": 3}
    assert response.metadata["gemini_contents"][-1]["role"] == "model"


@patch("urllib.request.urlopen")
def test_gemini_adapter_defers_client_tool_execution_to_runtime(mock_urlopen):
    mock_urlopen.return_value = _mock_gemini_response(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "add",
                                    "args": {"x": 2, "y": 3},
                                }
                            }
                        ]
                    }
                }
            ]
        }
    )
    calls = []

    def add(x: int, y: int) -> int:
        calls.append((x, y))
        return x + y

    tool = {
        "function": add,
        "description": "Add",
        "parameters": {
            "x": {"type": "int", "required": True},
            "y": {"type": "int", "required": True},
        },
    }
    provider = GeminiProvider(
        AgentConfig(provider="gemini", model="gemini-test", base_url="http://test")
    )

    response = provider.invoke(
        ModelRequest(
            provider="gemini",
            model="gemini-test",
            messages=[ModelMessage(role="user", content="2+3?")],
        ),
        tools=[tool],
    )

    assert response.content == ""
    assert response.tool_calls[0].name == "add"
    assert calls == []


@patch("urllib.request.urlopen")
def test_gemini_runtime_executes_tool_and_submits_function_response(mock_urlopen):
    mock_urlopen.side_effect = [
        _mock_gemini_response(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": "add",
                                        "args": {"x": 2, "y": 3},
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        ),
        _mock_gemini_response(
            {"candidates": [{"content": {"parts": [{"text": "5"}]}}]}
        ),
    ]

    def add(x: int, y: int) -> int:
        return x + y

    tool = {
        "function": add,
        "description": "Add",
        "parameters": {
            "x": {"type": "int", "required": True},
            "y": {"type": "int", "required": True},
        },
    }
    config = AgentConfig(provider="gemini", model="gemini-test", base_url="http://test")
    runtime = ModelRuntime(
        provider=GeminiProvider(config),
        provider_name="gemini",
        config=config,
    )

    response = runtime.invoke(
        messages=[{"role": "user", "content": "2+3?"}],
        tools=[tool],
    )

    assert response.content == "5"
    assert response.metadata["tool_results"][0]["content"] == "5"
    followup_request = mock_urlopen.call_args_list[1].args[0]
    followup_payload = json.loads(followup_request.data.decode("utf-8"))
    assert followup_payload["contents"][-1]["parts"][0]["functionResponse"] == {
        "name": "add",
        "response": {"result": "5"},
    }
