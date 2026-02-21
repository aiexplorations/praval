"""
OpenAI provider implementation for Praval framework.

Provides integration with OpenAI's Chat Completions API with support
for conversation history, tool calling, and streaming responses.
"""

import os
from typing import Any, Dict, List, Optional

import openai

from ..core.exceptions import (
    HITLConfigurationError,
    InterventionRequired,
    ProviderError,
)
from ..hitl.runtime import HITLRuntime


def _redact_secrets(message: str) -> str:
    if not message:
        return message
    secrets = [
        os.getenv("OPENAI_API_KEY"),
        os.getenv("ANTHROPIC_API_KEY"),
        os.getenv("COHERE_API_KEY"),
    ]
    redacted = message
    for secret in secrets:
        if secret and secret in redacted:
            redacted = redacted.replace(secret, "***")
    return redacted


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
            raise ProviderError(
                f"Failed to initialize OpenAI client: {_redact_secrets(str(e))}"
            ) from e

    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        hitl_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a response using OpenAI's Chat Completions API.

        Args:
            messages: Conversation history as list of message dictionaries
            tools: Optional list of available tools for function calling
            hitl_context: Optional run metadata for HITL gating/resume

        Returns:
            Generated response as a string

        Raises:
            ProviderError: If API call fails
        """
        try:
            call_params = {
                "model": "gpt-3.5-turbo",
                "messages": messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }

            if tools:
                formatted_tools = self._format_tools_for_openai(tools)
                if formatted_tools:
                    call_params["tools"] = formatted_tools
                    call_params["tool_choice"] = "auto"

            response = self.client.chat.completions.create(**call_params)

            if response.choices and response.choices[0].message:
                message = response.choices[0].message
                if hasattr(message, "tool_calls") and message.tool_calls:
                    return self._handle_tool_calls(
                        message.tool_calls,
                        tools,
                        messages,
                        hitl_context=hitl_context,
                    )
                return message.content or ""

            return ""

        except (InterventionRequired, HITLConfigurationError):
            raise
        except Exception as e:
            raise ProviderError(f"OpenAI API error: {_redact_secrets(str(e))}") from e

    def _format_tools_for_openai(
        self, tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Format tools for OpenAI's function calling format."""
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
                        "required": [],
                    },
                },
            }

            if "parameters" in tool:
                for param_name, param_info in tool["parameters"].items():
                    python_type = param_info.get("type", "str")
                    json_type = self._python_type_to_json_schema(python_type)

                    formatted_tool["function"]["parameters"]["properties"][
                        param_name
                    ] = {"type": json_type}
                    if param_info.get("required", False):
                        formatted_tool["function"]["parameters"]["required"].append(
                            param_name
                        )

            formatted_tools.append(formatted_tool)

        return formatted_tools

    def _python_type_to_json_schema(self, python_type: str) -> str:
        """Convert Python type annotation to JSON schema type."""
        type_mapping = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "list": "array",
            "dict": "object",
            "List": "array",
            "Dict": "object",
        }
        return type_mapping.get(python_type, "string")

    def _build_runtime(
        self, hitl_context: Optional[Dict[str, Any]]
    ) -> Optional[HITLRuntime]:
        if not hitl_context:
            return None
        run_id = hitl_context.get("run_id")
        agent_name = hitl_context.get("agent_name")
        provider_name = hitl_context.get("provider_name")
        if not run_id or not agent_name or not provider_name:
            return None
        return HITLRuntime(
            run_id=run_id,
            agent_name=agent_name,
            provider_name=provider_name,
            hitl_enabled=bool(hitl_context.get("enabled", False)),
            db_path=hitl_context.get("db_path"),
            trace_id=hitl_context.get("trace_id"),
        )

    def _serialize_tool_calls(self, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        serialized: List[Dict[str, Any]] = []
        for tool_call in tool_calls:
            if isinstance(tool_call, dict):
                call_type = tool_call.get("type")
                tool_id = tool_call.get("id")
                function_obj = tool_call.get("function", {})
                function_name = function_obj.get("name")
                arguments = function_obj.get("arguments", "{}")
            else:
                call_type = getattr(tool_call, "type", None)
                tool_id = getattr(tool_call, "id", None)
                function_obj = getattr(tool_call, "function", None)
                function_name = getattr(function_obj, "name", None)
                arguments = getattr(function_obj, "arguments", "{}")

            if call_type == "function":
                serialized.append(
                    {
                        "id": tool_id,
                        "type": "function",
                        "function": {
                            "name": function_name,
                            "arguments": arguments,
                        },
                    }
                )
        return serialized

    def _execute_tool_calls(
        self,
        *,
        serialized_tool_calls: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
        original_messages: List[Dict[str, str]],
        hitl_context: Optional[Dict[str, Any]],
        start_index: int = 0,
        existing_tool_messages: Optional[List[Dict[str, str]]] = None,
        resume_intervention: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        runtime = self._build_runtime(hitl_context)
        tool_messages = list(existing_tool_messages or [])
        tool_map = {
            tool["function"].__name__: tool
            for tool in available_tools or []
            if "function" in tool
        }

        for idx in range(start_index, len(serialized_tool_calls)):
            tool_call = serialized_tool_calls[idx]
            function_name = tool_call["function"]["name"]
            arguments = tool_call["function"]["arguments"]
            tool_call_id = tool_call["id"]

            if (
                idx == start_index
                and resume_intervention is not None
                and runtime is not None
            ):
                result_content = runtime.execute_with_decision(
                    intervention=resume_intervention,
                    available_tools=available_tools or [],
                )
            elif runtime is not None:
                continuation_state = {
                    "schema": "openai_tool_v1",
                    "original_messages": original_messages,
                    "tool_calls": serialized_tool_calls,
                    "current_index": idx,
                    "tool_messages": list(tool_messages),
                }
                result_content = runtime.execute_or_interrupt(
                    tool_call_id=tool_call_id,
                    function_name=function_name,
                    raw_args=arguments,
                    available_tools=available_tools or [],
                    continuation_state=continuation_state,
                )
            else:
                tool_def = tool_map.get(function_name)
                if tool_def is None:
                    result_content = f"Unknown function: {function_name}"
                else:
                    try:
                        import json

                        args = json.loads(arguments)
                        result_content = str(tool_def["function"](**args))
                    except Exception as e:
                        result_content = f"Error: {str(e)}"

            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": result_content,
                }
            )

        return tool_messages

    def _follow_up_response(
        self,
        *,
        serialized_tool_calls: List[Dict[str, Any]],
        original_messages: List[Dict[str, str]],
        tool_messages: List[Dict[str, str]],
    ) -> str:
        extended_messages = list(original_messages)
        extended_messages.append(
            {
                "role": "assistant",
                "tool_calls": serialized_tool_calls,
            }
        )
        extended_messages.extend(tool_messages)

        try:
            follow_up_response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=extended_messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            if follow_up_response.choices and follow_up_response.choices[0].message:
                return follow_up_response.choices[0].message.content or ""

            return "No response generated after tool execution"

        except Exception:
            return "\n".join([msg["content"] for msg in tool_messages])

    def _handle_tool_calls(
        self,
        tool_calls: List[Any],
        available_tools: List[Dict[str, Any]],
        original_messages: List[Dict[str, str]],
        hitl_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Handle OpenAI tool/function calls with optional HITL interception."""
        serialized_tool_calls = self._serialize_tool_calls(tool_calls)
        tool_messages = self._execute_tool_calls(
            serialized_tool_calls=serialized_tool_calls,
            available_tools=available_tools or [],
            original_messages=original_messages,
            hitl_context=hitl_context,
        )
        return self._follow_up_response(
            serialized_tool_calls=serialized_tool_calls,
            original_messages=original_messages,
            tool_messages=tool_messages,
        )

    def resume_tool_flow(
        self,
        suspended_state: Dict[str, Any],
        tools: Optional[List[Dict[str, Any]]],
        hitl_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Resume an interrupted OpenAI tool-call flow from persisted state."""
        if suspended_state.get("schema") != "openai_tool_v1":
            raise ProviderError("Invalid suspended state for OpenAI provider")

        resume_intervention = (hitl_context or {}).get("resume_intervention")
        if not resume_intervention:
            raise ProviderError("Missing resume intervention for suspended run")

        serialized_tool_calls = suspended_state.get("tool_calls", [])
        original_messages = suspended_state.get("original_messages", [])
        current_index = int(suspended_state.get("current_index", 0))
        existing_tool_messages = suspended_state.get("tool_messages", [])

        tool_messages = self._execute_tool_calls(
            serialized_tool_calls=serialized_tool_calls,
            available_tools=tools or [],
            original_messages=original_messages,
            hitl_context=hitl_context,
            start_index=current_index,
            existing_tool_messages=existing_tool_messages,
            resume_intervention=resume_intervention,
        )
        return self._follow_up_response(
            serialized_tool_calls=serialized_tool_calls,
            original_messages=original_messages,
            tool_messages=tool_messages,
        )
