"""OpenAI-compatible provider for local and third-party runtimes."""

from __future__ import annotations

import ipaddress
import os
from typing import Any, Dict
from urllib.parse import urlparse

import openai

from ..core.exceptions import ProviderError
from ..models import ProviderCapabilities
from .openai import OpenAIProvider, _redact_secrets

LOCAL_BASE_URLS = {
    "ollama": "http://localhost:11434/v1",
    "vllm": "http://localhost:8000/v1",
    "lmstudio": "http://localhost:1234/v1",
    "llama-cpp": "http://localhost:8080/v1",
    "local": "http://localhost:11434/v1",
}


class OpenAICompatibleProvider(OpenAIProvider):
    """Provider for OpenAI-compatible HTTP servers."""

    provider_name = "openai-compatible"
    capabilities = ProviderCapabilities(
        chat_completions=True,
        streaming=True,
        native_streaming=True,
        local=True,
    )

    def __init__(self, config: Any):
        self.config = config
        provider_name = str(getattr(config, "provider", "") or "").lower()
        base_url = getattr(config, "base_url", None) or LOCAL_BASE_URLS.get(
            provider_name
        )
        if not base_url:
            raise ProviderError(
                "OpenAI-compatible providers require base_url or a known local "
                "preset such as ollama, vllm, lmstudio, or llama-cpp"
            )
        self._validate_base_url(str(base_url))

        api_key_env = getattr(config, "api_key_env", None)
        api_key = os.getenv(api_key_env) if api_key_env else "local"
        try:
            client_kwargs: Dict[str, Any] = {"api_key": api_key, "base_url": base_url}
            if getattr(config, "timeout", None):
                client_kwargs["timeout"] = config.timeout
            self.client = openai.OpenAI(**client_kwargs)
            self.base_url = base_url
        except Exception as e:
            redacted_message = _redact_secrets(str(e))
            if api_key:
                redacted_message = redacted_message.replace(api_key, "***")
            raise ProviderError(
                "Failed to initialize OpenAI-compatible client: " f"{redacted_message}"
            ) from e

    def _model_name(self) -> str:
        return str(getattr(self.config, "model", None) or "local-model")

    def _validate_base_url(self, base_url: str) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"}:
            raise ProviderError("OpenAI-compatible base_url must use http or https")
        if not parsed.netloc or not parsed.hostname:
            raise ProviderError("OpenAI-compatible base_url must include a host")
        if parsed.username or parsed.password:
            raise ProviderError(
                "OpenAI-compatible base_url must not include credentials"
            )
        hostname = parsed.hostname.lower()
        if hostname in {"metadata.google.internal"}:
            raise ProviderError("OpenAI-compatible base_url targets a metadata host")
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            return
        if ip.is_link_local:
            raise ProviderError("OpenAI-compatible base_url targets a link-local host")
