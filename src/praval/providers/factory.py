"""
Factory for creating LLM provider instances.

Provides a unified interface for instantiating different LLM providers
with consistent configuration handling.
"""

from typing import Any

from ..core.exceptions import ProviderError
from .registry import get_provider_registry


class ProviderFactory:
    """Factory class for creating LLM provider instances."""

    @staticmethod
    def create_provider(provider_name: str, config: Any):
        """
        Create an LLM provider instance.

        Args:
            provider_name: Name of the provider (openai, anthropic, cohere)
            config: Configuration object for the provider

        Returns:
            Provider instance

        Raises:
            ProviderError: If provider is not supported or creation fails
        """
        try:
            return get_provider_registry().create_provider(provider_name, config)
        except ImportError as e:
            raise ProviderError(
                f"Failed to import provider '{provider_name}': {str(e)}"
            ) from e
        except Exception as e:
            raise ProviderError(
                f"Failed to create provider '{provider_name}': {str(e)}"
            ) from e
