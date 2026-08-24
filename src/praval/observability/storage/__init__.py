"""
Storage backends for observability data.
"""

from typing import Any

from .sqlite_store import SQLiteTraceStore, get_trace_store


def __getattr__(name: str) -> Any:
    """Load the SDK-backed exporter only when explicitly requested."""
    if name == "SQLiteSpanExporter":
        from .sqlite_exporter import SQLiteSpanExporter

        return SQLiteSpanExporter
    raise AttributeError(name)


__all__ = [
    "SQLiteTraceStore",
    "SQLiteSpanExporter",
    "get_trace_store",
]
