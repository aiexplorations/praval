"""Official OpenTelemetry span exporter for local SQLite diagnostics."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from ..privacy import TelemetrySanitizer
from .sqlite_store import SQLiteTraceStore

logger = logging.getLogger(__name__)


def _trace_state(context: Any) -> str:
    state = getattr(context, "trace_state", None)
    if state is None:
        return ""
    to_header = getattr(state, "to_header", None)
    return str(to_header()) if to_header is not None else str(state)


class SQLiteSpanExporter(SpanExporter):
    """Persist official readable spans for single-process diagnostics."""

    def __init__(
        self,
        db_path: str | None = None,
        *,
        store: SQLiteTraceStore | None = None,
        max_age_days: int | None = None,
        keep_last_n: int | None = None,
        capture_content: bool = False,
        content_allowlist: Sequence[str] = (),
        busy_timeout_ms: int = 5000,
    ) -> None:
        if store is None and db_path is None:
            raise ValueError("db_path or store is required")
        self.store = store or SQLiteTraceStore(
            str(db_path), busy_timeout_ms=busy_timeout_ms
        )
        self.max_age_days = max_age_days
        self.keep_last_n = keep_last_n
        self._sanitizer = TelemetrySanitizer(
            capture_content=capture_content,
            content_allowlist=content_allowlist,
        )

    def _event(self, event: Any) -> dict[str, Any]:
        return {
            "name": self._sanitizer.sanitize_value(event.name),
            "timestamp": event.timestamp,
            "attributes": self._sanitizer.sanitize_attributes(event.attributes),
            "dropped_attributes": getattr(event, "dropped_attributes", 0),
        }

    def _link(self, link: Any) -> dict[str, Any]:
        context = link.context
        return {
            "trace_id": format(context.trace_id, "032x"),
            "span_id": format(context.span_id, "016x"),
            "trace_state": _trace_state(context),
            "attributes": self._sanitizer.sanitize_attributes(link.attributes),
            "dropped_attributes": getattr(link, "dropped_attributes", 0),
        }

    def _record(self, span: Any) -> dict[str, Any]:
        context = span.context
        parent = span.parent
        resource = span.resource
        scope = span.instrumentation_scope
        status = span.status
        description = self._sanitizer.sanitize_attributes(
            {"error.description": status.description}
            if status.description is not None
            else None
        ).get("error.description", "")
        scope_attributes = getattr(scope, "attributes", None)
        if not isinstance(scope_attributes, Mapping):
            scope_attributes = None
        end_time = span.end_time
        duration_ms = (
            (end_time - span.start_time) / 1_000_000 if end_time is not None else None
        )
        return {
            "span_id": format(context.span_id, "016x"),
            "trace_id": format(context.trace_id, "032x"),
            "parent_span_id": (
                format(parent.span_id, "016x") if parent is not None else None
            ),
            "name": self._sanitizer.sanitize_value(span.name),
            "kind": span.kind.name,
            "start_time": span.start_time,
            "end_time": end_time,
            "duration_ms": duration_ms,
            "attributes": self._sanitizer.sanitize_attributes(span.attributes),
            "events": [self._event(event) for event in span.events],
            "status": status.status_code.name,
            "status_message": description,
            "resource_attributes": self._sanitizer.sanitize_attributes(
                resource.attributes
            ),
            "resource_schema_url": resource.schema_url,
            "scope_name": scope.name,
            "scope_version": scope.version,
            "scope_schema_url": scope.schema_url,
            "scope_attributes": self._sanitizer.sanitize_attributes(scope_attributes),
            "links": [self._link(link) for link in span.links],
            "trace_state": _trace_state(context),
        }

    def export(self, spans: Sequence[Any]) -> SpanExportResult:
        """Persist one SDK batch and apply complete-trace retention."""
        try:
            records = [self._record(span) for span in spans]
            with self.store._lock:
                self.store.store_span_records(records)
                self.store.cleanup_traces(
                    max_age_days=self.max_age_days,
                    keep_last_n=self.keep_last_n,
                )
        except Exception:
            logger.warning(
                "SQLite telemetry export failed",
                extra={"event_name": "praval.telemetry.local_export.failed"},
            )
            return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """SQLite commits synchronously, so there is nothing further to flush."""
        return True

    def shutdown(self) -> None:
        """SQLite connections are scoped to individual operations."""
        return None


__all__ = ["SQLiteSpanExporter"]
