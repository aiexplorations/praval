"""Praval-owned retries for provider requests outside ``ModelRuntime``.

SDK retries are off (WP2), so OpenAI ``transcribe``/``speak``, the follow-up
request of every adapter's legacy ``generate()`` tool flow, and the v0.8.3
provider-specific HITL resume (which ends in that follow-up) retry through
``call_with_retries``. A retryable failure is retried; a non-retryable one is
not; tools that already ran are never run again. No network is used: SDK
clients are fakes and failures are real SDK or ``urllib`` exception objects.
"""

import asyncio
import io
import json
import urllib.error
from email.message import Message
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import anthropic
import httpx
import openai
import pytest
from cohere.core.api_error import ApiError

from praval import (
    Agent,
    ProviderAuthenticationError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
)
from praval.core.agent import AgentConfig
from praval.core.exceptions import InterventionRequired
from praval.hitl.service import HITLService
from praval.model_runtime import (
    acall_with_retries,
    call_with_retries,
    max_provider_retries,
)
from praval.models.observation import RetryObservation
from praval.providers.anthropic import AnthropicProvider
from praval.providers.cohere import CohereProvider
from praval.providers.gemini import GeminiProvider
from praval.providers.openai import OpenAIProvider

OPENAI_URL = "https://api.openai.com/v1/audio/transcriptions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
# Newer anthropic SDKs build errors from httpx2 objects, older ones from httpx.
ANTHROPIC_HTTP = getattr(anthropic._exceptions, "httpx2", httpx)


def _openai_error(cls: Any, status: int) -> Exception:
    response = httpx.Response(status, request=httpx.Request("POST", OPENAI_URL))
    body = {"message": "failed"}
    return cls(f"Error code: {status}", response=response, body=body)


def _rate_limited() -> Exception:
    return _openai_error(openai.RateLimitError, 429)


def _unauthorized() -> Exception:
    return _openai_error(openai.AuthenticationError, 401)


def _anthropic_error(cls: Any, status: int, error_type: str) -> Exception:
    body = {"type": "error", "error": {"type": error_type, "message": "failed"}}
    response = ANTHROPIC_HTTP.Response(
        status, request=ANTHROPIC_HTTP.Request("POST", ANTHROPIC_URL)
    )
    return cls(f"Error code: {status}", response=response, body=body)


def _gemini_http_error(status: int) -> urllib.error.HTTPError:
    body = json.dumps({"error": {"status": "UNAVAILABLE", "message": "busy"}})
    return urllib.error.HTTPError(
        "https://gemini.test/v1beta/models/m:generateContent",
        status,
        "Error",
        Message(),
        io.BytesIO(body.encode()),
    )


@pytest.fixture
def sleeps(monkeypatch) -> List[float]:
    """Record backoff waits instead of sleeping."""
    delays: List[float] = []
    monkeypatch.setattr("praval.model_runtime._sleep", delays.append)
    monkeypatch.setattr("praval.model_runtime._jitter", lambda upper: upper)
    return delays


@pytest.fixture
def retries_recorded(monkeypatch) -> List[RetryObservation]:
    facts: List[RetryObservation] = []
    monkeypatch.setattr("praval.model_runtime.record_retry", facts.append)
    return facts


# --- The shared helper ------------------------------------------------------


def test_call_with_retries_retries_retryable_errors_then_succeeds(
    sleeps, retries_recorded
):
    outcomes: List[Any] = [
        ProviderRateLimitError("slow down"),
        ProviderRateLimitError("slow down", retry_after_seconds=3),
        "ok",
    ]

    def fn() -> str:
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    result = call_with_retries("follow_up", fn, retries=2, map_error=lambda exc: exc)
    assert result == "ok"
    assert sleeps == [0.5, 3.0]
    assert [fact.operation for fact in retries_recorded] == [
        "model.follow_up",
        "model.follow_up",
    ]
    assert [fact.reason_type for fact in retries_recorded] == [
        "ProviderRateLimitError",
        "ProviderRateLimitError",
    ]


def test_call_with_retries_stops_after_the_configured_retries(sleeps):
    calls = []

    def fn() -> None:
        calls.append(1)
        raise ProviderRateLimitError("slow down")

    with pytest.raises(ProviderRateLimitError):
        call_with_retries("speak", fn, retries=1, map_error=lambda exc: exc)
    assert len(calls) == 2
    assert len(sleeps) == 1


def test_call_with_retries_raises_non_retryable_at_once_with_cause(sleeps):
    raw = ValueError("raw detail")
    calls = []

    def fn() -> None:
        calls.append(1)
        raise raw

    with pytest.raises(ProviderInvalidRequestError) as info:
        call_with_retries(
            "transcribe",
            fn,
            retries=5,
            map_error=lambda exc: ProviderInvalidRequestError("mapped"),
        )
    assert calls == [1]
    assert sleeps == []
    assert info.value.__cause__ is raw


def test_call_with_retries_passes_hitl_signals_through(sleeps):
    signal = InterventionRequired("i", "r", "a", "t")

    def fn() -> None:
        raise signal

    mapper = Mock()
    with pytest.raises(InterventionRequired) as info:
        call_with_retries("follow_up", fn, retries=3, map_error=mapper)
    assert info.value is signal
    mapper.assert_not_called()
    assert sleeps == []


def test_acall_with_retries_uses_async_sleep_only(monkeypatch):
    def forbidden_sleep(seconds: float) -> None:
        raise AssertionError("sync sleep on the async path")

    async_sleep = AsyncMock()
    monkeypatch.setattr("praval.model_runtime._sleep", forbidden_sleep)
    monkeypatch.setattr("praval.model_runtime._async_sleep", async_sleep)
    outcomes: List[Any] = [ProviderRateLimitError("x", retry_after_seconds=1), 7]

    async def fn() -> int:
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    result = asyncio.run(
        acall_with_retries("invoke", fn, retries=1, map_error=lambda exc: exc)
    )
    assert result == 7
    async_sleep.assert_awaited_once_with(1.0)


def test_max_provider_retries_reads_config_and_clamps():
    assert max_provider_retries(SimpleNamespace(retries=3)) == 3
    assert max_provider_retries(SimpleNamespace(retries=-2)) == 0
    assert max_provider_retries(SimpleNamespace(retries=None)) == 0
    assert max_provider_retries(object()) == 0


# --- OpenAI transcribe and speak --------------------------------------------


@pytest.fixture
def openai_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client = Mock()
    with patch("praval.providers.openai.openai.OpenAI", return_value=client):
        provider = OpenAIProvider(
            AgentConfig(provider="openai", model="gpt-test", retries=2)
        )
    return provider, client


def test_transcribe_retries_retryable_error(openai_provider, sleeps):
    provider, client = openai_provider
    client.audio.transcriptions.create.side_effect = [
        _rate_limited(),
        SimpleNamespace(text="hello"),
    ]
    response = provider.transcribe({"audio": b"RIFF-bytes"})
    assert response.text == "hello"
    assert client.audio.transcriptions.create.call_count == 2
    assert len(sleeps) == 1


def test_transcribe_does_not_retry_non_retryable_error(openai_provider, sleeps):
    provider, client = openai_provider
    client.audio.transcriptions.create.side_effect = _unauthorized()
    with pytest.raises(ProviderAuthenticationError, match="transcription error"):
        provider.transcribe({"audio": b"RIFF-bytes"})
    assert client.audio.transcriptions.create.call_count == 1
    assert sleeps == []


def test_transcribe_retry_resends_the_whole_file(openai_provider, sleeps, tmp_path):
    provider, client = openai_provider
    path = tmp_path / "clip.wav"
    path.write_bytes(b"0123456789")
    uploads: List[bytes] = []

    def create(**params: Any) -> Any:
        uploads.append(params["file"].read())
        if len(uploads) == 1:
            raise _rate_limited()
        return SimpleNamespace(text="heard")

    client.audio.transcriptions.create.side_effect = create
    assert provider.transcribe({"audio": str(path)}).text == "heard"
    assert uploads == [b"0123456789", b"0123456789"]


def test_transcribe_rewinds_a_file_object_to_its_start_position(
    openai_provider, sleeps
):
    provider, client = openai_provider
    stream = io.BytesIO(b"headerAUDIO")
    stream.seek(6)
    uploads: List[bytes] = []

    def create(**params: Any) -> Any:
        uploads.append(params["file"].read())
        if len(uploads) == 1:
            raise _rate_limited()
        return SimpleNamespace(text="heard")

    client.audio.transcriptions.create.side_effect = create
    provider.transcribe({"audio": stream})
    assert uploads == [b"AUDIO", b"AUDIO"]


def test_transcribe_does_not_retry_an_unseekable_stream(openai_provider, sleeps):
    provider, client = openai_provider

    class Pipe(io.RawIOBase):
        def readable(self) -> bool:
            return True

        def seekable(self) -> bool:
            return False

        def readinto(self, buffer: Any) -> int:
            return 0

    client.audio.transcriptions.create.side_effect = _rate_limited()
    with pytest.raises(ProviderRateLimitError):
        provider.transcribe({"audio": Pipe()})
    assert client.audio.transcriptions.create.call_count == 1
    assert sleeps == []


def test_speak_retries_retryable_error(openai_provider, sleeps):
    provider, client = openai_provider
    client.audio.speech.create.side_effect = [
        openai.APIConnectionError(request=httpx.Request("POST", OPENAI_URL)),
        SimpleNamespace(content=b"mp3-bytes"),
    ]
    response = provider.speak({"input": "hello"})
    assert response.data == b"mp3-bytes"
    assert client.audio.speech.create.call_count == 2
    assert len(sleeps) == 1


def test_speak_does_not_retry_non_retryable_error(openai_provider, sleeps):
    provider, client = openai_provider
    client.audio.speech.create.side_effect = _unauthorized()
    with pytest.raises(ProviderAuthenticationError, match="speech generation error"):
        provider.speak({"input": "hello"})
    assert client.audio.speech.create.call_count == 1
    assert sleeps == []


def test_agent_transcribe_records_the_retry_on_its_observation(
    monkeypatch, sleeps, retries_recorded
):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client = Mock()
    client.audio.transcriptions.create.side_effect = [
        _rate_limited(),
        SimpleNamespace(text="agent heard"),
    ]
    with patch("praval.providers.openai.openai.OpenAI", return_value=client):
        agent = Agent("listener", provider="openai", model="gpt-test")
    assert agent.transcribe(b"RIFF-bytes") == "agent heard"
    assert [fact.operation for fact in retries_recorded] == ["model.transcribe"]


# --- Legacy generate() follow-ups -------------------------------------------


def _counting_tool(executed: List[Dict[str, Any]]) -> Dict[str, Any]:
    def publish(value: str) -> str:
        executed.append({"value": value})
        return f"published {value}"

    return {
        "function": publish,
        "description": "Publish a value",
        "parameters": {"value": {"type": "str", "required": True}},
    }


def _openai_tool_turn() -> Any:
    tool_call = SimpleNamespace(
        id="call-1",
        type="function",
        function=SimpleNamespace(name="publish", arguments='{"value": "v1"}'),
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[tool_call]))]
    )


def _openai_text_turn(text: str) -> Any:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text, tool_calls=None),
                finish_reason="stop",
            )
        ]
    )


@pytest.mark.parametrize(
    ("follow_up_error", "expected", "calls", "waits"),
    [
        (_rate_limited, "final answer", 3, 1),
        (_unauthorized, "published v1", 2, 0),
    ],
)
def test_openai_generate_follow_up_retries_only_when_retryable(
    openai_provider, sleeps, follow_up_error, expected, calls, waits
):
    provider, client = openai_provider
    executed: List[Dict[str, Any]] = []
    client.chat.completions.create.side_effect = [
        _openai_tool_turn(),
        follow_up_error(),
        _openai_text_turn("final answer"),
    ]
    result = provider.generate(
        [{"role": "user", "content": "publish"}], tools=[_counting_tool(executed)]
    )
    assert result == expected
    assert executed == [{"value": "v1"}]
    assert client.chat.completions.create.call_count == calls
    assert len(sleeps) == waits


@pytest.fixture
def anthropic_provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    client = Mock()
    with patch("praval.providers.anthropic.anthropic.Anthropic", return_value=client):
        provider = AnthropicProvider(
            AgentConfig(provider="anthropic", model="claude-test", retries=2)
        )
    return provider, client


@pytest.mark.parametrize(
    ("follow_up_error", "expected", "calls", "waits"),
    [
        (
            lambda: _anthropic_error(
                anthropic.InternalServerError, 529, "overloaded_error"
            ),
            "final answer",
            3,
            1,
        ),
        (
            lambda: _anthropic_error(
                anthropic.BadRequestError, 400, "invalid_request_error"
            ),
            "published v1",
            2,
            0,
        ),
    ],
)
def test_anthropic_generate_follow_up_retries_only_when_retryable(
    anthropic_provider, sleeps, follow_up_error, expected, calls, waits
):
    provider, client = anthropic_provider
    executed: List[Dict[str, Any]] = []
    tool_turn = SimpleNamespace(
        content=[
            {
                "type": "tool_use",
                "id": "toolu-1",
                "name": "publish",
                "input": {"value": "v1"},
            }
        ]
    )
    final_turn = SimpleNamespace(content=[{"type": "text", "text": "final answer"}])
    client.messages.create.side_effect = [tool_turn, follow_up_error(), final_turn]
    result = provider.generate(
        [{"role": "user", "content": "publish"}], tools=[_counting_tool(executed)]
    )
    assert result == expected
    assert executed == [{"value": "v1"}]
    assert client.messages.create.call_count == calls
    assert len(sleeps) == waits


@pytest.fixture
def cohere_provider(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "co-test")
    client = Mock()
    with patch("praval.providers.cohere.cohere.Client", return_value=client):
        provider = CohereProvider(
            AgentConfig(provider="cohere", model="command-test", retries=2)
        )
    return provider, client


@pytest.mark.parametrize(
    ("status", "expected", "calls", "waits"),
    [(503, "final answer", 3, 1), (401, "published v1", 2, 0)],
)
def test_cohere_generate_follow_up_retries_only_when_retryable(
    cohere_provider, sleeps, status, expected, calls, waits
):
    provider, client = cohere_provider
    executed: List[Dict[str, Any]] = []
    tool_turn = SimpleNamespace(
        text="",
        tool_calls=[{"id": "c1", "name": "publish", "parameters": {"value": "v1"}}],
    )
    client.chat.side_effect = [
        tool_turn,
        ApiError(status_code=status, body="failed"),
        SimpleNamespace(text="final answer", tool_calls=None),
    ]
    result = provider.generate(
        [{"role": "user", "content": "publish"}], tools=[_counting_tool(executed)]
    )
    assert result == expected
    assert executed == [{"value": "v1"}]
    assert client.chat.call_count == calls
    assert len(sleeps) == waits


@pytest.mark.parametrize(
    ("status", "expected", "calls", "waits"),
    [(503, "final answer", 3, 1), (400, "published v1", 2, 0)],
)
def test_gemini_generate_follow_up_retries_only_when_retryable(
    monkeypatch, sleeps, status, expected, calls, waits
):
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    provider = GeminiProvider(
        AgentConfig(provider="gemini", model="gemini-test", retries=2)
    )
    executed: List[Dict[str, Any]] = []
    tool_turn = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"functionCall": {"name": "publish", "args": {"value": "v1"}}}
                    ]
                }
            }
        ]
    }
    final_turn = {"candidates": [{"content": {"parts": [{"text": "final answer"}]}}]}
    post = Mock(side_effect=[tool_turn, _gemini_http_error(status), final_turn])
    with patch.object(provider, "_post_json", post):
        result = provider.generate(
            [{"role": "user", "content": "publish"}],
            tools=[_counting_tool(executed)],
        )
    assert result == expected
    assert executed == [{"value": "v1"}]
    assert post.call_count == calls
    assert len(sleeps) == waits


# --- v0.8.3 provider-specific HITL resume -----------------------------------


@pytest.mark.parametrize(
    ("follow_up_error", "expected", "calls", "waits"),
    [
        (_rate_limited, "resumed answer", 2, 1),
        (_unauthorized, "published approved", 1, 0),
    ],
)
def test_v083_openai_resume_retries_follow_up_without_rerunning_tool(
    monkeypatch, tmp_path, sleeps, follow_up_error, expected, calls, waits
):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    db_path = str(tmp_path / "hitl.db")
    client = Mock()
    client.chat.completions.create.side_effect = [
        follow_up_error(),
        _openai_text_turn("resumed answer"),
    ]
    with patch("praval.providers.openai.openai.OpenAI", return_value=client):
        agent = Agent(
            "resumer",
            provider="openai",
            model="gpt-test",
            hitl_enabled=True,
            hitl_db_path=db_path,
        )
    executed: List[str] = []

    @agent.tool
    def publish(value: str) -> str:
        """Publish a value."""
        executed.append(value)
        return f"published {value}"

    service = HITLService(db_path=db_path)
    intervention = service.store.create_intervention(
        run_id="run-1",
        agent_name="resumer",
        provider_name="openai",
        tool_name="publish",
        tool_call_id="call-1",
        original_args={"value": "approved"},
    )
    tool_calls = [
        {
            "id": "call-1",
            "type": "function",
            "function": {"name": "publish", "arguments": '{"value": "approved"}'},
        }
    ]
    service.store.upsert_suspended_run(
        run_id="run-1",
        agent_name="resumer",
        provider_name="openai",
        state={
            "schema": "openai_tool_v1",
            "intervention_id": intervention.id,
            "original_messages": [{"role": "user", "content": "publish it"}],
            "tool_calls": tool_calls,
            "current_index": 0,
            "tool_messages": [],
        },
        status="pending",
    )
    agent.approve_intervention(intervention.id, reviewer="qa")

    assert agent.resume_run("run-1") == expected
    assert executed == ["approved"]
    assert client.chat.completions.create.call_count == calls
    assert len(sleeps) == waits


def test_follow_up_failure_after_retries_keeps_tool_output_fallback(
    openai_provider, sleeps
):
    provider, client = openai_provider
    executed: List[Dict[str, Any]] = []
    client.chat.completions.create.side_effect = [
        _openai_tool_turn(),
        _rate_limited(),
        _rate_limited(),
        _rate_limited(),
    ]
    result = provider.generate(
        [{"role": "user", "content": "publish"}], tools=[_counting_tool(executed)]
    )
    assert result == "published v1"
    assert executed == [{"value": "v1"}]
    # One tool turn, the follow-up and its two retries.
    assert client.chat.completions.create.call_count == 4
    assert len(sleeps) == 2
