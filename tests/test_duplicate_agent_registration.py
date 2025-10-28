"""
Tests for duplicate agent registration in interactive environments.

This tests the fix for the issue where re-registering an agent
(common in Jupyter notebooks) would cause duplicate message handling.
"""

import pytest
import time
from praval import agent, start_agents, broadcast
from praval.core.reef import get_reef
from praval.core.registry import get_registry


def test_agent_reregistration_replaces_handler():
    """
    Test that re-registering an agent replaces its handler instead of adding duplicates.
    This is critical for interactive environments like Jupyter notebooks.
    """
    # Track how many times the agent responds
    response_count = []

    # Define agent first time
    @agent("test_agent_unique_1", responds_to=["test_message"])
    def first_agent(spore):
        """First version of the agent."""
        response_count.append(1)
        return {"version": 1}

    # Send a message
    result = start_agents(
        first_agent,
        initial_data={"type": "test_message", "content": "hello"}
    )
    time.sleep(0.1)  # Allow async handlers to execute

    # Should have responded once
    assert len(response_count) == 1, f"Expected 1 response, got {len(response_count)}"

    # Clear response count
    response_count.clear()

    # Re-define the same agent with THE SAME NAME (simulating re-running a notebook cell)
    @agent("test_agent_unique_1", responds_to=["test_message"])
    def first_agent(spore):
        """Second version of the agent - same name."""
        response_count.append(1)
        return {"version": 2}

    # Send another message
    result = start_agents(
        first_agent,
        initial_data={"type": "test_message", "content": "hello again"}
    )
    time.sleep(0.1)  # Allow async handlers to execute

    # Should still respond only once (not twice!)
    assert len(response_count) == 1, f"Expected 1 response after re-registration, got {len(response_count)}. This means the old handler wasn't replaced!"


def test_channel_subscribe_replace_default():
    """Test that Channel.subscribe() replaces by default."""
    reef = get_reef()
    reef.channels.clear()

    channel = reef.create_channel("test_channel")

    # Track calls
    call_count = []

    def handler1(spore):
        call_count.append(1)

    def handler2(spore):
        call_count.append(2)

    # Subscribe first handler
    channel.subscribe("agent1", handler1)

    # Verify one handler
    assert len(channel.subscribers["agent1"]) == 1

    # Subscribe second handler (should replace)
    channel.subscribe("agent1", handler2)

    # Should still have only one handler
    assert len(channel.subscribers["agent1"]) == 1, "Handler should have been replaced, not appended"

    # Verify it's the second handler by checking the function
    assert channel.subscribers["agent1"][0] == handler2


def test_channel_subscribe_no_replace():
    """Test that Channel.subscribe(replace=False) appends handlers."""
    reef = get_reef()
    reef.channels.clear()

    channel = reef.create_channel("test_channel")

    def handler1(spore):
        pass

    def handler2(spore):
        pass

    # Subscribe first handler
    channel.subscribe("agent1", handler1, replace=False)

    # Verify one handler
    assert len(channel.subscribers["agent1"]) == 1

    # Subscribe second handler without replacing
    channel.subscribe("agent1", handler2, replace=False)

    # Should now have two handlers
    assert len(channel.subscribers["agent1"]) == 2, "Handler should have been appended when replace=False"


def test_multiple_agents_independent():
    """Test that different agents don't interfere with each other."""
    response_counts = {"agent1": 0, "agent2": 0}

    @agent("unique_agent1", responds_to=["test"])
    def first_agent(spore):
        response_counts["agent1"] += 1
        return {"agent": 1}

    @agent("unique_agent2", responds_to=["test"])
    def second_agent(spore):
        response_counts["agent2"] += 1
        return {"agent": 2}

    # Both agents should respond once
    start_agents(
        first_agent,
        second_agent,
        initial_data={"type": "test"}
    )
    time.sleep(0.1)  # Allow async handlers to execute

    assert response_counts["agent1"] == 1
    assert response_counts["agent2"] == 1

    # Re-register agent1
    @agent("unique_agent1", responds_to=["test"])
    def first_agent(spore):
        response_counts["agent1"] += 1
        return {"agent": 1, "version": 2}

    # Send another message
    start_agents(
        first_agent,
        second_agent,
        initial_data={"type": "test"}
    )
    time.sleep(0.1)  # Allow async handlers to execute

    # Agent1 should have responded once more (not twice!)
    assert response_counts["agent1"] == 2, f"Agent1 responded {response_counts['agent1'] - 1} times on second call, expected 1"
    # Agent2 should also have responded once more
    assert response_counts["agent2"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
