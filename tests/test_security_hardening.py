"""WP7 security probes: secrets, untrusted tool input, schemas and headers.

Every probe runs without network access. Provider failures are built from
the real SDK exception classes or ``urllib.error.HTTPError`` with crafted
bodies, and SDK clients are fakes that record what they are sent.
"""

import io
import json
import logging
import pickle
import socket
import subprocess
import sys
import textwrap
import traceback
import urllib.error
import urllib.request
from email.message import Message
from typing import Any, Dict, List
from unittest.mock import Mock, patch

import anthropic
import httpx
import openai
import pytest
from cohere.core.api_error import ApiError
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from praval import ProviderError
from praval.core.agent import AgentConfig
from praval.hitl.runtime import HITLRuntime
from praval.model_runtime import (
    ModelRuntime,
    _retry_backoff_seconds,
    execute_legacy_tool_call,
)
from praval.models import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ProviderCapabilities,
    ToolCall,
)
from praval.models.observation import ObservationKind
from praval.providers.anthropic import AnthropicProvider
from praval.providers.cohere import CohereProvider
from praval.providers.errors import (
    MAX_ERROR_BODY_CHARS,
    map_gemini_http_error,
    map_provider_exception,
    parse_retry_after,
)
from praval.providers.gemini import GeminiProvider
from praval.providers.openai import OpenAIProvider
from praval.providers.openai_compatible import OpenAICompatibleProvider
from praval.runtime_observation import ObservationScope, use_observation_recorder
from praval.tool_execution import run_tool, validate_tool_arguments

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_HTTP = getattr(anthropic._exceptions, "httpx2", httpx)
GEMINI_KEY = "AIzaSyCanaryGeminiKey0123456789abcdefgh"
CUSTOM_KEY = "custom-canary-key-7f3a9c2e"


def _messages() -> List[Dict[str, Any]]:
    return [{"role": "user", "content": "hello"}]


def _openai_status_error(cls: Any, status: int, body: Any) -> Any:
    response = httpx.Response(status, request=httpx.Request("POST", OPENAI_URL))
    return cls(f"Error code: {status} - {body}", response=response, body=body)


def _gemini_http_error(status: int, body: bytes, url: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, status, "Error", Message(), io.BytesIO(body))


def _all_text(error: BaseException) -> str:
    """Every string a caller can see from an error, without its traceback."""
    return " ".join(
        [str(error), repr(error), repr(error.args), repr(vars(error))]
        + [repr(pickle.loads(pickle.dumps(error)).__dict__)]
    )


def _traceback_text(error: BaseException) -> str:
    return "".join(traceback.format_exception(type(error), error, None))


@pytest.fixture
def span_exporter(monkeypatch):
    """Route Praval runtime spans to an in-memory exporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider(shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(
        "praval.runtime_observation._get_tracer",
        lambda: provider.get_tracer("praval.runtime"),
    )
    return exporter


def _span_text(exporter: InMemorySpanExporter) -> str:
    parts: List[str] = []
    for span in exporter.get_finished_spans():
        parts.append(span.name)
        parts.append(repr(dict(span.attributes or {})))
        parts.append(repr(span.status.description))
        for event in span.events:
            parts.append(event.name)
            parts.append(repr(dict(event.attributes or {})))
    return "\n".join(parts)


# --- S1 Gemini key in URL and echoed error body ---------------------------


@pytest.fixture
def gemini_provider(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_KEY)
    return GeminiProvider(AgentConfig(provider="gemini", model="gemini-test"))


def test_s1_gemini_http_error_keeps_key_out_of_mapped_error(gemini_provider):
    url = f"https://example.invalid/v1beta/models/m:generateContent?key={GEMINI_KEY}"
    body = json.dumps(
        {
            "error": {
                "status": "INVALID_ARGUMENT",
                "message": f"bad request for {url} with key {GEMINI_KEY}",
            }
        }
    ).encode()
    with patch(
        "urllib.request.urlopen", side_effect=_gemini_http_error(400, body, url)
    ):
        with pytest.raises(ProviderError) as info:
            gemini_provider.invoke(
                ModelRequest(messages=[ModelMessage(role="user", content="x")])
            )
    assert GEMINI_KEY not in _all_text(info.value)
    # HTTPError's own text never includes its URL.
    assert GEMINI_KEY not in _traceback_text(info.value)


def test_s1_gemini_stream_error_event_has_no_key(gemini_provider):
    url = f"https://example.invalid/m:streamGenerateContent?key={GEMINI_KEY}"
    body = json.dumps({"error": {"message": f"echo {GEMINI_KEY}"}}).encode()
    request = ModelRequest(messages=[ModelMessage(role="user", content="x")])
    events = []
    with patch(
        "urllib.request.urlopen", side_effect=_gemini_http_error(503, body, url)
    ):
        with pytest.raises(ProviderError) as info:
            for event in gemini_provider.stream(request):
                events.append(event)
    assert events and events[0].type == "error"
    assert GEMINI_KEY not in repr(events[0].metadata)
    assert GEMINI_KEY not in _all_text(info.value)


def test_s1_gemini_key_absent_from_traceback_on_malformed_url(monkeypatch):
    # The key travels in the x-goog-api-key header, so an exception that
    # quotes the request URL (here http.client rejecting the path) cannot
    # carry it on the chained __cause__ either.
    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_KEY)
    provider = GeminiProvider(
        AgentConfig(
            provider="gemini",
            # A trailing newline, as read from an env file. http.client
            # rejects the path and quotes it, query string included.
            model="gemini-2.5-flash\n",
            base_url="http://127.0.0.1:9/v1beta",
        )
    )
    with patch.object(socket.socket, "connect", side_effect=AssertionError):
        with pytest.raises(ProviderError) as info:
            provider.invoke(
                ModelRequest(messages=[ModelMessage(role="user", content="x")])
            )
    assert GEMINI_KEY not in str(info.value)  # redacted at this level
    assert GEMINI_KEY not in _traceback_text(info.value)


def test_s1_gemini_key_with_trailing_newline_is_stripped(monkeypatch):
    # An env-file key ending in a newline is an invalid header value, and
    # http.client quotes it (escaped, so redaction misses it) in the error.
    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_KEY + "\n")
    provider = GeminiProvider(
        AgentConfig(
            provider="gemini",
            model="gemini-2.5-flash",
            base_url="http://127.0.0.1:9/v1beta",
        )
    )
    assert provider.api_key == GEMINI_KEY
    with patch.object(
        socket.socket, "connect", side_effect=ConnectionRefusedError("refused")
    ):
        with pytest.raises(ProviderError) as info:
            provider.invoke(
                ModelRequest(messages=[ModelMessage(role="user", content="x")])
            )
    assert GEMINI_KEY not in _traceback_text(info.value)


def test_s1_gemini_embedding_key_with_trailing_newline_is_stripped(monkeypatch):
    from praval.embeddings import EmbeddingRuntime

    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_KEY + "\n")
    sent: List[urllib.request.Request] = []

    def fake_urlopen(request: urllib.request.Request) -> Any:
        sent.append(request)
        response = Mock()
        response.read.return_value = b'{"embedding": {"values": [0.1, 0.2]}}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    runtime = EmbeddingRuntime(provider="gemini", model="embed-test", dimensions=2)
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        runtime.embed("hello")
    assert sent[0].get_header("X-goog-api-key") == GEMINI_KEY
    assert GEMINI_KEY not in sent[0].full_url


# --- S2 / S3 Error body size ------------------------------------------------


class _CountingBody(io.BytesIO):
    """A body that records how many bytes the mapper asked for."""

    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)
        self.requested: List[int] = []

    def read(self, size: Any = -1) -> bytes:  # type: ignore[override]
        self.requested.append(-1 if size is None else size)
        return super().read(size)


def test_s2_gemini_error_body_read_is_bounded():
    payload = b'{"error": {"message": "' + b"x" * (8 * 1024 * 1024) + b'"}}'
    body = _CountingBody(payload)
    error = urllib.error.HTTPError(
        "https://example.invalid/m", 500, "Error", Message(), body
    )
    mapped = map_gemini_http_error(
        error, prefix="Gemini API error", model="m", redact=lambda text: text
    )
    assert body.requested and all(0 < size <= 1024 * 1024 for size in body.requested)
    assert len(str(mapped)) <= MAX_ERROR_BODY_CHARS + 100


def test_s3_sdk_error_message_is_truncated():
    body = {"error": {"message": "x" * 2_000_000}}
    error = _openai_status_error(openai.InternalServerError, 500, body)
    mapped = map_provider_exception(error, provider="openai")
    assert len(str(mapped)) <= MAX_ERROR_BODY_CHARS + 100
    assert mapped.status_code == 500


def test_s3_truncation_happens_after_redaction():
    secret = "sk-redact-me-0123456789"
    text = "y" * (MAX_ERROR_BODY_CHARS - 5) + secret
    mapped = map_provider_exception(
        RuntimeError(text), redact=lambda value: value.replace(secret, "***")
    )
    # A secret cut in half by truncation would survive redaction.
    assert secret[:5] not in str(mapped)


# --- S4 Redaction of configured API keys ------------------------------------


def _assert_no_custom_key(error: BaseException) -> None:
    assert CUSTOM_KEY not in _all_text(error)


def test_s4_openai_redacts_key_from_custom_api_key_env(monkeypatch):
    monkeypatch.setenv("MY_OPENAI_KEY", CUSTOM_KEY)
    client = Mock()
    client.chat.completions.create.side_effect = _openai_status_error(
        openai.AuthenticationError, 401, {"message": f"bad key {CUSTOM_KEY}"}
    )
    with patch("praval.providers.openai.openai.OpenAI", return_value=client):
        provider = OpenAIProvider(
            AgentConfig(
                provider="openai", model="gpt-test", api_key_env="MY_OPENAI_KEY"
            )
        )
    with pytest.raises(ProviderError) as info:
        provider.generate(_messages())
    _assert_no_custom_key(info.value)
    _assert_no_custom_key(provider.map_provider_error(RuntimeError(CUSTOM_KEY)))


def test_s4_openai_compatible_redacts_key_on_call_errors(monkeypatch):
    monkeypatch.setenv("GROQ_KEY", CUSTOM_KEY)
    client = Mock()
    client.chat.completions.create.side_effect = RuntimeError(
        f"upstream rejected Authorization: Bearer {CUSTOM_KEY}"
    )
    with patch("praval.providers.openai.openai.OpenAI", return_value=client):
        provider = OpenAICompatibleProvider(
            AgentConfig(
                provider="openai_compatible",
                model="m",
                base_url="http://127.0.0.1:9/v1",
                api_key_env="GROQ_KEY",
            )
        )
    runtime = ModelRuntime(
        provider=provider, provider_name="openai_compatible", config=provider.config
    )
    with pytest.raises(ProviderError) as info:
        runtime.invoke(messages=_messages())
    _assert_no_custom_key(info.value)


def test_s4_openai_compatible_does_not_redact_local_placeholder():
    client = Mock()
    client.chat.completions.create.side_effect = RuntimeError("local server down")
    with patch("praval.providers.openai.openai.OpenAI", return_value=client):
        provider = OpenAICompatibleProvider(
            AgentConfig(provider="ollama", model="m", base_url="http://127.0.0.1:9/v1")
        )
    error = provider.map_provider_error(RuntimeError("local server down"))
    assert "local server down" in str(error)


def test_s4_anthropic_redacts_key_from_custom_api_key_env(monkeypatch):
    monkeypatch.setenv("MY_ANTHROPIC_KEY", CUSTOM_KEY)
    client = Mock()
    response = ANTHROPIC_HTTP.Response(
        401,
        request=ANTHROPIC_HTTP.Request("POST", "https://api.anthropic.com/v1/messages"),
    )
    body = {"type": "error", "error": {"type": "auth", "message": CUSTOM_KEY}}
    client.messages.create.side_effect = anthropic.AuthenticationError(
        f"Error code: 401 - {body}", response=response, body=body
    )
    with patch("praval.providers.anthropic.anthropic.Anthropic", return_value=client):
        provider = AnthropicProvider(
            AgentConfig(
                provider="anthropic",
                model="claude-test",
                api_key_env="MY_ANTHROPIC_KEY",
            )
        )
    with pytest.raises(ProviderError) as info:
        provider.generate(_messages())
    _assert_no_custom_key(info.value)
    _assert_no_custom_key(provider.map_provider_error(RuntimeError(CUSTOM_KEY)))


def test_s4_cohere_redacts_key_from_custom_api_key_env(monkeypatch):
    monkeypatch.setenv("MY_COHERE_KEY", CUSTOM_KEY)
    client = Mock()
    client.chat.side_effect = ApiError(
        status_code=401, headers={}, body={"message": f"invalid key {CUSTOM_KEY}"}
    )
    with patch("praval.providers.cohere.cohere.Client", return_value=client):
        provider = CohereProvider(
            AgentConfig(
                provider="cohere", model="command-test", api_key_env="MY_COHERE_KEY"
            )
        )
    with pytest.raises(ProviderError) as info:
        provider.generate(_messages())
    _assert_no_custom_key(info.value)
    _assert_no_custom_key(provider.map_provider_error(RuntimeError(CUSTOM_KEY)))


# --- S5 Span exception events ----------------------------------------------


def _openai_runtime_with_failing_client(monkeypatch, secret: str):
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    client = Mock()
    client.chat.completions.create.side_effect = _openai_status_error(
        openai.AuthenticationError, 401, {"message": f"bad key {secret}"}
    )
    with patch("praval.providers.openai.openai.OpenAI", return_value=client):
        provider = OpenAIProvider(AgentConfig(provider="openai", model="gpt-test"))
    return ModelRuntime(
        provider=provider, provider_name="openai", config=provider.config
    )


def _exception_events(exporter: InMemorySpanExporter) -> List[Dict[str, Any]]:
    return [
        dict(event.attributes or {})
        for span in exporter.get_finished_spans()
        for event in span.events
        if event.name == "exception"
    ]


def test_s5_provider_span_exception_message_is_redacted(monkeypatch, span_exporter):
    secret = "plain-canary-openai-key-0042"
    runtime = _openai_runtime_with_failing_client(monkeypatch, secret)
    with pytest.raises(ProviderError) as info:
        runtime.invoke(messages=_messages())
    assert secret not in str(info.value)
    events = _exception_events(span_exporter)
    assert events
    for attributes in events:
        assert secret not in str(attributes.get("exception.message"))


def test_s5_span_stacktrace_does_not_carry_raw_cause(monkeypatch, span_exporter):
    secret = "plain-canary-openai-key-0042"
    runtime = _openai_runtime_with_failing_client(monkeypatch, secret)
    with pytest.raises(ProviderError) as info:
        runtime.invoke(messages=_messages())
    # The raw SDK error, with the secret, is still the cause for the caller.
    assert secret in _traceback_text(info.value.__cause__)
    events = _exception_events(span_exporter)
    assert events
    for attributes in events:
        assert secret not in str(attributes.get("exception.stacktrace"))
        assert "direct cause" not in str(attributes.get("exception.stacktrace"))
        assert attributes["exception.type"].endswith("ProviderAuthenticationError")
        assert attributes["exception.escaped"] == "False"


def test_s5_each_span_records_its_exception_once(monkeypatch, span_exporter):
    runtime = _openai_runtime_with_failing_client(monkeypatch, "canary-0043")
    with pytest.raises(ProviderError):
        runtime.invoke(messages=_messages())
    spans = span_exporter.get_finished_spans()
    assert spans
    for span in spans:
        names = [event.name for event in span.events]
        assert names.count("exception") <= 1, span.name


def _redacted_error_with_raw_cause(secret: str) -> ProviderError:
    try:
        try:
            raise RuntimeError(f"raw sdk failure {secret}")
        except RuntimeError as raw:
            raise ProviderError("redacted failure") from raw
    except ProviderError as error:
        return error


def _assert_chain_free(exporter: InMemorySpanExporter, secret: str) -> None:
    events = _exception_events(exporter)
    assert len(events) == 1
    assert events[0]["exception.type"] == "praval.core.exceptions.ProviderError"
    assert events[0]["exception.message"] == "redacted failure"
    assert "redacted failure" in events[0]["exception.stacktrace"]
    assert secret not in str(events)


@pytest.mark.parametrize("is_async", [False, True])
def test_s5_instrumented_function_span_drops_cause_chain(monkeypatch, is_async):
    import asyncio

    from praval.observability.instrumentation import utils

    secret = "canary-instrumented-0044"
    exporter = InMemorySpanExporter()
    provider = TracerProvider(shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(utils, "get_tracer", lambda: provider.get_tracer("t"))

    if is_async:

        @utils.instrument_function("agent.test.execute")
        async def handler() -> None:
            raise _redacted_error_with_raw_cause(secret)

        with pytest.raises(ProviderError):
            asyncio.run(handler())
    else:

        @utils.instrument_function("agent.test.execute")
        def handler() -> None:
            raise _redacted_error_with_raw_cause(secret)

        with pytest.raises(ProviderError):
            handler()
    _assert_chain_free(exporter, secret)


def test_s5_post_hoc_evaluation_span_drops_cause_chain(monkeypatch):
    from datetime import datetime, timezone

    from praval.models import ExecutionObservation
    from praval.models.observation import ObservationStatus
    from praval.observability import evaluation

    secret = "canary-evaluation-0045"
    exporter = InMemorySpanExporter()
    provider = TracerProvider(shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(evaluation, "get_tracer", provider.get_tracer)
    now = datetime.now(timezone.utc)
    observation = ExecutionObservation(
        observation_id="o",
        run_id="r",
        kind=ObservationKind.AGENT,
        agent_name="a",
        started_at=now,
        ended_at=now,
        duration_ms=0,
        status=ObservationStatus.OK,
    )
    telemetry = evaluation.OnlineEvaluationTelemetry(
        suite_id="s", queue_depth=lambda: 0
    )
    with pytest.raises(ProviderError):
        with telemetry.start_post_hoc_span(observation, {"praval.test": "x"}):
            raise _redacted_error_with_raw_cause(secret)
    _assert_chain_free(exporter, secret)


def test_s5_retry_log_and_event_carry_type_only(monkeypatch, span_exporter, caplog):
    secret = "plain-canary-openai-key-0042"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    client = Mock()
    success = Mock()
    success.choices = [Mock(message=Mock(content="ok", tool_calls=None))]
    success.usage = None
    client.chat.completions.create.side_effect = [
        _openai_status_error(openai.RateLimitError, 429, {"message": secret}),
        success,
    ]
    with patch("praval.providers.openai.openai.OpenAI", return_value=client):
        provider = OpenAIProvider(
            AgentConfig(provider="openai", model="gpt-test", retries=1)
        )
    runtime = ModelRuntime(
        provider=provider, provider_name="openai", config=provider.config
    )
    caplog.set_level(logging.DEBUG)
    with patch("praval.model_runtime._sleep"):
        runtime.invoke(messages=_messages())
    assert secret not in caplog.text
    retry_events = [
        dict(event.attributes or {})
        for span in span_exporter.get_finished_spans()
        for event in span.events
        if event.name == "praval.retry"
    ]
    assert secret not in repr(retry_events)


# --- S6 Transcripts in metadata and HITL state ------------------------------

TRANSCRIPT_CANARY = "transcript-canary-5d1e"


class _TranscriptProvider:
    """Two rounds; every response carries a native transcript with a canary."""

    capabilities = ProviderCapabilities(tools=True)

    def invoke(self, request):
        return ModelResponse(
            tool_calls=[
                ToolCall(id="c1", name="lookup", arguments={"q": TRANSCRIPT_CANARY})
            ],
            metadata={"openai_chat_messages": [{"content": TRANSCRIPT_CANARY}]},
        )

    def continue_with_tool_results(self, request, response, tool_results):
        return ModelResponse(
            content=f"answer {TRANSCRIPT_CANARY}",
            metadata={"openai_chat_messages": [{"content": TRANSCRIPT_CANARY}]},
        )


def test_s6_transcripts_and_tool_content_stay_out_of_spans_and_observation(
    span_exporter, caplog
):
    observations: List[Any] = []

    class _Recorder:
        def record(self, observation):
            observations.append(observation)

    def lookup(q: str) -> str:
        return f"result {TRANSCRIPT_CANARY}"

    runtime = ModelRuntime(
        provider=_TranscriptProvider(),
        provider_name="fake",
        config=AgentConfig(provider="openai", model="m"),
    )
    caplog.set_level(logging.DEBUG)
    with use_observation_recorder(_Recorder()):
        with ObservationScope(kind=ObservationKind.AGENT, agent_name="probe"):
            response = runtime.invoke(
                messages=[{"role": "user", "content": TRANSCRIPT_CANARY}],
                tools=[{"function": lookup, "description": "Look up"}],
            )
    assert TRANSCRIPT_CANARY in response.content
    assert observations
    assert TRANSCRIPT_CANARY not in observations[0].model_dump_json()
    assert TRANSCRIPT_CANARY not in _span_text(span_exporter)
    assert TRANSCRIPT_CANARY not in caplog.text


def test_s6_hitl_state_holds_no_raw_sdk_object_or_credentials(tmp_path):
    provider = _TranscriptProvider()
    db_path = str(tmp_path / "hitl.db")
    config = AgentConfig(provider="openai", model="m")
    runtime = ModelRuntime(provider=provider, provider_name="fake", config=config)

    def lookup(q: str) -> str:
        return "result"

    from praval.core.exceptions import InterventionRequired
    from praval.hitl.store import HITLStore

    with pytest.raises(InterventionRequired) as info:
        runtime.invoke(
            messages=_messages(),
            tools=[{"function": lookup, "requires_approval": True}],
            hitl_context={
                "enabled": True,
                "run_id": "r1",
                "agent_name": "a",
                "provider_name": "fake",
                "db_path": db_path,
            },
        )
    store = HITLStore(db_path)
    state = store.get_suspended_run(info.value.run_id).state
    dumped = json.dumps(state)
    # The transcript is persisted on purpose (resume needs it) ...
    assert TRANSCRIPT_CANARY in dumped
    # ... but nothing credential-shaped is, and the request has no options.
    assert "api_key" not in dumped.lower()
    assert "authorization" not in dumped.lower()
    assert "raw" not in state["response"]


# --- S7 Untrusted tool arguments -------------------------------------------


def _deep_json(depth: int) -> str:
    return '{"a": ' * depth + "1" + "}" * depth


def test_s7_parse_args_survives_deeply_nested_json():
    brackets = "[" * 200_000
    assert HITLRuntime._parse_args(brackets) == {"raw": brackets}
    deep = _deep_json(200_000)
    assert HITLRuntime._parse_args(deep) == {"raw": deep}


def test_s7_openai_tool_call_parse_survives_deeply_nested_json(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    with patch("praval.providers.openai.openai.OpenAI", return_value=Mock()):
        provider = OpenAIProvider(AgentConfig(provider="openai", model="gpt-test"))
    raw = "[" * 200_000
    call = provider._chat_tool_call(
        {"id": "c", "function": {"name": "t", "arguments": raw}}
    )
    assert call.arguments == {"raw": raw}
    responses_call = provider._tool_call(
        {"call_id": "c", "name": "t", "arguments": raw}
    )
    assert responses_call.arguments == {"raw": raw}


def test_s7_deeply_nested_dict_arguments_reported_not_crashed():
    def handler(a: Dict[str, Any]) -> str:  # pragma: no cover - must not run
        raise AssertionError("handler ran")

    value: Any = 1
    for _ in range(5000):
        value = {"a": value}
    result = run_tool({"name": "h", "function": handler}, {"a": value})
    assert result.is_error


def test_s7_oversized_arguments_are_validated_without_error():
    calls = []

    def handler(text: str) -> str:
        calls.append(len(text))
        return "ok"

    result = run_tool({"name": "h", "function": handler}, {"text": "x" * 5_000_000})
    assert not result.is_error and calls == [5_000_000]


def test_s7_undeclared_parameters_rejected_before_handler():
    def handler(path: str) -> str:  # pragma: no cover - must not run
        raise AssertionError("handler ran")

    result = run_tool(
        {"name": "h", "function": handler},
        {"path": "/tmp/x", "__class__": "x", "shell": True},
    )
    assert result.is_error
    assert "__class__: unexpected argument" in result.content
    assert "shell: unexpected argument" in result.content


def test_s7_duplicate_keys_resolve_the_same_for_review_and_execution(tmp_path):
    raw = '{"path": "/safe", "path": "/etc/passwd"}'
    executed = []

    def write(path: str) -> str:
        executed.append(path)
        return "ok"

    tools = [{"function": write, "requires_approval": True}]
    db_path = str(tmp_path / "dup.db")
    runtime = HITLRuntime(
        run_id="r",
        agent_name="a",
        provider_name="p",
        hitl_enabled=True,
        db_path=db_path,
    )
    from praval.core.exceptions import InterventionRequired

    with pytest.raises(InterventionRequired) as info:
        runtime.execute_or_interrupt_result(
            tool_call_id="c",
            function_name="write",
            raw_args=raw,
            available_tools=tools,
            continuation_state={},
        )
    intervention = runtime.store.get_intervention(info.value.intervention_id)
    # Reviewer sees exactly what would execute: the last duplicate wins.
    assert intervention.original_args == {"path": "/etc/passwd"}


@pytest.mark.parametrize("raw_args", ["not-json", '["/etc/passwd"]', '{"path": '])
def test_s7_malformed_argument_string_does_not_run_tool_with_defaults(raw_args):
    executed = []

    def cleanup(path: str = "/tmp/default") -> str:
        executed.append(path)
        return "cleaned"

    content = execute_legacy_tool_call(
        hitl_context=None,
        tool_call_id="c",
        function_name="cleanup",
        raw_args=raw_args,
        available_tools=[{"function": cleanup}],
    )
    assert executed == []
    assert content.startswith("Error:")
    assert "raw: unexpected argument" in content


@pytest.mark.parametrize("raw_args", ["", "  ", None, "{}"])
def test_s7_empty_argument_string_still_runs_tool_with_defaults(raw_args):
    executed = []

    def cleanup(path: str = "/tmp/default") -> str:
        executed.append(path)
        return "cleaned"

    content = execute_legacy_tool_call(
        hitl_context=None,
        tool_call_id="c",
        function_name="cleanup",
        raw_args=raw_args,
        available_tools=[{"function": cleanup}],
    )
    assert content == "cleaned"
    assert executed == ["/tmp/default"]


# --- S8 Untrusted JSON Schemas (MCP) ----------------------------------------


def _kwargs_tool(schema: Dict[str, Any]) -> Dict[str, Any]:
    calls: List[Dict[str, Any]] = []

    def mcp_proxy(**kwargs: Any) -> str:
        calls.append(kwargs)
        return "proxied"

    return {
        "name": "mcp_tool",
        "function": mcp_proxy,
        "parameters": schema,
        "_c": calls,
    }


@pytest.mark.parametrize(
    "ref",
    [
        "https://attacker.invalid/schema.json",
        "http://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd",
        "#/$defs/missing",
    ],
)
def test_s8_unresolvable_ref_is_not_fetched_and_does_not_crash(ref):
    tool = _kwargs_tool(
        {"type": "object", "properties": {"a": {"$ref": ref}}, "required": ["a"]}
    )
    with (
        patch(
            "urllib.request.urlopen", side_effect=AssertionError("fetched")
        ) as urlopen,
        patch.object(
            socket.socket, "connect", side_effect=AssertionError("connected")
        ) as connect,
        patch("builtins.open", side_effect=AssertionError("opened")) as opened,
    ):
        result = run_tool(tool, {"a": 1})
    urlopen.assert_not_called()
    connect.assert_not_called()
    opened.assert_not_called()
    assert isinstance(result.content, str)


def test_s8_unresolvable_ref_skips_validation_without_network(caplog):
    tool = _kwargs_tool(
        {
            "type": "object",
            "properties": {
                "a": {"$ref": "https://x.invalid/s"},
                "b": {"type": "string"},
            },
            "required": ["a"],
        }
    )
    with (
        patch.object(
            socket.socket, "connect", side_effect=AssertionError("connected")
        ) as connect,
        patch.object(
            socket, "getaddrinfo", side_effect=AssertionError("resolved")
        ) as resolve,
    ):
        args, error = validate_tool_arguments(tool, {"a": 1, "b": "ok"})
    connect.assert_not_called()
    resolve.assert_not_called()
    # Same convention as an invalid schema: skipped with a warning.
    assert error is None and args == {"a": 1, "b": "ok"}
    assert "unresolvable $ref" in caplog.text


def test_s8_internal_defs_ref_still_validates():
    tool = _kwargs_tool(
        {
            "type": "object",
            "$defs": {
                "Item": {
                    "type": "object",
                    "properties": {"qty": {"type": "integer"}},
                    "required": ["qty"],
                }
            },
            "properties": {"item": {"$ref": "#/$defs/Item"}},
            "required": ["item"],
        }
    )
    result = run_tool(tool, {"item": {"qty": "three"}})
    assert result.is_error
    assert "item.qty" in result.content
    assert tool["_c"] == []
    assert not run_tool(tool, {"item": {"qty": 3}}).is_error
    assert tool["_c"] == [{"item": {"qty": 3}}]


def _nested_schema(depth: int) -> Dict[str, Any]:
    schema: Dict[str, Any] = {"type": "string"}
    for _ in range(depth):
        schema = {"type": "object", "properties": {"x": schema}}
    return schema


@pytest.mark.parametrize("depth", [150, 600, 5000])
def test_s8_deeply_nested_schema_does_not_crash(depth):
    tool = _kwargs_tool(_nested_schema(depth))
    result = run_tool(tool, {"x": {"x": 1}})
    assert isinstance(result.content, str)


def test_s8_recursive_schema_with_deep_arguments_is_an_error_not_a_crash():
    schema = {
        "type": "object",
        "properties": {"a": {"$ref": "#"}},
    }
    tool = _kwargs_tool(schema)
    value: Any = {}
    for _ in range(3000):
        value = {"a": value}
    result = run_tool(tool, value)
    assert result.is_error
    assert tool["_c"] == []


def test_s8_response_schema_with_unresolvable_ref_is_typed_error():
    from praval.core.exceptions import ProviderInvalidResponseError
    from praval.model_runtime import _validate_structured_content
    from praval.models import StructuredOutputConfig

    config = StructuredOutputConfig(
        schema={"type": "object", "properties": {"a": {"$ref": "file:///etc/passwd"}}}
    )
    with pytest.raises(ProviderInvalidResponseError):
        _validate_structured_content('{"a": 1}', config, provider="p", model="m")
    with pytest.raises(ProviderInvalidResponseError):
        _validate_structured_content("[" * 200_000, config, provider="p", model="m")


def test_s8_redos_pattern_on_long_string_does_not_hang_validation():
    """Strings over the cap fail before an external schema's pattern runs.

    ``re`` has no timeout, so the cap bounds how long a catastrophic pattern
    from an MCP server can backtrack. A short adversarial string (for example
    ``"a" * 34 + "!"`` against ``^(a+)+$``) is still evaluated by ``re``.
    """
    script = textwrap.dedent(
        """
        from praval.tool_execution import (
            MAX_PATTERN_STRING_CHARS,
            validate_tool_arguments,
        )

        def proxy(**kwargs):
            return "ok"

        schema = {
            "type": "object",
            "properties": {"s": {"type": "string", "pattern": "^(a+)+$"}},
        }
        _, error = validate_tool_arguments(
            {"name": "t", "function": proxy, "parameters": schema},
            {"s": "a" * MAX_PATTERN_STRING_CHARS + "!"},
        )
        assert error is not None and error.is_error, error
        assert "s: string of 10001 characters" in error.content, error.content
        assert str(MAX_PATTERN_STRING_CHARS) in error.content, error.content
        """
    )
    try:
        subprocess.run([sys.executable, "-c", script], timeout=5, check=True)
    except subprocess.TimeoutExpired:
        pytest.fail("pattern validation did not finish within 5 s")


def test_s8_pattern_still_applies_to_strings_within_the_cap():
    from praval.tool_execution import MAX_PATTERN_STRING_CHARS, validate_tool_arguments

    tool = _kwargs_tool(
        {
            "type": "object",
            "properties": {"code": {"type": "string", "pattern": "^[A-Z]+$"}},
        }
    )
    assert validate_tool_arguments(tool, {"code": "ABC"})[1] is None
    _, error = validate_tool_arguments(tool, {"code": "abc"})
    assert error is not None and "code:" in error.content
    at_cap = "A" * MAX_PATTERN_STRING_CHARS
    assert validate_tool_arguments(tool, {"code": at_cap})[1] is None
    _, error = validate_tool_arguments(tool, {"code": at_cap + "A"})
    assert error is not None and "limit for pattern checks" in error.content


def test_s8_pattern_cap_does_not_apply_to_response_schemas():
    """Response schemas come from the application, not an external server."""
    from praval.model_runtime import _validate_structured_content
    from praval.models import StructuredOutputConfig
    from praval.tool_execution import MAX_PATTERN_STRING_CHARS

    config = StructuredOutputConfig(
        schema={
            "type": "object",
            "properties": {"s": {"type": "string", "pattern": "^A+$"}},
        }
    )
    content = json.dumps({"s": "A" * (MAX_PATTERN_STRING_CHARS + 1)})
    _validate_structured_content(content, config, provider="p", model="m")


# --- S9 Untrusted Retry-After and error bodies ------------------------------


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"retry-after": "-5"}, 0.0),
        ({"retry-after": "nan"}, None),
        ({"retry-after": "inf"}, None),
        ({"retry-after": "1e309"}, None),
        ({"retry-after": "garbage"}, None),
        ({"retry-after": "Wed, 21 Oct 2015 07:28:00 GMT"}, 0.0),
        ({"retry-after": "Fri, 31 Dec 99999 23:59:59 GMT"}, None),
        ({"retry-after": "Mon, 32 Foo 2026 99:99:99 GMT"}, None),
        ({"retry-after-ms": "-1", "retry-after": "2"}, 2.0),
        ({"retry-after-ms": "nan"}, None),
        ({"retry-after": "\x00" * 10000}, None),
    ],
)
def test_s9_retry_after_values_are_clamped_or_ignored(headers, expected):
    assert parse_retry_after(headers) == expected


def test_s9_huge_retry_after_is_capped_by_runtime():
    error = ProviderError("x", retryable=True, retry_after_seconds=1e300)
    assert _retry_backoff_seconds(1, error) == 60.0
    error.retry_after_seconds = float("nan")
    assert 0.0 <= _retry_backoff_seconds(1, error) <= 60.0
    error.retry_after_seconds = -10.0
    assert _retry_backoff_seconds(1, error) == 0.0


@pytest.mark.parametrize("delay", ["1e400s", "infs", "nans", "-5s"])
def test_s9_gemini_retry_delay_is_finite_and_non_negative(delay):
    body = json.dumps(
        {
            "error": {
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": delay,
                    }
                ],
            }
        }
    ).encode()
    error = _gemini_http_error(429, body, "https://example.invalid/m")
    mapped = map_gemini_http_error(
        error, prefix="Gemini API error", model="m", redact=lambda text: text
    )
    value = mapped.retry_after_seconds
    assert value is None or (value >= 0.0 and value < float("inf"))


def test_s9_malformed_gemini_bodies_map_cleanly():
    for body in [b"\xff\xfe\x00", b"[1, 2]", b'{"error": "flat"}', b"{" * 100_000]:
        error = _gemini_http_error(500, body, "https://example.invalid/m")
        mapped = map_gemini_http_error(
            error, prefix="Gemini API error", model="m", redact=lambda text: text
        )
        assert mapped.status_code == 500
        assert len(str(mapped)) <= MAX_ERROR_BODY_CHARS + 100


# --- S10 Unsafe provider options --------------------------------------------


def _runtime_with_capturing_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client = Mock()
    success = Mock()
    success.choices = [Mock(message=Mock(content="ok", tool_calls=None))]
    success.usage = None
    client.chat.completions.create.return_value = success
    with patch("praval.providers.openai.openai.OpenAI", return_value=client):
        provider = OpenAIProvider(AgentConfig(provider="openai", model="gpt-test"))
    runtime = ModelRuntime(
        provider=provider, provider_name="openai", config=provider.config
    )
    return runtime, client


@pytest.mark.parametrize(
    "options",
    [
        {"api_key": "x"},
        {"API_KEY": "x"},
        {"Authorization": "Bearer x"},
        {"extra_headers": {"Authorization": "Bearer x"}},
        {"extra_headers": {"authorization": "Bearer x"}},
        {"extra_headers": {"api-key": "x"}},
        {"extra_headers": {"x-api-key": "x"}},
        {"extra_query": {"api_key": "x"}},
        {"extra_body": {"nested": [{"API_KEY": "x"}]}},
        {"default_headers": {"x": "y"}},
    ],
)
def test_s10_credential_options_are_blocked_at_any_depth(monkeypatch, options):
    runtime, client = _runtime_with_capturing_openai(monkeypatch)
    with pytest.raises(ProviderError, match="Unsafe provider option"):
        runtime.invoke(messages=_messages(), provider_options=options)
    client.chat.completions.create.assert_not_called()


def test_s10_benign_nested_options_still_pass_and_max_retries_is_not_sent(
    monkeypatch,
):
    runtime, client = _runtime_with_capturing_openai(monkeypatch)
    runtime.invoke(
        messages=_messages(),
        provider_options={
            "extra_headers": {"x-trace": "1"},
            "max_retries": 2,
            "metadata": {"team": "a"},
        },
    )
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["extra_headers"] == {"x-trace": "1"}
    assert "max_retries" not in kwargs


def test_s10_unsafe_options_in_agent_config_are_blocked(monkeypatch):
    runtime, client = _runtime_with_capturing_openai(monkeypatch)
    runtime.config.provider_options = {"extra_headers": {"Authorization": "x"}}
    with pytest.raises(ProviderError, match="Unsafe provider option"):
        runtime.invoke(messages=_messages())
    client.chat.completions.create.assert_not_called()


@pytest.mark.parametrize(
    "options",
    [
        {"extra_headers": {"Authorization": "Bearer x"}},
        {"API_KEY": "x"},
        {"extra_query": {"api-key": "x"}},
    ],
)
def test_s10_audio_requests_block_credential_options(monkeypatch, options):
    from praval.models import SpeechRequest, TranscriptionRequest

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client = Mock()
    with patch("praval.providers.openai.openai.OpenAI", return_value=client):
        provider = OpenAIProvider(AgentConfig(provider="openai", model="gpt-test"))
    with pytest.raises(ProviderError, match="Unsafe provider option"):
        provider.speak(
            SpeechRequest(input="hi", voice="nova", provider_options=options)
        )
    with pytest.raises(ProviderError, match="Unsafe provider option"):
        provider.transcribe(
            TranscriptionRequest(audio=b"RIFF", provider_options=options)
        )
    client.audio.speech.create.assert_not_called()
    client.audio.transcriptions.create.assert_not_called()
