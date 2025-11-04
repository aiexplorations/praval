"""
Praval Observability Framework.

OpenTelemetry-compatible distributed tracing for Praval agents.

Configuration:
    PRAVAL_OBSERVABILITY: "auto" | "on" | "off" (default: "auto")
    PRAVAL_OTLP_ENDPOINT: OTLP endpoint URL (optional)
    PRAVAL_SAMPLE_RATE: 0.0-1.0 (default: 1.0)
    PRAVAL_TRACES_PATH: SQLite database path (default: ~/.praval/traces.db)

Usage:
    # Zero configuration - automatic observability
    from praval import agent

    @agent("researcher")
    def research_agent(spore):
        result = chat("Research topic")
        return result

    # View traces
    from praval.observability import show_recent_traces
    show_recent_traces(limit=10)
"""

from .config import ObservabilityConfig, get_config
from .tracing import (
    Tracer,
    get_tracer,
    Span,
    SpanKind,
    SpanStatus,
    TraceContext,
    get_current_span,
)
from .storage import SQLiteTraceStore, get_trace_store
from .instrumentation import initialize_instrumentation, is_instrumented
from .export import (
    OTLPExporter,
    export_traces_to_otlp,
    ConsoleViewer,
    print_traces,
    show_recent_traces,
)

__all__ = [
    # Configuration
    "ObservabilityConfig",
    "get_config",
    # Tracing
    "Tracer",
    "get_tracer",
    "Span",
    "SpanKind",
    "SpanStatus",
    "TraceContext",
    "get_current_span",
    # Storage
    "SQLiteTraceStore",
    "get_trace_store",
    # Instrumentation
    "initialize_instrumentation",
    "is_instrumented",
    # Export & Viewing
    "OTLPExporter",
    "export_traces_to_otlp",
    "ConsoleViewer",
    "print_traces",
    "show_recent_traces",
]

__version__ = "0.8.0-dev"

# Auto-initialize instrumentation on import
initialize_instrumentation()
