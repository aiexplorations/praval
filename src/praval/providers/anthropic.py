"""
Anthropic provider implementation for Praval framework.

Provides integration with Anthropic's Claude models through the
Messages API with support for conversation history and system messages.
"""

import os
from typing import Any, Dict, Iterator, List, Optional

import anthropic

from ..core.exceptions import (
    HITLConfigurationError,
    InterventionRequired,
    ProviderError,
)
from ..hitl.runtime import HITLRuntime
from ..model_runtime import execute_legacy_tool_call
from ..models import (
    ContentPart,
    ModelEvent,
    ModelRequest,
    ModelResponse,
    ProviderCapabilities,
    ToolCall,
    ToolResult,
    ToolSpec,
    Usage,
)


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

    provider_name = "anthropic"
    capabilities = ProviderCapabilities(
        tools=True,
        streaming=True,
        native_streaming=True,
        tool_streaming=True,
        structured_outputs=True,
        json_schema_mode="json_schema",
        multimodal=True,
        image_input=True,
        reasoning=True,
        reasoning_effort=True,
        reasoning_budget=True,
    )

    def __init__(self, config):
        self.config = config

        try:
            api_key_env = getattr(config, "api_key_env", None) or "ANTHROPIC_API_KEY"
            api_key = os.getenv(api_key_env)
            if not api_key:
                raise ProviderError(f"{api_key_env} environment variable not set")

            client_kwargs: Dict[str, Any] = {"api_key": api_key}
            if getattr(config, "base_url", None):
                client_kwargs["base_url"] = config.base_url
            if getattr(config, "timeout", None):
                client_kwargs["timeout"] = config.timeout
            self.client = anthropic.Anthropic(**client_kwargs)
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
                "model": self._model_name(),
                "messages": conversation_messages,
                "temperature": self.config.temperature,
                "max_tokens": self._max_output_tokens(),
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

    def invoke(
        self,
        request: ModelRequest,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ModelResponse:
        """Invoke Anthropic through the provider-neutral adapter surface."""
        return self._invoke_messages(request, tools=tools)

    def _invoke_messages(
        self,
        request: ModelRequest,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ModelResponse:
        call_params = self._messages_params(request, tools=tools)
        response = self.client.messages.create(**call_params)
        return self._messages_model_response(response, call_params)

    def _messages_model_response(
        self,
        response: Any,
        call_params: Dict[str, Any],
    ) -> ModelResponse:
        content_blocks = getattr(response, "content", None)
        if not isinstance(content_blocks, (list, tuple)):
            content_blocks = []
        serialized_content = self._serialize_content_blocks(list(content_blocks))
        tool_uses = [
            block for block in serialized_content if block.get("type") == "tool_use"
        ]
        tool_calls = [
            ToolCall(
                id=str(block.get("id") or ""),
                name=str(block.get("name") or ""),
                arguments=(
                    block.get("input") if isinstance(block.get("input"), dict) else {}
                ),
                raw=block,
            )
            for block in tool_uses
        ]
        finish_reason = self._event_value(response, "stop_reason", None)
        return ModelResponse(
            content=self._extract_text(response),
            provider=self.provider_name,
            model=call_params["model"],
            tool_calls=tool_calls,
            raw=response,
            usage=self._extract_usage(response),
            finish_reason=finish_reason if isinstance(finish_reason, str) else None,
            metadata={
                "anthropic_assistant_content": serialized_content,
            },
        )

    def continue_with_tool_results(
        self,
        request: ModelRequest,
        response: ModelResponse,
        tool_results: List[ToolResult],
    ) -> ModelResponse:
        """Submit runtime-executed tool results to Anthropic."""
        assistant_content = response.metadata.get("anthropic_assistant_content")
        if not isinstance(assistant_content, list):
            raise ProviderError("Anthropic tool continuation state is missing")
        call_params = self._messages_params(request)
        messages = list(call_params["messages"])
        messages.append({"role": "assistant", "content": assistant_content})
        messages.append(
            {
                "role": "user",
                "content": [
                    self._anthropic_tool_result(result) for result in tool_results
                ],
            }
        )
        call_params["messages"] = messages
        continued = self.client.messages.create(**call_params)
        return self._messages_model_response(continued, call_params)

    def stream(
        self,
        request: ModelRequest,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[ModelEvent]:
        """Stream Anthropic messages as provider-neutral events."""
        call_params = self._messages_params(request, tools=tools)
        try:
            stream_factory = getattr(self.client.messages, "stream", None)
            if callable(stream_factory):
                yield from self._stream_messages_context(stream_factory, call_params)
                return
            call_params["stream"] = True
            yield from self._stream_messages_create(call_params)
        except Exception as e:
            message = _redact_secrets(str(e))
            yield ModelEvent(type="error", metadata={"message": message})
            raise ProviderError(f"Anthropic streaming error: {message}") from e

    def close(self) -> None:
        """Close the underlying SDK client when supported."""
        close = getattr(self.client, "close", None)
        if callable(close):
            close()

    def _model_name(self) -> str:
        return str(getattr(self.config, "model", None) or "claude-sonnet-5")

    def _max_output_tokens(self) -> int:
        return int(
            getattr(self.config, "max_output_tokens", None)
            or getattr(self.config, "max_tokens", 1000)
        )

    def _messages_params(
        self,
        request: ModelRequest,
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        messages = [
            message.model_dump(exclude_none=True) for message in request.messages
        ]
        system_message = self._extract_system_message(messages)
        conversation_messages = self._filter_conversation_messages(messages)
        call_params: Dict[str, Any] = {
            "model": request.model or self._model_name(),
            "messages": conversation_messages,
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens or self._max_output_tokens(),
        }
        if system_message:
            call_params["system"] = system_message
        if tools:
            formatted_tools = self._format_tools_for_anthropic(tools)
            if formatted_tools:
                call_params["tools"] = formatted_tools
        elif request.tools:
            call_params["tools"] = self._format_tool_specs_for_anthropic(request.tools)
        experimental_tools = self._experimental_tools(request)
        if experimental_tools:
            call_params.setdefault("tools", [])
            call_params["tools"].extend(experimental_tools)
        thinking = self._anthropic_thinking(request)
        if thinking:
            call_params["thinking"] = thinking
        output_config = self._anthropic_output_config(request)
        if output_config:
            call_params["output_config"] = output_config
        if request.timeout is not None:
            call_params["timeout"] = request.timeout
        reserved = {
            "capabilities",
            "allow_experimental_tools",
            "experimental_tools",
        }
        for key, value in request.provider_options.items():
            if key not in reserved:
                call_params.setdefault(key, value)
        return call_params

    def _experimental_tools(self, request: ModelRequest) -> List[Dict[str, Any]]:
        value = request.provider_options.get("experimental_tools")
        if value is None:
            return []
        if request.provider_options.get("allow_experimental_tools") is not True:
            raise ProviderError(
                "experimental_tools requires allow_experimental_tools=True"
            )
        if not isinstance(value, list) or not all(
            isinstance(tool, dict) for tool in value
        ):
            raise ProviderError("experimental_tools must be a list of tool mappings")
        return [dict(tool) for tool in value]

    def _serialize_content_blocks(
        self, content_blocks: List[Any]
    ) -> List[Dict[str, Any]]:
        serialized: List[Dict[str, Any]] = []
        for block in content_blocks:
            if isinstance(block, dict):
                serialized.append(dict(block))
                continue
            if hasattr(block, "model_dump"):
                dumped = block.model_dump(exclude_none=True)
                if isinstance(dumped, dict):
                    serialized.append(dict(dumped))
                    continue
            block_type = getattr(block, "type", None)
            if block_type == "tool_use":
                serialized.append(
                    {
                        "type": "tool_use",
                        "id": getattr(block, "id", None),
                        "name": getattr(block, "name", None),
                        "input": getattr(block, "input", None) or {},
                    }
                )
            elif block_type == "text":
                serialized.append({"type": "text", "text": getattr(block, "text", "")})
        return serialized

    def _anthropic_tool_result(self, result: ToolResult) -> Dict[str, Any]:
        block: Dict[str, Any] = {
            "type": "tool_result",
            "tool_use_id": result.tool_call_id,
            "content": result.content,
        }
        if result.is_error:
            block["is_error"] = True
        return block

    def _stream_messages_context(
        self,
        stream_factory: Any,
        call_params: Dict[str, Any],
    ) -> Iterator[ModelEvent]:
        content_parts: List[str] = []
        final_message: Any = None
        with stream_factory(**call_params) as stream:
            for text in getattr(stream, "text_stream", []):
                if text:
                    content_parts.append(str(text))
                    yield ModelEvent(type="delta", delta=str(text))
            get_final = getattr(stream, "get_final_message", None)
            if callable(get_final):
                final_message = get_final()
        usage = (
            self._extract_usage(final_message) if final_message is not None else None
        )
        response = ModelResponse(
            content=self._extract_text(final_message) or "".join(content_parts),
            provider=self.provider_name,
            model=call_params["model"],
            raw=final_message,
            usage=usage,
        )
        if usage:
            yield ModelEvent(type="usage", usage=usage)
        yield ModelEvent(type="final", response=response, usage=usage)

    def _stream_messages_create(
        self,
        call_params: Dict[str, Any],
    ) -> Iterator[ModelEvent]:
        content_parts: List[str] = []
        usage: Optional[Usage] = None
        stream = self.client.messages.create(**call_params)
        for event in stream:
            event_type = str(self._event_value(event, "type", ""))
            if event_type in {"content_block_delta", "text_delta"}:
                delta = self._event_value(event, "delta", event)
                text = self._event_value(delta, "text", "")
                if text:
                    content_parts.append(str(text))
                    yield ModelEvent(type="delta", delta=str(text))
            elif event_type == "message_delta":
                usage = self._extract_usage(event) or usage
            elif event_type == "error":
                yield ModelEvent(
                    type="error",
                    metadata={"message": _redact_secrets(str(event))},
                )
        response = ModelResponse(
            content="".join(content_parts),
            provider=self.provider_name,
            model=call_params["model"],
            usage=usage,
        )
        if usage:
            yield ModelEvent(type="usage", usage=usage)
        yield ModelEvent(type="final", response=response, usage=usage)

    def _extract_text(self, response: Any) -> str:
        content = getattr(response, "content", None)
        if content is None and isinstance(response, dict):
            content = response.get("content")
        text_parts: List[str] = []
        for block in content or []:
            block_type = getattr(block, "type", None) or (
                block.get("type") if isinstance(block, dict) else None
            )
            if block_type == "text":
                value = getattr(block, "text", None) or (
                    block.get("text", "") if isinstance(block, dict) else ""
                )
                text_parts.append(str(value))
        return "".join(text_parts)

    def _anthropic_thinking(self, request: ModelRequest) -> Dict[str, Any]:
        if request.reasoning is None:
            return {}
        reasoning = request.reasoning
        if reasoning.budget_tokens is None and not reasoning.mode:
            return {}
        thinking: Dict[str, Any] = {"type": reasoning.mode or "enabled"}
        if reasoning.budget_tokens is not None:
            thinking["budget_tokens"] = reasoning.budget_tokens
        if reasoning.display:
            thinking["display"] = reasoning.display
        return thinking

    def _anthropic_output_config(self, request: ModelRequest) -> Dict[str, Any]:
        output_config: Dict[str, Any] = {}
        if request.response_schema is not None:
            output_config["format"] = {
                "type": "json_schema",
                "schema": request.response_schema.json_schema or {},
            }
        if request.reasoning is not None and request.reasoning.effort:
            output_config["effort"] = request.reasoning.effort
        return output_config

    def _extract_usage(self, response: Any) -> Optional[Usage]:
        usage = getattr(response, "usage", None)
        if usage is None and isinstance(response, dict):
            usage = response.get("usage")
        if usage is None:
            return None

        def getter(key: str, default: int = 0) -> Any:
            if isinstance(usage, dict):
                return usage.get(key, default)
            return getattr(usage, key, default)

        input_tokens = int(getter("input_tokens", 0) or 0)
        output_tokens = int(getter("output_tokens", 0) or 0)
        return Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        )

    def _extract_system_message(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        for message in messages:
            if message.get("role") == "system":
                return self._content_to_text(message.get("content", ""))
        return None

    def _filter_conversation_messages(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        conversation_messages = []
        for message in messages:
            role = message.get("role", "")
            if role in ["user", "assistant"]:
                conversation_messages.append(
                    {
                        "role": role,
                        "content": self._format_anthropic_content(
                            message.get("content", "")
                        ),
                    }
                )
        return conversation_messages

    def _format_anthropic_content(self, content: Any) -> Any:
        if not isinstance(content, list):
            return content
        blocks: List[Dict[str, Any]] = []
        for item in content:
            part = item if isinstance(item, ContentPart) else ContentPart(**item)
            if part.type == "text":
                blocks.append({"type": "text", "text": part.text or ""})
            elif part.type in {"image_url", "image"}:
                blocks.append(
                    {
                        "type": "image",
                        "source": {"type": "url", "url": part.url or ""},
                    }
                )
            elif part.type == "image_base64":
                blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": part.mime_type or "image/png",
                            "data": part.data or "",
                        },
                    }
                )
            else:
                raise ProviderError(
                    "Anthropic provider cannot serialize content part type: "
                    f"{part.type}"
                )
        return blocks

    def _content_to_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                part = item if isinstance(item, ContentPart) else ContentPart(**item)
                if part.type == "text":
                    text_parts.append(part.text or "")
            return "".join(text_parts)
        return str(content)

    def _event_value(self, value: Any, key: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(key, default)
        return getattr(value, key, default)

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

    def _format_tool_specs_for_anthropic(
        self, tool_specs: List[ToolSpec]
    ) -> List[Dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.parameters,
            }
            for spec in tool_specs
        ]

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
        tool_results = list(existing_tool_results or [])

        for idx in range(start_index, len(serialized_tool_uses)):
            tool_use = serialized_tool_uses[idx]
            tool_name = tool_use.get("name")
            tool_id = tool_use.get("id")
            tool_input = tool_use.get("input") or {}

            continuation_state = None
            if not (idx == start_index and resume_intervention is not None):
                continuation_state = {
                    "schema": "anthropic_tool_v1",
                    "messages": messages,
                    "system_message": system_message,
                    "tool_uses": serialized_tool_uses,
                    "current_index": idx,
                    "tool_results": list(tool_results),
                }
            result_content = execute_legacy_tool_call(
                hitl_context=hitl_context,
                tool_call_id=str(tool_id),
                function_name=str(tool_name),
                raw_args=tool_input,
                available_tools=available_tools or [],
                continuation_state=continuation_state,
                resume_intervention=(
                    resume_intervention
                    if idx == start_index and resume_intervention is not None
                    else None
                ),
            )

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
            "model": self._model_name(),
            "messages": followup_messages,
            "temperature": self.config.temperature,
            "max_tokens": self._max_output_tokens(),
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
