"""
Cohere provider implementation for Praval framework.

Provides integration with Cohere's chat models through their
Chat API with support for conversation history.
"""

import os
from typing import List, Dict, Any, Optional

import cohere
from ..core.exceptions import ProviderError




def _redact_secrets(message: str) -> str:
    if not message:
        return message
    secrets = [
        os.getenv("OPENAI_API_KEY"),
        os.getenv("ANTHROPIC_API_KEY"),
        os.getenv("COHERE_API_KEY")
    ]
    redacted = message
    for secret in secrets:
        if secret and secret in redacted:
            redacted = redacted.replace(secret, "***")
    return redacted

class CohereProvider:
    """
    Cohere provider for LLM interactions.
    
    Handles communication with Cohere's chat models through the
    Chat API with conversation history support.
    """
    
    def __init__(self, config):
        """
        Initialize Cohere provider.
        
        Args:
            config: AgentConfig object with provider settings
            
        Raises:
            ProviderError: If Cohere client initialization fails
        """
        self.config = config
        
        try:
            api_key = os.getenv("COHERE_API_KEY")
            if not api_key:
                raise ProviderError("COHERE_API_KEY environment variable not set")
                
            self.client = cohere.Client(api_key)
        except Exception as e:
            raise ProviderError(f"Failed to initialize Cohere client: {_redact_secrets(str(e))}") from e
    
    def generate(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Generate a response using Cohere's Chat API.
        
        Args:
            messages: Conversation history as list of message dictionaries
            tools: Optional list of available tools
            
        Returns:
            Generated response as a string
            
        Raises:
            ProviderError: If API call fails
        """
        try:
            # Extract the current user message and chat history
            current_message, chat_history = self._prepare_chat_format(messages)
            
            # Prepare the API call parameters
            call_params = {
                "message": current_message,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens
            }
            
            # Add chat history if available
            if chat_history:
                call_params["chat_history"] = chat_history
            
            # Add system message as preamble if present
            system_message = self._extract_system_message(messages)
            if system_message:
                call_params["preamble"] = system_message

            # Add tools if provided
            if tools:
                formatted_tools = self._format_tools_for_cohere(tools)
                if formatted_tools:
                    call_params["tools"] = formatted_tools
            
            # Make the API call
            response = self.client.chat(**call_params)
            
            # Tool calls handling (if supported by response)
            tool_calls = getattr(response, "tool_calls", None)
            if tools and tool_calls:
                if isinstance(tool_calls, (list, tuple)) and tool_calls:
                    return self._handle_tool_calls(tool_calls, tools, messages)

            # Extract the response text
            return response.text if hasattr(response, 'text') else ""
            
        except Exception as e:
            raise ProviderError(f"Cohere API error: {_redact_secrets(str(e))}") from e
    
    def _prepare_chat_format(self, messages: List[Dict[str, str]]) -> tuple[str, List[Dict[str, str]]]:
        """
        Prepare messages in Cohere's chat format.
        
        Cohere expects the current user message separately from chat history.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            Tuple of (current_message, chat_history)
        """
        # Filter out system messages for conversation
        conversation_messages = [
            msg for msg in messages 
            if msg.get("role") in ["user", "assistant"]
        ]
        
        if not conversation_messages:
            return "", []
        
        # The last message should be the current user message
        current_message = ""
        chat_history = []
        
        if conversation_messages:
            # Get the last user message as current message
            last_message = conversation_messages[-1]
            if last_message.get("role") == "user":
                current_message = last_message.get("content", "")
                
                # Convert previous messages to chat history format
                for i, msg in enumerate(conversation_messages[:-1]):
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    
                    if role == "user":
                        chat_history.append({"role": "USER", "message": content})
                    elif role == "assistant":
                        chat_history.append({"role": "CHATBOT", "message": content})
            else:
                # If last message is not from user, treat it as continuation
                current_message = "Please continue."
                
                # Convert all messages to chat history
                for msg in conversation_messages:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    
                    if role == "user":
                        chat_history.append({"role": "USER", "message": content})
                    elif role == "assistant":
                        chat_history.append({"role": "CHATBOT", "message": content})
        
        return current_message, chat_history
    
    def _extract_system_message(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """
        Extract system message from conversation messages.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            System message content if found, None otherwise
        """
        for message in messages:
            if message.get("role") == "system":
                return message.get("content", "")
        return None

    def _format_tools_for_cohere(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format tools for Cohere tool calling schema."""
        formatted_tools = []
        for tool in tools or []:
            if "function" not in tool or "description" not in tool:
                continue
            tool_def = {
                "name": tool["function"].__name__,
                "description": tool["description"],
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
            for param_name, param_info in (tool.get("parameters") or {}).items():
                param_type = param_info.get("type", "str")
                json_type = self._python_type_to_json_schema(param_type)
                tool_def["parameters"]["properties"][param_name] = {"type": json_type}
                if param_info.get("required", False):
                    tool_def["parameters"]["required"].append(param_name)
            formatted_tools.append(tool_def)
        return formatted_tools

    def _python_type_to_json_schema(self, python_type: str) -> str:
        type_mapping = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "list": "array",
            "dict": "object",
            "List": "array",
            "Dict": "object"
        }
        return type_mapping.get(python_type, "string")

    def _handle_tool_calls(self, tool_calls: List[Any], available_tools: List[Dict[str, Any]], original_messages: List[Dict[str, str]]) -> str:
        tool_map = {
            tool["function"].__name__: tool["function"]
            for tool in available_tools
            if "function" in tool
        }

        tool_results = []
        for tool_call in tool_calls:
            name = getattr(tool_call, "name", None) or tool_call.get("name")
            args = getattr(tool_call, "args", None) or tool_call.get("args") or {}
            if name in tool_map:
                try:
                    result = tool_map[name](**args)
                    tool_results.append({"name": name, "result": str(result)})
                except Exception as e:
                    tool_results.append({"name": name, "result": f"Error: {str(e)}"})
            else:
                tool_results.append({"name": name, "result": f"Unknown function: {name}"})

        # Attempt a follow-up call with tool results
        try:
            current_message, chat_history = self._prepare_chat_format(original_messages)
            call_params = {
                "message": current_message,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }
            if chat_history:
                call_params["chat_history"] = chat_history

            system_message = self._extract_system_message(original_messages)
            if system_message:
                call_params["preamble"] = system_message

            call_params["tool_results"] = tool_results
            response = self.client.chat(**call_params)
            return response.text if hasattr(response, 'text') else ""
        except Exception:
            return "\n".join([r["result"] for r in tool_results])
