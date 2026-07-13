"""Security and downgrade tests for OpenAI-compatible local providers."""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import pytest

from praval.core.agent import AgentConfig
from praval.core.exceptions import ProviderError
from praval.models import ModelMessage, ModelRequest
from praval.providers.openai_compatible import OpenAICompatibleProvider


class FakeOpenAICompatibleHandler(BaseHTTPRequestHandler):
    """Tiny OpenAI-compatible server for offline local-provider tests."""

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if payload.get("stream"):
            self._write_stream()
        else:
            self._write_json(
                {
                    "id": "chatcmpl-test",
                    "object": "chat.completion",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "local hello",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 1,
                        "completion_tokens": 2,
                        "total_tokens": 3,
                    },
                }
            )

    def log_message(self, format, *args):
        return

    def _write_json(self, body):
        data = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _write_stream(self):
        chunks = [
            {
                "id": "chatcmpl-test",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": "local-model",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": "local "},
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "chatcmpl-test",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": "local-model",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": "stream"},
                        "finish_reason": "stop",
                    }
                ],
            },
        ]
        body = (
            "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
            + "data: [DONE]\n\n"
        )
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def fake_openai_compatible_server():
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeOpenAICompatibleHandler)
    except PermissionError:
        pytest.skip("loopback sockets are blocked in this environment")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@patch.dict(os.environ, {}, clear=True)
@patch("openai.OpenAI")
def test_openai_compatible_default_capabilities_are_conservative(mock_openai):
    provider = OpenAICompatibleProvider(AgentConfig(provider="ollama", model="llama3"))

    assert provider.capabilities.local is True
    assert provider.capabilities.streaming is True
    assert provider.capabilities.tools is False
    assert provider.capabilities.structured_outputs is False
    assert provider.capabilities.reasoning is False
    mock_openai.assert_called_once()


@pytest.mark.parametrize(
    "base_url,error",
    [
        ("file:///tmp/server", "http or https"),
        ("http://user:pass@localhost:11434/v1", "credentials"),
        ("http://169.254.169.254/latest/meta-data", "link-local"),
        ("http://metadata.google.internal/computeMetadata/v1", "metadata host"),
    ],
)
@patch.dict(os.environ, {}, clear=True)
@patch("openai.OpenAI")
def test_openai_compatible_rejects_unsafe_base_urls(
    mock_openai,
    base_url,
    error,
):
    with pytest.raises(ProviderError, match=error):
        OpenAICompatibleProvider(
            AgentConfig(provider="openai-compatible", model="x", base_url=base_url)
        )

    mock_openai.assert_not_called()


@patch.dict(os.environ, {}, clear=True)
@patch("openai.OpenAI")
def test_openai_compatible_allows_explicit_https_server(mock_openai):
    provider = OpenAICompatibleProvider(
        AgentConfig(
            provider="openai-compatible",
            model="x",
            base_url="https://models.example.com/v1",
        )
    )

    assert provider.base_url == "https://models.example.com/v1"
    mock_openai.assert_called_once()


@patch.dict(os.environ, {}, clear=True)
def test_openai_compatible_fake_server_chat_completion(
    fake_openai_compatible_server,
):
    provider = OpenAICompatibleProvider(
        AgentConfig(
            provider="openai-compatible",
            model="local-model",
            base_url=fake_openai_compatible_server,
        )
    )

    response = provider.generate([{"role": "user", "content": "hello"}])

    assert response == "local hello"


@patch.dict(os.environ, {}, clear=True)
def test_openai_compatible_fake_server_streaming(
    fake_openai_compatible_server,
):
    provider = OpenAICompatibleProvider(
        AgentConfig(
            provider="openai-compatible",
            model="local-model",
            base_url=fake_openai_compatible_server,
        )
    )
    request = ModelRequest(
        provider="openai-compatible",
        model="local-model",
        messages=[ModelMessage(role="user", content="hello")],
        stream=True,
    )

    events = list(provider.stream(request))

    assert [event.type for event in events] == ["delta", "delta", "final"]
    assert events[-1].response.content == "local stream"
