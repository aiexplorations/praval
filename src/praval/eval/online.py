"""Opt-in sampled online evaluation scheduling and durable workers.

The request path performs only deterministic sampling, bounded serialization,
and an in-memory ``put_nowait`` equivalent. PostgreSQL persistence and all
evaluator calls run in explicitly started asynchronous tasks.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Mapping, Protocol

from praval.config import OnlineEvalConfig
from praval.models import ContentKind, ContentReference, ExecutionObservation
from praval.observability import emit_evaluation_result
from praval.observability.evaluation import OnlineEvaluationTelemetry

from .context import evaluation_call_scope, is_evaluation_call
from .metrics import Metric
from .models import (
    AttemptStatus,
    EvalCase,
    EvalSuite,
    EvaluationAttempt,
    EvaluationJob,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
    EvaluationSubject,
    JobStatus,
    JudgeResult,
    MetricResult,
    ResultStatus,
)
from .runner import Judge, JudgeContext
from .store import EvaluationStore

logger = logging.getLogger(__name__)


class OnlineEvaluationProcessor(Protocol):  # pragma: no cover - declaration
    """Application evaluator invoked only by a durable worker."""

    async def __call__(self, job: EvaluationJob, subject: EvaluationSubject) -> None:
        """Persist idempotent metric or judge results for one subject."""
        ...


class OnlineContextLoader(Protocol):  # pragma: no cover - declaration
    """Resolve ephemeral candidate content away from the request path."""

    async def __call__(
        self, job: EvaluationJob, subject: EvaluationSubject
    ) -> JudgeContext:
        """Build the bounded judge context for one durable subject."""
        ...


class OnlineSubjectEvaluator:
    """Run configured judges and metrics for a leased online subject."""

    def __init__(
        self,
        *,
        store: EvaluationStore,
        suite: EvalSuite,
        context_loader: OnlineContextLoader,
        judges: Mapping[str, Judge],
        metrics: Mapping[str, Metric],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        unknown_judges = set(suite.judges) - set(judges)
        unknown_metrics = set(suite.metrics) - set(metrics)
        if unknown_judges:
            raise ValueError(f"unknown online judges: {sorted(unknown_judges)}")
        if unknown_metrics:
            raise ValueError(f"unknown online metrics: {sorted(unknown_metrics)}")
        self.store = store
        self.suite = suite
        self.context_loader = context_loader
        self.judges = dict(judges)
        self.metrics = dict(metrics)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def __call__(self, job: EvaluationJob, subject: EvaluationSubject) -> None:
        context = await self.context_loader(job, subject)
        self._validate_context(context, job, subject)
        for name in self.suite.judges:
            judge_result = await self.judges[name].evaluate(context)
            self._validate_result(judge_result, name, context)
            stored = await self.store.put_judge_result(judge_result)
            self._emit(stored, subject)
        for name in self.suite.metrics:
            metric = self.metrics[name]
            try:
                metric_result = await metric.evaluate(context)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                metric_result = MetricResult.create(
                    evaluation_run_id=job.evaluation_run_id,
                    case_id=job.case_id,
                    subject_id=job.subject_id,
                    metric=name,
                    metric_version=metric.version,
                    status=ResultStatus.ERROR,
                    error_type=type(exc).__name__[:256] or "MetricError",
                    created_at=self._aware_now(),
                )
            self._validate_result(metric_result, name, context, metric.version)
            stored_metric = await self.store.put_metric_result(metric_result)
            self._emit(stored_metric, subject)

    @staticmethod
    def _validate_context(
        context: JudgeContext,
        job: EvaluationJob,
        subject: EvaluationSubject,
    ) -> None:
        if context.evaluation_run_id != job.evaluation_run_id:
            raise ValueError("online context run identity does not match")
        if context.case.case.case_id != job.case_id:
            raise ValueError("online context case identity does not match")
        if context.subject != subject or context.subject.subject_id != job.subject_id:
            raise ValueError("online context subject identity does not match")
        if context.target_result.observation != subject.observation:
            raise ValueError("online context observation identity does not match")

    @staticmethod
    def _validate_result(
        result: JudgeResult | MetricResult,
        name: str,
        context: JudgeContext,
        version: str | None = None,
    ) -> None:
        if result.evaluation_run_id != context.evaluation_run_id:
            raise ValueError("online result run identity does not match")
        if result.case_id != context.case.case.case_id:
            raise ValueError("online result case identity does not match")
        if result.subject_id != context.subject.subject_id:
            raise ValueError("online result subject identity does not match")
        if isinstance(result, JudgeResult):
            if result.judge != name:
                raise ValueError("online judge identity does not match")
        elif result.metric != name or result.metric_version != version:
            raise ValueError("online metric identity does not match")

    @staticmethod
    def _emit(result: JudgeResult | MetricResult, subject: EvaluationSubject) -> None:
        try:
            emit_evaluation_result(result, subject)
        except Exception as exc:
            logger.warning(
                "Online evaluation result telemetry failed: %s",
                type(exc).__name__,
            )

    def _aware_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("online evaluator clock must be timezone-aware")
        return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class OnlineEvaluationStats:
    """Bounded service-health snapshot with no candidate content."""

    sampled: int
    skipped: int
    enqueued: int
    persisted: int
    processed: int
    retries: int
    dropped: int
    store_failures: int
    processor_failures: int
    dead_lettered: int
    queue_depth: int
    queue_capacity: int


@dataclass
class _QueuedObservation:
    observation: ExecutionObservation
    enqueue_attempts: int = 0


class _Counters:
    _NAMES = (
        "sampled",
        "skipped",
        "enqueued",
        "persisted",
        "processed",
        "retries",
        "dropped",
        "store_failures",
        "processor_failures",
        "dead_lettered",
    )

    def __init__(self) -> None:
        self._values = {name: 0 for name in self._NAMES}
        self._lock = threading.Lock()

    def increment(self, name: str) -> None:
        with self._lock:
            self._values[name] += 1

    def values(self) -> dict[str, int]:
        with self._lock:
            return dict(self._values)


def trace_sampled(trace_id: str | None, sample_ratio: float) -> bool:
    """Make a stable all-or-nothing decision from a 128-bit trace identity."""
    if not 0 <= sample_ratio <= 1:
        raise ValueError("sample_ratio must be in [0, 1]")
    if trace_id is None:
        return False
    if len(trace_id) != 32:
        raise ValueError("trace_id must contain 32 hexadecimal characters")
    try:
        value = int(trace_id, 16)
    except ValueError as exc:
        raise ValueError("trace_id must contain 32 hexadecimal characters") from exc
    if sample_ratio == 1:
        return True
    if sample_ratio == 0:
        return False
    return value < int(sample_ratio * (1 << 128))


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


class OnlineEvaluationService:
    """Bounded recorder, durable scheduler, and post-hoc worker lifecycle."""

    def __init__(
        self,
        *,
        store: EvaluationStore,
        suite: EvalSuite,
        processor: OnlineEvaluationProcessor,
        config: OnlineEvalConfig | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.suite = suite
        self.processor = processor
        self.config = config or OnlineEvalConfig()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._queue: deque[_QueuedObservation] = deque()
        self._queue_lock = threading.Lock()
        self._counters = _Counters()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._wakeup: asyncio.Event | None = None
        self._work_available: asyncio.Event | None = None
        self._scheduler: asyncio.Task[None] | None = None
        self._workers: list[asyncio.Task[None]] = []
        self._accepting = False
        self._stopping = False
        self._telemetry: OnlineEvaluationTelemetry | None = None

    @property
    def queue_depth(self) -> int:
        with self._queue_lock:
            return len(self._queue)

    @property
    def active(self) -> bool:
        return self._accepting

    def stats(self) -> OnlineEvaluationStats:
        """Return an atomic metadata-only health snapshot."""
        values = self._counters.values()
        return OnlineEvaluationStats(
            **values,
            queue_depth=self.queue_depth,
            queue_capacity=self.config.queue_capacity,
        )

    async def start(self) -> None:
        """Migrate storage and start explicitly owned async tasks."""
        if not self.config.enabled:
            return
        if self._accepting:
            return
        await self.store.migrate()
        await self.store.put_suite(self.suite)
        self._loop = asyncio.get_running_loop()
        self._wakeup = asyncio.Event()
        self._work_available = asyncio.Event()
        self._stopping = False
        self._accepting = True
        self._telemetry = OnlineEvaluationTelemetry(
            suite_id=self.suite.suite_id,
            queue_depth=lambda: self.queue_depth,
        )
        self._scheduler = asyncio.create_task(
            self._scheduler_loop(), name="praval-eval-scheduler"
        )
        self._workers = [
            asyncio.create_task(
                self._worker_loop(f"online-worker-{index + 1}"),
                name=f"praval-eval-worker-{index + 1}",
            )
            for index in range(self.config.workers)
        ]

    def record(self, observation: ExecutionObservation) -> None:
        """Schedule one completed observation without storage or judge calls."""
        if not self._accepting or is_evaluation_call():
            self._counters.increment("skipped")
            return
        if not self._matches_target(observation):
            self._counters.increment("skipped")
            return
        try:
            selected = trace_sampled(observation.trace_id, self.config.sample_ratio)
        except ValueError:
            self._drop("invalid_trace_id")
            return
        if not selected:
            self._counters.increment("skipped")
            return
        self._counters.increment("sampled")
        size = len(observation.model_dump_json().encode("utf-8"))
        if size > self.config.max_subject_bytes:
            self._drop("subject_too_large")
            return
        with self._queue_lock:
            if len(self._queue) >= self.config.queue_capacity:
                accepted = False
            else:
                self._queue.append(_QueuedObservation(observation))
                accepted = True
        if not accepted:
            self._drop("queue_saturated")
            return
        self._counters.increment("enqueued")
        self._signal(self._wakeup)

    async def shutdown(self, timeout_seconds: float | None = None) -> bool:
        """Stop acceptance and make one bounded drain/cancellation attempt."""
        self._accepting = False
        if self._scheduler is None:
            return True
        self._stopping = True
        self._signal(self._wakeup)
        self._signal(self._work_available)
        timeout = timeout_seconds or self.config.shutdown_timeout_seconds
        tasks = [self._scheduler, *self._workers]
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=timeout
            )
            completed = True
        except asyncio.TimeoutError:
            completed = False
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        with self._queue_lock:
            abandoned = len(self._queue)
            self._queue.clear()
        for _ in range(abandoned):
            self._counters.increment("dropped")
        self._scheduler = None
        self._workers = []
        return completed and abandoned == 0

    def _matches_target(self, observation: ExecutionObservation) -> bool:
        prefix, separator, identity = self.suite.target.partition(":")
        if not separator:
            identity = prefix
            prefix = observation.kind.value
        if prefix != observation.kind.value:
            return False
        candidates = (
            (observation.agent_id, observation.agent_name)
            if prefix == "agent"
            else (observation.workflow_id, observation.workflow_name)
        )
        return identity in candidates

    def _signal(self, event: asyncio.Event | None) -> None:
        if event is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(event.set)

    def _drop(self, reason: str) -> None:
        self._counters.increment("dropped")
        if self._telemetry is not None:
            self._telemetry.dropped(reason)

    def _pop(self) -> _QueuedObservation | None:
        with self._queue_lock:
            return self._queue.popleft() if self._queue else None

    def _requeue(self, item: _QueuedObservation) -> bool:
        with self._queue_lock:
            if len(self._queue) >= self.config.queue_capacity:
                return False
            self._queue.append(item)
            return True

    async def _scheduler_loop(self) -> None:
        assert self._wakeup is not None
        while True:
            item = self._pop()
            if item is None:
                if self._stopping:
                    return
                self._wakeup.clear()
                if self.queue_depth:
                    self._wakeup.set()
                    continue
                await self._wakeup.wait()
                continue
            try:
                persisted = await self._persist_observation(item.observation)
            except asyncio.CancelledError:
                if not self._requeue(item):
                    self._drop("shutdown_queue_full")
                raise
            except Exception as exc:
                self._counters.increment("store_failures")
                item.enqueue_attempts += 1
                if item.enqueue_attempts >= self.config.max_enqueue_attempts:
                    self._drop("store_unavailable")
                else:
                    await asyncio.sleep(
                        self.config.retry_backoff_seconds
                        * (2 ** (item.enqueue_attempts - 1))
                    )
                    if not self._requeue(item):
                        self._drop("queue_saturated_during_retry")
                logger.warning(
                    "Online evaluation persistence failed: %s",
                    type(exc).__name__,
                )
                continue
            if persisted:
                self._counters.increment("persisted")
                if self._telemetry is not None:
                    self._telemetry.scheduled()
                self._signal(self._work_available)

    async def _persist_observation(self, observation: ExecutionObservation) -> bool:
        now = self._aware_now()
        run_id = _stable_id("online-run", self.suite.suite_id, observation.run_id)
        case_id = _stable_id(
            "online-case", self.suite.suite_id, observation.observation_id
        )
        subject = EvaluationSubject.from_observation(
            evaluation_run_id=run_id,
            case_id=case_id,
            observation=observation,
        )
        job = EvaluationJob.create(
            evaluation_run_id=run_id,
            suite_id=self.suite.suite_id,
            case_id=case_id,
            subject_id=subject.subject_id,
            available_at=now,
            max_attempts=self.config.max_attempts,
            created_at=now,
            updated_at=now,
        )
        if await self.store.get_job(job.job_id) is not None:
            return False
        reference = ContentReference(
            kind=ContentKind.OTHER,
            sha256=hashlib.sha256(observation.observation_id.encode()).hexdigest(),
            size_bytes=0,
            reference=f"praval-observation:{observation.observation_id}",
        )
        case = EvalCase(
            case_id=case_id,
            name=f"Online observation {observation.observation_id}"[:512],
            input=reference,
        )
        run = EvaluationRun(
            evaluation_run_id=run_id,
            suite_id=self.suite.suite_id,
            target=self.suite.target,
            status=EvaluationRunStatus.PENDING,
            started_at=now,
        )
        await self.store.put_case(case)
        await self.store.put_run(run)
        await self.store.put_subject(subject)
        stored = await self.store.put_job(job)
        return stored == job

    async def _worker_loop(self, worker_id: str) -> None:
        assert self._work_available is not None
        while not self._stopping:
            try:
                job = await self.store.lease_job(
                    worker_id=worker_id,
                    now=self._aware_now(),
                    lease_seconds=self.config.lease_seconds,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._counters.increment("store_failures")
                logger.warning("Online evaluation lease failed: %s", type(exc).__name__)
                await asyncio.sleep(self.config.poll_interval_seconds)
                continue
            if job is None:
                self._work_available.clear()
                try:
                    await asyncio.wait_for(
                        self._work_available.wait(),
                        timeout=self.config.poll_interval_seconds,
                    )
                except asyncio.TimeoutError:
                    pass
                continue
            try:
                await self._process_job(worker_id, job)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._counters.increment("store_failures")
                logger.warning(
                    "Online evaluation worker state failed: %s",
                    type(exc).__name__,
                )

    async def _process_job(self, worker_id: str, job: EvaluationJob) -> None:
        subject = await self.store.get_subject(job.subject_id)
        if subject is None:
            await self._fail_job(worker_id, job, "SubjectMissing", 0.0)
            return
        started_at = self._aware_now()
        started = time.perf_counter()
        try:
            await self._mark_run_running(job)
            if self._telemetry is None:
                raise RuntimeError("online evaluation telemetry is not initialized")
            with self._telemetry.start_post_hoc_span(
                subject.observation,
                {
                    "praval.evaluation.run.id": job.evaluation_run_id,
                    "praval.evaluation.job.id": job.job_id,
                    "praval.evaluation.suite.id": job.suite_id,
                    "praval.evaluation.subject.id": job.subject_id,
                },
            ):
                with evaluation_call_scope():
                    await asyncio.wait_for(
                        self.processor(job, subject),
                        timeout=self.config.job_timeout_seconds,
                    )
        except asyncio.CancelledError:
            duration = max(0.0, (time.perf_counter() - started) * 1000)
            await self._record_attempt(
                job,
                started_at=started_at,
                duration_ms=duration,
                status=AttemptStatus.CANCELLED,
            )
            try:
                await self.store.retry_job(
                    job_id=job.job_id,
                    worker_id=worker_id,
                    now=self._aware_now(),
                    error_type="WorkerShutdown",
                    retry_delay_seconds=0,
                )
            except Exception:
                self._counters.increment("store_failures")
            raise
        except asyncio.TimeoutError:
            duration = max(0.0, (time.perf_counter() - started) * 1000)
            await self._fail_job(
                worker_id, job, "ProcessorTimeout", duration, started_at
            )
            return
        except Exception as exc:
            duration = max(0.0, (time.perf_counter() - started) * 1000)
            await self._fail_job(
                worker_id,
                job,
                type(exc).__name__[:256] or "ProcessorError",
                duration,
                started_at,
            )
            return
        duration = max(0.0, (time.perf_counter() - started) * 1000)
        await self._record_attempt(
            job,
            started_at=started_at,
            duration_ms=duration,
            status=AttemptStatus.SUCCEEDED,
        )
        await self.store.complete_job(
            job_id=job.job_id, worker_id=worker_id, now=self._aware_now()
        )
        await self._complete_run(job)
        self._counters.increment("processed")
        if self._telemetry is not None:
            self._telemetry.completed(duration)

    async def _fail_job(
        self,
        worker_id: str,
        job: EvaluationJob,
        error_type: str,
        duration_ms: float,
        started_at: datetime | None = None,
    ) -> None:
        self._counters.increment("processor_failures")
        await self._record_attempt(
            job,
            started_at=started_at or self._aware_now(),
            duration_ms=duration_ms,
            status=(
                AttemptStatus.TIMEOUT
                if error_type == "ProcessorTimeout"
                else AttemptStatus.FAILED
            ),
            error_type=error_type,
        )
        updated = await self.store.retry_job(
            job_id=job.job_id,
            worker_id=worker_id,
            now=self._aware_now(),
            error_type=error_type,
            retry_delay_seconds=self.config.retry_backoff_seconds
            * (2 ** max(0, job.attempt_count - 1)),
        )
        if updated.status is JobStatus.DEAD_LETTER:
            await self._fail_run(job, error_type)
            self._counters.increment("dead_lettered")
        else:
            self._counters.increment("retries")
            if self._telemetry is not None:
                self._telemetry.retry()
            self._signal(self._work_available)
        if self._telemetry is not None:
            self._telemetry.failed(error_type)

    async def _record_attempt(
        self,
        job: EvaluationJob,
        *,
        started_at: datetime,
        duration_ms: float,
        status: AttemptStatus,
        error_type: str | None = None,
    ) -> None:
        ended_at = started_at + (self._duration_delta(duration_ms))
        attempt = EvaluationAttempt.create(
            job_id=job.job_id,
            attempt_number=job.attempt_count,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
            error_type=error_type,
        )
        await self.store.put_attempt(attempt)

    @staticmethod
    def _duration_delta(duration_ms: float) -> timedelta:
        return timedelta(milliseconds=duration_ms)

    async def _mark_run_running(self, job: EvaluationJob) -> None:
        run = await self.store.get_run(job.evaluation_run_id)
        if run is not None and run.status is EvaluationRunStatus.PENDING:
            await self.store.put_run(
                run.model_copy(update={"status": EvaluationRunStatus.RUNNING})
            )

    async def _complete_run(self, job: EvaluationJob) -> None:
        now = self._aware_now()
        judges = await self.store.list_judge_results(
            evaluation_run_id=job.evaluation_run_id, limit=100_000
        )
        metrics = await self.store.list_metric_results(
            evaluation_run_id=job.evaluation_run_id, limit=100_000
        )
        statuses = {result.status for result in judges}
        statuses.update(result.status for result in metrics)
        failed = ResultStatus.FAILED in statuses
        errored = ResultStatus.ERROR in statuses
        skipped = bool(statuses) and statuses == {ResultStatus.SKIPPED}
        result = EvaluationResult(
            evaluation_run_id=job.evaluation_run_id,
            status=EvaluationRunStatus.COMPLETED,
            total_cases=1,
            passed_cases=0 if failed or errored or skipped else 1,
            failed_cases=1 if failed else 0,
            errored_cases=1 if errored else 0,
            skipped_cases=1 if skipped else 0,
            metric_result_ids=tuple(sorted(item.metric_result_id for item in metrics)),
            judge_result_ids=tuple(sorted(item.judge_result_id for item in judges)),
            completed_at=now,
        )
        await self.store.put_evaluation_result(result)
        run = await self.store.get_run(job.evaluation_run_id)
        if run is not None:
            await self.store.put_run(
                run.model_copy(
                    update={
                        "status": EvaluationRunStatus.COMPLETED,
                        "completed_at": now,
                    }
                )
            )

    async def _fail_run(self, job: EvaluationJob, error_type: str) -> None:
        run = await self.store.get_run(job.evaluation_run_id)
        if run is not None:
            await self.store.put_run(
                run.model_copy(
                    update={
                        "status": EvaluationRunStatus.FAILED,
                        "completed_at": self._aware_now(),
                        "error_type": error_type,
                    }
                )
            )

    def _aware_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("online evaluation clock must be timezone-aware")
        return value.astimezone(timezone.utc)


__all__ = [
    "OnlineContextLoader",
    "OnlineEvaluationProcessor",
    "OnlineEvaluationService",
    "OnlineEvaluationStats",
    "OnlineSubjectEvaluator",
    "trace_sampled",
]
