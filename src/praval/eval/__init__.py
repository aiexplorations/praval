"""Provider-neutral evaluation contracts and persistence."""

from .models import (
    AttemptStatus,
    EvalCase,
    EvalSuite,
    EvaluationAttempt,
    EvaluationBaseline,
    EvaluationJob,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
    EvaluationSubject,
    Gate,
    GateAggregation,
    GateOperator,
    GateResult,
    GateStatus,
    JobStatus,
    JudgeResult,
    MetricResult,
    ResultStatus,
)
from .postgres import PostgresEvaluationStore
from .sqlite import SQLiteEvaluationStore
from .store import (
    EvaluationConflictError,
    EvaluationStore,
    EvaluationStoreError,
)

__all__ = [
    "AttemptStatus",
    "EvalCase",
    "EvalSuite",
    "EvaluationAttempt",
    "EvaluationBaseline",
    "EvaluationConflictError",
    "EvaluationJob",
    "EvaluationResult",
    "EvaluationRun",
    "EvaluationRunStatus",
    "EvaluationStore",
    "EvaluationStoreError",
    "EvaluationSubject",
    "Gate",
    "GateAggregation",
    "GateOperator",
    "GateResult",
    "GateStatus",
    "JobStatus",
    "JudgeResult",
    "MetricResult",
    "PostgresEvaluationStore",
    "ResultStatus",
    "SQLiteEvaluationStore",
]
