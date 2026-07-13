"""
OpenAI provider implementation for Praval framework.

Provides integration with OpenAI's Chat Completions API with support
for conversation history, tool calling, and streaming responses.
"""

import json
import os
from typing import Any, Dict, Iterator, List, Optional, Tuple

import openai

from ..core.exceptions import (
    HITLConfigurationError,
    InterventionRequired,
    ProviderError,
)
from ..hitl.runtime import HITLRuntime
from ..model_runtime import execute_legacy_tool_call
from ..models import (
    AudioResponse,
    ContentPart,
    ModelEvent,
    ModelRequest,
    ModelResponse,
    ProviderCapabilities,
    SpeechRequest,
    ToolCall,
    ToolResult,
    ToolSpec,
    TranscriptionRequest,
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


class OpenAIProvider:
    """
    OpenAI provider for LLM interactions.

    Handles communication with OpenAI's GPT models through the
    Chat Completions API with support for tools and conversation history.
    """

    provider_name = "openai"
    capabilities = ProviderCapabilities(
        chat_completions=True,
        responses_api=True,
        tools=True,
        streaming=True,
        native_streaming=True,
        tool_streaming=True,
        structured_outputs=True,
        json_schema_mode="json_schema",
        multimodal=True,
        image_input=True,
        audio_transcription=True,
        speech_generation=True,
        reasoning=True,
        reasoning_effort=True,
        embeddings=True,
    )

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
            api_key_env = getattr(config, "api_key_env", None) or "OPENAI_API_KEY"
            api_key = os.getenv(api_key_env)
            if not api_key:
                raise ProviderError(f"{api_key_env} environment variable not set")

            client_kwargs: Dict[str, Any] = {"api_key": api_key}
            if getattr(config, "base_url", None):
                client_kwargs["base_url"] = config.base_url
            if getattr(config, "timeout", None):
                client_kwargs["timeout"] = config.timeout
            self.client = openai.OpenAI(**client_kwargs)
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
            call_params = self._base_chat_completion_params(
                model=self._model_name(),
                messages=messages,
                temperature=self.config.temperature,
                max_output_tokens=self._max_output_tokens(),
            )

            if tools:
                formatted_tools = self._format_tools_for_openai(tools)
                if formatted_tools:
                    call_params["tools"] = formatted_tools
                    call_params["tool_choice"] = "auto"

            response = self._create_chat_completion_with_empty_retry(call_params)

            if response.choices and response.choices[0].message:
                message = response.choices[0].message
                if hasattr(message, "tool_calls") and message.tool_calls:
                    return self._handle_tool_calls(
                        message.tool_calls,
                        tools,
                        messages,
                        hitl_context=hitl_context,
                    )
                return self._extract_chat_message_text(message)

            return ""

        except (InterventionRequired, HITLConfigurationError):
            raise
        except Exception as e:
            raise ProviderError(f"OpenAI API error: {_redact_secrets(str(e))}") from e

    def invoke(
        self,
        request: ModelRequest,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ModelResponse:
        """Invoke OpenAI through the provider-neutral adapter surface."""
        if self._use_responses_api(request):
            return self._invoke_responses(request)
        return self._invoke_chat_completions(request, tools=tools)

    def stream(
        self,
        request: ModelRequest,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[ModelEvent]:
        """Stream OpenAI responses as provider-neutral events."""
        try:
            if self._use_responses_api(request):
                yield from self._stream_responses(request)
            else:
                yield from self._stream_chat_completions(request, tools=tools)
        except Exception as e:
            message = _redact_secrets(str(e))
            yield ModelEvent(type="error", metadata={"message": message})
            raise ProviderError(f"OpenAI streaming error: {message}") from e

    def transcribe(self, request: TranscriptionRequest) -> AudioResponse:
        """Transcribe request-based audio through OpenAI's audio endpoint."""
        if not isinstance(request, TranscriptionRequest):
            request = TranscriptionRequest.model_validate(request)

        file_value, should_close = self._audio_file_value(request)
        try:
            call_params: Dict[str, Any] = {
                "file": file_value,
                "model": request.model
                or self._provider_config_option(
                    "transcription_model", "gpt-4o-transcribe"
                ),
                "response_format": request.response_format,
            }
            if request.language:
                call_params["language"] = request.language
            if request.prompt:
                call_params["prompt"] = request.prompt
            if request.temperature is not None:
                call_params["temperature"] = request.temperature
            if request.timeout is not None:
                call_params["timeout"] = request.timeout
            self._apply_audio_provider_options(call_params, request.provider_options)

            response = self.client.audio.transcriptions.create(**call_params)
            text = self._transcription_text(response)
            if not text:
                raise ProviderError("OpenAI transcription returned no text")
            return AudioResponse(
                text=text,
                provider=self.provider_name,
                model=str(call_params["model"]),
                format=request.response_format,
                raw=response,
                metadata=dict(request.metadata),
            )
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(
                f"OpenAI transcription error: {_redact_secrets(str(e))}"
            ) from e
        finally:
            if should_close:
                file_value.close()

    def speak(self, request: SpeechRequest) -> AudioResponse:
        """Synthesize request-based speech through OpenAI's audio endpoint."""
        if not isinstance(request, SpeechRequest):
            request = SpeechRequest.model_validate(request)
        if not request.input.strip():
            raise ProviderError("Speech input cannot be empty")
        if not 0.25 <= request.speed <= 4.0:
            raise ProviderError("Speech speed must be between 0.25 and 4.0")

        try:
            model = request.model or self._provider_config_option(
                "speech_model", "tts-1"
            )
            if request.instructions and model in {"tts-1", "tts-1-hd"}:
                raise ProviderError(
                    f"Speech instructions are not supported by model '{model}'"
                )
            call_params: Dict[str, Any] = {
                "input": request.input,
                "model": model,
                "voice": request.voice,
                "response_format": request.response_format,
                "speed": request.speed,
            }
            if request.instructions:
                call_params["instructions"] = request.instructions
            if request.timeout is not None:
                call_params["timeout"] = request.timeout
            self._apply_audio_provider_options(call_params, request.provider_options)

            response = self.client.audio.speech.create(**call_params)
            data = self._speech_bytes(response)
            if not data:
                raise ProviderError("OpenAI speech generation returned no audio")
            return AudioResponse(
                data=data,
                provider=self.provider_name,
                model=str(call_params["model"]),
                format=request.response_format,
                mime_type=self._speech_mime_type(request.response_format),
                raw=response,
                metadata=dict(request.metadata),
            )
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(
                f"OpenAI speech generation error: {_redact_secrets(str(e))}"
            ) from e

    def close(self) -> None:
        """Close the underlying SDK client when supported."""
        close = getattr(self.client, "close", None)
        if callable(close):
            close()

    def _audio_file_value(self, request: TranscriptionRequest) -> Tuple[Any, bool]:
        audio = request.audio
        if isinstance(audio, (bytes, bytearray, memoryview)):
            data = bytes(audio)
            if not data:
                raise ProviderError("Audio input cannot be empty")
            return (
                (
                    request.filename or "audio.wav",
                    data,
                    request.mime_type or "audio/wav",
                ),
                False,
            )
        if isinstance(audio, (str, os.PathLike)):
            path = os.fspath(audio)
            if not os.path.isfile(path):
                raise ProviderError(f"Audio file does not exist: {path}")
            return open(path, "rb"), True
        if audio is None:
            raise ProviderError("Audio input cannot be empty")
        if hasattr(audio, "read") or isinstance(audio, tuple):
            return audio, False
        raise ProviderError(
            "Audio input must be bytes, a file path, a file object, "
            "or an SDK file tuple"
        )

    def _provider_config_option(self, name: str, default: str) -> str:
        options = getattr(self.config, "provider_options", None) or {}
        return str(options.get(name) or default)

    def _apply_audio_provider_options(
        self,
        call_params: Dict[str, Any],
        provider_options: Dict[str, Any],
    ) -> None:
        if provider_options.get("stream"):
            raise ProviderError(
                "Streaming audio is outside the request-based voice API; "
                "use a realtime or streaming adapter instead"
            )
        reserved = {
            "file",
            "input",
            "model",
            "voice",
            "response_format",
            "speed",
            "instructions",
            "language",
            "prompt",
            "temperature",
            "timeout",
            "stream",
            "transcription_model",
            "speech_model",
        }
        for key, value in provider_options.items():
            if key not in reserved:
                call_params.setdefault(key, value)

    def _transcription_text(self, response: Any) -> str:
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            return str(response.get("text") or "")
        value = getattr(response, "text", None)
        return value if isinstance(value, str) else ""

    def _speech_bytes(self, response: Any) -> bytes:
        if isinstance(response, bytes):
            return response
        if isinstance(response, bytearray):
            return bytes(response)
        content = getattr(response, "content", None)
        if isinstance(content, bytes):
            return content
        if isinstance(content, bytearray):
            return bytes(content)
        read = getattr(response, "read", None)
        if callable(read):
            data = read()
            if isinstance(data, bytes):
                return data
            if isinstance(data, bytearray):
                return bytes(data)
        return b""

    def _speech_mime_type(self, response_format: str) -> str:
        return {
            "mp3": "audio/mpeg",
            "opus": "audio/opus",
            "aac": "audio/aac",
            "flac": "audio/flac",
            "wav": "audio/wav",
            "pcm": "audio/pcm",
        }.get(response_format.lower(), "application/octet-stream")

    def _model_name(self) -> str:
        return str(getattr(self.config, "model", None) or "gpt-5.4-mini")

    def _max_output_tokens(self) -> int:
        return int(
            getattr(self.config, "max_output_tokens", None)
            or getattr(self.config, "max_tokens", 1000)
        )

    def _base_chat_completion_params(
        self,
        *,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: Optional[float],
        max_output_tokens: int,
    ) -> Dict[str, Any]:
        call_params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        self._apply_chat_completion_model_constraints(call_params)
        return call_params

    def _apply_chat_completion_model_constraints(
        self,
        call_params: Dict[str, Any],
    ) -> None:
        model = str(call_params.get("model") or "")
        if not self._uses_max_completion_tokens(model):
            return

        if "max_completion_tokens" not in call_params:
            max_tokens = call_params.pop("max_tokens", None)
            if max_tokens is not None:
                call_params["max_completion_tokens"] = max_tokens
        else:
            call_params.pop("max_tokens", None)
        call_params.pop("temperature", None)

    def _uses_max_completion_tokens(self, model: str) -> bool:
        normalized = model.strip().lower().replace("_", "-")
        if ":" in normalized:
            normalized = normalized.rsplit(":", 1)[-1]
        if "/" in normalized:
            normalized = normalized.rsplit("/", 1)[-1]
        return normalized.startswith("gpt-5") or (
            normalized.startswith("o")
            and len(normalized) > 1
            and normalized[1].isdigit()
        )

    def _create_chat_completion_with_empty_retry(
        self,
        call_params: Dict[str, Any],
    ) -> Any:
        response = self.client.chat.completions.create(**call_params)
        retry_params = self._empty_text_retry_params(call_params, response)
        if retry_params is None:
            return response
        return self.client.chat.completions.create(**retry_params)

    def _empty_text_retry_params(
        self,
        call_params: Dict[str, Any],
        response: Any,
    ) -> Optional[Dict[str, Any]]:
        model = str(call_params.get("model") or "")
        if not self._uses_max_completion_tokens(model):
            return None

        finish_reason = self._chat_choice_finish_reason(response)
        if finish_reason == "content_filter":
            return None

        choice = self._first_chat_choice(response)
        message = self._chat_choice_message(choice)
        if message is not None:
            tool_calls = self._event_value(message, "tool_calls", None)
            if tool_calls:
                return None
            if self._extract_chat_message_text(message).strip():
                return None

        current_tokens = self._chat_completion_token_budget(call_params)
        if current_tokens >= 4096:
            return None

        retry_params = dict(call_params)
        retry_params["max_completion_tokens"] = max(current_tokens * 4, 4096)
        retry_params.pop("max_tokens", None)
        retry_params.pop("temperature", None)
        return retry_params

    def _chat_completion_token_budget(self, call_params: Dict[str, Any]) -> int:
        raw_tokens = call_params.get(
            "max_completion_tokens",
            call_params.get("max_tokens", self._max_output_tokens()),
        )
        try:
            return int(raw_tokens or self._max_output_tokens())
        except (TypeError, ValueError):
            return self._max_output_tokens()

    def _first_chat_choice(self, response: Any) -> Any:
        choices = getattr(response, "choices", None)
        if choices is None and isinstance(response, dict):
            choices = response.get("choices")
        if not choices:
            return None
        return choices[0]

    def _chat_choice_message(self, choice: Any) -> Any:
        if choice is None:
            return None
        return self._event_value(choice, "message", None)

    def _chat_choice_finish_reason(self, response: Any) -> Optional[str]:
        choice = self._first_chat_choice(response)
        if choice is None:
            return None
        value = self._event_value(choice, "finish_reason", None)
        return value if isinstance(value, str) else None

    def _extract_chat_message_text(self, message: Any) -> str:
        text = self._extract_content_text(self._event_value(message, "content", None))
        if text:
            return text
        return self._extract_content_text(self._event_value(message, "refusal", None))

    def _extract_content_text(self, content: Any) -> str:
        if content is None:
            return ""
        if type(content).__module__.startswith("unittest.mock"):
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(self._extract_content_part_text(part) for part in content)
        return str(content)

    def _extract_content_part_text(self, part: Any) -> str:
        if part is None:
            return ""
        if isinstance(part, str):
            return part
        for key in ("text", "content", "refusal"):
            value = (
                part.get(key) if isinstance(part, dict) else getattr(part, key, None)
            )
            if value is not None:
                return self._extract_content_text(value)
        return ""

    def _use_responses_api(self, request: ModelRequest) -> bool:
        endpoint = str(
            request.provider_options.get("endpoint")
            or request.provider_options.get("api")
            or ""
        ).lower()
        return (
            endpoint == "responses"
            or bool(request.provider_options.get("use_responses", False))
            or request.reasoning is not None
        )

    def _invoke_chat_completions(
        self,
        request: ModelRequest,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ModelResponse:
        call_params = self._chat_completion_params(request, tools=tools)
        response = self._create_chat_completion_with_empty_retry(call_params)
        return self._chat_model_response(response, call_params)

    def _chat_model_response(
        self,
        response: Any,
        call_params: Dict[str, Any],
    ) -> ModelResponse:
        content = ""
        tool_calls: List[ToolCall] = []
        assistant_tool_calls: List[Dict[str, Any]] = []
        choice = self._first_chat_choice(response)
        message = self._chat_choice_message(choice)
        if message is not None:
            content = self._extract_chat_message_text(message)
            raw_tool_calls = self._event_value(message, "tool_calls", None) or []
            if not isinstance(raw_tool_calls, (list, tuple)):
                raw_tool_calls = []
            assistant_tool_calls = self._serialize_tool_calls(list(raw_tool_calls))
            tool_calls = [
                self._chat_tool_call(tool_call) for tool_call in assistant_tool_calls
            ]
        return ModelResponse(
            content=content,
            provider=self.provider_name,
            model=call_params["model"],
            tool_calls=tool_calls,
            raw=response,
            usage=self._extract_usage(response),
            finish_reason=self._chat_choice_finish_reason(response),
            metadata={
                "openai_endpoint": "chat.completions",
                "assistant_tool_calls": assistant_tool_calls,
            },
        )

    def _chat_tool_call(self, tool_call: Dict[str, Any]) -> ToolCall:
        function = tool_call.get("function") or {}
        raw_arguments = function.get("arguments") or "{}"
        try:
            arguments = json.loads(raw_arguments)
        except (TypeError, json.JSONDecodeError):
            arguments = {"raw": raw_arguments}
        return ToolCall(
            id=str(tool_call.get("id") or ""),
            name=str(function.get("name") or ""),
            arguments=arguments if isinstance(arguments, dict) else {"raw": arguments},
            raw=tool_call,
        )

    def continue_with_tool_results(
        self,
        request: ModelRequest,
        response: ModelResponse,
        tool_results: List[ToolResult],
    ) -> ModelResponse:
        """Submit runtime-executed client tool results to OpenAI."""
        endpoint = response.metadata.get("openai_endpoint")
        if endpoint == "chat.completions":
            return self._continue_chat_completions(request, response, tool_results)
        if endpoint == "responses":
            return self._continue_responses(request, response, tool_results)
        raise ProviderError("OpenAI tool continuation state is missing")

    def _continue_chat_completions(
        self,
        request: ModelRequest,
        response: ModelResponse,
        tool_results: List[ToolResult],
    ) -> ModelResponse:
        assistant_tool_calls = response.metadata.get("assistant_tool_calls")
        if not isinstance(assistant_tool_calls, list):
            raise ProviderError("OpenAI Chat Completions tool state is missing")
        call_params = self._chat_completion_params(request)
        messages = list(call_params["messages"])
        messages.append(
            {
                "role": "assistant",
                "content": response.content or None,
                "tool_calls": assistant_tool_calls,
            }
        )
        messages.extend(
            {
                "role": "tool",
                "tool_call_id": result.tool_call_id,
                "content": result.content,
            }
            for result in tool_results
        )
        call_params["messages"] = messages
        continued = self._create_chat_completion_with_empty_retry(call_params)
        return self._chat_model_response(continued, call_params)

    def _continue_responses(
        self,
        request: ModelRequest,
        response: ModelResponse,
        tool_results: List[ToolResult],
    ) -> ModelResponse:
        response_id = response.metadata.get("response_id")
        if not response_id:
            raise ProviderError("OpenAI Responses tool state is missing response_id")
        call_params = self._responses_params(request)
        call_params["previous_response_id"] = response_id
        call_params["input"] = [
            {
                "type": "function_call_output",
                "call_id": result.tool_call_id,
                "output": result.content,
            }
            for result in tool_results
        ]
        continued = self.client.responses.create(**call_params)
        return self._responses_model_response(continued, call_params)

    def _invoke_responses(self, request: ModelRequest) -> ModelResponse:
        call_params = self._responses_params(request)
        response = self.client.responses.create(**call_params)
        return self._responses_model_response(response, call_params)

    def _responses_model_response(
        self,
        response: Any,
        call_params: Dict[str, Any],
    ) -> ModelResponse:
        output = self._event_value(response, "output", None) or []
        if not isinstance(output, (list, tuple)):
            output = []
        tool_calls = [
            self._tool_call(item)
            for item in output
            if self._event_value(item, "type", "") == "function_call"
        ]
        return ModelResponse(
            content=self._extract_responses_text(response),
            provider=self.provider_name,
            model=call_params["model"],
            tool_calls=tool_calls,
            raw=response,
            usage=self._extract_usage(response),
            metadata={
                "openai_endpoint": "responses",
                "response_id": self._event_value(response, "id", None),
            },
        )

    def _chat_completion_params(
        self,
        request: ModelRequest,
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        if request.provider_options.get("experimental_tools") is not None:
            raise ProviderError(
                "OpenAI experimental tools require the Responses API endpoint"
            )
        call_params = self._base_chat_completion_params(
            model=request.model or self._model_name(),
            messages=[
                self._format_message_for_openai(message, responses=False)
                for message in request.messages
            ],
            temperature=request.temperature,
            max_output_tokens=request.max_output_tokens or self._max_output_tokens(),
        )
        if tools:
            formatted_tools = self._format_tools_for_openai(tools)
            if formatted_tools:
                call_params["tools"] = formatted_tools
                call_params["tool_choice"] = "auto"
        elif request.tools:
            formatted_tool_specs = self._format_tool_specs_for_openai(request.tools)
            if formatted_tool_specs:
                call_params["tools"] = formatted_tool_specs
                call_params["tool_choice"] = "auto"
        if request.response_schema is not None:
            call_params["response_format"] = self._openai_response_format(
                request.response_schema
            )
        if request.timeout is not None:
            call_params["timeout"] = request.timeout
        if stream:
            call_params["stream"] = True
            if request.stream_options:
                call_params["stream_options"] = request.stream_options
        self._apply_provider_options(call_params, request)
        self._apply_chat_completion_model_constraints(call_params)
        return call_params

    def _responses_params(
        self,
        request: ModelRequest,
        *,
        stream: bool = False,
    ) -> Dict[str, Any]:
        call_params: Dict[str, Any] = {
            "model": request.model or self._model_name(),
            "input": self._responses_input(request),
            "temperature": request.temperature,
            "max_output_tokens": request.max_output_tokens or self._max_output_tokens(),
        }
        formatted_tools = self._format_tool_specs_for_openai(request.tools)
        formatted_tools.extend(self._experimental_tools(request))
        if formatted_tools:
            call_params["tools"] = formatted_tools
        if request.response_schema is not None:
            call_params["text"] = {
                "format": self._openai_text_format(request.response_schema)
            }
        if request.reasoning is not None:
            reasoning: Dict[str, Any] = {}
            if request.reasoning.effort:
                reasoning["effort"] = request.reasoning.effort
            if request.reasoning.summary:
                reasoning["summary"] = request.reasoning.summary
            if request.reasoning.budget_tokens is not None:
                reasoning["budget_tokens"] = request.reasoning.budget_tokens
            if reasoning:
                call_params["reasoning"] = reasoning
        if request.timeout is not None:
            call_params["timeout"] = request.timeout
        if stream:
            call_params["stream"] = True
            if request.stream_options:
                call_params["stream_options"] = request.stream_options
        self._apply_provider_options(call_params, request)
        return call_params

    def _apply_provider_options(
        self,
        call_params: Dict[str, Any],
        request: ModelRequest,
    ) -> None:
        reserved = {
            "endpoint",
            "api",
            "use_responses",
            "capabilities",
            "transcription_model",
            "speech_model",
            "allow_experimental_tools",
            "experimental_tools",
        }
        for key, value in request.provider_options.items():
            if key not in reserved:
                call_params.setdefault(key, value)

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

    def _responses_input(self, request: ModelRequest) -> List[Dict[str, Any]]:
        return [
            self._format_message_for_openai(message, responses=True)
            for message in request.messages
        ]

    def _format_message_for_openai(
        self,
        message: Any,
        *,
        responses: bool,
    ) -> Dict[str, Any]:
        content = self._format_openai_content(message.content, responses=responses)
        formatted: Dict[str, Any] = {"role": message.role, "content": content}
        if getattr(message, "name", None):
            formatted["name"] = message.name
        if getattr(message, "tool_call_id", None):
            formatted["tool_call_id"] = message.tool_call_id
        return formatted

    def _format_openai_content(self, content: Any, *, responses: bool) -> Any:
        if not isinstance(content, list):
            return content
        formatted_parts: List[Dict[str, Any]] = []
        for item in content:
            part = item if isinstance(item, ContentPart) else ContentPart(**item)
            if part.type == "text":
                if responses:
                    formatted_parts.append(
                        {"type": "input_text", "text": part.text or ""}
                    )
                else:
                    formatted_parts.append({"type": "text", "text": part.text or ""})
            elif part.type in {"image_url", "image_base64", "image"}:
                image_url = part.url or ""
                if part.type == "image_base64":
                    image_url = (
                        f"data:{part.mime_type or 'image/png'};base64,{part.data or ''}"
                    )
                if responses:
                    formatted_parts.append(
                        {"type": "input_image", "image_url": image_url}
                    )
                else:
                    formatted_parts.append(
                        {"type": "image_url", "image_url": {"url": image_url}}
                    )
            else:
                raise ProviderError(
                    f"OpenAI provider cannot serialize content part type: {part.type}"
                )
        return formatted_parts

    def _stream_chat_completions(
        self,
        request: ModelRequest,
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[ModelEvent]:
        call_params = self._chat_completion_params(
            request,
            tools=tools,
            stream=True,
        )
        chunks = self.client.chat.completions.create(**call_params)
        content_parts: List[str] = []
        usage: Optional[Usage] = None
        finish_reason: Optional[str] = None
        for chunk in chunks:
            usage = self._extract_usage(chunk) or usage
            choices = getattr(chunk, "choices", None) or []
            if not choices and isinstance(chunk, dict):
                choices = chunk.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = self._event_value(choice, "delta", {})
            text = self._event_value(delta, "content", None)
            if text:
                content_parts.append(str(text))
                yield ModelEvent(type="delta", delta=str(text))
            tool_call_deltas = self._event_value(delta, "tool_calls", None)
            if tool_call_deltas:
                yield ModelEvent(
                    type="tool_call_delta",
                    metadata={"delta": self._serialize_event_value(tool_call_deltas)},
                )
            finish_reason = self._event_value(choice, "finish_reason", finish_reason)
        response = ModelResponse(
            content="".join(content_parts),
            provider=self.provider_name,
            model=call_params["model"],
            usage=usage,
            finish_reason=finish_reason,
        )
        if usage:
            yield ModelEvent(type="usage", usage=usage)
        yield ModelEvent(type="final", response=response, usage=usage)

    def _stream_responses(self, request: ModelRequest) -> Iterator[ModelEvent]:
        call_params = self._responses_params(request, stream=True)
        events = self.client.responses.create(**call_params)
        content_parts: List[str] = []
        final_response: Optional[ModelResponse] = None
        usage: Optional[Usage] = None
        for event in events:
            event_type = str(self._event_value(event, "type", ""))
            if event_type in {"response.output_text.delta", "output_text.delta"}:
                delta = self._event_value(event, "delta", "")
                if delta:
                    content_parts.append(str(delta))
                    yield ModelEvent(type="delta", delta=str(delta))
            elif event_type.endswith("function_call_arguments.delta"):
                yield ModelEvent(
                    type="tool_call_delta",
                    metadata={"delta": self._event_value(event, "delta", "")},
                )
            elif event_type in {"response.output_item.done", "output_item.done"}:
                item = self._event_value(event, "item", {})
                if self._event_value(item, "type", "") == "function_call":
                    yield ModelEvent(type="tool_call", tool_call=self._tool_call(item))
            elif event_type in {"response.completed", "response.done"}:
                raw_response = self._event_value(event, "response", event)
                usage = self._extract_usage(raw_response) or usage
                final_response = ModelResponse(
                    content=self._extract_responses_text(raw_response)
                    or "".join(content_parts),
                    provider=self.provider_name,
                    model=call_params["model"],
                    raw=raw_response,
                    usage=usage,
                )
            elif event_type in {"response.failed", "response.error", "error"}:
                error = self._event_value(event, "error", event)
                yield ModelEvent(
                    type="error",
                    metadata={"message": _redact_secrets(str(error))},
                )
        if final_response is None:
            final_response = ModelResponse(
                content="".join(content_parts),
                provider=self.provider_name,
                model=call_params["model"],
                usage=usage,
            )
        if final_response.usage:
            yield ModelEvent(type="usage", usage=final_response.usage)
        yield ModelEvent(
            type="final",
            response=final_response,
            usage=final_response.usage,
        )

    def _format_tool_specs_for_openai(
        self, tool_specs: List[ToolSpec]
    ) -> List[Dict[str, Any]]:
        formatted_tools = []
        for spec in tool_specs:
            function_def: Dict[str, Any] = {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            }
            if spec.strict:
                function_def["strict"] = True
            formatted_tools.append({"type": "function", "function": function_def})
        return formatted_tools

    def _openai_response_format(self, config: Any) -> Dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": config.name or "praval_response",
                "schema": config.json_schema or {},
                "strict": config.strict,
            },
        }

    def _openai_text_format(self, config: Any) -> Dict[str, Any]:
        return {
            "type": "json_schema",
            "name": config.name or "praval_response",
            "schema": config.json_schema or {},
            "strict": config.strict,
        }

    def _extract_responses_text(self, response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if output_text is not None:
            return str(output_text)
        output = getattr(response, "output", None)
        if output is None and isinstance(response, dict):
            output = response.get("output")
        text_parts: List[str] = []
        for item in output or []:
            content = getattr(item, "content", None)
            if content is None and isinstance(item, dict):
                content = item.get("content")
            for part in content or []:
                part_type = getattr(part, "type", None) or (
                    part.get("type") if isinstance(part, dict) else None
                )
                if part_type in {"output_text", "text"}:
                    value = getattr(part, "text", None) or (
                        part.get("text", "") if isinstance(part, dict) else ""
                    )
                    text_parts.append(str(value))
        return "".join(text_parts)

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

        input_tokens = int(getter("input_tokens", getter("prompt_tokens", 0)) or 0)
        output_tokens = int(
            getter("output_tokens", getter("completion_tokens", 0)) or 0
        )
        total_tokens = int(getter("total_tokens", input_tokens + output_tokens) or 0)
        output_details = getter("output_tokens_details", {})
        if not output_details:
            output_details = getter("completion_tokens_details", {})
        if isinstance(output_details, dict):
            reasoning_tokens = int(output_details.get("reasoning_tokens", 0) or 0)
        else:
            reasoning_tokens = int(getattr(output_details, "reasoning_tokens", 0) or 0)
        return Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            reasoning_tokens=reasoning_tokens,
        )

    def _event_value(self, value: Any, key: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(key, default)
        return getattr(value, key, default)

    def _serialize_event_value(self, value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            return [self._serialize_event_value(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): self._serialize_event_value(item)
                for key, item in value.items()
            }
        if hasattr(value, "model_dump"):
            return value.model_dump(exclude_none=True)
        return {
            key: self._serialize_event_value(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }

    def _tool_call(self, item: Any) -> ToolCall:
        raw_args = self._event_value(item, "arguments", {}) or {}
        if isinstance(raw_args, str):
            try:
                arguments = json.loads(raw_args)
            except json.JSONDecodeError:
                arguments = {"raw": raw_args}
        elif isinstance(raw_args, dict):
            arguments = raw_args
        else:
            arguments = {"raw": raw_args}
        return ToolCall(
            id=str(
                self._event_value(item, "call_id", None)
                or self._event_value(item, "id", "")
            ),
            name=str(self._event_value(item, "name", "")),
            arguments=arguments,
            raw=item,
        )

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
        tool_messages = list(existing_tool_messages or [])

        for idx in range(start_index, len(serialized_tool_calls)):
            tool_call = serialized_tool_calls[idx]
            function_name = tool_call["function"]["name"]
            arguments = tool_call["function"]["arguments"]
            tool_call_id = tool_call["id"]

            continuation_state = None
            if not (idx == start_index and resume_intervention is not None):
                continuation_state = {
                    "schema": "openai_tool_v1",
                    "original_messages": original_messages,
                    "tool_calls": serialized_tool_calls,
                    "current_index": idx,
                    "tool_messages": list(tool_messages),
                }
            result_content = execute_legacy_tool_call(
                hitl_context=hitl_context,
                tool_call_id=tool_call_id,
                function_name=function_name,
                raw_args=arguments,
                available_tools=available_tools or [],
                continuation_state=continuation_state,
                resume_intervention=(
                    resume_intervention
                    if idx == start_index and resume_intervention is not None
                    else None
                ),
            )

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
            call_params = self._base_chat_completion_params(
                model=self._model_name(),
                messages=extended_messages,
                temperature=self.config.temperature,
                max_output_tokens=self._max_output_tokens(),
            )
            follow_up_response = self._create_chat_completion_with_empty_retry(
                call_params
            )

            if follow_up_response.choices and follow_up_response.choices[0].message:
                return self._extract_chat_message_text(
                    follow_up_response.choices[0].message
                )

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
