"""Provider-neutral model contracts for Praval.

These types describe model input, output, tools, events, and capabilities
without binding the rest of Praval to one provider's wire format.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field


class ContentPart(BaseModel):
    """A single multimodal content part."""

    model_config = ConfigDict(extra="allow")

    type: str = "text"
    text: Optional[str] = None
    data: Optional[str] = None
    url: Optional[str] = None
    mime_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def text_part(cls, text: str) -> "ContentPart":
        """Create a text content part."""
        return cls(type="text", text=text)

    @classmethod
    def image_url(cls, url: str, mime_type: Optional[str] = None) -> "ContentPart":
        """Create an image URL content part."""
        return cls(type="image_url", url=url, mime_type=mime_type)

    @classmethod
    def image_base64(cls, data: str, mime_type: str = "image/png") -> "ContentPart":
        """Create an inline base64 image content part."""
        return cls(type="image_base64", data=data, mime_type=mime_type)

    @classmethod
    def audio_url(cls, url: str, mime_type: Optional[str] = None) -> "ContentPart":
        """Create an audio URL content part."""
        return cls(type="audio_url", url=url, mime_type=mime_type)

    @classmethod
    def audio_base64(cls, data: str, mime_type: str = "audio/wav") -> "ContentPart":
        """Create an inline base64 audio content part."""
        return cls(type="audio_base64", data=data, mime_type=mime_type)

    @classmethod
    def video_url(cls, url: str, mime_type: Optional[str] = None) -> "ContentPart":
        """Create a video URL content part."""
        return cls(type="video_url", url=url, mime_type=mime_type)

    @classmethod
    def video_base64(cls, data: str, mime_type: str = "video/mp4") -> "ContentPart":
        """Create an inline base64 video content part."""
        return cls(type="video_base64", data=data, mime_type=mime_type)

    @classmethod
    def file_url(
        cls,
        url: str,
        mime_type: str = "application/octet-stream",
        *,
        name: Optional[str] = None,
    ) -> "ContentPart":
        """Create a remote file content part."""
        metadata = {"name": name} if name else {}
        return cls(type="file_url", url=url, mime_type=mime_type, metadata=metadata)

    @classmethod
    def file_data(
        cls,
        data: str,
        mime_type: str,
        *,
        name: Optional[str] = None,
    ) -> "ContentPart":
        """Create an inline file content part."""
        metadata = {"name": name} if name else {}
        return cls(type="file", data=data, mime_type=mime_type, metadata=metadata)


class ModelMessage(BaseModel):
    """A provider-neutral conversation message."""

    model_config = ConfigDict(extra="allow")

    role: str
    content: Any
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolSpec(BaseModel):
    """Provider-neutral tool declaration."""

    model_config = ConfigDict(extra="allow")

    name: str
    description: str = ""
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}, "required": []}
    )
    strict: bool = False
    requires_approval: bool = False
    risk_level: str = "low"
    approval_reason: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """A model-requested tool invocation."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    raw: Any = None


class ToolResult(BaseModel):
    """A result returned from a tool invocation."""

    model_config = ConfigDict(extra="allow")

    tool_call_id: str
    name: str
    content: str
    is_error: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Usage(BaseModel):
    """Provider-neutral token usage."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0


class EmbeddingRequest(BaseModel):
    """Provider-neutral embedding request."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    inputs: List[Any]
    provider: Optional[str] = None
    model: Optional[str] = None
    dimensions: Optional[int] = None
    provider_options: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EmbeddingResponse(BaseModel):
    """Provider-neutral embedding response."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    embeddings: List[List[float]]
    provider: Optional[str] = None
    model: Optional[str] = None
    dimensions: Optional[int] = None
    raw: Any = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TranscriptionRequest(BaseModel):
    """Provider-neutral request to transcribe an audio file or byte payload."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    audio: Any
    provider: Optional[str] = None
    model: Optional[str] = None
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    language: Optional[str] = None
    prompt: Optional[str] = None
    response_format: str = "json"
    temperature: Optional[float] = None
    provider_options: Dict[str, Any] = Field(default_factory=dict)
    timeout: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SpeechRequest(BaseModel):
    """Provider-neutral request to synthesize speech from text."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    input: str
    provider: Optional[str] = None
    model: Optional[str] = None
    voice: str = "alloy"
    response_format: str = "mp3"
    speed: float = 1.0
    instructions: Optional[str] = None
    provider_options: Dict[str, Any] = Field(default_factory=dict)
    timeout: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AudioResponse(BaseModel):
    """Provider-neutral transcription or synthesized-audio response."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    text: Optional[str] = None
    data: Optional[bytes] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    format: Optional[str] = None
    mime_type: Optional[str] = None
    raw: Any = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReasoningConfig(BaseModel):
    """Reasoning controls for providers that support them."""

    effort: Optional[str] = None
    summary: Optional[str] = None
    encrypted: bool = False
    budget_tokens: Optional[int] = None
    mode: Optional[str] = None
    display: Optional[str] = None


class StructuredOutputConfig(BaseModel):
    """Structured output request configuration."""

    model_config = ConfigDict(populate_by_name=True)

    json_schema: Optional[Dict[str, Any]] = Field(default=None, alias="schema")
    name: Optional[str] = None
    strict: bool = True


class ProviderCapabilities(BaseModel):
    """Capabilities exposed by a provider or a provider/model pair."""

    text: bool = True
    chat_completions: bool = False
    responses_api: bool = False
    tools: bool = False
    streaming: bool = False
    native_streaming: bool = False
    tool_streaming: bool = False
    structured_outputs: bool = False
    json_schema_mode: Optional[str] = None
    multimodal: bool = False
    image_input: bool = False
    file_input: bool = False
    audio_input: bool = False
    video_input: bool = False
    audio_transcription: bool = False
    speech_generation: bool = False
    reasoning: bool = False
    reasoning_effort: bool = False
    reasoning_budget: bool = False
    embeddings: bool = False
    local: bool = False
    server_tools: bool = False
    mcp: bool = False
    computer_use: bool = False

    def supports(self, capability: str) -> bool:
        """Return whether a named capability is enabled."""
        return bool(getattr(self, capability, False))


class ProviderProfile(BaseModel):
    """A registered provider/model profile."""

    provider: str
    model: str
    display_name: Optional[str] = None
    capabilities: ProviderCapabilities = Field(default_factory=ProviderCapabilities)
    default: bool = False
    endpoint: Optional[str] = None
    local_preset: Optional[str] = None
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    default_parameters: Dict[str, Any] = Field(default_factory=dict)
    unsupported_combinations: List[Dict[str, Any]] = Field(default_factory=list)
    downgrade_policy: str = "error"
    notes: str = ""


class ModelRequest(BaseModel):
    """Provider-neutral model request."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    messages: List[ModelMessage]
    provider: Optional[str] = None
    model: Optional[str] = None
    tools: List[ToolSpec] = Field(default_factory=list)
    temperature: Optional[float] = None
    max_output_tokens: Optional[int] = None
    stream: bool = False
    response_schema: Optional[StructuredOutputConfig] = None
    reasoning: Optional[ReasoningConfig] = None
    provider_options: Dict[str, Any] = Field(default_factory=dict)
    stream_options: Dict[str, Any] = Field(default_factory=dict)
    timeout: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    hitl_context: Optional[Dict[str, Any]] = None


class ModelResponse(BaseModel):
    """Provider-neutral model response."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    content: str = ""
    provider: Optional[str] = None
    model: Optional[str] = None
    messages: List[ModelMessage] = Field(default_factory=list)
    tool_calls: List[ToolCall] = Field(default_factory=list)
    usage: Optional[Usage] = None
    finish_reason: Optional[str] = None
    raw: Any = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def text(self) -> str:
        """Return response content as text."""
        return self.content


class ModelEvent(BaseModel):
    """A streaming model event."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    type: str
    delta: str = ""
    response: Optional[ModelResponse] = None
    tool_call: Optional[ToolCall] = None
    tool_result: Optional[ToolResult] = None
    usage: Optional[Usage] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProviderAdapter(Protocol):
    """Protocol implemented by provider-neutral adapters."""

    provider_name: str
    capabilities: ProviderCapabilities

    def invoke(self, request: ModelRequest) -> ModelResponse:
        """Execute a non-streaming model request."""
        ...

    def stream(self, request: ModelRequest) -> Iterator[ModelEvent]:
        """Execute a streaming model request."""
        ...

    async def ainvoke(self, request: ModelRequest) -> ModelResponse:
        """Execute a non-streaming request asynchronously."""
        ...

    def astream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        """Execute a streaming model request asynchronously."""
        ...

    def close(self) -> None:
        """Release provider resources."""
        ...


__all__ = [
    "AudioResponse",
    "ContentPart",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "ModelEvent",
    "ModelMessage",
    "ModelRequest",
    "ModelResponse",
    "ProviderAdapter",
    "ProviderCapabilities",
    "ProviderProfile",
    "ReasoningConfig",
    "SpeechRequest",
    "StructuredOutputConfig",
    "ToolCall",
    "ToolResult",
    "ToolSpec",
    "TranscriptionRequest",
    "Usage",
]
