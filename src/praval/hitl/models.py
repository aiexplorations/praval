"""HITL domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class InterventionStatus(Enum):
    """Lifecycle status for a human intervention request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class InterventionDecision(Enum):
    """Human decisions supported for a blocked tool call."""

    APPROVE = "APPROVE"
    EDIT = "EDIT"
    REJECT = "REJECT"


@dataclass
class InterventionPolicy:
    """Simple policy controls for approval gating."""

    enabled: bool = False
    default_requires_approval: bool = False


@dataclass
class InterventionRequest:
    """Persistent representation of a pending/decided intervention."""

    id: str
    run_id: str
    agent_name: str
    provider_name: str
    tool_name: str
    tool_call_id: str
    status: InterventionStatus
    decision: Optional[InterventionDecision] = None
    reason: str = ""
    reviewer: str = ""
    original_args: Dict[str, Any] = field(default_factory=dict)
    edited_args: Optional[Dict[str, Any]] = None
    risk_level: str = "low"
    approval_reason: str = ""
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert intervention request to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "agent_name": self.agent_name,
            "provider_name": self.provider_name,
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "status": self.status.value,
            "decision": self.decision.value if self.decision else None,
            "reason": self.reason,
            "reviewer": self.reviewer,
            "original_args": self.original_args,
            "edited_args": self.edited_args,
            "risk_level": self.risk_level,
            "approval_reason": self.approval_reason,
            "requested_at": self.requested_at.isoformat(),
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "trace_id": self.trace_id,
            "metadata": self.metadata,
        }


@dataclass
class SuspendedRunState:
    """Durable continuation state for interrupted runs."""

    run_id: str
    agent_name: str
    provider_name: str
    status: str
    state: Dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert suspended run state to a JSON-safe dictionary."""
        return {
            "run_id": self.run_id,
            "agent_name": self.agent_name,
            "provider_name": self.provider_name,
            "status": self.status,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
