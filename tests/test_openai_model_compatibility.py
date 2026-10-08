"""OpenAI model parameter, endpoint and dependent-tool compatibility contracts."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from provider_harnesses import OpenAIHarness, _tools

from praval import Agent
from praval.core.agent import AgentConfig
from praval.core.exceptions import ProviderError
from praval.models import ModelRequest, ReasoningConfig, ToolSpec
from praval.providers.openai import OpenAIProvider
from praval.providers.registry import reasoning_parameters


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with patch("praval.providers.openai.openai.OpenAI", return_value=Mock()):
        return OpenAIProvider(AgentConfig(provider="openai", model="gpt-6-luna"))


@pytest.mark.parametrize(
    "model",
    [
        "gpt-6-luna",
        "gpt-6-sol",
        "gpt-6-astra",
        "gpt-6.1-sol",
        "gpt-7-new",
        "gpt-6-luna-2026-10-01",
        "openai:gpt-6-luna",
        "vendor/gpt-6-luna",
    ],
)
def test_modern_chat_parameters_preserve_token_limit(provider, model):
    request = ModelRequest(
        provider="openai",
        model=model,
        messages=[],
        temperature=0.2,
        max_output_tokens=500,
        provider_options={"top_p": 0.8, "logprobs": True, "top_logprobs": 2},
    )
    params = provider._chat_completion_params(request)
    assert params["max_completion_tokens"] == 500
    assert (
        not {"max_tokens", "temperature", "top_p", "logprobs", "top_logprobs"}
        & params.keys()
    )


@pytest.mark.parametrize("model", ["gpt-4o", "gpt-4.1", "custom-model", "gpt-5ish"])
def test_older_and_custom_models_keep_existing_parameters(provider, model):
    params = provider._base_chat_completion_params(
        model=model,
        messages=[],
        temperature=0.2,
        max_output_tokens=500,
    )
    assert params["max_tokens"] == 500
    assert params["temperature"] == 0.2
    assert "max_completion_tokens" not in params


@pytest.mark.parametrize(
    "reasoning", [None, ReasoningConfig(level="low"), ReasoningConfig(effort="high")]
)
def test_responses_omits_sampling_with_or_without_reasoning(provider, reasoning):
    params = provider._responses_params(
        ModelRequest(
            provider="openai",
            model="gpt-6-luna",
            messages=[],
            temperature=0.2,
            max_output_tokens=500,
            reasoning=reasoning,
            provider_options={"top_p": 0.8, "top_logprobs": 2},
        )
    )
    assert params["max_output_tokens"] == 500
    assert not {"temperature", "top_p", "top_logprobs"} & params.keys()
    if reasoning:
        assert params["reasoning"]["effort"] == (reasoning.level or reasoning.effort)


@pytest.mark.parametrize(
    "model",
    ["gpt-6-luna", "gpt-6-sol", "gpt-6-astra", "gpt-6.1-sol", "gpt-6-luna-2026-10-01"],
)
@pytest.mark.parametrize("level", ["none", "low", "medium", "high"])
def test_gpt6_reasoning_profiles_are_model_specific(model, level):
    request = ModelRequest(
        provider="openai",
        model=model,
        messages=[],
        reasoning=ReasoningConfig(level=level),
    )
    if model in {"gpt-6-astra", "gpt-6.1-sol"} and level == "none":
        with pytest.raises(ProviderError, match="accepted levels: low, medium, high"):
            reasoning_parameters(request)
    else:
        assert reasoning_parameters(request) == {"effort": level}


@pytest.mark.parametrize("model", ["gpt-6-luna", "gpt-6-sol", "gpt-6-luna-2026-10-01"])
def test_explicit_chat_tools_use_none(provider, model):
    request = ModelRequest(
        provider="openai",
        model=model,
        messages=[],
        tools=[ToolSpec(name="lookup")],
        provider_options={"endpoint": "chat.completions"},
    )
    assert not provider._use_responses_api(request)
    assert provider._chat_completion_params(request)["reasoning_effort"] == "none"


@pytest.mark.parametrize(
    "model,reasoning",
    [
        ("gpt-6-astra", None),
        ("gpt-6.1-sol", None),
        ("gpt-6-luna", ReasoningConfig(level="low")),
        ("gpt-6-sol", ReasoningConfig(effort="high")),
    ],
)
def test_incompatible_explicit_chat_tools_fail_before_dispatch(
    provider, model, reasoning
):
    request = ModelRequest(
        provider="openai",
        model=model,
        messages=[],
        tools=[ToolSpec(name="lookup")],
        reasoning=reasoning,
        provider_options={"endpoint": "chat.completions"},
    )
    with pytest.raises(ProviderError, match="requires the Responses API"):
        provider.invoke(request)
    provider.client.chat.completions.create.assert_not_called()


@pytest.mark.parametrize(
    "endpoint,level",
    [
        (None, None),
        (None, "low"),
        ("responses", None),
        ("responses", "low"),
        ("chat.completions", None),
        ("chat.completions", "none"),
    ],
)
@pytest.mark.parametrize("use_async", [False, True])
def test_gpt6_dependent_tool_rounds_preserve_endpoint_and_parameters(
    monkeypatch, endpoint, level, use_async
):
    harness = OpenAIHarness()
    harness.model = "gpt-6-luna"
    adapter = harness.build(monkeypatch)
    chat = endpoint == "chat.completions"
    if chat:
        harness.responses = [
            harness.tool_turn([("lookup", {"city": "Paris"})]),
            harness.tool_turn([("forecast", {"code": "PX-1"})]),
            harness.final_turn("Sunny"),
        ]
    else:
        adapter.client.responses.create.side_effect = harness.respond
        harness.responses = [
            SimpleNamespace(
                id="resp-1",
                output=[
                    {
                        "type": "function_call",
                        "call_id": "call-1",
                        "name": "lookup",
                        "arguments": json.dumps({"city": "Paris"}),
                    }
                ],
                output_text="",
                usage=None,
            ),
            SimpleNamespace(
                id="resp-2",
                output=[
                    {
                        "type": "function_call",
                        "call_id": "call-2",
                        "name": "forecast",
                        "arguments": json.dumps({"code": "PX-1"}),
                    }
                ],
                output_text="",
                usage=None,
            ),
            SimpleNamespace(id="resp-3", output=[], output_text="Sunny", usage=None),
        ]
    log = []
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=adapter
    ):
        with Agent(
            "compatibility",
            provider="openai",
            model=harness.model,
            reasoning=level,
            config={"temperature": 0.2, "retries": 0},
        ) as agent:
            for tool in _tools(log):
                agent.tool(tool["function"])
            options = {"provider_options": {"endpoint": endpoint}} if endpoint else {}
            response = (
                asyncio.run(agent.agenerate("Forecast?", **options))
                if use_async
                else agent.generate("Forecast?", **options)
            )
    assert response.content == "Sunny"
    assert log == [("lookup", "Paris"), ("forecast", "PX-1")]
    assert len(harness.requests) == 3
    for params in harness.requests:
        assert "temperature" not in params
        assert "max_tokens" not in params
        if chat:
            assert params["reasoning_effort"] == "none"
            assert "max_completion_tokens" in params
        else:
            assert "max_output_tokens" in params
            if level:
                assert params["reasoning"] == {"effort": level}
    if not chat:
        assert harness.requests[1]["previous_response_id"] == "resp-1"
        assert harness.requests[2]["previous_response_id"] == "resp-2"
        assert harness.requests[2]["input"][0]["call_id"] == "call-2"
        adapter.client.chat.completions.create.assert_not_called()


@pytest.mark.parametrize("endpoint", ["responses", "chat.completions"])
def test_gpt6_streaming_uses_supported_parameters(provider, endpoint):
    if endpoint == "responses":
        create = provider.client.responses.create
        create.return_value = iter(
            [{"type": "response.output_text.delta", "delta": "Ready"}]
        )
    else:
        create = provider.client.chat.completions.create
        create.return_value = iter(
            [{"choices": [{"delta": {"content": "Ready"}, "finish_reason": "stop"}]}]
        )
    events = list(
        provider.stream(
            ModelRequest(
                provider="openai",
                model="gpt-6-luna",
                messages=[],
                temperature=0.2,
                provider_options={"endpoint": endpoint},
            )
        )
    )
    assert any(event.delta == "Ready" for event in events)
    assert "temperature" not in create.call_args.kwargs
    assert "max_tokens" not in create.call_args.kwargs
