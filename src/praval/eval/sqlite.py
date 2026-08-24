"""SQLite evaluation store for local development and CI."""

from __future__ import annotations

import asyncio
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, ParamSpec, TypeVar

from pydantic import BaseModel

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
from .store import EvaluationConflictError

_RecordT = TypeVar("_RecordT", bound=BaseModel)
_Params = ParamSpec("_Params")
_ReturnT = TypeVar("_ReturnT")


class SQLiteEvaluationStore:
    """Async SQLite implementation of the evaluation persistence contract.

    Blocking SQLite calls run in worker threads. A per-store async lock keeps
    transactions ordered, while WAL and a bounded busy timeout make separate
    store instances safe for local concurrent writers.
    """

    _SCHEMA_VERSION = 1

    def __init__(self, db_path: str | os.PathLike[str], *, busy_timeout_ms: int = 5000):
        if busy_timeout_ms <= 0:
            raise ValueError("busy_timeout_ms must be positive")
        self.db_path = os.fspath(db_path)
        self.busy_timeout_ms = busy_timeout_ms
        self._lock = asyncio.Lock()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            self.db_path,
            timeout=self.busy_timeout_ms / 1000,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    async def _run(
        self,
        function: Callable[_Params, _ReturnT],
        *args: _Params.args,
        **kwargs: _Params.kwargs,
    ) -> _ReturnT:
        async with self._lock:
            return await asyncio.to_thread(function, *args, **kwargs)

    async def migrate(self) -> None:
        """Apply the initial schema transactionally and idempotently."""
        await self._run(self._migrate_sync)

    def _migrate_sync(self) -> None:
        Path(self.db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS evaluation_schema_migrations (
                        version INTEGER PRIMARY KEY,
                        applied_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS evaluation_cases (
                        id TEXT PRIMARY KEY,
                        payload TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS evaluation_suites (
                        id TEXT PRIMARY KEY,
                        payload TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS evaluation_runs (
                        id TEXT PRIMARY KEY,
                        suite_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        payload TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_evaluation_runs_suite_started
                        ON evaluation_runs(suite_id, started_at DESC);
                    CREATE TABLE IF NOT EXISTS evaluation_subjects (
                        id TEXT PRIMARY KEY,
                        evaluation_run_id TEXT NOT NULL,
                        case_id TEXT NOT NULL,
                        observation_id TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        payload TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_evaluation_subjects_run
                        ON evaluation_subjects(evaluation_run_id, id);
                    CREATE TABLE IF NOT EXISTS evaluation_metric_results (
                        id TEXT PRIMARY KEY,
                        evaluation_run_id TEXT NOT NULL,
                        case_id TEXT NOT NULL,
                        subject_id TEXT NOT NULL,
                        metric TEXT NOT NULL,
                        payload TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_evaluation_metrics_run_metric
                        ON evaluation_metric_results(evaluation_run_id, metric, id);
                    CREATE TABLE IF NOT EXISTS evaluation_judge_results (
                        id TEXT PRIMARY KEY,
                        evaluation_run_id TEXT NOT NULL,
                        case_id TEXT NOT NULL,
                        subject_id TEXT NOT NULL,
                        judge TEXT NOT NULL,
                        payload TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_evaluation_judges_run
                        ON evaluation_judge_results(evaluation_run_id, id);
                    CREATE TABLE IF NOT EXISTS evaluation_gate_results (
                        id TEXT PRIMARY KEY,
                        evaluation_run_id TEXT NOT NULL,
                        gate_id TEXT NOT NULL,
                        metric TEXT NOT NULL,
                        payload TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_evaluation_gates_run
                        ON evaluation_gate_results(evaluation_run_id, id);
                    CREATE TABLE IF NOT EXISTS evaluation_results (
                        evaluation_run_id TEXT PRIMARY KEY,
                        payload TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS evaluation_baselines (
                        id TEXT PRIMARY KEY,
                        suite_id TEXT NOT NULL,
                        source_evaluation_run_id TEXT NOT NULL,
                        active INTEGER NOT NULL,
                        promoted_at TEXT NOT NULL,
                        payload TEXT NOT NULL
                    );
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_evaluation_active_baseline
                        ON evaluation_baselines(suite_id) WHERE active = 1;
                    CREATE INDEX IF NOT EXISTS idx_evaluation_baseline_history
                        ON evaluation_baselines(suite_id, promoted_at DESC);
                    CREATE TABLE IF NOT EXISTS evaluation_jobs (
                        id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        available_at TEXT NOT NULL,
                        lease_expires_at TEXT,
                        payload TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_evaluation_jobs_ready
                        ON evaluation_jobs(status, available_at, id);
                    CREATE TABLE IF NOT EXISTS evaluation_attempts (
                        id TEXT PRIMARY KEY,
                        job_id TEXT NOT NULL,
                        attempt_number INTEGER NOT NULL,
                        payload TEXT NOT NULL,
                        UNIQUE(job_id, attempt_number)
                    );
                    CREATE INDEX IF NOT EXISTS idx_evaluation_attempts_job
                        ON evaluation_attempts(job_id, attempt_number);
                    """
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO evaluation_schema_migrations
                        (version, applied_at)
                    VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                    """
                )
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    async def schema_version(self) -> int:
        """Return the latest applied migration version."""
        return int(await self._run(self._schema_version_sync))

    def _schema_version_sync(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) AS version "
                "FROM evaluation_schema_migrations"
            ).fetchone()
        return int(row["version"])

    async def close(self) -> None:
        """Close the store; connections are scoped per operation."""

    @staticmethod
    def _payload(record: BaseModel) -> str:
        return record.model_dump_json()

    def _put_immutable_sync(
        self,
        *,
        table: str,
        identity: str,
        record: _RecordT,
        columns: tuple[str, ...] = (),
        values: tuple[Any, ...] = (),
        description: str,
    ) -> _RecordT:
        payload = self._payload(record)
        names = ("id", *columns, "payload")
        placeholders = ", ".join("?" for _ in names)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    f"INSERT OR IGNORE INTO {table} "
                    f"({', '.join(names)}) VALUES ({placeholders})",
                    (identity, *values, payload),
                )
                row = connection.execute(
                    f"SELECT payload FROM {table} WHERE id = ?", (identity,)
                ).fetchone()
                if row is None:  # pragma: no cover - SQLite invariant
                    raise RuntimeError(f"failed to persist {description}")
                if row["payload"] != payload:
                    raise EvaluationConflictError(
                        f"{description} identity conflicts with stored data"
                    )
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        return record

    def _get_sync(
        self, table: str, identity_column: str, identity: str, model: type[_RecordT]
    ) -> _RecordT | None:
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT payload FROM {table} WHERE {identity_column} = ?", (identity,)
            ).fetchone()
        return model.model_validate_json(row["payload"]) if row else None

    def _list_sync(
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
        query += f" ORDER BY {order_by} LIMIT ?"
        with self._connect() as connection:
            rows = connection.execute(query, (*values, bounded_limit)).fetchall()
        return [model.model_validate_json(row["payload"]) for row in rows]

    async def put_case(self, case: EvalCase) -> EvalCase:
        """Persist an immutable case idempotently."""
        return await self._run(
            self._put_immutable_sync,
            table="evaluation_cases",
            identity=case.case_id,
            record=case,
            description="case",
        )

    async def get_case(self, case_id: str) -> EvalCase | None:
        """Load one case by identity."""
        return await self._run(
            self._get_sync, "evaluation_cases", "id", case_id, EvalCase
        )

    async def list_cases(self, *, limit: int = 100) -> list[EvalCase]:
        """List cases in stable identity order."""
        return await self._run(
            self._list_sync,
            table="evaluation_cases",
            model=EvalCase,
            limit=limit,
        )

    async def put_suite(self, suite: EvalSuite) -> EvalSuite:
        """Persist an immutable suite idempotently."""
        return await self._run(
            self._put_immutable_sync,
            table="evaluation_suites",
            identity=suite.suite_id,
            record=suite,
            description="suite",
        )

    async def get_suite(self, suite_id: str) -> EvalSuite | None:
        """Load one suite by identity."""
        return await self._run(
            self._get_sync, "evaluation_suites", "id", suite_id, EvalSuite
        )

    async def put_run(self, run: EvaluationRun) -> EvaluationRun:
        """Create or update a run lifecycle record."""
        await self._run(self._put_run_sync, run)
        return run

    def _put_run_sync(self, run: EvaluationRun) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO evaluation_runs (id, suite_id, status, started_at, payload)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    suite_id=excluded.suite_id,
                    status=excluded.status,
                    started_at=excluded.started_at,
                    payload=excluded.payload
                """,
                (
                    run.evaluation_run_id,
                    run.suite_id,
                    run.status.value,
                    run.started_at.isoformat(),
                    self._payload(run),
                ),
            )

    async def get_run(self, evaluation_run_id: str) -> EvaluationRun | None:
        """Load one evaluation run."""
        return await self._run(
            self._get_sync,
            "evaluation_runs",
            "id",
            evaluation_run_id,
            EvaluationRun,
        )

    async def list_runs(
        self, *, suite_id: str | None = None, limit: int = 100
    ) -> list[EvaluationRun]:
        """List recent runs, optionally restricted to a suite."""
        return await self._run(
            self._list_sync,
            table="evaluation_runs",
            model=EvaluationRun,
            where="suite_id = ?" if suite_id is not None else "",
            values=(suite_id,) if suite_id is not None else (),
            order_by="started_at DESC, id",
            limit=limit,
        )

    async def put_subject(self, subject: EvaluationSubject) -> EvaluationSubject:
        """Persist one immutable agent or workflow subject."""
        return await self._run(
            self._put_immutable_sync,
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
        return await self._run(
            self._get_sync,
            "evaluation_subjects",
            "id",
            subject_id,
            EvaluationSubject,
        )

    async def list_subjects(
        self, *, evaluation_run_id: str, limit: int = 100
    ) -> list[EvaluationSubject]:
        """List subjects belonging to a run."""
        return await self._run(
            self._list_sync,
            table="evaluation_subjects",
            model=EvaluationSubject,
            where="evaluation_run_id = ?",
            values=(evaluation_run_id,),
            limit=limit,
        )

    async def put_metric_result(self, result: MetricResult) -> MetricResult:
        """Persist one immutable, idempotent metric result."""
        return await self._run(
            self._put_immutable_sync,
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
        where = "evaluation_run_id = ?"
        values: tuple[Any, ...] = (evaluation_run_id,)
        if metric is not None:
            where += " AND metric = ?"
            values += (metric,)
        return await self._run(
            self._list_sync,
            table="evaluation_metric_results",
            model=MetricResult,
            where=where,
            values=values,
            limit=limit,
        )

    async def put_judge_result(self, result: JudgeResult) -> JudgeResult:
        """Persist one immutable, idempotent judge result."""
        return await self._run(
            self._put_immutable_sync,
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
        return await self._run(
            self._list_sync,
            table="evaluation_judge_results",
            model=JudgeResult,
            where="evaluation_run_id = ?",
            values=(evaluation_run_id,),
            limit=limit,
        )

    async def put_gate_result(self, result: GateResult) -> GateResult:
        """Persist one immutable, idempotent gate result."""
        return await self._run(
            self._put_immutable_sync,
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
        return await self._run(
            self._list_sync,
            table="evaluation_gate_results",
            model=GateResult,
            where="evaluation_run_id = ?",
            values=(evaluation_run_id,),
            limit=limit,
        )

    async def put_evaluation_result(self, result: EvaluationResult) -> EvaluationResult:
        """Persist one immutable terminal run summary."""
        return await self._run(
            self._put_result_sync,
            result,
        )

    def _put_result_sync(self, result: EvaluationResult) -> EvaluationResult:
        payload = self._payload(result)
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO evaluation_results "
                "(evaluation_run_id, payload) VALUES (?, ?)",
                (result.evaluation_run_id, payload),
            )
            row = connection.execute(
                "SELECT payload FROM evaluation_results WHERE evaluation_run_id = ?",
                (result.evaluation_run_id,),
            ).fetchone()
        if row is None:  # pragma: no cover - SQLite invariant
            raise RuntimeError("failed to persist evaluation result")
        if row["payload"] != payload:
            raise EvaluationConflictError(
                "evaluation result identity conflicts with stored data"
            )
        return result

    async def get_evaluation_result(
        self, evaluation_run_id: str
    ) -> EvaluationResult | None:
        """Load a terminal run summary."""
        return await self._run(
            self._get_sync,
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
        return await self._run(self._promote_baseline_sync, baseline)

    def _promote_baseline_sync(
        self, baseline: EvaluationBaseline
    ) -> EvaluationBaseline:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                rows = connection.execute(
                    "SELECT id, payload FROM evaluation_baselines "
                    "WHERE suite_id = ? AND active = 1",
                    (baseline.suite_id,),
                ).fetchall()
                for row in rows:
                    previous = EvaluationBaseline.model_validate_json(row["payload"])
                    inactive = previous.model_copy(update={"active": False})
                    connection.execute(
                        "UPDATE evaluation_baselines SET active = 0, payload = ? "
                        "WHERE id = ?",
                        (self._payload(inactive), previous.baseline_id),
                    )
                connection.execute(
                    """
                    INSERT INTO evaluation_baselines (
                        id, suite_id, source_evaluation_run_id, active,
                        promoted_at, payload
                    ) VALUES (?, ?, ?, 1, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        active=1,
                        promoted_at=excluded.promoted_at,
                        payload=excluded.payload
                    """,
                    (
                        baseline.baseline_id,
                        baseline.suite_id,
                        baseline.source_evaluation_run_id,
                        baseline.promoted_at.isoformat(),
                        self._payload(baseline),
                    ),
                )
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        return baseline

    async def get_active_baseline(self, suite_id: str) -> EvaluationBaseline | None:
        """Load the active baseline for a suite."""
        return await self._run(self._get_active_baseline_sync, suite_id)

    def _get_active_baseline_sync(self, suite_id: str) -> EvaluationBaseline | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM evaluation_baselines "
                "WHERE suite_id = ? AND active = 1",
                (suite_id,),
            ).fetchone()
        return EvaluationBaseline.model_validate_json(row["payload"]) if row else None

    async def list_baselines(
        self, *, suite_id: str, limit: int = 100
    ) -> list[EvaluationBaseline]:
        """List baseline promotion history for a suite."""
        return await self._run(
            self._list_sync,
            table="evaluation_baselines",
            model=EvaluationBaseline,
            where="suite_id = ?",
            values=(suite_id,),
            order_by="promoted_at DESC, id",
            limit=limit,
        )

    async def put_job(self, job: EvaluationJob) -> EvaluationJob:
        """Create a durable job idempotently without reverting its lifecycle."""
        return await self._run(self._put_job_sync, job)

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

    @staticmethod
    def _write_job_row(connection: sqlite3.Connection, job: EvaluationJob) -> None:
        connection.execute(
            "UPDATE evaluation_jobs SET status = ?, available_at = ?, "
            "lease_expires_at = ?, payload = ? WHERE id = ?",
            (
                job.status.value,
                job.available_at.isoformat(),
                (
                    job.lease_expires_at.isoformat()
                    if job.lease_expires_at is not None
                    else None
                ),
                SQLiteEvaluationStore._payload(job),
                job.job_id,
            ),
        )

    def _put_job_sync(self, job: EvaluationJob) -> EvaluationJob:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "INSERT INTO evaluation_jobs "
                    "(id, status, available_at, lease_expires_at, payload) "
                    "VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING",
                    (
                        job.job_id,
                        job.status.value,
                        job.available_at.isoformat(),
                        (
                            job.lease_expires_at.isoformat()
                            if job.lease_expires_at is not None
                            else None
                        ),
                        self._payload(job),
                    ),
                )
                row = connection.execute(
                    "SELECT payload FROM evaluation_jobs WHERE id = ?",
                    (job.job_id,),
                ).fetchone()
                existing = EvaluationJob.model_validate_json(row["payload"])
                if not self._same_job_identity(existing, job):
                    raise EvaluationConflictError(
                        "job identity conflicts with stored data"
                    )
                connection.commit()
                return existing
            except BaseException:
                connection.rollback()
                raise

    async def get_job(self, job_id: str) -> EvaluationJob | None:
        """Load one job."""
        return await self._run(
            self._get_sync, "evaluation_jobs", "id", job_id, EvaluationJob
        )

    async def list_jobs(
        self, *, status: JobStatus | None = None, limit: int = 100
    ) -> list[EvaluationJob]:
        """List jobs, optionally filtered by status."""
        return await self._run(
            self._list_sync,
            table="evaluation_jobs",
            model=EvaluationJob,
            where="status = ?" if status is not None else "",
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
        """Atomically lease one ready job, including an expired prior lease."""
        return await self._run(
            self._lease_job_sync,
            worker_id,
            self._aware_utc(now, field="now"),
            lease_seconds,
        )

    def _lease_job_sync(
        self, worker_id: str, now: datetime, lease_seconds: float
    ) -> EvaluationJob | None:
        if not worker_id.strip() or len(worker_id) > 256:
            raise ValueError("worker_id must be non-empty and bounded")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                while True:
                    row = connection.execute(
                        "SELECT payload FROM evaluation_jobs WHERE "
                        "(status = ? AND available_at <= ?) OR "
                        "(status = ? AND lease_expires_at <= ?) "
                        "ORDER BY available_at, id LIMIT 1",
                        (
                            JobStatus.PENDING.value,
                            now.isoformat(),
                            JobStatus.LEASED.value,
                            now.isoformat(),
                        ),
                    ).fetchone()
                    if row is None:
                        connection.commit()
                        return None
                    job = EvaluationJob.model_validate_json(row["payload"])
                    if job.attempt_count >= job.max_attempts:
                        exhausted = job.model_copy(
                            update={
                                "status": JobStatus.DEAD_LETTER,
                                "lease_owner": None,
                                "lease_expires_at": None,
                                "error_type": "LeaseExpired",
                                "updated_at": now,
                            }
                        )
                        self._write_job_row(connection, exhausted)
                        continue
                    leased = job.model_copy(
                        update={
                            "status": JobStatus.LEASED,
                            "lease_owner": worker_id,
                            "lease_expires_at": now + timedelta(seconds=lease_seconds),
                            "attempt_count": job.attempt_count + 1,
                            "error_type": None,
                            "updated_at": now,
                        }
                    )
                    self._write_job_row(connection, leased)
                    connection.commit()
                    return leased
            except BaseException:
                connection.rollback()
                raise

    def _load_leased_job(
        self, connection: sqlite3.Connection, job_id: str, worker_id: str
    ) -> EvaluationJob:
        row = connection.execute(
            "SELECT payload FROM evaluation_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if row is None:
            raise EvaluationConflictError("job does not exist")
        job = EvaluationJob.model_validate_json(row["payload"])
        if job.status is not JobStatus.LEASED or job.lease_owner != worker_id:
            raise EvaluationConflictError("job lease owner does not match")
        return job

    async def complete_job(
        self, *, job_id: str, worker_id: str, now: datetime
    ) -> EvaluationJob:
        """Complete an actively leased job atomically."""
        return await self._run(
            self._complete_job_sync,
            job_id,
            worker_id,
            self._aware_utc(now, field="now"),
        )

    def _complete_job_sync(
        self, job_id: str, worker_id: str, now: datetime
    ) -> EvaluationJob:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                job = self._load_leased_job(connection, job_id, worker_id)
                completed = job.model_copy(
                    update={
                        "status": JobStatus.COMPLETED,
                        "lease_owner": None,
                        "lease_expires_at": None,
                        "error_type": None,
                        "updated_at": now,
                    }
                )
                self._write_job_row(connection, completed)
                connection.commit()
                return completed
            except BaseException:
                connection.rollback()
                raise

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
        return await self._run(
            self._retry_job_sync,
            job_id,
            worker_id,
            self._aware_utc(now, field="now"),
            error_type,
            retry_delay_seconds,
        )

    def _retry_job_sync(
        self,
        job_id: str,
        worker_id: str,
        now: datetime,
        error_type: str,
        retry_delay_seconds: float,
    ) -> EvaluationJob:
        if not error_type.strip() or len(error_type) > 256:
            raise ValueError("error_type must be non-empty and bounded")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                job = self._load_leased_job(connection, job_id, worker_id)
                exhausted = job.attempt_count >= job.max_attempts
                updated = job.model_copy(
                    update={
                        "status": (
                            JobStatus.DEAD_LETTER if exhausted else JobStatus.PENDING
                        ),
                        "available_at": now + timedelta(seconds=retry_delay_seconds),
                        "lease_owner": None,
                        "lease_expires_at": None,
                        "error_type": error_type if exhausted else None,
                        "updated_at": now,
                    }
                )
                self._write_job_row(connection, updated)
                connection.commit()
                return updated
            except BaseException:
                connection.rollback()
                raise

    async def put_attempt(self, attempt: EvaluationAttempt) -> EvaluationAttempt:
        """Persist one immutable job attempt and enforce its natural key."""
        return await self._run(self._put_attempt_sync, attempt)

    def _put_attempt_sync(self, attempt: EvaluationAttempt) -> EvaluationAttempt:
        payload = self._payload(attempt)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                try:
                    connection.execute(
                        "INSERT INTO evaluation_attempts "
                        "(id, job_id, attempt_number, payload) VALUES (?, ?, ?, ?)",
                        (
                            attempt.attempt_id,
                            attempt.job_id,
                            attempt.attempt_number,
                            payload,
                        ),
                    )
                except sqlite3.IntegrityError:
                    row = connection.execute(
                        "SELECT id, payload FROM evaluation_attempts "
                        "WHERE job_id = ? AND attempt_number = ?",
                        (attempt.job_id, attempt.attempt_number),
                    ).fetchone()
                    if row is None or row["id"] != attempt.attempt_id:
                        raise EvaluationConflictError(
                            "attempt number conflicts with stored attempt"
                        ) from None
                    if row["payload"] != payload:
                        raise EvaluationConflictError(
                            "attempt identity conflicts with stored data"
                        ) from None
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        return attempt

    async def list_attempts(
        self, *, job_id: str, limit: int = 100
    ) -> list[EvaluationAttempt]:
        """List attempts for one job in attempt order."""
        return await self._run(
            self._list_sync,
            table="evaluation_attempts",
            model=EvaluationAttempt,
            where="job_id = ?",
            values=(job_id,),
            order_by="attempt_number, id",
            limit=limit,
        )


__all__ = ["SQLiteEvaluationStore"]
