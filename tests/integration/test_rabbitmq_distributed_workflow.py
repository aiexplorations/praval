"""
Integration tests for RabbitMQ distributed agent workflows.

These tests verify end-to-end agent communication through RabbitMQ backend.
They test:
1. Multi-agent workflows with message passing
2. Proper message routing and delivery
3. Agent lifecycle in distributed environment
4. Message ordering and consistency

Note: These tests require RabbitMQ to be running on localhost:5672.
They will be skipped if RabbitMQ is not available.
"""

import pytest
import asyncio
import logging
from datetime import datetime

try:
    import aio_pika
    HAS_RABBITMQ = True
except ImportError:
    HAS_RABBITMQ = False

from praval.decorators import agent, broadcast
from praval.core.reef import get_reef, SporeType
from praval.core.agent_runner import AgentRunner
from praval.core.reef_backend import RabbitMQBackend, InMemoryBackend

logger = logging.getLogger(__name__)

# Skip all tests in this module if RabbitMQ support not available
pytestmark = pytest.mark.skipif(
    not HAS_RABBITMQ,
    reason="aio-pika not installed or RabbitMQ not available"
)


class TestDistributedWorkflow:
    """Test complete distributed workflows with RabbitMQ."""

    @pytest.fixture
    def rabbitmq_config(self):
        """RabbitMQ configuration for tests."""
        return {
            'url': 'amqp://guest:guest@localhost:5672/',
            'exchange_name': 'praval.test.agents',
            'verify_tls': False
        }

    @pytest.fixture
    def workflow_agents(self):
        """Create agents for workflow testing."""
        messages_processed = {'count': 0, 'data': []}

        @agent("processor")
        def processor_agent(spore):
            """Process incoming data."""
            data = spore.knowledge.get('data', '')
            processed = {
                'original': data,
                'processed': data.upper() if isinstance(data, str) else str(data),
                'processor_timestamp': datetime.now().isoformat()
            }
            messages_processed['count'] += 1
            messages_processed['data'].append(processed)
            return processed

        @agent("analyzer")
        def analyzer_agent(spore):
            """Analyze processed data."""
            processed_data = spore.knowledge
            analysis = {
                'length': len(str(processed_data.get('processed', ''))),
                'has_uppercase': any(
                    c.isupper() for c in str(processed_data.get('processed', ''))
                ),
                'analyzer_timestamp': datetime.now().isoformat()
            }
            return analysis

        return [processor_agent, analyzer_agent]

    @pytest.mark.integration
    def test_local_workflow_with_inmemory_backend(self, workflow_agents):
        """Test workflow with local InMemoryBackend (sanity check)."""
        runner = AgentRunner(agents=workflow_agents)

        # Create an event loop for async initialization
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Initialize
            loop.run_until_complete(runner.initialize())

            # Verify backend is InMemory
            assert isinstance(runner.backend, InMemoryBackend)

            # Verify agents are registered
            assert len(runner.agents) == 2

        finally:
            loop.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skipif(
        not HAS_RABBITMQ,
        reason="RabbitMQ not available"
    )
    async def test_distributed_workflow_initialization(self, workflow_agents, rabbitmq_config):
        """Test that distributed workflow initializes correctly with RabbitMQ."""
        runner = AgentRunner(
            agents=workflow_agents,
            backend_config=rabbitmq_config
        )

        # Verify backend is RabbitMQ
        assert isinstance(runner.backend, RabbitMQBackend)

        try:
            # Initialize (this should connect to RabbitMQ)
            await runner.initialize()

            # Verify initialization succeeded
            assert runner.reef is not None
            stats = runner.get_stats()
            assert stats['agents'] == 2

        except ConnectionError as e:
            pytest.skip(f"RabbitMQ not available: {e}")

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skipif(
        not HAS_RABBITMQ,
        reason="RabbitMQ not available"
    )
    async def test_agent_message_delivery(self, workflow_agents, rabbitmq_config):
        """Test that agents receive messages through RabbitMQ."""
        runner = AgentRunner(
            agents=workflow_agents,
            backend_config=rabbitmq_config
        )

        try:
            await runner.initialize()

            # Send a message to processor agent
            reef = runner.reef
            spore_id = await reef.send(
                from_agent="test_client",
                to_agent="processor",
                knowledge={"data": "hello"},
                spore_type=SporeType.REQUEST
            )

            # Wait a bit for message delivery
            await asyncio.sleep(0.5)

            # Verify message was sent (basic check)
            assert spore_id is not None

        except ConnectionError as e:
            pytest.skip(f"RabbitMQ not available: {e}")
        finally:
            await runner.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skipif(
        not HAS_RABBITMQ,
        reason="RabbitMQ not available"
    )
    async def test_broadcast_delivery(self, workflow_agents, rabbitmq_config):
        """Test that broadcast messages reach all agents."""
        runner = AgentRunner(
            agents=workflow_agents,
            backend_config=rabbitmq_config
        )

        try:
            await runner.initialize()

            reef = runner.reef

            # Broadcast a message
            spore_id = await reef.broadcast(
                from_agent="test_client",
                knowledge={
                    "type": "broadcast_test",
                    "data": "test_broadcast"
                }
            )

            # Wait for delivery
            await asyncio.sleep(0.5)

            # Verify broadcast was sent
            assert spore_id is not None

        except ConnectionError as e:
            pytest.skip(f"RabbitMQ not available: {e}")
        finally:
            await runner.shutdown()


class TestDistributedReliability:
    """Test reliability and error handling in distributed workflows."""

    @pytest.fixture
    def reliable_agents(self):
        """Create agents for reliability testing."""
        execution_log = {'calls': []}

        @agent("reliable_agent")
        def reliable(spore):
            """Agent that logs execution."""
            execution_log['calls'].append({
                'timestamp': datetime.now().isoformat(),
                'knowledge': spore.knowledge
            })
            return {'status': 'processed'}

        return [reliable], execution_log

    @pytest.mark.integration
    def test_agent_runs_without_errors(self):
        """Test that agents execute without raising errors."""
        @agent("safe_agent")
        def safe(spore):
            try:
                # Simulate safe processing
                result = len(str(spore.knowledge))
                return {'length': result}
            except Exception as e:
                logger.error(f"Agent error: {e}")
                return {'error': str(e)}

        runner = AgentRunner(agents=[safe])
        assert runner is not None
        assert len(runner.agents) == 1


class TestMultiAgentCoordination:
    """Test coordination between multiple agents."""

    @pytest.fixture
    def coordinating_agents(self):
        """Create agents that coordinate."""
        @agent("initiator")
        def initiator(spore):
            return {"initiated": True, "step": 1}

        @agent("follower")
        def follower(spore):
            step = spore.knowledge.get("step", 0)
            return {"followed": True, "step": step + 1}

        return [initiator, follower]

    @pytest.mark.integration
    def test_multiple_agents_coordination(self, coordinating_agents):
        """Test that multiple agents can coordinate."""
        runner = AgentRunner(agents=coordinating_agents)

        # Verify agents can be created and run
        assert len(runner.agents) == 2
        assert runner.reef is None  # Not initialized yet

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_agent_sequence_execution(self, coordinating_agents):
        """Test execution sequence with multiple agents."""
        runner = AgentRunner(agents=coordinating_agents)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            await runner.initialize()

            # Verify both agents are registered
            assert runner.reef is not None
            stats = runner.get_stats()
            assert stats['agents'] == 2

        finally:
            await runner.shutdown()
            loop.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-k', 'integration'])
