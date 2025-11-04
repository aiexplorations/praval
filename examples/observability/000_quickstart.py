#!/usr/bin/env python3
"""
Example 000: Observability Quickstart
======================================

The simplest possible demonstration of observability.
Shows what it will look like when Phase 2 is complete.

Run: python examples/observability/000_quickstart.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import time
from praval.observability import get_tracer, get_trace_store


def simple_example():
    """Simple example - just create a span and view it."""
    tracer = get_tracer()
    store = get_trace_store()

    print("Creating a simple trace...\n")

    # Create a span (this will be automatic in Phase 2)
    with tracer.start_as_current_span("my_operation") as span:
        span.set_attribute("user", "alice")
        time.sleep(0.1)
        print("✓ Did some work (100ms)\n")

    # View what was captured
    print(f"Trace ID: {span.trace_id}\n")

    # Retrieve from storage
    spans = store.get_trace(span.trace_id)
    print(f"Stored {len(spans)} span(s) to SQLite")
    print(f"Duration: {spans[0]['duration_ms']:.0f}ms")
    print(f"Attributes: {spans[0]['attributes']}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Observability Quickstart")
    print("=" * 60)
    print()

    simple_example()

    print("\n" + "=" * 60)
    print("That's it! Traces are automatically stored.")
    print("=" * 60)
    print(f"\nStorage location: ~/.praval/traces.db")
    print()
