"""Lifecycle edge cases for AgentRunner."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from praval.core.agent_runner import AgentRunner, run_agents


@pytest.fixture
def decorated_agent():
    func = Mock()
    func.__name__ = "worker"
    func._praval_name = "worker"
    func._praval_channel = "agent.worker"
    func._praval_agent = Mock()
    return func


@pytest.mark.asyncio
async def test_agent_runner_initialize_propagates_backend_failure(decorated_agent):
    reef = Mock()
    reef.backend = Mock()
    reef.initialize_backend = AsyncMock(side_effect=RuntimeError("backend failed"))
    runner = AgentRunner(agents=[decorated_agent], backend=reef.backend)
    with patch("praval.core.agent_runner.get_reef", return_value=reef):
        with pytest.raises(RuntimeError, match="backend failed"):
            await runner.initialize()


@pytest.mark.asyncio
async def test_agent_runner_rejects_duplicate_run_and_resets_after_error(
    decorated_agent,
):
    runner = AgentRunner(agents=[decorated_agent], backend=Mock())
    runner._running = True
    with pytest.raises(RuntimeError, match="already running"):
        await runner.run_async()

    runner._running = False
    runner.initialize = AsyncMock(side_effect=RuntimeError("startup failed"))
    runner.shutdown = AsyncMock(side_effect=lambda: setattr(runner, "_running", False))
    with pytest.raises(RuntimeError, match="startup failed"):
        await runner.run_async()
    runner.shutdown.assert_awaited_once()


def test_agent_runner_run_creates_and_closes_loop(decorated_agent):
    loop = Mock()
    loop.run_until_complete.side_effect = lambda coroutine: coroutine.close()
    runner = AgentRunner(agents=[decorated_agent], backend=Mock())
    with (
        patch("asyncio.new_event_loop", return_value=loop),
        patch("asyncio.set_event_loop"),
        patch("signal.signal") as signal_mock,
    ):
        runner.run()
    loop.run_until_complete.assert_called_once()
    loop.close.assert_called_once()
    assert runner.loop is None
    assert signal_mock.call_count == 2


@pytest.mark.asyncio
async def test_agent_runner_shutdown_swallows_reef_errors(decorated_agent):
    runner = AgentRunner(agents=[decorated_agent], backend=Mock())
    reef = Mock()
    reef.close_backend = AsyncMock(side_effect=RuntimeError("close failed"))
    runner.reef = reef
    runner._running = True
    await runner.shutdown()
    assert runner._running is False


def test_agent_runner_stats_include_initialized_reef(decorated_agent):
    runner = AgentRunner(agents=[decorated_agent], backend=Mock())
    runner.reef = Mock()
    runner.reef.get_network_stats.return_value = {
        "backend": "rabbitmq",
        "total_channels": 3,
        "backend_stats": {"spores_sent": 2},
    }
    runner._running = True
    assert runner.get_stats() == {
        "status": "running",
        "agents": 1,
        "running": True,
        "backend": "rabbitmq",
        "channels": 3,
        "backend_stats": {"spores_sent": 2},
    }


def test_run_agents_constructs_and_runs_runner(decorated_agent):
    with patch("praval.core.agent_runner.AgentRunner") as runner_class:
        run_agents(
            decorated_agent,
            backend_config={"url": "amqp://test"},
            channel_queue_map={"channel": "queue"},
        )
    runner_class.assert_called_once_with(
        agents=[decorated_agent],
        backend_config={"url": "amqp://test"},
        backend=None,
        channel_queue_map={"channel": "queue"},
    )
    runner_class.return_value.run.assert_called_once()
