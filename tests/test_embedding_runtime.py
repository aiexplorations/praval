"""Tests for provider-neutral embedding runtime."""

import builtins
import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from praval.core.exceptions import ProviderError
from praval.embeddings import DEFAULT_EMBEDDING_DIMENSIONS, EmbeddingRuntime
from praval.models import ContentPart, EmbeddingResponse


def test_embedding_runtime_fallback_is_deterministic():
    runtime = EmbeddingRuntime(provider="sentence-transformers", dimensions=16)
    runtime._sentence_model_loaded = True
    runtime._sentence_model = None

    first = runtime.embed_text("Praval memory embeddings")
    second = runtime.embed_text("Praval memory embeddings")

    assert first == second
    assert len(first) == 16
    assert any(value != 0 for value in first)


def test_embedding_runtime_returns_neutral_response_for_batch():
    runtime = EmbeddingRuntime(provider="sentence-transformers", dimensions=8)
    runtime._sentence_model_loaded = True
    runtime._sentence_model = None

    response = runtime.embed(["alpha", "beta"])

    assert isinstance(response, EmbeddingResponse)
    assert response.provider == "sentence-transformers"
    assert response.dimensions == 8
    assert len(response.embeddings) == 2


@pytest.mark.filterwarnings("ignore")
def test_openai_compatible_embedding_runtime_uses_sdk_client():
    mock_client = Mock()
    mock_client.embeddings.create.return_value = SimpleNamespace(
        data=[
            SimpleNamespace(embedding=[0.1, 0.2, 0.3]),
            SimpleNamespace(embedding=[0.4, 0.5, 0.6]),
        ]
    )

    with patch("openai.OpenAI", return_value=mock_client) as mock_openai:
        runtime = EmbeddingRuntime(
            provider="openai-compatible",
            model="nomic-embed-text",
            dimensions=3,
            provider_options={"base_url": "http://localhost:11434/v1"},
        )
        response = runtime.embed(["one", "two"])

    mock_openai.assert_called_once_with(
        base_url="http://localhost:11434/v1", api_key="local"
    )
    mock_client.embeddings.create.assert_called_once_with(
        model="nomic-embed-text",
        input=["one", "two"],
        dimensions=3,
    )
    assert response.embeddings == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


def test_embedding_runtime_rejects_unknown_provider():
    runtime = EmbeddingRuntime(provider="unknown-provider")

    with pytest.raises(ProviderError, match="Unsupported embedding provider"):
        runtime.embed("hello")


def test_embedding_runtime_dimension_defaults_and_empty_text():
    assert EmbeddingRuntime.default_dimensions("local", "custom-model") == 384
    assert EmbeddingRuntime.default_dimensions("unknown") == 384
    assert (
        EmbeddingRuntime.default_dimensions("openai")
        == DEFAULT_EMBEDDING_DIMENSIONS["openai"]
    )

    runtime = EmbeddingRuntime(provider="local", dimensions=4)
    runtime._sentence_model_loaded = True
    runtime._sentence_model = None
    assert runtime.embed_text("") == [0.0, 0.0, 0.0, 0.0]


def test_sentence_transformer_model_encodes_array_and_list_results():
    model = Mock()
    array_result = Mock()
    array_result.tolist.return_value = [0.1, 0.2]
    model.encode.return_value = [array_result, (0.3, 0.4)]
    runtime = EmbeddingRuntime(provider="sentence-transformers", dimensions=2)
    runtime._sentence_model_loaded = True
    runtime._sentence_model = model

    response = runtime.embed(["one", "two"])

    assert response.embeddings == [[0.1, 0.2], [0.3, 0.4]]
    model.encode.assert_called_once_with(["one", "two"], convert_to_tensor=False)


def test_sentence_transformer_load_updates_dimensions_and_falls_back_on_failure():
    model = Mock()
    model.get_sentence_embedding_dimension.return_value = 12
    module = SimpleNamespace(SentenceTransformer=Mock(return_value=model))
    with patch.dict(sys.modules, {"sentence_transformers": module}):
        runtime = EmbeddingRuntime(provider="sentence-transformers")
        assert runtime._load_sentence_model() is model
        assert runtime.dimensions == 12
        assert runtime._load_sentence_model() is model

    failed_module = SimpleNamespace(
        SentenceTransformer=Mock(side_effect=RuntimeError("model unavailable"))
    )
    with patch.dict(sys.modules, {"sentence_transformers": failed_module}):
        failed = EmbeddingRuntime(provider="sentence-transformers")
        assert failed._load_sentence_model() is None


@pytest.mark.filterwarnings("ignore")
def test_openai_embedding_uses_api_key_and_can_omit_dimensions():
    mock_client = Mock()
    mock_client.embeddings.create.return_value = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.2, 0.4])]
    )
    with patch("openai.OpenAI", return_value=mock_client) as mock_openai:
        response = EmbeddingRuntime(
            provider="openai",
            model="text-embedding-test",
            dimensions=2,
            provider_options={"api_key": "test-key", "send_dimensions": False},
        ).embed("hello")

    mock_openai.assert_called_once_with(api_key="test-key")
    mock_client.embeddings.create.assert_called_once_with(
        model="text-embedding-test", input=["hello"]
    )
    assert response.embeddings == [[0.2, 0.4]]


def test_openai_embedding_reports_missing_sdk():
    real_import = builtins.__import__

    def import_without_openai(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=import_without_openai):
        with pytest.raises(ProviderError, match="openai is required"):
            EmbeddingRuntime(provider="openai").embed("hello")


def test_gemini_embedding_requires_credentials(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        EmbeddingRuntime(provider="gemini").embed("hello")


def test_gemini_embedding_serializes_multimodal_parts(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    responses = [
        {"embedding": {"values": [0.1, 0.2]}},
        {"embeddings": [{"values": [0.3, 0.4]}]},
        {"embedding": {"values": [0.5, 0.6]}},
    ]
    requests = []

    def fake_urlopen(request):
        requests.append(request)
        response = Mock()
        response.read.return_value = json.dumps(responses[len(requests) - 1]).encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    runtime = EmbeddingRuntime(
        provider="gemini",
        model="gemini-embed-test",
        dimensions=2,
        provider_options={"base_url": "https://gemini.test/v1beta/"},
    )
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        response = runtime.embed(
            [
                ContentPart.text_part("hello"),
                ContentPart.audio_base64("AAA", "audio/mpeg"),
                ContentPart.file_url("gs://bucket/file.pdf", "application/pdf"),
            ]
        )

    assert response.embeddings == [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
    assert all(
        request.full_url.startswith(
            "https://gemini.test/v1beta/models/gemini-embed-test:embedContent"
        )
        for request in requests
    )
    payloads = [json.loads(request.data.decode()) for request in requests]
    assert payloads[0]["content"]["parts"] == [{"text": "hello"}]
    assert payloads[1]["content"]["parts"][0]["inlineData"]["data"] == "AAA"
    assert payloads[2]["content"]["parts"][0]["fileData"]["fileUri"] == (
        "gs://bucket/file.pdf"
    )
    assert all(payload["output_dimensionality"] == 2 for payload in payloads)


def test_embedding_content_part_text_conversion_covers_url_and_data():
    assert EmbeddingRuntime._input_to_text(ContentPart.text_part("text")) == "text"
    assert EmbeddingRuntime._input_to_text(ContentPart.image_url("https://image")) == (
        "https://image"
    )
    assert (
        EmbeddingRuntime._input_to_text(
            ContentPart.file_data("AAA", "application/octet-stream")
        )
        == "AAA"
    )
    assert EmbeddingRuntime._input_to_text(42) == "42"
    runtime = EmbeddingRuntime(provider="gemini")
    assert runtime._gemini_part(ContentPart(type="unknown", data="opaque")) == {
        "text": "opaque"
    }
