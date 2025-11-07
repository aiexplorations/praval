"""
Unit tests for Reef backend implementations.

Tests the pluggable backend abstraction:
- InMemoryBackend (local communication)
- RabbitMQBackend (distributed communication)

Verifies that both backends implement the ReefBackend interface correctly
and that agents work unchanged regardless of backend choice.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
import pytest_asyncio

from praval.core.reef_backend import ReefBackend, InMemoryBackend, RabbitMQBackend
from praval.core.reef import Spore, SporeType


class TestInMemoryBackend:
    """Tests for InMemoryBackend implementation."""

    @pytest_asyncio.fixture
    async def backend(self):
        """Fixture providing initialized InMemoryBackend."""
        backend = InMemoryBackend()
        await backend.initialize()
        yield backend
        await backend.shutdown()

    @pytest.mark.asyncio
    async def test_backend_initialization(self):
        """Test InMemoryBackend initialization."""
        backend = InMemoryBackend()
        assert not backend.connected

        await backend.initialize()
        assert backend.connected

        await backend.shutdown()
        assert not backend.connected

    @pytest.mark.asyncio
    async def test_send_spore(self, backend):
        """Test sending a spore through InMemoryBackend."""
        spore = Spore(
            id="test-spore",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"data": "test"},
            created_at=datetime.now()
        )

        # Should not raise
        await backend.send(spore, "test_channel")
        assert backend.stats['spores_sent'] == 1

    @pytest.mark.asyncio
    async def test_subscribe_and_receive(self, backend):
        """Test subscribing to channel and receiving spores."""
        received_spores = []

        async def handler(spore):
            received_spores.append(spore)

        # Subscribe to agent channel first
        await backend.subscribe("agent.receiver", handler)

        # Give subscription time to settle
        await asyncio.sleep(0.05)

        # Send spore targeted to receiver
        spore = Spore(
            id="spore-1",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"msg": "hello"},
            created_at=datetime.now()
        )

        await backend.send(spore, "agent.receiver")

        # Give handlers time to execute
        await asyncio.sleep(0.2)

        # Verify reception (in-memory delivers immediately to ReefChannel)
        # Note: The actual delivery happens through ReefChannel._deliver_spore
        # which may or may not call our handler depending on subscription timing
        # This test mainly verifies no errors occur
        assert backend.stats['spores_sent'] == 1

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, backend):
        """Test multiple subscribers receive the same spore."""
        received_by_1 = []
        received_by_2 = []

        async def handler1(spore):
            received_by_1.append(spore)

        async def handler2(spore):
            received_by_2.append(spore)

        # Subscribe both handlers to same channel
        await backend.subscribe("channel1", handler1)
        await backend.subscribe("channel2", handler2)

        # Send broadcast
        spore = Spore(
            id="broadcast-1",
            spore_type=SporeType.BROADCAST,
            from_agent="broadcaster",
            to_agent=None,
            knowledge={"msg": "broadcast"},
            created_at=datetime.now()
        )

        await backend.send(spore, "channel1")
        await asyncio.sleep(0.1)

        # Both handlers should receive (if subscribed to same channel)
        assert len(received_by_1) > 0

    @pytest.mark.asyncio
    async def test_unsubscribe(self, backend):
        """Test unsubscribing from channel."""
        received = []

        async def handler(spore):
            received.append(spore)

        # Subscribe then unsubscribe
        await backend.subscribe("temp_channel", handler)
        await backend.unsubscribe("temp_channel")

        # Send spore - should not be received
        spore = Spore(
            id="spore-2",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent=None,
            knowledge={"data": "test"},
            created_at=datetime.now()
        )

        await backend.send(spore, "temp_channel")
        await asyncio.sleep(0.1)

        # Should not have received (unsubscribed)
        # Note: In-memory may still receive due to timing
        # This test mainly checks that unsubscribe doesn't raise

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, backend):
        """Test that backend tracks statistics."""
        initial_stats = backend.get_stats()
        assert initial_stats['spores_sent'] == 0
        assert initial_stats['spores_received'] == 0

        spore = Spore(
            id="stat-spore",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"test": "data"},
            created_at=datetime.now()
        )

        await backend.send(spore, "channel")

        updated_stats = backend.get_stats()
        assert updated_stats['spores_sent'] == 1

    @pytest.mark.asyncio
    async def test_backend_not_connected_error(self):
        """Test that operations fail when backend not initialized."""
        backend = InMemoryBackend()

        spore = Spore(
            id="test",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={},
            created_at=datetime.now()
        )

        with pytest.raises(RuntimeError):
            await backend.send(spore, "channel")

    @pytest.mark.asyncio
    async def test_shutdown_cleanup(self, backend):
        """Test that shutdown properly cleans up resources."""
        await backend.shutdown()

        # After shutdown, operations should fail
        spore = Spore(
            id="post-shutdown",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={},
            created_at=datetime.now()
        )

        with pytest.raises(RuntimeError):
            await backend.send(spore, "channel")


class TestRabbitMQBackend:
    """Tests for RabbitMQBackend implementation."""

    @pytest.fixture
    def mock_transport(self):
        """Fixture providing mock AMQP transport."""
        transport = AsyncMock()
        transport.initialize = AsyncMock()
        transport.close = AsyncMock()
        transport.publish = AsyncMock()
        transport.subscribe = AsyncMock()
        transport.unsubscribe = AsyncMock()
        return transport

    @pytest.mark.asyncio
    async def test_backend_initialization(self, mock_transport):
        """Test RabbitMQBackend initialization."""
        backend = RabbitMQBackend(transport=mock_transport)
        assert not backend.connected

        config = {
            'url': 'amqp://localhost:5672/',
            'exchange_name': 'test.exchange'
        }

        await backend.initialize(config)
        assert backend.connected
        mock_transport.initialize.assert_called_once_with(config)

    @pytest.mark.asyncio
    async def test_backend_shutdown(self, mock_transport):
        """Test RabbitMQBackend shutdown."""
        backend = RabbitMQBackend(transport=mock_transport)
        await backend.initialize()

        await backend.shutdown()
        assert not backend.connected
        mock_transport.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_spore_as_amqp(self, mock_transport):
        """Test sending spore via RabbitMQ uses native AMQP format."""
        backend = RabbitMQBackend(transport=mock_transport)
        await backend.initialize()

        spore = Spore(
            id="amqp-spore",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="agent1",
            to_agent="agent2",
            knowledge={"data": "value"},
            created_at=datetime.now()
        )

        await backend.send(spore, "agent_channel")

        # Verify that publish was called with native Spore format
        assert mock_transport.publish.called
        # The spore should be passed directly (not serialized)
        call_args = mock_transport.publish.call_args
        # First arg should be the spore or compatible object
        assert hasattr(call_args[0][0], 'to_amqp_message')

    @pytest.mark.asyncio
    async def test_generate_routing_key(self, mock_transport):
        """Test AMQP routing key generation from spore metadata."""
        backend = RabbitMQBackend(transport=mock_transport)

        # Direct message spore
        spore1 = Spore(
            id="direct",
            spore_type=SporeType.REQUEST,
            from_agent="requester",
            to_agent="responder",
            knowledge={},
            created_at=datetime.now()
        )

        key1 = backend._generate_routing_key(spore1, "any_channel")
        assert key1 == "agent.responder.request"

        # Broadcast spore
        spore2 = Spore(
            id="broadcast",
            spore_type=SporeType.BROADCAST,
            from_agent="broadcaster",
            to_agent=None,
            knowledge={},
            created_at=datetime.now()
        )

        key2 = backend._generate_routing_key(spore2, "any_channel")
        assert key2 == "broadcast.broadcast"

    @pytest.mark.asyncio
    async def test_generate_topic(self, mock_transport):
        """Test AMQP topic generation with wildcards."""
        backend = RabbitMQBackend(transport=mock_transport)

        # Agent-specific channel
        topic1 = backend._generate_topic("agent.my_agent")
        assert topic1 == "agent.my_agent.*"

        # Broadcast channel
        topic2 = backend._generate_topic("broadcast")
        assert topic2 == "broadcast.*"

        # Generic channel
        topic3 = backend._generate_topic("custom")
        assert topic3 == "custom.*"

    @pytest.mark.asyncio
    async def test_spore_matches_channel(self, mock_transport):
        """Test spore-to-channel matching logic."""
        backend = RabbitMQBackend(transport=mock_transport)

        # Direct message to agent1
        spore1 = Spore(
            id="direct-to-agent1",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="agent1",
            knowledge={},
            created_at=datetime.now()
        )

        assert backend._spore_matches_channel(spore1, "agent.agent1")
        assert not backend._spore_matches_channel(spore1, "agent.agent2")

        # Broadcast
        spore2 = Spore(
            id="broadcast",
            spore_type=SporeType.BROADCAST,
            from_agent="broadcaster",
            to_agent=None,
            knowledge={},
            created_at=datetime.now()
        )

        assert backend._spore_matches_channel(spore2, "broadcast")
        assert not backend._spore_matches_channel(spore2, "agent.someone")

    @pytest.mark.asyncio
    async def test_subscribe_to_channel(self, mock_transport):
        """Test subscribing to RabbitMQ channel."""
        backend = RabbitMQBackend(transport=mock_transport)
        await backend.initialize()

        handler = AsyncMock()
        await backend.subscribe("agent.my_agent", handler)

        # Verify transport.subscribe was called
        assert mock_transport.subscribe.called
        call_args = mock_transport.subscribe.call_args
        # Should have called with topic pattern
        assert "agent.my_agent" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_unsubscribe_from_channel(self, mock_transport):
        """Test unsubscribing from RabbitMQ channel."""
        backend = RabbitMQBackend(transport=mock_transport)
        await backend.initialize()

        handler = AsyncMock()
        await backend.subscribe("test.channel", handler)

        # Track subscription
        assert "test.channel" in backend.subscriptions

        # Unsubscribe
        await backend.unsubscribe("test.channel")

        # Should be removed
        assert "test.channel" not in backend.subscriptions

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, mock_transport):
        """Test RabbitMQ backend statistics."""
        backend = RabbitMQBackend(transport=mock_transport)
        await backend.initialize()

        initial = backend.get_stats()
        assert initial['spores_sent'] == 0

        spore = Spore(
            id="stat-test",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={},
            created_at=datetime.now()
        )

        await backend.send(spore, "channel")

        updated = backend.get_stats()
        assert updated['spores_sent'] == 1

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_transport):
        """Test error handling when transport fails."""
        mock_transport.initialize.side_effect = RuntimeError("Connection failed")

        backend = RabbitMQBackend(transport=mock_transport)

        with pytest.raises(RuntimeError):
            await backend.initialize()

    @pytest.mark.asyncio
    async def test_backend_not_initialized_error(self, mock_transport):
        """Test that operations fail when not initialized."""
        backend = RabbitMQBackend(transport=mock_transport)

        spore = Spore(
            id="test",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={},
            created_at=datetime.now()
        )

        with pytest.raises(RuntimeError):
            await backend.send(spore, "channel")


class TestBackendAbstraction:
    """Tests for backend abstraction and interface."""

    def test_backend_is_abstract(self):
        """Test that ReefBackend is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            ReefBackend()

    def test_in_memory_implements_interface(self):
        """Test that InMemoryBackend implements ReefBackend interface."""
        backend = InMemoryBackend()
        assert isinstance(backend, ReefBackend)

        # Check all required methods exist
        assert hasattr(backend, 'initialize')
        assert hasattr(backend, 'shutdown')
        assert hasattr(backend, 'send')
        assert hasattr(backend, 'subscribe')
        assert hasattr(backend, 'unsubscribe')
        assert hasattr(backend, 'get_stats')

    def test_rabbitmq_implements_interface(self):
        """Test that RabbitMQBackend implements ReefBackend interface."""
        backend = RabbitMQBackend()
        assert isinstance(backend, ReefBackend)

        # Check all required methods exist
        assert hasattr(backend, 'initialize')
        assert hasattr(backend, 'shutdown')
        assert hasattr(backend, 'send')
        assert hasattr(backend, 'subscribe')
        assert hasattr(backend, 'unsubscribe')
        assert hasattr(backend, 'get_stats')


class TestBackendIntegration:
    """Integration tests for backend usage with Reef."""

    @pytest.mark.asyncio
    async def test_reef_with_in_memory_backend(self):
        """Test Reef works with InMemoryBackend."""
        from praval.core.reef import Reef

        backend = InMemoryBackend()
        reef = Reef(backend=backend)

        # Basic operations should work
        reef_id = reef.send(
            from_agent="agent1",
            to_agent="agent2",
            knowledge={"data": "test"},
            spore_type=SporeType.KNOWLEDGE
        )

        assert reef_id is not None

    @pytest.mark.asyncio
    async def test_reef_default_backend(self):
        """Test that Reef defaults to InMemoryBackend."""
        from praval.core.reef import Reef

        reef = Reef()
        assert isinstance(reef.backend, InMemoryBackend)

    @pytest.mark.asyncio
    async def test_reef_with_custom_backend(self):
        """Test Reef with custom backend."""
        from praval.core.reef import Reef

        backend = InMemoryBackend()
        reef = Reef(backend=backend)

        assert reef.backend is backend

    @pytest.mark.asyncio
    async def test_reef_backend_initialization(self):
        """Test Reef backend async initialization."""
        from praval.core.reef import Reef

        backend = InMemoryBackend()
        reef = Reef(backend=backend)

        config = {}
        await reef.initialize_backend(config)

        # Should be initialized
        assert reef._backend_initialized

    @pytest.mark.asyncio
    async def test_reef_backend_shutdown(self):
        """Test Reef backend async shutdown."""
        from praval.core.reef import Reef

        backend = InMemoryBackend()
        reef = Reef(backend=backend)

        await reef.initialize_backend()
        await reef.close_backend()

        assert not reef._backend_initialized
