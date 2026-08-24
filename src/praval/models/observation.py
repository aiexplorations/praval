"""Provider-neutral execution observation contracts.

The models in this module are shared by runtime instrumentation,
``praval.observability``, and ``praval.eval``.  They intentionally do not import
OpenTelemetry or evaluation plugins.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _ObservationModel(BaseModel):
    """Immutable base for the versioned observation schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ObservationKind(str, Enum):
    """Execution boundary represented by an observation."""

    AGENT = "agent"
    WORKFLOW = "workflow"


class ObservationStatus(str, Enum):
    """Terminal status of an observed execution."""

    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ObservationFactStatus(str, Enum):
    """Status shared by bounded child facts such as tools and handoffs."""

    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    REJECTED = "rejected"


class ContentKind(str, Enum):
    """Sensitive content category represented by a safe reference."""

    PROMPT = "prompt"
    RESPONSE = "response"
    CONTEXT = "context"
    TOOL_ARGUMENTS = "tool_arguments"
    TOOL_RESULT = "tool_result"
    RETRIEVED_DOCUMENT = "retrieved_document"
    MEDIA = "media"
    JUDGE_EVIDENCE = "judge_evidence"
    OTHER = "other"


class PrivacyMode(str, Enum):
    """Content handling policy applied before an observation is recorded."""

    METADATA_ONLY = "metadata_only"
    REDACTED = "redacted"
    FULL = "full"


class TokenUsageObservation(_ObservationModel):
    """Bounded provider-neutral model token usage."""

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_total(self) -> "TokenUsageObservation":
        """Reject totals smaller than the directly billed token classes."""
        minimum_total = self.input_tokens + self.output_tokens
        if self.total_tokens < minimum_total:
            raise ValueError("total_tokens cannot be less than input plus output")
        return self


class ToolCallObservation(_ObservationModel):
    """Metadata-only facts about one tool invocation."""

    tool_call_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=256)
    status: ObservationFactStatus
    duration_ms: float = Field(ge=0)
    error_type: str | None = Field(default=None, max_length=256)


class RetryObservation(_ObservationModel):
    """One bounded retry decision made during execution."""

    attempt: int = Field(ge=1, le=1000)
    operation: str = Field(min_length=1, max_length=256)
    reason_type: str | None = Field(default=None, max_length=256)
    backoff_ms: float = Field(default=0, ge=0)


class HITLDecisionObservation(_ObservationModel):
    """Metadata-only human-in-the-loop decision."""

    decision_id: str = Field(min_length=1, max_length=256)
    decision: Literal[
        "requested", "approved", "rejected", "edited", "timeout", "cancelled"
    ]
    tool_name: str | None = Field(default=None, max_length=256)
    reviewer_type: str | None = Field(default=None, max_length=128)


class ReefHandoffObservation(_ObservationModel):
    """Metadata-only facts about one Reef handoff."""

    handoff_id: str = Field(min_length=1, max_length=256)
    source_agent_id: str | None = Field(default=None, max_length=256)
    target_agent_id: str = Field(min_length=1, max_length=256)
    spore_id: str | None = Field(default=None, max_length=256)
    channel: str | None = Field(default=None, max_length=256)
    status: ObservationFactStatus
    duration_ms: float | None = Field(default=None, ge=0)
    error_type: str | None = Field(default=None, max_length=256)


class ContentReference(_ObservationModel):
    """Safe identity for content that is not embedded in an observation."""

    kind: ContentKind
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    reference: str | None = Field(default=None, max_length=2048)
    media_type: str | None = Field(default=None, max_length=256)


class ObservationPrivacy(_ObservationModel):
    """Privacy policy applied to all content facts in an observation."""

    mode: PrivacyMode = PrivacyMode.METADATA_ONLY
    content_captured: bool = False
    redaction_applied: bool = False
    byte_limit: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_capture_policy(self) -> "ObservationPrivacy":
        """Keep metadata-only observations free from captured content."""
        if self.mode is PrivacyMode.METADATA_ONLY and self.content_captured:
            raise ValueError("metadata_only privacy cannot capture content")
        if self.content_captured and self.byte_limit == 0:
            raise ValueError("captured content requires a positive byte_limit")
        return self


class ExecutionObservation(_ObservationModel):
    """Versioned facts for one completed agent invocation or workflow.

    The schema contains identities and bounded metadata only. Raw prompts,
    responses, tool payloads, retrieved documents, media, and judge evidence
    are represented through :class:`ContentReference` values.
    """

    schema_version: Literal[1] = 1
    observation_id: str = Field(min_length=1, max_length=256)
    run_id: str = Field(min_length=1, max_length=256)
    kind: ObservationKind
    conversation_id: str | None = Field(default=None, min_length=1, max_length=256)
    response_id: str | None = Field(default=None, min_length=1, max_length=256)
    agent_id: str | None = Field(default=None, min_length=1, max_length=256)
    agent_name: str | None = Field(default=None, min_length=1, max_length=256)
    workflow_id: str | None = Field(default=None, min_length=1, max_length=256)
    workflow_name: str | None = Field(default=None, min_length=1, max_length=256)

    started_at: datetime
    ended_at: datetime
    duration_ms: float = Field(ge=0)
    status: ObservationStatus
    error_type: str | None = Field(default=None, min_length=1, max_length=256)
    terminal_outcome: str | None = Field(default=None, min_length=1, max_length=256)

    provider: str | None = Field(default=None, min_length=1, max_length=256)
    model: str | None = Field(default=None, min_length=1, max_length=512)
    request_mode: str | None = Field(default=None, min_length=1, max_length=128)
    usage: TokenUsageObservation | None = None

    tool_calls: tuple[ToolCallObservation, ...] = Field(
        default_factory=tuple, max_length=128
    )
    retries: tuple[RetryObservation, ...] = Field(default_factory=tuple, max_length=32)
    hitl_decisions: tuple[HITLDecisionObservation, ...] = Field(
        default_factory=tuple, max_length=32
    )
    handoffs: tuple[ReefHandoffObservation, ...] = Field(
        default_factory=tuple, max_length=128
    )
    content_references: tuple[ContentReference, ...] = Field(
        default_factory=tuple, max_length=128
    )
    privacy: ObservationPrivacy = Field(default_factory=ObservationPrivacy)

    trace_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    span_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")

    @field_validator("started_at", "ended_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        """Require timezone-aware timestamps and normalize them to UTC."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observation timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_contract(self) -> "ExecutionObservation":
        """Validate cross-field identity, timing, error, and trace invariants."""
        if self.ended_at < self.started_at:
            raise ValueError("ended_at cannot be earlier than started_at")
        if self.kind is ObservationKind.AGENT and not (
            self.agent_id or self.agent_name
        ):
            raise ValueError("agent observations require agent_id or agent_name")
        if self.kind is ObservationKind.WORKFLOW and not (
            self.workflow_id or self.workflow_name
        ):
            raise ValueError(
                "workflow observations require workflow_id or workflow_name"
            )
        if (self.trace_id is None) != (self.span_id is None):
            raise ValueError("trace_id and span_id must be supplied together")
        if self.status is ObservationStatus.ERROR and not self.error_type:
            raise ValueError("error observations require error_type")
        if self.status is ObservationStatus.OK and self.error_type:
            raise ValueError("error_type is only valid for non-ok observations")
        return self


@runtime_checkable
class ObservationRecorder(Protocol):
    """Structural interface for consumers of completed observations."""

    def record(self, observation: ExecutionObservation) -> None:
        """Record one completed execution observation."""
        ...


class NoOpObservationRecorder:
    """Default recorder used when no observation consumer is configured."""

    __slots__ = ()

    def record(self, observation: ExecutionObservation) -> None:
        """Discard an observation without side effects."""


NOOP_OBSERVATION_RECORDER = NoOpObservationRecorder()


__all__ = [
    "ContentKind",
    "ContentReference",
    "ExecutionObservation",
    "HITLDecisionObservation",
    "NOOP_OBSERVATION_RECORDER",
    "NoOpObservationRecorder",
    "ObservationFactStatus",
    "ObservationKind",
    "ObservationPrivacy",
    "ObservationRecorder",
    "ObservationStatus",
    "PrivacyMode",
    "ReefHandoffObservation",
    "RetryObservation",
    "TokenUsageObservation",
    "ToolCallObservation",
]
