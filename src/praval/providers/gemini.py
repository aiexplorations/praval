"""Gemini provider implementation."""

from __future__ import annotations

import copy
import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator, List, Optional, Set

from ..core.exceptions import ProviderError
from ..model_runtime import (
    call_with_retries,
    execute_legacy_tool_call,
    max_provider_retries,
)
from ..models import (
    ContentPart,
    ModelEvent,
    ModelRequest,
    ModelResponse,
    ProviderCapabilities,
    ToolCall,
    ToolResult,
)
from .errors import map_gemini_http_error, map_provider_exception


def _redact_secret(message: str, secret: Optional[str]) -> str:
    if message and secret:
        return message.replace(secret, "***")
    return message


class GeminiProvider:
    """Google Gemini provider using the public REST API."""

    provider_name = "gemini"
    capabilities = ProviderCapabilities(
        tools=True,
        streaming=True,
        native_streaming=True,
        structured_outputs=True,
        json_schema_mode="json_schema",
        multimodal=True,
        image_input=True,
        file_input=True,
        audio_input=True,
        video_input=True,
        reasoning=True,
        embeddings=True,
    )

    def __init__(self, config: Any):
        self.config = config
        api_key_env = getattr(config, "api_key_env", None) or "GEMINI_API_KEY"
        self.api_key = os.getenv(api_key_env) or os.getenv("GOOGLE_API_KEY")
        if not self.api_key and not getattr(config, "base_url", None):
            raise ProviderError(
                f"{api_key_env} or GOOGLE_API_KEY environment variable not set"
            )
        self.base_url = (
            getattr(config, "base_url", None)
            or "https://generativelanguage.googleapis.com/v1beta"
        )

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        hitl_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a response from Gemini."""
        payload = self._build_payload(messages, tools)
        try:
            data = self._post_json("generateContent", payload)
        except Exception as e:
            raise self._provider_error(e, "Gemini API error") from e

        function_calls = self._extract_function_calls(data)
        if function_calls:
            return self._handle_function_calls(
                function_calls=function_calls,
                available_tools=tools or [],
                messages=messages,
                request=None,
                hitl_context=hitl_context,
            ).content

        return self._extract_text(data)

    def invoke(
        self,
        request: ModelRequest,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ModelResponse:
        """Invoke Gemini through the provider-neutral adapter surface."""
        payload = self._build_payload(
            [message.model_dump(exclude_none=True) for message in request.messages],
            tools,
            request=request,
        )
        try:
            data = self._post_json("generateContent", payload, timeout=request.timeout)
        except Exception as e:
            raise self._provider_error(e, "Gemini API error") from e

        function_calls = self._extract_function_calls(data)
        if function_calls:
            return self._runtime_tool_call_response(data, payload, function_calls)

        return ModelResponse(
            content=self._extract_text(data),
            provider=self.provider_name,
            model=self._model_name(),
            raw=data,
        )

    def continue_with_tool_results(
        self,
        request: ModelRequest,
        response: ModelResponse,
        tool_results: List[ToolResult],
    ) -> ModelResponse:
        """Submit runtime-executed function results to Gemini."""
        template = response.metadata.get("gemini_payload")
        contents = response.metadata.get("gemini_contents")
        if not isinstance(template, dict) or not isinstance(contents, list):
            raise ProviderError("Gemini tool continuation state is missing")

        payload = dict(template)
        payload["contents"] = list(contents)
        native_ids = self._native_function_call_ids(contents)
        payload["contents"].append(
            {
                "role": "user",
                "parts": [
                    self._function_response_part(
                        result,
                        call_id=(
                            result.tool_call_id
                            if result.tool_call_id in native_ids
                            else None
                        ),
                    )
                    for result in tool_results
                ],
            }
        )
        try:
            data = self._post_json(
                "generateContent",
                payload,
                timeout=request.timeout,
            )
        except Exception as e:
            raise self._provider_error(e, "Gemini API error") from e

        function_calls = self._extract_function_calls(
            data, id_offset=self._content_function_call_count(payload["contents"])
        )
        if function_calls:
            return self._runtime_tool_call_response(data, payload, function_calls)
        return ModelResponse(
            content=self._extract_text(data),
            provider=self.provider_name,
            model=self._model_name(),
            raw=data,
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelEvent]:
        """Stream Gemini responses as provider-neutral events."""
        payload = self._build_payload(
            [message.model_dump(exclude_none=True) for message in request.messages],
            None,
            request=request,
        )
        content_parts: List[str] = []
        try:
            for data in self._post_stream(
                "streamGenerateContent",
                payload,
                timeout=request.timeout,
            ):
                text = self._extract_text(data)
                if text:
                    content_parts.append(text)
                    yield ModelEvent(type="delta", delta=text)
        except Exception as e:
            error = self._provider_error(e, "Gemini streaming error")
            yield ModelEvent(type="error", metadata={"message": error.message})
            raise error from e
        response = ModelResponse(
            content="".join(content_parts),
            provider=self.provider_name,
            model=self._model_name(),
        )
        yield ModelEvent(type="final", response=response)

    def close(self) -> None:
        """Gemini REST provider does not hold persistent resources."""

    def _provider_error(self, exc: BaseException, prefix: str) -> ProviderError:
        """Map a REST failure, reading and redacting an HTTP error body."""
        if isinstance(exc, urllib.error.HTTPError):
            return map_gemini_http_error(
                exc,
                prefix=prefix,
                model=self._model_name(),
                redact=lambda text: _redact_secret(text, self.api_key),
            )
        return map_provider_exception(
            exc,
            provider=self.provider_name,
            model=self._model_name(),
            message=f"{prefix}: {_redact_secret(str(exc), self.api_key)}",
        )

    def _model_name(self) -> str:
        return str(getattr(self.config, "model", None) or "gemini-3.5-flash")

    def _max_output_tokens(self) -> int:
        return int(
            getattr(self.config, "max_output_tokens", None)
            or getattr(self.config, "max_tokens", 1000)
        )

    def _build_payload(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        request: Optional[ModelRequest] = None,
    ) -> Dict[str, Any]:
        contents = []
        system_text = None
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system":
                system_text = self._content_to_text(content)
                continue
            gemini_role = "model" if role == "assistant" else "user"
            contents.append(
                {"role": gemini_role, "parts": self._content_to_parts(content)}
            )

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": (
                    request.temperature
                    if request is not None and request.temperature is not None
                    else getattr(self.config, "temperature", 0.7)
                ),
                "maxOutputTokens": self._max_output_tokens(),
            },
        }
        if request is not None and request.max_output_tokens is not None:
            payload["generationConfig"]["maxOutputTokens"] = request.max_output_tokens
        if request is not None and request.response_schema is not None:
            payload["generationConfig"]["responseMimeType"] = "application/json"
            payload["generationConfig"]["responseSchema"] = (
                request.response_schema.json_schema or {}
            )
        if (
            request is not None
            and request.reasoning is not None
            and request.reasoning.budget_tokens is not None
        ):
            payload["generationConfig"]["thinkingConfig"] = {
                "thinkingBudget": request.reasoning.budget_tokens
            }
        if request is not None:
            generation_config = request.provider_options.get("generation_config")
            if isinstance(generation_config, dict):
                payload["generationConfig"].update(generation_config)
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        formatted_tools = self._format_tools(tools or [])
        if formatted_tools:
            payload["tools"] = [{"functionDeclarations": formatted_tools}]
        return payload

    def _post_json(
        self,
        method: str,
        payload: Dict[str, Any],
        *,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        request = urllib.request.Request(
            self._method_url(method),
            data=json.dumps(payload).encode("utf-8"),
            headers=self._request_headers(),
            method="POST",
        )
        with urllib.request.urlopen(
            request,
            timeout=timeout or getattr(self.config, "timeout", None) or 60,
        ) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post_stream(
        self,
        method: str,
        payload: Dict[str, Any],
        *,
        timeout: Optional[float] = None,
    ) -> Iterator[Dict[str, Any]]:
        request = urllib.request.Request(
            self._method_url(method, stream=True),
            data=json.dumps(payload).encode("utf-8"),
            headers=self._request_headers(),
            method="POST",
        )
        with urllib.request.urlopen(
            request,
            timeout=timeout or getattr(self.config, "timeout", None) or 60,
        ) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                if line.startswith("data:"):
                    line = line[len("data:") :].strip()
                if line in {"[DONE]", "DONE"}:
                    break
                yield json.loads(line)

    def _method_url(self, method: str, *, stream: bool = False) -> str:
        """Build the endpoint URL; the API key travels in a header, never here."""
        url = f"{self.base_url}/models/{self._model_name()}:{method}"
        if stream:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}alt=sse"
        return url

    def _request_headers(self) -> Dict[str, str]:
        """JSON headers plus ``x-goog-api-key`` when a key is configured.

        Sending the key as a header keeps it out of the URL, so exceptions,
        logs and proxies that quote the URL never carry it.
        """
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-goog-api-key"] = self.api_key
        return headers

    def _content_to_parts(self, content: Any) -> List[Dict[str, Any]]:
        if not isinstance(content, list):
            return [{"text": str(content)}]
        parts: List[Dict[str, Any]] = []
        for item in content:
            part = item if isinstance(item, ContentPart) else ContentPart(**item)
            if part.type == "text":
                parts.append({"text": part.text or ""})
            elif part.type in {"image_url", "file_url", "audio_url", "video_url"}:
                parts.append(
                    {
                        "fileData": {
                            "mimeType": self._default_mime_type(part),
                            "fileUri": part.url or "",
                        }
                    }
                )
            elif part.type in {
                "image_base64",
                "file",
                "audio_base64",
                "video_base64",
            }:
                parts.append(
                    {
                        "inlineData": {
                            "mimeType": self._default_mime_type(part),
                            "data": part.data or "",
                        }
                    }
                )
            else:
                raise ProviderError(
                    f"Gemini provider cannot serialize content part type: {part.type}"
                )
        return parts

    def _default_mime_type(self, part: ContentPart) -> str:
        if part.mime_type:
            return part.mime_type
        if part.type.startswith("image"):
            return "image/png"
        if part.type.startswith("audio"):
            return "audio/wav"
        if part.type.startswith("video"):
            return "video/mp4"
        return "application/octet-stream"

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

    def _format_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        declarations = []
        for tool in tools:
            func = tool.get("function")
            if not callable(func):
                continue
            declarations.append(
                {
                    "name": getattr(func, "__name__", ""),
                    "description": tool.get("description", ""),
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            name: self._gemini_parameter_schema(param_info)
                            for name, param_info in (
                                tool.get("parameters") or {}
                            ).items()
                        },
                        "required": [
                            name
                            for name, param_info in (
                                tool.get("parameters") or {}
                            ).items()
                            if isinstance(param_info, dict)
                            and param_info.get("required", False)
                        ],
                    },
                }
            )
        return declarations

    def _gemini_parameter_schema(self, param_info: Any) -> Dict[str, Any]:
        if not isinstance(param_info, dict):
            return {"type": "STRING"}
        json_type = self._python_type_to_gemini_schema_type(
            str(param_info.get("type", "str"))
        )
        schema: Dict[str, Any] = {"type": json_type}
        if param_info.get("description"):
            schema["description"] = str(param_info["description"])
        if param_info.get("enum"):
            schema["enum"] = list(param_info["enum"])
        return schema

    def _python_type_to_gemini_schema_type(self, python_type: str) -> str:
        mapping = {
            "str": "STRING",
            "int": "INTEGER",
            "float": "NUMBER",
            "bool": "BOOLEAN",
            "list": "ARRAY",
            "dict": "OBJECT",
            "List": "ARRAY",
            "Dict": "OBJECT",
        }
        return mapping.get(python_type, "STRING")

    def _extract_text(self, data: Dict[str, Any]) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            return ""
        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        return "".join(str(part.get("text", "")) for part in parts)

    def _extract_function_calls(
        self,
        data: Dict[str, Any],
        *,
        id_offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return the first candidate's function calls with run-unique ids.

        The API's ``functionCall.id`` is used when present; otherwise ids are
        numbered from ``id_offset``, the count of earlier calls in the run.
        """
        calls: List[Dict[str, Any]] = []
        for part in self._candidate_content(data).get("parts") or []:
            function_call = self._part_function_call(part)
            if function_call is None:
                continue
            name = str(function_call.get("name") or "")
            if not name:
                continue
            native_id = function_call.get("id")
            calls.append(
                {
                    "id": (
                        str(native_id)
                        if native_id
                        else f"gemini-call-{id_offset + len(calls)}"
                    ),
                    "name": name,
                    "args": function_call.get("args") or {},
                    "raw": function_call,
                }
            )
        return calls

    def _candidate_content(self, data: Dict[str, Any]) -> Dict[str, Any]:
        candidates = data.get("candidates") or []
        if not candidates or not isinstance(candidates[0], dict):
            return {}
        content = candidates[0].get("content")
        return content if isinstance(content, dict) else {}

    def _part_function_call(self, part: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(part, dict):
            return None
        function_call = part.get("functionCall") or part.get("function_call")
        return function_call if isinstance(function_call, dict) else None

    def _content_function_call_count(self, contents: List[Dict[str, Any]]) -> int:
        return sum(
            1
            for content in contents
            if isinstance(content, dict) and content.get("role") == "model"
            for part in content.get("parts") or []
            if self._part_function_call(part) is not None
        )

    def _native_function_call_ids(self, contents: List[Dict[str, Any]]) -> Set[str]:
        """Return API-issued call ids from the latest model turn."""
        for content in reversed(contents):
            if isinstance(content, dict) and content.get("role") == "model":
                return {
                    str(function_call["id"])
                    for function_call in (
                        self._part_function_call(part)
                        for part in content.get("parts") or []
                    )
                    if function_call is not None and function_call.get("id")
                }
        return set()

    def _runtime_tool_call_response(
        self,
        data: Dict[str, Any],
        payload: Dict[str, Any],
        function_calls: List[Dict[str, Any]],
    ) -> ModelResponse:
        tool_calls = [
            ToolCall(
                id=str(call["id"]),
                name=str(call["name"]),
                arguments=(
                    call.get("args") if isinstance(call.get("args"), dict) else {}
                ),
                raw=call.get("raw"),
            )
            for call in function_calls
        ]
        template = {key: value for key, value in payload.items() if key != "contents"}
        contents = list(payload.get("contents") or [])
        # Return the model turn exactly as received: Gemini 3 rejects a
        # continuation whose functionCall parts lost their thoughtSignature,
        # and text or thought parts belong to the same turn.
        model_content = copy.deepcopy(self._candidate_content(data))
        model_content["role"] = model_content.get("role") or "model"
        contents.append(model_content)
        return ModelResponse(
            provider=self.provider_name,
            model=self._model_name(),
            tool_calls=tool_calls,
            raw=data,
            metadata={
                "gemini_payload": template,
                "gemini_contents": contents,
            },
        )

    def _function_response_part(
        self,
        result: ToolResult,
        *,
        call_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        response: Dict[str, Any] = {"result": result.content}
        if result.is_error:
            response["is_error"] = True
        function_response: Dict[str, Any] = {
            "name": result.name,
            "response": response,
        }
        if call_id:
            # Echo only ids the API issued; generated ids are Praval-local.
            function_response["id"] = call_id
        return {"functionResponse": function_response}

    def _handle_function_calls(
        self,
        *,
        function_calls: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        request: Optional[ModelRequest],
        hitl_context: Optional[Dict[str, Any]],
    ) -> ModelResponse:
        function_response_parts: List[Dict[str, Any]] = []
        tool_calls: List[ToolCall] = []
        tool_results: List[Dict[str, Any]] = []

        for idx, function_call in enumerate(function_calls):
            name = function_call["name"]
            raw_args = function_call.get("args") or {}
            tool_call_id = function_call["id"]
            continuation_state = {
                "schema": "gemini_tool_v1",
                "messages": messages,
                "function_calls": function_calls,
                "current_index": idx,
                "tool_results": list(tool_results),
            }
            result_content = execute_legacy_tool_call(
                hitl_context=hitl_context,
                tool_call_id=tool_call_id,
                function_name=name,
                raw_args=raw_args,
                available_tools=available_tools or [],
                continuation_state=continuation_state,
            )
            tool_calls.append(
                ToolCall(
                    id=tool_call_id,
                    name=name,
                    arguments=raw_args if isinstance(raw_args, dict) else {},
                    raw=function_call.get("raw"),
                )
            )
            tool_results.append(
                {
                    "tool_call_id": tool_call_id,
                    "name": name,
                    "content": result_content,
                }
            )
            function_response_parts.append(
                {
                    "functionResponse": {
                        "name": name,
                        "response": {"result": result_content},
                    }
                }
            )

        followup_payload = self._build_followup_payload(
            messages=messages,
            function_calls=function_calls,
            function_response_parts=function_response_parts,
            available_tools=available_tools,
            request=request,
        )
        try:
            # The tools have already run: retry only this request.
            data = call_with_retries(
                "follow_up",
                lambda: self._post_json(
                    "generateContent",
                    followup_payload,
                    timeout=request.timeout if request is not None else None,
                ),
                retries=max_provider_retries(self.config),
                map_error=lambda exc: self._provider_error(exc, "Gemini API error"),
            )
            content = self._extract_text(data)
        except Exception:
            data = None
            content = "\n".join(result["content"] for result in tool_results)

        return ModelResponse(
            content=content,
            provider=self.provider_name,
            model=self._model_name(),
            tool_calls=tool_calls,
            raw=data,
            metadata={"tool_results": tool_results},
        )

    def _build_followup_payload(
        self,
        *,
        messages: List[Dict[str, Any]],
        function_calls: List[Dict[str, Any]],
        function_response_parts: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
        request: Optional[ModelRequest],
    ) -> Dict[str, Any]:
        payload = self._build_payload(messages, available_tools, request=request)
        payload["contents"].append(
            {
                "role": "model",
                "parts": [
                    {
                        "functionCall": {
                            "name": call["name"],
                            "args": call.get("args") or {},
                        }
                    }
                    for call in function_calls
                ],
            }
        )
        payload["contents"].append({"role": "user", "parts": function_response_parts})
        return payload
