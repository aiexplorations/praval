"""Edge-case contracts for the Anthropic 0.8 provider adapter."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from praval.core.agent import AgentConfig
from praval.core.exceptions import ProviderError
from praval.models import (
    ContentPart,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ReasoningConfig,
    ToolResult,
)
from praval.providers.anthropic import AnthropicProvider, _redact_secrets


@pytest.fixture
def anthropic_provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    client = Mock()
    with patch("praval.providers.anthropic.anthropic.Anthropic", return_value=client):
        provider = AnthropicProvider(
            AgentConfig(provider="anthropic", model="claude-test", max_tokens=100)
        )
    return provider, client


def test_anthropic_initialization_options_close_and_redaction(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-key")
    client = Mock()
    with patch(
        "praval.providers.anthropic.anthropic.Anthropic", return_value=client
    ) as constructor:
        provider = AnthropicProvider(
            AgentConfig(
                provider="anthropic",
                model="claude-test",
                base_url="https://anthropic.test",
                timeout=9,
            )
        )
    constructor.assert_called_once_with(
        api_key="secret-key", base_url="https://anthropic.test", timeout=9
    )
    assert _redact_secrets("") == ""
    assert _redact_secrets("bad secret-key") == "bad ***"
    provider.close()
    client.close.assert_called_once()


def test_anthropic_content_formatting_and_text_extraction(anthropic_provider):
    provider, _ = anthropic_provider
    formatted = provider._format_anthropic_content(
        [
            ContentPart.text_part("hello"),
            ContentPart.image_url("https://image"),
            ContentPart.image_base64("AAA", "image/jpeg"),
        ]
    )
    assert formatted[1]["source"] == {"type": "url", "url": "https://image"}
    assert formatted[2]["source"]["media_type"] == "image/jpeg"
    with pytest.raises(ProviderError, match="cannot serialize"):
        provider._format_anthropic_content([ContentPart.audio_base64("AAA")])
    assert (
        provider._content_to_text(
            [ContentPart.text_part("a"), ContentPart.image_url("https://image")]
        )
        == "a"
    )
    assert provider._content_to_text(42) == "42"
    assert (
        provider._extract_text(
            {"content": [{"type": "text", "text": "one"}, {"type": "tool_use"}]}
        )
        == "one"
    )


def test_anthropic_serializes_sdk_content_blocks_and_error_results(
    anthropic_provider,
):
    provider, _ = anthropic_provider
    model_block = Mock()
    model_block.model_dump.return_value = {"type": "text", "text": "model"}
    tool_block = SimpleNamespace(type="tool_use", id="tool-1", name="lookup", input={})
    text_block = SimpleNamespace(type="text", text="text")
    blocks = provider._serialize_content_blocks(
        [{"type": "text", "text": "dict"}, model_block, tool_block, text_block]
    )
    assert [block["type"] for block in blocks] == [
        "text",
        "text",
        "tool_use",
        "text",
    ]
    result = provider._anthropic_tool_result(
        ToolResult(
            tool_call_id="tool-1", name="lookup", content="failed", is_error=True
        )
    )
    assert result["is_error"] is True


def test_anthropic_usage_and_reasoning_helpers_cover_object_shapes(
    anthropic_provider,
):
    provider, _ = anthropic_provider
    usage = provider._extract_usage(
        SimpleNamespace(usage=SimpleNamespace(input_tokens=2, output_tokens=3))
    )
    assert usage.total_tokens == 5
    assert provider._extract_usage({}) is None

    request = ModelRequest(
        messages=[ModelMessage(role="user", content="x")],
        reasoning=ReasoningConfig(mode="enabled", budget_tokens=20, display="summary"),
    )
    assert provider._anthropic_thinking(request) == {
        "type": "enabled",
        "budget_tokens": 20,
        "display": "summary",
    }
    assert (
        provider._anthropic_thinking(
            request.model_copy(update={"reasoning": ReasoningConfig(effort="low")})
        )
        == {}
    )


def test_anthropic_experimental_tools_validate_direct_requests(anthropic_provider):
    provider, _ = anthropic_provider
    base = ModelRequest(messages=[ModelMessage(role="user", content="x")])
    with pytest.raises(ProviderError, match="allow_experimental_tools"):
        provider._experimental_tools(
            base.model_copy(update={"provider_options": {"experimental_tools": [{}]}})
        )
    with pytest.raises(ProviderError, match="list of tool mappings"):
        provider._experimental_tools(
            base.model_copy(
                update={
                    "provider_options": {
                        "allow_experimental_tools": True,
                        "experimental_tools": "bad",
                    }
                }
            )
        )


def test_anthropic_stream_context_emits_delta_usage_and_final(anthropic_provider):
    provider, client = anthropic_provider
    final = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="hello")],
        usage={"input_tokens": 1, "output_tokens": 2},
    )
    stream = Mock()
    stream.text_stream = ["hel", "", "lo"]
    stream.get_final_message.return_value = final
    stream.__enter__ = Mock(return_value=stream)
    stream.__exit__ = Mock(return_value=False)
    client.messages.stream.return_value = stream

    events = list(
        provider.stream(
            ModelRequest(
                provider="anthropic",
                model="claude-test",
                messages=[ModelMessage(role="user", content="x")],
                stream=True,
            )
        )
    )
    assert [event.type for event in events] == ["delta", "delta", "usage", "final"]
    assert events[-1].response.content == "hello"


def test_anthropic_stream_create_normalizes_events_and_errors(anthropic_provider):
    provider, client = anthropic_provider
    client.messages.stream = None
    client.messages.create.return_value = iter(
        [
            {"type": "content_block_delta", "delta": {"text": "hi"}},
            {"type": "message_delta", "usage": {"output_tokens": 2}},
            {"type": "error", "message": "ignored"},
        ]
    )
    events = list(
        provider.stream(
            ModelRequest(
                provider="anthropic",
                model="claude-test",
                messages=[ModelMessage(role="user", content="x")],
                stream=True,
            )
        )
    )
    assert [event.type for event in events] == [
        "delta",
        "error",
        "usage",
        "final",
    ]

    client.messages.create.side_effect = RuntimeError("stream failed")
    stream = provider.stream(
        ModelRequest(
            provider="anthropic",
            model="claude-test",
            messages=[ModelMessage(role="user", content="x")],
            stream=True,
        )
    )
    assert next(stream).type == "error"
    with pytest.raises(ProviderError, match="streaming error"):
        next(stream)


def test_anthropic_continuation_and_legacy_resume_validation(anthropic_provider):
    provider, _ = anthropic_provider
    request = ModelRequest(
        provider="anthropic",
        model="claude-test",
        messages=[ModelMessage(role="user", content="x")],
    )
    with pytest.raises(ProviderError, match="continuation state"):
        provider.continue_with_tool_results(request, ModelResponse(), [])
    with pytest.raises(ProviderError, match="Invalid suspended state"):
        provider.resume_tool_flow({}, tools=[])
    with pytest.raises(ProviderError, match="Missing resume intervention"):
        provider.resume_tool_flow({"schema": "anthropic_tool_v1"}, tools=[])
