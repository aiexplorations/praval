"""
Tests for SQLite trace storage.
"""

import tempfile
import os
import pytest
from pathlib import Path

from praval.observability.storage.sqlite_store import SQLiteTraceStore
from praval.observability.tracing.span import Span, SpanKind, SpanStatus


class TestSQLiteTraceStore:
    """Tests for SQLiteTraceStore."""

    def setup_method(self):
        """Create temporary database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_traces.db")
        self.store = SQLiteTraceStore(self.db_path)

    def teardown_method(self):
        """Clean up temporary database."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_store_initialization(self):
        """Test that store initializes database."""
        assert Path(self.db_path).exists()

    def test_store_span(self):
        """Test storing a single span."""
        span = Span(
            name="test.operation",
            trace_id="trace123",
            span_id="span456"
        )
        span.set_attribute("key", "value")
        span.end()

        self.store.store_span(span)

        # Verify stored
        traces = self.store.get_recent_traces(limit=1)
        assert len(traces) == 1
        assert traces[0] == "trace123"

    def test_store_multiple_spans(self):
        """Test storing multiple spans."""
        spans = [
            Span(name="span1", trace_id="trace1", span_id="span1"),
            Span(name="span2", trace_id="trace1", span_id="span2"),
            Span(name="span3", trace_id="trace2", span_id="span3")
        ]

        for span in spans:
            span.end()

        self.store.store_spans(spans)

        # Should have 2 distinct traces
        recent = self.store.get_recent_traces(limit=10)
        assert len(recent) == 2
        assert "trace1" in recent
        assert "trace2" in recent

    def test_get_trace(self):
        """Test retrieving all spans for a trace."""
        trace_id = "trace123"

        # Create parent and child spans
        parent = Span(
            name="parent",
            trace_id=trace_id,
            span_id="parent456"
        )
        parent.end()

        child = Span(
            name="child",
            trace_id=trace_id,
            span_id="child789",
            parent_span_id="parent456"
        )
        child.end()

        self.store.store_span(parent)
        self.store.store_span(child)

        # Retrieve trace
        spans = self.store.get_trace(trace_id)

        assert len(spans) == 2
        assert spans[0]["name"] == "parent"
        assert spans[1]["name"] == "child"
        assert spans[1]["parent_span_id"] == "parent456"

    def test_get_trace_empty(self):
        """Test retrieving non-existent trace."""
        spans = self.store.get_trace("nonexistent")
        assert len(spans) == 0

    def test_get_recent_traces(self):
        """Test getting recent trace IDs."""
        # Create several traces
        for i in range(5):
            span = Span(name=f"span{i}", trace_id=f"trace{i}", span_id=f"span{i}")
            span.end()
            self.store.store_span(span)

        # Get recent traces
        recent = self.store.get_recent_traces(limit=3)

        assert len(recent) == 3
        # Most recent should be first
        assert recent[0] == "trace4"

    def test_find_spans_by_name(self):
        """Test finding spans by agent name."""
        spans = [
            Span(name="agent.researcher.execute", trace_id="t1", span_id="s1"),
            Span(name="agent.analyzer.execute", trace_id="t2", span_id="s2"),
            Span(name="llm.chat", trace_id="t3", span_id="s3")
        ]

        for span in spans:
            span.end()
            self.store.store_span(span)

        # Find researcher spans
        results = self.store.find_spans(agent_name="researcher")

        assert len(results) == 1
        assert "researcher" in results[0]["name"]

    def test_find_spans_by_status(self):
        """Test finding spans by status."""
        span_ok = Span(name="success", trace_id="t1", span_id="s1")
        span_ok.set_status("ok")
        span_ok.end()

        span_error = Span(name="failure", trace_id="t2", span_id="s2")
        span_error.set_status("error")
        span_error.end()

        self.store.store_span(span_ok)
        self.store.store_span(span_error)

        # Find error spans
        errors = self.store.find_spans(status="ERROR")
        assert len(errors) == 1
        assert errors[0]["status"] == "ERROR"

        # Find successful spans
        successes = self.store.find_spans(status="OK")
        assert len(successes) == 1
        assert successes[0]["status"] == "OK"

    def test_find_spans_by_duration(self):
        """Test finding spans by minimum duration."""
        import time

        # Create slow span
        slow = Span(name="slow", trace_id="t1", span_id="s1")
        time.sleep(0.02)  # 20ms
        slow.end()

        # Create fast span
        fast = Span(name="fast", trace_id="t2", span_id="s2")
        fast.end()

        self.store.store_span(slow)
        self.store.store_span(fast)

        # Find spans longer than 10ms
        results = self.store.find_spans(min_duration_ms=10)

        assert len(results) >= 1
        assert any(r["name"] == "slow" for r in results)

    def test_get_stats(self):
        """Test getting storage statistics."""
        # Create some traces
        for i in range(3):
            span = Span(name=f"span{i}", trace_id=f"trace{i}", span_id=f"span{i}")
            span.end()
            self.store.store_span(span)

        stats = self.store.get_stats()

        assert stats["trace_count"] == 3
        assert stats["span_count"] == 3
        assert "avg_duration_ms" in stats

    def test_cleanup_old_traces(self):
        """Test cleaning up old traces."""
        import time

        # Create span with very old timestamp
        old_span = Span(name="old", trace_id="old_trace", span_id="old_span")
        # Set start time to 60 days ago
        old_span.start_time = int((time.time() - 60 * 24 * 60 * 60) * 1_000_000_000)
        old_span.end()

        # Create recent span
        recent_span = Span(name="recent", trace_id="recent_trace", span_id="recent_span")
        recent_span.end()

        self.store.store_span(old_span)
        self.store.store_span(recent_span)

        # Cleanup traces older than 30 days
        deleted = self.store.cleanup_old_traces(days=30)

        assert deleted == 1  # Old span should be deleted

        # Recent trace should still exist
        recent_traces = self.store.get_recent_traces()
        assert "recent_trace" in recent_traces
        assert "old_trace" not in recent_traces

    def test_span_attributes_preserved(self):
        """Test that span attributes are preserved in storage."""
        span = Span(name="test", trace_id="t1", span_id="s1")
        span.set_attribute("string_attr", "value")
        span.set_attribute("int_attr", 42)
        span.set_attribute("float_attr", 3.14)
        span.set_attribute("bool_attr", True)
        span.end()

        self.store.store_span(span)

        # Retrieve and verify
        spans = self.store.get_trace("t1")
        assert len(spans) == 1

        attrs = spans[0]["attributes"]
        assert attrs["string_attr"] == "value"
        assert attrs["int_attr"] == 42
        assert attrs["float_attr"] == 3.14
        assert attrs["bool_attr"] is True

    def test_span_events_preserved(self):
        """Test that span events are preserved in storage."""
        span = Span(name="test", trace_id="t1", span_id="s1")
        span.add_event("event1", {"key": "value"})
        span.add_event("event2", {"count": 5})
        span.end()

        self.store.store_span(span)

        # Retrieve and verify
        spans = self.store.get_trace("t1")
        events = spans[0]["events"]

        assert len(events) == 2
        assert events[0]["name"] == "event1"
        assert events[0]["attributes"]["key"] == "value"
        assert events[1]["name"] == "event2"
        assert events[1]["attributes"]["count"] == 5

    def test_thread_safety(self):
        """Test thread-safe operations."""
        import threading

        def store_spans(start_idx):
            for i in range(start_idx, start_idx + 10):
                span = Span(name=f"span{i}", trace_id=f"trace{i}", span_id=f"span{i}")
                span.end()
                self.store.store_span(span)

        # Create multiple threads storing spans concurrently
        threads = [
            threading.Thread(target=store_spans, args=(i * 10,))
            for i in range(5)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should have stored all 50 spans
        stats = self.store.get_stats()
        assert stats["span_count"] == 50
        assert stats["trace_count"] == 50


class TestSQLiteTraceStorePathHandling:
    """Tests for path handling."""

    def test_expands_user_home(self):
        """Test that ~ is expanded in paths."""
        store = SQLiteTraceStore("~/test_traces.db")

        # Should expand to actual home directory
        assert "~" not in str(store.db_path)
        assert str(Path.home()) in str(store.db_path)

        # Cleanup
        if store.db_path.exists():
            store.db_path.unlink()

    def test_creates_parent_directories(self):
        """Test that parent directories are created."""
        temp_dir = tempfile.mkdtemp()
        nested_path = os.path.join(temp_dir, "nested", "dir", "traces.db")

        store = SQLiteTraceStore(nested_path)

        assert Path(nested_path).parent.exists()
        assert Path(nested_path).exists()

        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)
