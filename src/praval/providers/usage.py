"""Normalize provider-reported chat usage without estimating missing values."""

from __future__ import annotations

from typing import Any, Optional

from ..models import Usage


def _value(obj: Any, name: str, default: Any = None) -> Any:
    value = (
        obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)
    )
    return default if type(value).__module__.startswith("unittest.mock") else value


def _count(obj: Any, name: str) -> int:
    value = _value(obj, name, 0)
    return max(0, int(value)) if isinstance(value, (int, float)) else 0


def openai_usage(response: Any) -> Optional[Usage]:
    """Chat Completions/Responses counts include cache and reasoning subsets."""
    usage = _value(response, "usage")
    if usage is None:
        return None
    inputs = _count(usage, "input_tokens") or _count(usage, "prompt_tokens")
    outputs = _count(usage, "output_tokens") or _count(usage, "completion_tokens")
    input_details = _value(usage, "input_tokens_details") or _value(
        usage, "prompt_tokens_details"
    )
    output_details = _value(usage, "output_tokens_details") or _value(
        usage, "completion_tokens_details"
    )
    return Usage(
        input_tokens=inputs,
        output_tokens=outputs,
        total_tokens=max(_count(usage, "total_tokens"), inputs + outputs),
        reasoning_tokens=_count(output_details, "reasoning_tokens"),
        cache_read_tokens=_count(input_details, "cached_tokens"),
        cache_write_tokens=_count(input_details, "cache_write_tokens"),
    )


def anthropic_usage(response: Any) -> Optional[Usage]:
    """Anthropic reports cache reads/writes outside ordinary input tokens."""
    usage = _value(response, "usage")
    if usage is None:
        return None
    reads, writes = _count(usage, "cache_read_input_tokens"), _count(
        usage, "cache_creation_input_tokens"
    )
    inputs = _count(usage, "input_tokens") + reads + writes
    outputs = _count(usage, "output_tokens")
    return Usage(
        input_tokens=inputs,
        output_tokens=outputs,
        total_tokens=inputs + outputs,
        cache_read_tokens=reads,
        cache_write_tokens=writes,
    )


def gemini_usage(response: Any) -> Optional[Usage]:
    """Gemini candidate text and thought counts are separate output counts."""
    usage = _value(response, "usageMetadata")
    if usage is None:
        return None
    inputs, thoughts = _count(usage, "promptTokenCount"), _count(
        usage, "thoughtsTokenCount"
    )
    outputs = _count(usage, "candidatesTokenCount") + thoughts
    return Usage(
        input_tokens=inputs,
        output_tokens=outputs,
        total_tokens=max(_count(usage, "totalTokenCount"), inputs + outputs),
        reasoning_tokens=thoughts,
        cache_read_tokens=_count(usage, "cachedContentTokenCount"),
    )


def cohere_usage(response: Any) -> Optional[Usage]:
    """Use billed units from Cohere v1 meta or v2 usage, not raw token counts."""
    container = _value(response, "usage") or _value(response, "meta")
    units = _value(container, "billed_units")
    if units is None or (
        not isinstance(units, dict)
        and type(units).__module__.startswith("unittest.mock")
    ):
        return None
    if _value(units, "input_tokens") is None and _value(units, "output_tokens") is None:
        return None
    inputs, outputs = _count(units, "input_tokens"), _count(units, "output_tokens")
    return Usage(
        input_tokens=inputs, output_tokens=outputs, total_tokens=inputs + outputs
    )
