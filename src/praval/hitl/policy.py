"""Policy helpers for HITL approval gating."""

from typing import Any, Dict


def requires_approval(tool_definition: Dict[str, Any], default: bool = False) -> bool:
    """Determine whether a tool call requires human approval."""
    if not tool_definition:
        return default
    return bool(tool_definition.get("requires_approval", default))


def risk_level(tool_definition: Dict[str, Any]) -> str:
    """Return normalized risk level from a tool definition."""
    if not tool_definition:
        return "low"
    value = str(tool_definition.get("risk_level", "low") or "low").strip().lower()
    if value not in {"low", "medium", "high", "critical"}:
        return "low"
    return value


def approval_reason(tool_definition: Dict[str, Any]) -> str:
    """Return operator-facing reason for approval requests."""
    if not tool_definition:
        return ""
    return str(tool_definition.get("approval_reason", "") or "")
