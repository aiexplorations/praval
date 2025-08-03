"""
Integration tests for Praval framework.

Tests the complete functionality using the target API examples
to ensure the framework works as intended end-to-end.
"""

import pytest
import tempfile
import shutil
from unittest.mock import Mock, patch
from praval import Agent


class TestIntegrationBasicUsage:
    """Test basic usage patterns from target API examples."""
    
    @patch('praval.providers.openai.OpenAIProvider')
    def test_simplest_usage_example(self, mock_provider_class):
        """Test Example 1: Absolute Simplest Usage."""
        # Setup mock provider
        mock_provider = Mock()
        mock_provider.generate.return_value = "Hello! How can I help you today?"
        mock_provider_class.return_value = mock_provider
        
        # Test the simplest possible usage
        agent = Agent("assistant")
        response = agent.chat("Hello, how are you?")
        
        assert response == "Hello! How can I help you today?"
        assert agent.name == "assistant"
        assert len(agent.conversation_history) == 2  # user + assistant
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'})
    @patch('praval.providers.openai.OpenAIProvider')
    def test_auto_provider_detection(self, mock_provider_class):
        """Test automatic provider detection from environment."""
        mock_provider = Mock()
        mock_provider.generate.return_value = "Response"
        mock_provider_class.return_value = mock_provider
        
        agent = Agent("assistant")
        assert agent.provider_name == "openai"


class TestIntegrationStatefulConversations:
    """Test stateful conversation patterns from target API examples."""
    
    def setup_method(self):
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('praval.providers.openai.OpenAIProvider')
    @patch('praval.core.storage.StateStorage')
    def test_stateful_conversation_example(self, mock_storage_class, mock_provider_class):
        """Test Example 2: Stateful Conversations."""
        # Setup mocks
        mock_provider = Mock()
        mock_provider.generate.side_effect = [
            "Nice to meet you, Alice! I'll remember that you're learning Python.",
            "That's great! Web development is a very useful skill.",
            "You're learning Python, specifically web development!"
        ]
        mock_provider_class.return_value = mock_provider
        
        mock_storage = Mock()
        mock_storage.load.return_value = None  # No existing state initially
        mock_storage_class.return_value = mock_storage
        
        # First session
        agent = Agent("personal_assistant", persist_state=True)
        response1 = agent.chat("My name is Alice and I'm learning Python")
        response2 = agent.chat("I'm particularly interested in web development")
        
        assert "Alice" in response1
        assert "web development" in response2.lower()
        assert agent.persist_state is True
        
        # Verify state was saved
        assert mock_storage.save.call_count == 2
    
    @patch('praval.providers.openai.OpenAIProvider')
    @patch('praval.core.storage.StateStorage')
    def test_state_restoration_example(self, mock_storage_class, mock_provider_class):
        """Test state restoration across sessions."""
        # Setup mocks
        mock_provider = Mock()
        mock_provider.generate.return_value = "You're learning Python, specifically web development"
        mock_provider_class.return_value = mock_provider
        
        # Mock existing conversation history
        existing_history = [
            {"role": "user", "content": "My name is Alice and I'm learning Python"},
            {"role": "assistant", "content": "Nice to meet you, Alice!"},
            {"role": "user", "content": "I'm particularly interested in web development"},
            {"role": "assistant", "content": "That's great! Web development is very useful."}
        ]
        
        mock_storage = Mock()
        mock_storage.load.return_value = existing_history
        mock_storage_class.return_value = mock_storage
        
        # New session with same agent name
        agent = Agent("personal_assistant", persist_state=True)
        response = agent.chat("What am I learning about?")
        
        # Verify history was loaded
        assert len(agent.conversation_history) == 6  # 4 loaded + 1 user + 1 assistant
        assert "Python" in response
        assert "web development" in response


class TestIntegrationToolUsage:
    """Test tool integration patterns from target API examples."""
    
    @patch('praval.providers.openai.OpenAIProvider')
    def test_tool_registration_example(self, mock_provider_class):
        """Test Example 3: Using Tools - Registration."""
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        
        agent = Agent("researcher")
        
        # Test tool registration with decorator
        @agent.tool
        def calculate(expression: str) -> float:
            """Safely evaluate a mathematical expression"""
            # Simple implementation for testing
            if expression == "2+2":
                return 4.0
            return 0.0
        
        @agent.tool  
        def get_date() -> str:
            """Get the current date"""
            return "2024-01-15"
        
        # Verify tools were registered
        assert "calculate" in agent.tools
        assert "get_date" in agent.tools
        assert len(agent.tools) == 2
        
        # Verify tool metadata
        calc_tool = agent.tools["calculate"]
        assert calc_tool["function"] == calculate
        assert "mathematical expression" in calc_tool["description"]
        
        date_tool = agent.tools["get_date"]
        assert date_tool["function"] == get_date
        assert "current date" in date_tool["description"]
    
    @patch('praval.providers.openai.OpenAIProvider')
    def test_tool_function_preservation(self, mock_provider_class):
        """Test that tool functions remain callable after decoration."""
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        
        agent = Agent("calculator")
        
        @agent.tool
        def add_numbers(x: int, y: int) -> int:
            """Add two numbers together"""
            return x + y
        
        # Function should still be callable directly
        result = add_numbers(5, 3)
        assert result == 8
        
        # Function should be registered as tool
        assert "add_numbers" in agent.tools
        assert agent.tools["add_numbers"]["function"] == add_numbers


class TestIntegrationProviderCompatibility:
    """Test compatibility across different providers."""
    
    @patch('praval.providers.openai.OpenAIProvider')
    def test_openai_provider_integration(self, mock_provider_class):
        """Test complete integration with OpenAI provider."""
        mock_provider = Mock()
        mock_provider.generate.return_value = "OpenAI response"
        mock_provider_class.return_value = mock_provider
        
        agent = Agent("assistant", provider="openai")
        response = agent.chat("Test message")
        
        assert response == "OpenAI response"
        assert agent.provider_name == "openai"
    
    @patch('praval.providers.anthropic.AnthropicProvider')
    def test_anthropic_provider_integration(self, mock_provider_class):
        """Test complete integration with Anthropic provider."""
        mock_provider = Mock()
        mock_provider.generate.return_value = "Anthropic response"
        mock_provider_class.return_value = mock_provider
        
        agent = Agent("assistant", provider="anthropic")
        response = agent.chat("Test message")
        
        assert response == "Anthropic response"
        assert agent.provider_name == "anthropic"
    
    @patch('praval.providers.cohere.CohereProvider')
    def test_cohere_provider_integration(self, mock_provider_class):
        """Test complete integration with Cohere provider."""
        mock_provider = Mock()
        mock_provider.generate.return_value = "Cohere response"
        mock_provider_class.return_value = mock_provider
        
        agent = Agent("assistant", provider="cohere")
        response = agent.chat("Test message")
        
        assert response == "Cohere response"
        assert agent.provider_name == "cohere"


class TestIntegrationConfiguration:
    """Test configuration patterns and flexibility."""
    
    @patch('praval.providers.openai.OpenAIProvider')
    def test_configuration_via_constructor(self, mock_provider_class):
        """Test configuring agent via constructor parameters."""
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        
        agent = Agent(
            "configured_agent",
            provider="openai",
            system_message="You are a helpful coding assistant.",
            config={
                "temperature": 0.8,
                "max_tokens": 2000
            }
        )
        
        assert agent.config.temperature == 0.8
        assert agent.config.max_tokens == 2000
        assert agent.config.system_message == "You are a helpful coding assistant."
    
    @patch('praval.providers.anthropic.AnthropicProvider')
    def test_system_message_integration(self, mock_provider_class):
        """Test system message handling across providers."""
        mock_provider = Mock()
        mock_provider.generate.return_value = "I am a helpful assistant."
        mock_provider_class.return_value = mock_provider
        
        agent = Agent(
            "assistant",
            provider="anthropic",
            system_message="You are a helpful assistant."
        )
        
        response = agent.chat("What are you?")
        
        # Verify system message is in conversation history
        assert any(
            msg.get("role") == "system" and "helpful assistant" in msg.get("content", "")
            for msg in agent.conversation_history
        )


class TestIntegrationErrorHandling:
    """Test error handling in integrated scenarios."""
    
    def test_graceful_error_handling_no_api_keys(self):
        """Test graceful error when no API keys are available."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(Exception):  # Should raise ProviderError
                Agent("assistant")
    
    @patch('praval.providers.openai.OpenAIProvider')
    def test_graceful_error_handling_api_failure(self, mock_provider_class):
        """Test graceful error handling when API calls fail."""
        mock_provider = Mock()
        mock_provider.generate.side_effect = Exception("API temporarily unavailable")
        mock_provider_class.return_value = mock_provider
        
        agent = Agent("assistant", provider="openai")
        
        with pytest.raises(Exception):  # Should raise PravalError
            agent.chat("This will fail")


class TestIntegrationCompleteWorkflow:
    """Test complete workflows combining multiple features."""
    
    @patch('praval.providers.openai.OpenAIProvider')
    @patch('praval.core.storage.StateStorage')
    def test_complete_agent_workflow(self, mock_storage_class, mock_provider_class):
        """Test a complete agent workflow with persistence and tools."""
        # Setup mocks
        mock_provider = Mock()
        mock_provider.generate.side_effect = [
            "I can help you with calculations!",
            "The result of 15 + 25 is 40."
        ]
        mock_provider_class.return_value = mock_provider
        
        mock_storage = Mock()
        mock_storage.load.return_value = None
        mock_storage_class.return_value = mock_storage
        
        # Create agent with persistence and tools
        agent = Agent("math_helper", persist_state=True, provider="openai")
        
        @agent.tool
        def add(x: int, y: int) -> int:
            """Add two numbers"""
            return x + y
        
        # Test conversation
        response1 = agent.chat("Can you help me with math?")
        response2 = agent.chat("What is 15 + 25?")
        
        # Verify complete functionality
        assert "calculations" in response1
        assert "40" in response2
        assert len(agent.tools) == 1
        assert "add" in agent.tools
        assert len(agent.conversation_history) == 4  # 2 user + 2 assistant
        assert mock_storage.save.call_count == 2  # State saved after each chat