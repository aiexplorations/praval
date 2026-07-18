"""Provider-neutral embedding runtime for Praval memory and RAG paths."""

from __future__ import annotations

import hashlib
import json
import math
import os
import urllib.request
from typing import Any, Dict, Iterable, List, Optional

from .core.exceptions import ProviderError
from .models import ContentPart, EmbeddingRequest, EmbeddingResponse

DEFAULT_EMBEDDING_MODELS = {
    "sentence-transformers": "all-MiniLM-L6-v2",
    "local": "all-MiniLM-L6-v2",
    "openai": "text-embedding-3-small",
    "openai-compatible": "text-embedding-3-small",
    "gemini": "gemini-embedding-2",
}

DEFAULT_EMBEDDING_DIMENSIONS = {
    "sentence-transformers": 384,
    "local": 384,
    "openai": 1536,
    "openai-compatible": 1536,
    "gemini": 768,
}


class EmbeddingRuntime:
    """Execute embedding requests through a configured provider."""

    def __init__(
        self,
        *,
        provider: str = "sentence-transformers",
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
        provider_options: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.provider = self._normalize_provider(provider)
        self.model = model or DEFAULT_EMBEDDING_MODELS.get(self.provider)
        self.dimensions = dimensions or DEFAULT_EMBEDDING_DIMENSIONS.get(
            self.provider, 384
        )
        self.provider_options = dict(provider_options or {})
        self._sentence_model: Any = None
        self._sentence_model_loaded = False

    def embed(self, inputs: Any) -> EmbeddingResponse:
        """Embed one input or a list of inputs."""
        request = self._build_request(inputs)
        provider = self._normalize_provider(request.provider or self.provider)
        if provider in {"sentence-transformers", "local"}:
            embeddings = self._embed_sentence_transformers(request.inputs)
            raw = None
        elif provider in {"openai", "openai-compatible"}:
            embeddings, raw = self._embed_openai_compatible(request, provider)
        elif provider == "gemini":
            embeddings, raw = self._embed_gemini(request)
        else:
            raise ProviderError(f"Unsupported embedding provider: {provider}")

        dimensions = len(embeddings[0]) if embeddings else request.dimensions
        return EmbeddingResponse(
            embeddings=embeddings,
            provider=provider,
            model=request.model,
            dimensions=dimensions,
            raw=raw,
        )

    def embed_text(self, text: str) -> List[float]:
        """Embed a single text input and return the vector."""
        response = self.embed(text)
        return response.embeddings[0] if response.embeddings else []

    @classmethod
    def default_dimensions(cls, provider: str, model: Optional[str] = None) -> int:
        """Return the default dimensionality for an embedding provider."""
        normalized = cls._normalize_provider(provider)
        if normalized in {"sentence-transformers", "local"} and model:
            return DEFAULT_EMBEDDING_DIMENSIONS["sentence-transformers"]
        return DEFAULT_EMBEDDING_DIMENSIONS.get(normalized, 384)

    def _build_request(self, inputs: Any) -> EmbeddingRequest:
        values = list(inputs) if self._is_sequence(inputs) else [inputs]
        return EmbeddingRequest(
            inputs=values,
            provider=self.provider,
            model=self.model,
            dimensions=self.dimensions,
            provider_options=dict(self.provider_options),
        )

    @staticmethod
    def _normalize_provider(provider: str) -> str:
        return provider.strip().lower().replace("_", "-")

    @staticmethod
    def _is_sequence(value: Any) -> bool:
        return isinstance(value, (list, tuple)) and not isinstance(value, ContentPart)

    def _embed_sentence_transformers(self, inputs: List[Any]) -> List[List[float]]:
        model = self._load_sentence_model()
        if model is None:
            texts = [self._input_to_text(item) for item in inputs]
            return [self._fallback_embedding(text) for text in texts]
        embeddings = model.encode(
            [self._input_to_text(item) for item in inputs],
            convert_to_tensor=False,
        )
        return [
            embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
            for embedding in embeddings
        ]

    def _load_sentence_model(self) -> Any:
        if self._sentence_model_loaded:
            return self._sentence_model
        self._sentence_model_loaded = True
        try:
            from sentence_transformers import SentenceTransformer

            self._sentence_model = SentenceTransformer(self.model)
            if hasattr(self._sentence_model, "get_sentence_embedding_dimension"):
                self.dimensions = int(
                    self._sentence_model.get_sentence_embedding_dimension()
                )
        except Exception:
            self._sentence_model = None
        return self._sentence_model

    def _embed_openai_compatible(
        self,
        request: EmbeddingRequest,
        provider: str,
    ) -> tuple[List[List[float]], Any]:
        try:
            import openai
        except ImportError as exc:
            raise ProviderError("openai is required for OpenAI embeddings") from exc

        client_kwargs: Dict[str, Any] = {}
        if request.provider_options.get("api_key"):
            client_kwargs["api_key"] = request.provider_options["api_key"]
        if provider == "openai-compatible":
            client_kwargs["base_url"] = request.provider_options.get("base_url")
            client_kwargs["api_key"] = client_kwargs.get(
                "api_key", request.provider_options.get("api_key", "local")
            )
        client = openai.OpenAI(**{k: v for k, v in client_kwargs.items() if v})
        call_kwargs: Dict[str, Any] = {
            "model": request.model,
            "input": [self._input_to_text(item) for item in request.inputs],
        }
        if request.dimensions and request.provider_options.get("send_dimensions", True):
            call_kwargs["dimensions"] = request.dimensions
        response = client.embeddings.create(**call_kwargs)
        embeddings = [list(item.embedding) for item in response.data]
        return embeddings, response

    def _embed_gemini(
        self, request: EmbeddingRequest
    ) -> tuple[List[List[float]], List[Dict[str, Any]]]:
        api_key = (
            request.provider_options.get("api_key")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        if not api_key:
            raise ProviderError("GEMINI_API_KEY or GOOGLE_API_KEY is required")
        base_url = request.provider_options.get(
            "base_url", "https://generativelanguage.googleapis.com/v1beta"
        ).rstrip("/")
        model = request.model or DEFAULT_EMBEDDING_MODELS["gemini"]
        raw_responses: List[Dict[str, Any]] = []
        embeddings: List[List[float]] = []
        for item in request.inputs:
            payload: Dict[str, Any] = {"content": {"parts": [self._gemini_part(item)]}}
            if request.dimensions:
                payload["output_dimensionality"] = request.dimensions
            url = f"{base_url}/models/{model}:embedContent?key={api_key}"
            http_request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(http_request) as response:
                data = json.loads(response.read().decode("utf-8"))
            raw_responses.append(data)
            embeddings.append(
                list(
                    data.get("embedding", {}).get("values")
                    or data.get("embeddings", [{}])[0].get("values")
                    or []
                )
            )
        return embeddings, raw_responses

    def _gemini_part(self, item: Any) -> Dict[str, Any]:
        if isinstance(item, ContentPart):
            if item.type == "text":
                return {"text": item.text or ""}
            if item.type in {"image_base64", "audio_base64", "video_base64", "file"}:
                return {
                    "inlineData": {
                        "mimeType": item.mime_type or "application/octet-stream",
                        "data": item.data or "",
                    }
                }
            if item.type in {"image_url", "audio_url", "video_url", "file_url"}:
                return {
                    "fileData": {
                        "mimeType": item.mime_type or "application/octet-stream",
                        "fileUri": item.url or "",
                    }
                }
        return {"text": self._input_to_text(item)}

    @staticmethod
    def _input_to_text(item: Any) -> str:
        if isinstance(item, ContentPart):
            if item.text is not None:
                return item.text
            if item.url is not None:
                return item.url
            return item.data or ""
        return str(item)

    def _fallback_embedding(self, text: str) -> List[float]:
        dimensions = int(self.dimensions or 384)
        vector = [0.0] * dimensions
        tokens = self._fallback_tokens(text)
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    @staticmethod
    def _fallback_tokens(text: str) -> Iterable[str]:
        cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
        return [token for token in cleaned.split() if token]


__all__ = [
    "DEFAULT_EMBEDDING_DIMENSIONS",
    "DEFAULT_EMBEDDING_MODELS",
    "EmbeddingRuntime",
]
