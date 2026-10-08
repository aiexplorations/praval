"""Portable reasoning is preserved across agent entry points and tool rounds."""

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from cohere.types import AssistantMessageResponse
from provider_harnesses import (
    AnthropicHarness,
    GeminiHarness,
    OpenAICompatibleHarness,
    OpenAIHarness,
    _tools,
)
from pydantic import ValidationError

from praval import Agent, agent
from praval.core.agent import AgentConfig
from praval.core.exceptions import ProviderError
from praval.model_runtime import normalize_reasoning_config
from praval.models import ModelRequest, ReasoningConfig
from praval.providers.cohere import CohereProvider
from praval.providers.registry import get_provider_registry, reasoning_parameters


class ResponsesHarness(OpenAIHarness):
    name = "responses"
    provider_options = {"endpoint": "responses"}

    def build(self, monkeypatch):
        provider = super().build(monkeypatch)
        provider.client.responses.create.side_effect = self.respond
        return provider

    def tool_turn(self, calls):
        return SimpleNamespace(
            id=self.call_id(),
            output=[
                {
                    "type": "function_call",
                    "call_id": self.call_id(),
                    "name": name,
                    "arguments": json.dumps(args),
                }
                for name, args in calls
            ],
            output_text="",
            usage=None,
        )

    def final_turn(self, text):
        return SimpleNamespace(
            id=self.call_id(), output=[], output_text=text, usage=None
        )


class V2Harness:
    name = "cohere-v2"
    provider_name = "cohere"
    provider_options = {}
    model = "command-a-reasoning-08-2025"

    def __init__(self):
        self.requests = []
        self.responses = []

    def build(self, monkeypatch):
        monkeypatch.setenv("COHERE_API_KEY", "fake-key")
        self.client = Mock()
        self.client.chat.side_effect = self.respond
        with patch("praval.providers.cohere.cohere.Client", return_value=Mock()):
            provider = CohereProvider(AgentConfig(provider="cohere", model=self.model))
        provider._reasoning_client = self.client
        return provider

    def respond(self, **params):
        self.requests.append(copy.deepcopy(params))
        return self.responses.pop(0)

    def turn(self, text, calls):
        native = {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "private native reasoning"},
                {"type": "text", "text": text},
            ],
            "tool_calls": [
                {
                    "id": f"call-{i}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args),
                    },
                }
                for i, (name, args) in enumerate(calls)
            ],
        }
        return SimpleNamespace(
            message=AssistantMessageResponse.model_validate(native),
            finish_reason="TOOL_CALL" if calls else "COMPLETE",
            usage=None,
        )

    def tool_turn(self, calls):
        return self.turn("", calls)

    def final_turn(self, text):
        return self.turn(text, [])


# Each combination sends a real native initial request and continuation. Tool
# execution makes stream/astream follow the same runtime loop as text entry points.
FAMILIES = [
    (OpenAIHarness, "openai", "gpt-5.4", ("none", "low", "medium", "high")),
    (ResponsesHarness, "openai", "gpt-5.4", ("none", "low", "medium", "high")),
    (
        OpenAICompatibleHarness,
        "vllm",
        "google/gemma-4-26B-A4B-it",
        ("none", "low", "medium", "high"),
    ),
    (
        AnthropicHarness,
        "anthropic",
        "claude-sonnet-5",
        ("none", "low", "medium", "high"),
    ),
    (
        AnthropicHarness,
        "anthropic",
        "claude-haiku-4-5",
        ("none", "low", "medium", "high"),
    ),
    (GeminiHarness, "gemini", "gemini-3.5-flash", ("low", "medium", "high")),
    (GeminiHarness, "gemini", "gemini-2.5-flash", ("none", "low", "medium", "high")),
    (
        V2Harness,
        "cohere",
        "command-a-reasoning-08-2025",
        ("none", "low", "medium", "high"),
    ),
]
CASES = [
    (cls, provider, model, level)
    for cls, provider, model, levels in FAMILIES
    for level in levels
]


def native_controls(params, provider, endpoint):
    if provider in {"openai", "vllm"}:
        return (
            {"effort": params["reasoning"]["effort"]}
            if endpoint == "responses"
            else {"effort": params["reasoning_effort"]}
        )
    if provider == "anthropic":
        controls = {"thinking": params["thinking"]}
        if params.get("output_config"):
            controls["output_config"] = params["output_config"]
        return controls
    if provider == "gemini":
        return params["generationConfig"]["thinkingConfig"]
    return {"thinking": params["thinking"]}


@pytest.mark.parametrize(
    "cls,provider,model,level",
    CASES,
    ids=[f"{p}-{c.name}-{m}-{l}" for c, p, m, l in CASES],
)
@pytest.mark.parametrize(
    "entry", ["chat", "generate", "agenerate", "stream", "astream"]
)
def test_reasoning_agent_entry_and_continuation(
    monkeypatch, cls, provider, model, level, entry
):
    harness = cls()
    harness.model = model
    adapter = harness.build(monkeypatch)
    harness.responses = [
        harness.tool_turn([("lookup", {"city": "Paris"})]),
        harness.final_turn("Sunny"),
    ]
    options = dict(harness.provider_options)
    if cls is OpenAIHarness:
        options["endpoint"] = "chat.completions"
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=adapter
    ):
        instance = Agent(
            "reasoning-test",
            provider=provider,
            model=model,
            reasoning="high",
            config={
                "max_output_tokens": 16384,
                "retries": 0,
                "provider_options": options,
            },
        )
    log = []
    instance.tools = {tool["function"].__name__: tool for tool in _tools(log)}
    try:
        if entry == "agenerate":
            result = asyncio.run(instance.agenerate("Forecast?", reasoning=level))
        elif entry == "astream":

            async def consume():
                return [
                    event
                    async for event in instance.astream("Forecast?", reasoning=level)
                ]

            events = asyncio.run(consume())
            result = next(event.response for event in events if event.type == "final")
        elif entry == "stream":
            events = list(instance.stream("Forecast?", reasoning=level))
            result = next(event.response for event in events if event.type == "final")
        else:
            result = getattr(instance, entry)("Forecast?", reasoning=level)
        assert (result if isinstance(result, str) else result.content) == "Sunny"
        assert log == [("lookup", "Paris")]
        assert len(harness.requests) == 2
        expected = reasoning_parameters(
            ModelRequest(
                provider=provider,
                model=model,
                messages=[],
                max_output_tokens=16384,
                reasoning=ReasoningConfig(level=level),
            )
        )
        for payload in harness.requests:
            assert (
                native_controls(payload, provider, options.get("endpoint")) == expected
            )
        assert instance.config.reasoning == "high"
        assert instance.conversation_history[-1]["content"] == "Sunny"
        if provider == "cohere":
            transcript = harness.requests[-1]["messages"]
            assert transcript[-2]["content"][0]["type"] == "thinking"
            assert transcript[-1] == {
                "role": "tool",
                "tool_call_id": "call-0",
                "content": "PX-1",
            }
    finally:
        instance.close()


@pytest.mark.parametrize("level", ["none", "low", "medium", "high"])
@pytest.mark.parametrize("shape", ["string", "dict", "model"])
def test_normalization_preserves_levels(level, shape):
    values = {
        "string": level,
        "dict": {"level": level},
        "model": ReasoningConfig(level=level),
    }
    normalized = normalize_reasoning_config(values[shape])
    assert normalized.level == level
    if shape == "model":
        assert normalized is values[shape]


@pytest.mark.parametrize("value", ["minimal", "max", "LOW", "", 5, []])
def test_bad_public_values_are_rejected(value):
    with pytest.raises((TypeError, ValidationError)):
        normalize_reasoning_config(value)


@pytest.mark.parametrize(
    "provider,model",
    [
        ("openai", "gpt-4o"),
        ("openai", "gpt-unknown"),
        ("gemini", "gemini-3.5-flash"),
        ("gemini", "gemini-2.5-pro"),
        ("anthropic", "claude-fable-5"),
        ("cohere", "command-a-03-2025"),
        ("ollama", "llama3"),
        ("lmstudio", "local-model"),
    ],
)
def test_unsupported_none_names_provider_model_and_accepted(provider, model):
    with pytest.raises(ProviderError) as raised:
        reasoning_parameters(
            ModelRequest(
                provider=provider,
                model=model,
                messages=[],
                reasoning=ReasoningConfig(level="none"),
            )
        )
    message = str(raised.value)
    assert provider in message and model in message
    assert "accepted levels:" in message


def test_explicit_effort_overrides_portable_mapping(monkeypatch):
    harness = OpenAIHarness()
    provider = harness.build(monkeypatch)
    request = ModelRequest(
        provider="openai",
        model="gpt-5.4",
        messages=[],
        reasoning=ReasoningConfig(level="low", effort="xhigh"),
        provider_options={"endpoint": "chat.completions"},
    )
    assert provider._chat_completion_params(request)["reasoning_effort"] == "xhigh"
    assert provider._responses_params(request)["reasoning"]["effort"] == "xhigh"
    assert provider._use_responses_api(request) is False


def test_gemini_explicit_budget_unchanged(monkeypatch):
    provider = GeminiHarness().build(monkeypatch)
    request = ModelRequest(
        provider="gemini",
        model="gemini-2.5-flash",
        messages=[],
        reasoning=ReasoningConfig(level="high", budget_tokens=1234),
    )
    payload = provider._build_payload([], None, request=request)
    assert payload["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 1234}


def test_anthropic_budget_requires_output_room():
    with pytest.raises(ProviderError, match="greater than 1024"):
        reasoning_parameters(
            ModelRequest(
                provider="anthropic",
                model="claude-haiku-4-5",
                messages=[],
                max_output_tokens=1000,
                reasoning=ReasoningConfig(level="low"),
            )
        )


def test_dated_profile_and_mapping_are_not_mutated():
    registry = get_provider_registry()
    request = ModelRequest(
        provider="openai",
        model="gpt-5.4-2026-03-05",
        messages=[],
        reasoning=ReasoningConfig(level="low"),
    )
    mapping = reasoning_parameters(request)
    mapping["effort"] = "high"
    assert reasoning_parameters(request) == {"effort": "low"}
    assert registry.get_profile("openai", "gpt-5.4").reasoning_source.startswith(
        "https://"
    )


def test_decorator_reasoning_default_is_forwarded(monkeypatch):
    provider = OpenAIHarness().build(monkeypatch)
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=provider
    ):

        @agent(
            "reasoning-decorated",
            provider="openai",
            model="gpt-5.4",
            reasoning="medium",
            auto_discover_tools=False,
        )
        def decorated(spore):
            return {}

    try:
        assert decorated._praval_agent.config.reasoning == "medium"
    finally:
        decorated._praval_agent.close()


@pytest.mark.parametrize("level", ["none", "low", "medium", "high"])
@pytest.mark.parametrize("use_async", [False, True])
def test_cohere_v2_reasoning_survives_hitl_restart(
    monkeypatch, tmp_path, level, use_async
):
    from praval.core.exceptions import InterventionRequired
    from praval.hitl.service import HITLService
    from praval.model_runtime import ModelRuntime

    harness = V2Harness()
    provider = harness.build(monkeypatch)
    harness.responses = [
        harness.tool_turn([("lookup", {"city": "Paris"})]),
        harness.final_turn("Sunny"),
    ]
    config = AgentConfig(
        provider="cohere",
        model=harness.model,
        reasoning=level,
        max_output_tokens=16384,
        retries=0,
    )
    runtime = ModelRuntime(provider=provider, provider_name="cohere", config=config)
    log = []
    tools = _tools(log)
    tools[0]["requires_approval"] = True
    context = {
        "enabled": True,
        "run_id": "reasoning-resume",
        "agent_name": "reasoner",
        "provider_name": "cohere",
        "db_path": str(tmp_path / "hitl.db"),
    }
    with pytest.raises(InterventionRequired):
        runtime.invoke(
            messages=[{"role": "user", "content": "Forecast?"}],
            tools=tools,
            hitl_context=context,
        )
    assert log == []
    service = HITLService(db_path=context["db_path"])
    pending = service.get_pending_interventions(run_id=context["run_id"])
    decision = service.approve_intervention(pending[0].id, reviewer="qa")
    suspended = service.get_suspended_run(context["run_id"])
    # Persistence is real SQLite; new runtime has no initial response object.
    restarted = ModelRuntime(provider=provider, provider_name="cohere", config=config)
    resume = {**context, "resume_intervention": decision.to_dict()}
    if use_async:
        response = asyncio.run(
            restarted.resume_tool_flow_async(suspended.state, tools, resume)
        )
    else:
        response = restarted.resume_tool_flow(suspended.state, tools, resume)
    assert response.content == "Sunny"
    assert log == [("lookup", "Paris")]
    assert harness.requests[0]["thinking"] == harness.requests[1]["thinking"]
    assert (
        harness.requests[1]["messages"][-2]["content"][0]["thinking"]
        == "private native reasoning"
    )


@pytest.mark.parametrize("use_async", [False, True])
def test_decorator_chat_passes_reasoning_override(monkeypatch, use_async):
    from praval.decorators import _agent_context, achat, chat

    harness = OpenAIHarness()
    harness.model = "gpt-5.4"
    provider = harness.build(monkeypatch)
    harness.responses = [harness.final_turn("answer")]
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=provider
    ):
        instance = Agent(
            "reasoning-chat",
            provider="openai",
            model=harness.model,
            reasoning="high",
            config={"provider_options": {"endpoint": "chat.completions"}},
        )
    previous = _agent_context.agent
    _agent_context.agent = instance
    try:
        result = (
            asyncio.run(achat("Question", reasoning="low"))
            if use_async
            else chat("Question", reasoning="low")
        )
        assert result == "answer"
        assert harness.requests[0]["reasoning_effort"] == "low"
        assert instance.config.reasoning == "high"
    finally:
        _agent_context.agent = previous
        instance.close()


@pytest.mark.parametrize("cls,provider,model,level", CASES)
def test_agent_config_reasoning_defaults_reach_native_payload(
    monkeypatch, cls, provider, model, level
):
    harness = cls()
    harness.model = model
    adapter = harness.build(monkeypatch)
    harness.responses = [harness.final_turn("done")]
    options = dict(harness.provider_options)
    if cls is OpenAIHarness:
        options["endpoint"] = "chat.completions"
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=adapter
    ):
        instance = Agent(
            "reasoning-default",
            provider=provider,
            model=model,
            config={
                "reasoning": {"level": level},
                "max_output_tokens": 16384,
                "provider_options": options,
            },
        )
    try:
        assert instance.chat("Question") == "done"
        expected = reasoning_parameters(
            ModelRequest(
                provider=provider,
                model=model,
                messages=[],
                max_output_tokens=16384,
                reasoning=ReasoningConfig(level=level),
            )
        )
        assert (
            native_controls(harness.requests[0], provider, options.get("endpoint"))
            == expected
        )
        if provider in {"openai", "anthropic"}:
            assert "temperature" not in harness.requests[0]
    finally:
        instance.close()


def test_cohere_v2_explicit_budget_and_mode_unchanged(monkeypatch):
    provider = V2Harness().build(monkeypatch)
    request = ModelRequest(
        provider="cohere",
        model="command-a-reasoning-08-2025",
        messages=[],
        reasoning=ReasoningConfig(budget_tokens=4321, mode="enabled"),
    )
    assert provider._v2_params(request)["thinking"] == {
        "type": "enabled",
        "token_budget": 4321,
    }


def test_anthropic_explicit_budget_and_effort_override(monkeypatch):
    provider = AnthropicHarness().build(monkeypatch)
    request = ModelRequest(
        provider="anthropic",
        model="claude-sonnet-5",
        messages=[],
        reasoning=ReasoningConfig(level="low", effort="high", budget_tokens=5555),
    )
    assert provider._anthropic_thinking(request) == {
        "type": "enabled",
        "budget_tokens": 5555,
    }
    assert provider._anthropic_output_config(request)["effort"] == "high"


def test_local_explicit_effort_never_selects_responses(monkeypatch):
    provider = OpenAICompatibleHarness().build(monkeypatch)
    request = ModelRequest(
        provider="openai-compatible",
        model="local-model",
        messages=[],
        reasoning=ReasoningConfig(effort="high"),
    )
    assert provider._use_responses_api(request) is False
    assert provider._chat_completion_params(request)["reasoning_effort"] == "high"


def test_unknown_model_level_rejected_before_sdk_call(monkeypatch):
    harness = OpenAIHarness()
    harness.model = "gpt-unknown"
    provider = harness.build(monkeypatch)
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=provider
    ):
        instance = Agent("unknown-reasoning", provider="openai", model=harness.model)
    try:
        with pytest.raises(ProviderError, match="gpt-unknown.*accepted levels"):
            instance.generate("Question", reasoning="low")
        assert harness.requests == []
    finally:
        instance.close()


@pytest.mark.parametrize(
    "provider,model,level,expected",
    [
        ("openai", "o3", "low", {"effort": "low"}),
        ("openai", "gpt-5", "high", {"effort": "high"}),
        ("openai", "gpt-5.4", "none", {"effort": "none"}),
        (
            "anthropic",
            "claude-sonnet-5",
            "medium",
            {"thinking": {"type": "adaptive"}, "output_config": {"effort": "medium"}},
        ),
        ("anthropic", "claude-opus-4-8", "none", {"thinking": {"type": "disabled"}}),
        (
            "anthropic",
            "claude-fable-5",
            "high",
            {"thinking": {"type": "adaptive"}, "output_config": {"effort": "high"}},
        ),
        (
            "anthropic",
            "claude-haiku-4-5",
            "low",
            {"thinking": {"type": "enabled", "budget_tokens": 1024}},
        ),
        (
            "anthropic",
            "claude-haiku-4-5",
            "medium",
            {"thinking": {"type": "enabled", "budget_tokens": 4096}},
        ),
        (
            "anthropic",
            "claude-haiku-4-5",
            "high",
            {"thinking": {"type": "enabled", "budget_tokens": 8192}},
        ),
        ("gemini", "gemini-3.1-pro-preview", "medium", {"thinkingLevel": "medium"}),
        ("gemini", "gemini-2.5-flash", "none", {"thinkingBudget": 0}),
        ("gemini", "gemini-2.5-flash", "low", {"thinkingBudget": 1024}),
        ("gemini", "gemini-2.5-flash", "medium", {"thinkingBudget": 4096}),
        ("gemini", "gemini-2.5-flash", "high", {"thinkingBudget": 8192}),
        (
            "cohere",
            "command-a-reasoning-08-2025",
            "none",
            {"thinking": {"type": "disabled"}},
        ),
        (
            "cohere",
            "command-a-reasoning-08-2025",
            "low",
            {"thinking": {"type": "enabled", "token_budget": 512}},
        ),
        (
            "cohere",
            "command-a-reasoning-08-2025",
            "medium",
            {"thinking": {"type": "enabled", "token_budget": 2048}},
        ),
        (
            "cohere",
            "command-a-reasoning-08-2025",
            "high",
            {"thinking": {"type": "enabled", "token_budget": 8192}},
        ),
        ("vllm", "google/gemma-4-26B-A4B-it", "none", {"effort": "none"}),
    ],
)
def test_documented_native_mapping(provider, model, level, expected):
    request = ModelRequest(
        provider=provider,
        model=model,
        messages=[],
        reasoning=ReasoningConfig(level=level),
    )
    assert reasoning_parameters(request) == expected


def test_older_openai_cannot_disable_thinking():
    with pytest.raises(ProviderError, match="o3.*accepted levels: low, medium, high"):
        reasoning_parameters(
            ModelRequest(
                provider="openai",
                model="o3",
                messages=[],
                reasoning=ReasoningConfig(level="none"),
            )
        )


def test_vllm_reasoning_does_not_change_other_local_profiles():
    registry = get_provider_registry()
    assert registry.resolve_capabilities("vllm", "local-model").reasoning is True
    for provider in ("ollama", "lmstudio", "llama-cpp", "openai-compatible"):
        assert registry.resolve_capabilities(provider, "local-model").reasoning is False


def test_constructor_reasoning_overrides_config_without_mutating_it(monkeypatch):
    harness = OpenAIHarness()
    provider = harness.build(monkeypatch)
    supplied = {"reasoning": "high"}
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=provider
    ):
        instance = Agent(
            "constructor-reasoning",
            provider="openai",
            model="gpt-5.4",
            config=supplied,
            reasoning="low",
        )
    try:
        assert instance.config.reasoning == "low"
        assert supplied == {"reasoning": "high"}
    finally:
        instance.close()


def test_cohere_v2_client_is_lazy_and_disables_sdk_retries(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "fake-key")
    client = Mock()
    with (
        patch("praval.providers.cohere.cohere.Client", return_value=Mock()),
        patch(
            "praval.providers.cohere.cohere.ClientV2", return_value=client
        ) as factory,
    ):
        provider = CohereProvider(
            AgentConfig(provider="cohere", model="command-a-reasoning-08-2025")
        )
        factory.assert_not_called()
        assert provider._v2_client() is client
        assert provider._v2_client() is client
        assert factory.call_count == 1
        assert factory.call_args.kwargs["max_retries"] == 0
        provider.close()
        client.close.assert_called_once()


def test_unknown_vllm_model_cannot_promise_disabled_thinking():
    with pytest.raises(ProviderError, match="accepted levels: low, medium, high"):
        reasoning_parameters(
            ModelRequest(
                provider="vllm",
                model="deepseek-r1",
                messages=[],
                reasoning=ReasoningConfig(level="none"),
            )
        )
