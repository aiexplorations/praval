"""
Tests for the core Agent class.

Following TDD principles - these tests define the expected behavior
before implementation.
"""

import pytest
from unittest.mock import Mock, patch
from praval.core.agent import Agent
from praval.core.exceptions import PravalError, ProviderError


class TestAgentInitialization:
    """Test Agent initialization and configuration."""
    
    def test_agent_simple_initialization(self):
        """Test simplest Agent initialization with just a name."""
        agent = Agent("assistant")
        assert agent.name == "assistant"
        assert agent.provider is not None
        assert agent.persist_state is False
        
    def test_agent_initialization_with_provider(self):
        """Test Agent initialization with explicit provider."""
        agent = Agent("assistant", provider="openai")
        assert agent.name == "assistant"
        assert agent.provider_name == "openai"
        
    def test_agent_initialization_with_persist_state(self):
        """Test Agent initialization with state persistence."""
        agent = Agent("assistant", persist_state=True)
        assert agent.name == "assistant"
        assert agent.persist_state is True
        
    def test_agent_initialization_with_config(self):
        """Test Agent initialization with configuration dictionary."""
        config = {
            "provider": "anthropic",
            "temperature": 0.7,
            "max_tokens": 1000
        }
        agent = Agent("assistant", config=config)
        assert agent.name == "assistant"
        assert agent.provider_name == "anthropic"
        assert agent.config["temperature"] == 0.7
        assert agent.config["max_tokens"] == 1000
        
    def test_agent_invalid_provider_raises_error(self):
        """Test that invalid provider raises appropriate error."""
        with pytest.raises(ProviderError):
            Agent("assistant", provider="invalid_provider")


class TestAgentChat:
    """Test Agent chat functionality."""
    
    @patch('praval.providers.openai.OpenAIProvider')
    def test_simple_chat(self, mock_provider_class):
        """Test basic chat functionality."""
        mock_provider = Mock()
        mock_provider.generate.return_value = "Hello! How can I help you?"
        mock_provider_class.return_value = mock_provider
        
        agent = Agent("assistant", provider="openai")
        response = agent.chat("Hello, how are you?")
        
        assert response == "Hello! How can I help you?"
        mock_provider.generate.assert_called_once()
        
    @patch('praval.providers.openai.OpenAIProvider')
    def test_chat_maintains_conversation_history(self, mock_provider_class):
        """Test that chat maintains conversation history."""
        mock_provider = Mock()
        mock_provider.generate.return_value = "Hello!"
        mock_provider_class.return_value = mock_provider
        
        agent = Agent("assistant", provider="openai")
        agent.chat("Hi there")
        agent.chat("How are you?")
        
        assert len(agent.conversation_history) == 4  # 2 user + 2 assistant messages
        assert agent.conversation_history[0]["role"] == "user"
        assert agent.conversation_history[0]["content"] == "Hi there"
        assert agent.conversation_history[1]["role"] == "assistant"
        assert agent.conversation_history[2]["role"] == "user"
        assert agent.conversation_history[2]["content"] == "How are you?"
        
    @patch('praval.providers.openai.OpenAIProvider')
    def test_chat_with_system_message(self, mock_provider_class):
        """Test chat with system message configuration."""
        mock_provider = Mock()
        mock_provider.generate.return_value = "I am a helpful assistant."
        mock_provider_class.return_value = mock_provider
        
        agent = Agent("assistant", provider="openai", 
                     system_message="You are a helpful assistant.")
        response = agent.chat("What are you?")
        
        assert response == "I am a helpful assistant."
        
    def test_chat_with_empty_message_raises_error(self):
        """Test that empty chat message raises appropriate error."""
        agent = Agent("assistant")
        with pytest.raises(ValueError, match="Message cannot be empty"):
            agent.chat("")
            
    def test_chat_with_none_message_raises_error(self):
        """Test that None chat message raises appropriate error."""
        agent = Agent("assistant")
        with pytest.raises(ValueError, match="Message cannot be empty"):
            agent.chat(None)


class TestAgentStatePersistence:
    """Test Agent state persistence functionality."""
    
    @patch('praval.core.storage.StateStorage')
    def test_persist_state_saves_conversation(self, mock_storage_class):
        """Test that state persistence saves conversation history."""
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage
        
        agent = Agent("persistent_agent", persist_state=True)
        agent.conversation_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        agent._save_state()
        
        mock_storage.save.assert_called_once_with(
            "persistent_agent", 
            agent.conversation_history
        )
        
    @patch('praval.core.storage.StateStorage')
    def test_load_state_restores_conversation(self, mock_storage_class):
        """Test that loading state restores conversation history."""
        mock_storage = Mock()
        saved_history = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"}
        ]
        mock_storage.load.return_value = saved_history
        mock_storage_class.return_value = mock_storage
        
        agent = Agent("persistent_agent", persist_state=True)
        
        assert agent.conversation_history == saved_history
        mock_storage.load.assert_called_once_with("persistent_agent")
        
    def test_non_persistent_agent_does_not_save_state(self):
        """Test that non-persistent agents don't save state."""
        agent = Agent("temp_agent", persist_state=False)
        # This should not raise any errors
        agent._save_state()  # Should be a no-op


class TestAgentTools:
    """Test Agent tool integration functionality."""
    
    def test_tool_decorator_registers_function(self):
        """Test that @agent.tool decorator registers functions properly."""
        agent = Agent("tool_agent")
        
        @agent.tool
        def calculate(x: int, y: int) -> int:
            """Add two numbers."""
            return x + y
            
        assert "calculate" in agent.tools
        assert agent.tools["calculate"]["function"] == calculate
        assert "Add two numbers." in agent.tools["calculate"]["description"]
        
    def test_tool_decorator_preserves_function_metadata(self):
        """Test that tool decorator preserves original function metadata."""
        agent = Agent("tool_agent")
        
        @agent.tool
        def multiply(a: float, b: float) -> float:
            """Multiply two numbers together."""
            return a * b
            
        tool_info = agent.tools["multiply"]
        assert tool_info["function"].__name__ == "multiply"
        assert "Multiply two numbers together." in tool_info["description"]
        
    def test_tool_with_invalid_signature_raises_error(self):
        """Test that tools without proper type hints raise error."""
        agent = Agent("tool_agent")
        
        with pytest.raises(ValueError, match="Tool functions must have type hints"):
            @agent.tool
            def bad_function(x, y):  # No type hints
                return x + y


class TestAgentProviderIntegration:
    """Test Agent integration with different providers."""
    
    def test_openai_provider_auto_detection(self):
        """Test automatic detection of OpenAI provider from environment."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}):
            agent = Agent("assistant")
            assert agent.provider_name == "openai"
            
    def test_anthropic_provider_auto_detection(self):
        """Test automatic detection of Anthropic provider from environment."""
        with patch.dict('os.environ', 
                       {'ANTHROPIC_API_KEY': 'test_key'}, 
                       clear=True):
            agent = Agent("assistant")
            assert agent.provider_name == "anthropic"
            
    def test_cohere_provider_auto_detection(self):
        """Test automatic detection of Cohere provider from environment."""
        with patch.dict('os.environ', 
                       {'COHERE_API_KEY': 'test_key'}, 
                       clear=True):
            agent = Agent("assistant")
            assert agent.provider_name == "cohere"
            
    def test_no_provider_available_raises_error(self):
        """Test that missing all provider keys raises appropriate error."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ProviderError, 
                             match="No LLM provider credentials found"):
                Agent("assistant")


class TestAgentErrorHandling:
    """Test Agent error handling and edge cases."""
    
    def test_agent_handles_provider_errors_gracefully(self):
        """Test that Agent handles provider errors appropriately."""
        with patch('praval.providers.openai.OpenAIProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider.generate.side_effect = Exception("API Error")
            mock_provider_class.return_value = mock_provider
            
            agent = Agent("assistant", provider="openai")
            with pytest.raises(PravalError, match="Failed to generate response"):
                agent.chat("Hello")
                
    def test_agent_validates_configuration(self):
        """Test that Agent validates configuration parameters."""
        with pytest.raises(ValueError, match="temperature must be between 0 and 2"):
            Agent("assistant", config={"temperature": 3.0})
            
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            Agent("assistant", config={"max_tokens": -100})
            
    def test_agent_name_validation(self):
        """Test that Agent validates name parameter."""
        with pytest.raises(ValueError, match="Agent name cannot be empty"):
            Agent("")
            
        with pytest.raises(ValueError, match="Agent name cannot be empty"):
            Agent(None)