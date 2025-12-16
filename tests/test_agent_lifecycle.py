"""
Tests for Agent lifecycle management.

Verifies Agent.close() and context manager functionality.
Part of rearchitecture issue M2.
"""

import logging
from unittest.mock import Mock, MagicMock, patch

import pytest


class TestAgentClose:
    """Tests for Agent.close() method."""

    def test_agent_close_sets_closed_flag(self):
        """Verify close() sets _closed flag."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            agent = Agent("test_close")
            assert not agent._closed
            assert not agent.is_closed

            agent.close()

            assert agent._closed
            assert agent.is_closed

    def test_agent_close_is_idempotent(self):
        """Verify calling close() multiple times is safe."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            agent = Agent("test_idempotent")
            agent.close()
            agent.close()  # Should not raise
            agent.close()  # Should not raise

            assert agent._closed

    def test_agent_close_clears_conversation_history(self):
        """Verify close() clears conversation history."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            agent = Agent("test_history")
            agent.conversation_history = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ]

            agent.close()

            assert len(agent.conversation_history) == 0

    def test_agent_close_clears_subscriptions(self):
        """Verify close() unsubscribes from reef channels."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent
            from praval.core.reef import get_reef, reset_reef

            reset_reef()

            agent = Agent("test_subscriptions")
            agent.subscribe_to_channel("test_channel_1")
            agent.subscribe_to_channel("test_channel_2")

            assert len(agent._subscribed_channels) == 2

            reef = get_reef()
            channel1 = reef.get_channel("test_channel_1")
            channel2 = reef.get_channel("test_channel_2")
            assert "test_subscriptions" in channel1.subscribers
            assert "test_subscriptions" in channel2.subscribers

            agent.close()

            assert len(agent._subscribed_channels) == 0
            assert "test_subscriptions" not in channel1.subscribers
            assert "test_subscriptions" not in channel2.subscribers

    def test_agent_close_releases_memory(self):
        """Verify close() releases memory system."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            agent = Agent("test_memory", memory_enabled=False)

            # Set up mock memory with shutdown method
            mock_memory = MagicMock()
            agent.memory = mock_memory

            agent.close()

            mock_memory.shutdown.assert_called_once()
            assert agent.memory is None

    def test_agent_close_handles_memory_without_shutdown(self):
        """Verify close() handles memory without shutdown method."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            agent = Agent("test_no_shutdown", memory_enabled=False)

            # Set up mock memory without shutdown method
            mock_memory = Mock(spec=[])  # No methods
            agent.memory = mock_memory

            agent.close()  # Should not raise

            assert agent.memory is None

    def test_agent_close_handles_errors_gracefully(self, caplog):
        """Verify close() handles errors during cleanup."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            agent = Agent("test_error_handling", memory_enabled=False)

            # Set up memory that raises on shutdown
            mock_memory = MagicMock()
            mock_memory.shutdown.side_effect = RuntimeError("Shutdown failed")
            agent.memory = mock_memory

            with caplog.at_level(logging.WARNING, logger="praval.core.agent"):
                agent.close()  # Should not raise

            assert agent._closed
            assert agent.memory is None
            # Should have logged warning
            assert any("Error shutting down memory" in r.message for r in caplog.records)

    def test_agent_close_handles_reef_errors(self, caplog):
        """Verify close() handles reef cleanup errors gracefully."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            agent = Agent("test_reef_error", memory_enabled=False)
            agent._subscribed_channels = ["broken_channel"]

            # Mock get_reef at the reef module level (since it's imported inside close())
            with patch("praval.core.reef.get_reef") as mock_get_reef:
                mock_get_reef.side_effect = RuntimeError("Reef error")

                with caplog.at_level(logging.WARNING, logger="praval.core.agent"):
                    agent.close()  # Should not raise

            assert agent._closed


class TestAgentContextManager:
    """Tests for Agent context manager support."""

    def test_agent_as_context_manager(self):
        """Verify agent works as context manager."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            with Agent("ctx_test") as agent:
                assert not agent._closed
                assert agent.name == "ctx_test"

            assert agent._closed

    def test_context_manager_calls_close_on_exception(self):
        """Verify context manager calls close() even on exception."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            agent = None
            try:
                with Agent("ctx_exception") as agent:
                    raise ValueError("Test exception")
            except ValueError:
                pass

            assert agent is not None
            assert agent._closed

    def test_context_manager_returns_agent(self):
        """Verify __enter__ returns the agent itself."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            agent = Agent("ctx_return")
            result = agent.__enter__()

            assert result is agent
            agent.close()

    def test_nested_context_managers(self):
        """Verify nested context managers work correctly."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            with Agent("outer") as outer:
                with Agent("inner") as inner:
                    assert not outer._closed
                    assert not inner._closed

                assert not outer._closed
                assert inner._closed

            assert outer._closed


class TestAgentDestructor:
    """Tests for Agent __del__ behavior."""

    def test_destructor_calls_close(self):
        """Verify __del__ calls close if not already closed."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            agent = Agent("del_test")
            agent._closed = False

            # Manually call __del__
            agent.__del__()

            assert agent._closed

    def test_destructor_skips_if_already_closed(self):
        """Verify __del__ skips cleanup if already closed."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            agent = Agent("del_skip")
            agent.close()

            # Track if close is called again
            close_called = []
            original_close = agent.close

            def tracking_close():
                close_called.append(True)
                original_close()

            agent.close = tracking_close
            agent._closed = True  # Ensure it's marked closed

            agent.__del__()

            assert len(close_called) == 0

    def test_destructor_handles_errors(self):
        """Verify __del__ suppresses errors."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            agent = Agent("del_error")

            # Make close() raise
            def bad_close():
                raise RuntimeError("Close failed")

            agent.close = bad_close
            agent._closed = False

            # Should not raise
            agent.__del__()


class TestAgentSubscriptionTracking:
    """Tests for subscription tracking."""

    def test_subscribe_tracks_channel(self):
        """Verify subscribe_to_channel tracks the subscription."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent
            from praval.core.reef import reset_reef

            reset_reef()

            agent = Agent("track_test")
            assert len(agent._subscribed_channels) == 0

            agent.subscribe_to_channel("channel_a")
            assert "channel_a" in agent._subscribed_channels

            agent.subscribe_to_channel("channel_b")
            assert "channel_b" in agent._subscribed_channels
            assert len(agent._subscribed_channels) == 2

            agent.close()

    def test_unsubscribe_removes_from_tracking(self):
        """Verify unsubscribe_from_channel removes from tracking."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent
            from praval.core.reef import reset_reef

            reset_reef()

            agent = Agent("untrack_test")
            agent.subscribe_to_channel("channel_x")
            assert "channel_x" in agent._subscribed_channels

            agent.unsubscribe_from_channel("channel_x")
            assert "channel_x" not in agent._subscribed_channels

            agent.close()

    def test_duplicate_subscribe_not_tracked_twice(self):
        """Verify subscribing twice doesn't duplicate tracking."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent
            from praval.core.reef import reset_reef

            reset_reef()

            agent = Agent("dup_test")
            agent.subscribe_to_channel("channel_dup")
            agent.subscribe_to_channel("channel_dup")

            assert agent._subscribed_channels.count("channel_dup") == 1

            agent.close()


class TestAgentLifecycleInitialization:
    """Tests for lifecycle attribute initialization."""

    def test_agent_initializes_closed_false(self):
        """Verify _closed is False on initialization."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            agent = Agent("init_test")
            assert agent._closed is False
            agent.close()

    def test_agent_initializes_empty_subscriptions(self):
        """Verify _subscribed_channels is empty on initialization."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            agent = Agent("init_subs")
            assert agent._subscribed_channels == []
            agent.close()

    def test_is_closed_property(self):
        """Verify is_closed property reflects state."""
        with patch("praval.core.agent.ProviderFactory"):
            from praval import Agent

            agent = Agent("prop_test")
            assert agent.is_closed is False

            agent.close()
            assert agent.is_closed is True
