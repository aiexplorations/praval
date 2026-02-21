"""
Anthropic provider implementation for Praval framework.

Provides integration with Anthropic's Claude models through the
Messages API with support for conversation history and system messages.
"""

import os
from typing import Any, Dict, List, Optional

import anthropic

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


class AnthropicProvider:
    """Anthropic provider for LLM interactions."""

    def __init__(self, config):
        self.config = config

        try:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ProviderError("ANTHROPIC_API_KEY environment variable not set")

            self.client = anthropic.Anthropic(api_key=api_key)
        except Exception as e:
            raise ProviderError(
                f"Failed to initialize Anthropic client: {_redact_secrets(str(e))}"
            ) from e

    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        hitl_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a response using Anthropic's Messages API."""
        try:
            system_message = self._extract_system_message(messages)
            conversation_messages = self._filter_conversation_messages(messages)

            call_params = {
                "model": "claude-3-sonnet-20240229",
                "messages": conversation_messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }

            if system_message:
                call_params["system"] = system_message

            if tools:
                formatted_tools = self._format_tools_for_anthropic(tools)
                if formatted_tools:
                    call_params["tools"] = formatted_tools

            response = self.client.messages.create(**call_params)

            if response.content and len(response.content) > 0:
                content_blocks = response.content
                tool_uses = []
                for block in content_blocks:
                    block_type = getattr(block, "type", None) or (
                        block.get("type") if isinstance(block, dict) else None
                    )
                    if block_type == "tool_use":
                        tool_uses.append(block)
                    elif block_type == "text" and not tool_uses:
                        return getattr(block, "text", None) or (
                            block.get("text", "") if isinstance(block, dict) else ""
                        )

                if tool_uses and tools:
                    return self._handle_tool_calls(
                        tool_uses,
                        tools,
                        conversation_messages,
                        system_message,
                        hitl_context=hitl_context,
                    )

            return ""

        except (InterventionRequired, HITLConfigurationError):
            raise
        except Exception as e:
            raise ProviderError(
                f"Anthropic API error: {_redact_secrets(str(e))}"
            ) from e

    def _extract_system_message(self, messages: List[Dict[str, str]]) -> Optional[str]:
        for message in messages:
            if message.get("role") == "system":
                return message.get("content", "")
        return None

    def _filter_conversation_messages(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        conversation_messages = []
        for message in messages:
            role = message.get("role", "")
            if role in ["user", "assistant"]:
                conversation_messages.append(
                    {
                        "role": role,
                        "content": message.get("content", ""),
                    }
                )
        return conversation_messages

    def _format_tools_for_anthropic(
        self, tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
                    "required": [],
                },
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

    def _serialize_tool_uses(self, tool_uses: List[Any]) -> List[Dict[str, Any]]:
        serialized: List[Dict[str, Any]] = []
        for tool_use in tool_uses:
            if isinstance(tool_use, dict):
                tool_type = tool_use.get("type")
                tool_id = tool_use.get("id")
                tool_name = tool_use.get("name")
                tool_input = tool_use.get("input") or {}
            else:
                tool_type = getattr(tool_use, "type", None)
                tool_id = getattr(tool_use, "id", None)
                tool_name = getattr(tool_use, "name", None)
                tool_input = getattr(tool_use, "input", None) or {}

            if tool_type == "tool_use":
                serialized.append(
                    {
                        "type": "tool_use",
                        "id": tool_id,
                        "name": tool_name,
                        "input": tool_input,
                    }
                )
        return serialized

    def _execute_tool_uses(
        self,
        *,
        serialized_tool_uses: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
        messages: List[Dict[str, str]],
        system_message: Optional[str],
        hitl_context: Optional[Dict[str, Any]],
        start_index: int = 0,
        existing_tool_results: Optional[List[Dict[str, Any]]] = None,
        resume_intervention: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        runtime = self._build_runtime(hitl_context)
        tool_results = list(existing_tool_results or [])
        tool_map = {
            tool["function"].__name__: tool
            for tool in available_tools or []
            if "function" in tool
        }

        for idx in range(start_index, len(serialized_tool_uses)):
            tool_use = serialized_tool_uses[idx]
            tool_name = tool_use.get("name")
            tool_id = tool_use.get("id")
            tool_input = tool_use.get("input") or {}

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
                    "schema": "anthropic_tool_v1",
                    "messages": messages,
                    "system_message": system_message,
                    "tool_uses": serialized_tool_uses,
                    "current_index": idx,
                    "tool_results": list(tool_results),
                }
                result_content = runtime.execute_or_interrupt(
                    tool_call_id=str(tool_id),
                    function_name=str(tool_name),
                    raw_args=tool_input,
                    available_tools=available_tools or [],
                    continuation_state=continuation_state,
                )
            else:
                tool_def = tool_map.get(tool_name)
                if tool_def is None:
                    result_content = f"Unknown function: {tool_name}"
                else:
                    try:
                        result_content = str(tool_def["function"](**tool_input))
                    except Exception as e:
                        result_content = f"Error: {str(e)}"

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result_content,
                }
            )

        return tool_results

    def _follow_up_response(
        self,
        *,
        messages: List[Dict[str, str]],
        serialized_tool_uses: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]],
        system_message: Optional[str],
    ) -> str:
        followup_messages = list(messages)
        followup_messages.append({"role": "assistant", "content": serialized_tool_uses})
        followup_messages.append({"role": "user", "content": tool_results})

        call_params = {
            "model": "claude-3-sonnet-20240229",
            "messages": followup_messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if system_message:
            call_params["system"] = system_message

        try:
            response = self.client.messages.create(**call_params)
            if response.content and len(response.content) > 0:
                for block in response.content:
                    block_type = getattr(block, "type", None) or (
                        block.get("type") if isinstance(block, dict) else None
                    )
                    if block_type == "text":
                        return getattr(block, "text", None) or (
                            block.get("text", "") if isinstance(block, dict) else ""
                        )
            return "No response generated after tool execution"
        except Exception:
            return "\n".join([str(r["content"]) for r in tool_results])

    def _handle_tool_calls(
        self,
        tool_uses: List[Any],
        available_tools: List[Dict[str, Any]],
        messages: List[Dict[str, str]],
        system_message: Optional[str],
        hitl_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        serialized_tool_uses = self._serialize_tool_uses(tool_uses)
        tool_results = self._execute_tool_uses(
            serialized_tool_uses=serialized_tool_uses,
            available_tools=available_tools or [],
            messages=messages,
            system_message=system_message,
            hitl_context=hitl_context,
        )
        return self._follow_up_response(
            messages=messages,
            serialized_tool_uses=serialized_tool_uses,
            tool_results=tool_results,
            system_message=system_message,
        )

    def resume_tool_flow(
        self,
        suspended_state: Dict[str, Any],
        tools: Optional[List[Dict[str, Any]]],
        hitl_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Resume an interrupted Anthropic tool-use flow from persisted state."""
        if suspended_state.get("schema") != "anthropic_tool_v1":
            raise ProviderError("Invalid suspended state for Anthropic provider")

        resume_intervention = (hitl_context or {}).get("resume_intervention")
        if not resume_intervention:
            raise ProviderError("Missing resume intervention for suspended run")

        messages = suspended_state.get("messages", [])
        system_message = suspended_state.get("system_message")
        serialized_tool_uses = suspended_state.get("tool_uses", [])
        current_index = int(suspended_state.get("current_index", 0))
        existing_tool_results = suspended_state.get("tool_results", [])

        tool_results = self._execute_tool_uses(
            serialized_tool_uses=serialized_tool_uses,
            available_tools=tools or [],
            messages=messages,
            system_message=system_message,
            hitl_context=hitl_context,
            start_index=current_index,
            existing_tool_results=existing_tool_results,
            resume_intervention=resume_intervention,
        )

        return self._follow_up_response(
            messages=messages,
            serialized_tool_uses=serialized_tool_uses,
            tool_results=tool_results,
            system_message=system_message,
        )
