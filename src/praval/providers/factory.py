"""
Factory for creating LLM provider instances.

Provides a unified interface for instantiating different LLM providers
with consistent configuration handling.
"""

from typing import Any, Dict
from ..core.exceptions import ProviderError


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
            if provider_name == "openai":
                from .openai import OpenAIProvider
                return OpenAIProvider(config)
            elif provider_name == "anthropic":
                from .anthropic import AnthropicProvider
                return AnthropicProvider(config)
            elif provider_name == "cohere":
                from .cohere import CohereProvider
                return CohereProvider(config)
            else:
                raise ProviderError(f"Unsupported provider: {provider_name}")
        except ImportError as e:
            raise ProviderError(f"Failed to import provider '{provider_name}': {str(e)}") from e
        except Exception as e:
            raise ProviderError(f"Failed to create provider '{provider_name}': {str(e)}") from e