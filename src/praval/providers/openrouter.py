"""OpenRouter's unified Chat Completions, reasoning, routing and charged cost."""

from __future__ import annotations

import math
import os
from dataclasses import replace
from typing import Any, Dict, List, Optional

from ..core.exceptions import ProviderError
from ..models import ModelRequest, ModelResponse, ProviderCapabilities
from .openai_compatible import OpenAICompatibleProvider
from .registry import reasoning_parameters


class OpenRouterProvider(OpenAICompatibleProvider):
    """Keep OpenRouter model IDs and unified parameters intact."""

    provider_name = "openrouter"
    capabilities = ProviderCapabilities(
        chat_completions=True,
        tools=True,
        streaming=True,
        native_streaming=True,
        tool_streaming=True,
        structured_outputs=True,
        image_input=True,
        multimodal=True,
        reasoning=True,
        reasoning_effort=True,
        reasoning_budget=True,
    )

    def __init__(self, config: Any) -> None:
        key_env = getattr(config, "api_key_env", None) or "OPENROUTER_API_KEY"
        if not os.getenv(key_env):
            raise ProviderError(f"{key_env} environment variable not set")
        super().__init__(
            replace(
                config,
                base_url=getattr(config, "base_url", None)
                or "https://openrouter.ai/api/v1",
                api_key_env=key_env,
            )
        )

    def _client_default_headers(self) -> Dict[str, str]:
        options = getattr(self.config, "provider_options", {}) or {}
        return {
            header: str(options[key])
            for key, header in (
                ("http_referer", "HTTP-Referer"),
                ("app_title", "X-OpenRouter-Title"),
            )
            if options.get(key)
        }

    def _uses_max_completion_tokens(self, model: str) -> bool:
        # OpenRouter owns translation to each upstream provider's token limit.
        return False

    def _base_chat_completion_params(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: Optional[float],
        max_output_tokens: int,
    ) -> Dict[str, Any]:
        params = super()._base_chat_completion_params(
            model=model,
            messages=messages,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        options = getattr(self.config, "provider_options", {}) or {}
        routing = options.get("routing", {})
        if not isinstance(routing, dict):
            raise ProviderError("OpenRouter routing must be a dict")
        params["extra_body"] = {"provider": {**routing, "require_parameters": True}}
        return params

    def _use_responses_api(self, request: ModelRequest) -> bool:
        if super()._use_responses_api(request):
            raise ProviderError(
                "The OpenRouter adapter uses Chat Completions; "
                "remove the Responses endpoint override"
            )
        return False

    def _parameter_repair(
        self, exc: BaseException, params: Dict[str, Any]
    ) -> Optional[Dict[str, Optional[str]]]:
        # require_parameters must remain strict; never negotiate away caller intent.
        return None

    def _chat_completion_params(
        self,
        request: ModelRequest,
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        reserved = {"routing", "http_referer", "app_title"}
        prepared = request.model_copy(
            update={
                "provider_options": {
                    k: v
                    for k, v in request.provider_options.items()
                    if k not in reserved
                }
            }
        )
        params = super()._chat_completion_params(prepared, tools=tools, stream=stream)
        params.pop("reasoning_effort", None)
        if params.get("temperature") is None:
            params.pop("temperature", None)
        body = dict(params.get("extra_body") or {})
        extra = request.provider_options.get("extra_body", {})
        if not isinstance(extra, dict):
            raise ProviderError("OpenRouter extra_body must be a dict")
        body.update(extra)
        routing = request.provider_options.get("routing", body.get("provider", {}))
        if not isinstance(routing, dict):
            raise ProviderError("OpenRouter routing must be a dict")
        body["provider"] = {**routing, "require_parameters": True}
        reasoning = dict(reasoning_parameters(request))
        if request.reasoning is not None:
            if request.reasoning.effort is not None:
                reasoning.pop("enabled", None)
                reasoning["effort"] = request.reasoning.effort
            if request.reasoning.budget_tokens is not None:
                reasoning["max_tokens"] = request.reasoning.budget_tokens
            if reasoning:
                body["reasoning"] = reasoning
        params["extra_body"] = body
        return params

    def _request_usage_response(self, response: Any) -> ModelResponse:
        result = super()._request_usage_response(response)
        usage = self._event_value(response, "usage", None)
        value = self._event_value(usage, "cost", None)
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        ):
            result.metadata["reported_cost_usd"] = float(value)
        return result

    def _chat_model_response(
        self, response: Any, call_params: Dict[str, Any]
    ) -> ModelResponse:
        result = super()._chat_model_response(response, call_params)
        result.metadata.update(self._request_usage_response(response).metadata)
        return result
