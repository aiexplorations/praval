"""
Cohere provider implementation for Praval framework.

Provides integration with Cohere's chat models through their
Chat API with support for conversation history.
"""

import inspect
import json
import os
from typing import Any, Dict, List, Optional

import cohere

from ..core.exceptions import (
    HITLConfigurationError,
    InterventionRequired,
    ProviderError,
)
from ..hitl.runtime import HITLRuntime
from ..model_runtime import (
    call_with_retries,
    execute_legacy_tool_call,
    max_provider_retries,
)
from ..models import (
    ModelEvent,
    ModelRequest,
    ModelResponse,
    ProviderCapabilities,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from .errors import map_provider_exception, sdk_max_retries
from .registry import reasoning_parameters
from .usage import cohere_usage


def _accepts_keyword(factory: Any, name: str) -> bool:
    """Return whether ``factory`` takes ``name``; older cohere SDKs may not."""
    try:
        parameters = inspect.signature(factory).parameters
    except (TypeError, ValueError):
        return False
    return name in parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
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


class CohereProvider:
    """Cohere provider for LLM interactions."""

    provider_name = "cohere"
    capabilities = ProviderCapabilities(tools=True)

    def __init__(self, config):
        self.config = config
        self._reasoning_client: Any = None

        try:
            api_key_env = getattr(config, "api_key_env", None) or "COHERE_API_KEY"
            api_key = os.getenv(api_key_env)
            if not api_key:
                raise ProviderError(f"{api_key_env} environment variable not set")

            client_kwargs: Dict[str, Any] = {}
            if _accepts_keyword(cohere.Client, "max_retries"):
                client_kwargs["max_retries"] = sdk_max_retries(config)
            self.client = cohere.Client(api_key, **client_kwargs)
        except Exception as e:
            raise ProviderError(
                f"Failed to initialize Cohere client: {self._redact(str(e))}"
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
                "max_tokens": self._max_output_tokens(),
            }
            if self._model_name():
                call_params["model"] = self._model_name()

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
            raise self._mapped_error(
                e, f"Cohere API error: {self._redact(str(e))}"
            ) from e

    def _redact(self, message: str) -> str:
        """Redact known provider keys and the key from ``config.api_key_env``."""
        redacted = _redact_secrets(message)
        api_key_env = getattr(self.config, "api_key_env", None)
        secret = os.getenv(api_key_env) if api_key_env else None
        if secret and redacted:
            redacted = redacted.replace(secret, "***")
        return redacted

    def map_provider_error(self, exc: BaseException) -> ProviderError:
        """Map a Cohere SDK exception to a typed, redacted ``ProviderError``."""
        message: Optional[str] = None
        body = getattr(exc, "body", None)
        status_code = getattr(exc, "status_code", None)
        if isinstance(body, dict) and isinstance(body.get("message"), str):
            # ApiError's own str() dumps response headers; the body is clearer.
            message = f"HTTP {status_code}: {body['message']}"
        return self._mapped_error(exc, message)

    def _mapped_error(
        self, exc: BaseException, message: Optional[str]
    ) -> ProviderError:
        return map_provider_exception(
            exc,
            provider=self.provider_name,
            model=self._model_name(),
            message=message,
            redact=self._redact,
        )

    def invoke(
        self,
        request: ModelRequest,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ModelResponse:
        """Invoke Cohere through the provider-neutral adapter surface."""
        if self._uses_v2(request):
            return self._invoke_v2(request)
        call_params = self._request_chat_params(request, tools=tools)
        response = self.client.chat(**call_params)
        return self._chat_model_response(response, call_params)

    def _chat_model_response(
        self,
        response: Any,
        call_params: Dict[str, Any],
    ) -> ModelResponse:
        raw_tool_calls = getattr(response, "tool_calls", None) or []
        if not isinstance(raw_tool_calls, (list, tuple)):
            raw_tool_calls = []
        serialized = self._serialize_tool_calls(list(raw_tool_calls))
        # v1 tool calls carry no id; number them across the whole run so a
        # later round never reuses an earlier round's id.
        id_offset = self._history_tool_call_count(call_params.get("chat_history"))
        for index, call in enumerate(serialized):
            if not call.get("id"):
                call["id"] = f"cohere-call-{id_offset + index}"
        tool_calls = [
            ToolCall(
                id=str(call["id"]),
                name=str(call.get("name") or ""),
                arguments=(
                    call.get("args") if isinstance(call.get("args"), dict) else {}
                ),
                raw=call,
            )
            for call in serialized
        ]
        content = str(getattr(response, "text", "") or "")
        finish_reason = getattr(response, "finish_reason", None)
        if not isinstance(finish_reason, str):
            finish_reason = None
        metadata: Dict[str, Any] = {"cohere_tool_calls": serialized}
        if serialized:
            metadata["cohere_chat_history"] = self._cohere_chat_history(
                call_params, content, serialized
            )
        return ModelResponse(
            content=content,
            provider=self.provider_name,
            model=self._model_name(),
            tool_calls=tool_calls,
            raw=response,
            usage=cohere_usage(response),
            finish_reason=finish_reason,
            metadata=metadata,
        )

    def continue_with_tool_results(
        self,
        request: ModelRequest,
        response: ModelResponse,
        tool_results: List[ToolResult],
    ) -> ModelResponse:
        """Submit runtime-executed tool results to Cohere.

        Follows the v1 multi-step pattern: the run so far goes in
        ``chat_history``, only the latest round's results go in
        ``tool_results``, and ``message`` is empty.
        """
        if response.metadata.get("cohere_endpoint") == "chat.v2":
            transcript = response.metadata.get("cohere_v2_messages")
            if not isinstance(transcript, list):
                raise ProviderError("Cohere v2 tool continuation state is missing")
            messages = list(transcript)
            messages.extend(
                {
                    "role": "tool",
                    "tool_call_id": result.tool_call_id,
                    "content": result.content,
                }
                for result in tool_results
            )
            return self._invoke_v2(request, messages=messages)
        serialized = response.metadata.get("cohere_tool_calls")
        if not isinstance(serialized, list):
            raise ProviderError("Cohere tool continuation state is missing")
        call_params = self._request_chat_params(request)
        history = response.metadata.get("cohere_chat_history")
        if not isinstance(history, list):
            # State written by v0.8.3 has no transcript; rebuild one round.
            history = self._cohere_chat_history(
                call_params, response.content, serialized
            )
        call_params["chat_history"] = list(history)
        call_params["message"] = ""
        calls_by_id = {
            str(call.get("id")): call for call in serialized if isinstance(call, dict)
        }
        call_params["tool_results"] = [
            self._cohere_tool_result(result, calls_by_id.get(result.tool_call_id))
            for result in tool_results
        ]
        continued = self.client.chat(**call_params)
        return self._chat_model_response(continued, call_params)

    def _cohere_chat_history(
        self,
        call_params: Dict[str, Any],
        content: str,
        serialized_calls: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Return the v1 chat history up to and including this tool-call turn."""
        history = list(call_params.get("chat_history") or [])
        message = call_params.get("message")
        if message:
            history.append({"role": "USER", "message": message})
        if call_params.get("tool_results"):
            history.append(
                {"role": "TOOL", "tool_results": list(call_params["tool_results"])}
            )
        history.append(
            {
                "role": "CHATBOT",
                "message": content,
                "tool_calls": [self._cohere_call(call) for call in serialized_calls],
            }
        )
        return history

    def _cohere_call(self, call: Dict[str, Any]) -> Dict[str, Any]:
        args = call.get("args")
        return {
            "name": str(call.get("name") or ""),
            "parameters": args if isinstance(args, dict) else {},
        }

    def _cohere_tool_result(
        self,
        result: ToolResult,
        call: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        output: Dict[str, Any] = {"result": result.content}
        if result.is_error:
            output["is_error"] = True
        return {
            "call": (
                self._cohere_call(call)
                if call is not None
                else {"name": result.name, "parameters": {}}
            ),
            "outputs": [output],
        }

    def _history_tool_call_count(self, history: Any) -> int:
        if not isinstance(history, list):
            return 0
        return sum(
            len(entry.get("tool_calls") or [])
            for entry in history
            if isinstance(entry, dict) and entry.get("role") == "CHATBOT"
        )

    def _request_chat_params(
        self,
        request: ModelRequest,
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        messages = [
            message.model_dump(exclude_none=True) for message in request.messages
        ]
        current_message, chat_history = self._prepare_chat_format(messages)
        call_params: Dict[str, Any] = {
            "message": current_message,
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens or self._max_output_tokens(),
            "model": request.model or self._model_name(),
        }
        if chat_history:
            call_params["chat_history"] = chat_history
        system_message = self._extract_system_message(messages)
        if system_message:
            call_params["preamble"] = system_message
        if tools:
            formatted = self._format_tools_for_cohere(tools)
            if formatted:
                call_params["tools"] = formatted
        elif request.tools:
            call_params["tools"] = self._format_tool_specs_for_cohere(request.tools)
        if request.timeout is not None:
            call_params["timeout"] = request.timeout
        for key, value in request.provider_options.items():
            if key not in {"capabilities", "max_retries", "endpoint", "api"}:
                call_params.setdefault(key, value)
        return call_params

    def stream(self, request: ModelRequest):
        """Streaming adapter placeholder with non-streaming fallback."""
        response = self.invoke(request)
        if response.content:
            yield ModelEvent(type="delta", delta=response.content)
        yield ModelEvent(type="final", response=response, usage=response.usage)

    def close(self) -> None:
        """Close the underlying SDK client when supported."""
        for client in (self.client, self._reasoning_client):
            close = getattr(client, "close", None)
            if callable(close):
                close()

    def _uses_v2(self, request: ModelRequest) -> bool:
        """Reasoning is opt-in on the v2 endpoint; legacy v1 stays unchanged."""
        return request.provider_options.get("endpoint") == "chat.v2" or (
            request.reasoning is not None
            and (request.model or self._model_name()).startswith("command-a-reasoning-")
        )

    def _v2_client(self) -> Any:
        if self._reasoning_client is None:
            api_key_env = getattr(self.config, "api_key_env", None) or "COHERE_API_KEY"
            kwargs: Dict[str, Any] = {"api_key": os.getenv(api_key_env)}
            if _accepts_keyword(cohere.ClientV2, "max_retries"):
                kwargs["max_retries"] = sdk_max_retries(self.config)
            self._reasoning_client = cohere.ClientV2(**kwargs)
        return self._reasoning_client

    def _v2_params(
        self, request: ModelRequest, messages: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "model": request.model or self._model_name(),
            "messages": (
                messages
                if messages is not None
                else [
                    {"role": message.role, "content": message.content}
                    for message in request.messages
                ]
            ),
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens or self._max_output_tokens(),
        }
        if request.tools:
            params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in request.tools
            ]
        thinking = dict(reasoning_parameters(request).get("thinking") or {})
        if request.reasoning is not None:
            if request.reasoning.mode is not None:
                thinking["type"] = request.reasoning.mode
            if request.reasoning.budget_tokens is not None:
                thinking.setdefault("type", "enabled")
                thinking["token_budget"] = request.reasoning.budget_tokens
        if thinking:
            params["thinking"] = thinking
        if request.timeout is not None:
            params["request_options"] = {"timeout_in_seconds": request.timeout}
        for key, value in request.provider_options.items():
            if key not in {"capabilities", "max_retries", "endpoint", "api"}:
                params.setdefault(key, value)
        return params

    def _invoke_v2(
        self, request: ModelRequest, messages: Optional[List[Dict[str, Any]]] = None
    ) -> ModelResponse:
        params = self._v2_params(request, messages)
        response = self._v2_client().chat(**params)
        message = response.message
        native = message.model_dump(mode="json", exclude_none=True)
        # Native content contains both text and thinking blocks; retain both
        # in continuation state but return only the answer as public content.
        content = "".join(
            str(block.get("text") or "")
            for block in native.get("content") or []
            if block.get("type") == "text"
        )
        calls = [
            ToolCall(
                id=str(call["id"]),
                name=str(call["function"]["name"]),
                arguments=json.loads(call["function"].get("arguments") or "{}"),
                raw=call,
            )
            for call in native.get("tool_calls") or []
        ]
        transcript = list(params["messages"])
        transcript.append(native)
        return ModelResponse(
            content=content,
            provider=self.provider_name,
            model=params["model"],
            usage=cohere_usage(response),
            raw=response,
            tool_calls=calls,
            finish_reason=getattr(response, "finish_reason", None),
            metadata={"cohere_endpoint": "chat.v2", "cohere_v2_messages": transcript},
        )

    def _model_name(self) -> str:
        return str(getattr(self.config, "model", None) or "command-a-03-2025")

    def _max_output_tokens(self) -> int:
        return int(
            getattr(self.config, "max_output_tokens", None)
            or getattr(self.config, "max_tokens", 1000)
        )

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
        parts = [
            message.get("content", "")
            for message in messages
            if message.get("role") == "system"
        ]
        return "\n\n".join(parts) if parts else None

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

    def _format_tool_specs_for_cohere(
        self, tool_specs: List[ToolSpec]
    ) -> List[Dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
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

    def _serialize_tool_calls(self, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        serialized: List[Dict[str, Any]] = []
        for tool_call in tool_calls:
            # Cohere v1 ToolCall carries ``parameters``; ``args`` stays as a
            # fallback for older recorded payloads.
            if isinstance(tool_call, dict):
                call_id = tool_call.get("id")
                name = tool_call.get("name")
                args = tool_call.get("parameters") or tool_call.get("args") or {}
            else:
                call_id = getattr(tool_call, "id", None)
                name = getattr(tool_call, "name", None)
                args = (
                    getattr(tool_call, "parameters", None)
                    or getattr(tool_call, "args", None)
                    or {}
                )
            serialized.append({"id": call_id, "name": name, "args": args})
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
        tool_results = list(existing_tool_results or [])

        for idx in range(start_index, len(serialized_tool_calls)):
            tool_call = serialized_tool_calls[idx]
            name = tool_call.get("name")
            args = tool_call.get("args") or {}

            continuation_state = None
            if not (idx == start_index and resume_intervention is not None):
                continuation_state = {
                    "schema": "cohere_tool_v1",
                    "original_messages": original_messages,
                    "tool_calls": serialized_tool_calls,
                    "current_index": idx,
                    "tool_results": list(tool_results),
                }
            result_content = execute_legacy_tool_call(
                hitl_context=hitl_context,
                tool_call_id=f"{name}:{idx}",
                function_name=str(name),
                raw_args=args,
                available_tools=available_tools or [],
                continuation_state=continuation_state,
                resume_intervention=(
                    resume_intervention
                    if idx == start_index and resume_intervention is not None
                    else None
                ),
            )

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
                "max_tokens": self._max_output_tokens(),
            }
            if self._model_name():
                call_params["model"] = self._model_name()
            if chat_history:
                call_params["chat_history"] = chat_history

            system_message = self._extract_system_message(original_messages)
            if system_message:
                call_params["preamble"] = system_message

            call_params["tool_results"] = tool_results
            # The tools have already run: retry only this request.
            response = call_with_retries(
                "follow_up",
                lambda: self.client.chat(**call_params),
                retries=max_provider_retries(self.config),
                map_error=self.map_provider_error,
            )
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
