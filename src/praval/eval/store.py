"""Async persistence contract shared by evaluation stores."""

from __future__ import annotations

from typing import Protocol

from .models import (
    EvalCase,
    EvalSuite,
    EvaluationAttempt,
    EvaluationBaseline,
    EvaluationJob,
    EvaluationResult,
    EvaluationRun,
    EvaluationSubject,
    GateResult,
    JobStatus,
    JudgeResult,
    MetricResult,
)


class EvaluationStoreError(RuntimeError):
    """Base error raised by an evaluation store."""


class EvaluationConflictError(EvaluationStoreError):
    """A natural idempotency key was reused with different data."""


class EvaluationStore(Protocol):
    """Common asynchronous persistence and query contract for evaluation."""

    async def migrate(self) -> None:
        """Apply all pending schema migrations idempotently."""
        ...

    async def schema_version(self) -> int:
        """Return the latest applied schema version."""
        ...

    async def close(self) -> None:
        """Release store-owned resources."""
        ...

    async def put_case(self, case: EvalCase) -> EvalCase:
        """Persist an immutable case idempotently."""
        ...

    async def get_case(self, case_id: str) -> EvalCase | None:
        """Load one case by identity."""
        ...

    async def list_cases(self, *, limit: int = 100) -> list[EvalCase]:
        """List cases in stable identity order."""
        ...

    async def put_suite(self, suite: EvalSuite) -> EvalSuite:
        """Persist an immutable suite idempotently."""
        ...

    async def get_suite(self, suite_id: str) -> EvalSuite | None:
        """Load one suite by identity."""
        ...

    async def put_run(self, run: EvaluationRun) -> EvaluationRun:
        """Create or update a run lifecycle record."""
        ...

    async def get_run(self, evaluation_run_id: str) -> EvaluationRun | None:
        """Load one evaluation run."""
        ...

    async def list_runs(
        self, *, suite_id: str | None = None, limit: int = 100
    ) -> list[EvaluationRun]:
        """List recent runs, optionally restricted to a suite."""
        ...

    async def put_subject(self, subject: EvaluationSubject) -> EvaluationSubject:
        """Persist one immutable agent or workflow subject."""
        ...

    async def get_subject(self, subject_id: str) -> EvaluationSubject | None:
        """Load one subject."""
        ...

    async def list_subjects(
        self, *, evaluation_run_id: str, limit: int = 100
    ) -> list[EvaluationSubject]:
        """List subjects belonging to a run."""
        ...

    async def put_metric_result(self, result: MetricResult) -> MetricResult:
        """Persist one immutable, idempotent metric result."""
        ...

    async def list_metric_results(
        self,
        *,
        evaluation_run_id: str,
        metric: str | None = None,
        limit: int = 1000,
    ) -> list[MetricResult]:
        """List metric results for a run."""
        ...

    async def put_judge_result(self, result: JudgeResult) -> JudgeResult:
        """Persist one immutable, idempotent judge result."""
        ...

    async def list_judge_results(
        self, *, evaluation_run_id: str, limit: int = 1000
    ) -> list[JudgeResult]:
        """List judge results for a run."""
        ...

    async def put_gate_result(self, result: GateResult) -> GateResult:
        """Persist one immutable, idempotent gate result."""
        ...

    async def list_gate_results(
        self, *, evaluation_run_id: str, limit: int = 1000
    ) -> list[GateResult]:
        """List gate decisions for a run."""
        ...

    async def put_evaluation_result(self, result: EvaluationResult) -> EvaluationResult:
        """Persist one immutable terminal run summary."""
        ...

    async def get_evaluation_result(
        self, evaluation_run_id: str
    ) -> EvaluationResult | None:
        """Load a terminal run summary."""
        ...

    async def promote_baseline(
        self, baseline: EvaluationBaseline
    ) -> EvaluationBaseline:
        """Atomically make an explicit baseline active for its suite."""
        ...

    async def get_active_baseline(self, suite_id: str) -> EvaluationBaseline | None:
        """Load the active baseline for a suite."""
        ...

    async def list_baselines(
        self, *, suite_id: str, limit: int = 100
    ) -> list[EvaluationBaseline]:
        """List baseline promotion history for a suite."""
        ...

    async def put_job(self, job: EvaluationJob) -> EvaluationJob:
        """Create or update a durable evaluation job."""
        ...

    async def get_job(self, job_id: str) -> EvaluationJob | None:
        """Load one job."""
        ...

    async def list_jobs(
        self, *, status: JobStatus | None = None, limit: int = 100
    ) -> list[EvaluationJob]:
        """List jobs, optionally filtered by status."""
        ...

    async def put_attempt(self, attempt: EvaluationAttempt) -> EvaluationAttempt:
        """Persist one immutable job attempt."""
        ...

    async def list_attempts(
        self, *, job_id: str, limit: int = 100
    ) -> list[EvaluationAttempt]:
        """List attempts for one job in attempt order."""
        ...


__all__ = [
    "EvaluationConflictError",
    "EvaluationStore",
    "EvaluationStoreError",
]
