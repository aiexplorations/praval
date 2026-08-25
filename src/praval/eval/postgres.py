"""PostgreSQL evaluation store for shared and production deployments."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from importlib import import_module
from typing import Any, TypeVar

from pydantic import BaseModel

try:
    asyncpg: Any = import_module("asyncpg")
except ImportError:  # pragma: no cover - exercised in minimal wheel tests
    asyncpg = None

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
from .store import EvaluationConflictError, EvaluationStoreError

_RecordT = TypeVar("_RecordT", bound=BaseModel)


class PostgresEvaluationStore:
    """Pooled async PostgreSQL implementation of ``EvaluationStore``."""

    _SCHEMA_VERSION = 1

    def __init__(
        self,
        dsn: str,
        *,
        min_pool_size: int = 1,
        max_pool_size: int = 10,
        command_timeout: float = 30.0,
    ):
        if asyncpg is None:
            raise EvaluationStoreError(
                "asyncpg is required for PostgreSQL evaluation storage; "
                "install praval[storage]"
            )
        if not dsn.strip():
            raise ValueError("dsn must not be empty")
        if min_pool_size < 1 or max_pool_size < min_pool_size:
            raise ValueError(
                "pool sizes must satisfy 1 <= min_pool_size <= max_pool_size"
            )
        if command_timeout <= 0:
            raise ValueError("command_timeout must be positive")
        self.dsn = dsn
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        self.command_timeout = command_timeout
        self._pool: Any = None

    async def _get_pool(self) -> Any:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self.dsn,
                min_size=self.min_pool_size,
                max_size=self.max_pool_size,
                command_timeout=self.command_timeout,
            )
        return self._pool

    async def migrate(self) -> None:
        """Apply the initial schema transactionally and idempotently."""
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtext('praval_eval_migrations'))"
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS evaluation_schema_migrations (
                        version INTEGER PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    CREATE TABLE IF NOT EXISTS evaluation_cases (
                        id TEXT PRIMARY KEY,
                        payload JSONB NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS evaluation_suites (
                        id TEXT PRIMARY KEY,
                        payload JSONB NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS evaluation_runs (
                        id TEXT PRIMARY KEY,
                        suite_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        started_at TIMESTAMPTZ NOT NULL,
                        payload JSONB NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_evaluation_runs_suite_started
                        ON evaluation_runs(suite_id, started_at DESC);
                    CREATE TABLE IF NOT EXISTS evaluation_subjects (
                        id TEXT PRIMARY KEY,
                        evaluation_run_id TEXT NOT NULL,
                        case_id TEXT NOT NULL,
                        observation_id TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        payload JSONB NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_evaluation_subjects_run
                        ON evaluation_subjects(evaluation_run_id, id);
                    CREATE TABLE IF NOT EXISTS evaluation_metric_results (
                        id TEXT PRIMARY KEY,
                        evaluation_run_id TEXT NOT NULL,
                        case_id TEXT NOT NULL,
                        subject_id TEXT NOT NULL,
                        metric TEXT NOT NULL,
                        payload JSONB NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_evaluation_metrics_run_metric
                        ON evaluation_metric_results(evaluation_run_id, metric, id);
                    CREATE TABLE IF NOT EXISTS evaluation_judge_results (
                        id TEXT PRIMARY KEY,
                        evaluation_run_id TEXT NOT NULL,
                        case_id TEXT NOT NULL,
                        subject_id TEXT NOT NULL,
                        judge TEXT NOT NULL,
                        payload JSONB NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_evaluation_judges_run
                        ON evaluation_judge_results(evaluation_run_id, id);
                    CREATE TABLE IF NOT EXISTS evaluation_gate_results (
                        id TEXT PRIMARY KEY,
                        evaluation_run_id TEXT NOT NULL,
                        gate_id TEXT NOT NULL,
                        metric TEXT NOT NULL,
                        payload JSONB NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_evaluation_gates_run
                        ON evaluation_gate_results(evaluation_run_id, id);
                    CREATE TABLE IF NOT EXISTS evaluation_results (
                        evaluation_run_id TEXT PRIMARY KEY,
                        payload JSONB NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS evaluation_baselines (
                        id TEXT PRIMARY KEY,
                        suite_id TEXT NOT NULL,
                        source_evaluation_run_id TEXT NOT NULL,
                        active BOOLEAN NOT NULL,
                        promoted_at TIMESTAMPTZ NOT NULL,
                        payload JSONB NOT NULL
                    );
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_evaluation_active_baseline
                        ON evaluation_baselines(suite_id) WHERE active;
                    CREATE INDEX IF NOT EXISTS idx_evaluation_baseline_history
                        ON evaluation_baselines(suite_id, promoted_at DESC);
                    CREATE TABLE IF NOT EXISTS evaluation_jobs (
                        id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        available_at TIMESTAMPTZ NOT NULL,
                        lease_expires_at TIMESTAMPTZ,
                        payload JSONB NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_evaluation_jobs_ready
                        ON evaluation_jobs(status, available_at, id);
                    CREATE TABLE IF NOT EXISTS evaluation_attempts (
                        id TEXT PRIMARY KEY,
                        job_id TEXT NOT NULL,
                        attempt_number INTEGER NOT NULL,
                        payload JSONB NOT NULL,
                        UNIQUE(job_id, attempt_number)
                    );
                    CREATE INDEX IF NOT EXISTS idx_evaluation_attempts_job
                        ON evaluation_attempts(job_id, attempt_number);
                    INSERT INTO evaluation_schema_migrations (version)
                    VALUES (1) ON CONFLICT (version) DO NOTHING;
                    """
                )

    async def schema_version(self) -> int:
        """Return the latest applied migration version."""
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            value = await connection.fetchval(
                "SELECT COALESCE(MAX(version), 0) " "FROM evaluation_schema_migrations"
            )
        return int(value)

    async def close(self) -> None:
        """Close the owned connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @staticmethod
    def _payload(record: BaseModel) -> str:
        return record.model_dump_json()

    @staticmethod
    def _decode(model: type[_RecordT], payload: Any) -> _RecordT:
        if isinstance(payload, str):
            return model.model_validate_json(payload)
        return model.model_validate(payload)

    async def _put_immutable(
        self,
        *,
        table: str,
        identity: str,
        record: _RecordT,
        columns: tuple[str, ...] = (),
        values: tuple[Any, ...] = (),
        description: str,
    ) -> _RecordT:
        names = ("id", *columns, "payload")
        placeholders = [f"${index}" for index in range(1, len(names) + 1)]
        placeholders[-1] += "::jsonb"
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    f"INSERT INTO {table} ({', '.join(names)}) "
                    f"VALUES ({', '.join(placeholders)}) "
                    "ON CONFLICT (id) DO NOTHING",
                    identity,
                    *values,
                    self._payload(record),
                )
                payload = await connection.fetchval(
                    f"SELECT payload FROM {table} WHERE id = $1", identity
                )
        if payload is None:  # pragma: no cover - PostgreSQL invariant
            raise EvaluationStoreError(f"failed to persist {description}")
        existing = self._decode(type(record), payload)
        if existing != record:
            raise EvaluationConflictError(
                f"{description} identity conflicts with stored data"
            )
        return record

    async def _get(
        self,
        table: str,
        identity_column: str,
        identity: str,
        model: type[_RecordT],
    ) -> _RecordT | None:
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            payload = await connection.fetchval(
                f"SELECT payload FROM {table} WHERE {identity_column} = $1", identity
            )
        return self._decode(model, payload) if payload is not None else None

    async def _list(
        self,
        *,
        table: str,
        model: type[_RecordT],
        where: str = "",
        values: tuple[Any, ...] = (),
        order_by: str = "id",
        limit: int,
    ) -> list[_RecordT]:
        bounded_limit = max(1, min(limit, 100_000))
        query = f"SELECT payload FROM {table}"
        if where:
            query += f" WHERE {where}"
        query += f" ORDER BY {order_by} LIMIT ${len(values) + 1}"
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(query, *values, bounded_limit)
        return [self._decode(model, row["payload"]) for row in rows]

    async def put_case(self, case: EvalCase) -> EvalCase:
        """Persist an immutable case idempotently."""
        return await self._put_immutable(
            table="evaluation_cases",
            identity=case.case_id,
            record=case,
            description="case",
        )

    async def get_case(self, case_id: str) -> EvalCase | None:
        """Load one case by identity."""
        return await self._get("evaluation_cases", "id", case_id, EvalCase)

    async def list_cases(self, *, limit: int = 100) -> list[EvalCase]:
        """List cases in stable identity order."""
        return await self._list(table="evaluation_cases", model=EvalCase, limit=limit)

    async def put_suite(self, suite: EvalSuite) -> EvalSuite:
        """Persist an immutable suite idempotently."""
        return await self._put_immutable(
            table="evaluation_suites",
            identity=suite.suite_id,
            record=suite,
            description="suite",
        )

    async def get_suite(self, suite_id: str) -> EvalSuite | None:
        """Load one suite by identity."""
        return await self._get("evaluation_suites", "id", suite_id, EvalSuite)

    async def put_run(self, run: EvaluationRun) -> EvaluationRun:
        """Create or update a run lifecycle record."""
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO evaluation_runs (id, suite_id, status, started_at, payload)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                ON CONFLICT(id) DO UPDATE SET
                    suite_id=excluded.suite_id,
                    status=excluded.status,
                    started_at=excluded.started_at,
                    payload=excluded.payload
                """,
                run.evaluation_run_id,
                run.suite_id,
                run.status.value,
                run.started_at,
                self._payload(run),
            )
        return run

    async def get_run(self, evaluation_run_id: str) -> EvaluationRun | None:
        """Load one evaluation run."""
        return await self._get(
            "evaluation_runs", "id", evaluation_run_id, EvaluationRun
        )

    async def list_runs(
        self, *, suite_id: str | None = None, limit: int = 100
    ) -> list[EvaluationRun]:
        """List recent runs, optionally restricted to a suite."""
        return await self._list(
            table="evaluation_runs",
            model=EvaluationRun,
            where="suite_id = $1" if suite_id is not None else "",
            values=(suite_id,) if suite_id is not None else (),
            order_by="started_at DESC, id",
            limit=limit,
        )

    async def put_subject(self, subject: EvaluationSubject) -> EvaluationSubject:
        """Persist one immutable agent or workflow subject."""
        return await self._put_immutable(
            table="evaluation_subjects",
            identity=subject.subject_id,
            record=subject,
            columns=(
                "evaluation_run_id",
                "case_id",
                "observation_id",
                "kind",
            ),
            values=(
                subject.evaluation_run_id,
                subject.case_id,
                subject.observation_id,
                subject.kind.value,
            ),
            description="subject",
        )

    async def get_subject(self, subject_id: str) -> EvaluationSubject | None:
        """Load one subject."""
        return await self._get(
            "evaluation_subjects", "id", subject_id, EvaluationSubject
        )

    async def list_subjects(
        self, *, evaluation_run_id: str, limit: int = 100
    ) -> list[EvaluationSubject]:
        """List subjects belonging to a run."""
        return await self._list(
            table="evaluation_subjects",
            model=EvaluationSubject,
            where="evaluation_run_id = $1",
            values=(evaluation_run_id,),
            limit=limit,
        )

    async def put_metric_result(self, result: MetricResult) -> MetricResult:
        """Persist one immutable, idempotent metric result."""
        return await self._put_immutable(
            table="evaluation_metric_results",
            identity=result.metric_result_id,
            record=result,
            columns=("evaluation_run_id", "case_id", "subject_id", "metric"),
            values=(
                result.evaluation_run_id,
                result.case_id,
                result.subject_id,
                result.metric,
            ),
            description="metric result",
        )

    async def list_metric_results(
        self,
        *,
        evaluation_run_id: str,
        metric: str | None = None,
        limit: int = 1000,
    ) -> list[MetricResult]:
        """List metric results for a run."""
        where = "evaluation_run_id = $1"
        values: tuple[Any, ...] = (evaluation_run_id,)
        if metric is not None:
            where += " AND metric = $2"
            values += (metric,)
        return await self._list(
            table="evaluation_metric_results",
            model=MetricResult,
            where=where,
            values=values,
            limit=limit,
        )

    async def put_judge_result(self, result: JudgeResult) -> JudgeResult:
        """Persist one immutable, idempotent judge result."""
        return await self._put_immutable(
            table="evaluation_judge_results",
            identity=result.judge_result_id,
            record=result,
            columns=("evaluation_run_id", "case_id", "subject_id", "judge"),
            values=(
                result.evaluation_run_id,
                result.case_id,
                result.subject_id,
                result.judge,
            ),
            description="judge result",
        )

    async def list_judge_results(
        self, *, evaluation_run_id: str, limit: int = 1000
    ) -> list[JudgeResult]:
        """List judge results for a run."""
        return await self._list(
            table="evaluation_judge_results",
            model=JudgeResult,
            where="evaluation_run_id = $1",
            values=(evaluation_run_id,),
            limit=limit,
        )

    async def put_gate_result(self, result: GateResult) -> GateResult:
        """Persist one immutable, idempotent gate result."""
        return await self._put_immutable(
            table="evaluation_gate_results",
            identity=result.gate_result_id,
            record=result,
            columns=("evaluation_run_id", "gate_id", "metric"),
            values=(result.evaluation_run_id, result.gate_id, result.metric),
            description="gate result",
        )

    async def list_gate_results(
        self, *, evaluation_run_id: str, limit: int = 1000
    ) -> list[GateResult]:
        """List gate decisions for a run."""
        return await self._list(
            table="evaluation_gate_results",
            model=GateResult,
            where="evaluation_run_id = $1",
            values=(evaluation_run_id,),
            limit=limit,
        )

    async def put_evaluation_result(self, result: EvaluationResult) -> EvaluationResult:
        """Persist one immutable terminal run summary."""
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "INSERT INTO evaluation_results (evaluation_run_id, payload) "
                    "VALUES ($1, $2::jsonb) "
                    "ON CONFLICT (evaluation_run_id) DO NOTHING",
                    result.evaluation_run_id,
                    self._payload(result),
                )
                payload = await connection.fetchval(
                    "SELECT payload FROM evaluation_results "
                    "WHERE evaluation_run_id = $1",
                    result.evaluation_run_id,
                )
        if self._decode(EvaluationResult, payload) != result:
            raise EvaluationConflictError(
                "evaluation result identity conflicts with stored data"
            )
        return result

    async def get_evaluation_result(
        self, evaluation_run_id: str
    ) -> EvaluationResult | None:
        """Load a terminal run summary."""
        return await self._get(
            "evaluation_results",
            "evaluation_run_id",
            evaluation_run_id,
            EvaluationResult,
        )

    async def promote_baseline(
        self, baseline: EvaluationBaseline
    ) -> EvaluationBaseline:
        """Atomically make an explicit baseline active for its suite."""
        if not baseline.active:
            raise ValueError("a promoted baseline must be active")
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtext($1))",
                    f"praval_eval_baseline:{baseline.suite_id}",
                )
                rows = await connection.fetch(
                    "SELECT id, payload FROM evaluation_baselines "
                    "WHERE suite_id = $1 AND active FOR UPDATE",
                    baseline.suite_id,
                )
                for row in rows:
                    previous = self._decode(EvaluationBaseline, row["payload"])
                    inactive = previous.model_copy(update={"active": False})
                    await connection.execute(
                        "UPDATE evaluation_baselines "
                        "SET active = FALSE, payload = $1::jsonb WHERE id = $2",
                        self._payload(inactive),
                        previous.baseline_id,
                    )
                await connection.execute(
                    """
                    INSERT INTO evaluation_baselines (
                        id, suite_id, source_evaluation_run_id, active,
                        promoted_at, payload
                    ) VALUES ($1, $2, $3, TRUE, $4, $5::jsonb)
                    ON CONFLICT(id) DO UPDATE SET
                        active=TRUE,
                        promoted_at=excluded.promoted_at,
                        payload=excluded.payload
                    """,
                    baseline.baseline_id,
                    baseline.suite_id,
                    baseline.source_evaluation_run_id,
                    baseline.promoted_at,
                    self._payload(baseline),
                )
        return baseline

    async def get_active_baseline(self, suite_id: str) -> EvaluationBaseline | None:
        """Load the active baseline for a suite."""
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            payload = await connection.fetchval(
                "SELECT payload FROM evaluation_baselines "
                "WHERE suite_id = $1 AND active",
                suite_id,
            )
        return (
            self._decode(EvaluationBaseline, payload) if payload is not None else None
        )

    async def list_baselines(
        self, *, suite_id: str, limit: int = 100
    ) -> list[EvaluationBaseline]:
        """List baseline promotion history for a suite."""
        return await self._list(
            table="evaluation_baselines",
            model=EvaluationBaseline,
            where="suite_id = $1",
            values=(suite_id,),
            order_by="promoted_at DESC, id",
            limit=limit,
        )

    async def put_job(self, job: EvaluationJob) -> EvaluationJob:
        """Create a durable job idempotently without reverting its lifecycle."""
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "INSERT INTO evaluation_jobs "
                    "(id, status, available_at, lease_expires_at, payload) "
                    "VALUES ($1, $2, $3, $4, $5::jsonb) "
                    "ON CONFLICT(id) DO NOTHING",
                    job.job_id,
                    job.status.value,
                    job.available_at,
                    job.lease_expires_at,
                    self._payload(job),
                )
                payload = await connection.fetchval(
                    "SELECT payload FROM evaluation_jobs WHERE id = $1",
                    job.job_id,
                )
                existing = self._decode(EvaluationJob, payload)
                if not self._same_job_identity(existing, job):
                    raise EvaluationConflictError(
                        "job identity conflicts with stored data"
                    )
                return existing

    @staticmethod
    def _same_job_identity(left: EvaluationJob, right: EvaluationJob) -> bool:
        return (
            left.evaluation_run_id,
            left.suite_id,
            left.case_id,
            left.subject_id,
            left.max_attempts,
        ) == (
            right.evaluation_run_id,
            right.suite_id,
            right.case_id,
            right.subject_id,
            right.max_attempts,
        )

    @staticmethod
    def _aware_utc(value: datetime, *, field: str) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field} must be timezone-aware")
        return value.astimezone(timezone.utc)

    async def _write_job_row(self, connection: Any, job: EvaluationJob) -> None:
        await connection.execute(
            "UPDATE evaluation_jobs SET status = $1, available_at = $2, "
            "lease_expires_at = $3, payload = $4::jsonb WHERE id = $5",
            job.status.value,
            job.available_at,
            job.lease_expires_at,
            self._payload(job),
            job.job_id,
        )

    async def get_job(self, job_id: str) -> EvaluationJob | None:
        """Load one job."""
        return await self._get("evaluation_jobs", "id", job_id, EvaluationJob)

    async def list_jobs(
        self, *, status: JobStatus | None = None, limit: int = 100
    ) -> list[EvaluationJob]:
        """List jobs, optionally filtered by status."""
        return await self._list(
            table="evaluation_jobs",
            model=EvaluationJob,
            where="status = $1" if status is not None else "",
            values=(status.value,) if status is not None else (),
            order_by="available_at, id",
            limit=limit,
        )

    async def lease_job(
        self,
        *,
        worker_id: str,
        now: datetime,
        lease_seconds: float,
    ) -> EvaluationJob | None:
        """Atomically lease one ready job with ``FOR UPDATE SKIP LOCKED``."""
        if not worker_id.strip() or len(worker_id) > 256:
            raise ValueError("worker_id must be non-empty and bounded")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        current = self._aware_utc(now, field="now")
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                while True:
                    payload = await connection.fetchval(
                        "SELECT payload FROM evaluation_jobs WHERE "
                        "(status = $1 AND available_at <= $3) OR "
                        "(status = $2 AND lease_expires_at <= $3) "
                        "ORDER BY available_at, id FOR UPDATE SKIP LOCKED LIMIT 1",
                        JobStatus.PENDING.value,
                        JobStatus.LEASED.value,
                        current,
                    )
                    if payload is None:
                        return None
                    job = self._decode(EvaluationJob, payload)
                    if job.attempt_count >= job.max_attempts:
                        exhausted = job.model_copy(
                            update={
                                "status": JobStatus.DEAD_LETTER,
                                "lease_owner": None,
                                "lease_expires_at": None,
                                "error_type": "LeaseExpired",
                                "updated_at": current,
                            }
                        )
                        await self._write_job_row(connection, exhausted)
                        continue
                    leased = job.model_copy(
                        update={
                            "status": JobStatus.LEASED,
                            "lease_owner": worker_id,
                            "lease_expires_at": current
                            + timedelta(seconds=lease_seconds),
                            "attempt_count": job.attempt_count + 1,
                            "error_type": None,
                            "updated_at": current,
                        }
                    )
                    await self._write_job_row(connection, leased)
                    return leased

    async def _load_leased_job(
        self, connection: Any, job_id: str, worker_id: str
    ) -> EvaluationJob:
        payload = await connection.fetchval(
            "SELECT payload FROM evaluation_jobs WHERE id = $1 FOR UPDATE",
            job_id,
        )
        if payload is None:
            raise EvaluationConflictError("job does not exist")
        job = self._decode(EvaluationJob, payload)
        if job.status is not JobStatus.LEASED or job.lease_owner != worker_id:
            raise EvaluationConflictError("job lease owner does not match")
        return job

    async def complete_job(
        self, *, job_id: str, worker_id: str, now: datetime
    ) -> EvaluationJob:
        """Complete an actively leased job atomically."""
        current = self._aware_utc(now, field="now")
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                job = await self._load_leased_job(connection, job_id, worker_id)
                completed = job.model_copy(
                    update={
                        "status": JobStatus.COMPLETED,
                        "lease_owner": None,
                        "lease_expires_at": None,
                        "error_type": None,
                        "updated_at": current,
                    }
                )
                await self._write_job_row(connection, completed)
                return completed

    async def retry_job(
        self,
        *,
        job_id: str,
        worker_id: str,
        now: datetime,
        error_type: str,
        retry_delay_seconds: float,
    ) -> EvaluationJob:
        """Release a failed lease or dead-letter an exhausted job."""
        if not error_type.strip() or len(error_type) > 256:
            raise ValueError("error_type must be non-empty and bounded")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")
        current = self._aware_utc(now, field="now")
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                job = await self._load_leased_job(connection, job_id, worker_id)
                exhausted = job.attempt_count >= job.max_attempts
                updated = job.model_copy(
                    update={
                        "status": (
                            JobStatus.DEAD_LETTER if exhausted else JobStatus.PENDING
                        ),
                        "available_at": current
                        + timedelta(seconds=retry_delay_seconds),
                        "lease_owner": None,
                        "lease_expires_at": None,
                        "error_type": error_type if exhausted else None,
                        "updated_at": current,
                    }
                )
                await self._write_job_row(connection, updated)
                return updated

    async def put_attempt(self, attempt: EvaluationAttempt) -> EvaluationAttempt:
        """Persist one immutable job attempt and enforce its natural key."""
        pool = await self._get_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "INSERT INTO evaluation_attempts "
                    "(id, job_id, attempt_number, payload) "
                    "VALUES ($1, $2, $3, $4::jsonb) "
                    "ON CONFLICT DO NOTHING",
                    attempt.attempt_id,
                    attempt.job_id,
                    attempt.attempt_number,
                    self._payload(attempt),
                )
                row = await connection.fetchrow(
                    "SELECT id, payload FROM evaluation_attempts "
                    "WHERE job_id = $1 AND attempt_number = $2",
                    attempt.job_id,
                    attempt.attempt_number,
                )
                if row is None or row["id"] != attempt.attempt_id:
                    raise EvaluationConflictError(
                        "attempt number conflicts with stored attempt"
                    )
                existing = self._decode(EvaluationAttempt, row["payload"])
                if existing != attempt:
                    raise EvaluationConflictError(
                        "attempt identity conflicts with stored data"
                    )
        return attempt

    async def list_attempts(
        self, *, job_id: str, limit: int = 100
    ) -> list[EvaluationAttempt]:
        """List attempts for one job in attempt order."""
        return await self._list(
            table="evaluation_attempts",
            model=EvaluationAttempt,
            where="job_id = $1",
            values=(job_id,),
            order_by="attempt_number, id",
            limit=limit,
        )


__all__ = ["PostgresEvaluationStore"]
