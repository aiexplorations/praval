"""Provider-neutral, schema-versioned evaluation contracts."""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from praval.models import (
    ContentReference,
    ExecutionObservation,
    ObservationKind,
    ObservationPrivacy,
    TokenUsageObservation,
)


def _stable_id(prefix: str, *parts: str) -> str:
    """Build a compact deterministic identifier from a natural record key."""
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


class _EvaluationModel(BaseModel):
    """Immutable base shared by persisted evaluation records."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class EvaluationRunStatus(str, Enum):
    """Lifecycle of an evaluation suite run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResultStatus(str, Enum):
    """Outcome shared by metric and judge results."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class GateStatus(str, Enum):
    """Outcome of applying one quality gate."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class JobStatus(str, Enum):
    """Durable evaluation job lifecycle."""

    PENDING = "pending"
    LEASED = "leased"
    AWAITING_INTERVENTION = "awaiting_intervention"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class AttemptStatus(str, Enum):
    """Outcome of one evaluation job attempt."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class GateAggregation(str, Enum):
    """Supported aggregation for a quality gate."""

    MEAN = "mean"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    PERCENTILE = "percentile"
    COUNT = "count"
    PASS_RATE = "pass_rate"


class GateOperator(str, Enum):
    """Comparison applied to an aggregate gate value."""

    GREATER_THAN_OR_EQUAL = ">="
    GREATER_THAN = ">"
    LESS_THAN_OR_EQUAL = "<="
    LESS_THAN = "<"
    EQUAL = "=="


class EvaluationMetadata(_EvaluationModel):
    """One bounded, query-safe scalar attached to an evaluation case."""

    key: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    value: str | int | float | bool | None

    @field_validator("value")
    @classmethod
    def require_finite_value(
        cls, value: str | int | float | bool | None
    ) -> str | int | float | bool | None:
        """Reject non-finite floats that cannot round-trip through strict JSON."""
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("metadata floats must be finite")
        return value


class EvalCase(_EvaluationModel):
    """One versioned case whose content is represented by safe references."""

    schema_version: Literal[1] = 1
    case_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=512)
    input: ContentReference
    expected_output: ContentReference | None = None
    reference_contexts: tuple[ContentReference, ...] = Field(
        default_factory=tuple, max_length=128
    )
    expected_tool_calls: tuple[str, ...] = Field(default_factory=tuple, max_length=128)
    metadata: tuple[EvaluationMetadata, ...] = Field(
        default_factory=tuple, max_length=64
    )
    tags: tuple[str, ...] = Field(default_factory=tuple, max_length=64)

    @field_validator("expected_tool_calls", "tags")
    @classmethod
    def validate_bounded_names(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Reject blank, oversized, or duplicate names."""
        if any(not value.strip() or len(value) > 256 for value in values):
            raise ValueError("values must contain non-empty names up to 256 characters")
        if len(set(values)) != len(values):
            raise ValueError("values must not contain duplicates")
        return values

    @field_validator("metadata")
    @classmethod
    def validate_metadata_keys(
        cls, values: tuple[EvaluationMetadata, ...]
    ) -> tuple[EvaluationMetadata, ...]:
        """Reject duplicate metadata keys."""
        keys = [item.key for item in values]
        if len(keys) != len(set(keys)):
            raise ValueError("metadata keys must not contain duplicates")
        return values


class Gate(_EvaluationModel):
    """Declarative threshold over one aggregated metric."""

    schema_version: Literal[1] = 1
    gate_id: str = Field(min_length=1, max_length=256)
    metric: str = Field(min_length=1, max_length=256)
    aggregation: GateAggregation
    operator: GateOperator
    threshold: float
    required: bool = True
    percentile: float | None = Field(default=None, gt=0, le=100)

    @model_validator(mode="after")
    def validate_percentile(self) -> "Gate":
        """Require a percentile only for percentile aggregation."""
        if (self.aggregation is GateAggregation.PERCENTILE) != (
            self.percentile is not None
        ):
            raise ValueError(
                "percentile must be supplied only for percentile aggregation"
            )
        return self


class EvalSuite(_EvaluationModel):
    """Stable selection of cases, target, judges, metrics, and gates."""

    schema_version: Literal[1] = 1
    suite_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=512)
    target: str = Field(min_length=1, max_length=512)
    case_ids: tuple[str, ...] = Field(min_length=1, max_length=100_000)
    judges: tuple[str, ...] = Field(default_factory=tuple, max_length=128)
    metrics: tuple[str, ...] = Field(default_factory=tuple, max_length=128)
    gates: tuple[Gate, ...] = Field(default_factory=tuple, max_length=128)
    tags: tuple[str, ...] = Field(default_factory=tuple, max_length=64)

    @field_validator("case_ids", "judges", "metrics", "tags")
    @classmethod
    def validate_unique_names(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Keep suite selectors stable and unambiguous."""
        if any(not value.strip() or len(value) > 512 for value in values):
            raise ValueError("suite values must be non-empty and bounded")
        if len(set(values)) != len(values):
            raise ValueError("suite values must not contain duplicates")
        return values

    @model_validator(mode="after")
    def validate_gate_ids(self) -> "EvalSuite":
        """Reject duplicate gate identities within a suite."""
        ids = [gate.gate_id for gate in self.gates]
        if len(ids) != len(set(ids)):
            raise ValueError("gate_id values must be unique within a suite")
        return self


class EvaluationRun(_EvaluationModel):
    """Lifecycle record for one execution of an evaluation suite."""

    schema_version: Literal[1] = 1
    evaluation_run_id: str = Field(min_length=1, max_length=256)
    suite_id: str = Field(min_length=1, max_length=256)
    target: str = Field(min_length=1, max_length=512)
    status: EvaluationRunStatus
    started_at: datetime
    completed_at: datetime | None = None
    baseline_id: str | None = Field(default=None, min_length=1, max_length=256)
    error_type: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("started_at", "completed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        """Require timezone-aware timestamps and normalize them to UTC."""
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluation timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "EvaluationRun":
        """Keep terminal state, timing, and error fields consistent."""
        terminal = {
            EvaluationRunStatus.COMPLETED,
            EvaluationRunStatus.FAILED,
            EvaluationRunStatus.CANCELLED,
        }
        if self.status in terminal and self.completed_at is None:
            raise ValueError("completed runs require completed_at")
        if self.status not in terminal and self.completed_at is not None:
            raise ValueError("non-terminal runs cannot have completed_at")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be earlier than started_at")
        if self.status is EvaluationRunStatus.FAILED and self.error_type is None:
            raise ValueError("failed runs require error_type")
        if (
            self.status is not EvaluationRunStatus.FAILED
            and self.error_type is not None
        ):
            raise ValueError("error_type is only valid for failed runs")
        return self


class EvaluationSubject(_EvaluationModel):
    """Exactly one agent or workflow observation selected for evaluation."""

    schema_version: Literal[1] = 1
    subject_id: str = Field(min_length=1, max_length=256)
    evaluation_run_id: str = Field(min_length=1, max_length=256)
    case_id: str = Field(min_length=1, max_length=256)
    observation_id: str = Field(min_length=1, max_length=256)
    execution_run_id: str = Field(min_length=1, max_length=256)
    kind: ObservationKind
    response_id: str | None = Field(default=None, min_length=1, max_length=256)
    observation: ExecutionObservation

    @classmethod
    def from_observation(
        cls,
        *,
        evaluation_run_id: str,
        case_id: str,
        observation: ExecutionObservation,
    ) -> "EvaluationSubject":
        """Map one frozen runtime observation into one evaluation subject."""
        return cls(
            subject_id=_stable_id(
                "subject",
                evaluation_run_id,
                case_id,
                observation.observation_id,
            ),
            evaluation_run_id=evaluation_run_id,
            case_id=case_id,
            observation_id=observation.observation_id,
            execution_run_id=observation.run_id,
            kind=observation.kind,
            response_id=observation.response_id,
            observation=observation,
        )

    @model_validator(mode="after")
    def validate_observation_identity(self) -> "EvaluationSubject":
        """Prevent duplicated query fields from drifting from the payload."""
        if self.observation_id != self.observation.observation_id:
            raise ValueError("observation_id must match observation")
        if self.execution_run_id != self.observation.run_id:
            raise ValueError("execution_run_id must match observation")
        if self.kind is not self.observation.kind:
            raise ValueError("kind must match observation")
        if self.response_id != self.observation.response_id:
            raise ValueError("response_id must match observation")
        return self


class MetricResult(_EvaluationModel):
    """Normalized result from one deterministic or plugin metric."""

    schema_version: Literal[1] = 1
    metric_result_id: str = Field(min_length=1, max_length=256)
    evaluation_run_id: str = Field(min_length=1, max_length=256)
    case_id: str = Field(min_length=1, max_length=256)
    subject_id: str = Field(min_length=1, max_length=256)
    metric: str = Field(min_length=1, max_length=256)
    metric_version: str = Field(min_length=1, max_length=128)
    status: ResultStatus
    score: float | None = None
    label: str | None = Field(default=None, min_length=1, max_length=128)
    error_type: str | None = Field(default=None, min_length=1, max_length=256)
    created_at: datetime

    @classmethod
    def create(cls, **values: Any) -> "MetricResult":
        """Create a result with its natural idempotency identity."""
        values["metric_result_id"] = _stable_id(
            "metric",
            values["evaluation_run_id"],
            values["case_id"],
            values["subject_id"],
            values["metric"],
            values["metric_version"],
        )
        return cls(**values)

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        """Require a timezone-aware creation time."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_result(self) -> "MetricResult":
        """Keep scores and errors consistent with the result status."""
        if self.status is ResultStatus.ERROR and self.error_type is None:
            raise ValueError("errored metric results require error_type")
        if self.status is not ResultStatus.ERROR and self.error_type is not None:
            raise ValueError("error_type is only valid for errored metric results")
        if self.status in {ResultStatus.PASSED, ResultStatus.FAILED} and (
            self.score is None
        ):
            raise ValueError("passed and failed metric results require a score")
        return self


class JudgeResult(_EvaluationModel):
    """Validated result from one versioned evaluator agent or model."""

    schema_version: Literal[1] = 1
    judge_result_id: str = Field(min_length=1, max_length=256)
    evaluation_run_id: str = Field(min_length=1, max_length=256)
    case_id: str = Field(min_length=1, max_length=256)
    subject_id: str = Field(min_length=1, max_length=256)
    judge: str = Field(min_length=1, max_length=256)
    judge_version: str = Field(min_length=1, max_length=128)
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rubric_version: str = Field(min_length=1, max_length=128)
    status: ResultStatus
    score: float | None = None
    label: str | None = Field(default=None, min_length=1, max_length=128)
    explanation: str | None = Field(default=None, max_length=8192)
    evidence: tuple[ContentReference, ...] = Field(default_factory=tuple, max_length=64)
    privacy: ObservationPrivacy = Field(default_factory=ObservationPrivacy)
    model: str | None = Field(default=None, min_length=1, max_length=512)
    usage: TokenUsageObservation | None = None
    cost_usd: float | None = Field(default=None, ge=0)
    duration_ms: float | None = Field(default=None, ge=0)
    attempt_count: int = Field(default=1, ge=1, le=100)
    error_type: str | None = Field(default=None, min_length=1, max_length=256)
    created_at: datetime

    @classmethod
    def create(cls, **values: Any) -> "JudgeResult":
        """Create a judge result with its natural idempotency identity."""
        values["judge_result_id"] = _stable_id(
            "judge",
            values["evaluation_run_id"],
            values["case_id"],
            values["subject_id"],
            values["judge"],
            values["judge_version"],
            values["prompt_sha256"],
            values["rubric_version"],
        )
        return cls(**values)

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        """Require a timezone-aware creation time."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_result(self) -> "JudgeResult":
        """Enforce result status and metadata-only privacy defaults."""
        if self.status is ResultStatus.ERROR and self.error_type is None:
            raise ValueError("errored judge results require error_type")
        if self.status is not ResultStatus.ERROR and self.error_type is not None:
            raise ValueError("error_type is only valid for errored judge results")
        if self.status in {ResultStatus.PASSED, ResultStatus.FAILED} and (
            self.score is None or self.label is None
        ):
            raise ValueError("passed and failed judge results require score and label")
        if self.explanation is not None and not self.privacy.content_captured:
            raise ValueError("explanation requires explicit content capture")
        return self


class GateResult(_EvaluationModel):
    """Persisted decision from applying a gate to an aggregate."""

    schema_version: Literal[1] = 1
    gate_result_id: str = Field(min_length=1, max_length=256)
    evaluation_run_id: str = Field(min_length=1, max_length=256)
    gate_id: str = Field(min_length=1, max_length=256)
    metric: str = Field(min_length=1, max_length=256)
    status: GateStatus
    observed_value: float | None = None
    threshold: float
    error_type: str | None = Field(default=None, min_length=1, max_length=256)
    created_at: datetime

    @classmethod
    def create(cls, **values: Any) -> "GateResult":
        """Create one idempotent gate decision per run and gate."""
        values["gate_result_id"] = _stable_id(
            "gate", values["evaluation_run_id"], values["gate_id"]
        )
        return cls(**values)

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        """Require a timezone-aware creation time."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_result(self) -> "GateResult":
        """Keep gate errors separate from measured decisions."""
        if self.status is GateStatus.ERROR:
            if self.error_type is None:
                raise ValueError("errored gate results require error_type")
        elif self.error_type is not None:
            raise ValueError("error_type is only valid for errored gate results")
        if self.status is not GateStatus.ERROR and self.observed_value is None:
            raise ValueError("passed and failed gates require observed_value")
        return self


class EvaluationResult(_EvaluationModel):
    """Immutable summary of a completed evaluation run."""

    schema_version: Literal[1] = 1
    evaluation_run_id: str = Field(min_length=1, max_length=256)
    status: Literal[
        EvaluationRunStatus.COMPLETED,
        EvaluationRunStatus.FAILED,
        EvaluationRunStatus.CANCELLED,
    ]
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    errored_cases: int = Field(default=0, ge=0)
    skipped_cases: int = Field(default=0, ge=0)
    metric_result_ids: tuple[str, ...] = Field(default_factory=tuple)
    judge_result_ids: tuple[str, ...] = Field(default_factory=tuple)
    gate_result_ids: tuple[str, ...] = Field(default_factory=tuple)
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def normalize_completed_at(cls, value: datetime) -> datetime:
        """Require a timezone-aware completion time."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("completed_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_case_totals(self) -> "EvaluationResult":
        """Require the terminal case counts to add up."""
        counted = (
            self.passed_cases
            + self.failed_cases
            + self.errored_cases
            + self.skipped_cases
        )
        if counted != self.total_cases:
            raise ValueError("case outcome counts must equal total_cases")
        return self


class EvaluationBaseline(_EvaluationModel):
    """Explicit promotion of one completed run as a suite baseline."""

    schema_version: Literal[1] = 1
    baseline_id: str = Field(min_length=1, max_length=256)
    suite_id: str = Field(min_length=1, max_length=256)
    source_evaluation_run_id: str = Field(min_length=1, max_length=256)
    promoted_at: datetime
    promoted_by: str = Field(min_length=1, max_length=256)
    active: bool = True

    @classmethod
    def create(cls, **values: Any) -> "EvaluationBaseline":
        """Create an idempotent promotion identity for a suite and run."""
        values["baseline_id"] = _stable_id(
            "baseline", values["suite_id"], values["source_evaluation_run_id"]
        )
        return cls(**values)

    @field_validator("promoted_at")
    @classmethod
    def normalize_promoted_at(cls, value: datetime) -> datetime:
        """Require a timezone-aware promotion time."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("promoted_at must be timezone-aware")
        return value.astimezone(timezone.utc)


class EvaluationJob(_EvaluationModel):
    """Durable unit of deferred evaluation work."""

    schema_version: Literal[1] = 1
    job_id: str = Field(min_length=1, max_length=256)
    evaluation_run_id: str = Field(min_length=1, max_length=256)
    suite_id: str = Field(min_length=1, max_length=256)
    case_id: str = Field(min_length=1, max_length=256)
    subject_id: str = Field(min_length=1, max_length=256)
    status: JobStatus
    available_at: datetime
    lease_owner: str | None = Field(default=None, min_length=1, max_length=256)
    lease_expires_at: datetime | None = None
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1, le=3)
    error_type: str | None = Field(default=None, min_length=1, max_length=256)
    created_at: datetime
    updated_at: datetime

    @field_validator("available_at", "lease_expires_at", "created_at", "updated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        """Require timezone-aware job timestamps."""
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("job timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "EvaluationJob":
        """Keep leasing, attempts, timing, and terminal errors consistent."""
        if (self.lease_owner is None) != (self.lease_expires_at is None):
            raise ValueError(
                "lease_owner and lease_expires_at must be supplied together"
            )
        if self.status is JobStatus.LEASED and self.lease_owner is None:
            raise ValueError("leased jobs require an active lease")
        if self.status is not JobStatus.LEASED and self.lease_owner is not None:
            raise ValueError("only leased jobs may have an active lease")
        if self.attempt_count > self.max_attempts:
            raise ValueError("attempt_count cannot exceed max_attempts")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        if self.status in {JobStatus.FAILED, JobStatus.DEAD_LETTER}:
            if self.error_type is None:
                raise ValueError("failed jobs require error_type")
        elif self.error_type is not None:
            raise ValueError("error_type is only valid for failed jobs")
        return self


class EvaluationAttempt(_EvaluationModel):
    """One bounded attempt to process an evaluation job."""

    schema_version: Literal[1] = 1
    attempt_id: str = Field(min_length=1, max_length=256)
    job_id: str = Field(min_length=1, max_length=256)
    attempt_number: int = Field(ge=1, le=3)
    status: AttemptStatus
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    usage: TokenUsageObservation | None = None
    cost_usd: float | None = Field(default=None, ge=0)
    error_type: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("started_at", "ended_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        """Require timezone-aware attempt timestamps."""
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("attempt timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "EvaluationAttempt":
        """Keep attempt status, timing, and errors consistent."""
        terminal = {
            AttemptStatus.SUCCEEDED,
            AttemptStatus.FAILED,
            AttemptStatus.TIMEOUT,
            AttemptStatus.CANCELLED,
        }
        if self.status in terminal and self.ended_at is None:
            raise ValueError("finished attempts require ended_at")
        if self.status is AttemptStatus.RUNNING and self.ended_at is not None:
            raise ValueError("running attempts cannot have ended_at")
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at cannot be earlier than started_at")
        if (self.duration_ms is None) != (self.ended_at is None):
            raise ValueError("duration_ms and ended_at must be supplied together")
        if self.status in {AttemptStatus.FAILED, AttemptStatus.TIMEOUT}:
            if self.error_type is None:
                raise ValueError("failed attempts require error_type")
        elif self.error_type is not None:
            raise ValueError("error_type is only valid for failed attempts")
        return self


__all__ = [
    "AttemptStatus",
    "EvalCase",
    "EvalSuite",
    "EvaluationAttempt",
    "EvaluationBaseline",
    "EvaluationJob",
    "EvaluationMetadata",
    "EvaluationResult",
    "EvaluationRun",
    "EvaluationRunStatus",
    "EvaluationSubject",
    "Gate",
    "GateAggregation",
    "GateOperator",
    "GateResult",
    "GateStatus",
    "JobStatus",
    "JudgeResult",
    "MetricResult",
    "ResultStatus",
]
