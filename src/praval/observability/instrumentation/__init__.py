"""
Instrumentation layer for automatic tracing.

Automatically instruments Praval framework components to capture traces.
"""

from .manager import initialize_instrumentation, is_instrumented

__all__ = [
    "initialize_instrumentation",
    "is_instrumented",
]
