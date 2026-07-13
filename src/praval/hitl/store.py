"""SQLite-backed persistence for HITL interventions and suspended runs."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .models import (
    InterventionDecision,
    InterventionRequest,
    InterventionStatus,
    SuspendedRunState,
)

_DEFAULT_DB_PATH = os.path.expanduser("~/.praval/hitl.db")


class HITLStore:
    """Durable storage for intervention queues and paused runs."""

    def __init__(self, db_path: Optional[str] = None):
        resolved_path = db_path or os.getenv("PRAVAL_HITL_DB_PATH") or _DEFAULT_DB_PATH
        self.db_path = os.path.expanduser(resolved_path)
        self._lock = threading.RLock()
        self._initialize_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _initialize_db(self) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS interventions (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    provider_name TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    tool_call_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    decision TEXT,
                    reason TEXT,
                    reviewer TEXT,
                    original_args_json TEXT NOT NULL,
                    edited_args_json TEXT,
                    risk_level TEXT NOT NULL,
                    approval_reason TEXT,
                    requested_at INTEGER NOT NULL,
                    decided_at INTEGER,
                    expires_at INTEGER,
                    trace_id TEXT,
                    metadata_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS suspended_runs (
                    run_id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    provider_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_interventions_status_requested_at "
                "ON interventions(status, requested_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_interventions_run_id "
                "ON interventions(run_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_interventions_agent_name "
                "ON interventions(agent_name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_suspended_runs_status "
                "ON suspended_runs(status)"
            )
            conn.commit()

    @staticmethod
    def _now_ts() -> int:
        return int(time.time())

    def create_intervention(
        self,
        *,
        run_id: str,
        agent_name: str,
        provider_name: str,
        tool_name: str,
        tool_call_id: str,
        original_args: Dict[str, Any],
        risk_level: str = "low",
        approval_reason: str = "",
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expires_in_seconds: int = 24 * 60 * 60,
    ) -> InterventionRequest:
        """Create a new pending intervention."""
        intervention_id = str(uuid.uuid4())
        requested_at = self._now_ts()
        expires_at = (
            requested_at + expires_in_seconds if expires_in_seconds > 0 else None
        )

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO interventions (
                    id, run_id, agent_name, provider_name, tool_name, tool_call_id,
                    status, decision, reason, reviewer,
                    original_args_json, edited_args_json,
                    risk_level, approval_reason,
                    requested_at, decided_at, expires_at,
                    trace_id, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    intervention_id,
                    run_id,
                    agent_name,
                    provider_name,
                    tool_name,
                    tool_call_id,
                    InterventionStatus.PENDING.value,
                    None,
                    "",
                    "",
                    json.dumps(original_args or {}),
                    None,
                    risk_level,
                    approval_reason,
                    requested_at,
                    None,
                    expires_at,
                    trace_id,
                    json.dumps(metadata or {}),
                ),
            )
            conn.commit()

        req = self.get_intervention(intervention_id)
        if req is None:
            raise RuntimeError("Failed to create intervention")
        return req

    def get_intervention(self, intervention_id: str) -> Optional[InterventionRequest]:
        """Fetch a single intervention by id."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM interventions WHERE id = ?", (intervention_id,)
            ).fetchone()
        return self._row_to_intervention(row) if row else None

    def list_interventions(
        self,
        *,
        status: Optional[InterventionStatus] = None,
        run_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[InterventionRequest]:
        """List interventions with optional filters."""
        query = "SELECT * FROM interventions WHERE 1=1"
        params: List[Any] = []

        if status is not None:
            query += " AND status = ?"
            params.append(status.value)
        if run_id is not None:
            query += " AND run_id = ?"
            params.append(run_id)
        if agent_name is not None:
            query += " AND agent_name = ?"
            params.append(agent_name)

        query += " ORDER BY requested_at DESC LIMIT ?"
        params.append(max(1, limit))

        with self._lock, self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        return [self._row_to_intervention(row) for row in rows]

    def list_pending_interventions(
        self,
        *,
        run_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[InterventionRequest]:
        """List pending interventions with optional filters."""
        self.expire_overdue_interventions()
        return self.list_interventions(
            status=InterventionStatus.PENDING,
            run_id=run_id,
            agent_name=agent_name,
            limit=limit,
        )

    def decide_intervention(
        self,
        intervention_id: str,
        *,
        decision: InterventionDecision,
        reviewer: str,
        reason: str = "",
        edited_args: Optional[Dict[str, Any]] = None,
    ) -> InterventionRequest:
        """Apply a human decision for a pending intervention."""
        decided_at = self._now_ts()
        edited_args_json = json.dumps(edited_args) if edited_args is not None else None

        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE interventions
                SET status = ?,
                    decision = ?,
                    reason = ?,
                    reviewer = ?,
                    edited_args_json = ?,
                    decided_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    (
                        InterventionStatus.REJECTED.value
                        if decision == InterventionDecision.REJECT
                        else InterventionStatus.APPROVED.value
                    ),
                    decision.value,
                    reason,
                    reviewer,
                    edited_args_json,
                    decided_at,
                    intervention_id,
                    InterventionStatus.PENDING.value,
                ),
            )
            if cursor.rowcount == 0:
                existing = conn.execute(
                    "SELECT status FROM interventions WHERE id = ?", (intervention_id,)
                ).fetchone()
                if existing is None:
                    raise ValueError(f"Intervention '{intervention_id}' not found")
                raise ValueError(
                    f"Intervention '{intervention_id}' is not pending "
                    f"(status={existing['status']})"
                )
            conn.commit()

        req = self.get_intervention(intervention_id)
        if req is None:
            raise RuntimeError("Failed to load decided intervention")
        return req

    def expire_overdue_interventions(self) -> int:
        """Mark expired pending interventions as EXPIRED."""
        now_ts = self._now_ts()
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE interventions
                SET status = ?
                WHERE status = ? AND expires_at IS NOT NULL AND expires_at < ?
                """,
                (
                    InterventionStatus.EXPIRED.value,
                    InterventionStatus.PENDING.value,
                    now_ts,
                ),
            )
            conn.commit()
            return int(cursor.rowcount)

    def upsert_suspended_run(
        self,
        *,
        run_id: str,
        agent_name: str,
        provider_name: str,
        state: Dict[str, Any],
        status: str = "pending",
    ) -> SuspendedRunState:
        """Create or update suspended run state."""
        now_ts = self._now_ts()
        state_json = json.dumps(state or {})

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO suspended_runs (
                    run_id, agent_name, provider_name, status, state_json, created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id)
                DO UPDATE SET
                    agent_name=excluded.agent_name,
                    provider_name=excluded.provider_name,
                    status=excluded.status,
                    state_json=excluded.state_json,
                    updated_at=excluded.updated_at
                """,
                (
                    run_id,
                    agent_name,
                    provider_name,
                    status,
                    state_json,
                    now_ts,
                    now_ts,
                ),
            )
            conn.commit()

        suspended = self.get_suspended_run(run_id)
        if suspended is None:
            raise RuntimeError("Failed to upsert suspended run")
        return suspended

    def get_suspended_run(self, run_id: str) -> Optional[SuspendedRunState]:
        """Get suspended run state by run_id."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM suspended_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return self._row_to_suspended_run(row) if row else None

    def update_suspended_run_status(
        self, run_id: str, status: str, state: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update run status and optional state payload."""
        now_ts = self._now_ts()
        with self._lock, self._connect() as conn:
            if state is None:
                conn.execute(
                    """
                    UPDATE suspended_runs
                    SET status = ?, updated_at = ?
                    WHERE run_id = ?
                    """,
                    (status, now_ts, run_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE suspended_runs
                    SET status = ?, state_json = ?, updated_at = ?
                    WHERE run_id = ?
                    """,
                    (status, json.dumps(state), now_ts, run_id),
                )
            conn.commit()

    def delete_suspended_run(self, run_id: str) -> None:
        """Delete suspended run state."""
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM suspended_runs WHERE run_id = ?", (run_id,))
            conn.commit()

    def _row_to_intervention(self, row: sqlite3.Row) -> InterventionRequest:
        decision_raw = row["decision"]
        return InterventionRequest(
            id=row["id"],
            run_id=row["run_id"],
            agent_name=row["agent_name"],
            provider_name=row["provider_name"],
            tool_name=row["tool_name"],
            tool_call_id=row["tool_call_id"],
            status=InterventionStatus(row["status"]),
            decision=InterventionDecision(decision_raw) if decision_raw else None,
            reason=row["reason"] or "",
            reviewer=row["reviewer"] or "",
            original_args=json.loads(row["original_args_json"] or "{}"),
            edited_args=(
                json.loads(row["edited_args_json"])
                if row["edited_args_json"] is not None
                else None
            ),
            risk_level=row["risk_level"] or "low",
            approval_reason=row["approval_reason"] or "",
            requested_at=datetime.fromtimestamp(int(row["requested_at"]), timezone.utc),
            decided_at=(
                datetime.fromtimestamp(int(row["decided_at"]), timezone.utc)
                if row["decided_at"] is not None
                else None
            ),
            expires_at=(
                datetime.fromtimestamp(int(row["expires_at"]), timezone.utc)
                if row["expires_at"] is not None
                else None
            ),
            trace_id=row["trace_id"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def _row_to_suspended_run(self, row: sqlite3.Row) -> SuspendedRunState:
        return SuspendedRunState(
            run_id=row["run_id"],
            agent_name=row["agent_name"],
            provider_name=row["provider_name"],
            status=row["status"],
            state=json.loads(row["state_json"] or "{}"),
            created_at=datetime.fromtimestamp(int(row["created_at"]), timezone.utc),
            updated_at=datetime.fromtimestamp(int(row["updated_at"]), timezone.utc),
        )


_store_lock = threading.RLock()
_store_by_path: Dict[str, HITLStore] = {}


def get_hitl_store(db_path: Optional[str] = None) -> HITLStore:
    """Get a shared HITL store instance by path."""
    resolved_path = os.path.expanduser(
        db_path or os.getenv("PRAVAL_HITL_DB_PATH") or _DEFAULT_DB_PATH
    )
    with _store_lock:
        store = _store_by_path.get(resolved_path)
        if store is None:
            store = HITLStore(resolved_path)
            _store_by_path[resolved_path] = store
        return store


def reset_hitl_stores() -> None:
    """Reset shared store cache (primarily for tests)."""
    with _store_lock:
        _store_by_path.clear()
