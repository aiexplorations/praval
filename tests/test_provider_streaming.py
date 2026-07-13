"""Provider streaming adapter contract tests with fake SDK responses."""

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from praval.core.agent import AgentConfig
from praval.models import ModelMessage, ModelRequest
from praval.providers.anthropic import AnthropicProvider
from praval.providers.gemini import GeminiProvider
from praval.providers.openai import OpenAIProvider


def _request(provider: str = "openai") -> ModelRequest:
    return ModelRequest(
        provider=provider,
        model="test-model",
        messages=[ModelMessage(role="user", content="hello")],
        stream=True,
        stream_options={"include_usage": True},
    )


def test_openai_chat_stream_normalizes_delta_usage_and_final():
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.config = AgentConfig(provider="openai", model="test-model")
    chunks = [
        {"choices": [{"delta": {"content": "hel"}}]},
        {"choices": [{"delta": {"content": "lo"}, "finish_reason": "stop"}]},
        {
            "choices": [],
            "usage": {
                "prompt_tokens": 2,
                "completion_tokens": 3,
                "total_tokens": 5,
            },
        },
    ]
    provider.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=Mock(return_value=iter(chunks)))
        )
    )

    events = list(provider.stream(_request("openai")))

    assert [event.type for event in events] == ["delta", "delta", "usage", "final"]
    assert events[-1].response.content == "hello"
    assert events[-1].usage.total_tokens == 5
    call_kwargs = provider.client.chat.completions.create.call_args.kwargs
    assert call_kwargs["stream"] is True
    assert call_kwargs["stream_options"] == {"include_usage": True}


def test_openai_responses_stream_normalizes_tool_delta_and_final():
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.config = AgentConfig(provider="openai", model="test-model")
    events = [
        {"type": "response.output_text.delta", "delta": "hi"},
        {"type": "response.function_call_arguments.delta", "delta": '{"x"'},
        {
            "type": "response.output_item.done",
            "item": {
                "type": "function_call",
                "id": "call-1",
                "name": "lookup",
                "arguments": '{"query":"praval"}',
            },
        },
        {
            "type": "response.completed",
            "response": {
                "output": [
                    {"content": [{"type": "output_text", "text": "hi"}]},
                ],
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            },
        },
    ]
    provider.client = SimpleNamespace(
        responses=SimpleNamespace(create=Mock(return_value=iter(events)))
    )
    request = _request("openai")
    request.provider_options["endpoint"] = "responses"

    streamed = list(provider.stream(request))

    assert [event.type for event in streamed] == [
        "delta",
        "tool_call_delta",
        "tool_call",
        "usage",
        "final",
    ]
    assert streamed[2].tool_call.name == "lookup"
    assert streamed[-1].response.content == "hi"


def test_anthropic_context_stream_normalizes_delta_usage_and_final():
    class FakeAnthropicStream:
        text_stream = ["hel", "lo"]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def get_final_message(self):
            return {
                "content": [{"type": "text", "text": "hello"}],
                "usage": {"input_tokens": 2, "output_tokens": 3},
            }

    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.config = AgentConfig(provider="anthropic", model="test-model")
    provider.client = SimpleNamespace(
        messages=SimpleNamespace(stream=Mock(return_value=FakeAnthropicStream()))
    )

    events = list(provider.stream(_request("anthropic")))

    assert [event.type for event in events] == ["delta", "delta", "usage", "final"]
    assert events[-1].response.content == "hello"
    assert events[-1].usage.total_tokens == 5


@patch("urllib.request.urlopen")
def test_gemini_stream_parses_sse_lines(mock_urlopen):
    response = Mock()
    response.__iter__ = Mock(
        return_value=iter(
            [
                b'data: {"candidates":[{"content":{"parts":[{"text":"hel"}]}}]}\n',
                b'data: {"candidates":[{"content":{"parts":[{"text":"lo"}]}}]}\n',
                b"data: [DONE]\n",
            ]
        )
    )
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    mock_urlopen.return_value = response
    provider = GeminiProvider(
        AgentConfig(provider="gemini", model="test-model", base_url="http://test")
    )

    events = list(provider.stream(_request("gemini")))

    assert [event.type for event in events] == ["delta", "delta", "final"]
    assert events[-1].response.content == "hello"
    request_body = mock_urlopen.call_args.args[0].data
    assert json.loads(request_body.decode("utf-8"))["contents"][0]["parts"] == [
        {"text": "hello"}
    ]
