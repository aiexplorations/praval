"""Edge-case contracts for the Gemini 0.8 provider adapter."""

import urllib.error
from unittest.mock import Mock, patch

import pytest

from praval.core.agent import AgentConfig
from praval.core.exceptions import ProviderError
from praval.models import (
    ContentPart,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ReasoningConfig,
    StructuredOutputConfig,
    ToolResult,
)
from praval.providers.gemini import GeminiProvider, _redact_secret


@pytest.fixture
def gemini_provider(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    return GeminiProvider(
        AgentConfig(
            provider="gemini",
            model="gemini-test",
            base_url="https://gemini.test/v1beta",
            max_tokens=100,
        )
    )


def test_gemini_requires_key_for_default_endpoint_and_redacts(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="environment variable not set"):
        GeminiProvider(AgentConfig(provider="gemini"))
    assert _redact_secret("", "secret") == ""
    assert _redact_secret("bad secret", "secret") == "bad ***"


def test_gemini_build_payload_applies_system_schema_reasoning_and_options(
    gemini_provider,
):
    request = ModelRequest(
        provider="gemini",
        model="gemini-test",
        messages=[ModelMessage(role="user", content="x")],
        temperature=0.2,
        max_output_tokens=50,
        response_schema=StructuredOutputConfig(schema={"type": "object"}),
        reasoning=ReasoningConfig(budget_tokens=20),
        provider_options={"generation_config": {"topP": 0.8}},
    )
    payload = gemini_provider._build_payload(
        [
            {"role": "system", "content": "system"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "question"},
        ],
        None,
        request=request,
    )
    assert payload["systemInstruction"] == {"parts": [{"text": "system"}]}
    assert payload["contents"][0]["role"] == "model"
    assert payload["generationConfig"] == {
        "temperature": 0.2,
        "maxOutputTokens": 50,
        "responseMimeType": "application/json",
        "responseSchema": {"type": "object"},
        "thinkingConfig": {"thinkingBudget": 20},
        "topP": 0.8,
    }


def test_gemini_generation_and_continuation_errors_are_provider_errors(
    gemini_provider,
):
    with patch.object(
        gemini_provider, "_post_json", side_effect=urllib.error.URLError("offline")
    ):
        with pytest.raises(ProviderError, match="Gemini API error"):
            gemini_provider.generate([{"role": "user", "content": "x"}])
    with patch.object(gemini_provider, "_post_json", side_effect=RuntimeError("bad")):
        with pytest.raises(ProviderError, match="Gemini API error"):
            gemini_provider.invoke(
                ModelRequest(messages=[ModelMessage(role="user", content="x")])
            )

    request = ModelRequest(messages=[ModelMessage(role="user", content="x")])
    with pytest.raises(ProviderError, match="continuation state"):
        gemini_provider.continue_with_tool_results(request, ModelResponse(), [])
    response = ModelResponse(metadata={"gemini_payload": {}, "gemini_contents": []})
    with patch.object(gemini_provider, "_post_json", side_effect=RuntimeError("bad")):
        with pytest.raises(ProviderError, match="Gemini API error"):
            gemini_provider.continue_with_tool_results(request, response, [])


def test_gemini_stream_parser_handles_sse_blanks_and_done(gemini_provider):
    response = Mock()
    response.__iter__ = Mock(
        return_value=iter(
            [
                b"\n",
                b'data: {"candidates":[{"content":{"parts":[{"text":"hi"}]}}]}\n',
                b"data: [DONE]\n",
                b'{"ignored":true}\n',
            ]
        )
    )
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        chunks = list(
            gemini_provider._post_stream(
                "streamGenerateContent", {"contents": []}, timeout=3
            )
        )
    assert len(chunks) == 1
    assert gemini_provider._extract_text(chunks[0]) == "hi"
    assert "alt=sse" in urlopen.call_args.args[0].full_url
    assert "key=" not in urlopen.call_args.args[0].full_url


def test_gemini_stream_emits_error_before_raising(gemini_provider):
    with patch.object(gemini_provider, "_post_stream", side_effect=RuntimeError("bad")):
        stream = gemini_provider.stream(
            ModelRequest(messages=[ModelMessage(role="user", content="x")], stream=True)
        )
        assert next(stream).type == "error"
        with pytest.raises(ProviderError, match="streaming error"):
            next(stream)


def test_gemini_content_mime_tool_schema_and_function_call_edges(gemini_provider):
    parts = gemini_provider._content_to_parts(
        [
            ContentPart.image_url("https://image"),
            ContentPart.audio_base64("AAA"),
            ContentPart.video_url("https://video"),
            ContentPart.file_data("BBB", "application/pdf"),
        ]
    )
    assert parts[0]["fileData"]["mimeType"] == "image/png"
    assert parts[1]["inlineData"]["mimeType"] == "audio/wav"
    assert parts[2]["fileData"]["mimeType"] == "video/mp4"
    with pytest.raises(ProviderError, match="cannot serialize"):
        gemini_provider._content_to_parts([ContentPart(type="unknown")])

    assert gemini_provider._gemini_parameter_schema("bad") == {"type": "STRING"}
    assert gemini_provider._gemini_parameter_schema(
        {"type": "int", "description": "count", "enum": [1, 2]}
    ) == {"type": "INTEGER", "description": "count", "enum": [1, 2]}
    calls = gemini_provider._extract_function_calls(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"functionCall": "bad"},
                            {"function_call": {"name": ""}},
                            {"function_call": {"name": "lookup", "args": {"q": 1}}},
                        ]
                    }
                }
            ]
        }
    )
    assert calls[0]["name"] == "lookup"


def test_gemini_error_tool_results_and_legacy_followup_fallback(gemini_provider):
    part = gemini_provider._function_response_part(
        ToolResult(tool_call_id="call", name="lookup", content="failed", is_error=True)
    )
    assert part["functionResponse"]["response"]["is_error"] is True

    def lookup() -> str:
        return "cached"

    with patch.object(
        gemini_provider, "_post_json", side_effect=RuntimeError("offline")
    ):
        response = gemini_provider._handle_function_calls(
            function_calls=[{"id": "call", "name": "lookup", "args": {}, "raw": {}}],
            available_tools=[{"function": lookup, "description": "Lookup"}],
            messages=[{"role": "user", "content": "lookup"}],
            request=None,
            hitl_context=None,
        )
    assert response.content == "cached"
    assert response.raw is None
