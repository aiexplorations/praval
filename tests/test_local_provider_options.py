from __future__ import annotations

from types import SimpleNamespace

from praval.models import ModelMessage, ModelRequest
from praval.providers.openai import OpenAIProvider


def test_local_preset_is_not_forwarded_to_chat_completions(monkeypatch) -> None:
    monkeypatch.setenv("TEST_OPENAI_KEY", "test-key")
    provider = OpenAIProvider(
        SimpleNamespace(
            model="gpt-test",
            max_tokens=32,
            api_key_env="TEST_OPENAI_KEY",
            base_url=None,
            timeout=None,
        )
    )
    request = ModelRequest(
        provider="ollama",
        model="phi4-mini-reasoning",
        messages=[ModelMessage(role="user", content="hello")],
        provider_options={"endpoint": "chat.completions", "local_preset": "ollama"},
    )

    params = provider._chat_completion_params(request)

    assert params["model"] == "phi4-mini-reasoning"
    assert "endpoint" not in params
    assert "local_preset" not in params
