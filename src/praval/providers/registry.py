"""Provider registry and model profile catalog."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional

from ..core.exceptions import ProviderError
from ..models import ModelRequest, ProviderCapabilities, ProviderProfile

ProviderBuilder = Callable[[Any], Any]


@dataclass(frozen=True)
class ProviderRegistration:
    """Registered provider factory and metadata."""

    name: str
    builder: ProviderBuilder
    aliases: tuple[str, ...] = ()
    default_model: Optional[str] = None
    capabilities: ProviderCapabilities = field(default_factory=ProviderCapabilities)


class ProviderRegistry:
    """Registry for provider factories and provider/model profiles."""

    def __init__(self) -> None:
        self._providers: Dict[str, ProviderRegistration] = {}
        self._aliases: Dict[str, str] = {}
        self._profiles: Dict[str, ProviderProfile] = {}

    def register_provider(
        self,
        name: str,
        builder: ProviderBuilder,
        *,
        aliases: Iterable[str] = (),
        default_model: Optional[str] = None,
        capabilities: Optional[ProviderCapabilities] = None,
    ) -> None:
        """Register a provider factory."""
        normalized = self._normalize(name)
        registration = ProviderRegistration(
            name=normalized,
            builder=builder,
            aliases=tuple(self._normalize(alias) for alias in aliases),
            default_model=default_model,
            capabilities=capabilities or ProviderCapabilities(),
        )
        self._providers[normalized] = registration
        self._aliases[normalized] = normalized
        for alias in registration.aliases:
            self._aliases[alias] = normalized

    def register_profile(self, profile: ProviderProfile) -> None:
        """Register a provider/model profile."""
        key = self.profile_key(profile.provider, profile.model)
        self._profiles[key] = profile

    def create_provider(self, provider_name: str, config: Any) -> Any:
        """Create a provider instance from the registry."""
        registration = self.get_registration(provider_name)
        instance = registration.builder(config)
        options = getattr(config, "provider_options", {}) or {}
        if options.get("discover_model") is True:
            try:
                self.discover_models(provider_name, config)
            except Exception:
                close = getattr(instance, "close", None)
                if callable(close):
                    close()
                raise
        return instance

    def discover_models(self, provider: str, config: Any) -> List[ProviderProfile]:
        """Fetch and register live profiles explicitly; never fetch at import time."""
        from .catalog import discover_models

        profiles = discover_models(provider, config, self)
        for profile in profiles:
            self.register_profile(profile)
        return profiles

    def get_registration(self, provider_name: str) -> ProviderRegistration:
        """Return a provider registration by name or alias."""
        canonical = self.canonical_provider(provider_name)
        if canonical is None or canonical not in self._providers:
            raise ProviderError(f"Unsupported provider: {provider_name}")
        return self._providers[canonical]

    def canonical_provider(self, provider_name: str) -> Optional[str]:
        """Return the canonical provider name for a name or alias."""
        normalized = self._normalize(provider_name)
        return self._aliases.get(normalized)

    def list_providers(self) -> List[str]:
        """List registered canonical provider names."""
        return sorted(self._providers.keys())

    def get_profile(self, provider: str, model: str) -> Optional[ProviderProfile]:
        """Return a model profile if one is registered."""
        normalized_provider = self._normalize(provider)
        candidates = [normalized_provider]
        canonical = self.canonical_provider(provider)
        if canonical and canonical not in candidates:
            candidates.append(canonical)

        for provider_name in candidates:
            profile = self._profiles.get(self.profile_key(provider_name, model))
            if profile is not None:
                return profile
            # Dated snapshots share the explicitly registered model family.
            for candidate in self._profiles.values():
                if candidate.provider != provider_name:
                    continue
                suffix = model.removeprefix(candidate.model + "-")
                if suffix != model and re.fullmatch(r"\d{4}-?\d{2}-?\d{2}", suffix):
                    return candidate
            wildcard = self._profiles.get(self.profile_key(provider_name, "*"))
            if wildcard is not None:
                return wildcard
        return None

    def list_profiles(self, provider: Optional[str] = None) -> List[ProviderProfile]:
        """List registered provider/model profiles."""
        profiles = list(self._profiles.values())
        if provider is not None:
            normalized = self._normalize(provider)
            canonical = self.canonical_provider(provider)
            accepted = {normalized}
            if canonical:
                accepted.add(canonical)
            profiles = [
                profile
                for profile in profiles
                if self._normalize(profile.provider) in accepted
            ]
        return sorted(profiles, key=lambda item: (item.provider, item.model))

    def resolve_profile(
        self,
        provider: str,
        model: Optional[str] = None,
    ) -> Optional[ProviderProfile]:
        """Resolve the best provider/model profile for a request."""
        if model:
            profile = self.get_profile(provider, model)
            if profile is not None:
                return profile
        return self.get_profile(provider, "*")

    def resolve_capabilities(
        self,
        provider: str,
        model: Optional[str] = None,
        *,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> ProviderCapabilities:
        """Resolve effective capabilities for a provider/model request."""
        registration = self.get_registration(provider)
        profile = self.resolve_profile(provider, model)
        capabilities = (
            profile.capabilities.model_copy(deep=True)
            if profile is not None
            else registration.capabilities.model_copy(deep=True)
        )
        for key, value in (overrides or {}).items():
            if hasattr(capabilities, key):
                setattr(capabilities, key, value)
        return capabilities

    def default_model_for(self, provider: str) -> Optional[str]:
        """Return the default model for a provider if configured."""
        return self.get_registration(provider).default_model

    @staticmethod
    def profile_key(provider: str, model: str) -> str:
        """Build a stable profile key."""
        return f"{ProviderRegistry._normalize(provider)}:{model}"

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().lower().replace("_", "-")


_global_registry: Optional[ProviderRegistry] = None


def _openai_builder(config: Any) -> Any:
    from .openai import OpenAIProvider

    return OpenAIProvider(config)


def _anthropic_builder(config: Any) -> Any:
    from .anthropic import AnthropicProvider

    return AnthropicProvider(config)


def _cohere_builder(config: Any) -> Any:
    from .cohere import CohereProvider

    return CohereProvider(config)


def _openai_compatible_builder(config: Any) -> Any:
    from .openai_compatible import OpenAICompatibleProvider

    return OpenAICompatibleProvider(config)


def _gemini_builder(config: Any) -> Any:
    from .gemini import GeminiProvider

    return GeminiProvider(config)


def _openrouter_builder(config: Any) -> Any:
    from .openrouter import OpenRouterProvider

    return OpenRouterProvider(config)


def get_provider_registry() -> ProviderRegistry:
    """Return the process-wide provider registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ProviderRegistry()
        register_default_providers(_global_registry)
    return _global_registry


def reset_provider_registry() -> ProviderRegistry:
    """Reset and return the process-wide provider registry."""
    global _global_registry
    _global_registry = ProviderRegistry()
    register_default_providers(_global_registry)
    return _global_registry


def register_default_providers(registry: ProviderRegistry) -> None:
    """Register built-in provider factories and model profiles."""
    openai_capabilities = ProviderCapabilities(
        chat_completions=True,
        responses_api=True,
        tools=True,
        streaming=True,
        native_streaming=True,
        tool_streaming=True,
        structured_outputs=True,
        json_schema_mode="json_schema",
        multimodal=True,
        image_input=True,
        audio_transcription=True,
        speech_generation=True,
        reasoning=True,
        reasoning_effort=True,
        embeddings=True,
    )
    anthropic_capabilities = ProviderCapabilities(
        tools=True,
        streaming=True,
        native_streaming=True,
        tool_streaming=True,
        structured_outputs=True,
        json_schema_mode="json_schema",
        multimodal=True,
        image_input=True,
        reasoning=True,
        reasoning_effort=True,
        reasoning_budget=True,
    )
    gemini_capabilities = ProviderCapabilities(
        tools=True,
        streaming=True,
        native_streaming=True,
        structured_outputs=True,
        json_schema_mode="json_schema",
        multimodal=True,
        image_input=True,
        file_input=True,
        audio_input=True,
        video_input=True,
        reasoning=True,
        reasoning_budget=True,
        embeddings=True,
    )
    local_capabilities = ProviderCapabilities(
        chat_completions=True,
        streaming=True,
        native_streaming=True,
        local=True,
    )
    registry.register_provider(
        "openai",
        _openai_builder,
        default_model="gpt-5.4-mini",
        capabilities=openai_capabilities,
    )
    registry.register_provider(
        "anthropic",
        _anthropic_builder,
        aliases=("claude",),
        default_model="claude-sonnet-5",
        capabilities=anthropic_capabilities,
    )
    registry.register_provider(
        "cohere",
        _cohere_builder,
        default_model="command-a-03-2025",
        capabilities=ProviderCapabilities(tools=True, streaming=False),
    )
    registry.register_provider(
        "gemini",
        _gemini_builder,
        aliases=("google",),
        default_model="gemini-3.5-flash",
        capabilities=gemini_capabilities,
    )
    registry.register_provider(
        "openai-compatible",
        _openai_compatible_builder,
        aliases=("ollama", "vllm", "lmstudio", "llama-cpp", "local"),
        default_model=None,
        capabilities=local_capabilities,
    )
    registry.register_provider(
        "openrouter",
        _openrouter_builder,
        capabilities=ProviderCapabilities(
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
        ),
    )

    profiles = [
        ProviderProfile(
            provider="openai",
            model="gpt-5.4-mini",
            default=True,
            endpoint="responses",
            capabilities=openai_capabilities,
            notes="Balanced OpenAI profile for general Praval agents.",
        ),
        ProviderProfile(
            provider="openai",
            model="gpt-5.4",
            endpoint="responses",
            capabilities=openai_capabilities,
            notes="OpenAI profile for broad reasoning, coding, and agent tasks.",
        ),
        ProviderProfile(
            provider="openai",
            model="gpt-5.4-nano",
            endpoint="responses",
            capabilities=openai_capabilities,
            notes="Lower-latency OpenAI profile for lightweight agent tasks.",
        ),
        ProviderProfile(
            provider="openai",
            model="gpt-5.5",
            endpoint="responses",
            capabilities=openai_capabilities,
            notes="Flagship OpenAI profile for reasoning and coding.",
        ),
        ProviderProfile(
            provider="anthropic",
            model="claude-sonnet-5",
            default=True,
            endpoint="messages",
            capabilities=anthropic_capabilities,
        ),
        ProviderProfile(
            provider="anthropic",
            model="claude-fable-5",
            endpoint="messages",
            capabilities=anthropic_capabilities,
        ),
        ProviderProfile(
            provider="anthropic",
            model="claude-opus-4-8",
            endpoint="messages",
            capabilities=anthropic_capabilities,
        ),
        ProviderProfile(
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            endpoint="messages",
            capabilities=anthropic_capabilities,
        ),
        ProviderProfile(
            provider="anthropic",
            model="claude-haiku-4-5",
            endpoint="messages",
            capabilities=anthropic_capabilities,
            notes="Alias profile retained for compatibility with provider shorthand.",
        ),
        ProviderProfile(
            provider="cohere",
            model="command-a-03-2025",
            default=True,
            endpoint="chat",
            capabilities=ProviderCapabilities(tools=True, streaming=False),
            notes="Current Cohere text model profile for tool-using agents.",
        ),
        ProviderProfile(
            provider="gemini",
            model="gemini-3.5-flash",
            default=True,
            endpoint="generateContent",
            capabilities=gemini_capabilities,
        ),
        ProviderProfile(
            provider="gemini",
            model="gemini-3.1-flash-lite",
            endpoint="generateContent",
            capabilities=gemini_capabilities,
        ),
        ProviderProfile(
            provider="gemini",
            model="gemini-3.1-pro-preview",
            endpoint="generateContent",
            capabilities=gemini_capabilities,
        ),
        ProviderProfile(
            provider="ollama",
            model="*",
            local_preset="ollama",
            endpoint="chat.completions",
            capabilities=local_capabilities,
            downgrade_policy="error",
            notes=(
                "Conservative Ollama preset. Enable tools/schema manually "
                "if server supports them."
            ),
        ),
        ProviderProfile(
            provider="vllm",
            model="*",
            local_preset="vllm",
            endpoint="chat.completions",
            capabilities=local_capabilities,
            downgrade_policy="error",
            notes="Conservative vLLM preset for OpenAI-compatible chat.",
        ),
        ProviderProfile(
            provider="lmstudio",
            model="*",
            local_preset="lmstudio",
            endpoint="chat.completions",
            capabilities=local_capabilities,
            downgrade_policy="error",
            notes="Conservative LM Studio preset for OpenAI-compatible chat.",
        ),
        ProviderProfile(
            provider="llama-cpp",
            model="*",
            local_preset="llama-cpp",
            endpoint="chat.completions",
            capabilities=local_capabilities,
            downgrade_policy="error",
            notes="Conservative llama.cpp preset for OpenAI-compatible chat.",
        ),
        ProviderProfile(
            provider="openai-compatible",
            model="*",
            endpoint="chat.completions",
            capabilities=local_capabilities,
            downgrade_policy="error",
            notes=(
                "Generic OpenAI-compatible profile. Explicitly override "
                "capabilities for richer servers."
            ),
        ),
    ]
    for profile in profiles:
        registry.register_profile(profile)
    registry.register_profile(
        ProviderProfile(
            provider="openrouter",
            model="*",
            endpoint="chat.completions",
            capabilities=registry.get_registration("openrouter").capabilities,
            reasoning_levels={
                "none": {"enabled": False},
                **{level: {"effort": level} for level in ("low", "medium", "high")},
            },
            reasoning_source=(
                "https://openrouter.ai/docs/guides/best-practices/reasoning-tokens"
            ),
            notes=(
                "Routing requires all requested parameters; "
                "discover the catalogue for model-specific limits."
            ),
        )
    )
    _register_reasoning_profiles(registry)


# Audited 2026-10-08. Budgets are Praval defaults within documented ranges,
# not claims of equal compute or answer quality across providers.
def _register_reasoning_profiles(registry: ProviderRegistry) -> None:
    def add(
        provider: str,
        models: Iterable[str],
        levels: Dict[str, Dict[str, Any]],
        source: str,
    ) -> None:
        for model in models:
            existing = registry.get_profile(provider, model)
            if existing is None or existing.model != model:
                existing = ProviderProfile(
                    provider=provider,
                    model=model,
                    capabilities=registry.get_registration(provider).capabilities,
                )
            profile = existing.model_copy(deep=True)
            profile.reasoning_levels = copy.deepcopy(levels)
            profile.reasoning_source = source
            profile.capabilities.reasoning = True
            registry.register_profile(profile)

    efforts = {level: {"effort": level} for level in ("low", "medium", "high")}
    add(
        "openai",
        (
            "o1",
            "o3",
            "o3-mini",
            "o4-mini",
            "gpt-5",
            "gpt-5-mini",
            "gpt-5-nano",
        ),
        efforts,
        "https://developers.openai.com/api/docs/guides/reasoning",
    )
    add(
        "openai",
        ("gpt-5.1", "gpt-5.2", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.5"),
        {"none": {"effort": "none"}, **efforts},
        "https://developers.openai.com/api/docs/guides/latest-model",
    )
    add(
        "openai",
        ("gpt-6-luna", "gpt-6-sol"),
        {"none": {"effort": "none"}, **efforts},
        "https://developers.openai.com/api/docs/guides/latest-model",
    )
    add(
        "openai",
        ("gpt-6-astra", "gpt-6.1-sol"),
        efforts,
        "https://developers.openai.com/api/docs/guides/latest-model",
    )
    adaptive = {
        level: {"thinking": {"type": "adaptive"}, "output_config": {"effort": level}}
        for level in ("low", "medium", "high")
    }
    add(
        "anthropic",
        (
            "claude-sonnet-5",
            "claude-opus-4-8",
            "claude-opus-4-7",
            "claude-opus-4-6",
            "claude-sonnet-4-6",
        ),
        {"none": {"thinking": {"type": "disabled"}}, **adaptive},
        (
            "https://platform.claude.com/docs/en/build-with-claude/"
            "thinking-troubleshooting"
        ),
    )
    add(
        "anthropic",
        ("claude-fable-5",),
        adaptive,
        "https://platform.claude.com/docs/en/build-with-claude/effort",
    )
    add(
        "anthropic",
        ("claude-sonnet-5-5",),
        {"none": {"thinking": {"type": "between_tools"}}, **adaptive},
        "https://platform.claude.com/docs/en/models/sonnet-5-5/migration-guide",
    )
    add(
        "anthropic",
        ("claude-haiku-5-5",),
        {"none": {"thinking": {"type": "disabled"}}, **adaptive},
        "https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide",
    )
    manual = {
        level: {"thinking": {"type": "enabled", "budget_tokens": budget}}
        for level, budget in (("low", 1024), ("medium", 4096), ("high", 8192))
    }
    add(
        "anthropic",
        ("claude-haiku-4-5", "claude-haiku-4-5-20251001", "claude-sonnet-4-5"),
        {"none": {"thinking": {"type": "disabled"}}, **manual},
        "https://platform.claude.com/docs/en/build-with-claude/extended-thinking",
    )
    add(
        "gemini",
        (
            "gemini-3.5-flash",
            "gemini-3.6-flash",
            "gemini-3.7-flash",
            "gemini-3.8-flash",
            "gemini-3.1-flash-lite",
            "gemini-3.1-pro-preview",
            "gemini-3-flash-preview",
        ),
        {level: {"thinkingLevel": level} for level in ("low", "medium", "high")},
        "https://ai.google.dev/gemini-api/docs/generate-content/thinking",
    )
    budgets = {
        level: {"thinkingBudget": budget}
        for level, budget in (("low", 1024), ("medium", 4096), ("high", 8192))
    }
    add(
        "gemini",
        ("gemini-2.5-pro",),
        budgets,
        "https://ai.google.dev/gemini-api/docs/generate-content/thinking",
    )
    add(
        "gemini",
        ("gemini-2.5-flash", "gemini-2.5-flash-lite"),
        {"none": {"thinkingBudget": 0}, **budgets},
        "https://ai.google.dev/gemini-api/docs/generate-content/thinking",
    )
    add(
        "cohere",
        ("command-a-reasoning-08-2025",),
        {
            "none": {"thinking": {"type": "disabled"}},
            **{
                level: {"thinking": {"type": "enabled", "token_budget": budget}}
                for level, budget in (("low", 512), ("medium", 2048), ("high", 8192))
            },
        },
        "https://docs.cohere.com/docs/reasoning (cohere 5.17.0 ClientV2.chat)",
    )
    profile = registry.get_profile("cohere", "command-a-reasoning-08-2025")
    if profile is not None:
        profile.endpoint = "chat.v2"
        profile.capabilities.reasoning_budget = True
        profile.capabilities.streaming = True
    profile = registry.get_profile("vllm", "*")
    if profile is not None:
        profile = profile.model_copy(deep=True)
        profile.capabilities.reasoning = True
        profile.capabilities.reasoning_effort = True
        profile.reasoning_levels = copy.deepcopy(efforts)
        profile.reasoning_source = (
            "https://docs.vllm.ai/en/latest/features/reasoning_outputs/"
        )
        registry.register_profile(profile)
        # The wildcard cannot promise that a model can disable thinking.
        # Gemma 4's documented template declares enable_thinking.
        disabling_profile = profile.model_copy(
            update={"model": "google/gemma-4-26B-A4B-it"}, deep=True
        )
        disabling_profile.reasoning_levels = {"none": {"effort": "none"}, **efforts}
        registry.register_profile(disabling_profile)


def reasoning_parameters(request: ModelRequest) -> Dict[str, Any]:
    """Resolve portable controls without changing explicit provider controls."""
    reasoning = request.reasoning
    if reasoning is None or reasoning.level is None:
        return {}
    provider = request.provider or "unknown"
    model = request.model or "unknown"
    profile = get_provider_registry().resolve_profile(provider, model)
    levels = profile.reasoning_levels if profile is not None else {}
    if reasoning.level not in levels:
        accepted = ", ".join(levels) or "none available"
        raise ProviderError(
            f"Provider '{provider}' model '{model}' does not support reasoning "
            f"level '{reasoning.level}'; accepted levels: {accepted}"
        )
    native = copy.deepcopy(levels[reasoning.level])
    budget = native.get("thinking", {}).get("budget_tokens")
    if (
        budget is not None
        and reasoning.budget_tokens is None
        and request.max_output_tokens is not None
        and request.max_output_tokens <= budget
    ):
        raise ProviderError(
            f"Provider '{provider}' model '{model}' "
            f"reasoning level '{reasoning.level}' "
            f"requires max_output_tokens greater than {budget}"
        )
    return native
