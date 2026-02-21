"""
Cohere provider implementation for Praval framework.

Provides integration with Cohere's chat models through their
Chat API with support for conversation history.
"""

import os
from typing import Any, Dict, List, Optional

import cohere

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


class CohereProvider:
    """Cohere provider for LLM interactions."""

    def __init__(self, config):
        self.config = config

        try:
            api_key = os.getenv("COHERE_API_KEY")
            if not api_key:
                raise ProviderError("COHERE_API_KEY environment variable not set")

            self.client = cohere.Client(api_key)
        except Exception as e:
            raise ProviderError(
                f"Failed to initialize Cohere client: {_redact_secrets(str(e))}"
            ) from e

    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        hitl_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a response using Cohere's Chat API."""
        try:
            current_message, chat_history = self._prepare_chat_format(messages)

            call_params = {
                "message": current_message,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }

            if chat_history:
                call_params["chat_history"] = chat_history

            system_message = self._extract_system_message(messages)
            if system_message:
                call_params["preamble"] = system_message

            if tools:
                formatted_tools = self._format_tools_for_cohere(tools)
                if formatted_tools:
                    call_params["tools"] = formatted_tools

            response = self.client.chat(**call_params)

            tool_calls = getattr(response, "tool_calls", None)
            if tools and tool_calls:
                if isinstance(tool_calls, (list, tuple)) and tool_calls:
                    return self._handle_tool_calls(
                        list(tool_calls),
                        tools,
                        messages,
                        hitl_context=hitl_context,
                    )

            return response.text if hasattr(response, "text") else ""

        except (InterventionRequired, HITLConfigurationError):
            raise
        except Exception as e:
            raise ProviderError(f"Cohere API error: {_redact_secrets(str(e))}") from e

    def _prepare_chat_format(
        self, messages: List[Dict[str, str]]
    ) -> tuple[str, List[Dict[str, str]]]:
        conversation_messages = [
            msg for msg in messages if msg.get("role") in ["user", "assistant"]
        ]

        if not conversation_messages:
            return "", []

        current_message = ""
        chat_history: List[Dict[str, str]] = []

        last_message = conversation_messages[-1]
        if last_message.get("role") == "user":
            current_message = last_message.get("content", "")
            for msg in conversation_messages[:-1]:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    chat_history.append({"role": "USER", "message": content})
                elif role == "assistant":
                    chat_history.append({"role": "CHATBOT", "message": content})
        else:
            current_message = "Please continue."
            for msg in conversation_messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    chat_history.append({"role": "USER", "message": content})
                elif role == "assistant":
                    chat_history.append({"role": "CHATBOT", "message": content})

        return current_message, chat_history

    def _extract_system_message(self, messages: List[Dict[str, str]]) -> Optional[str]:
        for message in messages:
            if message.get("role") == "system":
                return message.get("content", "")
        return None

    def _format_tools_for_cohere(
        self, tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
                    "required": [],
                },
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
                name = tool_call.get("name")
                args = tool_call.get("args") or {}
            else:
                name = getattr(tool_call, "name", None)
                args = getattr(tool_call, "args", None) or {}
            serialized.append({"name": name, "args": args})
        return serialized

    def _execute_tool_calls(
        self,
        *,
        serialized_tool_calls: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
        original_messages: List[Dict[str, str]],
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

        for idx in range(start_index, len(serialized_tool_calls)):
            tool_call = serialized_tool_calls[idx]
            name = tool_call.get("name")
            args = tool_call.get("args") or {}

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
                    "schema": "cohere_tool_v1",
                    "original_messages": original_messages,
                    "tool_calls": serialized_tool_calls,
                    "current_index": idx,
                    "tool_results": list(tool_results),
                }
                result_content = runtime.execute_or_interrupt(
                    tool_call_id=f"{name}:{idx}",
                    function_name=str(name),
                    raw_args=args,
                    available_tools=available_tools or [],
                    continuation_state=continuation_state,
                )
            else:
                tool_def = tool_map.get(name)
                if tool_def is None:
                    result_content = f"Unknown function: {name}"
                else:
                    try:
                        result_content = str(tool_def["function"](**args))
                    except Exception as e:
                        result_content = f"Error: {str(e)}"

            tool_results.append({"name": name, "result": result_content})

        return tool_results

    def _follow_up_response(
        self,
        *,
        original_messages: List[Dict[str, str]],
        tool_results: List[Dict[str, Any]],
    ) -> str:
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
            return response.text if hasattr(response, "text") else ""
        except Exception:
            return "\n".join([str(r["result"]) for r in tool_results])

    def _handle_tool_calls(
        self,
        tool_calls: List[Any],
        available_tools: List[Dict[str, Any]],
        original_messages: List[Dict[str, str]],
        hitl_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        serialized_tool_calls = self._serialize_tool_calls(tool_calls)
        tool_results = self._execute_tool_calls(
            serialized_tool_calls=serialized_tool_calls,
            available_tools=available_tools or [],
            original_messages=original_messages,
            hitl_context=hitl_context,
        )
        return self._follow_up_response(
            original_messages=original_messages,
            tool_results=tool_results,
        )

    def resume_tool_flow(
        self,
        suspended_state: Dict[str, Any],
        tools: Optional[List[Dict[str, Any]]],
        hitl_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Resume an interrupted Cohere tool-call flow from persisted state."""
        if suspended_state.get("schema") != "cohere_tool_v1":
            raise ProviderError("Invalid suspended state for Cohere provider")

        resume_intervention = (hitl_context or {}).get("resume_intervention")
        if not resume_intervention:
            raise ProviderError("Missing resume intervention for suspended run")

        original_messages = suspended_state.get("original_messages", [])
        serialized_tool_calls = suspended_state.get("tool_calls", [])
        current_index = int(suspended_state.get("current_index", 0))
        existing_tool_results = suspended_state.get("tool_results", [])

        tool_results = self._execute_tool_calls(
            serialized_tool_calls=serialized_tool_calls,
            available_tools=tools or [],
            original_messages=original_messages,
            hitl_context=hitl_context,
            start_index=current_index,
            existing_tool_results=existing_tool_results,
            resume_intervention=resume_intervention,
        )
        return self._follow_up_response(
            original_messages=original_messages,
            tool_results=tool_results,
        )
