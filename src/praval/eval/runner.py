"""Bounded-concurrency offline evaluation orchestration."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol

from praval.models import ExecutionObservation
from praval.observability import emit_evaluation_result

from .dataset import LoadedEvalCase, LoadedEvalSuite
from .models import (
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
    EvaluationSubject,
    JudgeResult,
    ResultStatus,
)
from .store import EvaluationStore

logger = logging.getLogger(__name__)


class EvaluationExecutionError(RuntimeError):
    """An offline evaluation cannot produce a valid persisted result."""


@dataclass(frozen=True)
class TargetResult:
    """One frozen observation plus output retained only for active evaluation."""

    observation: ExecutionObservation
    output: Any


@dataclass(frozen=True)
class JudgeContext:
    """Bounded input supplied to one configured judge."""

    evaluation_run_id: str
    case: LoadedEvalCase
    subject: EvaluationSubject
    target_result: TargetResult


class EvaluationTarget(Protocol):  # pragma: no cover - structural declaration
    """Async target capable of evaluating one loaded case."""

    async def evaluate(self, case: LoadedEvalCase) -> TargetResult:
        """Execute one case and return its observation and ephemeral output."""
        ...


class Judge(Protocol):  # pragma: no cover - structural declaration
    """Configured evaluator that returns a validated judge result."""

    name: str

    async def evaluate(self, context: JudgeContext) -> JudgeResult:
        """Evaluate one completed target subject."""
        ...


@dataclass(frozen=True)
class _CaseOutcome:
    status: ResultStatus
    judge_results: tuple[JudgeResult, ...]


class EvalRunner:
    """Run a loaded suite with bounded target concurrency and persistence."""

    def __init__(
        self,
        *,
        store: EvaluationStore,
        target: EvaluationTarget,
        judges: Mapping[str, Judge],
        concurrency: int = 4,
        clock: Callable[[], datetime] | None = None,
    ):
        if concurrency <= 0:
            raise ValueError("concurrency must be positive")
        self.store = store
        self.target = target
        self.judges = dict(judges)
        self.concurrency = concurrency
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def run(
        self,
        loaded_suite: LoadedEvalSuite,
        *,
        evaluation_run_id: str | None = None,
    ) -> EvaluationResult:
        """Execute, persist, and summarize one offline evaluation suite."""
        unknown_judges = sorted(set(loaded_suite.suite.judges) - set(self.judges))
        if unknown_judges:
            raise EvaluationExecutionError(f"unknown judges: {unknown_judges}")
        run_id = evaluation_run_id or str(uuid.uuid4())
        started_at = self._aware_now()
        run = EvaluationRun(
            evaluation_run_id=run_id,
            suite_id=loaded_suite.suite.suite_id,
            target=loaded_suite.suite.target,
            status=EvaluationRunStatus.RUNNING,
            started_at=started_at,
        )
        await self.store.put_suite(loaded_suite.suite)
        for loaded_case in loaded_suite.cases:
            await self.store.put_case(loaded_case.case)
        await self.store.put_run(run)
        semaphore = asyncio.Semaphore(self.concurrency)

        async def evaluate_case(case: LoadedEvalCase) -> _CaseOutcome:
            async with semaphore:
                return await self._evaluate_case(run_id, loaded_suite, case)

        try:
            outcomes = await asyncio.gather(
                *(evaluate_case(case) for case in loaded_suite.cases)
            )
        except Exception as exc:
            error = (
                exc
                if isinstance(exc, EvaluationExecutionError)
                else EvaluationExecutionError(
                    f"evaluation run failed with {type(exc).__name__}"
                )
            )
            failed_run = run.model_copy(
                update={
                    "status": EvaluationRunStatus.FAILED,
                    "completed_at": self._aware_now(),
                    "error_type": type(error).__name__,
                }
            )
            await self.store.put_run(failed_run)
            if error is exc:
                raise
            raise error from exc

        judge_result_ids = tuple(
            sorted(
                result.judge_result_id
                for outcome in outcomes
                for result in outcome.judge_results
            )
        )
        result = EvaluationResult(
            evaluation_run_id=run_id,
            status=EvaluationRunStatus.COMPLETED,
            total_cases=len(outcomes),
            passed_cases=sum(
                outcome.status is ResultStatus.PASSED for outcome in outcomes
            ),
            failed_cases=sum(
                outcome.status is ResultStatus.FAILED for outcome in outcomes
            ),
            errored_cases=sum(
                outcome.status is ResultStatus.ERROR for outcome in outcomes
            ),
            skipped_cases=sum(
                outcome.status is ResultStatus.SKIPPED for outcome in outcomes
            ),
            judge_result_ids=judge_result_ids,
            completed_at=self._aware_now(),
        )
        await self.store.put_evaluation_result(result)
        await self.store.put_run(
            run.model_copy(
                update={
                    "status": EvaluationRunStatus.COMPLETED,
                    "completed_at": result.completed_at,
                }
            )
        )
        return result

    async def _evaluate_case(
        self,
        evaluation_run_id: str,
        loaded_suite: LoadedEvalSuite,
        case: LoadedEvalCase,
    ) -> _CaseOutcome:
        target_result = await self.target.evaluate(case)
        subject = EvaluationSubject.from_observation(
            evaluation_run_id=evaluation_run_id,
            case_id=case.case.case_id,
            observation=target_result.observation,
        )
        await self.store.put_subject(subject)
        results = []
        for judge_name in loaded_suite.suite.judges:
            context = JudgeContext(
                evaluation_run_id=evaluation_run_id,
                case=case,
                subject=subject,
                target_result=target_result,
            )
            result = await self.judges[judge_name].evaluate(context)
            self._validate_judge_identity(result, judge_name, context)
            stored = await self.store.put_judge_result(result)
            results.append(stored)
            self._emit_result(stored, subject)
        statuses = {result.status for result in results}
        if ResultStatus.ERROR in statuses:
            status = ResultStatus.ERROR
        elif ResultStatus.FAILED in statuses:
            status = ResultStatus.FAILED
        elif statuses and statuses == {ResultStatus.SKIPPED}:
            status = ResultStatus.SKIPPED
        else:
            status = ResultStatus.PASSED
        return _CaseOutcome(status=status, judge_results=tuple(results))

    @staticmethod
    def _validate_judge_identity(
        result: JudgeResult, judge_name: str, context: JudgeContext
    ) -> None:
        if result.evaluation_run_id != context.evaluation_run_id:
            raise EvaluationExecutionError("judge result run identity does not match")
        if result.case_id != context.case.case.case_id:
            raise EvaluationExecutionError("judge result case identity does not match")
        if result.subject_id != context.subject.subject_id:
            raise EvaluationExecutionError(
                "judge result subject identity does not match"
            )
        if result.judge != judge_name:
            raise EvaluationExecutionError(
                "judge result evaluator identity does not match"
            )

    def _aware_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise EvaluationExecutionError(
                "runner clock must return an aware timestamp"
            )
        return value.astimezone(timezone.utc)

    @staticmethod
    def _emit_result(result: JudgeResult, subject: EvaluationSubject) -> None:
        """Keep telemetry exporter failures out of evaluation semantics."""
        try:
            emit_evaluation_result(result, subject)
        except Exception as exc:
            logger.warning("Evaluation result telemetry failed: %s", type(exc).__name__)


__all__ = [
    "EvalRunner",
    "EvaluationExecutionError",
    "EvaluationTarget",
    "Judge",
    "JudgeContext",
    "TargetResult",
]
