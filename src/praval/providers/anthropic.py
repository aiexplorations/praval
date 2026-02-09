"""
Anthropic provider implementation for Praval framework.

Provides integration with Anthropic's Claude models through the
Messages API with support for conversation history and system messages.
"""

import os
from typing import List, Dict, Any, Optional

import anthropic
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

class AnthropicProvider:
    """
    Anthropic provider for LLM interactions.
    
    Handles communication with Anthropic's Claude models through the
    Messages API with proper system message handling.
    """
    
    def __init__(self, config):
        """
        Initialize Anthropic provider.
        
        Args:
            config: AgentConfig object with provider settings
            
        Raises:
            ProviderError: If Anthropic client initialization fails
        """
        self.config = config
        
        try:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ProviderError("ANTHROPIC_API_KEY environment variable not set")
                
            self.client = anthropic.Anthropic(api_key=api_key)
        except Exception as e:
            raise ProviderError(f"Failed to initialize Anthropic client: {_redact_secrets(str(e))}") from e
    
    def generate(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Generate a response using Anthropic's Messages API.
        
        Args:
            messages: Conversation history as list of message dictionaries
            tools: Optional list of available tools
            
        Returns:
            Generated response as a string
            
        Raises:
            ProviderError: If API call fails
        """
        try:
            # Separate system messages from conversation messages
            system_message = self._extract_system_message(messages)
            conversation_messages = self._filter_conversation_messages(messages)
            
            # Prepare the API call parameters
            call_params = {
                "model": "claude-3-sonnet-20240229",
                "messages": conversation_messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens
            }
            
            # Add system message if present
            if system_message:
                call_params["system"] = system_message

            # Add tools if provided
            if tools:
                formatted_tools = self._format_tools_for_anthropic(tools)
                if formatted_tools:
                    call_params["tools"] = formatted_tools
            
            # Make the API call
            response = self.client.messages.create(**call_params)
            
            # Extract the response content
            if response.content and len(response.content) > 0:
                content_blocks = response.content
                tool_uses = []
                for block in content_blocks:
                    block_type = getattr(block, "type", None) or block.get("type")
                    if block_type == "tool_use":
                        tool_uses.append(block)
                    elif block_type == "text":
                        # If there are no tool calls, return the first text
                        if not tool_uses:
                            return getattr(block, "text", None) or block.get("text", "")

                if tool_uses and tools:
                    return self._handle_tool_calls(tool_uses, tools, conversation_messages, system_message)
            
            return ""
            
        except Exception as e:
            raise ProviderError(f"Anthropic API error: {_redact_secrets(str(e))}") from e
    
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
    
    def _filter_conversation_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Filter out system messages to get conversation messages only.
        
        Args:
            messages: List of all messages including system messages
            
        Returns:
            List of conversation messages (user/assistant only)
        """
        conversation_messages = []
        
        for message in messages:
            role = message.get("role", "")
            if role in ["user", "assistant"]:
                conversation_messages.append({
                    "role": role,
                    "content": message.get("content", "")
                })
        
        return conversation_messages
    def _format_tools_for_anthropic(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format tools for Anthropic tool use schema."""
        formatted_tools = []
        for tool in tools or []:
            if "function" not in tool or "description" not in tool:
                continue
            tool_name = tool["function"].__name__
            tool_def = {
                "name": tool_name,
                "description": tool["description"],
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }

            for param_name, param_info in (tool.get("parameters") or {}).items():
                param_type = param_info.get("type", "str")
                json_type = self._python_type_to_json_schema(param_type)
                tool_def["input_schema"]["properties"][param_name] = {"type": json_type}
                if param_info.get("required", False):
                    tool_def["input_schema"]["required"].append(param_name)

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

    def _handle_tool_calls(self, tool_uses: List[Any], available_tools: List[Dict[str, Any]], messages: List[Dict[str, str]], system_message: Optional[str]) -> str:
        tool_map = {
            tool["function"].__name__: tool["function"]
            for tool in available_tools
            if "function" in tool
        }

        tool_results = []
        for tool_use in tool_uses:
            tool_name = getattr(tool_use, "name", None) or tool_use.get("name")
            tool_id = getattr(tool_use, "id", None) or tool_use.get("id")
            tool_input = getattr(tool_use, "input", None) or tool_use.get("input") or {}

            if tool_name in tool_map:
                try:
                    result = tool_map[tool_name](**tool_input)
                    content = str(result)
                except Exception as e:
                    content = f"Error: {str(e)}"
            else:
                content = f"Unknown function: {tool_name}"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": content
            })

        followup_messages = list(messages)
        followup_messages.append({"role": "assistant", "content": tool_uses})
        followup_messages.append({"role": "user", "content": tool_results})

        call_params = {
            "model": "claude-3-sonnet-20240229",
            "messages": followup_messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens
        }
        if system_message:
            call_params["system"] = system_message

        try:
            response = self.client.messages.create(**call_params)
            if response.content and len(response.content) > 0:
                content_blocks = response.content
                for block in content_blocks:
                    block_type = getattr(block, "type", None) or block.get("type")
                    if block_type == "text":
                        return getattr(block, "text", None) or block.get("text", "")
            return "No response generated after tool execution"
        except Exception:
            return "\n".join([r["content"] for r in tool_results])
