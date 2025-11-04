#!/usr/bin/env python3
"""
Example 001: Basic Tracing Demo
================================

This example demonstrates the Phase 1 observability infrastructure:
- Creating spans manually
- Parent-child span relationships
- Storing traces to SQLite
- Viewing traces

This shows what's working NOW (Phase 1), before full auto-instrumentation.

Run: python examples/observability/001_basic_tracing_demo.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import time
from praval.observability import (
    get_tracer,
    get_trace_store,
    get_config,
    SpanKind
)


def simulate_agent_operation():
    """Simulate an agent operation with tracing."""
    tracer = get_tracer()
    store = get_trace_store()

    print("=" * 70)
    print("Simulating Agent Operation with Manual Tracing")
    print("=" * 70)
    print()

    # Start a root span for the agent execution
    with tracer.start_as_current_span(
        "agent.researcher.execute",
        kind=SpanKind.INTERNAL
    ) as agent_span:
        agent_span.set_attribute("agent.name", "researcher")
        agent_span.set_attribute("agent.type", "researcher")

        print("✓ Created root span: agent.researcher.execute")

        # Simulate LLM call
        time.sleep(0.05)  # Simulate 50ms LLM call
        with tracer.start_as_current_span(
            "llm.chat",
            kind=SpanKind.CLIENT
        ) as llm_span:
            llm_span.set_attribute("llm.provider", "openai")
            llm_span.set_attribute("llm.model", "gpt-4-turbo")
            llm_span.set_attribute("llm.tokens.input", 150)
            llm_span.set_attribute("llm.tokens.output", 200)
            llm_span.set_attribute("llm.tokens.total", 350)
            llm_span.set_attribute("llm.cost_usd", 0.0025)

            time.sleep(0.05)
            print("✓ Created child span: llm.chat")

        # Simulate memory operation
        with tracer.start_as_current_span("memory.store") as memory_span:
            memory_span.set_attribute("memory.backend", "chromadb")
            memory_span.set_attribute("memory.operation", "store")
            memory_span.set_attribute("memory.content_length", 256)

            time.sleep(0.01)
            print("✓ Created child span: memory.store")

        agent_span.set_attribute("result.status", "success")

    # Store the spans
    print("\n✓ Spans automatically stored to SQLite")

    # Show trace info
    print("\n" + "=" * 70)
    print("Trace Information")
    print("=" * 70)
    print(f"Trace ID: {agent_span.trace_id}")
    print(f"Root Span ID: {agent_span.span_id}")
    print(f"Duration: {agent_span.duration_ms():.2f}ms")
    print(f"Status: {agent_span.status.value}")

    return agent_span.trace_id


def view_trace(trace_id):
    """View a trace from storage."""
    store = get_trace_store()

    print("\n" + "=" * 70)
    print("Viewing Trace from Storage")
    print("=" * 70)
    print()

    spans = store.get_trace(trace_id)

    print(f"Found {len(spans)} spans in trace:")
    print()

    for span in spans:
        indent = "  " if span['parent_span_id'] else ""
        status_icon = "✓" if span['status'] == "OK" else "✗"

        print(f"{indent}├─ {span['name']} ({span['duration_ms']:.2f}ms) {status_icon}")

        # Show key attributes
        attrs = span['attributes']
        if 'llm.model' in attrs:
            print(f"{indent}│  ├─ Model: {attrs['llm.model']}")
            print(f"{indent}│  ├─ Tokens: {attrs['llm.tokens.total']}")
            print(f"{indent}│  └─ Cost: ${attrs['llm.cost_usd']}")
        elif 'memory.backend' in attrs:
            print(f"{indent}│  └─ Backend: {attrs['memory.backend']}")


def show_storage_stats():
    """Show storage statistics."""
    store = get_trace_store()

    print("\n" + "=" * 70)
    print("Storage Statistics")
    print("=" * 70)
    print()

    stats = store.get_stats()

    print(f"Total traces: {stats.get('trace_count', 0)}")
    print(f"Total spans: {stats.get('span_count', 0)}")
    print(f"Average duration: {stats.get('avg_duration_ms', 0):.2f}ms")


def demonstrate_parent_child():
    """Demonstrate parent-child span relationships."""
    tracer = get_tracer()

    print("\n" + "=" * 70)
    print("Demonstrating Parent-Child Relationships")
    print("=" * 70)
    print()

    with tracer.start_as_current_span("parent.operation") as parent:
        print(f"Parent span: {parent.name}")
        print(f"  Trace ID: {parent.trace_id}")
        print(f"  Span ID: {parent.span_id}")

        time.sleep(0.01)

        with tracer.start_as_current_span("child.operation.1") as child1:
            print(f"\nChild 1 span: {child1.name}")
            print(f"  Trace ID: {child1.trace_id} (same as parent)")
            print(f"  Span ID: {child1.span_id}")
            print(f"  Parent Span ID: {child1.parent_span_id}")
            time.sleep(0.01)

        with tracer.start_as_current_span("child.operation.2") as child2:
            print(f"\nChild 2 span: {child2.name}")
            print(f"  Trace ID: {child2.trace_id} (same as parent)")
            print(f"  Span ID: {child2.span_id}")
            print(f"  Parent Span ID: {child2.parent_span_id}")
            time.sleep(0.01)

    return parent.trace_id


def main():
    """Run the basic tracing demo."""
    print("\n" + "=" * 70)
    print("Praval Observability - Basic Tracing Demo (Phase 1)")
    print("=" * 70)
    print()

    # Show configuration
    config = get_config()
    print("Configuration:")
    print(f"  Observability enabled: {config.is_enabled()}")
    print(f"  Sample rate: {config.sample_rate * 100}%")
    print(f"  Storage path: {config.storage_path}")
    print()

    # Simulate agent operation
    trace_id = simulate_agent_operation()

    # View the trace
    view_trace(trace_id)

    # Demonstrate parent-child relationships
    parent_trace_id = demonstrate_parent_child()
    view_trace(parent_trace_id)

    # Show storage stats
    show_storage_stats()

    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print()
    print("Key Takeaways:")
    print("✓ Phase 1 provides OpenTelemetry-compatible tracing infrastructure")
    print("✓ Spans can be created manually with full context")
    print("✓ Parent-child relationships are tracked automatically")
    print("✓ All traces stored to local SQLite database")
    print("✓ Traces can be queried and analyzed")
    print()
    print("Next: Phase 2 will add automatic instrumentation")
    print("  - Agents will be traced automatically")
    print("  - LLM calls will be captured automatically")
    print("  - Memory operations will be tracked automatically")
    print()


if __name__ == "__main__":
    main()
