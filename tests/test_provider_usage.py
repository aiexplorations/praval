"""Synthetic documented wire/SDK shapes; live certification is separate."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from praval.core.agent import AgentConfig
from praval.core.exceptions import ProviderUnavailableError
from praval.model_runtime import ModelRuntime
from praval.providers.gemini import GeminiProvider
from praval.providers.openai import OpenAIProvider
from praval.providers.usage import (
    anthropic_usage,
    cohere_usage,
    gemini_usage,
    openai_usage,
)


def sdk(value):
    return (
        SimpleNamespace(**{key: sdk(item) for key, item in value.items()})
        if isinstance(value, dict)
        else value
    )


CASES = [
    (
        openai_usage,
        {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_tokens_details": {
                    "cached_tokens": 40,
                    "cache_write_tokens": 10,
                },
                "completion_tokens_details": {"reasoning_tokens": 15},
            }
        },
        (100, 20, 120, 15, 40, 10),
    ),
    (
        openai_usage,
        {
            "usage": {
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
                "input_tokens_details": {"cached_tokens": 40},
                "output_tokens_details": {"reasoning_tokens": 15},
            }
        },
        (100, 20, 120, 15, 40, 0),
    ),
    (
        anthropic_usage,
        {
            "usage": {
                "input_tokens": 10,
                "output_tokens": 20,
                "cache_read_input_tokens": 100,
                "cache_creation_input_tokens": 50,
            }
        },
        (160, 20, 180, 0, 100, 50),
    ),
    (
        gemini_usage,
        {
            "usageMetadata": {
                "promptTokenCount": 100,
                "candidatesTokenCount": 20,
                "thoughtsTokenCount": 50,
                "cachedContentTokenCount": 40,
                "totalTokenCount": 170,
            }
        },
        (100, 70, 170, 50, 40, 0),
    ),
    (
        cohere_usage,
        {
            "meta": {
                "billed_units": {"input_tokens": 5, "output_tokens": 20},
                "tokens": {"input_tokens": 100, "output_tokens": 30},
            }
        },
        (5, 20, 25, 0, 0, 0),
    ),
    (
        cohere_usage,
        {
            "usage": {
                "billed_units": {"input_tokens": 5.0, "output_tokens": 20.0},
                "tokens": {"input_tokens": 100, "output_tokens": 30},
            }
        },
        (5, 20, 25, 0, 0, 0),
    ),
]


@pytest.mark.parametrize("normalize,payload,expected", CASES)
@pytest.mark.parametrize("as_sdk", [False, True])
def test_usage_mapping_preserves_token_semantics(normalize, payload, expected, as_sdk):
    usage = normalize(sdk(payload) if as_sdk else payload)
    fields = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "reasoning_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
    )
    assert tuple(getattr(usage, name) for name in fields) == expected
    assert usage.reasoning_tokens <= usage.output_tokens
    assert usage.cache_read_tokens + usage.cache_write_tokens <= usage.input_tokens


@pytest.mark.parametrize(
    "normalize", [openai_usage, anthropic_usage, gemini_usage, cohere_usage]
)
@pytest.mark.parametrize("payload", [None, {}, SimpleNamespace(), Mock()])
def test_missing_usage_is_unreported_not_zero(normalize, payload):
    assert normalize(payload) is None


@pytest.mark.parametrize(
    "normalize,key",
    [
        (openai_usage, "usage"),
        (anthropic_usage, "usage"),
        (gemini_usage, "usageMetadata"),
    ],
)
def test_explicit_zero_usage_is_reported(normalize, key):
    assert normalize({key: {}}).total_tokens == 0


@pytest.mark.parametrize("failed_second", [False, True])
def test_empty_openai_answer_expansion_counts_both_requests(failed_second):
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.config = AgentConfig(
        provider="openai", model="gpt-5-test", max_tokens=100, retries=0
    )
    provider.client = Mock()
    first = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="", tool_calls=None),
                finish_reason="length",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    )
    second = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="done", tool_calls=None),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=15, completion_tokens=30, total_tokens=45),
    )
    provider.client.chat.completions.create.side_effect = [
        first,
        ProviderUnavailableError("failure") if failed_second else second,
    ]
    runtime = ModelRuntime(
        provider=provider, provider_name="openai", config=provider.config
    )
    if failed_second:
        with pytest.raises(ProviderUnavailableError):
            runtime.invoke(messages=[{"role": "user", "content": "hello"}])
    else:
        response = runtime.invoke(messages=[{"role": "user", "content": "hello"}])
        assert response.content == "done" and response.usage.total_tokens == 75
        assert len(response.metadata["model_calls"]) == 2
    assert provider.client.chat.completions.create.call_count == 2
    assert runtime.usage.totals.calls == 2
    assert runtime.usage.totals.total_tokens == (30 if failed_second else 75)
    assert runtime.usage.totals.failed_calls == int(failed_second)


def test_gemini_stream_uses_latest_cumulative_snapshot(monkeypatch):
    provider = GeminiProvider.__new__(GeminiProvider)
    provider.config = AgentConfig(provider="gemini", model="gemini-test")
    monkeypatch.setattr(
        provider,
        "_post_stream",
        lambda *args, **kwargs: iter(
            [
                {
                    "candidates": [{"content": {"parts": [{"text": "hi"}]}}],
                    "usageMetadata": {
                        "promptTokenCount": 10,
                        "candidatesTokenCount": 1,
                        "totalTokenCount": 11,
                    },
                },
                {
                    "usageMetadata": {
                        "promptTokenCount": 10,
                        "candidatesTokenCount": 2,
                        "thoughtsTokenCount": 3,
                        "totalTokenCount": 15,
                    }
                },
            ]
        ),
    )
    runtime = ModelRuntime(
        provider=provider, provider_name="gemini", config=provider.config
    )
    final = list(runtime.stream(messages=[{"role": "user", "content": "hello"}]))[
        -1
    ].response
    assert final.content == "hi" and final.usage.total_tokens == 15
    assert final.usage.output_tokens == 5
    assert runtime.usage.totals.calls == 1 and runtime.usage.totals.total_tokens == 15


def test_cohere_actual_sdk_metadata_uses_billed_units():
    from cohere.types.api_meta import ApiMeta

    meta = ApiMeta.model_validate(
        {
            "billed_units": {"input_tokens": 5, "output_tokens": 20},
            "tokens": {"input_tokens": 100, "output_tokens": 30},
        }
    )
    assert cohere_usage(SimpleNamespace(meta=meta)).total_tokens == 25
