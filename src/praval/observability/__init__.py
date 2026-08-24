"""Explicit OpenTelemetry configuration and compatibility diagnostics.

Importing this module does not configure providers, start worker threads, open
files, or monkeypatch Praval runtime functions.
"""

from praval.runtime_observation import (
    CompositeObservationRecorder,
    configure_observation_recorder,
    use_observation_recorder,
)

from .config import ObservabilityConfig, get_config
from .export import (
    ConsoleViewer,
    OTLPExporter,
    export_traces_to_otlp,
    print_traces,
    show_recent_traces,
)
from .instrumentation import initialize_instrumentation, is_instrumented
from .lifecycle import (
    ObservabilityHandle,
    configure_observability,
    configure_tracing,
    force_flush,
    get_logger,
    get_meter,
    get_tracer,
    shutdown_observability,
)
from .storage import SQLiteTraceStore, get_trace_store
from .tracing import (
    Span,
    SpanKind,
    SpanStatus,
    TraceContext,
    Tracer,
    get_current_span,
)

__all__ = [
    # Configuration
    "ObservabilityConfig",
    "ObservabilityHandle",
    "get_config",
    "configure_observability",
    "configure_tracing",
    "force_flush",
    "shutdown_observability",
    # Tracing
    "Tracer",
    "get_tracer",
    "get_meter",
    "get_logger",
    "Span",
    "SpanKind",
    "SpanStatus",
    "TraceContext",
    "get_current_span",
    "CompositeObservationRecorder",
    "configure_observation_recorder",
    "use_observation_recorder",
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
