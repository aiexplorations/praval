"""Shared metadata-first sanitization for exported telemetry values."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_SENSITIVE_KEY = re.compile(
    r"(?i)(?:authorization|cookie|api[_-]?key|access[_-]?token|password|secret|"
    r"private[_-]?key|credential)"
)
_SENSITIVE_VALUE = re.compile(
    r"(?i)(?:bearer\s+\S+|sk-[a-z0-9_-]{8,}|api[_-]?key\s*[=:]\s*\S+|"
    r"password\s*[=:]\s*\S+|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)
_CONTENT_KEYS = {
    "db.statement",
    "error.description",
    "gen_ai.completion",
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "gen_ai.prompt",
    "input.value",
    "messaging.message.body",
    "output.value",
    "tool.arguments",
    "tool.result",
}
_CONTENT_SUFFIXES = (
    ".arguments",
    ".completion",
    ".content",
    ".documents",
    ".evidence",
    ".prompt",
    ".response",
    ".result",
)


class TelemetrySanitizer:
    """Apply deterministic redaction, content policy, and size bounds."""

    def __init__(
        self,
        *,
        capture_content: bool = False,
        content_allowlist: Sequence[str] = (),
        max_attribute_bytes: int = 4096,
        max_collection_items: int = 128,
    ) -> None:
        self.capture_content = capture_content
        self.content_allowlist = frozenset(content_allowlist)
        self.max_attribute_bytes = max(1, max_attribute_bytes)
        self.max_collection_items = max(1, max_collection_items)

    def sanitize_attributes(
        self, attributes: Mapping[str, Any] | None
    ) -> dict[str, Any]:
        """Return JSON-safe, bounded attributes under the active policy."""
        if not attributes:
            return {}
        sanitized: dict[str, Any] = {}
        for raw_key, value in list(attributes.items())[: self.max_collection_items]:
            key = self._truncate(str(raw_key), 256)
            if self._is_content_key(key) and not (
                self.capture_content and key in self.content_allowlist
            ):
                continue
            if _SENSITIVE_KEY.search(key):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = self.sanitize_value(value)
        return sanitized

    def sanitize_value(self, value: Any) -> Any:
        """Normalize one telemetry value without retaining arbitrary objects."""
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            if _SENSITIVE_VALUE.search(value):
                return "[REDACTED]"
            return self._truncate(value, self.max_attribute_bytes)
        if isinstance(value, bytes):
            return {"type": "bytes", "size_bytes": len(value)}
        if isinstance(value, Mapping):
            return self.sanitize_attributes(value)
        if isinstance(value, Sequence):
            return [
                self.sanitize_value(item)
                for item in list(value)[: self.max_collection_items]
            ]
        return self._truncate(type(value).__name__, self.max_attribute_bytes)

    @staticmethod
    def _is_content_key(key: str) -> bool:
        lowered = key.lower()
        return lowered in _CONTENT_KEYS or lowered.endswith(_CONTENT_SUFFIXES)

    @staticmethod
    def _truncate(value: str, max_bytes: int) -> str:
        encoded = value.encode("utf-8")
        if len(encoded) <= max_bytes:
            return value
        return encoded[:max_bytes].decode("utf-8", errors="ignore")


__all__ = ["TelemetrySanitizer"]
