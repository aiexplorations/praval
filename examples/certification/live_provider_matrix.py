"""Certify the stable provider-neutral runtime against real provider APIs."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from support import (
    live_entrypoint,
    report_dir,
    require_environment,
    write_json_artifact,
)

from praval import Agent, ContentPart, EmbeddingRuntime, ToolSpec

MODEL_VARIABLES = {
    "openai": "PRAVAL_OPENAI_MODEL",
    "anthropic": "PRAVAL_ANTHROPIC_MODEL",
    "cohere": "PRAVAL_COHERE_MODEL",
    "gemini": "PRAVAL_GEMINI_MODEL",
    "openai-compatible": "PRAVAL_OPENAI_COMPATIBLE_MODEL",
}

ASSETS = Path(__file__).with_name("assets")


def committed_fixture(
    name: str, expected_sha256: str, *, compressed: bool = False
) -> bytes:
    """Decode and hash a committed binary fixture before sending it to a provider."""
    encoded = base64.b64decode((ASSETS / name).read_text(encoding="ascii"))
    value = gzip.decompress(encoded) if compressed else encoded
    assert hashlib.sha256(value).hexdigest() == expected_sha256
    return value


def agent_for(provider: str, name: str) -> Agent:
    """Create a bounded live agent from protected environment configuration."""
    model_name = require_environment(MODEL_VARIABLES[provider])[
        MODEL_VARIABLES[provider]
    ]
    kwargs: Dict[str, Any] = {
        "provider": provider,
        "model": model_name,
        "config": {
            "temperature": 0,
            "max_output_tokens": 128,
            "timeout": 60,
            "retries": 0,
        },
    }
    if provider == "openai-compatible":
        values = require_environment(
            "OPENAI_COMPATIBLE_BASE_URL", "OPENAI_COMPATIBLE_API_KEY"
        )
        kwargs["config"]["base_url"] = values["OPENAI_COMPATIBLE_BASE_URL"]
        kwargs["config"]["api_key_env"] = "OPENAI_COMPATIBLE_API_KEY"
    return Agent(f"live-{provider}-{name}", **kwargs)


def assert_response(response: Any, provider: str, capability: str) -> Dict[str, Any]:
    """Assert a structurally valid neutral response and return safe evidence."""
    assert response.provider == provider
    assert response.model
    assert isinstance(response.content, str) and response.content.strip()
    evidence: Dict[str, Any] = {
        "capability": capability,
        "model": response.model,
        "content_chars": len(response.content),
    }
    if response.usage is not None:
        assert response.usage.total_tokens >= 0
        evidence["usage"] = response.usage.model_dump()
    return evidence


def certify_text(provider: str) -> Dict[str, Any]:
    """Exercise real sync invocation for one provider."""
    with agent_for(provider, "text") as agent:
        response = agent.generate(
            "Reply with a short sentence containing the word Praval."
        )
    return assert_response(response, provider, "text")


def certify_stream(provider: str) -> Dict[str, Any]:
    """Require actual provider streaming deltas and a final response."""
    with agent_for(provider, "stream") as agent:
        events = list(agent.stream("Stream a short sentence about coral reefs."))
    deltas = [event.delta for event in events if event.type == "delta" and event.delta]
    finals = [event.response for event in events if event.type == "final"]
    assert deltas
    assert finals and finals[-1] is not None
    assert "".join(deltas).strip()
    return {
        "capability": "streaming",
        "model": finals[-1].model,
        "delta_count": len(deltas),
        "event_types": [event.type for event in events],
    }


def certify_tool(provider: str) -> Dict[str, Any]:
    """Require a model-generated tool call and real handler execution."""
    executions: List[Tuple[int, int]] = []

    def certification_add(a: int, b: int) -> int:
        executions.append((a, b))
        return a + b

    spec = ToolSpec(
        name="certification_add",
        description="Add two integers. Use this whenever the user requests addition.",
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
        strict=True,
    )
    with agent_for(provider, "tool") as agent:
        agent.add_tool_spec(spec, certification_add)
        response = agent.generate(
            "You must call certification_add with a=2 and b=3. Do not add them "
            "yourself; use the tool."
        )
    assert executions == [(2, 3)]
    assert response.tool_calls
    results = response.metadata.get("tool_results") or []
    assert results and str(results[0]["content"]) == "5"
    evidence = assert_response(response, provider, "tools")
    evidence["tool_calls"] = len(response.tool_calls)
    evidence["executed_result"] = 5
    return evidence


def certify_structured(provider: str) -> Dict[str, Any]:
    """Require output that validates against the requested JSON schema."""
    schema = {
        "type": "object",
        "properties": {
            "framework": {"type": "string"},
            "ready": {"type": "boolean"},
        },
        "required": ["framework", "ready"],
        "additionalProperties": False,
    }
    with agent_for(provider, "structured") as agent:
        response = agent.generate(
            "Return framework Praval with ready set to true.", response_schema=schema
        )
    payload = json.loads(response.content)
    assert isinstance(payload["framework"], str)
    assert payload["ready"] is True
    evidence = assert_response(response, provider, "structured_outputs")
    evidence["schema_valid"] = True
    return evidence


def certify_reasoning(provider: str) -> Dict[str, Any]:
    """Exercise stable reasoning controls without inspecting private reasoning."""
    reasoning = (
        {"budget_tokens": 256, "mode": "enabled"}
        if provider == "gemini"
        else {"effort": "low"}
    )
    with agent_for(provider, "reasoning") as agent:
        response = agent.generate(
            "Which is larger, 17 times 6 or 19 times 5? Answer briefly.",
            reasoning=reasoning,
        )
    return assert_response(response, provider, "reasoning")


def certify_multimodal() -> Dict[str, Any]:
    """Exercise real image and Gemini file/audio/video content serialization."""
    image_bytes = committed_fixture(
        "image_input.png.base64",
        "f6a996480096b673a0b79ff45d7d2c95e3962ce3c4a5d4a3a5532736beede47d",
    )
    image_path = report_dir() / "provider-matrix-red.png"
    image_path.write_bytes(image_bytes)
    image_data = base64.b64encode(image_bytes).decode("ascii")
    image_message = [
        ContentPart.text_part("Name the dominant color in this image."),
        ContentPart.image_base64(image_data, "image/png"),
    ]
    evidence: Dict[str, Any] = {}
    for provider in ("openai", "anthropic", "gemini"):
        with agent_for(provider, "image") as agent:
            response = agent.generate(image_message)
        item = assert_response(response, provider, "image_input")
        assert "red" in response.content.lower()
        evidence[provider] = item

    gemini_parts = [
        ContentPart.text_part(
            "A text file, an audio clip, and a one-frame animation follow. "
            "Reply with the three words: file audio video."
        ),
        ContentPart.file_data(
            base64.b64encode(b"Praval certification file").decode("ascii"),
            "text/plain",
            name="certification.txt",
        ),
        ContentPart.audio_base64(
            base64.b64encode(
                committed_fixture(
                    "voice_input.wav.gz.base64",
                    "041f5f356daec0d916580e31cc7913ba4837fc29a5fb3a0b2a3e8f5ac926648b",
                    compressed=True,
                )
            ).decode("ascii"),
            "audio/wav",
        ),
        ContentPart.video_base64(
            base64.b64encode(
                committed_fixture(
                    "video_input.mp4.base64",
                    "4c8f057507d062995d5ec00431f00f9157425e9b7de506f1405456e397170873",
                )
            ).decode("ascii"),
            "video/mp4",
        ),
    ]
    with agent_for("gemini", "mixed-media") as agent:
        response = agent.generate(gemini_parts)
    lower = response.content.lower()
    assert all(word in lower for word in ("file", "audio", "video"))
    evidence["gemini_mixed_media"] = assert_response(
        response, "gemini", "file_audio_video_input"
    )
    return evidence


def certify_embeddings() -> Dict[str, Any]:
    """Execute real OpenAI, Gemini, and declared compatible embeddings."""
    values = require_environment(
        "PRAVAL_OPENAI_EMBEDDING_MODEL", "PRAVAL_GEMINI_EMBEDDING_MODEL"
    )
    evidence: Dict[str, Any] = {}
    for provider, model in (
        ("openai", values["PRAVAL_OPENAI_EMBEDDING_MODEL"]),
        ("gemini", values["PRAVAL_GEMINI_EMBEDDING_MODEL"]),
    ):
        response = EmbeddingRuntime(provider=provider, model=model).embed(
            ["Praval coral agents", "Reef coordination"]
        )
        assert len(response.embeddings) == 2
        assert response.dimensions and response.dimensions > 0
        evidence[provider] = {
            "model": response.model,
            "dimensions": response.dimensions,
            "vectors": len(response.embeddings),
        }

    compatible_enabled = os.getenv(
        "PRAVAL_OPENAI_COMPATIBLE_EMBEDDINGS", "false"
    ).lower() in {"1", "true", "yes"}
    evidence["openai_compatible_declared"] = compatible_enabled
    if compatible_enabled:
        compatible = require_environment(
            "PRAVAL_OPENAI_COMPATIBLE_EMBEDDING_MODEL",
            "OPENAI_COMPATIBLE_BASE_URL",
            "OPENAI_COMPATIBLE_API_KEY",
        )
        response = EmbeddingRuntime(
            provider="openai-compatible",
            model=compatible["PRAVAL_OPENAI_COMPATIBLE_EMBEDDING_MODEL"],
            provider_options={
                "base_url": compatible["OPENAI_COMPATIBLE_BASE_URL"],
                "api_key": compatible["OPENAI_COMPATIBLE_API_KEY"],
                "send_dimensions": False,
            },
        ).embed("Praval compatible embeddings")
        assert response.embeddings and response.embeddings[0]
        evidence["openai-compatible"] = {
            "model": response.model,
            "dimensions": response.dimensions,
            "vectors": len(response.embeddings),
        }
    return evidence


async def certify_async_provider_path() -> Dict[str, Any]:
    """Exercise real async invocation through the common runtime."""
    with agent_for("openai", "async") as agent:
        response = await agent.agenerate("Reply with exactly: async ready")
        events = [
            event async for event in agent.astream("Stream exactly: async stream ready")
        ]
    assert response.content.strip()
    assert any(event.type == "delta" and event.delta for event in events)
    assert events[-1].type == "final"
    return {
        "agenerate": True,
        "astream": True,
        "model": response.model,
        "event_types": [event.type for event in events],
    }


async def main() -> None:
    """Run the required live provider capability matrix."""
    require_environment(
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "COHERE_API_KEY",
        "GEMINI_API_KEY",
        "OPENAI_COMPATIBLE_BASE_URL",
        "OPENAI_COMPATIBLE_API_KEY",
        *MODEL_VARIABLES.values(),
    )
    evidence: Dict[str, Any] = {
        "text": {provider: certify_text(provider) for provider in MODEL_VARIABLES},
        "streaming": {
            provider: certify_stream(provider)
            for provider in ("openai", "anthropic", "gemini", "openai-compatible")
        },
        "tools": {
            provider: certify_tool(provider)
            for provider in ("openai", "anthropic", "cohere", "gemini")
        },
        "structured_outputs": {
            provider: certify_structured(provider)
            for provider in ("openai", "anthropic", "gemini")
        },
        "reasoning": {
            provider: certify_reasoning(provider)
            for provider in ("openai", "anthropic", "gemini")
        },
        "multimodal": certify_multimodal(),
        "embeddings": certify_embeddings(),
        "async_runtime": await certify_async_provider_path(),
    }
    write_json_artifact("live-provider-matrix.json", evidence)
    print("CERTIFIED: real provider capability matrix")


if __name__ == "__main__":
    live_entrypoint(main)
