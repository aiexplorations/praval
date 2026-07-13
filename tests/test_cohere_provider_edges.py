"""Edge-case contracts for the Cohere 0.8 provider adapter."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from praval.core.agent import AgentConfig
from praval.core.exceptions import ProviderError
from praval.models import ModelMessage, ModelRequest, ModelResponse
from praval.providers.cohere import CohereProvider, _redact_secrets


@pytest.fixture
def cohere_provider(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "test-cohere-key")
    client = Mock()
    with patch("praval.providers.cohere.cohere.Client", return_value=client):
        provider = CohereProvider(
            AgentConfig(provider="cohere", model="command-test", max_tokens=100)
        )
    return provider, client


def test_cohere_redaction_close_and_missing_key(monkeypatch, cohere_provider):
    provider, client = cohere_provider
    monkeypatch.setenv("COHERE_API_KEY", "secret-key")
    assert _redact_secrets("") == ""
    assert _redact_secrets("bad secret-key") == "bad ***"
    provider.close()
    client.close.assert_called_once()

    monkeypatch.delenv("COHERE_API_KEY")
    with pytest.raises(ProviderError, match="environment variable not set"):
        CohereProvider(AgentConfig(provider="cohere"))


def test_cohere_chat_format_handles_empty_and_assistant_tail(cohere_provider):
    provider, _ = cohere_provider
    assert provider._prepare_chat_format([{"role": "system", "content": "s"}]) == (
        "",
        [],
    )
    message, history = provider._prepare_chat_format(
        [
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
        ]
    )
    assert message == "Please continue."
    assert history == [
        {"role": "USER", "message": "one"},
        {"role": "CHATBOT", "message": "two"},
    ]


def test_cohere_request_params_include_history_system_tools_and_options(
    cohere_provider,
):
    provider, _ = cohere_provider

    def lookup(query: str) -> str:
        return query

    request = ModelRequest(
        provider="cohere",
        model="command-test",
        messages=[
            ModelMessage(role="system", content="system"),
            ModelMessage(role="user", content="past"),
            ModelMessage(role="assistant", content="answer"),
            ModelMessage(role="user", content="now"),
        ],
        timeout=4,
        provider_options={"seed": 7, "capabilities": {"tools": True}},
    )
    params = provider._request_chat_params(
        request,
        tools=[
            {
                "function": lookup,
                "description": "Lookup",
                "parameters": {"query": {"type": "str", "required": True}},
            }
        ],
    )
    assert params["message"] == "now"
    assert params["preamble"] == "system"
    assert params["chat_history"][1]["role"] == "CHATBOT"
    assert params["tools"][0]["parameters"]["required"] == ["query"]
    assert params["timeout"] == 4
    assert params["seed"] == 7
    assert "capabilities" not in params


def test_cohere_serializes_object_calls_and_streams_fallback(cohere_provider):
    provider, client = cohere_provider
    calls = provider._serialize_tool_calls(
        [SimpleNamespace(id="call-1", name="lookup", args={"q": "x"})]
    )
    assert calls == [{"id": "call-1", "name": "lookup", "args": {"q": "x"}}]

    client.chat.return_value = SimpleNamespace(
        text="hello", tool_calls=[], finish_reason="COMPLETE"
    )
    events = list(
        provider.stream(
            ModelRequest(
                provider="cohere",
                model="command-test",
                messages=[ModelMessage(role="user", content="x")],
            )
        )
    )
    assert [event.type for event in events] == ["delta", "final"]
    assert events[-1].response.finish_reason == "COMPLETE"


def test_cohere_continuation_and_followup_error_fallback(cohere_provider):
    provider, client = cohere_provider
    request = ModelRequest(
        provider="cohere",
        model="command-test",
        messages=[ModelMessage(role="user", content="x")],
    )
    with pytest.raises(ProviderError, match="continuation state"):
        provider.continue_with_tool_results(request, ModelResponse(), [])
    client.chat.side_effect = RuntimeError("followup failed")
    assert (
        provider._follow_up_response(
            original_messages=[{"role": "user", "content": "x"}],
            tool_results=[{"name": "lookup", "result": "cached"}],
        )
        == "cached"
    )


def test_cohere_legacy_resume_validation(cohere_provider):
    provider, _ = cohere_provider
    assert provider._build_runtime(None) is None
    assert provider._build_runtime({"run_id": "missing"}) is None
    with pytest.raises(ProviderError, match="Invalid suspended state"):
        provider.resume_tool_flow({}, tools=[])
    with pytest.raises(ProviderError, match="Missing resume intervention"):
        provider.resume_tool_flow({"schema": "cohere_tool_v1"}, tools=[])
