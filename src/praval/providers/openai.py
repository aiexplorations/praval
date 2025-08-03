"""
OpenAI provider implementation for Praval framework.

Provides integration with OpenAI's Chat Completions API with support
for conversation history, tool calling, and streaming responses.
"""

import os
from typing import List, Dict, Any, Optional

import openai
from ..core.exceptions import ProviderError


class OpenAIProvider:
    """
    OpenAI provider for LLM interactions.
    
    Handles communication with OpenAI's GPT models through the
    Chat Completions API with support for tools and conversation history.
    """
    
    def __init__(self, config):
        """
        Initialize OpenAI provider.
        
        Args:
            config: AgentConfig object with provider settings
            
        Raises:
            ProviderError: If OpenAI client initialization fails
        """
        self.config = config
        
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ProviderError("OPENAI_API_KEY environment variable not set")
                
            self.client = openai.OpenAI(api_key=api_key)
        except Exception as e:
            raise ProviderError(f"Failed to initialize OpenAI client: {str(e)}") from e
    
    def generate(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Generate a response using OpenAI's Chat Completions API.
        
        Args:
            messages: Conversation history as list of message dictionaries
            tools: Optional list of available tools for function calling
            
        Returns:
            Generated response as a string
            
        Raises:
            ProviderError: If API call fails
        """
        try:
            # Prepare the API call parameters
            call_params = {
                "model": "gpt-3.5-turbo",
                "messages": messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens
            }
            
            # Add tools if provided
            if tools:
                formatted_tools = self._format_tools_for_openai(tools)
                if formatted_tools:
                    call_params["tools"] = formatted_tools
                    call_params["tool_choice"] = "auto"
            
            # Make the API call
            response = self.client.chat.completions.create(**call_params)
            
            # Extract the response content
            if response.choices and response.choices[0].message:
                message = response.choices[0].message
                
                # Handle tool calls if present
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    return self._handle_tool_calls(message.tool_calls, tools, messages)
                
                # Return regular message content
                return message.content or ""
            
            return ""
            
        except Exception as e:
            raise ProviderError(f"OpenAI API error: {str(e)}") from e
    
    def _format_tools_for_openai(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format tools for OpenAI's function calling format.
        
        Args:
            tools: List of tool dictionaries from Praval format
            
        Returns:
            List of tools in OpenAI's expected format
        """
        formatted_tools = []
        
        for tool in tools:
            if "function" not in tool or "description" not in tool:
                continue
                
            formatted_tool = {
                "type": "function",
                "function": {
                    "name": tool["function"].__name__,
                    "description": tool["description"],
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            
            # Add parameter information if available
            if "parameters" in tool:
                for param_name, param_info in tool["parameters"].items():
                    # Convert Python type to JSON schema type
                    python_type = param_info.get("type", "str")
                    json_type = self._python_type_to_json_schema(python_type)
                    
                    formatted_tool["function"]["parameters"]["properties"][param_name] = {
                        "type": json_type
                    }
                    if param_info.get("required", False):
                        formatted_tool["function"]["parameters"]["required"].append(param_name)
            
            formatted_tools.append(formatted_tool)
        
        return formatted_tools
    
    def _python_type_to_json_schema(self, python_type: str) -> str:
        """
        Convert Python type annotation to JSON schema type.
        
        Args:
            python_type: Python type name as string
            
        Returns:
            JSON schema type string
        """
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
        """
        Handle tool/function calls from OpenAI response.
        
        Args:
            tool_calls: Tool calls from OpenAI response
            available_tools: List of available tool functions
            original_messages: Original conversation messages
            
        Returns:
            String response after executing tool calls and getting LLM response
        """
        # Create a mapping of tool names to functions
        tool_map = {
            tool["function"].__name__: tool["function"] 
            for tool in available_tools 
            if "function" in tool
        }
        
        # Execute tool calls and collect results
        tool_messages = []
        
        for tool_call in tool_calls:
            if tool_call.type == "function":
                function_name = tool_call.function.name
                
                if function_name in tool_map:
                    try:
                        # Parse arguments and call the function
                        import json
                        args = json.loads(tool_call.function.arguments)
                        result = tool_map[function_name](**args)
                        
                        # Add tool result to messages
                        tool_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": str(result)
                        })
                    except Exception as e:
                        tool_messages.append({
                            "role": "tool", 
                            "tool_call_id": tool_call.id,
                            "content": f"Error: {str(e)}"
                        })
                else:
                    tool_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id, 
                        "content": f"Unknown function: {function_name}"
                    })
        
        # Now make another API call with the tool results to get the final response
        extended_messages = original_messages.copy()
        
        # Add the assistant's tool call message
        extended_messages.append({
            "role": "assistant",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                } for tc in tool_calls
            ]
        })
        
        # Add tool responses
        extended_messages.extend(tool_messages)
        
        try:
            # Make follow-up call to get final response
            follow_up_response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=extended_messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            
            if follow_up_response.choices and follow_up_response.choices[0].message:
                return follow_up_response.choices[0].message.content or ""
            
            return "No response generated after tool execution"
            
        except Exception as e:
            # Fallback to simple tool output if follow-up fails
            return "\n".join([msg["content"] for msg in tool_messages])