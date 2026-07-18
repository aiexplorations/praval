"""Shared helpers for executable Praval certification demos."""

from __future__ import annotations

import json
import os
import struct
import sys
import traceback
import wave
import zlib
from pathlib import Path
from typing import Any, Dict, Iterator, List

from praval.models import (
    ModelEvent,
    ModelResponse,
    ProviderCapabilities,
    ToolCall,
    ToolResult,
    Usage,
)


class CertificationProvider:
    """Deterministic provider used only for offline framework certification."""

    provider_name = "certification-fake"
    capabilities = ProviderCapabilities(
        text=True,
        tools=True,
        streaming=True,
        native_streaming=True,
        structured_outputs=True,
        reasoning=True,
        reasoning_effort=True,
        multimodal=True,
        image_input=True,
        embeddings=True,
    )

    def __init__(self, config: Any) -> None:
        self.config = config
        self.closed = False

    def invoke(self, request: Any, tools: Any = None) -> ModelResponse:
        """Return structured text or a real runtime-owned tool call."""
        if request.tools:
            spec = request.tools[0]
            properties = spec.parameters.get("properties", {})
            arguments: Dict[str, Any] = {}
            for name, schema in properties.items():
                json_type = schema.get("type") if isinstance(schema, dict) else None
                arguments[name] = 2 if json_type in {"integer", "number"} else "praval"
            return ModelResponse(
                provider=self.provider_name,
                model=request.model,
                tool_calls=[
                    ToolCall(
                        id="certification-tool-call",
                        name=spec.name,
                        arguments=arguments,
                    )
                ],
                usage=Usage(input_tokens=4, output_tokens=2, total_tokens=6),
            )
        content = (
            json.dumps({"summary": "runtime contracts are explicit"})
            if request.response_schema
            else "Praval certification response"
        )
        return ModelResponse(
            content=content,
            provider=self.provider_name,
            model=request.model,
            usage=Usage(input_tokens=4, output_tokens=3, total_tokens=7),
        )

    def continue_with_tool_results(
        self, request: Any, response: ModelResponse, results: List[ToolResult]
    ) -> ModelResponse:
        """Finish a provider-neutral tool round using the actual result."""
        if not results or results[0].is_error:
            raise AssertionError("certification tool did not execute successfully")
        return ModelResponse(
            content=f"tool-result:{results[0].content}",
            provider=self.provider_name,
            model=request.model,
            usage=Usage(input_tokens=6, output_tokens=3, total_tokens=9),
        )

    def stream(self, request: Any, tools: Any = None) -> Iterator[ModelEvent]:
        """Emit native normalized streaming events."""
        yield ModelEvent(type="delta", delta="Praval ")
        yield ModelEvent(type="delta", delta="streams")
        response = ModelResponse(
            content="Praval streams",
            provider=self.provider_name,
            model=request.model,
            usage=Usage(input_tokens=2, output_tokens=2, total_tokens=4),
        )
        yield ModelEvent(type="usage", usage=response.usage)
        yield ModelEvent(type="final", response=response, usage=response.usage)

    def close(self) -> None:
        """Record deterministic lifecycle cleanup."""
        self.closed = True


def report_dir() -> Path:
    """Return the runner-owned artifact directory."""
    value = os.environ.get("PRAVAL_DEMO_REPORT_DIR")
    if not value:
        raise RuntimeError("PRAVAL_DEMO_REPORT_DIR is required")
    path = Path(value)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json_artifact(name: str, payload: Dict[str, Any]) -> Path:
    """Write stable, non-secret certification evidence."""
    path = report_dir() / name
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def write_red_png(path: Path, width: int = 32, height: int = 32) -> None:
    """Write a deterministic red PNG without image-library dependencies."""
    raw = b"".join(b"\x00" + (b"\xff\x00\x00" * width) for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    contents = b"\x89PNG\r\n\x1a\n"
    contents += chunk(
        "IHDR".encode(), struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    )
    contents += chunk(b"IDAT", zlib.compress(raw, 9))
    contents += chunk(b"IEND", b"")
    path.write_bytes(contents)


def write_minimal_pdf(path: Path, text: str) -> None:
    """Write a deterministic one-page PDF containing extractable text."""
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 50 740 Td ({escaped}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    contents = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(contents))
        contents.extend(f"{index} 0 obj\n".encode("ascii"))
        contents.extend(obj)
        contents.extend(b"\nendobj\n")
    xref = len(contents)
    contents.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    contents.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        contents.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    contents.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(bytes(contents))


def require_environment(*names: str) -> Dict[str, str]:
    """Return required live configuration or raise a configuration error."""
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise ValueError("Missing live configuration: " + ", ".join(missing))
    return {name: os.environ[name] for name in names}


def sanitized_exception(exc: BaseException) -> str:
    """Return an exception message with every configured credential redacted."""
    message = f"{type(exc).__name__}: {exc}"
    for name, value in os.environ.items():
        upper = name.upper()
        if value and (
            name == "OPENAI_COMPATIBLE_BASE_URL"
            or any(
                marker in upper
                for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH")
            )
        ):
            message = message.replace(value, "***")
    return message


def live_entrypoint(function: Any) -> None:
    """Run a live certificate with standardized exit and retry semantics."""
    try:
        result = function()
        if hasattr(result, "__await__"):
            import asyncio

            asyncio.run(result)
    except ValueError as exc:
        print(sanitized_exception(exc), file=sys.stderr)
        raise SystemExit(2) from None
    except AssertionError as exc:
        print(sanitized_exception(exc), file=sys.stderr)
        raise SystemExit(3) from None
    except Exception as exc:
        message = sanitized_exception(exc)
        print(message, file=sys.stderr)
        lower = message.lower()
        transient = any(
            marker in lower
            for marker in (
                "429",
                "502",
                "503",
                "504",
                "connection reset",
                "rate limit",
                "temporarily unavailable",
                "timed out",
                "timeout",
            )
        )
        if os.environ.get("PRAVAL_DEMO_DEBUG") == "1":
            traceback.print_exc()
        raise SystemExit(75 if transient else 1) from None


def validate_wav(data: bytes) -> Dict[str, Any]:
    """Validate a nonempty PCM WAV and return safe media metadata."""
    import io

    with wave.open(io.BytesIO(data), "rb") as handle:
        declared_frames = handle.getnframes()
        rate = handle.getframerate()
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        payload = handle.readframes(declared_frames)
    frame_size = channels * width
    frames = len(payload) // frame_size if frame_size > 0 else 0
    if frames <= 0 or rate <= 0 or channels <= 0 or width <= 0:
        raise AssertionError("WAV contains no decodable audio frames")
    if len(payload) % frame_size:
        raise AssertionError("WAV contains an incomplete PCM frame")
    if not payload or all(byte == 0 for byte in payload):
        raise AssertionError("WAV contains only silence")
    return {
        "frames": frames,
        "sample_rate": rate,
        "channels": channels,
        "sample_width": width,
        "duration_seconds": round(frames / rate, 3),
    }
