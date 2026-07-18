"""
Instrumentation utilities.

Helper functions for wrapping and instrumenting code.
"""

import functools
import inspect
from typing import Any, Callable, Optional

from ..tracing import SpanKind, TraceContext, get_tracer


def instrument_function(
    span_name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    extract_context_from_arg: Optional[str] = None,
    inject_context_to_arg: Optional[str] = None,
) -> Callable:
    """Decorator to instrument a function with tracing.

    Args:
        span_name: Name of the span to create
        kind: Span kind (default: INTERNAL)
        extract_context_from_arg: Argument name to extract TraceContext from (e.g.,
        "spore")
        inject_context_to_arg: Argument name to inject TraceContext into (e.g., "spore")

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        def prepare_span(args: Any, kwargs: Any) -> Any:
            tracer = get_tracer()

            # Extract parent context if specified
            parent_context = None
            if extract_context_from_arg:
                # Try to get from kwargs first
                arg_value = kwargs.get(extract_context_from_arg)
                if arg_value is None and args:
                    # Try positional args (assume first arg)
                    arg_value = args[0]

                if arg_value and hasattr(arg_value, "metadata"):
                    parent_context = TraceContext.from_spore(arg_value)

            return tracer.start_as_current_span(
                span_name, parent=parent_context, kind=kind
            )

        def inject_context(span: Any, args: Any, kwargs: Any) -> None:
            if not inject_context_to_arg:
                return

            arg_value = kwargs.get(inject_context_to_arg)
            if arg_value is None and args:
                arg_value = args[0]

            if arg_value and hasattr(arg_value, "metadata"):
                context = TraceContext.from_span(span)
                context.inject_into_spore(arg_value)

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with prepare_span(args, kwargs) as span:
                    inject_context(span, args, kwargs)
                    result = await func(*args, **kwargs)
                    span.set_status("ok")
                    return result

            return async_wrapper

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with prepare_span(args, kwargs) as span:
                inject_context(span, args, kwargs)
                result = func(*args, **kwargs)
                span.set_status("ok")
                return result

        return wrapper

    return decorator
