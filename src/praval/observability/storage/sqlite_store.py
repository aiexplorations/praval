"""
SQLite storage backend for traces.

Stores traces locally for querying and analysis.
"""

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence


class _StoredValue(Protocol):
    """Enum-like value accepted by the legacy diagnostic store."""

    value: str


class _StoredEvent(Protocol):
    """Serializable event accepted by the legacy diagnostic store."""

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-compatible event."""
        ...


class StorableSpan(Protocol):
    """Temporary input boundary retained until the O5 exporter migration."""

    span_id: str
    trace_id: str
    parent_span_id: str | None
    name: str
    kind: _StoredValue
    start_time: int
    end_time: int | None
    attributes: Dict[str, Any]
    events: Sequence[_StoredEvent]
    status: _StoredValue
    status_message: str

    def duration_ms(self) -> float:
        """Return the completed duration in milliseconds."""
        ...


logger = logging.getLogger(__name__)


class SQLiteTraceStore:
    """SQLite-based trace storage.

    Stores spans in a local SQLite database with OpenTelemetry schema.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS spans (
        span_id TEXT PRIMARY KEY,
        trace_id TEXT NOT NULL,
        parent_span_id TEXT,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        start_time INTEGER NOT NULL,
        end_time INTEGER,
        duration_ms REAL,
        attributes TEXT,
        events TEXT,
        status TEXT,
        status_message TEXT,
        resource_attributes TEXT,
        resource_schema_url TEXT,
        scope_name TEXT,
        scope_version TEXT,
        scope_schema_url TEXT,
        scope_attributes TEXT,
        links TEXT,
        trace_state TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans(trace_id);
    CREATE INDEX IF NOT EXISTS idx_spans_parent ON spans(parent_span_id);
    CREATE INDEX IF NOT EXISTS idx_spans_name ON spans(name);
    CREATE INDEX IF NOT EXISTS idx_spans_start_time ON spans(start_time DESC);
    CREATE INDEX IF NOT EXISTS idx_spans_status ON spans(status);
    """

    def __init__(self, db_path: str, *, busy_timeout_ms: int = 5000):
        """Initialize SQLite trace store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path).expanduser()
        self.busy_timeout_ms = max(1, busy_timeout_ms)

        self._lock = threading.RLock()
        self._init_error = None

        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_schema()
        except (OSError, sqlite3.OperationalError) as e:
            # Defer hard failure until a connection is actually requested.
            self._init_error = e
            logger.warning(
                f"Failed to initialize SQLite trace store at {self.db_path}: {e}"
            )

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection.

        Returns:
            SQLite connection
        """
        if self._init_error is not None:
            raise sqlite3.OperationalError(
                f"SQLite trace store unavailable at {self.db_path}: {self._init_error}"
            )
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.executescript(self.SCHEMA)
                existing = {
                    row["name"] for row in conn.execute("PRAGMA table_info(spans)")
                }
                migrations = {
                    "resource_attributes": "TEXT",
                    "resource_schema_url": "TEXT",
                    "scope_name": "TEXT",
                    "scope_version": "TEXT",
                    "scope_schema_url": "TEXT",
                    "scope_attributes": "TEXT",
                    "links": "TEXT",
                    "trace_state": "TEXT",
                }
                for name, column_type in migrations.items():
                    if name not in existing:
                        conn.execute(
                            f"ALTER TABLE spans ADD COLUMN {name} {column_type}"
                        )
                conn.commit()
            finally:
                conn.close()

    def store_span(self, span: StorableSpan) -> None:
        """Store a completed span.

        Args:
            span: Span to store
        """
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO spans
                    (span_id, trace_id, parent_span_id, name, kind,
                     start_time, end_time, duration_ms,
                     attributes, events, status, status_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        span.span_id,
                        span.trace_id,
                        span.parent_span_id,
                        span.name,
                        span.kind.value,
                        span.start_time,
                        span.end_time,
                        span.duration_ms(),
                        json.dumps(span.attributes),
                        json.dumps([e.to_dict() for e in span.events]),
                        span.status.value,
                        span.status_message,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def store_spans(self, spans: Sequence[StorableSpan]) -> None:
        """Store multiple spans (batch operation).

        Args:
            spans: List of spans to store
        """
        if not spans:
            return

        with self._lock:
            conn = self._get_connection()
            try:
                for span in spans:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO spans
                        (span_id, trace_id, parent_span_id, name, kind,
                         start_time, end_time, duration_ms,
                         attributes, events, status, status_message)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            span.span_id,
                            span.trace_id,
                            span.parent_span_id,
                            span.name,
                            span.kind.value,
                            span.start_time,
                            span.end_time,
                            span.duration_ms(),
                            json.dumps(span.attributes),
                            json.dumps([e.to_dict() for e in span.events]),
                            span.status.value,
                            span.status_message,
                        ),
                    )
                conn.commit()
            finally:
                conn.close()

    def store_span_records(self, records: Sequence[Dict[str, Any]]) -> None:
        """Store normalized records produced by the official SDK exporter."""
        if not records:
            return
        columns = (
            "span_id",
            "trace_id",
            "parent_span_id",
            "name",
            "kind",
            "start_time",
            "end_time",
            "duration_ms",
            "attributes",
            "events",
            "status",
            "status_message",
            "resource_attributes",
            "resource_schema_url",
            "scope_name",
            "scope_version",
            "scope_schema_url",
            "scope_attributes",
            "links",
            "trace_state",
        )
        json_columns = {
            "attributes",
            "events",
            "resource_attributes",
            "scope_attributes",
            "links",
        }
        values = []
        for record in records:
            values.append(
                tuple(
                    (
                        json.dumps(record.get(column), sort_keys=True)
                        if column in json_columns
                        else record.get(column)
                    )
                    for column in columns
                )
            )
        placeholders = ", ".join("?" for _ in columns)
        with self._lock:
            conn = self._get_connection()
            try:
                conn.executemany(
                    f"INSERT OR REPLACE INTO spans ({', '.join(columns)}) "
                    f"VALUES ({placeholders})",
                    values,
                )
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def _parse_row(row: sqlite3.Row) -> Dict[str, Any]:
        span = dict(row)
        for column, fallback in (
            ("attributes", {}),
            ("events", []),
            ("resource_attributes", {}),
            ("scope_attributes", {}),
            ("links", []),
        ):
            if column in span:
                span[column] = (
                    json.loads(span[column]) if span[column] is not None else fallback
                )
        return span

    def get_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """Get all spans for a trace.

        Args:
            trace_id: Trace identifier

        Returns:
            List of span dictionaries
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM spans
                WHERE trace_id = ?
                ORDER BY start_time
            """,
                (trace_id,),
            )

            return [self._parse_row(row) for row in cursor]
        finally:
            conn.close()

    def get_recent_traces(self, limit: int = 10) -> List[str]:
        """Get recent trace IDs.

        Args:
            limit: Maximum number of trace IDs to return

        Returns:
            List of trace IDs (most recent first)
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT trace_id
                FROM spans
                GROUP BY trace_id
                ORDER BY MAX(start_time) DESC, trace_id DESC
                LIMIT ?
            """,
                (limit,),
            )

            return [row["trace_id"] for row in cursor]
        finally:
            conn.close()

    def find_spans(
        self,
        agent_name: Optional[str] = None,
        status: Optional[str] = None,
        min_duration_ms: Optional[float] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query spans with filters.

        Args:
            agent_name: Filter by agent name (matches span name)
            status: Filter by status (OK, ERROR, UNSET)
            min_duration_ms: Minimum duration in milliseconds
            limit: Maximum number of spans to return

        Returns:
            List of span dictionaries
        """
        query = "SELECT * FROM spans WHERE 1=1"
        params: List[Any] = []

        if agent_name:
            query += " AND name LIKE ?"
            params.append(f"%{agent_name}%")

        if status:
            query += " AND status = ?"
            params.append(status.upper())

        if min_duration_ms is not None:
            query += " AND duration_ms >= ?"
            params.append(min_duration_ms)

        query += " ORDER BY start_time DESC LIMIT ?"
        params.append(limit)

        conn = self._get_connection()
        try:
            cursor = conn.execute(query, params)

            return [self._parse_row(row) for row in cursor]
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics.

        Returns:
            Dictionary with storage stats
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(DISTINCT trace_id) as trace_count,
                    COUNT(*) as span_count,
                    AVG(duration_ms) as avg_duration_ms,
                    MAX(start_time) as latest_span_time
                FROM spans
            """
            )

            row = cursor.fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def cleanup_old_traces(self, days: int = 30) -> int:
        """Delete traces older than specified days.

        Args:
            days: Number of days to retain

        Returns:
            Number of spans deleted
        """
        return self.cleanup_traces(max_age_days=days)

    def cleanup_traces(
        self,
        *,
        max_age_days: int | None = None,
        keep_last_n: int | None = None,
        now_ns: int | None = None,
    ) -> int:
        """Delete complete traces outside age and count retention bounds."""
        if max_age_days is not None and max_age_days < 0:
            raise ValueError("max_age_days cannot be negative")
        if keep_last_n is not None and keep_last_n < 0:
            raise ValueError("keep_last_n cannot be negative")
        if max_age_days is None and keep_last_n is None:
            return 0

        with self._lock:
            conn = self._get_connection()
            try:
                expired: set[str] = set()
                if max_age_days is not None:
                    current_ns = now_ns if now_ns is not None else time.time_ns()
                    cutoff_ns = current_ns - (
                        max_age_days * 24 * 60 * 60 * 1_000_000_000
                    )
                    expired.update(
                        row["trace_id"]
                        for row in conn.execute(
                            """
                            SELECT trace_id
                            FROM spans
                            GROUP BY trace_id
                            HAVING MAX(start_time) < ?
                            """,
                            (cutoff_ns,),
                        )
                    )
                if keep_last_n is not None:
                    retained_order = [
                        row["trace_id"]
                        for row in conn.execute(
                            """
                            SELECT trace_id
                            FROM spans
                            GROUP BY trace_id
                            ORDER BY MAX(start_time) DESC, trace_id DESC
                            """
                        )
                        if row["trace_id"] not in expired
                    ]
                    expired.update(retained_order[keep_last_n:])
                if not expired:
                    return 0
                cursor = conn.executemany(
                    "DELETE FROM spans WHERE trace_id = ?",
                    ((trace_id,) for trace_id in sorted(expired)),
                )
                deleted = cursor.rowcount
                conn.commit()
                return deleted
            finally:
                conn.close()


# Global trace store instance
_global_store: Optional[SQLiteTraceStore] = None


def get_trace_store() -> SQLiteTraceStore:
    """Get the global trace store instance.

    Returns:
        SQLiteTraceStore instance
    """
    if _global_store is None:
        from praval.core.exceptions import PravalConfigurationError

        raise PravalConfigurationError(
            "the local diagnostic exporter is not enabled for the active pipeline"
        )

    return _global_store


def set_trace_store(store: SQLiteTraceStore | None) -> None:
    """Bind the store owned by the active explicit lifecycle."""
    global _global_store
    _global_store = store


def reset_trace_store() -> None:
    """Reset the global trace store to None.

    This is primarily used for testing to ensure test isolation.
    """
    global _global_store
    _global_store = None
