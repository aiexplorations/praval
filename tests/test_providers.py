"""
Tests for LLM provider integrations.

Tests the provider factory and individual provider implementations
to ensure consistent behavior across different LLM APIs.
"""

import os
from unittest.mock import Mock, patch

import pytest

from praval.core.agent import AgentConfig
from praval.core.exceptions import ProviderError
from praval.providers.anthropic import AnthropicProvider
from praval.providers.cohere import CohereProvider
from praval.providers.factory import ProviderFactory
from praval.providers.openai import OpenAIProvider


class TestProviderFactory:
    """Test the provider factory functionality."""

    def test_create_openai_provider(self):
        """Test creating OpenAI provider through factory."""
        config = AgentConfig(provider="openai")

        with patch("praval.providers.openai.OpenAIProvider") as mock_provider:
            _ = ProviderFactory.create_provider("openai", config)
            mock_provider.assert_called_once_with(config)

    def test_create_anthropic_provider(self):
        """Test creating Anthropic provider through factory."""
        config = AgentConfig(provider="anthropic")

        with patch("praval.providers.anthropic.AnthropicProvider") as mock_provider:
            _ = ProviderFactory.create_provider("anthropic", config)
            mock_provider.assert_called_once_with(config)

    def test_create_cohere_provider(self):
        """Test creating Cohere provider through factory."""
        config = AgentConfig(provider="cohere")

        with patch("praval.providers.cohere.CohereProvider") as mock_provider:
            _ = ProviderFactory.create_provider("cohere", config)
            mock_provider.assert_called_once_with(config)

    def test_invalid_provider_raises_error(self):
        """Test that invalid provider name raises ProviderError."""
        config = AgentConfig()

        with pytest.raises(ProviderError, match="Unsupported provider"):
            ProviderFactory.create_provider("invalid_provider", config)


class TestOpenAIProvider:
    """Test OpenAI provider implementation."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_provider_initialization(self, mock_openai_class):
        """Test OpenAI provider initializes correctly."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        config = AgentConfig(temperature=0.8, max_tokens=500)
        provider = OpenAIProvider(config)

        assert provider.config == config
        assert provider.client == mock_client

    @patch.dict(os.environ, {}, clear=True)
    def test_openai_missing_api_key_raises_error(self):
        """Test that missing API key raises ProviderError."""
        # Ensure OPENAI_API_KEY is not set
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]

        config = AgentConfig()
        with pytest.raises(
            ProviderError, match="OPENAI_API_KEY environment variable not set"
        ):
            OpenAIProvider(config)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_client_initialization_error(self, mock_openai_class):
        """Test OpenAI client initialization error is wrapped properly."""
        mock_openai_class.side_effect = Exception("Connection failed")

        config = AgentConfig()
        with pytest.raises(ProviderError, match="Failed to initialize OpenAI client"):
            OpenAIProvider(config)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_generate_simple_message(self, mock_openai_class):
        """Test OpenAI provider generates response for simple message."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello! How can I help you?"
        mock_response.choices[0].message.tool_calls = None  # Explicitly set to None
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        config = AgentConfig()
        provider = OpenAIProvider(config)

        messages = [{"role": "user", "content": "Hello"}]
        response = provider.generate(messages)

        assert response == "Hello! How can I help you?"
        mock_client.chat.completions.create.assert_called_once()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_generate_empty_choices(self, mock_openai_class):
        """Test OpenAI provider handles empty choices gracefully."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = []  # Empty choices
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        config = AgentConfig()
        provider = OpenAIProvider(config)

        messages = [{"role": "user", "content": "Hello"}]
        response = provider.generate(messages)

        assert response == ""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_openai_generate_none_content(self, mock_openai_class):
        """Test OpenAI provider handles None content gracefully."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None  # None content
        mock_response.choices[0].message.tool_calls = None
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        config = AgentConfig()
        provider = OpenAIProvider(config)

        messages = [{"role": "user", "content": "Hello"}]
        response = provider.generate(messages)

        assert response == ""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
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

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
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


class TestOpenAIToolFormatting:
    """Test OpenAI tool formatting methods."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_format_tools_basic(self, mock_openai_class):
        """Test basic tool formatting for OpenAI."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        def my_tool():
            pass

        tools = [{"function": my_tool, "description": "A test tool"}]
        formatted = provider._format_tools_for_openai(tools)

        assert len(formatted) == 1
        assert formatted[0]["type"] == "function"
        assert formatted[0]["function"]["name"] == "my_tool"
        assert formatted[0]["function"]["description"] == "A test tool"
        assert formatted[0]["function"]["parameters"]["type"] == "object"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_format_tools_with_parameters(self, mock_openai_class):
        """Test tool formatting with parameters."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        def calculator(x, y):
            return x + y

        tools = [
            {
                "function": calculator,
                "description": "Add two numbers",
                "parameters": {
                    "x": {"type": "int", "required": True},
                    "y": {"type": "int", "required": True},
                },
            }
        ]
        formatted = provider._format_tools_for_openai(tools)

        assert len(formatted) == 1
        params = formatted[0]["function"]["parameters"]
        assert "x" in params["properties"]
        assert params["properties"]["x"]["type"] == "integer"
        assert "y" in params["properties"]
        assert params["properties"]["y"]["type"] == "integer"
        assert "x" in params["required"]
        assert "y" in params["required"]

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_format_tools_with_optional_parameters(self, mock_openai_class):
        """Test tool formatting with optional parameters."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        def search(query, limit):
            pass

        tools = [
            {
                "function": search,
                "description": "Search for items",
                "parameters": {
                    "query": {"type": "str", "required": True},
                    "limit": {"type": "int", "required": False},
                },
            }
        ]
        formatted = provider._format_tools_for_openai(tools)

        params = formatted[0]["function"]["parameters"]
        assert "query" in params["required"]
        assert "limit" not in params["required"]

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_format_tools_skips_invalid_tools(self, mock_openai_class):
        """Test that tools without function or description are skipped."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        def valid_tool():
            pass

        tools = [
            {"function": valid_tool, "description": "Valid"},  # Valid
            {"function": valid_tool},  # Missing description
            {"description": "Missing function"},  # Missing function
            {},  # Empty
        ]
        formatted = provider._format_tools_for_openai(tools)

        assert len(formatted) == 1
        assert formatted[0]["function"]["name"] == "valid_tool"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_format_tools_empty_list(self, mock_openai_class):
        """Test formatting empty tool list."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        formatted = provider._format_tools_for_openai([])
        assert formatted == []


class TestOpenAITypeConversion:
    """Test Python type to JSON schema conversion."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_python_type_to_json_schema_str(self, mock_openai_class):
        """Test string type conversion."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        assert provider._python_type_to_json_schema("str") == "string"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_python_type_to_json_schema_int(self, mock_openai_class):
        """Test integer type conversion."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        assert provider._python_type_to_json_schema("int") == "integer"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_python_type_to_json_schema_float(self, mock_openai_class):
        """Test float type conversion."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        assert provider._python_type_to_json_schema("float") == "number"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_python_type_to_json_schema_bool(self, mock_openai_class):
        """Test boolean type conversion."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        assert provider._python_type_to_json_schema("bool") == "boolean"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_python_type_to_json_schema_list(self, mock_openai_class):
        """Test list type conversion."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        assert provider._python_type_to_json_schema("list") == "array"
        assert provider._python_type_to_json_schema("List") == "array"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_python_type_to_json_schema_dict(self, mock_openai_class):
        """Test dict type conversion."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        assert provider._python_type_to_json_schema("dict") == "object"
        assert provider._python_type_to_json_schema("Dict") == "object"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_python_type_to_json_schema_unknown(self, mock_openai_class):
        """Test unknown type defaults to string."""
        mock_openai_class.return_value = Mock()
        config = AgentConfig()
        provider = OpenAIProvider(config)

        assert provider._python_type_to_json_schema("UnknownType") == "string"
        assert provider._python_type_to_json_schema("CustomClass") == "string"


class TestOpenAIToolCallHandling:
    """Test OpenAI tool call handling."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_handle_tool_calls_executes_function(self, mock_openai_class):
        """Test that tool calls execute the correct function."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock the follow-up response
        mock_followup_response = Mock()
        mock_followup_response.choices = [Mock()]
        mock_followup_response.choices[0].message.content = "The result is 7."
        mock_client.chat.completions.create.return_value = mock_followup_response

        config = AgentConfig()
        provider = OpenAIProvider(config)

        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.type = "function"
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "add_numbers"
        mock_tool_call.function.arguments = '{"x": 3, "y": 4}'

        def add_numbers(x, y):
            return x + y

        tools = [{"function": add_numbers, "description": "Add two numbers"}]
        messages = [{"role": "user", "content": "Add 3 and 4"}]

        result = provider._handle_tool_calls([mock_tool_call], tools, messages)

        assert result == "The result is 7."
        # Verify the API was called with the tool results
        mock_client.chat.completions.create.assert_called()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_handle_tool_calls_unknown_function(self, mock_openai_class):
        """Test handling of unknown function in tool calls."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock the follow-up response
        mock_followup_response = Mock()
        mock_followup_response.choices = [Mock()]
        mock_followup_response.choices[0].message.content = (
            "I couldn't find that function."
        )
        mock_client.chat.completions.create.return_value = mock_followup_response

        config = AgentConfig()
        provider = OpenAIProvider(config)

        # Create mock tool call for unknown function
        mock_tool_call = Mock()
        mock_tool_call.type = "function"
        mock_tool_call.id = "call_456"
        mock_tool_call.function.name = "unknown_function"
        mock_tool_call.function.arguments = "{}"

        def known_function():
            return "known"

        tools = [{"function": known_function, "description": "A known function"}]
        messages = [{"role": "user", "content": "Do something"}]

        _ = provider._handle_tool_calls([mock_tool_call], tools, messages)

        # Should have called the API with unknown function error message
        mock_client.chat.completions.create.assert_called()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_handle_tool_calls_function_execution_error(self, mock_openai_class):
        """Test handling of function execution errors in tool calls."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock the follow-up response
        mock_followup_response = Mock()
        mock_followup_response.choices = [Mock()]
        mock_followup_response.choices[0].message.content = "There was an error."
        mock_client.chat.completions.create.return_value = mock_followup_response

        config = AgentConfig()
        provider = OpenAIProvider(config)

        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.type = "function"
        mock_tool_call.id = "call_789"
        mock_tool_call.function.name = "failing_function"
        mock_tool_call.function.arguments = "{}"

        def failing_function():
            raise ValueError("Function failed!")

        tools = [{"function": failing_function, "description": "A failing function"}]
        messages = [{"role": "user", "content": "Run the function"}]

        _ = provider._handle_tool_calls([mock_tool_call], tools, messages)

        # Should handle the error gracefully
        mock_client.chat.completions.create.assert_called()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_handle_tool_calls_follow_up_error_fallback(self, mock_openai_class):
        """Test fallback when follow-up API call fails."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock the follow-up to fail
        mock_client.chat.completions.create.side_effect = Exception("API error")

        config = AgentConfig()
        provider = OpenAIProvider(config)

        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.type = "function"
        mock_tool_call.id = "call_abc"
        mock_tool_call.function.name = "simple_function"
        mock_tool_call.function.arguments = "{}"

        def simple_function():
            return "result_value"

        tools = [{"function": simple_function, "description": "A simple function"}]
        messages = [{"role": "user", "content": "Run it"}]

        result = provider._handle_tool_calls([mock_tool_call], tools, messages)

        # Should fallback to returning tool results
        assert "result_value" in result

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_handle_tool_calls_multiple_calls(self, mock_openai_class):
        """Test handling of multiple tool calls."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock the follow-up response
        mock_followup_response = Mock()
        mock_followup_response.choices = [Mock()]
        mock_followup_response.choices[0].message.content = "Both functions executed."
        mock_client.chat.completions.create.return_value = mock_followup_response

        config = AgentConfig()
        provider = OpenAIProvider(config)

        # Create mock tool calls
        mock_tool_call1 = Mock()
        mock_tool_call1.type = "function"
        mock_tool_call1.id = "call_1"
        mock_tool_call1.function.name = "func_a"
        mock_tool_call1.function.arguments = "{}"

        mock_tool_call2 = Mock()
        mock_tool_call2.type = "function"
        mock_tool_call2.id = "call_2"
        mock_tool_call2.function.name = "func_b"
        mock_tool_call2.function.arguments = "{}"

        def func_a():
            return "A"

        def func_b():
            return "B"

        tools = [
            {"function": func_a, "description": "Function A"},
            {"function": func_b, "description": "Function B"},
        ]
        messages = [{"role": "user", "content": "Run both"}]

        result = provider._handle_tool_calls(
            [mock_tool_call1, mock_tool_call2], tools, messages
        )

        assert result == "Both functions executed."

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_handle_tool_calls_empty_follow_up_response(self, mock_openai_class):
        """Test handling of empty follow-up response."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock empty follow-up response
        mock_followup_response = Mock()
        mock_followup_response.choices = []
        mock_client.chat.completions.create.return_value = mock_followup_response

        config = AgentConfig()
        provider = OpenAIProvider(config)

        mock_tool_call = Mock()
        mock_tool_call.type = "function"
        mock_tool_call.id = "call_empty"
        mock_tool_call.function.name = "test_func"
        mock_tool_call.function.arguments = "{}"

        def test_func():
            return "test"

        tools = [{"function": test_func, "description": "Test function"}]
        messages = [{"role": "user", "content": "Test"}]

        result = provider._handle_tool_calls([mock_tool_call], tools, messages)

        assert result == "No response generated after tool execution"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    @patch("openai.OpenAI")
    def test_generate_with_actual_tool_calls(self, mock_openai_class):
        """Test generate method when API returns tool calls."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Create mock tool call object
        mock_tool_call = Mock()
        mock_tool_call.type = "function"
        mock_tool_call.id = "call_gen"
        mock_tool_call.function.name = "get_weather"
        mock_tool_call.function.arguments = '{"location": "Paris"}'

        # First response with tool calls
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [mock_tool_call]

        # Follow-up response
        mock_followup = Mock()
        mock_followup.choices = [Mock()]
        mock_followup.choices[0].message.content = "The weather in Paris is sunny."

        mock_client.chat.completions.create.side_effect = [mock_response, mock_followup]

        config = AgentConfig()
        provider = OpenAIProvider(config)

        def get_weather(location):
            return f"Sunny in {location}"

        messages = [{"role": "user", "content": "What's the weather in Paris?"}]
        tools = [{"function": get_weather, "description": "Get weather for a location"}]

        result = provider.generate(messages, tools)

        assert result == "The weather in Paris is sunny."
        assert mock_client.chat.completions.create.call_count == 2


class TestAnthropicProvider:
    """Test Anthropic provider implementation."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    @patch("anthropic.Anthropic")
    def test_anthropic_provider_initialization(self, mock_anthropic_class):
        """Test Anthropic provider initializes correctly."""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        config = AgentConfig(temperature=0.8, max_tokens=500)
        provider = AnthropicProvider(config)

        assert provider.config == config
        assert provider.client == mock_client

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    @patch("anthropic.Anthropic")
    def test_anthropic_generate_simple_message(self, mock_anthropic_class):
        """Test Anthropic provider generates response for simple message."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "Hello! How can I assist you today?"
        mock_response.content[0].type = "text"  # Anthropic checks content type
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        config = AgentConfig()
        provider = AnthropicProvider(config)

        messages = [{"role": "user", "content": "Hello"}]
        response = provider.generate(messages)

        assert response == "Hello! How can I assist you today?"
        mock_client.messages.create.assert_called_once()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    @patch("anthropic.Anthropic")
    def test_anthropic_handles_system_messages(self, mock_anthropic_class):
        """Test Anthropic provider handles system messages correctly."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "I am a helpful assistant."
        mock_response.content[0].type = "text"  # Anthropic checks content type
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        config = AgentConfig()
        provider = AnthropicProvider(config)

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What are you?"},
        ]
        response = provider.generate(messages)

        assert response == "I am a helpful assistant."

        # Verify system message was passed correctly
        call_args = mock_client.messages.create.call_args
        assert "system" in call_args.kwargs

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    @patch("anthropic.Anthropic")
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

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    @patch("anthropic.Anthropic")
    def test_anthropic_generate_with_tools(self, mock_anthropic_class):
        """Test Anthropic provider passes tools to the API."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "Done"
        mock_response.content[0].type = "text"
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        config = AgentConfig()
        provider = AnthropicProvider(config)

        def add(x: int, y: int) -> int:
            return x + y

        messages = [{"role": "user", "content": "Add 1 and 2"}]
        tools = [
            {
                "function": add,
                "description": "Add numbers",
                "parameters": {
                    "x": {"type": "int", "required": True},
                    "y": {"type": "int", "required": True},
                },
            }
        ]

        result = provider.generate(messages, tools)
        assert result == "Done"

        call_args = mock_client.messages.create.call_args
        assert "tools" in call_args.kwargs

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    @patch("anthropic.Anthropic")
    def test_anthropic_handles_tool_calls(self, mock_anthropic_class):
        """
        Test Anthropic provider executes tool calls and returns a follow-up response.
        """
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # First response includes a tool_use block
        tool_use = Mock()
        tool_use.type = "tool_use"
        tool_use.id = "tool_1"
        tool_use.name = "add"
        tool_use.input = {"x": 2, "y": 5}

        first_response = Mock()
        first_response.content = [tool_use]

        # Follow-up response returns text
        followup_response = Mock()
        followup_block = Mock()
        followup_block.type = "text"
        followup_block.text = "Result is 7"
        followup_response.content = [followup_block]

        mock_client.messages.create.side_effect = [first_response, followup_response]

        config = AgentConfig()
        provider = AnthropicProvider(config)

        def add(x: int, y: int) -> int:
            return x + y

        messages = [{"role": "user", "content": "Add"}]
        tools = [
            {
                "function": add,
                "description": "Add numbers",
                "parameters": {
                    "x": {"type": "int", "required": True},
                    "y": {"type": "int", "required": True},
                },
            }
        ]

        result = provider.generate(messages, tools)
        assert result == "Result is 7"
        assert mock_client.messages.create.call_count == 2


class TestCohereProvider:
    """Test Cohere provider implementation."""

    @patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
    @patch("cohere.Client")
    def test_cohere_provider_initialization(self, mock_cohere_class):
        """Test Cohere provider initializes correctly."""
        mock_client = Mock()
        mock_cohere_class.return_value = mock_client

        config = AgentConfig(temperature=0.8, max_tokens=500)
        provider = CohereProvider(config)

        assert provider.config == config
        assert provider.client == mock_client

    @patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
    @patch("cohere.Client")
    def test_cohere_generate_with_tools(self, mock_cohere_class):
        """Test Cohere provider passes tools to the API."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "OK"
        mock_client.chat.return_value = mock_response
        mock_cohere_class.return_value = mock_client

        config = AgentConfig()
        provider = CohereProvider(config)

        def echo(text: str) -> str:
            return text

        messages = [{"role": "user", "content": "Hi"}]
        tools = [
            {
                "function": echo,
                "description": "Echo text",
                "parameters": {"text": {"type": "str", "required": True}},
            }
        ]

        result = provider.generate(messages, tools)
        assert result == "OK"

        call_args = mock_client.chat.call_args
        assert "tools" in call_args.kwargs

    @patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
    @patch("cohere.Client")
    def test_cohere_handles_tool_calls(self, mock_cohere_class):
        """Test Cohere provider executes tool calls and returns follow-up response."""
        mock_client = Mock()
        mock_cohere_class.return_value = mock_client

        # First response includes tool calls
        tool_call = {"name": "echo", "args": {"text": "hello"}}
        first_response = Mock()
        first_response.tool_calls = [tool_call]

        followup_response = Mock()
        followup_response.text = "hello"

        mock_client.chat.side_effect = [first_response, followup_response]

        config = AgentConfig()
        provider = CohereProvider(config)

        def echo(text: str) -> str:
            return text

        messages = [{"role": "user", "content": "Echo"}]
        tools = [
            {
                "function": echo,
                "description": "Echo text",
                "parameters": {"text": {"type": "str", "required": True}},
            }
        ]

        result = provider.generate(messages, tools)
        assert result == "hello"
        assert mock_client.chat.call_count == 2

    @patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
    @patch("cohere.Client")
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

    @patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
    @patch("cohere.Client")
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
            {"role": "user", "content": "What's my name?"},
        ]
        response = provider.generate(messages)

        assert response == "I remember our previous conversation."

        # Verify conversation history was passed correctly
        call_args = mock_client.chat.call_args
        assert "chat_history" in call_args.kwargs

    @patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
    @patch("cohere.Client")
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

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-test-key"})
    def test_temperature_configuration_applied(self):
        """Test that temperature configuration is applied to providers."""
        config = AgentConfig(temperature=0.9)

        with patch("openai.OpenAI"):
            provider = OpenAIProvider(config)
            assert provider.config.temperature == 0.9

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-test-key"})
    def test_max_tokens_configuration_applied(self):
        """Test that max_tokens configuration is applied to providers."""
        config = AgentConfig(max_tokens=2000)

        with patch("anthropic.Anthropic"):
            provider = AnthropicProvider(config)
            assert provider.config.max_tokens == 2000

    @patch.dict(os.environ, {"COHERE_API_KEY": "fake-test-key"})
    def test_system_message_configuration_applied(self):
        """Test that system message configuration is handled correctly."""
        config = AgentConfig(system_message="You are a coding assistant.")

        with patch("cohere.Client"):
            provider = CohereProvider(config)
            assert provider.config.system_message == "You are a coding assistant."
