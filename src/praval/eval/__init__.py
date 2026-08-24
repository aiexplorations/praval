"""Provider-neutral evaluation contracts, datasets, and persistence."""

from .dataset import (
    EvalDatasetError,
    LoadedEvalCase,
    LoadedEvalSuite,
    load_jsonl_suite,
)
from .models import (
    AttemptStatus,
    EvalCase,
    EvalSuite,
    EvaluationAttempt,
    EvaluationBaseline,
    EvaluationJob,
    EvaluationMetadata,
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
    "EvalDatasetError",
    "EvalCase",
    "EvalSuite",
    "EvaluationAttempt",
    "EvaluationBaseline",
    "EvaluationConflictError",
    "EvaluationJob",
    "EvaluationMetadata",
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
    "LoadedEvalCase",
    "LoadedEvalSuite",
    "MetricResult",
    "PostgresEvaluationStore",
    "ResultStatus",
    "SQLiteEvaluationStore",
    "load_jsonl_suite",
]
