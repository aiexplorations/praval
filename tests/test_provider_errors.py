"""Typed provider errors: classes, SDK/HTTP mapping and SDK retry settings."""

import io
import json
import pickle
import urllib.error
from datetime import datetime, timedelta, timezone
from email.message import Message
from email.utils import format_datetime
from unittest.mock import Mock, patch

import anthropic
import cohere
import httpx
import openai
import pytest
from cohere.core.api_error import ApiError

from praval import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderTransportError,
    ProviderUnavailableError,
    ToolRoundLimitError,
)
from praval.core.agent import AgentConfig
from praval.model_runtime import ModelRuntime
from praval.models import ModelMessage, ModelRequest
from praval.providers.anthropic import AnthropicProvider
from praval.providers.cohere import CohereProvider
from praval.providers.errors import (
    error_class_for_status,
    map_provider_exception,
    parse_retry_after,
    sdk_max_retries,
)
from praval.providers.gemini import GeminiProvider
from praval.providers.openai import OpenAIProvider
from praval.providers.openai_compatible import OpenAICompatibleProvider

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
# Newer anthropic SDKs build errors from httpx2 objects, older ones from httpx.
ANTHROPIC_HTTP = getattr(anthropic._exceptions, "httpx2", httpx)


def _request(model="test-model"):
    return ModelRequest(
        model=model, messages=[ModelMessage(role="user", content="question")]
    )


def _openai_status_error(cls, status, body, headers=None):
    response = httpx.Response(
        status,
        headers=headers or {},
        request=httpx.Request("POST", OPENAI_URL),
    )
    return cls(f"Error code: {status} - {body}", response=response, body=body)


def _anthropic_status_error(cls, status, error_type, headers=None):
    body = {"type": "error", "error": {"type": error_type, "message": "failed"}}
    response = ANTHROPIC_HTTP.Response(
        status,
        headers=headers or {},
        request=ANTHROPIC_HTTP.Request("POST", ANTHROPIC_URL),
    )
    return cls(f"Error code: {status} - {body}", response=response, body=body)


@pytest.fixture
def openai_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-openai")
    client = Mock()
    with patch("praval.providers.openai.openai.OpenAI", return_value=client) as ctor:
        provider = OpenAIProvider(AgentConfig(provider="openai", model="gpt-test"))
    return provider, client, ctor


@pytest.fixture
def anthropic_provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")
    client = Mock()
    with patch(
        "praval.providers.anthropic.anthropic.Anthropic", return_value=client
    ) as ctor:
        provider = AnthropicProvider(
            AgentConfig(provider="anthropic", model="claude-test")
        )
    return provider, client, ctor


@pytest.fixture
def cohere_provider(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "co-secret")
    client = Mock()
    with patch("praval.providers.cohere.cohere.Client", return_value=client) as ctor:
        provider = CohereProvider(AgentConfig(provider="cohere", model="command-test"))
    return provider, client, ctor


@pytest.fixture
def gemini_provider(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-secret-gemini")
    return GeminiProvider(AgentConfig(provider="gemini", model="gemini-test"))


# --- Exception classes ---------------------------------------------------


def test_provider_error_keeps_positional_message_and_defaults():
    error = ProviderError("plain failure")
    assert str(error) == "plain failure"
    assert error.args == ("plain failure",)
    assert error.retryable is False
    assert error.provider is None and error.status_code is None
    assert error.retry_after_seconds is None


@pytest.mark.parametrize(
    ("error_class", "retryable"),
    [
        (ProviderAuthenticationError, False),
        (ProviderInvalidRequestError, False),
        (ProviderQuotaError, False),
        (ProviderRateLimitError, True),
        (ProviderUnavailableError, True),
        (ProviderTransportError, True),
        (ToolRoundLimitError, False),
    ],
)
def test_subclasses_have_retry_defaults_and_are_provider_errors(error_class, retryable):
    error = error_class("failed")
    assert error.retryable is retryable
    with pytest.raises(ProviderError, match="failed"):
        raise error


def test_explicit_retryable_overrides_class_default():
    assert ProviderRateLimitError("x", retryable=False).retryable is False
    assert ProviderError("x", retryable=True).retryable is True


def test_tool_round_limit_error_is_never_retryable_and_keeps_limit():
    error = ToolRoundLimitError("too many", limit=3, provider="p", model="m")
    assert error.retryable is False
    assert (error.limit, error.provider, error.model) == (3, "p", "m")


def test_provider_errors_round_trip_through_pickle_with_fields():
    error = ProviderRateLimitError(
        "slow down",
        provider="openai",
        model="gpt",
        operation="invoke",
        status_code=429,
        error_code="rate_limit_exceeded",
        request_id="req_1",
        retry_after_seconds=2.5,
    )
    restored = pickle.loads(pickle.dumps(error))
    assert type(restored) is ProviderRateLimitError
    assert str(restored) == "slow down"
    assert vars(restored) == vars(error)
    limit = pickle.loads(pickle.dumps(ToolRoundLimitError("limit", limit=4)))
    assert limit.limit == 4 and limit.retryable is False


# --- Generic helpers -----------------------------------------------------


def test_parse_retry_after_accepts_seconds_milliseconds_and_dates():
    assert parse_retry_after({"retry-after": "3"}) == 3.0
    assert parse_retry_after({"retry-after-ms": "1500", "retry-after": "9"}) == 1.5
    assert parse_retry_after({"Retry-After": "4"}) == 4.0
    future = datetime.now(timezone.utc) + timedelta(seconds=30)
    parsed = parse_retry_after({"retry-after": format_datetime(future, usegmt=True)})
    assert parsed is not None and 25 <= parsed <= 31
    past = datetime.now(timezone.utc) - timedelta(seconds=30)
    assert parse_retry_after({"retry-after": format_datetime(past, usegmt=True)}) == 0
    assert parse_retry_after({"retry-after": "soon"}) is None
    assert parse_retry_after({"retry-after": "nan"}) is None
    assert parse_retry_after({"retry-after-ms": "bad"}) is None
    assert parse_retry_after({}) is None
    assert parse_retry_after(None) is None


@pytest.mark.parametrize(
    ("status", "code", "expected"),
    [
        (400, None, ProviderInvalidRequestError),
        (401, None, ProviderAuthenticationError),
        (402, None, ProviderQuotaError),
        (403, None, ProviderAuthenticationError),
        (404, None, ProviderInvalidRequestError),
        (408, None, ProviderTransportError),
        (409, None, ProviderUnavailableError),
        (413, None, ProviderInvalidRequestError),
        (422, None, ProviderInvalidRequestError),
        (429, None, ProviderRateLimitError),
        (429, "insufficient_quota", ProviderQuotaError),
        (500, None, ProviderUnavailableError),
        (503, None, ProviderUnavailableError),
        (529, None, ProviderUnavailableError),
        (None, "rate_limit_error", ProviderRateLimitError),
        (None, "overloaded_error", ProviderUnavailableError),
        (None, "something", ProviderError),
        (302, None, ProviderError),
    ],
)
def test_error_class_for_status(status, code, expected):
    assert error_class_for_status(status, error_code=code) is expected


def test_unrecognised_exception_maps_to_plain_non_retryable_error():
    error = map_provider_exception(RuntimeError("boom"), provider="x")
    assert type(error) is ProviderError
    assert str(error) == "boom"
    assert error.retryable is False and error.provider == "x"


def test_builtin_connection_failures_map_to_transport_errors():
    assert isinstance(
        map_provider_exception(ConnectionResetError("reset")), ProviderTransportError
    )
    assert isinstance(map_provider_exception(TimeoutError()), ProviderTransportError)
    assert isinstance(
        map_provider_exception(urllib.error.URLError("offline")),
        ProviderTransportError,
    )


def test_existing_provider_error_is_kept_or_reworded_with_same_type():
    original = ProviderRateLimitError("slow", status_code=429)
    assert map_provider_exception(original, provider="p") is original
    assert original.provider == "p"
    reworded = map_provider_exception(original, message="Adapter: slow")
    assert reworded is not original
    assert type(reworded) is ProviderRateLimitError
    assert str(reworded) == "Adapter: slow" and reworded.status_code == 429
    assert str(original) == "slow"


def test_x_should_retry_header_overrides_status_policy():
    error = _openai_status_error(
        openai.BadRequestError,
        400,
        {"message": "transient", "type": "x"},
        headers={"x-should-retry": "true"},
    )
    mapped = map_provider_exception(error)
    assert isinstance(mapped, ProviderInvalidRequestError)
    assert mapped.retryable is True
    error = _openai_status_error(
        openai.InternalServerError,
        500,
        {"message": "fatal"},
        headers={"x-should-retry": "false"},
    )
    assert map_provider_exception(error).retryable is False


def test_sdk_max_retries_defaults_to_zero_and_accepts_overrides():
    assert sdk_max_retries(AgentConfig()) == 0
    assert sdk_max_retries(AgentConfig(provider_options={"max_retries": 3})) == 3
    assert sdk_max_retries(Mock(max_retries=4, provider_options={})) == 4
    with pytest.raises(ProviderError, match="non-negative"):
        sdk_max_retries(AgentConfig(provider_options={"max_retries": -1}))
    with pytest.raises(ProviderError, match="non-negative"):
        sdk_max_retries(AgentConfig(provider_options={"max_retries": True}))


# --- OpenAI --------------------------------------------------------------


def test_openai_client_disables_sdk_retries_unless_configured(
    monkeypatch, openai_provider
):
    _, _, ctor = openai_provider
    assert ctor.call_args.kwargs["max_retries"] == 0
    with patch("praval.providers.openai.openai.OpenAI") as configured:
        provider = OpenAIProvider(
            AgentConfig(provider="openai", provider_options={"max_retries": 2})
        )
    assert configured.call_args.kwargs["max_retries"] == 2
    params = provider._chat_completion_params(_request())
    assert "max_retries" not in params


def test_openai_rate_limit_maps_with_retry_after_and_request_id(openai_provider):
    provider, _, _ = openai_provider
    error = _openai_status_error(
        openai.RateLimitError,
        429,
        {"message": "Rate limit reached", "type": "requests", "code": "rate_limit"},
        headers={"retry-after": "3", "x-request-id": "req_openai_1"},
    )
    mapped = provider.map_provider_error(error)
    assert isinstance(mapped, ProviderRateLimitError)
    assert mapped.retryable is True
    assert mapped.status_code == 429
    assert mapped.retry_after_seconds == 3.0
    assert mapped.request_id == "req_openai_1"
    assert mapped.error_code == "rate_limit"
    assert mapped.provider == "openai" and mapped.model == "gpt-test"


def test_openai_insufficient_quota_is_a_quota_error(openai_provider):
    provider, _, _ = openai_provider
    error = _openai_status_error(
        openai.RateLimitError,
        429,
        {
            "message": "You exceeded your current quota",
            "type": "insufficient_quota",
            "code": "insufficient_quota",
        },
    )
    mapped = provider.map_provider_error(error)
    assert isinstance(mapped, ProviderQuotaError)
    assert mapped.retryable is False
    assert mapped.error_code == "insufficient_quota"


@pytest.mark.parametrize(
    ("cls", "status", "expected"),
    [
        (openai.AuthenticationError, 401, ProviderAuthenticationError),
        (openai.PermissionDeniedError, 403, ProviderAuthenticationError),
        (openai.BadRequestError, 400, ProviderInvalidRequestError),
        (openai.NotFoundError, 404, ProviderInvalidRequestError),
        (openai.UnprocessableEntityError, 422, ProviderInvalidRequestError),
        (openai.InternalServerError, 500, ProviderUnavailableError),
        (openai.InternalServerError, 503, ProviderUnavailableError),
    ],
)
def test_openai_status_errors_map_by_status(openai_provider, cls, status, expected):
    provider, _, _ = openai_provider
    mapped = provider.map_provider_error(
        _openai_status_error(cls, status, {"message": "failed"})
    )
    assert type(mapped) is expected
    assert mapped.status_code == status


def test_openai_connection_and_timeout_errors_are_transport_errors(openai_provider):
    provider, _, _ = openai_provider
    request = httpx.Request("POST", OPENAI_URL)
    for error in (
        openai.APIConnectionError(request=request),
        openai.APITimeoutError(request=request),
    ):
        mapped = provider.map_provider_error(error)
        assert isinstance(mapped, ProviderTransportError)
        assert mapped.retryable is True
        assert mapped.status_code is None


def test_openai_error_messages_are_redacted(openai_provider):
    provider, client, _ = openai_provider
    error = _openai_status_error(
        openai.AuthenticationError,
        401,
        {"message": "Incorrect API key provided: sk-secret-openai"},
    )
    mapped = provider.map_provider_error(error)
    assert "sk-secret-openai" not in str(mapped)
    client.chat.completions.create.side_effect = error
    with pytest.raises(ProviderAuthenticationError, match="OpenAI API error") as info:
        provider.generate([{"role": "user", "content": "x"}])
    assert "sk-secret-openai" not in str(info.value)
    assert info.value.__cause__ is error


def test_openai_stream_error_event_then_typed_error(openai_provider):
    provider, client, _ = openai_provider
    client.chat.completions.create.side_effect = _openai_status_error(
        openai.RateLimitError, 429, {"message": "slow"}, headers={"retry-after": "1"}
    )
    stream = provider.stream(_request())
    assert next(stream).type == "error"
    with pytest.raises(ProviderRateLimitError, match="OpenAI streaming error") as info:
        next(stream)
    assert info.value.retry_after_seconds == 1.0


def test_openai_compatible_client_disables_sdk_retries():
    with patch("praval.providers.openai_compatible.openai.OpenAI") as ctor:
        OpenAICompatibleProvider(AgentConfig(provider="ollama", model="llama"))
    assert ctor.call_args.kwargs["max_retries"] == 0
    with patch("praval.providers.openai_compatible.openai.OpenAI") as ctor:
        OpenAICompatibleProvider(
            AgentConfig(
                provider="ollama", model="llama", provider_options={"max_retries": 5}
            )
        )
    assert ctor.call_args.kwargs["max_retries"] == 5


# --- Anthropic -----------------------------------------------------------


def test_anthropic_client_disables_sdk_retries_and_reserves_option(anthropic_provider):
    _, _, ctor = anthropic_provider
    assert ctor.call_args.kwargs["max_retries"] == 0
    with patch("praval.providers.anthropic.anthropic.Anthropic") as configured:
        provider = AnthropicProvider(
            AgentConfig(provider="anthropic", provider_options={"max_retries": 1})
        )
    assert configured.call_args.kwargs["max_retries"] == 1
    request = _request("claude-test").model_copy(
        update={"provider_options": {"max_retries": 1}}
    )
    assert "max_retries" not in provider._messages_params(request)


def test_anthropic_overloaded_maps_to_retryable_unavailable(anthropic_provider):
    provider, _, _ = anthropic_provider
    error = _anthropic_status_error(
        anthropic.OverloadedError, 529, "overloaded_error", {"request-id": "req_ant_1"}
    )
    mapped = provider.map_provider_error(error)
    assert isinstance(mapped, ProviderUnavailableError)
    assert mapped.retryable is True
    assert mapped.status_code == 529
    assert mapped.error_code == "overloaded_error"
    assert mapped.request_id == "req_ant_1"
    assert mapped.provider == "anthropic"


@pytest.mark.parametrize(
    ("cls", "status", "error_type", "expected"),
    [
        (
            anthropic.RateLimitError,
            429,
            "rate_limit_error",
            ProviderRateLimitError,
        ),
        (
            anthropic.AuthenticationError,
            401,
            "authentication_error",
            ProviderAuthenticationError,
        ),
        (
            anthropic.PermissionDeniedError,
            403,
            "permission_error",
            ProviderAuthenticationError,
        ),
        (
            anthropic.BadRequestError,
            400,
            "invalid_request_error",
            ProviderInvalidRequestError,
        ),
        (anthropic.NotFoundError, 404, "not_found_error", ProviderInvalidRequestError),
        (anthropic.InternalServerError, 500, "api_error", ProviderUnavailableError),
    ],
)
def test_anthropic_status_errors_map_by_status(
    anthropic_provider, cls, status, error_type, expected
):
    provider, _, _ = anthropic_provider
    mapped = provider.map_provider_error(
        _anthropic_status_error(cls, status, error_type, {"retry-after": "2"})
    )
    assert type(mapped) is expected
    assert mapped.error_code == error_type
    assert mapped.retry_after_seconds == 2.0


def test_anthropic_connection_errors_are_transport_errors(anthropic_provider):
    provider, client, _ = anthropic_provider
    request = ANTHROPIC_HTTP.Request("POST", ANTHROPIC_URL)
    mapped = provider.map_provider_error(anthropic.APIConnectionError(request=request))
    assert isinstance(mapped, ProviderTransportError)
    client.messages.create.side_effect = anthropic.APITimeoutError(request=request)
    with pytest.raises(ProviderTransportError, match="Anthropic API error"):
        provider.generate([{"role": "user", "content": "x"}])


# --- Cohere --------------------------------------------------------------


def test_cohere_client_without_max_retries_keyword_is_still_built(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "co-secret")
    built = {}

    class OldCohereClient:
        def __init__(self, api_key, timeout=120):
            built["api_key"] = api_key

    with patch("praval.providers.cohere.cohere.Client", OldCohereClient):
        provider = CohereProvider(AgentConfig(provider="cohere"))
    assert isinstance(provider.client, OldCohereClient)
    assert built == {"api_key": "co-secret"}


def test_cohere_client_disables_sdk_retries_and_reserves_option(cohere_provider):
    provider, _, ctor = cohere_provider
    assert ctor.call_args.kwargs["max_retries"] == 0
    request = _request("command-test").model_copy(
        update={"provider_options": {"max_retries": 2}}
    )
    assert "max_retries" not in provider._request_chat_params(request)


def test_cohere_sdk_errors_map_to_typed_errors(cohere_provider):
    provider, client, _ = cohere_provider
    rate_limited = cohere.errors.TooManyRequestsError(
        body={"message": "trial key limit"}, headers={"retry-after": "4"}
    )
    mapped = provider.map_provider_error(rate_limited)
    assert isinstance(mapped, ProviderRateLimitError)
    assert mapped.retry_after_seconds == 4.0
    assert str(mapped) == "HTTP 429: trial key limit"
    assert mapped.provider == "cohere"

    unauthorized = cohere.errors.UnauthorizedError(
        body={"message": "invalid api token"}
    )
    assert isinstance(
        provider.map_provider_error(unauthorized), ProviderAuthenticationError
    )
    unavailable = ApiError(status_code=503, body="upstream down")
    assert isinstance(
        provider.map_provider_error(unavailable), ProviderUnavailableError
    )
    assert isinstance(
        provider.map_provider_error(httpx.ConnectTimeout("timed out")),
        ProviderTransportError,
    )

    client.chat.side_effect = rate_limited
    with pytest.raises(ProviderRateLimitError, match="Cohere API error"):
        provider.generate([{"role": "user", "content": "x"}])


# --- Gemini --------------------------------------------------------------


def _gemini_http_error(status, payload, headers=None):
    message = Message()
    for key, value in (headers or {}).items():
        message[key] = value
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return urllib.error.HTTPError(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:"
        "generateContent?key=AIza-secret-gemini",
        status,
        "Error",
        message,
        io.BytesIO(body),
    )


def test_gemini_http_error_body_is_preserved_and_redacted(gemini_provider):
    error = _gemini_http_error(
        400,
        {
            "error": {
                "code": 400,
                "message": "API key not valid: AIza-secret-gemini",
                "status": "INVALID_ARGUMENT",
            }
        },
    )
    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(ProviderInvalidRequestError) as info:
            gemini_provider.invoke(_request("gemini-test"))
    mapped = info.value
    assert str(mapped) == (
        "Gemini API error: HTTP 400 INVALID_ARGUMENT: API key not valid: ***"
    )
    assert mapped.status_code == 400
    assert mapped.error_code == "INVALID_ARGUMENT"
    assert mapped.provider == "gemini" and mapped.model == "gemini-test"
    assert mapped.retryable is False
    assert "AIza-secret-gemini" not in repr(vars(mapped))


def test_gemini_rate_limit_uses_retry_info_delay(gemini_provider):
    error = _gemini_http_error(
        429,
        {
            "error": {
                "code": 429,
                "message": "Quota exceeded for requests per minute",
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [
                            {
                                "quotaId": "GenerateRequestsPerMinutePerProject",
                                "quotaMetric": "generate_requests",
                            }
                        ],
                    },
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "7s",
                    },
                ],
            }
        },
    )
    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(ProviderRateLimitError) as info:
            gemini_provider.invoke(_request("gemini-test"))
    assert info.value.retryable is True
    assert info.value.retry_after_seconds == 7.0
    assert info.value.error_code == "RESOURCE_EXHAUSTED"


def test_gemini_retry_after_header_wins_over_retry_info(gemini_provider):
    error = _gemini_http_error(
        429,
        {
            "error": {
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "7s",
                    }
                ],
            }
        },
        headers={"Retry-After": "2"},
    )
    mapped = gemini_provider._provider_error(error, "Gemini API error")
    assert isinstance(mapped, ProviderRateLimitError)
    assert mapped.retry_after_seconds == 2.0


@pytest.mark.parametrize(
    "details",
    [
        [
            {
                "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [{"quotaId": "GenerateRequestsPerDayPerProject"}],
            },
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "3s"},
        ],
        [
            {
                "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [{"quotaMetric": "tokens"}],
            }
        ],
    ],
)
def test_gemini_exhausted_quota_is_not_retryable(gemini_provider, details):
    error = _gemini_http_error(
        429,
        {
            "error": {
                "message": "Quota exceeded",
                "status": "RESOURCE_EXHAUSTED",
                "details": details,
            }
        },
    )
    mapped = gemini_provider._provider_error(error, "Gemini API error")
    assert isinstance(mapped, ProviderQuotaError)
    assert mapped.retryable is False


def test_gemini_unavailable_non_json_body_and_transport_errors(gemini_provider):
    unavailable = gemini_provider._provider_error(
        _gemini_http_error(503, {"error": {"status": "UNAVAILABLE", "message": "x"}}),
        "Gemini API error",
    )
    assert isinstance(unavailable, ProviderUnavailableError)
    raw = gemini_provider._provider_error(
        _gemini_http_error(502, b"<html>" + b"x" * 5000 + b"</html>"),
        "Gemini API error",
    )
    assert isinstance(raw, ProviderUnavailableError)
    assert str(raw).startswith("Gemini API error: HTTP 502: <html>")
    assert len(str(raw)) < 2100
    offline = gemini_provider._provider_error(
        urllib.error.URLError("offline"), "Gemini API error"
    )
    assert isinstance(offline, ProviderTransportError)
    assert str(offline) == "Gemini API error: <urlopen error offline>"


def test_gemini_continuation_and_stream_errors_are_typed(gemini_provider):
    from praval.models import ModelResponse

    response = ModelResponse(metadata={"gemini_payload": {}, "gemini_contents": []})
    error = _gemini_http_error(503, {"error": {"status": "UNAVAILABLE"}})
    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(ProviderUnavailableError, match="Gemini API error"):
            gemini_provider.continue_with_tool_results(
                _request("gemini-test"), response, []
            )
    error = _gemini_http_error(429, {"error": {"status": "RESOURCE_EXHAUSTED"}})
    with patch("urllib.request.urlopen", side_effect=error):
        stream = gemini_provider.stream(_request("gemini-test"))
        event = next(stream)
        assert event.type == "error"
        assert "HTTP 429" in event.metadata["message"]
        with pytest.raises(ProviderRateLimitError, match="Gemini streaming error"):
            next(stream)


# --- Runtime integration -------------------------------------------------


def test_runtime_retries_mapped_openai_rate_limit_using_retry_after(
    openai_provider,
):
    provider, client, _ = openai_provider
    success = Mock()
    success.choices = [Mock()]
    success.choices[0].message.content = "recovered"
    success.choices[0].message.tool_calls = None
    success.choices[0].finish_reason = "stop"
    success.usage = None
    client.chat.completions.create.side_effect = [
        _openai_status_error(
            openai.RateLimitError,
            429,
            {"message": "slow"},
            headers={"retry-after": "3"},
        ),
        success,
    ]
    runtime = ModelRuntime(
        provider=provider,
        provider_name="openai",
        config=AgentConfig(provider="openai", model="gpt-test", retries=1),
    )
    with patch("praval.model_runtime._sleep") as sleep:
        response = runtime.invoke(messages=[{"role": "user", "content": "x"}])
    assert response.content == "recovered"
    sleep.assert_called_once_with(3.0)
    assert client.chat.completions.create.call_count == 2


def test_runtime_raises_mapped_openai_auth_error_without_retry(openai_provider):
    provider, client, _ = openai_provider
    auth_error = _openai_status_error(
        openai.AuthenticationError, 401, {"message": "bad key"}
    )
    client.chat.completions.create.side_effect = auth_error
    runtime = ModelRuntime(
        provider=provider,
        provider_name="openai",
        config=AgentConfig(provider="openai", model="gpt-test", retries=3),
    )
    with patch("praval.model_runtime._sleep") as sleep:
        with pytest.raises(ProviderAuthenticationError) as info:
            runtime.invoke(messages=[{"role": "user", "content": "x"}])
    sleep.assert_not_called()
    assert client.chat.completions.create.call_count == 1
    assert info.value.__cause__ is auth_error
    assert info.value.operation == "invoke"
    assert info.value.provider == "openai"
