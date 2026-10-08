"""Explicit, bounded provider catalogue discovery for application setup."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any, Dict, List
from urllib.parse import quote

from ..core.exceptions import ProviderError
from ..models import ProviderCapabilities, ProviderProfile
from .errors import map_provider_exception

if TYPE_CHECKING:
    from .registry import ProviderRegistry

logger = logging.getLogger(__name__)
MAX_CATALOG_BYTES = 16 * 1024 * 1024


def fetch_json(
    url: str, *, headers: Dict[str, str], timeout: float, payload: Any = None
) -> Dict[str, Any]:
    """Read bounded JSON without putting credentials in query strings."""
    request = urllib.request.Request(
        url,
        headers={"Content-Type": "application/json", **headers},
        data=json.dumps(payload).encode() if payload is not None else None,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(MAX_CATALOG_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise map_provider_exception(
            exc, message=f"Model catalogue HTTP {exc.code}"
        ) from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderError("Model catalogue could not be reached") from exc
    if len(body) > MAX_CATALOG_BYTES:
        raise ProviderError("Model catalogue exceeds the response size limit")
    try:
        value = json.loads(body)
    except (ValueError, RecursionError) as exc:
        raise ProviderError("Model catalogue returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise ProviderError("Model catalogue must be a JSON object")
    return value


def _positive(value: Any) -> int | None:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
        else None
    )


def _catalog_list(value: Any) -> List[Any]:
    if not isinstance(value, list):
        raise ProviderError("Model catalogue entries must be a list")
    if len(value) > 10000:
        raise ProviderError("Model catalogue exceeds the entry limit")
    return value


def _catalog_object(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ProviderError("Model catalogue metadata must be an object")
    return value


def discover_models(
    provider: str, config: Any, registry: ProviderRegistry
) -> List[ProviderProfile]:
    """Fetch model names, limits and declared capabilities from owning APIs."""
    name = registry.canonical_provider(provider) or provider
    timeout = float(getattr(config, "timeout", None) or 10)
    base = getattr(config, "base_url", None)
    options = getattr(config, "provider_options", {}) or {}
    key_env = getattr(config, "api_key_env", None)
    if provider in {"ollama", "local"}:
        from .openai_compatible import OpenAICompatibleProvider

        base = str(base or "http://localhost:11434/v1").rstrip("/").removesuffix("/v1")
        OpenAICompatibleProvider._validate_base_url(base)
        headers = (
            {"Authorization": "Bearer " + os.environ[key_env]}
            if key_env and os.getenv(key_env)
            else {}
        )
        tags = fetch_json(base + "/api/tags", headers=headers, timeout=timeout)
        loaded = fetch_json(base + "/api/ps", headers=headers, timeout=timeout)
        loaded_contexts = {
            item.get("name"): _positive(item.get("context_length"))
            for item in _catalog_list(loaded.get("models", []))
            if isinstance(item, dict)
        }
        rows = _catalog_list(tags.get("models", []))
        profiles = []
        selected = getattr(config, "model", None)
        for item in rows:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            model = item["name"]
            if (
                options.get("discover_model") is True
                and selected
                and model not in {selected, selected + ":latest"}
            ):
                continue
            info = fetch_json(
                base + "/api/show",
                headers=headers,
                timeout=timeout,
                payload={"model": model},
            )
            declared = _catalog_list(info.get("capabilities", []))
            model_info = _catalog_object(info.get("model_info", {}))
            limits = [
                _positive(v)
                for k, v in model_info.items()
                if k.endswith(".context_length")
            ]
            context = max((v for v in limits if v is not None), default=None)
            profiles.append(
                ProviderProfile(
                    provider=provider,
                    model=(
                        selected
                        if options.get("discover_model") is True and selected
                        else model
                    ),
                    local_preset="ollama",
                    endpoint="chat.completions",
                    context_window=context,
                    max_output_tokens=loaded_contexts.get(model) or context,
                    capabilities=ProviderCapabilities(
                        chat_completions=True,
                        streaming=True,
                        native_streaming=True,
                        local=True,
                        tools="tools" in declared,
                        image_input="vision" in declared,
                        multimodal="vision" in declared,
                        reasoning="thinking" in declared,
                    ),
                    metadata={
                        "loaded_context_window": loaded_contexts.get(model),
                        "capabilities": declared,
                        "catalogue_source": base + "/api/show",
                    },
                    pricing={"cost": "0", "currency": "USD"},
                )
            )
            required = options.get("required_context_tokens")
            loaded_context = loaded_contexts.get(model)
            if required is not None and (
                not isinstance(required, int)
                or isinstance(required, bool)
                or required <= 0
            ):
                raise ProviderError(
                    "required_context_tokens must be a positive integer"
                )
            if required and loaded_context and loaded_context < required:
                logger.warning(
                    "Ollama model %s is loaded with %s context tokens; "
                    "the application requires %s. Configure num_ctx in a "
                    "Modelfile and reload the model.",
                    model,
                    loaded_context,
                    required,
                )
        if selected and options.get("discover_model") is True and not profiles:
            raise ProviderError(
                f"Ollama model '{selected}' is not installed; choose an installed model"
            )
        return profiles

    defaults = {
        "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
        "anthropic": ("https://api.anthropic.com/v1", "ANTHROPIC_API_KEY"),
        "gemini": (
            "https://generativelanguage.googleapis.com/v1beta",
            "GEMINI_API_KEY",
        ),
        "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    }
    if name not in defaults:
        raise ProviderError(f"Provider '{provider}' does not expose model discovery")
    default_base, default_env = defaults[name]
    key = os.getenv(key_env or default_env) or (
        os.getenv("GOOGLE_API_KEY") if name == "gemini" else None
    )
    if not key and name != "openrouter":
        raise ProviderError(f"{key_env or default_env} is required for model discovery")
    headers = {"Authorization": "Bearer " + key} if key else {}
    if name == "anthropic":
        headers = {"x-api-key": key or "", "anthropic-version": "2023-06-01"}
    elif name == "gemini":
        headers = {"x-goog-api-key": key or ""}
    url = str(base or default_base).rstrip("/") + "/models"
    rows = []
    for _ in range(100):
        data = fetch_json(url, headers=headers, timeout=timeout)
        batch = _catalog_list(data.get("models" if name == "gemini" else "data", []))
        rows.extend(batch)
        if len(rows) > 10000:
            raise ProviderError("Model catalogue exceeds the entry limit")
        token = (
            data.get("nextPageToken")
            if name == "gemini"
            else data.get("last_id") if data.get("has_more") else None
        )
        if not token:
            break
        url = (
            str(base or default_base).rstrip("/")
            + "/models?"
            + ("pageToken=" if name == "gemini" else "after_id=")
            + quote(str(token), safe="")
        )
    else:
        raise ProviderError("Model catalogue exceeds the page limit")
    profiles = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        model = item.get("name" if name == "gemini" else "id")
        if not isinstance(model, str) or not model:
            continue
        if name == "gemini":
            model = model.removeprefix("models/")
            if "generateContent" not in _catalog_list(
                item.get("supportedGenerationMethods", [])
            ):
                continue
        existing = registry.get_profile(provider, model)
        profile = (
            existing.model_copy(deep=True)
            if existing and existing.model != "*"
            else ProviderProfile(
                provider=provider,
                model=model,
                capabilities=registry.get_registration(
                    provider
                ).capabilities.model_copy(deep=True),
            )
        )
        profile.model = model
        profile.display_name = (
            item.get("displayName") or item.get("display_name") or item.get("name")
        )
        profile.context_window = (
            _positive(item.get("inputTokenLimit") or item.get("context_length"))
            or profile.context_window
        )
        per_request = _catalog_object(item.get("top_provider") or {})
        profile.max_output_tokens = (
            _positive(
                item.get("outputTokenLimit") or per_request.get("max_completion_tokens")
            )
            or profile.max_output_tokens
        )
        if name == "openrouter":
            profile.supported_parameters = [
                v
                for v in _catalog_list(item.get("supported_parameters", []))
                if isinstance(v, str)
            ]
            profile.pricing = {
                str(k): str(v)
                for k, v in _catalog_object(item.get("pricing") or {}).items()
            }
            profile.capabilities.tools = "tools" in profile.supported_parameters
            profile.capabilities.structured_outputs = (
                "response_format" in profile.supported_parameters
            )
            profile.capabilities.reasoning = "reasoning" in profile.supported_parameters
            profile.capabilities.reasoning_effort = profile.capabilities.reasoning
            architecture = _catalog_object(item.get("architecture") or {})
            profile.capabilities.image_input = "image" in _catalog_list(
                architecture.get("input_modalities", [])
            )
            profile.capabilities.multimodal = profile.capabilities.image_input
            if profile.capabilities.reasoning:
                profile.reasoning_levels = {
                    "none": {"enabled": False},
                    **{level: {"effort": level} for level in ("low", "medium", "high")},
                }
                profile.reasoning_source = (
                    "https://openrouter.ai/docs/guides/best-practices/reasoning-tokens"
                )
        profile.metadata["catalogue_source"] = (
            str(base or default_base).rstrip("/") + "/models"
        )
        profiles.append(profile)
    return profiles
