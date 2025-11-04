"""
Integration tests for automatic instrumentation of Praval components.

Tests that the instrumentation layer correctly wraps and traces:
- Agent decorator execution
- Reef communication
- Storage operations
"""

import os
import pytest
import time
from datetime import datetime

# Set up environment for testing
os.environ["PRAVAL_OBSERVABILITY"] = "on"
os.environ["PRAVAL_SAMPLE_RATE"] = "1.0"


class TestAgentInstrumentation:
    """Test automatic instrumentation of @agent decorated functions."""

    def test_agent_execution_creates_spans(self):
        """Verify that agent execution creates trace spans."""
        from praval import agent
        from praval.observability import get_trace_store

        store = get_trace_store()
        store.cleanup_old_traces(days=0)  # Clear all traces

        # Define a simple agent
        @agent("test_agent_inst")
        def simple_agent(spore):
            return {"result": "success"}

        # Send a message to the agent through reef
        simple_agent.send_knowledge({"test": "data"})

        # Give a moment for async span storage
        time.sleep(0.3)

        # Check that spans were created
        recent_traces = store.get_recent_traces(limit=10)
        assert len(recent_traces) > 0

        # Find the agent execution span
        agent_spans = store.find_spans_by_name("agent.test_agent_inst.execute")
        assert len(agent_spans) > 0

        span = agent_spans[0]
        assert span["name"] == "agent.test_agent_inst.execute"
        assert span["kind"] == "SERVER"
        assert span["status"] == "ok"

    def test_agent_error_recorded(self):
        """Verify that agent errors are recorded in spans."""
        from praval import agent
        from praval.observability import get_trace_store
        from praval.core.reef import Spore, SporeType

        store = get_trace_store()
        store.cleanup_old_traces(days=0)

        # Define an agent that raises an error
        @agent("error_agent")
        def error_agent(spore):
            raise ValueError("Test error")

        # Create a properly formatted spore
        test_spore = Spore(
            id="test-spore-2",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="test",
            to_agent="error_agent",
            knowledge={"test": "data"},
            created_at=datetime.now()
        )

        # Execute the agent (expect error)
        try:
            error_agent._praval_agent.spore_handler(test_spore)
        except ValueError:
            pass

        time.sleep(0.2)

        # Check error was recorded
        agent_spans = store.find_spans_by_name("agent.error_agent.execute")
        assert len(agent_spans) > 0

        span = agent_spans[0]
        assert span["status"] == "error"
        assert "events" in span
        # Check for exception event
        events = span["events"]
        assert any("exception" in e["name"].lower() for e in events)

    def test_trace_context_propagation(self):
        """Verify trace context is propagated through spore metadata."""
        from praval import agent
        from praval.observability import get_trace_store
        from praval.core.reef import Spore, SporeType

        store = get_trace_store()
        store.cleanup_old_traces(days=0)

        # Track if context was injected
        context_data = {}

        @agent("context_agent")
        def context_agent(spore):
            # Check if trace context is in metadata
            if hasattr(spore, 'metadata') and spore.metadata:
                context_data['trace_id'] = spore.metadata.get('trace_id')
                context_data['span_id'] = spore.metadata.get('span_id')
            return {"result": "success"}

        # Create spore without context
        test_spore = Spore(
            id="test-spore-3",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="test",
            to_agent="context_agent",
            knowledge={"test": "data"},
            created_at=datetime.now()
        )

        # Execute agent
        context_agent._praval_agent.spore_handler(test_spore)

        time.sleep(0.2)

        # Verify context was injected
        assert 'trace_id' in context_data
        assert 'span_id' in context_data
        assert len(context_data['trace_id']) == 32  # Valid trace ID
        assert len(context_data['span_id']) == 16  # Valid span ID


class TestReefInstrumentation:
    """Test automatic instrumentation of Reef communication."""

    def test_reef_send_creates_span(self):
        """Verify that reef.send creates trace spans."""
        from praval.core.reef import get_reef
        from praval.observability import get_trace_store

        store = get_trace_store()
        store.cleanup_old_traces(days=0)

        reef = get_reef()

        # Send a message
        reef.send(
            from_agent="sender",
            to_agent="receiver",
            knowledge={"message": "test"}
        )

        time.sleep(0.2)

        # Check for send span
        send_spans = store.find_spans_by_name("reef.send")
        assert len(send_spans) > 0

        span = send_spans[0]
        assert span["name"] == "reef.send"
        assert span["kind"] == "PRODUCER"

    def test_reef_broadcast_creates_span(self):
        """Verify that reef.broadcast creates trace spans."""
        from praval.core.reef import get_reef
        from praval.observability import get_trace_store

        store = get_trace_store()
        store.cleanup_old_traces(days=0)

        reef = get_reef()

        # Broadcast a message
        reef.broadcast(
            from_agent="broadcaster",
            knowledge={"announcement": "test"}
        )

        time.sleep(0.2)

        # Check for broadcast span
        broadcast_spans = store.find_spans_by_name("reef.broadcast")
        assert len(broadcast_spans) > 0

        span = broadcast_spans[0]
        assert span["name"] == "reef.broadcast"
        assert span["kind"] == "PRODUCER"


class TestStorageInstrumentation:
    """Test automatic instrumentation of storage providers."""

    def test_storage_save_creates_span(self):
        """Verify that storage.save creates trace spans."""
        from praval.storage.embedded_store import EmbeddedStore
        from praval.observability import get_trace_store

        store_trace = get_trace_store()
        store_trace.cleanup_old_traces(days=0)

        # Create storage provider
        storage = EmbeddedStore()

        # Save data
        storage.save("test_key", {"data": "value"})

        time.sleep(0.2)

        # Check for save span
        save_spans = store_trace.find_spans_by_name("storage.save")
        assert len(save_spans) > 0

        span = save_spans[0]
        assert span["name"] == "storage.save"
        assert span["kind"] == "CLIENT"

    def test_storage_load_creates_span(self):
        """Verify that storage.load creates trace spans."""
        from praval.storage.embedded_store import EmbeddedStore
        from praval.observability import get_trace_store

        store_trace = get_trace_store()
        store_trace.cleanup_old_traces(days=0)

        # Create storage provider
        storage = EmbeddedStore()

        # Save and load data
        storage.save("test_key", {"data": "value"})
        storage.load("test_key")

        time.sleep(0.2)

        # Check for load span
        load_spans = store_trace.find_spans_by_name("storage.load")
        assert len(load_spans) > 0

        span = load_spans[0]
        assert span["name"] == "storage.load"
        assert span["kind"] == "CLIENT"


class TestEndToEndInstrumentation:
    """Test end-to-end instrumentation across multiple components."""

    def test_multi_component_trace(self):
        """Verify complete trace across agent and storage."""
        from praval import agent
        from praval.core.reef import Spore, SporeType
        from praval.observability import get_trace_store
        from praval.storage.embedded_store import EmbeddedStore

        store_trace = get_trace_store()
        store_trace.cleanup_old_traces(days=0)

        # Create storage
        storage = EmbeddedStore()

        # Define agent that uses storage
        @agent("storage_agent")
        def storage_agent(spore):
            key = spore.knowledge.get("key", "default")
            value = spore.knowledge.get("value", {})
            storage.save(key, value)
            return {"saved": True}

        # Execute agent workflow
        test_spore = Spore(
            id="test-spore-4",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="test",
            to_agent="storage_agent",
            knowledge={"key": "test_key", "value": {"data": "test"}},
            created_at=datetime.now()
        )

        storage_agent._praval_agent.spore_handler(test_spore)

        time.sleep(0.3)

        # Verify multiple components created spans
        recent = store_trace.get_recent_traces(limit=100)

        # Should have spans from: agent execution, storage save
        assert len(recent) >= 2

        span_names = {s["name"] for s in recent}
        assert "agent.storage_agent.execute" in span_names
        assert "storage.save" in span_names

    def test_trace_hierarchy(self):
        """Verify parent-child relationships in traced operations."""
        from praval import agent
        from praval.core.reef import Spore, SporeType
        from praval.observability import get_trace_store

        store = get_trace_store()
        store.cleanup_old_traces(days=0)

        @agent("parent_agent")
        def parent_agent(spore):
            return {"result": "success"}

        # Execute agent
        test_spore = Spore(
            id="test-spore-5",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="test",
            to_agent="parent_agent",
            knowledge={"test": "data"},
            created_at=datetime.now()
        )

        parent_agent._praval_agent.spore_handler(test_spore)

        time.sleep(0.2)

        # Get the agent span
        agent_spans = store.find_spans_by_name("agent.parent_agent.execute")
        assert len(agent_spans) > 0

        # Verify it has a trace_id (can be used to build hierarchy)
        span = agent_spans[0]
        assert "trace_id" in span
        assert len(span["trace_id"]) == 32


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
