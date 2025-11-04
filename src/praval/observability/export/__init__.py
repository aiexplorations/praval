"""
Export layer for sending traces to external systems.

Supports:
- OTLP HTTP export to collectors (Jaeger, Zipkin, etc.)
- Console output for debugging
"""

from .otlp_exporter import OTLPExporter, export_traces_to_otlp
from .console_viewer import ConsoleViewer, print_traces, show_recent_traces

__all__ = [
    "OTLPExporter",
    "export_traces_to_otlp",
    "ConsoleViewer",
    "print_traces",
    "show_recent_traces",
]
