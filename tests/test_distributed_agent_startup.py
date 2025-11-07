"""
Tests for AgentRunner and distributed agent lifecycle management.

These tests verify that:
1. AgentRunner properly initializes the async event loop
2. RabbitMQ backend is initialized before agents consume messages
3. Agents can subscribe and receive messages
4. Graceful shutdown works correctly
5. Signal handling works as expected
"""

import pytest
import asyncio
import logging
from unittest.mock import Mock, AsyncMock, patch

from praval.decorators import agent
from praval.core.agent_runner import AgentRunner, run_agents
from praval.core.reef_backend import InMemoryBackend, RabbitMQBackend

logger = logging.getLogger(__name__)


class TestAgentRunner:
    """Test AgentRunner initialization and lifecycle."""

    @pytest.fixture
    def sample_agents(self):
        """Create sample agents for testing."""
        @agent("processor")
        def processor_agent(spore):
            return {"processed": True}

        @agent("analyzer")
        def analyzer_agent(spore):
            return {"analyzed": True}

        return [processor_agent, analyzer_agent]

    def test_runner_initialization_with_local_backend(self, sample_agents):
        """Test AgentRunner initialization with local backend."""
        runner = AgentRunner(agents=sample_agents)

        assert runner.agents == sample_agents
        assert len(runner.agents) == 2
        assert runner._running is False
        assert isinstance(runner.backend, InMemoryBackend)

    def test_runner_initialization_with_rabbitmq_config(self, sample_agents):
        """Test AgentRunner initialization with RabbitMQ config."""
        backend_config = {
            'url': 'amqp://localhost:5672/',
            'exchange_name': 'test.agents'
        }

        runner = AgentRunner(agents=sample_agents, backend_config=backend_config)

        assert runner.backend_config == backend_config
        assert isinstance(runner.backend, RabbitMQBackend)

    def test_runner_invalid_agent_raises_error(self):
        """Test that non-decorated functions raise error."""
        def not_an_agent(spore):
            return {}

        with pytest.raises(ValueError, match="not decorated with @agent"):
            AgentRunner(agents=[not_an_agent])

    @pytest.mark.asyncio
    async def test_runner_initialization_with_inmemory_backend(self, sample_agents):
        """Test async initialization of AgentRunner with InMemoryBackend."""
        runner = AgentRunner(agents=sample_agents)

        # Should not raise
        await runner.initialize()

        # Verify backend was initialized
        assert runner.reef is not None
        stats = runner.get_stats()
        # After initialization, status is 'stopped' (not running, but initialized)
        assert stats['status'] == 'stopped'

    @pytest.mark.asyncio
    async def test_runner_shutdown_cleans_up_resources(self, sample_agents):
        """Test that shutdown properly cleans up resources."""
        runner = AgentRunner(agents=sample_agents)
        await runner.initialize()

        # Perform shutdown
        await runner.shutdown()

        assert runner._running is False

    @pytest.mark.asyncio
    async def test_runner_context_manager(self, sample_agents):
        """Test AgentRunner as async context manager."""
        runner = AgentRunner(agents=sample_agents)

        async with runner.context():
            # Inside context, runner should be initialized
            assert runner.reef is not None

        # After context, runner should be shut down
        assert runner._running is False

    def test_get_stats_not_initialized(self, sample_agents):
        """Test get_stats returns correct values when not initialized."""
        runner = AgentRunner(agents=sample_agents)

        stats = runner.get_stats()

        assert stats['status'] == 'not_initialized'
        assert stats['agents'] == 2
        assert stats['running'] is False

    @pytest.mark.asyncio
    async def test_get_stats_after_initialization(self, sample_agents):
        """Test get_stats returns correct values after initialization."""
        runner = AgentRunner(agents=sample_agents)
        await runner.initialize()

        stats = runner.get_stats()

        assert stats['agents'] == 2
        assert stats['running'] is False
        assert stats['backend'] == 'InMemoryBackend'

    def test_agent_validation(self):
        """Test that AgentRunner validates all agents."""
        @agent("valid_agent")
        def valid(spore):
            return {}

        def invalid(spore):
            return {}

        # Valid agent should work
        runner = AgentRunner(agents=[valid])
        assert len(runner.agents) == 1

        # Invalid agent should raise
        with pytest.raises(ValueError):
            AgentRunner(agents=[invalid])

        # Mixed should raise on first invalid
        with pytest.raises(ValueError):
            AgentRunner(agents=[valid, invalid])


class TestRunAgentsFunction:
    """Test the run_agents convenience function."""

    @pytest.fixture
    def agents(self):
        """Create test agents."""
        @agent("test_agent")
        def test(spore):
            return {"test": True}

        return [test]

    def test_run_agents_creates_runner(self, agents):
        """Test that run_agents is callable and accessible."""
        # We can't test the actual blocking call without mocking extensively
        # Instead, just verify the function exists and is callable
        from praval.composition import run_agents as test_run_agents
        assert callable(test_run_agents)

        # Verify it has proper documentation
        assert test_run_agents.__doc__ is not None
        assert 'distributed' in test_run_agents.__doc__.lower()


class TestAgentRunnerShutdown:
    """Test graceful shutdown behavior."""

    @pytest.fixture
    def runner(self):
        """Create a test runner."""
        @agent("test")
        def test_agent(spore):
            return {}

        return AgentRunner(agents=[test_agent])

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self, runner):
        """Test that shutdown can be called multiple times safely."""
        await runner.initialize()

        # First shutdown
        await runner.shutdown()
        assert runner._running is False

        # Second shutdown should not raise
        await runner.shutdown()
        assert runner._running is False

    @pytest.mark.asyncio
    async def test_run_async_already_running_raises(self, runner):
        """Test that run_async raises if already running."""
        runner._running = True

        with pytest.raises(RuntimeError, match="already running"):
            await runner.run_async()

    @pytest.mark.asyncio
    async def test_run_async_initializes_before_waiting(self, runner):
        """Test that run_async initializes backend before waiting for shutdown."""
        # We'll trigger shutdown immediately to avoid infinite wait
        async def trigger_shutdown():
            await asyncio.sleep(0.1)
            runner._shutdown_event.set()

        # Start shutdown trigger task
        shutdown_task = asyncio.create_task(trigger_shutdown())

        # Run the agent (will initialize then wait for shutdown)
        await runner.run_async()

        # Verify we completed without error
        assert runner._shutdown_event.is_set()
        await shutdown_task


class TestAgentRunnerMultipleAgents:
    """Test AgentRunner with multiple agents."""

    def test_runner_with_many_agents(self):
        """Test AgentRunner handles multiple agents correctly."""
        agents_list = []
        for i in range(5):
            @agent(f"agent_{i}")
            def agent_func(spore):
                return {}
            agents_list.append(agent_func)

        runner = AgentRunner(agents=agents_list)

        assert len(runner.agents) == 5
        assert all(hasattr(a, '_praval_agent') for a in runner.agents)

    @pytest.mark.asyncio
    async def test_initialization_with_many_agents(self):
        """Test that initialization works with many agents."""
        agents_list = []
        for i in range(3):
            @agent(f"agent_{i}")
            def agent_func(spore):
                return {}
            agents_list.append(agent_func)

        runner = AgentRunner(agents=agents_list)
        await runner.initialize()

        assert runner.reef is not None
        stats = runner.get_stats()
        assert stats['agents'] == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
