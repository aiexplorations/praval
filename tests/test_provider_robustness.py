"""Provider error negotiation, discovery, caching, routing and charged-cost checks."""

import asyncio
import io
import urllib.error
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from praval import Agent
from praval.core.agent import AgentConfig
from praval.core.exceptions import ProviderError, ProviderQuotaError
from praval.models import (
    ModelMessage,
    ModelRequest,
    ProviderProfile,
    ReasoningConfig,
    ToolSpec,
)
from praval.providers.anthropic import AnthropicProvider
from praval.providers.errors import map_gemini_http_error
from praval.providers.openai import OpenAIProvider
from praval.providers.openrouter import OpenRouterProvider
from praval.providers.registry import (
    ProviderRegistry,
    reasoning_parameters,
    register_default_providers,
)


class RejectedParameter(Exception):
    def __init__(
        self, parameter, *, status=400, code="unsupported_parameter", message=None
    ):
        self.status_code = status
        self.body = {
            "param": parameter,
            "code": code,
            "message": message or f"Unsupported parameter: '{parameter}'",
        }
        super().__init__(self.body["message"])


def completion(text="Ready", cost=None):
    usage = {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}
    if cost is not None:
        usage["cost"] = cost
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text, tool_calls=None),
                finish_reason="stop",
            )
        ],
        usage=usage,
    )


@pytest.fixture
def openai_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    with patch("praval.providers.openai.openai.OpenAI", return_value=Mock()):
        return OpenAIProvider(AgentConfig(provider="openai", model="custom-model"))


@pytest.mark.parametrize("endpoint", ["chat.completions", "responses"])
def test_parameter_recovery_is_once_and_remembered_per_model_endpoint(
    openai_provider, endpoint
):
    provider = openai_provider
    create = (
        provider.client.responses.create
        if endpoint == "responses"
        else provider.client.chat.completions.create
    )
    create.side_effect = [RejectedParameter("temperature"), completion(), completion()]
    params = {
        "model": "custom-model",
        "temperature": 0.2,
        "tools": [{"name": "retain"}],
    }
    provider._create_model_request(endpoint, params)
    provider._create_model_request(endpoint, params)
    assert create.call_count == 3
    assert "temperature" in create.call_args_list[0].kwargs
    assert all("temperature" not in call.kwargs for call in create.call_args_list[1:])
    assert all(
        call.kwargs["tools"] == params["tools"] for call in create.call_args_list
    )
    assert "temperature" in params
    assert "temperature" in provider._model_request_params(
        endpoint, {**params, "model": "different"}
    )
    other = "responses" if endpoint == "chat.completions" else "chat.completions"
    assert "temperature" in provider._model_request_params(other, params)


def test_token_parameter_rename_preserves_budget(openai_provider):
    create = openai_provider.client.chat.completions.create
    create.side_effect = [
        RejectedParameter(
            "max_tokens",
            message=(
                "Unsupported parameter: 'max_tokens'. "
                "Use 'max_completion_tokens' instead."
            ),
        ),
        completion(),
    ]
    openai_provider._create_model_request(
        "chat.completions", {"model": "future", "max_tokens": 123}
    )
    assert create.call_args.kwargs == {"model": "future", "max_completion_tokens": 123}


@pytest.mark.parametrize(
    "parameter,status,code",
    [
        ("tools", 400, "unsupported_parameter"),
        ("reasoning_effort", 400, "unsupported_parameter"),
        ("max_tokens", 400, "unsupported_parameter"),
        ("temperature", 429, "unsupported_parameter"),
        ("temperature", 400, "invalid_api_key"),
    ],
)
def test_parameter_recovery_keeps_required_controls_and_other_errors(
    openai_provider, parameter, status, code
):
    create = openai_provider.client.chat.completions.create
    create.side_effect = RejectedParameter(
        parameter,
        status=status,
        code=code,
        message="Invalid request" if code == "invalid_api_key" else None,
    )
    with pytest.raises(RejectedParameter):
        openai_provider._create_model_request(
            "chat.completions", {"model": "future", parameter: 1}
        )
    assert create.call_count == 1


def test_recovery_does_not_repeat_or_learn_failed_repairs(openai_provider):
    create = openai_provider.client.chat.completions.create
    create.side_effect = [RejectedParameter("temperature"), RejectedParameter("top_p")]
    with pytest.raises(RejectedParameter):
        openai_provider._create_model_request(
            "chat.completions", {"model": "future", "temperature": 0.2, "top_p": 0.8}
        )
    assert create.call_count == 2
    assert not openai_provider._parameter_policies


def test_parameter_recovery_failure_and_success_are_both_metered(openai_provider):
    provider = openai_provider
    provider.client.chat.completions.create.side_effect = [
        RejectedParameter("temperature"),
        completion(),
        completion(),
    ]
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=provider
    ):
        with Agent(
            "recover", provider="openai", model="custom-model", config={"retries": 0}
        ) as agent:
            response = agent.generate("Hello")
            assert agent.usage.totals.calls == 2
            assert agent.usage.totals.failed_calls == 1
            assert response.usage.total_tokens == 7
            assert [call["status"] for call in response.metadata["model_calls"]] == [
                "error",
                "ok",
            ]
            agent.generate("Again")
            assert agent.usage.totals.calls == 3


def test_stream_recovery_only_before_stream_opens(openai_provider):
    create = openai_provider.client.chat.completions.create
    chunk = {
        "choices": [{"delta": {"content": "Ready"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
    }
    create.side_effect = [RejectedParameter("temperature"), iter([chunk])]
    with patch(
        "praval.core.agent.ProviderFactory.create_provider",
        return_value=openai_provider,
    ):
        with Agent(
            "recover-stream",
            provider="openai",
            model="custom-model",
            config={"retries": 0},
        ) as agent:
            events = list(agent.stream("Hello"))
            assert [event.delta for event in events if event.type == "delta"] == [
                "Ready"
            ]
            assert agent.usage.totals.calls == 2
            assert agent.usage.totals.total_tokens == 7

    def failing_stream():
        yield chunk
        raise RejectedParameter("top_p")

    create.reset_mock(side_effect=True)
    create.return_value = failing_stream()
    iterator = openai_provider._stream_model_request(
        "chat.completions", {"model": "another", "top_p": 0.8}
    )
    assert next(iterator) == chunk
    with pytest.raises(RejectedParameter):
        next(iterator)
    assert create.call_count == 1


@pytest.mark.parametrize(
    "model,level,thinking",
    [
        ("claude-sonnet-5-5", "none", "between_tools"),
        ("claude-haiku-5-5", "none", "disabled"),
        ("claude-sonnet-5-5", "low", "adaptive"),
        ("claude-haiku-5-5", "high", "adaptive"),
        ("claude-sonnet-5-5-20261008", "low", "adaptive"),
        ("claude-haiku-5-5-20261008", "none", "disabled"),
    ],
)
def test_current_anthropic_profiles_sampling_and_cache_control(
    monkeypatch, model, level, thinking
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    with patch("praval.providers.anthropic.anthropic.Anthropic", return_value=Mock()):
        provider = AnthropicProvider(AgentConfig(provider="anthropic", model=model))
    request = ModelRequest(
        provider="anthropic",
        model=model,
        messages=[ModelMessage(role="user", content="Hello")],
        temperature=0.2,
        reasoning=ReasoningConfig(level=level),
        provider_options={"prompt_caching": {"type": "ephemeral", "ttl": "1h"}},
    )
    params = provider._messages_params(request)
    assert params["thinking"]["type"] == thinking
    assert "temperature" not in params and "prompt_caching" not in params
    assert params["extra_body"]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    request.reasoning = None
    assert "temperature" not in provider._messages_params(request)


@pytest.mark.parametrize(
    "model", ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash"]
)
def test_current_gemini_profiles_have_documented_thinking(model):
    assert reasoning_parameters(
        ModelRequest(
            provider="gemini",
            model=model,
            messages=[],
            reasoning=ReasoningConfig(level="low"),
        )
    ) == {"thinkingLevel": "low"}


def test_gemini_model_not_available_diagnostic():
    error = urllib.error.HTTPError(
        "https://example.test", 404, "Not Found", {}, io.BytesIO(b"{}")
    )
    mapped = map_gemini_http_error(
        error, prefix="Gemini", model="retired", redact=lambda value: value
    )
    assert mapped.status_code == 404
    assert "not available" in str(mapped) and "choose an available model" in str(mapped)
    assert not mapped.retryable


@pytest.fixture
def registry():
    value = ProviderRegistry()
    register_default_providers(value)
    return value


def test_gemini_catalogue_pagination_and_limits(monkeypatch, registry):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    fetch = Mock(
        side_effect=[
            {
                "models": [
                    {
                        "name": "models/gemini-3.8-flash",
                        "inputTokenLimit": 1000000,
                        "outputTokenLimit": 65536,
                        "supportedGenerationMethods": ["generateContent"],
                    }
                ],
                "nextPageToken": "a/b",
            },
            {
                "models": [
                    {
                        "name": "models/embedding",
                        "supportedGenerationMethods": ["embedContent"],
                    }
                ]
            },
        ]
    )
    with patch("praval.providers.catalog.fetch_json", fetch):
        profiles = registry.discover_models("gemini", AgentConfig(provider="gemini"))
    assert len(profiles) == 1
    assert profiles[0].context_window == 1000000
    assert profiles[0].max_output_tokens == 65536
    assert profiles[0].reasoning_levels["low"] == {"thinkingLevel": "low"}
    assert "pageToken=a%2Fb" in fetch.call_args.args[0]


def test_ollama_catalogue_declared_capabilities_and_loaded_context(
    monkeypatch, registry, caplog
):
    fetch = Mock(
        side_effect=[
            {"models": [{"name": "qwen3.5:9b"}]},
            {"models": [{"name": "qwen3.5:9b", "context_length": 4096}]},
            {
                "capabilities": ["completion", "tools", "vision", "thinking"],
                "model_info": {"qwen3.context_length": 262144},
            },
        ]
    )
    config = AgentConfig(
        provider="ollama",
        model="qwen3.5:9b",
        provider_options={"required_context_tokens": 16000},
    )
    with patch("praval.providers.catalog.fetch_json", fetch):
        profiles = registry.discover_models("ollama", config)
    assert profiles[0].capabilities.tools and profiles[0].capabilities.reasoning
    assert profiles[0].context_window == 262144
    assert profiles[0].metadata["loaded_context_window"] == 4096
    assert profiles[0].pricing["cost"] == "0"
    assert "Configure num_ctx" in caplog.text
    assert registry.resolve_capabilities("ollama", "qwen3.5:9b").tools


def test_openrouter_public_catalogue_preserves_ids_prices_and_capabilities(registry):
    fetch = Mock(
        return_value={
            "data": [
                {
                    "id": "vendor/model:free",
                    "name": "A model",
                    "context_length": 100000,
                    "top_provider": {"max_completion_tokens": 8192},
                    "supported_parameters": ["tools", "reasoning", "response_format"],
                    "pricing": {"prompt": "0.000001", "completion": "0.000002"},
                }
            ]
        }
    )
    with patch("praval.providers.catalog.fetch_json", fetch):
        profiles = registry.discover_models(
            "openrouter", AgentConfig(provider="openrouter")
        )
    assert profiles[0].model == "vendor/model:free"
    assert profiles[0].max_output_tokens == 8192 and profiles[0].capabilities.tools
    assert profiles[0].pricing["prompt"] == "0.000001"
    assert registry.get_profile("openrouter", "vendor/model:free") is profiles[0]


@pytest.mark.parametrize("use_async", [False, True])
def test_openrouter_routing_reasoning_and_actual_cost_across_rounds(
    monkeypatch, use_async
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-key")
    client = Mock()
    with patch(
        "praval.providers.openai_compatible.openai.OpenAI", return_value=client
    ) as constructor:
        provider = OpenRouterProvider(
            AgentConfig(
                provider="openrouter",
                model="vendor/model:variant",
                provider_options={
                    "http_referer": "https://app.test",
                    "app_title": "Praval",
                },
            )
        )
    assert (
        constructor.call_args.kwargs["default_headers"]["HTTP-Referer"]
        == "https://app.test"
    )
    first = completion(cost=0.03)
    first.choices[0].message.tool_calls = [
        {
            "id": "call-1",
            "type": "function",
            "function": {"name": "lookup", "arguments": "{}"},
        }
    ]
    first.choices[0].message.reasoning_details = [
        {"type": "reasoning.encrypted", "data": "opaque"}
    ]
    client.chat.completions.create.side_effect = [first, completion(cost=0.02)]
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=provider
    ):
        with Agent(
            "router",
            provider="openrouter",
            model="vendor/model:variant",
            reasoning="low",
            config={"retries": 0},
        ) as agent:
            agent.add_tool_spec(ToolSpec(name="lookup"), lambda: "found")
            options = {
                "provider_options": {
                    "routing": {"only": ["chosen"], "require_parameters": False}
                }
            }
            response = (
                asyncio.run(agent.agenerate("Find", **options))
                if use_async
                else agent.generate("Find", **options)
            )
            assert agent.usage.totals.reported_cost_usd == pytest.approx(0.05)
    assert response.metadata["reported_cost"]["amount"] == pytest.approx(0.05)
    assert response.metadata["reported_cost"]["complete"]
    for call in client.chat.completions.create.call_args_list:
        assert call.kwargs["model"] == "vendor/model:variant"
        assert call.kwargs["extra_body"]["provider"] == {
            "only": ["chosen"],
            "require_parameters": True,
        }
        assert call.kwargs["extra_body"]["reasoning"] == {"effort": "low"}
        assert "reasoning_effort" not in call.kwargs and "max_tokens" in call.kwargs
    assert (
        client.chat.completions.create.call_args.kwargs["messages"][-2][
            "reasoning_details"
        ]
        == first.choices[0].message.reasoning_details
    )
    assert isinstance(
        provider.map_provider_error(RejectedParameter("x", status=402)),
        ProviderQuotaError,
    )


def test_openrouter_qualified_model_name_and_variant_are_distinct():
    config = AgentConfig(model="openrouter:vendor/model:free")
    assert config.provider == "openrouter" and config.model == "vendor/model:free"
    config = AgentConfig(model="vendor/model:free")
    assert config.provider is None and config.model == "vendor/model:free"


def test_discovered_output_limit_rejects_before_dispatch(
    monkeypatch, registry, openai_provider
):
    monkeypatch.setattr("praval.providers.registry._global_registry", registry)
    registry.register_profile(
        ProviderProfile(
            provider="openai",
            model="custom-model",
            max_output_tokens=100,
            capabilities=openai_provider.capabilities,
        )
    )
    with patch(
        "praval.core.agent.ProviderFactory.create_provider",
        return_value=openai_provider,
    ):
        with Agent(
            "too-large",
            provider="openai",
            model="custom-model",
            config={"max_output_tokens": 101},
        ) as agent:
            with pytest.raises(ProviderError, match="exceeds its discovered limit 100"):
                agent.generate("Hello")
    openai_provider.client.chat.completions.create.assert_not_called()


def test_temperature_none_omits_sampling_instead_of_sending_null(openai_provider):
    assert AgentConfig(temperature=None).temperature is None
    request = ModelRequest(
        provider="openai", model="custom-model", messages=[], temperature=None
    )
    assert "temperature" not in openai_provider._chat_completion_params(request)
    assert "temperature" not in openai_provider._responses_params(request)


def test_parameter_recovery_can_be_disabled_and_cache_is_bounded(openai_provider):
    openai_provider.config.provider_options = {"parameter_recovery": False}
    assert (
        openai_provider._parameter_repair(
            RejectedParameter("temperature"), {"temperature": 0.2}
        )
        is None
    )
    for index in range(150):
        openai_provider._remember_parameter_policy(
            "responses", {"model": str(index)}, {"temperature": None}
        )
    assert len(openai_provider._parameter_policies) == 128
    assert ("responses", "0") not in openai_provider._parameter_policies


def test_ollama_discovery_at_construction_enables_declared_tools(monkeypatch, registry):
    fetch = Mock(
        side_effect=[
            {"models": [{"name": "qwen:latest"}]},
            {"models": []},
            {"capabilities": ["tools"], "model_info": {"qwen.context_length": 32768}},
        ]
    )
    config = AgentConfig(
        provider="ollama", model="qwen", provider_options={"discover_model": True}
    )
    with (
        patch("praval.providers.catalog.fetch_json", fetch),
        patch("praval.providers.openai_compatible.openai.OpenAI", return_value=Mock()),
    ):
        provider = registry.create_provider("ollama", config)
    assert registry.resolve_capabilities("ollama", "qwen").tools
    assert provider.base_url == "http://localhost:11434/v1"
    provider.close()


def test_openrouter_stream_reports_actual_charge(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-key")
    with patch("praval.providers.openai_compatible.openai.OpenAI", return_value=Mock()):
        provider = OpenRouterProvider(
            AgentConfig(provider="openrouter", model="vendor/model")
        )
    provider.client.chat.completions.create.return_value = iter(
        [
            {"choices": [{"delta": {"content": "Ready"}}]},
            {
                "choices": [],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 2,
                    "total_tokens": 7,
                    "cost": 0.04,
                },
            },
        ]
    )
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=provider
    ):
        with Agent(
            "router-stream", provider="openrouter", model="vendor/model"
        ) as agent:
            events = list(agent.stream("Hello"))
            assert agent.usage.totals.reported_cost_usd == pytest.approx(0.04)
    final = next(event.response for event in events if event.type == "final")
    assert final.metadata["reported_cost"]["amount"] == pytest.approx(0.04)


def test_per_call_parameter_recovery_override_is_not_sent_to_sdk(openai_provider):
    openai_provider.client.chat.completions.create.side_effect = RejectedParameter(
        "temperature"
    )
    request = ModelRequest(
        provider="openai",
        model="custom-model",
        messages=[],
        temperature=0.2,
        provider_options={"parameter_recovery": False},
    )
    with pytest.raises(RejectedParameter):
        openai_provider.invoke(request)
    create = openai_provider.client.chat.completions.create
    assert create.call_count == 1
    assert "_praval_parameter_recovery" not in create.call_args.kwargs


def test_openrouter_preserves_extra_body_and_enforces_routing(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-key")
    with patch("praval.providers.openai_compatible.openai.OpenAI", return_value=Mock()):
        provider = OpenRouterProvider(
            AgentConfig(provider="openrouter", model="vendor/model")
        )
    params = provider._chat_completion_params(
        ModelRequest(
            provider="openrouter",
            model="vendor/model",
            messages=[],
            provider_options={
                "extra_body": {
                    "provider": {"only": ["chosen"], "require_parameters": False},
                    "plugins": [{"id": "response-healing"}],
                }
            },
        )
    )
    assert params["extra_body"]["provider"] == {
        "only": ["chosen"],
        "require_parameters": True,
    }
    assert params["extra_body"]["plugins"] == [{"id": "response-healing"}]


@pytest.mark.parametrize("scope", ["config", "request"])
def test_disabled_parameter_recovery_bypasses_learned_policy(openai_provider, scope):
    provider = openai_provider
    provider._remember_parameter_policy(
        "chat.completions", {"model": "custom-model"}, {"temperature": None}
    )
    params = {"model": "custom-model", "temperature": 0.2}
    if scope == "config":
        provider.config.provider_options = {"parameter_recovery": False}
    else:
        params["_praval_parameter_recovery"] = False
    assert provider._model_request_params("chat.completions", params) == {
        "model": "custom-model",
        "temperature": 0.2,
    }


@pytest.mark.parametrize("payload", [b"not json", b"[]", b"x" * 17])
def test_catalogue_fetch_checks_size_and_json(payload):
    from praval.providers.catalog import fetch_json

    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = payload
    with (
        patch("praval.providers.catalog.urllib.request.urlopen", return_value=response),
        patch("praval.providers.catalog.MAX_CATALOG_BYTES", 16),
    ):
        with pytest.raises(ProviderError, match="catalogue"):
            fetch_json("https://example.test/models", headers={}, timeout=1)
    response.read.assert_called_once_with(17)


def test_catalogue_http_errors_are_typed_and_do_not_expose_credentials():
    from praval.providers.catalog import fetch_json

    error = urllib.error.HTTPError(
        "https://example.test/models",
        402,
        "credits secret",
        {},
        io.BytesIO(b'{"error":{"message":"secret","code":"insufficient_quota"}}'),
    )
    with patch("praval.providers.catalog.urllib.request.urlopen", side_effect=error):
        with pytest.raises(ProviderQuotaError) as caught:
            fetch_json(
                "https://example.test/models",
                headers={"Authorization": "Bearer secret"},
                timeout=1,
            )
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize(
    "provider,payload",
    [
        ("ollama", {"models": {}}),
        ("openrouter", {"data": [{"id": "vendor/model", "pricing": []}]}),
        ("openrouter", {"data": [{"id": "vendor/model", "supported_parameters": {}}]}),
    ],
)
def test_catalogue_malformed_metadata_has_provider_error(registry, provider, payload):
    # A nonempty wrong-shaped price mapping fails instead of an AttributeError.
    if provider == "openrouter" and payload["data"][0].get("pricing") == []:
        payload["data"][0]["pricing"] = [1]
    with patch("praval.providers.catalog.fetch_json", return_value=payload):
        with pytest.raises(ProviderError, match="catalogue"):
            registry.discover_models(provider, AgentConfig(provider=provider))


def test_anthropic_catalogue_auth_pagination_and_dated_reasoning(monkeypatch, registry):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    fetch = Mock(
        side_effect=[
            {
                "data": [
                    {"id": "claude-sonnet-5-5-20261008", "display_name": "Sonnet"}
                ],
                "has_more": True,
                "last_id": "model/id",
            },
            {"data": [], "has_more": False},
        ]
    )
    with patch("praval.providers.catalog.fetch_json", fetch):
        profiles = registry.discover_models(
            "anthropic", AgentConfig(provider="anthropic")
        )
    assert profiles[0].model == "claude-sonnet-5-5-20261008"
    assert profiles[0].reasoning_levels["low"]["thinking"]["type"] == "adaptive"
    assert fetch.call_args.kwargs["headers"]["x-api-key"] == "secret"
    assert "after_id=model%2Fid" in fetch.call_args.args[0]
