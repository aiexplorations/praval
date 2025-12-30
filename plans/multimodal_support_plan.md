# Praval Multimodal Support Plan

**Version**: 1.0
**Date**: 2024-12-29
**Status**: Draft
**Target Release**: v0.8.0

---

## Executive Summary

This document outlines the plan to add multimodal support to Praval, enabling agents to process and generate content across multiple modalities: **text**, **images**, **audio**, and **video**. This enhancement positions Praval as a comprehensive multi-agent framework capable of handling modern AI workloads that span beyond text-only interactions.

### Key Objectives

1. **Vision Support**: Enable agents to analyze images and screenshots
2. **Audio Input**: Support speech-to-text transcription within agent workflows
3. **Audio Output**: Enable text-to-speech generation for agent responses
4. **Video Processing**: Extract and analyze video frames
5. **Backward Compatibility**: Existing text-only agents continue to work unchanged

### Scope

| In Scope | Out of Scope (v0.8.0) |
|----------|----------------------|
| Image analysis (OpenAI, Anthropic) | Real-time video streaming |
| Audio transcription (Whisper) | Video generation |
| Text-to-speech (OpenAI TTS) | Image generation (DALL-E) |
| Video frame extraction | Real-time audio streaming |
| Spore binary attachments | WebRTC integration |

---

## Part 1: Content Type System

### 1.1 Core Data Structures

**File**: `src/praval/core/content.py` (~150 lines)

```python
"""
Multimodal content types for Praval framework.

Provides unified content representation for text, images, audio, and video
that works seamlessly across providers and the Spore protocol.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Union, Optional, List, Dict, Any
import base64
import mimetypes
from pathlib import Path


class ContentType(Enum):
    """Supported content modalities."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


class ImageFormat(Enum):
    """Supported image formats for vision models."""
    PNG = "image/png"
    JPEG = "image/jpeg"
    WEBP = "image/webp"
    GIF = "image/gif"


class AudioFormat(Enum):
    """Supported audio formats."""
    WAV = "audio/wav"
    MP3 = "audio/mpeg"
    FLAC = "audio/flac"
    OGG = "audio/ogg"
    WEBM = "audio/webm"


class VideoFormat(Enum):
    """Supported video formats."""
    MP4 = "video/mp4"
    WEBM = "video/webm"
    MOV = "video/quicktime"


@dataclass
class ContentPart:
    """
    A single piece of content in a multimodal message.

    Attributes:
        type: The modality type (text, image, audio, video)
        data: The content data (string for text, bytes for binary)
        mime_type: MIME type for binary content
        url: Optional URL for remote content
        metadata: Additional metadata (dimensions, duration, etc.)

    Examples:
        # Text content
        ContentPart(type=ContentType.TEXT, data="Describe this image")

        # Image from bytes
        ContentPart(
            type=ContentType.IMAGE,
            data=image_bytes,
            mime_type="image/png"
        )

        # Image from URL
        ContentPart(
            type=ContentType.IMAGE,
            url="https://example.com/image.png"
        )

        # Audio for transcription
        ContentPart(
            type=ContentType.AUDIO,
            data=audio_bytes,
            mime_type="audio/wav"
        )
    """
    type: ContentType
    data: Optional[Union[str, bytes]] = None
    mime_type: Optional[str] = None
    url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate content part."""
        if self.data is None and self.url is None:
            raise ValueError("Either data or url must be provided")

        if self.type != ContentType.TEXT and self.data is not None:
            if not isinstance(self.data, bytes) and self.url is None:
                raise ValueError(f"Binary content types require bytes data or URL")

    @classmethod
    def from_file(cls, path: Union[str, Path], content_type: Optional[ContentType] = None) -> "ContentPart":
        """
        Create ContentPart from a file path.

        Args:
            path: Path to the file
            content_type: Optional explicit content type (auto-detected if not provided)

        Returns:
            ContentPart with file contents
        """
        path = Path(path)
        mime_type, _ = mimetypes.guess_type(str(path))

        # Auto-detect content type from MIME
        if content_type is None:
            if mime_type:
                if mime_type.startswith("image/"):
                    content_type = ContentType.IMAGE
                elif mime_type.startswith("audio/"):
                    content_type = ContentType.AUDIO
                elif mime_type.startswith("video/"):
                    content_type = ContentType.VIDEO
                else:
                    content_type = ContentType.TEXT
            else:
                content_type = ContentType.TEXT

        # Read file
        if content_type == ContentType.TEXT:
            data = path.read_text()
        else:
            data = path.read_bytes()

        return cls(
            type=content_type,
            data=data,
            mime_type=mime_type,
            metadata={"source_path": str(path), "size_bytes": path.stat().st_size}
        )

    def to_base64(self) -> str:
        """Convert binary data to base64 string."""
        if isinstance(self.data, bytes):
            return base64.b64encode(self.data).decode("utf-8")
        raise ValueError("Cannot base64 encode non-binary content")

    def to_data_url(self) -> str:
        """Convert to data URL format for embedding."""
        if self.type == ContentType.TEXT:
            raise ValueError("Text content cannot be converted to data URL")
        b64 = self.to_base64()
        return f"data:{self.mime_type};base64,{b64}"


# Type alias for multimodal messages
MultimodalContent = Union[str, ContentPart, List[ContentPart]]


def normalize_content(content: MultimodalContent) -> List[ContentPart]:
    """
    Normalize any content format to a list of ContentParts.

    Args:
        content: String, single ContentPart, or list of ContentParts

    Returns:
        List of ContentPart objects
    """
    if isinstance(content, str):
        return [ContentPart(type=ContentType.TEXT, data=content)]
    elif isinstance(content, ContentPart):
        return [content]
    elif isinstance(content, list):
        return content
    else:
        raise TypeError(f"Unsupported content type: {type(content)}")
```

### 1.2 Helper Functions

**File**: `src/praval/core/content.py` (continued, ~50 lines)

```python
def text(content: str) -> ContentPart:
    """Create a text content part."""
    return ContentPart(type=ContentType.TEXT, data=content)


def image(
    data: Optional[bytes] = None,
    url: Optional[str] = None,
    path: Optional[Union[str, Path]] = None,
    mime_type: str = "image/png"
) -> ContentPart:
    """
    Create an image content part.

    Args:
        data: Raw image bytes
        url: URL to image
        path: Path to image file
        mime_type: MIME type (auto-detected from path if provided)

    Returns:
        ContentPart for image
    """
    if path:
        return ContentPart.from_file(path, ContentType.IMAGE)
    return ContentPart(
        type=ContentType.IMAGE,
        data=data,
        url=url,
        mime_type=mime_type
    )


def audio(
    data: Optional[bytes] = None,
    url: Optional[str] = None,
    path: Optional[Union[str, Path]] = None,
    mime_type: str = "audio/wav"
) -> ContentPart:
    """Create an audio content part."""
    if path:
        return ContentPart.from_file(path, ContentType.AUDIO)
    return ContentPart(
        type=ContentType.AUDIO,
        data=data,
        url=url,
        mime_type=mime_type
    )


def video(
    data: Optional[bytes] = None,
    url: Optional[str] = None,
    path: Optional[Union[str, Path]] = None,
    mime_type: str = "video/mp4"
) -> ContentPart:
    """Create a video content part."""
    if path:
        return ContentPart.from_file(path, ContentType.VIDEO)
    return ContentPart(
        type=ContentType.VIDEO,
        data=data,
        url=url,
        mime_type=mime_type
    )
```

---

## Part 2: Provider Interface Changes

### 2.1 Base Provider Protocol

**File**: `src/praval/providers/base.py` (new file, ~80 lines)

```python
"""
Base provider protocol for Praval LLM providers.

Defines the interface that all providers must implement,
including multimodal capabilities.
"""

from typing import Protocol, List, Dict, Any, Optional, Union
from enum import Flag, auto

from ..core.content import ContentPart, MultimodalContent


class ProviderCapability(Flag):
    """Capabilities that a provider may support."""
    TEXT = auto()           # Basic text generation
    VISION = auto()         # Image understanding
    AUDIO_INPUT = auto()    # Speech-to-text
    AUDIO_OUTPUT = auto()   # Text-to-speech
    VIDEO = auto()          # Video frame analysis
    TOOLS = auto()          # Function/tool calling
    STREAMING = auto()      # Streaming responses


class BaseProvider(Protocol):
    """Protocol defining the provider interface."""

    @property
    def capabilities(self) -> ProviderCapability:
        """Return the capabilities this provider supports."""
        ...

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        output_modality: str = "text"
    ) -> Union[str, bytes]:
        """
        Generate a response from the model.

        Args:
            messages: Conversation history with multimodal content
            tools: Optional tools for function calling
            output_modality: Desired output format ("text", "audio")

        Returns:
            Generated response (string for text, bytes for audio)
        """
        ...

    def supports(self, capability: ProviderCapability) -> bool:
        """Check if provider supports a capability."""
        return capability in self.capabilities


def format_multimodal_message(
    role: str,
    content: MultimodalContent
) -> Dict[str, Any]:
    """
    Format a multimodal message for provider consumption.

    Args:
        role: Message role (user, assistant, system)
        content: Text string or list of ContentParts

    Returns:
        Formatted message dictionary
    """
    from ..core.content import normalize_content, ContentType

    parts = normalize_content(content)

    # If all text, return simple format
    if all(p.type == ContentType.TEXT for p in parts):
        text_content = " ".join(p.data for p in parts if p.data)
        return {"role": role, "content": text_content}

    # Otherwise, return multimodal format
    content_list = []
    for part in parts:
        if part.type == ContentType.TEXT:
            content_list.append({"type": "text", "text": part.data})
        elif part.type == ContentType.IMAGE:
            if part.url:
                content_list.append({
                    "type": "image_url",
                    "image_url": {"url": part.url}
                })
            else:
                content_list.append({
                    "type": "image_url",
                    "image_url": {"url": part.to_data_url()}
                })
        # Audio and video handled separately by providers

    return {"role": role, "content": content_list}
```

### 2.2 OpenAI Provider Updates

**File**: `src/praval/providers/openai.py` (modifications, ~200 lines added)

```python
# Add to existing OpenAIProvider class

from ..core.content import (
    ContentType, ContentPart, MultimodalContent,
    normalize_content
)
from .base import ProviderCapability, format_multimodal_message


class OpenAIProvider:
    """OpenAI provider with multimodal support."""

    # Model capabilities mapping
    VISION_MODELS = {"gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4-vision-preview"}
    AUDIO_MODELS = {"whisper-1", "tts-1", "tts-1-hd"}

    @property
    def capabilities(self) -> ProviderCapability:
        """OpenAI supports all modalities."""
        return (
            ProviderCapability.TEXT |
            ProviderCapability.VISION |
            ProviderCapability.AUDIO_INPUT |
            ProviderCapability.AUDIO_OUTPUT |
            ProviderCapability.TOOLS |
            ProviderCapability.STREAMING
        )

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        output_modality: str = "text"
    ) -> Union[str, bytes]:
        """
        Generate response with multimodal support.

        Handles:
        - Text generation (GPT models)
        - Vision/image analysis (GPT-4o, GPT-4V)
        - Audio transcription (Whisper)
        - Audio generation (TTS)
        """
        # Check for audio input - route to Whisper
        has_audio_input = self._has_audio_content(messages)
        if has_audio_input:
            return self._transcribe_audio(messages)

        # Check for audio output request
        if output_modality == "audio":
            text_response = self._generate_text(messages, tools)
            return self._generate_speech(text_response)

        # Standard text/vision generation
        return self._generate_text(messages, tools)

    def _has_audio_content(self, messages: List[Dict]) -> bool:
        """Check if messages contain audio content."""
        for msg in messages:
            content = msg.get("content", [])
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, ContentPart) and part.type == ContentType.AUDIO:
                        return True
        return False

    def _generate_text(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None
    ) -> str:
        """Generate text response (handles vision automatically)."""
        # Format messages for OpenAI API
        formatted_messages = []
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, (list, ContentPart)):
                formatted_messages.append(
                    format_multimodal_message(msg["role"], content)
                )
            else:
                formatted_messages.append(msg)

        # Select model based on content
        has_images = self._has_image_content(formatted_messages)
        model = "gpt-4o" if has_images else self.config.model or "gpt-4o-mini"

        call_params = {
            "model": model,
            "messages": formatted_messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens
        }

        if tools:
            call_params["tools"] = self._format_tools_for_openai(tools)
            call_params["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**call_params)

        if response.choices and response.choices[0].message:
            message = response.choices[0].message
            if hasattr(message, 'tool_calls') and message.tool_calls:
                return self._handle_tool_calls(message.tool_calls, tools, messages)
            return message.content or ""

        return ""

    def _has_image_content(self, messages: List[Dict]) -> bool:
        """Check if messages contain image content."""
        for msg in messages:
            content = msg.get("content", [])
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        return True
        return False

    def _transcribe_audio(self, messages: List[Dict]) -> str:
        """
        Transcribe audio content using Whisper.

        Extracts audio from messages and returns transcription.
        """
        # Extract audio content
        audio_data = None
        for msg in messages:
            content = msg.get("content", [])
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, ContentPart) and part.type == ContentType.AUDIO:
                        audio_data = part.data
                        break

        if not audio_data:
            raise ValueError("No audio content found in messages")

        # Create a temporary file for Whisper API
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name

        try:
            with open(temp_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            return transcript
        finally:
            os.unlink(temp_path)

    def _generate_speech(self, text: str, voice: str = "alloy") -> bytes:
        """
        Generate speech audio from text using TTS.

        Args:
            text: Text to convert to speech
            voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)

        Returns:
            Audio bytes in MP3 format
        """
        response = self.client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )
        return response.content
```

### 2.3 Anthropic Provider Updates

**File**: `src/praval/providers/anthropic.py` (modifications, ~100 lines added)

```python
# Add to existing AnthropicProvider class

class AnthropicProvider:
    """Anthropic provider with vision support."""

    # All Claude 3 models support vision
    VISION_MODELS = {
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022"
    }

    @property
    def capabilities(self) -> ProviderCapability:
        """Anthropic supports text and vision."""
        return (
            ProviderCapability.TEXT |
            ProviderCapability.VISION |
            ProviderCapability.TOOLS
        )

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        output_modality: str = "text"
    ) -> str:
        """Generate response with vision support."""
        if output_modality != "text":
            raise ValueError("Anthropic only supports text output")

        # Format messages for Anthropic API
        formatted_messages = self._format_messages(messages)

        # Extract system message if present
        system_message = None
        if formatted_messages and formatted_messages[0].get("role") == "system":
            system_message = formatted_messages[0]["content"]
            formatted_messages = formatted_messages[1:]

        call_params = {
            "model": self.config.model or "claude-3-5-sonnet-20241022",
            "max_tokens": self.config.max_tokens,
            "messages": formatted_messages
        }

        if system_message:
            call_params["system"] = system_message

        response = self.client.messages.create(**call_params)

        if response.content:
            return response.content[0].text
        return ""

    def _format_messages(self, messages: List[Dict]) -> List[Dict]:
        """Format messages with image support for Anthropic."""
        formatted = []

        for msg in messages:
            content = msg.get("content")

            if isinstance(content, str):
                formatted.append(msg)
                continue

            # Handle multimodal content
            parts = normalize_content(content) if not isinstance(content, list) else content
            anthropic_content = []

            for part in parts:
                if isinstance(part, ContentPart):
                    if part.type == ContentType.TEXT:
                        anthropic_content.append({
                            "type": "text",
                            "text": part.data
                        })
                    elif part.type == ContentType.IMAGE:
                        if part.url and not part.url.startswith("data:"):
                            # Anthropic requires base64, fetch URL content
                            anthropic_content.append({
                                "type": "image",
                                "source": {
                                    "type": "url",
                                    "url": part.url
                                }
                            })
                        else:
                            anthropic_content.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": part.mime_type,
                                    "data": part.to_base64()
                                }
                            })
                elif isinstance(part, dict):
                    anthropic_content.append(part)

            formatted.append({
                "role": msg["role"],
                "content": anthropic_content
            })

        return formatted
```

---

## Part 3: Agent API Updates

### 3.1 Enhanced chat() Function

**File**: `src/praval/decorators.py` (modifications, ~80 lines)

```python
from .core.content import (
    ContentType, ContentPart, MultimodalContent,
    normalize_content, text, image, audio, video
)


def chat(
    message: MultimodalContent,
    timeout: float = 30.0,
    output_modality: str = "text"
) -> Union[str, bytes]:
    """
    Multimodal chat function for use within @agent decorated functions.

    Supports text, images, audio, and video content. Automatically routes
    to appropriate model capabilities based on content type.

    Args:
        message: Content to send - can be:
            - str: Plain text message
            - ContentPart: Single content piece (text, image, audio, video)
            - List[ContentPart]: Multiple content pieces
        timeout: Maximum time to wait for response (default 30s for multimodal)
        output_modality: Desired output format:
            - "text": Return text response (default)
            - "audio": Return audio bytes (TTS)

    Returns:
        str for text output, bytes for audio output

    Raises:
        RuntimeError: If called outside of @agent context
        TimeoutError: If LLM call exceeds timeout
        ValueError: If unsupported modality combination

    Examples:
        # Text only (backward compatible)
        response = chat("What is machine learning?")

        # Image analysis
        response = chat([
            image(path="screenshot.png"),
            text("What's in this image?")
        ])

        # Audio transcription
        transcript = chat([
            audio(path="recording.wav"),
            text("Transcribe this audio")
        ])

        # Get audio response
        audio_bytes = chat(
            "Say hello in a friendly voice",
            output_modality="audio"
        )
    """
    current_agent = _get_current_agent()
    if current_agent is None:
        raise RuntimeError(
            "chat() can only be used within @agent decorated functions. "
            "For standalone usage, use Agent.chat() instead."
        )

    # Normalize content to list of ContentParts
    content_parts = normalize_content(message)

    # Build the message
    user_message = {"role": "user", "content": content_parts}

    # Get conversation history and append new message
    messages = current_agent.conversation_history.copy()
    messages.append(user_message)

    # Call provider with multimodal support
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            current_agent.provider.generate,
            messages,
            tools=list(current_agent.tools.values()) if current_agent.tools else None,
            output_modality=output_modality
        )
        try:
            result = future.result(timeout=timeout)

            # Update conversation history (text responses only)
            if output_modality == "text" and isinstance(result, str):
                current_agent.conversation_history.append(user_message)
                current_agent.conversation_history.append({
                    "role": "assistant",
                    "content": result
                })

            return result

        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"LLM call timed out after {timeout} seconds")
```

### 3.2 Export Updates

**File**: `src/praval/__init__.py` (additions)

```python
# Add multimodal content exports
from .core.content import (
    ContentType,
    ContentPart,
    MultimodalContent,
    text,
    image,
    audio,
    video,
    normalize_content
)

__all__ = [
    # ... existing exports ...

    # Multimodal content (v0.8.0+)
    "ContentType",
    "ContentPart",
    "MultimodalContent",
    "text",
    "image",
    "audio",
    "video",
    "normalize_content",
]
```

---

## Part 4: Spore Protocol Extensions

### 4.1 Binary Attachment Support

**File**: `src/praval/core/reef.py` (modifications, ~60 lines)

```python
@dataclass
class Spore:
    """
    Knowledge carrier in the Praval ecosystem.

    Extended in v0.8.0 to support binary attachments for multimodal content.
    """
    knowledge: Dict[str, Any]
    spore_type: SporeType = SporeType.KNOWLEDGE
    source_agent: Optional[str] = None
    target_channel: str = "main"
    timestamp: Optional[float] = None
    correlation_id: Optional[str] = None

    # Multimodal extensions (v0.8.0+)
    attachments: Optional[Dict[str, bytes]] = None
    attachment_metadata: Optional[Dict[str, Dict[str, Any]]] = None

    def add_attachment(
        self,
        name: str,
        data: bytes,
        mime_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a binary attachment to the spore.

        Args:
            name: Unique identifier for the attachment
            data: Binary content
            mime_type: MIME type of the content
            metadata: Optional additional metadata
        """
        if self.attachments is None:
            self.attachments = {}
        if self.attachment_metadata is None:
            self.attachment_metadata = {}

        self.attachments[name] = data
        self.attachment_metadata[name] = {
            "mime_type": mime_type,
            "size_bytes": len(data),
            **(metadata or {})
        }

    def get_attachment(self, name: str) -> Optional[bytes]:
        """Get an attachment by name."""
        if self.attachments:
            return self.attachments.get(name)
        return None

    def get_attachment_as_content_part(self, name: str) -> Optional[ContentPart]:
        """Get attachment as a ContentPart for multimodal processing."""
        from .content import ContentPart, ContentType

        data = self.get_attachment(name)
        if data is None:
            return None

        metadata = self.attachment_metadata.get(name, {}) if self.attachment_metadata else {}
        mime_type = metadata.get("mime_type", "application/octet-stream")

        # Determine content type from MIME
        if mime_type.startswith("image/"):
            content_type = ContentType.IMAGE
        elif mime_type.startswith("audio/"):
            content_type = ContentType.AUDIO
        elif mime_type.startswith("video/"):
            content_type = ContentType.VIDEO
        else:
            content_type = ContentType.TEXT

        return ContentPart(
            type=content_type,
            data=data,
            mime_type=mime_type,
            metadata=metadata
        )
```

### 4.2 AMQP Serialization Updates

**File**: `src/praval/core/transport.py` (modifications, ~40 lines)

```python
def serialize_spore(spore: Spore) -> bytes:
    """
    Serialize spore for AMQP transport.

    Handles binary attachments efficiently using msgpack.
    """
    import msgpack

    data = {
        "knowledge": spore.knowledge,
        "spore_type": spore.spore_type.value,
        "source_agent": spore.source_agent,
        "target_channel": spore.target_channel,
        "timestamp": spore.timestamp,
        "correlation_id": spore.correlation_id,
    }

    # Include attachments if present
    if spore.attachments:
        data["attachments"] = spore.attachments
        data["attachment_metadata"] = spore.attachment_metadata

    return msgpack.packb(data, use_bin_type=True)


def deserialize_spore(data: bytes) -> Spore:
    """Deserialize spore from AMQP transport."""
    import msgpack

    unpacked = msgpack.unpackb(data, raw=False)

    return Spore(
        knowledge=unpacked["knowledge"],
        spore_type=SporeType(unpacked["spore_type"]),
        source_agent=unpacked.get("source_agent"),
        target_channel=unpacked.get("target_channel", "main"),
        timestamp=unpacked.get("timestamp"),
        correlation_id=unpacked.get("correlation_id"),
        attachments=unpacked.get("attachments"),
        attachment_metadata=unpacked.get("attachment_metadata")
    )
```

---

## Part 5: Video Processing

### 5.1 Frame Extraction Utility

**File**: `src/praval/utils/video.py` (new file, ~100 lines)

```python
"""
Video processing utilities for Praval multimodal support.

Provides frame extraction for video analysis using vision models.
"""

from typing import List, Optional, Generator
from pathlib import Path
import io

from ..core.content import ContentPart, ContentType


def extract_frames(
    video_path: str,
    max_frames: int = 10,
    interval_seconds: Optional[float] = None
) -> List[ContentPart]:
    """
    Extract frames from a video file for vision model analysis.

    Args:
        video_path: Path to video file
        max_frames: Maximum number of frames to extract
        interval_seconds: Seconds between frames (auto-calculated if None)

    Returns:
        List of ContentPart objects containing frame images

    Requires:
        opencv-python (cv2) package
    """
    try:
        import cv2
    except ImportError:
        raise ImportError(
            "Video processing requires opencv-python. "
            "Install with: pip install praval[video]"
        )

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    # Calculate frame interval
    if interval_seconds is None:
        interval_seconds = duration / max_frames if max_frames > 0 else 1.0

    frame_interval = int(fps * interval_seconds)

    frames = []
    frame_count = 0

    while len(frames) < max_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count)
        ret, frame = cap.read()

        if not ret:
            break

        # Encode frame as JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        frame_bytes = buffer.tobytes()

        frames.append(ContentPart(
            type=ContentType.IMAGE,
            data=frame_bytes,
            mime_type="image/jpeg",
            metadata={
                "frame_number": frame_count,
                "timestamp_seconds": frame_count / fps if fps > 0 else 0,
                "source_video": video_path
            }
        ))

        frame_count += frame_interval

    cap.release()
    return frames


def analyze_video(
    video_path: str,
    prompt: str,
    max_frames: int = 5,
    agent_chat_fn=None
) -> str:
    """
    High-level function to analyze a video using vision models.

    Args:
        video_path: Path to video file
        prompt: Analysis prompt/question about the video
        max_frames: Number of frames to analyze
        agent_chat_fn: The chat function to use (defaults to praval.chat)

    Returns:
        Analysis result as string
    """
    from ..decorators import chat as default_chat
    from .content import text

    chat_fn = agent_chat_fn or default_chat

    frames = extract_frames(video_path, max_frames=max_frames)

    # Build multimodal message with frames and prompt
    content = frames + [text(f"Video analysis request: {prompt}")]

    return chat_fn(content)
```

---

## Part 6: Implementation Schedule

### Phase 1: Foundation (Week 1-2)

| Task | Files | Lines | Status |
|------|-------|-------|--------|
| Content type system | `core/content.py` | ~200 | Pending |
| Base provider protocol | `providers/base.py` | ~80 | Pending |
| Unit tests for content types | `tests/test_content.py` | ~150 | Pending |

### Phase 2: Provider Updates (Week 3-4)

| Task | Files | Lines | Status |
|------|-------|-------|--------|
| OpenAI multimodal | `providers/openai.py` | ~200 | Pending |
| Anthropic vision | `providers/anthropic.py` | ~100 | Pending |
| Provider tests | `tests/test_providers_multimodal.py` | ~200 | Pending |

### Phase 3: Agent Integration (Week 5-6)

| Task | Files | Lines | Status |
|------|-------|-------|--------|
| Enhanced chat() | `decorators.py` | ~80 | Pending |
| Spore attachments | `core/reef.py` | ~60 | Pending |
| AMQP serialization | `core/transport.py` | ~40 | Pending |
| Integration tests | `tests/test_multimodal_agents.py` | ~200 | Pending |

### Phase 4: Video & Polish (Week 7-8)

| Task | Files | Lines | Status |
|------|-------|-------|--------|
| Video utilities | `utils/video.py` | ~100 | Pending |
| Documentation | `docs/multimodal.md` | ~300 | Pending |
| Examples | `examples/multimodal_*.py` | ~200 | Pending |
| Release prep | Various | ~50 | Pending |

---

## Part 7: Dependencies

### Required Dependencies (Core)

```toml
# pyproject.toml additions
[project.optional-dependencies]
multimodal = [
    "Pillow>=10.0.0",      # Image processing
]

video = [
    "opencv-python>=4.8.0", # Video frame extraction
]
```

### Provider Requirements

| Provider | Package | Multimodal Support |
|----------|---------|-------------------|
| OpenAI | `openai>=1.0.0` | Vision, Whisper, TTS |
| Anthropic | `anthropic>=0.8.0` | Vision only |
| Cohere | `cohere>=4.0.0` | Text only |

---

## Part 8: Testing Strategy

### Unit Tests

```python
# tests/test_content.py
class TestContentPart:
    def test_text_content(self):
        part = ContentPart(type=ContentType.TEXT, data="Hello")
        assert part.type == ContentType.TEXT
        assert part.data == "Hello"

    def test_image_from_file(self):
        part = ContentPart.from_file("tests/fixtures/test_image.png")
        assert part.type == ContentType.IMAGE
        assert part.mime_type == "image/png"

    def test_to_base64(self):
        part = ContentPart(type=ContentType.IMAGE, data=b"\x89PNG...")
        b64 = part.to_base64()
        assert isinstance(b64, str)


# tests/test_providers_multimodal.py
class TestOpenAIMultimodal:
    @pytest.mark.integration
    def test_vision_analysis(self, openai_provider):
        messages = [{
            "role": "user",
            "content": [
                ContentPart(type=ContentType.IMAGE, data=test_image_bytes),
                ContentPart(type=ContentType.TEXT, data="Describe this image")
            ]
        }]
        response = openai_provider.generate(messages)
        assert isinstance(response, str)
        assert len(response) > 0

    @pytest.mark.integration
    def test_audio_transcription(self, openai_provider):
        messages = [{
            "role": "user",
            "content": [
                ContentPart(type=ContentType.AUDIO, data=test_audio_bytes)
            ]
        }]
        transcript = openai_provider.generate(messages)
        assert isinstance(transcript, str)
```

### Integration Tests

```python
# tests/test_multimodal_agents.py
class TestMultimodalAgents:
    def test_vision_agent(self):
        @agent("vision_analyst", responds_to=["image_analysis"])
        def vision_agent(spore):
            image_data = spore.get_attachment("image")
            response = chat([
                image(data=image_data),
                text("What's in this image?")
            ])
            return {"description": response}

        # Test with sample image
        ...

    def test_audio_transcription_agent(self):
        @agent("transcriber", responds_to=["audio_upload"])
        def transcriber(spore):
            audio_data = spore.get_attachment("audio")
            transcript = chat([
                audio(data=audio_data),
                text("Transcribe this audio")
            ])
            return {"transcript": transcript}

        # Test with sample audio
        ...
```

---

## Part 9: Example Applications

### 9.1 Image Analysis Pipeline

**File**: `examples/multimodal_vision_pipeline.py`

```python
"""
Example: Multi-agent image analysis pipeline.

Demonstrates vision capabilities with specialized agents
for different aspects of image analysis.
"""

from praval import agent, chat, broadcast, start_agents, get_reef
from praval import image, text

@agent("image_classifier", responds_to=["image_upload"])
def classifier(spore):
    """I classify images into categories."""
    img = spore.get_attachment_as_content_part("image")

    classification = chat([
        img,
        text("Classify this image. Return: category, confidence, key_objects")
    ])

    broadcast({
        "type": "classification_complete",
        "classification": classification,
        "image_id": spore.knowledge.get("image_id")
    })

@agent("detail_analyzer", responds_to=["classification_complete"])
def analyzer(spore):
    """I provide detailed analysis based on classification."""
    category = spore.knowledge.get("classification")

    analysis = chat(f"Provide detailed analysis for {category}")

    broadcast({
        "type": "analysis_complete",
        "analysis": analysis
    })

@agent("report_generator", responds_to=["analysis_complete"])
def reporter(spore):
    """I generate the final report."""
    analysis = spore.knowledge.get("analysis")

    report = chat(f"Generate a structured report: {analysis}")
    print(f"📄 Final Report:\n{report}")

if __name__ == "__main__":
    # Load test image
    with open("test_image.jpg", "rb") as f:
        image_bytes = f.read()

    # Create initial spore with image attachment
    from praval.core.reef import Spore

    initial_spore = Spore(
        knowledge={"type": "image_upload", "image_id": "test_001"}
    )
    initial_spore.add_attachment("image", image_bytes, "image/jpeg")

    start_agents(classifier, analyzer, reporter, initial_spore=initial_spore)
    get_reef().wait_for_completion()
    get_reef().shutdown()
```

### 9.2 Voice-Enabled Agent

**File**: `examples/multimodal_voice_agent.py`

```python
"""
Example: Voice-enabled conversational agent.

Accepts audio input, processes with text agents,
returns audio output.
"""

from praval import agent, chat, broadcast, start_agents, get_reef
from praval import audio, text

@agent("voice_input", responds_to=["voice_message"])
def voice_input_handler(spore):
    """I transcribe voice input."""
    audio_data = spore.get_attachment_as_content_part("audio")

    # Transcribe using Whisper
    transcript = chat([audio_data])

    broadcast({
        "type": "text_query",
        "transcript": transcript,
        "user_id": spore.knowledge.get("user_id")
    })

@agent("assistant", responds_to=["text_query"])
def assistant(spore):
    """I answer questions."""
    query = spore.knowledge.get("transcript")

    response = chat(f"User asked: {query}")

    broadcast({
        "type": "response_ready",
        "response": response
    })

@agent("voice_output", responds_to=["response_ready"])
def voice_output_handler(spore):
    """I generate voice response."""
    response_text = spore.knowledge.get("response")

    # Generate speech
    audio_response = chat(response_text, output_modality="audio")

    # Save or stream audio
    with open("response.mp3", "wb") as f:
        f.write(audio_response)

    print("🔊 Voice response saved to response.mp3")

if __name__ == "__main__":
    # Example with audio file
    with open("question.wav", "rb") as f:
        audio_bytes = f.read()

    from praval.core.reef import Spore

    initial_spore = Spore(
        knowledge={"type": "voice_message", "user_id": "user_001"}
    )
    initial_spore.add_attachment("audio", audio_bytes, "audio/wav")

    start_agents(voice_input_handler, assistant, voice_output_handler,
                 initial_spore=initial_spore)
    get_reef().wait_for_completion()
    get_reef().shutdown()
```

---

## Part 10: Success Criteria

### Functional Requirements

| Requirement | Metric | Target |
|-------------|--------|--------|
| Image analysis | Works with PNG, JPEG, WebP, GIF | 100% |
| Audio transcription | Whisper integration | Working |
| Text-to-speech | TTS generation | Working |
| Video frames | Extract and analyze | Working |
| Backward compatibility | Existing tests pass | 100% |

### Performance Requirements

| Metric | Target |
|--------|--------|
| Image processing latency | < 5s for standard images |
| Audio transcription | < 10s for 1 minute audio |
| TTS generation | < 3s for 100 words |
| Memory overhead | < 100MB for typical use |

### Quality Requirements

| Metric | Target |
|--------|--------|
| Test coverage | > 80% |
| Documentation | Complete API docs |
| Examples | 3+ working examples |

---

## Part 11: Risk Analysis

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Provider API changes | Medium | High | Abstract behind interface, version pin |
| Large file handling | Medium | Medium | Streaming, chunking, size limits |
| Binary serialization | Low | Medium | Use proven msgpack library |
| Memory usage | Medium | Medium | Lazy loading, cleanup handlers |

### Compatibility Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking existing agents | Low | High | Extensive backward compat testing |
| Python version issues | Low | Low | Test on 3.9, 3.10, 3.11, 3.12 |
| Provider availability | Low | Medium | Graceful degradation |

---

## Appendix A: API Quick Reference

```python
# Content creation helpers
from praval import text, image, audio, video, ContentPart, ContentType

# Text (backward compatible)
chat("Hello")

# Image analysis
chat([image(path="photo.jpg"), text("Describe this")])
chat([image(url="https://..."), text("What's in this image?")])
chat([image(data=bytes_data, mime_type="image/png"), text("Analyze")])

# Audio transcription
chat([audio(path="recording.wav")])

# Audio output
audio_bytes = chat("Say hello", output_modality="audio")

# Video analysis
from praval.utils.video import extract_frames, analyze_video
frames = extract_frames("video.mp4", max_frames=5)
result = analyze_video("video.mp4", "Summarize this video")

# Spore attachments
spore.add_attachment("image", image_bytes, "image/png")
img = spore.get_attachment_as_content_part("image")
```

---

## Appendix B: Provider Capability Matrix

| Capability | OpenAI | Anthropic | Cohere |
|------------|--------|-----------|--------|
| Text generation | gpt-4o, gpt-4o-mini | claude-3-* | command-* |
| Vision/Images | gpt-4o, gpt-4-vision | claude-3-* (all) | ❌ |
| Audio input | whisper-1 | ❌ | ❌ |
| Audio output | tts-1, tts-1-hd | ❌ | ❌ |
| Video | Via frame extraction | Via frame extraction | ❌ |
| Tools | ✅ | ✅ | ✅ |
| Streaming | ✅ | ✅ | ✅ |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-12-29 | Claude Code | Initial draft |

---

## Next Steps

1. **Review**: Get stakeholder feedback on this plan
2. **Prioritize**: Decide Phase 1 vs full implementation
3. **Branch**: Create `feature/multimodal-support` branch
4. **Implement**: Follow the schedule in Part 6
5. **Test**: Validate against success criteria
6. **Release**: Include in v0.8.0
