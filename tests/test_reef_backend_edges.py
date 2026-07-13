"""Error and routing contracts for Reef communication backends."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from praval.core.reef import Spore, SporeType
from praval.core.reef_backend import InMemoryBackend, RabbitMQBackend


def _spore(to_agent=None):
    return Spore(
        id="edge-spore",
        spore_type=SporeType.REQUEST,
        from_agent="sender",
        to_agent=to_agent,
        knowledge={"value": 1},
        created_at=datetime.now(),
    )


@pytest.mark.asyncio
async def test_inmemory_backend_rejects_disconnected_operations():
    backend = InMemoryBackend()
    with pytest.raises(RuntimeError, match="not connected"):
        await backend.send(_spore(), "channel")
    with pytest.raises(RuntimeError, match="not connected"):
        await backend.subscribe("channel", Mock())


@pytest.mark.asyncio
async def test_inmemory_backend_counts_send_and_subscribe_errors():
    backend = InMemoryBackend()
    await backend.initialize()
    broken_channel = Mock()
    broken_channel._deliver_spore.side_effect = RuntimeError("delivery failed")
    backend.channels["broken"] = broken_channel
    with pytest.raises(RuntimeError, match="Failed to send spore"):
        await backend.send(_spore("target"), "broken")
    assert backend.stats["errors"] == 1

    broken_channel.subscribe.side_effect = RuntimeError("subscribe failed")
    with pytest.raises(RuntimeError, match="Failed to subscribe"):
        await backend.subscribe("broken", Mock())
    assert backend.stats["errors"] == 2


@pytest.mark.asyncio
async def test_inmemory_unsubscribe_swallows_channel_errors():
    backend = InMemoryBackend()
    await backend.initialize()
    channel = Mock()
    channel.unsubscribe.side_effect = RuntimeError("unsubscribe failed")
    backend.channels["agent.worker"] = channel
    await backend.unsubscribe("agent.worker")
    channel.unsubscribe.assert_called_once_with("worker")


@pytest.mark.asyncio
async def test_rabbitmq_initialize_send_shutdown_and_subscribe_errors():
    transport = Mock()
    transport.initialize = AsyncMock(side_effect=RuntimeError("init failed"))
    backend = RabbitMQBackend(transport=transport)
    with pytest.raises(RuntimeError, match="Failed to initialize"):
        await backend.initialize()
    assert backend.stats["errors"] == 1

    with pytest.raises(RuntimeError, match="not connected"):
        await backend.send(_spore(), "channel")
    with pytest.raises(RuntimeError, match="not connected"):
        await backend.subscribe("channel", Mock())

    backend.connected = True
    transport.publish = AsyncMock(side_effect=RuntimeError("publish failed"))
    with pytest.raises(RuntimeError, match="Failed to send"):
        await backend.send(_spore(), "channel")
    transport.subscribe = AsyncMock(side_effect=RuntimeError("subscribe failed"))
    with pytest.raises(RuntimeError, match="Failed to subscribe"):
        await backend.subscribe("channel", AsyncMock())

    transport.close = AsyncMock(side_effect=RuntimeError("close failed"))
    await backend.shutdown()


@pytest.mark.asyncio
async def test_rabbitmq_unsubscribe_swallows_transport_error():
    transport = Mock()
    transport.unsubscribe = AsyncMock(side_effect=RuntimeError("failed"))
    backend = RabbitMQBackend(transport=transport)
    backend.subscriptions["channel"] = ["channel.*"]
    await backend.unsubscribe("channel")
    assert "channel" in backend.subscriptions


def test_rabbitmq_topic_and_channel_matching_variants():
    backend = RabbitMQBackend(transport=Mock())
    assert backend._generate_topic("agent.worker") == "agent.worker.*"
    assert backend._generate_topic("broadcast") == "broadcast.*"
    assert backend._generate_topic("custom") == "custom.*"
    assert backend._spore_matches_channel(_spore("worker"), "agent.worker") is True
    assert backend._spore_matches_channel(_spore("other"), "agent.worker") is False
    assert backend._spore_matches_channel(_spore(), "broadcast") is True
    assert backend._spore_matches_channel(_spore("worker"), "broadcast") is False
    assert backend._spore_matches_channel(_spore(), "custom") is True


@pytest.mark.asyncio
async def test_rabbitmq_creates_default_transport_error_is_actionable():
    backend = RabbitMQBackend()
    with patch(
        "praval.core.transport.TransportFactory.create_transport",
        side_effect=RuntimeError("factory failed"),
    ):
        with pytest.raises(RuntimeError, match="Failed to create AMQP transport"):
            await backend.initialize()
