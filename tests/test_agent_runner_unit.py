from types import SimpleNamespace
from unittest.mock import patch

import pytest

from praval.core.agent_runner import AgentRunner
from praval.core.reef import get_reef


class FakeBackend:
    def __init__(self):
        self.initialized = False
        self.subscriptions = []
        self.closed = False

    async def initialize(self, config=None):
        self.initialized = True

    async def shutdown(self):
        self.closed = True

    async def subscribe(self, channel, handler):
        self.subscriptions.append(channel)

    async def send(self, spore, channel):
        return None

    async def unsubscribe(self, channel):
        return None


@pytest.fixture
def dummy_agent():
    def handler(spore):
        return {"ok": True}

    underlying = SimpleNamespace()
    underlying.subscribed = []
    underlying._startup_channel = None

    def subscribe_to_channel(channel):
        underlying.subscribed.append(channel)

    underlying.subscribe_to_channel = subscribe_to_channel
    underlying.on_spore_received = lambda spore: None

    handler._praval_agent = underlying
    handler._praval_name = "dummy"
    handler._praval_channel = "agent.dummy"
    return handler


def test_agent_runner_validates_agents():
    with pytest.raises(ValueError):
        AgentRunner(agents=[lambda spore: None])


def test_agent_runner_defers_shutdown_event_until_async_use(dummy_agent):
    backend = FakeBackend()
    with patch(
        "praval.core.agent_runner.asyncio.Event",
        side_effect=AssertionError("event created eagerly"),
    ):
        runner = AgentRunner(agents=[dummy_agent], backend=backend)

    assert runner._shutdown_event is None


@pytest.mark.asyncio
async def test_agent_runner_initialize_distributed(dummy_agent):
    backend = FakeBackend()
    runner = AgentRunner(
        agents=[dummy_agent], backend=backend, backend_config={"url": "amqp://"}
    )

    await runner.initialize()

    reef = get_reef()
    assert backend.initialized is True
    # Distributed routing needs direct and broadcast topics. Logical channels stay
    # subscribed for queue mappings and backward compatibility.
    assert "agent.dummy" in backend.subscriptions
    assert "broadcast" in backend.subscriptions
    assert dummy_agent._praval_channel in backend.subscriptions
    assert reef.default_channel in backend.subscriptions
    assert "distributed_agents" in backend.subscriptions
    assert "distributed_agents" in dummy_agent._praval_agent.subscribed


@pytest.mark.asyncio
async def test_agent_runner_run_async_exits_when_shutdown_set(dummy_agent):
    backend = FakeBackend()
    runner = AgentRunner(
        agents=[dummy_agent], backend=backend, backend_config={"url": "amqp://"}
    )
    runner._get_shutdown_event().set()
    await runner.run_async()
    assert runner._running is False


def test_agent_runner_get_stats_not_initialized(dummy_agent):
    runner = AgentRunner(agents=[dummy_agent])
    stats = runner.get_stats()
    assert stats["status"] == "not_initialized"
    assert stats["agents"] == 1
