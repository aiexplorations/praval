"""
Tests for chained agent broadcasts.

This test suite verifies that broadcast() correctly sends messages to all agents
on the default channel, enabling agent chains to work as expected.
"""

import pytest
import time
from praval import agent, broadcast, start_agents


class TestBroadcastChaining:
    """Test agent chaining via broadcasts."""

    def test_simple_broadcast_reaches_all_agents(self):
        """Test that broadcast() sends to all agents on default channel."""
        execution_log = []

        @agent("broadcaster", responds_to=["trigger"])
        def broadcaster(spore):
            execution_log.append("broadcaster_started")
            broadcast({"type": "message", "content": "hello"})
            execution_log.append("broadcaster_done")

        @agent("listener1", responds_to=["message"])
        def listener1(spore):
            execution_log.append("listener1_received")

        @agent("listener2", responds_to=["message"])
        def listener2(spore):
            execution_log.append("listener2_received")

        # Start agents with initial trigger
        start_agents(
            broadcaster, listener1, listener2,
            initial_data={"type": "trigger"}
        )

        # Wait for async execution
        time.sleep(2)

        # Broadcaster should execute
        assert "broadcaster_started" in execution_log
        assert "broadcaster_done" in execution_log

        # Both listeners should receive the broadcast
        assert "listener1_received" in execution_log
        assert "listener2_received" in execution_log

    def test_agent_chain_broadcast(self):
        """Test multi-stage agent chain: researcher -> analyst -> writer."""
        execution_log = []

        @agent("researcher", responds_to=["query"])
        def researcher(spore):
            execution_log.append("researcher_started")
            broadcast({"type": "analysis_request", "data": "findings"})
            execution_log.append("researcher_done")

        @agent("analyst", responds_to=["analysis_request"])
        def analyst(spore):
            execution_log.append("analyst_started")
            broadcast({"type": "report", "insights": "analysis"})
            execution_log.append("analyst_done")

        @agent("writer", responds_to=["report"])
        def writer(spore):
            execution_log.append("writer_started")
            execution_log.append("writer_done")

        # Start pipeline
        start_agents(
            researcher, analyst, writer,
            initial_data={"type": "query", "topic": "test"}
        )

        # Wait for async execution
        time.sleep(3)

        # Verify chain execution order
        assert "researcher_started" in execution_log
        assert "researcher_done" in execution_log
        assert "analyst_started" in execution_log
        assert "analyst_done" in execution_log
        assert "writer_started" in execution_log
        assert "writer_done" in execution_log

        # Verify rough order (researcher should execute before analyst)
        researcher_idx = execution_log.index("researcher_started")
        analyst_idx = execution_log.index("analyst_started")
        writer_idx = execution_log.index("writer_started")
        assert researcher_idx < analyst_idx < writer_idx

    def test_broadcast_with_explicit_channel(self):
        """Test broadcast can target specific channels when specified."""
        execution_log = []

        @agent("sender", responds_to=["start"])
        def sender(spore):
            execution_log.append("sender_started")
            # Broadcast to a specific channel, not default
            broadcast({"type": "special"}, channel="special_channel")

        @agent("receiver1", responds_to=["special"])
        def receiver1(spore):
            execution_log.append("receiver1_received")

        @agent("receiver2", responds_to=["special"])
        def receiver2(spore):
            execution_log.append("receiver2_received")

        # Start agents - only sender should execute (no one listening on "special_channel")
        start_agents(
            sender, receiver1, receiver2,
            initial_data={"type": "start"}
        )

        # Wait for async execution
        time.sleep(2)

        # Sender should execute
        assert "sender_started" in execution_log

        # Receivers should NOT receive (they're on default channel, not "special_channel")
        # This verifies that explicit channels are isolated
        assert "receiver1_received" not in execution_log
        assert "receiver2_received" not in execution_log

    def test_broadcast_filters_by_message_type(self):
        """Test that agents correctly filter broadcasts by message type."""
        execution_log = []

        @agent("broadcaster", responds_to=["trigger"])
        def broadcaster(spore):
            execution_log.append("broadcaster_started")
            broadcast({"type": "type_a", "data": "message_a"})
            broadcast({"type": "type_b", "data": "message_b"})

        @agent("handler_a", responds_to=["type_a"])
        def handler_a(spore):
            execution_log.append("handler_a_received")

        @agent("handler_b", responds_to=["type_b"])
        def handler_b(spore):
            execution_log.append("handler_b_received")

        @agent("handler_all", responds_to=None)  # Responds to all
        def handler_all(spore):
            msg_type = spore.knowledge.get("type")
            if msg_type == "type_a":
                execution_log.append("handler_all_type_a")
            elif msg_type == "type_b":
                execution_log.append("handler_all_type_b")

        start_agents(
            broadcaster, handler_a, handler_b, handler_all,
            initial_data={"type": "trigger"}
        )

        time.sleep(2)

        # Each handler should only receive their matched types
        assert "handler_a_received" in execution_log
        assert "handler_b_received" in execution_log
        assert "handler_all_type_a" in execution_log
        assert "handler_all_type_b" in execution_log

    def test_agent_doesnt_receive_own_broadcast(self):
        """Test that agents don't receive their own broadcasts."""
        execution_log = []
        receive_count = {"count": 0}

        @agent("self_broadcaster", responds_to=["trigger", "self_message"])
        def self_broadcaster(spore):
            msg_type = spore.knowledge.get("type")
            if msg_type == "trigger":
                execution_log.append("broadcaster_triggered")
                broadcast({"type": "self_message", "data": "test"})
            elif msg_type == "self_message":
                receive_count["count"] += 1
                execution_log.append("self_received_own_broadcast")

        start_agents(
            self_broadcaster,
            initial_data={"type": "trigger"}
        )

        time.sleep(1)

        # Broadcaster should be triggered
        assert "broadcaster_triggered" in execution_log

        # Agent should NOT receive its own broadcast
        # (broadcasts are delivered to all except sender in ReefChannel._deliver_spore)
        assert "self_received_own_broadcast" not in execution_log
        assert receive_count["count"] == 0
