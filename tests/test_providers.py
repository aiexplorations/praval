"""
Tests for LLM provider integrations.

Tests the provider factory and individual provider implementations
to ensure consistent behavior across different LLM APIs.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from praval.providers.factory import ProviderFactory
from praval.providers.openai import OpenAIProvider
from praval.providers.anthropic import AnthropicProvider
from praval.providers.cohere import CohereProvider
from praval.core.exceptions import ProviderError
from praval.core.agent import AgentConfig


class TestProviderFactory:
    """Test the provider factory functionality."""
    
    def test_create_openai_provider(self):
        """Test creating OpenAI provider through factory."""
        config = AgentConfig(provider="openai")
        
        with patch('praval.providers.openai.OpenAIProvider') as mock_provider:
            provider = ProviderFactory.create_provider("openai", config)
            mock_provider.assert_called_once_with(config)
    
    def test_create_anthropic_provider(self):
        """Test creating Anthropic provider through factory."""
        config = AgentConfig(provider="anthropic")
        
        with patch('praval.providers.anthropic.AnthropicProvider') as mock_provider:
            provider = ProviderFactory.create_provider("anthropic", config)
            mock_provider.assert_called_once_with(config)
    
    def test_create_cohere_provider(self):
        """Test creating Cohere provider through factory."""
        config = AgentConfig(provider="cohere")
        
        with patch('praval.providers.cohere.CohereProvider') as mock_provider:
            provider = ProviderFactory.create_provider("cohere", config)
            mock_provider.assert_called_once_with(config)
    
    def test_invalid_provider_raises_error(self):
        """Test that invalid provider name raises ProviderError."""
        config = AgentConfig()
        
        with pytest.raises(ProviderError, match="Unsupported provider"):
            ProviderFactory.create_provider("invalid_provider", config)


class TestOpenAIProvider:
    """Test OpenAI provider implementation."""
    
    @patch('openai.OpenAI')
    def test_openai_provider_initialization(self, mock_openai_class):
        """Test OpenAI provider initializes correctly."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        
        config = AgentConfig(temperature=0.8, max_tokens=500)
        provider = OpenAIProvider(config)
        
        assert provider.config == config
        assert provider.client == mock_client
    
    @patch('openai.OpenAI')
    def test_openai_generate_simple_message(self, mock_openai_class):
        """Test OpenAI provider generates response for simple message."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello! How can I help you?"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        config = AgentConfig()
        provider = OpenAIProvider(config)
        
        messages = [{"role": "user", "content": "Hello"}]
        response = provider.generate(messages)
        
        assert response == "Hello! How can I help you?"
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('openai.OpenAI')
    def test_openai_generate_with_tools(self, mock_openai_class):
        """Test OpenAI provider handles tool calls correctly."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "I'll calculate that for you."
        mock_response.choices[0].message.tool_calls = None
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        config = AgentConfig()
        provider = OpenAIProvider(config)
        
        messages = [{"role": "user", "content": "What is 2+2?"}]
        tools = [{"function": lambda x, y: x + y, "description": "Add numbers"}]
        response = provider.generate(messages, tools)
        
        assert response == "I'll calculate that for you."
    
    @patch('openai.OpenAI')
    def test_openai_handles_api_errors(self, mock_openai_class):
        """Test OpenAI provider handles API errors gracefully."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai_class.return_value = mock_client
        
        config = AgentConfig()
        provider = OpenAIProvider(config)
        
        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(ProviderError, match="OpenAI API error"):
            provider.generate(messages)


class TestAnthropicProvider:
    """Test Anthropic provider implementation."""
    
    @patch('anthropic.Anthropic')
    def test_anthropic_provider_initialization(self, mock_anthropic_class):
        """Test Anthropic provider initializes correctly."""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        config = AgentConfig(temperature=0.8, max_tokens=500)
        provider = AnthropicProvider(config)
        
        assert provider.config == config
        assert provider.client == mock_client
    
    @patch('anthropic.Anthropic')
    def test_anthropic_generate_simple_message(self, mock_anthropic_class):
        """Test Anthropic provider generates response for simple message."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "Hello! How can I assist you today?"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client
        
        config = AgentConfig()
        provider = AnthropicProvider(config)
        
        messages = [{"role": "user", "content": "Hello"}]
        response = provider.generate(messages)
        
        assert response == "Hello! How can I assist you today?"
        mock_client.messages.create.assert_called_once()
    
    @patch('anthropic.Anthropic')
    def test_anthropic_handles_system_messages(self, mock_anthropic_class):
        """Test Anthropic provider handles system messages correctly."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "I am a helpful assistant."
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client
        
        config = AgentConfig()
        provider = AnthropicProvider(config)
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What are you?"}
        ]
        response = provider.generate(messages)
        
        assert response == "I am a helpful assistant."
        
        # Verify system message was passed correctly
        call_args = mock_client.messages.create.call_args
        assert "system" in call_args.kwargs
    
    @patch('anthropic.Anthropic')
    def test_anthropic_handles_api_errors(self, mock_anthropic_class):
        """Test Anthropic provider handles API errors gracefully."""
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("API Error")
        mock_anthropic_class.return_value = mock_client
        
        config = AgentConfig()
        provider = AnthropicProvider(config)
        
        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(ProviderError, match="Anthropic API error"):
            provider.generate(messages)


class TestCohereProvider:
    """Test Cohere provider implementation."""
    
    @patch('cohere.Client')
    def test_cohere_provider_initialization(self, mock_cohere_class):
        """Test Cohere provider initializes correctly."""
        mock_client = Mock()
        mock_cohere_class.return_value = mock_client
        
        config = AgentConfig(temperature=0.8, max_tokens=500)
        provider = CohereProvider(config)
        
        assert provider.config == config
        assert provider.client == mock_client
    
    @patch('cohere.Client')
    def test_cohere_generate_simple_message(self, mock_cohere_class):
        """Test Cohere provider generates response for simple message."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Hello! I'm here to help you with anything you need."
        mock_client.chat.return_value = mock_response
        mock_cohere_class.return_value = mock_client
        
        config = AgentConfig()
        provider = CohereProvider(config)
        
        messages = [{"role": "user", "content": "Hello"}]
        response = provider.generate(messages)
        
        assert response == "Hello! I'm here to help you with anything you need."
        mock_client.chat.assert_called_once()
    
    @patch('cohere.Client')
    def test_cohere_handles_conversation_history(self, mock_cohere_class):
        """Test Cohere provider handles conversation history correctly."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "I remember our previous conversation."
        mock_client.chat.return_value = mock_response
        mock_cohere_class.return_value = mock_client
        
        config = AgentConfig()
        provider = CohereProvider(config)
        
        messages = [
            {"role": "user", "content": "My name is Alice"},
            {"role": "assistant", "content": "Nice to meet you, Alice!"},
            {"role": "user", "content": "What's my name?"}
        ]
        response = provider.generate(messages)
        
        assert response == "I remember our previous conversation."
        
        # Verify conversation history was passed correctly
        call_args = mock_client.chat.call_args
        assert "chat_history" in call_args.kwargs
    
    @patch('cohere.Client')
    def test_cohere_handles_api_errors(self, mock_cohere_class):
        """Test Cohere provider handles API errors gracefully."""
        mock_client = Mock()
        mock_client.chat.side_effect = Exception("API Error")
        mock_cohere_class.return_value = mock_client
        
        config = AgentConfig()
        provider = CohereProvider(config)
        
        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(ProviderError, match="Cohere API error"):
            provider.generate(messages)


class TestProviderConfiguration:
    """Test provider configuration handling."""
    
    def test_temperature_configuration_applied(self):
        """Test that temperature configuration is applied to providers."""
        config = AgentConfig(temperature=0.9)
        
        with patch('openai.OpenAI') as mock_openai:
            provider = OpenAIProvider(config)
            assert provider.config.temperature == 0.9
    
    def test_max_tokens_configuration_applied(self):
        """Test that max_tokens configuration is applied to providers."""
        config = AgentConfig(max_tokens=2000)
        
        with patch('anthropic.Anthropic') as mock_anthropic:
            provider = AnthropicProvider(config)
            assert provider.config.max_tokens == 2000
    
    def test_system_message_configuration_applied(self):
        """Test that system message configuration is handled correctly."""
        config = AgentConfig(system_message="You are a coding assistant.")
        
        with patch('cohere.Client') as mock_cohere:
            provider = CohereProvider(config)
            assert provider.config.system_message == "You are a coding assistant."