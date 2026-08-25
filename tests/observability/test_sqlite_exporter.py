"""Official SQLite span exporter and complete-trace retention contracts."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult
from opentelemetry.trace import Link, SpanContext, Status, StatusCode, TraceFlags

from praval.observability.storage import SQLiteSpanExporter, SQLiteTraceStore
from praval.observability.storage.sqlite_exporter import _trace_state


def _export_test_trace(path: Path) -> tuple[SQLiteTraceStore, str]:
    exporter = SQLiteSpanExporter(
        str(path),
        capture_content=False,
        content_allowlist=(),
    )
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "sqlite-test",
                "deployment.environment.name": "test",
                "api_key": "must-not-be-stored",
            },
            schema_url="https://opentelemetry.io/schemas/1.29.0",
        ),
        shutdown_on_exit=False,
    )
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(
        "sqlite.instrumentation",
        "1.2.3",
        schema_url="https://opentelemetry.io/schemas/1.30.0",
        attributes={"praval.scope.kind": "runtime"},
    )
    linked = SpanContext(
        trace_id=1,
        span_id=2,
        is_remote=True,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    with tracer.start_as_current_span(
        "agent.invoke",
        attributes={
            "praval.agent.name": "researcher",
            "gen_ai.prompt": "private prompt",
            "authorization": "Bearer private-token",
        },
        links=[Link(linked, {"praval.link.kind": "handoff"})],
    ) as span:
        span.add_event(
            "tool.completed",
            {
                "gen_ai.tool.name": "search",
                "tool.arguments": "private arguments",
            },
        )
        span.set_status(Status(StatusCode.ERROR, "private application error"))
        trace_id = format(span.get_span_context().trace_id, "032x")
    provider.shutdown()
    return exporter.store, trace_id


def test_official_exporter_preserves_otel_structure_and_filters_content(
    tmp_path: Path,
) -> None:
    store, trace_id = _export_test_trace(tmp_path / "telemetry.db")

    rows = store.get_trace(trace_id)
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "agent.invoke"
    assert row["resource_attributes"]["service.name"] == "sqlite-test"
    assert row["resource_attributes"]["api_key"] == "[REDACTED]"
    assert row["resource_schema_url"] == "https://opentelemetry.io/schemas/1.29.0"
    assert row["scope_name"] == "sqlite.instrumentation"
    assert row["scope_version"] == "1.2.3"
    assert row["scope_schema_url"] == "https://opentelemetry.io/schemas/1.30.0"
    assert row["scope_attributes"] == {"praval.scope.kind": "runtime"}
    assert row["attributes"]["praval.agent.name"] == "researcher"
    assert "gen_ai.prompt" not in row["attributes"]
    assert row["attributes"]["authorization"] == "[REDACTED]"
    assert row["events"][0]["name"] == "tool.completed"
    assert row["events"][0]["attributes"] == {"gen_ai.tool.name": "search"}
    assert row["links"][0]["trace_id"] == format(1, "032x")
    assert row["links"][0]["span_id"] == format(2, "016x")
    assert row["links"][0]["attributes"] == {"praval.link.kind": "handoff"}
    assert row["status"] == "ERROR"
    assert row["status_message"] == ""


def test_sqlite_connections_enable_wal_and_bounded_busy_timeout(
    tmp_path: Path,
) -> None:
    store = SQLiteTraceStore(str(tmp_path / "telemetry.db"), busy_timeout_ms=4321)
    connection = store._get_connection()
    try:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 4321
    finally:
        connection.close()


def test_exporter_returns_failure_without_raising_on_unavailable_store(
    tmp_path: Path,
) -> None:
    store = SQLiteTraceStore(str(tmp_path / "telemetry.db"))
    store._init_error = sqlite3.OperationalError("database unavailable")
    exporter = SQLiteSpanExporter(store=store)

    assert exporter.export([object()]) is SpanExportResult.FAILURE


def test_exporter_constructor_and_synchronous_lifecycle_edges(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="db_path or store"):
        SQLiteSpanExporter()
    exporter = SQLiteSpanExporter(str(tmp_path / "telemetry.db"))

    assert exporter.force_flush() is True
    assert exporter.shutdown() is None
    assert _trace_state(object()) == ""


def test_storage_module_rejects_unknown_lazy_exports() -> None:
    import praval.observability.storage as storage

    with pytest.raises(AttributeError):
        storage.__getattr__("UnknownExporter")


def test_cleanup_retains_or_deletes_complete_traces(tmp_path: Path) -> None:
    from tests.observability.test_sqlite_store import Span

    store = SQLiteTraceStore(str(tmp_path / "telemetry.db"))
    spans = [
        Span(name="old-root", trace_id="old", span_id="old-root", start_time=10),
        Span(name="old-child", trace_id="old", span_id="old-child", start_time=20),
        Span(name="middle", trace_id="middle", span_id="middle", start_time=30),
        Span(name="new-root", trace_id="new", span_id="new-root", start_time=40),
        Span(name="new-child", trace_id="new", span_id="new-child", start_time=50),
    ]
    store.store_spans(spans)

    deleted = store.cleanup_traces(keep_last_n=2)

    assert deleted == 2
    assert store.get_trace("old") == []
    assert len(store.get_trace("middle")) == 1
    assert len(store.get_trace("new")) == 2


def test_cleanup_age_uses_whole_trace_recency(tmp_path: Path) -> None:
    from tests.observability.test_sqlite_store import Span

    store = SQLiteTraceStore(str(tmp_path / "telemetry.db"))
    day_ns = 24 * 60 * 60 * 1_000_000_000
    now_ns = 100 * day_ns
    spans = [
        Span(
            name="old-root",
            trace_id="mixed",
            span_id="old-root",
            start_time=now_ns - 10 * day_ns,
        ),
        Span(
            name="recent-child",
            trace_id="mixed",
            span_id="recent-child",
            start_time=now_ns - day_ns,
        ),
        Span(
            name="expired",
            trace_id="expired",
            span_id="expired",
            start_time=now_ns - 20 * day_ns,
        ),
    ]
    store.store_spans(spans)

    assert store.cleanup_traces(max_age_days=7, now_ns=now_ns) == 1
    assert len(store.get_trace("mixed")) == 2
    assert store.get_trace("expired") == []


def test_cleanup_validates_retention_bounds(tmp_path: Path) -> None:
    store = SQLiteTraceStore(str(tmp_path / "telemetry.db"))

    assert store.cleanup_traces() == 0
    with pytest.raises(ValueError, match="max_age_days"):
        store.cleanup_traces(max_age_days=-1)
    with pytest.raises(ValueError, match="keep_last_n"):
        store.cleanup_traces(keep_last_n=-1)


def test_exporter_applies_count_retention_after_successful_batches(
    tmp_path: Path,
) -> None:
    exporter = SQLiteSpanExporter(str(tmp_path / "telemetry.db"), keep_last_n=2)
    provider = TracerProvider(shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("retention-test")
    trace_ids = []
    for index in range(3):
        with tracer.start_as_current_span(f"trace-{index}") as span:
            trace_ids.append(format(span.get_span_context().trace_id, "032x"))
    provider.shutdown()

    assert exporter.store.get_trace(trace_ids[0]) == []
    assert len(exporter.store.get_trace(trace_ids[1])) == 1
    assert len(exporter.store.get_trace(trace_ids[2])) == 1


def test_existing_v082_schema_is_migrated_in_place(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE spans (
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
        )
        """
    )
    connection.commit()
    connection.close()

    store, trace_id = _export_test_trace(path)

    row = store.get_trace(trace_id)[0]
    assert row["resource_attributes"]["service.name"] == "sqlite-test"
    assert row["scope_name"] == "sqlite.instrumentation"


def test_concurrent_official_batches_are_serialized(tmp_path: Path) -> None:
    class ReadableSpan:
        pass

    store = SQLiteTraceStore(str(tmp_path / "telemetry.db"))
    exporter = SQLiteSpanExporter(store=store)
    batches: list[list[Any]] = []
    for index in range(20):
        span = ReadableSpan()
        span.name = f"span-{index}"
        span.context = SpanContext(
            trace_id=index + 1,
            span_id=index + 1,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
        span.parent = None
        span.kind = type("Kind", (), {"name": "INTERNAL"})()
        span.start_time = index + 1
        span.end_time = index + 2
        span.attributes = {}
        span.events = ()
        span.links = ()
        span.status = type(
            "Status",
            (),
            {"status_code": type("Code", (), {"name": "UNSET"})(), "description": None},
        )()
        span.resource = Resource.create({"service.name": "concurrent"})
        span.instrumentation_scope = type(
            "Scope",
            (),
            {"name": "test", "version": None, "schema_url": None, "attributes": None},
        )()
        batches.append([span])

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(exporter.export, batches))

    assert results == [SpanExportResult.SUCCESS] * 20
    assert store.get_stats()["span_count"] == 20
