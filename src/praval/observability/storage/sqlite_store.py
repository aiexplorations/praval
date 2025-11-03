"""
SQLite storage backend for traces.

Stores traces locally for querying and analysis.
"""

import json
import sqlite3
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..tracing.span import Span


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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans(trace_id);
    CREATE INDEX IF NOT EXISTS idx_spans_parent ON spans(parent_span_id);
    CREATE INDEX IF NOT EXISTS idx_spans_name ON spans(name);
    CREATE INDEX IF NOT EXISTS idx_spans_start_time ON spans(start_time DESC);
    CREATE INDEX IF NOT EXISTS idx_spans_status ON spans(status);
    """

    def __init__(self, db_path: str):
        """Initialize SQLite trace store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection.

        Returns:
            SQLite connection
        """
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.executescript(self.SCHEMA)
                conn.commit()
            finally:
                conn.close()

    def store_span(self, span: Span) -> None:
        """Store a completed span.

        Args:
            span: Span to store
        """
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO spans
                    (span_id, trace_id, parent_span_id, name, kind,
                     start_time, end_time, duration_ms,
                     attributes, events, status, status_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
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
                    span.status_message
                ))
                conn.commit()
            finally:
                conn.close()

    def store_spans(self, spans: List[Span]) -> None:
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
                    conn.execute("""
                        INSERT OR REPLACE INTO spans
                        (span_id, trace_id, parent_span_id, name, kind,
                         start_time, end_time, duration_ms,
                         attributes, events, status, status_message)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
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
                        span.status_message
                    ))
                conn.commit()
            finally:
                conn.close()

    def get_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """Get all spans for a trace.

        Args:
            trace_id: Trace identifier

        Returns:
            List of span dictionaries
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT * FROM spans
                WHERE trace_id = ?
                ORDER BY start_time
            """, (trace_id,))

            spans = []
            for row in cursor:
                span_dict = dict(row)
                # Parse JSON fields
                span_dict['attributes'] = json.loads(span_dict['attributes'])
                span_dict['events'] = json.loads(span_dict['events'])
                spans.append(span_dict)

            return spans
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
            cursor = conn.execute("""
                SELECT DISTINCT trace_id
                FROM spans
                ORDER BY start_time DESC
                LIMIT ?
            """, (limit,))

            return [row['trace_id'] for row in cursor]
        finally:
            conn.close()

    def find_spans(
        self,
        agent_name: Optional[str] = None,
        status: Optional[str] = None,
        min_duration_ms: Optional[float] = None,
        limit: int = 100
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
        params = []

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

            spans = []
            for row in cursor:
                span_dict = dict(row)
                span_dict['attributes'] = json.loads(span_dict['attributes'])
                span_dict['events'] = json.loads(span_dict['events'])
                spans.append(span_dict)

            return spans
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics.

        Returns:
            Dictionary with storage stats
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT
                    COUNT(DISTINCT trace_id) as trace_count,
                    COUNT(*) as span_count,
                    AVG(duration_ms) as avg_duration_ms,
                    MAX(start_time) as latest_span_time
                FROM spans
            """)

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
        import time

        # Calculate cutoff time (nanoseconds)
        cutoff_ns = (time.time() - (days * 24 * 60 * 60)) * 1_000_000_000

        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute("""
                    DELETE FROM spans
                    WHERE start_time < ?
                """, (int(cutoff_ns),))

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
    global _global_store

    if _global_store is None:
        from ..config import get_config
        config = get_config()
        _global_store = SQLiteTraceStore(config.storage_path)

    return _global_store
