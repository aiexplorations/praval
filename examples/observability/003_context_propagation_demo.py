#!/usr/bin/env python3
"""
Example 003: Context Propagation Demo
======================================

This example demonstrates how trace context propagates between agents:
- Extracting context from Spore metadata
- Injecting context into Spore metadata
- Creating parent-child relationships across agent boundaries
- Simulating multi-agent workflows

This simulates what will happen automatically when Phase 2 instrumentation is complete.

Run: python examples/observability/003_context_propagation_demo.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import time
from praval.observability import (
    get_tracer,
    get_trace_store,
    TraceContext,
    SpanKind
)


class MockSpore:
    """Mock Spore for demonstration."""

    def __init__(self, knowledge=None, metadata=None):
        self.knowledge = knowledge or {}
        self.metadata = metadata or {}


def agent_1_researcher(spore):
    """Simulate Agent 1: Researcher."""
    tracer = get_tracer()

    print("=" * 70)
    print("Agent 1: Researcher")
    print("=" * 70)
    print()

    # Agent 1 starts a new trace
    with tracer.start_as_current_span(
        "agent.researcher.execute",
        kind=SpanKind.INTERNAL
    ) as span:
        span.set_attribute("agent.name", "researcher")
        span.set_attribute("agent.type", "researcher")
        span.set_attribute("spore.id", "spore-001")

        print(f"✓ Started root span")
        print(f"  Trace ID: {span.trace_id}")
        print(f"  Span ID: {span.span_id}")
        print()

        # Simulate work
        time.sleep(0.02)
        print("✓ Performing research...")
        time.sleep(0.03)

        # Prepare to send result to Agent 2
        # Get current context
        context = TraceContext.from_span(span)

        # Create spore for Agent 2
        outgoing_spore = MockSpore(
            knowledge={"research_result": "Quantum computing overview"}
        )

        # Inject trace context into spore
        context.inject_into_spore(outgoing_spore)

        print(f"✓ Injected trace context into spore for Agent 2")
        print(f"  Context: trace_id={context.trace_id[:8]}...")
        print()

        return span.trace_id, outgoing_spore


def agent_2_analyzer(spore, incoming_trace_id):
    """Simulate Agent 2: Analyzer (receives spore from Agent 1)."""
    tracer = get_tracer()

    print("=" * 70)
    print("Agent 2: Analyzer")
    print("=" * 70)
    print()

    # Extract trace context from incoming spore
    parent_context = TraceContext.from_spore(spore)

    if parent_context:
        print(f"✓ Extracted trace context from spore")
        print(f"  Parent trace ID: {parent_context.trace_id[:8]}...")
        print(f"  Parent span ID: {parent_context.span_id[:8]}...")
        print()
    else:
        print("✗ No trace context found in spore")
        return

    # Agent 2 creates a child span using parent context
    with tracer.start_as_current_span(
        "agent.analyzer.execute",
        parent=parent_context,
        kind=SpanKind.INTERNAL
    ) as span:
        span.set_attribute("agent.name", "analyzer")
        span.set_attribute("agent.type", "analyzer")
        span.set_attribute("spore.id", "spore-002")

        print(f"✓ Started child span")
        print(f"  Trace ID: {span.trace_id} (same as parent)")
        print(f"  Span ID: {span.span_id}")
        print(f"  Parent Span ID: {span.parent_span_id}")
        print()

        # Verify trace continuity
        assert span.trace_id == incoming_trace_id, "Trace ID mismatch!"
        assert span.parent_span_id == parent_context.span_id, "Parent link broken!"

        print("✓ Trace continuity verified!")
        print()

        # Simulate work
        time.sleep(0.02)
        print("✓ Analyzing research results...")
        time.sleep(0.02)

        # Prepare to send to Agent 3
        context = TraceContext.from_span(span)
        outgoing_spore = MockSpore(
            knowledge={"analysis": "High potential, requires quantum hardware"}
        )
        context.inject_into_spore(outgoing_spore)

        print(f"✓ Injected trace context into spore for Agent 3")
        print()

        return outgoing_spore


def agent_3_reporter(spore, original_trace_id):
    """Simulate Agent 3: Reporter (receives spore from Agent 2)."""
    tracer = get_tracer()

    print("=" * 70)
    print("Agent 3: Reporter")
    print("=" * 70)
    print()

    # Extract context
    parent_context = TraceContext.from_spore(spore)

    if parent_context:
        print(f"✓ Extracted trace context from spore")
        print(f"  Trace ID: {parent_context.trace_id[:8]}...")
        print()

    # Create child span
    with tracer.start_as_current_span(
        "agent.reporter.execute",
        parent=parent_context,
        kind=SpanKind.INTERNAL
    ) as span:
        span.set_attribute("agent.name", "reporter")
        span.set_attribute("agent.type", "reporter")
        span.set_attribute("spore.id", "spore-003")

        print(f"✓ Started child span")
        print(f"  Trace ID: {span.trace_id} (same as original)")
        print(f"  Span ID: {span.span_id}")
        print(f"  Parent Span ID: {span.parent_span_id}")
        print()

        # Verify trace continuity
        assert span.trace_id == original_trace_id, "Trace ID mismatch!"

        print("✓ Trace continuity verified across 3 agents!")
        print()

        # Simulate work
        time.sleep(0.02)
        print("✓ Generating final report...")
        time.sleep(0.02)


def view_complete_trace(trace_id):
    """View the complete trace showing all 3 agents."""
    store = get_trace_store()

    print("\n" + "=" * 70)
    print("Complete Trace Visualization")
    print("=" * 70)
    print()

    spans = store.get_trace(trace_id)

    print(f"Trace ID: {trace_id}")
    print(f"Total spans: {len(spans)}")
    print()

    print("Span Hierarchy:")
    print()

    for span in spans:
        # Calculate indentation based on hierarchy
        indent_level = 0
        if span['parent_span_id']:
            # Find parent to calculate depth
            for other in spans:
                if other['span_id'] == span['parent_span_id']:
                    if other['parent_span_id']:
                        indent_level = 2
                    else:
                        indent_level = 1
                    break

        indent = "  " * indent_level
        connector = "├─" if indent_level == 0 else "└─"

        print(f"{indent}{connector} {span['name']} ({span['duration_ms']:.2f}ms)")

        # Show key attributes
        attrs = span['attributes']
        if 'agent.name' in attrs:
            print(f"{indent}   └─ Agent: {attrs['agent.name']}")

    print()

    # Show timing summary
    total_duration = sum(s['duration_ms'] for s in spans if not s['parent_span_id'])
    print(f"Total workflow duration: {total_duration:.2f}ms")


def demonstrate_parallel_agents():
    """Demonstrate parallel agent execution (same parent)."""
    tracer = get_tracer()

    print("\n" + "=" * 70)
    print("Bonus: Parallel Agent Execution")
    print("=" * 70)
    print()

    with tracer.start_as_current_span("coordinator") as coordinator_span:
        print("✓ Coordinator started")
        context = TraceContext.from_span(coordinator_span)

        # Spawn two parallel agents from same parent
        spore_a = MockSpore()
        spore_b = MockSpore()

        context.inject_into_spore(spore_a)
        context.inject_into_spore(spore_b)

        print("✓ Sent work to Agent A and Agent B in parallel")
        print()

        # Agent A
        parent_a = TraceContext.from_spore(spore_a)
        with tracer.start_as_current_span("agent.a.execute", parent=parent_a) as span_a:
            span_a.set_attribute("agent.name", "agent_a")
            time.sleep(0.01)
            print(f"✓ Agent A completed (parent: {span_a.parent_span_id[:8]}...)")

        # Agent B
        parent_b = TraceContext.from_spore(spore_b)
        with tracer.start_as_current_span("agent.b.execute", parent=parent_b) as span_b:
            span_b.set_attribute("agent.name", "agent_b")
            time.sleep(0.01)
            print(f"✓ Agent B completed (parent: {span_b.parent_span_id[:8]}...)")

        print()
        print("✓ Both agents have same parent (coordinator)")
        print(f"  Agent A parent: {span_a.parent_span_id[:8]}...")
        print(f"  Agent B parent: {span_b.parent_span_id[:8]}...")
        print(f"  Same? {span_a.parent_span_id == span_b.parent_span_id}")

    return coordinator_span.trace_id


def main():
    """Run the context propagation demo."""
    print("\n" + "=" * 70)
    print("Praval Observability - Context Propagation Demo")
    print("=" * 70)
    print()
    print("This demonstrates how trace context flows between agents:")
    print("  Agent 1 (Researcher) → Agent 2 (Analyzer) → Agent 3 (Reporter)")
    print()
    print("Key mechanism: TraceContext via Spore metadata")
    print()

    # Simulate the multi-agent workflow
    trace_id, spore_for_agent2 = agent_1_researcher(MockSpore())
    spore_for_agent3 = agent_2_analyzer(spore_for_agent2, trace_id)
    agent_3_reporter(spore_for_agent3, trace_id)

    # View the complete trace
    view_complete_trace(trace_id)

    # Demonstrate parallel execution
    parallel_trace_id = demonstrate_parallel_agents()
    view_complete_trace(parallel_trace_id)

    print("\n" + "=" * 70)
    print("Context Propagation Demo Complete!")
    print("=" * 70)
    print()
    print("Key Takeaways:")
    print("✓ Trace context flows through Spore metadata")
    print("✓ Parent-child relationships preserved across agents")
    print("✓ Single trace ID spans entire multi-agent workflow")
    print("✓ Supports both sequential and parallel agent execution")
    print()
    print("Next: Phase 2 will make this automatic")
    print("  - No manual context injection/extraction needed")
    print("  - @agent decorator handles it automatically")
    print("  - Works seamlessly with existing Praval code")
    print()


if __name__ == "__main__":
    main()
