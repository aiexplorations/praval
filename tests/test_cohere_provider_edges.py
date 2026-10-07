"""Edge-case contracts for the Cohere 0.8 provider adapter."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from cohere.types.tool_call import ToolCall as CohereToolCall

from praval.core.agent import AgentConfig
from praval.core.exceptions import ProviderError
from praval.models import ModelMessage, ModelRequest, ModelResponse, ToolResult
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


def test_cohere_reads_sdk_parameters_and_numbers_calls_across_rounds(
    cohere_provider,
):
    provider, _ = cohere_provider
    calls = provider._serialize_tool_calls(
        [
            CohereToolCall(name="lookup", parameters={"q": "x"}),
            {"name": "lookup", "parameters": {"q": "y"}},
        ]
    )
    assert calls == [
        {"id": None, "name": "lookup", "args": {"q": "x"}},
        {"id": None, "name": "lookup", "args": {"q": "y"}},
    ]

    history = [
        {"role": "USER", "message": "q"},
        {"role": "CHATBOT", "message": "", "tool_calls": [{"name": "a"}] * 2},
        "ignored",
    ]
    assert provider._history_tool_call_count(history) == 2
    assert provider._history_tool_call_count(None) == 0
    response = provider._chat_model_response(
        SimpleNamespace(
            text="",
            tool_calls=[CohereToolCall(name="lookup", parameters={"q": "z"})],
        ),
        {"message": "", "chat_history": history, "tool_results": [{"r": 1}]},
    )
    assert response.tool_calls[0].id == "cohere-call-2"
    assert response.metadata["cohere_chat_history"][-2:] == [
        {"role": "TOOL", "tool_results": [{"r": 1}]},
        {
            "role": "CHATBOT",
            "message": "",
            "tool_calls": [{"name": "lookup", "parameters": {"q": "z"}}],
        },
    ]


def test_cohere_tool_result_shape_for_errors_and_unknown_calls(cohere_provider):
    provider, _ = cohere_provider
    result = ToolResult(
        tool_call_id="missing", name="lookup", content="Error: boom", is_error=True
    )
    assert provider._cohere_tool_result(result, None) == {
        "call": {"name": "lookup", "parameters": {}},
        "outputs": [{"result": "Error: boom", "is_error": True}],
    }
