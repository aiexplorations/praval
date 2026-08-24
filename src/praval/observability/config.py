"""Compatibility imports for the typed Praval configuration system."""

from praval.config import (
    ObservabilityConfig,
    get_legacy_observability_config,
    reset_legacy_observability_config,
)


def get_config() -> ObservabilityConfig:
    """Return the v0.8.2-compatible cached observability configuration."""
    return get_legacy_observability_config()


def reset_config() -> None:
    """Reset legacy configuration state for test isolation."""
    reset_legacy_observability_config()


__all__ = ["ObservabilityConfig", "get_config", "reset_config"]
