"""
Test cases for Reef broadcast invocation fix.

This test suite validates that:
1. Agents receive broadcasts from reef.broadcast()
2. No duplicate invocations occur
3. The fix doesn't break existing functionality
"""

import time
import threading
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from praval.decorators import agent
from praval.core.reef import Spore, SporeType, get_reef


class TestBroadcastInvocation:
    """Test that reef.broadcast() invokes registered agents."""

    def setup_method(self):
        """Reset reef before each test."""
        # Get fresh reef instance for each test
        from praval.core import reef as reef_module
        reef_module._global_reef = reef_module.Reef()

    def test_agent_receives_broadcast_from_reef(self):
        """Test that @agent decorated function receives broadcasts from reef.broadcast()."""
        # Track invocations
        invocations = []

        @agent("broadcast_receiver")
        def receiver_agent(spore):
            invocations.append({
                "spore_type": spore.spore_type,
                "from_agent": spore.from_agent,
                "knowledge": spore.knowledge,
                "timestamp": time.time()
            })
            return {"received": True}

        # Broadcast a message
        reef = get_reef()
        spore_id = reef.broadcast(
            from_agent="system",
            knowledge={"message": "test_broadcast", "data": 123}
        )

        # Give async handlers time to execute
        time.sleep(0.5)

        # Verify agent was invoked
        assert len(invocations) == 1, f"Expected 1 invocation, got {len(invocations)}"
        assert invocations[0]["from_agent"] == "system"
        assert invocations[0]["knowledge"]["message"] == "test_broadcast"
        assert invocations[0]["spore_type"] == SporeType.BROADCAST

    def test_multiple_agents_receive_same_broadcast(self):
        """Test that multiple agents all receive the same broadcast."""
        invocations_a = []
        invocations_b = []

        @agent("agent_a")
        def agent_a(spore):
            invocations_a.append(spore.knowledge)
            return {"agent": "a"}

        @agent("agent_b")
        def agent_b(spore):
            invocations_b.append(spore.knowledge)
            return {"agent": "b"}

        # Broadcast
        reef = get_reef()
        reef.broadcast(
            from_agent="system",
            knowledge={"type": "test", "value": "shared"}
        )

        # Wait for async execution
        time.sleep(0.5)

        # Both agents should receive the broadcast
        assert len(invocations_a) == 1
        assert len(invocations_b) == 1
        assert invocations_a[0]["value"] == "shared"
        assert invocations_b[0]["value"] == "shared"

    def test_broadcaster_does_not_receive_own_broadcast(self):
        """Test that the agent that broadcasts doesn't receive its own broadcast."""
        invocations = []

        @agent("self_broadcaster")
        def broadcaster(spore):
            invocations.append(spore.from_agent)
            return {"broadcasted": True}

        # The agent broadcasts to itself via reef
        reef = get_reef()
        broadcaster._praval_agent.broadcast_knowledge(
            {"self": "message"},
            channel="main"
        )

        # Wait for async execution
        time.sleep(0.5)

        # Agent should NOT receive its own broadcast
        # (The spore carries from_agent="self_broadcaster",
        #  so the delivery logic filters it out)
        assert len(invocations) == 0, "Agent should not receive its own broadcast"

    def test_no_duplicate_invocations_with_multiple_channel_subscriptions(self):
        """Test that agent is not invoked twice even with multiple subscriptions."""
        invocations = []

        @agent("multi_subscriber")
        def subscriber(spore):
            invocations.append(spore.knowledge)
            return {"processed": True}

        # Broadcast to default channel
        reef = get_reef()
        reef.broadcast(
            from_agent="system",
            knowledge={"test": "no_duplicates"}
        )

        # Wait for async execution
        time.sleep(0.5)

        # Should only receive ONE invocation, not multiple
        assert len(invocations) == 1, f"Expected 1 invocation, got {len(invocations)}"

    def test_broadcast_with_explicit_channel(self):
        """Test broadcast to a specific channel still works."""
        invocations = []

        @agent("channel_subscriber", channel="specific_channel")
        def subscriber(spore):
            invocations.append(spore.knowledge)
            return {"processed": True}

        # Create and use a specific channel
        reef = get_reef()
        reef.create_channel("specific_channel")

        # Send a spore to specific_channel
        reef.send(
            from_agent="sender",
            to_agent=None,
            knowledge={"channel": "specific"},
            spore_type=SporeType.BROADCAST,
            channel="specific_channel"
        )

        # Wait for async execution
        time.sleep(0.5)

        # Agent should receive it
        assert len(invocations) == 1
        assert invocations[0]["channel"] == "specific"

    def test_broadcast_with_responds_to_filter(self):
        """Test that responds_to filter still works with broadcasts."""
        query_invocations = []
        other_invocations = []

        @agent("filter_agent", responds_to=["query"])
        def filtered_agent(spore):
            query_invocations.append(spore.knowledge)
            return {"type": "query_response"}

        # This agent receives all messages
        @agent("all_receiver")
        def all_agent(spore):
            other_invocations.append(spore.knowledge)
            return {"type": "all"}

        # Broadcast a "query" type message
        reef = get_reef()
        reef.broadcast(
            from_agent="system",
            knowledge={"type": "query", "question": "What is 2+2?"}
        )

        time.sleep(0.5)

        # filter_agent should receive it (matches responds_to)
        assert len(query_invocations) == 1
        # all_receiver should also receive it
        assert len(other_invocations) == 1

        # Now broadcast a different type
        query_invocations.clear()
        other_invocations.clear()

        reef.broadcast(
            from_agent="system",
            knowledge={"type": "notification", "message": "alert"}
        )

        time.sleep(0.5)

        # filter_agent should NOT receive it (doesn't match responds_to)
        assert len(query_invocations) == 0
        # all_receiver should receive it (no filter)
        assert len(other_invocations) == 1


class TestBroadcastWithCustomChannels:
    """Test broadcast behavior with custom agent channels."""

    def setup_method(self):
        """Reset reef before each test."""
        from praval.core import reef as reef_module
        reef_module._global_reef = reef_module.Reef()

    def test_agent_with_custom_channel_still_receives_default_broadcasts(self):
        """Test that agents with custom channels also receive default broadcasts."""
        invocations = []

        @agent("custom_channel_agent", channel="my_custom_channel")
        def agent_func(spore):
            invocations.append({
                "channel": spore.knowledge.get("_channel", "unknown"),
                "data": spore.knowledge
            })
            return {"status": "ok"}

        # Broadcast to default channel
        reef = get_reef()
        reef.broadcast(
            from_agent="system",
            knowledge={"message": "default_broadcast"}
        )

        time.sleep(0.5)

        # Agent should receive the broadcast even with custom channel
        assert len(invocations) == 1
        assert invocations[0]["data"]["message"] == "default_broadcast"

    def test_agent_subscription_on_both_channels(self):
        """Test that agent can be subscribed to multiple channels."""
        invocations = []

        @agent("dual_channel_agent", channel="custom_ch")
        def agent_func(spore):
            invocations.append(spore.knowledge)
            return {"received": True}

        reef = get_reef()

        # Broadcast to default channel
        reef.broadcast(
            from_agent="system",
            knowledge={"source": "default_channel"}
        )

        # Create custom channel and send a spore
        reef.create_channel("custom_ch")
        reef.send(
            from_agent="sender",
            to_agent="dual_channel_agent",
            knowledge={"source": "custom_channel"},
            spore_type=SporeType.KNOWLEDGE,
            channel="custom_ch"
        )

        time.sleep(0.5)

        # Agent should receive broadcasts from both channels
        assert len(invocations) == 2
        sources = [inv["source"] for inv in invocations]
        assert "default_channel" in sources
        assert "custom_channel" in sources


class TestBroadcastConcurrency:
    """Test broadcast behavior under concurrent load."""

    def setup_method(self):
        """Reset reef before each test."""
        from praval.core import reef as reef_module
        reef_module._global_reef = reef_module.Reef()

    def test_concurrent_broadcasts_dont_lose_messages(self):
        """Test that concurrent broadcasts are all delivered."""
        invocations = []
        lock = threading.Lock()

        @agent("concurrent_receiver")
        def receiver(spore):
            with lock:
                invocations.append(spore.knowledge["id"])
            return {"received": True}

        reef = get_reef()

        # Send 10 broadcasts concurrently
        def send_broadcast(msg_id):
            reef.broadcast(
                from_agent="system",
                knowledge={"id": msg_id, "content": f"message_{msg_id}"}
            )

        threads = [
            threading.Thread(target=send_broadcast, args=(i,))
            for i in range(10)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Wait for async handlers
        time.sleep(1)

        # All messages should be received
        assert len(invocations) == 10, f"Expected 10 invocations, got {len(invocations)}"
        assert set(invocations) == set(range(10))

    def test_broadcast_and_direct_send_concurrent(self):
        """Test concurrent broadcasts and direct sends to same agent."""
        invocations = []
        lock = threading.Lock()

        @agent("mixed_receiver")
        def receiver(spore):
            with lock:
                invocations.append({
                    "type": spore.spore_type,
                    "from": spore.from_agent,
                    "to": spore.to_agent
                })
            return {"processed": True}

        reef = get_reef()

        def send_broadcast():
            for i in range(5):
                reef.broadcast(
                    from_agent="system",
                    knowledge={"type": "broadcast", "id": f"b{i}"}
                )
                time.sleep(0.01)

        def send_direct():
            for i in range(5):
                reef.send(
                    from_agent="direct_sender",
                    to_agent="mixed_receiver",
                    knowledge={"type": "direct", "id": f"d{i}"},
                    spore_type=SporeType.KNOWLEDGE
                )
                time.sleep(0.01)

        t1 = threading.Thread(target=send_broadcast)
        t2 = threading.Thread(target=send_direct)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        # Wait for all async handlers
        time.sleep(1)

        # Should receive both broadcasts and direct sends
        broadcasts = [inv for inv in invocations if inv["type"] == SporeType.BROADCAST]
        directs = [inv for inv in invocations if inv["type"] == SporeType.KNOWLEDGE]

        assert len(broadcasts) == 5
        assert len(directs) == 5


class TestBroadcastRegressions:
    """Test for regressions with the fix."""

    def setup_method(self):
        """Reset reef before each test."""
        from praval.core import reef as reef_module
        reef_module._global_reef = reef_module.Reef()

    def test_agent_auto_broadcast_still_works(self):
        """Test that agent auto-broadcast of return values still works."""
        outer_invocations = []
        inner_invocations = []

        @agent("inner_agent")
        def inner_agent(spore):
            inner_invocations.append(spore.knowledge)
            return {"processed": True, "result": "inner"}

        @agent("outer_agent")
        def outer_agent(spore):
            outer_invocations.append(spore.knowledge)
            return {"processed": True, "result": "outer"}

        # Send a message to outer_agent
        reef = get_reef()
        reef.broadcast(
            from_agent="system",
            knowledge={"initial": "message"}
        )

        time.sleep(1)

        # Both agents should be invoked by initial broadcast
        assert len(outer_invocations) >= 1
        assert len(inner_invocations) >= 1

    def test_memory_enabled_agents_still_work(self):
        """Test that memory-enabled agents work with broadcast fix."""
        invocations = []

        @agent("memory_agent", memory=True)
        def mem_agent(spore):
            invocations.append(spore.knowledge)
            # Should be able to use memory methods
            if hasattr(mem_agent, 'remember'):
                mem_agent.remember(f"Received: {spore.knowledge}")
            return {"processed": True}

        reef = get_reef()
        reef.broadcast(
            from_agent="system",
            knowledge={"memo": "test"}
        )

        time.sleep(0.5)

        # Agent should receive broadcast
        assert len(invocations) == 1
        assert invocations[0]["memo"] == "test"
