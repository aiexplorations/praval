"""
Instrumentation utilities.

Helper functions for wrapping and instrumenting code.
"""

import functools
from typing import Callable, Any, Optional

from ..tracing import get_tracer, TraceContext, SpanKind
from ..storage import get_trace_store


def instrument_function(
    span_name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    extract_context_from_arg: Optional[str] = None,
    inject_context_to_arg: Optional[str] = None
) -> Callable:
    """Decorator to instrument a function with tracing.

    Args:
        span_name: Name of the span to create
        kind: Span kind (default: INTERNAL)
        extract_context_from_arg: Argument name to extract TraceContext from (e.g., "spore")
        inject_context_to_arg: Argument name to inject TraceContext into (e.g., "spore")

    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            store = get_trace_store()

            # Extract parent context if specified
            parent_context = None
            if extract_context_from_arg:
                # Try to get from kwargs first
                arg_value = kwargs.get(extract_context_from_arg)
                if arg_value is None and args:
                    # Try positional args (assume first arg)
                    arg_value = args[0]

                if arg_value and hasattr(arg_value, 'metadata'):
                    parent_context = TraceContext.from_spore(arg_value)

            # Create span
            with tracer.start_as_current_span(
                span_name,
                parent=parent_context,
                kind=kind
            ) as span:
                # Inject context if specified
                if inject_context_to_arg:
                    arg_value = kwargs.get(inject_context_to_arg)
                    if arg_value is None and args:
                        arg_value = args[0]

                    if arg_value and hasattr(arg_value, 'metadata'):
                        context = TraceContext.from_span(span)
                        context.inject_into_spore(arg_value)

                try:
                    # Execute function
                    result = func(*args, **kwargs)

                    # Record success
                    span.set_status("ok")

                    # Store span
                    if span.end_time:  # Span ended successfully
                        store.store_span(span)

                    return result

                except Exception as e:
                    # Record error
                    span.record_exception(e)
                    span.set_status("error", str(e))

                    # Store span even on error
                    if span.end_time:
                        store.store_span(span)

                    raise

        return wrapper
    return decorator
