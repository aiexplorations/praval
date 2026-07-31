"""Failure and cleanup paths for concrete message transports."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from praval.core.transport import (
    AMQPTransport,
    ConnectionError,
    MQTTTransport,
    PublishError,
    STOMPTransport,
)


@pytest.mark.asyncio
async def test_amqp_publish_subscribe_and_close_failure_paths():
    transport = AMQPTransport()
    with pytest.raises(PublishError, match="not connected"):
        await transport.publish("topic", b"message")
    with pytest.raises(ConnectionError, match="not connected"):
        await transport.subscribe("topic", AsyncMock())

    transport.connected = True
    transport.exchange = object()
    with pytest.raises(PublishError, match="dependency not initialized"):
        await transport.publish("topic", b"message")

    transport._aio_pika = SimpleNamespace(
        Message=Mock(return_value=object()),
        DeliveryMode=SimpleNamespace(PERSISTENT="persistent"),
    )
    await transport.publish("topic", b"message")

    transport.exchange = SimpleNamespace(
        publish=AsyncMock(side_effect=RuntimeError("publish failed"))
    )
    with pytest.raises(PublishError, match="publish failed"):
        await transport.publish("topic", b"message")

    transport.connection = SimpleNamespace(
        is_closed=False,
        close=AsyncMock(side_effect=RuntimeError("close failed")),
    )
    await transport.close()


@pytest.mark.asyncio
async def test_amqp_initialize_and_subscribe_wrap_dependency_errors(monkeypatch):
    async def fail_connect(**kwargs):
        raise RuntimeError("broker unavailable")

    fake_module = SimpleNamespace(
        connect_robust=fail_connect,
        ExchangeType=SimpleNamespace(TOPIC="topic"),
    )
    monkeypatch.setitem(__import__("sys").modules, "aio_pika", fake_module)
    with pytest.raises(ConnectionError, match="broker unavailable"):
        await AMQPTransport().initialize({})

    channel = SimpleNamespace(
        declare_queue=AsyncMock(side_effect=RuntimeError("queue failed"))
    )
    transport = AMQPTransport()
    transport.connected = True
    transport.channel = channel
    with pytest.raises(ConnectionError, match="queue failed"):
        await transport.subscribe("topic", AsyncMock())


@pytest.mark.asyncio
async def test_amqp_precise_consumer_cleanup_respects_queue_ownership():
    temporary_queue = SimpleNamespace(
        bind=AsyncMock(),
        consume=AsyncMock(return_value="temporary-consumer"),
        cancel=AsyncMock(),
        delete=AsyncMock(),
    )
    configured_queue = SimpleNamespace(
        consume=AsyncMock(return_value="configured-consumer"),
        cancel=AsyncMock(),
        delete=AsyncMock(),
    )
    channel = SimpleNamespace(
        declare_queue=AsyncMock(return_value=temporary_queue),
        get_queue=AsyncMock(return_value=configured_queue),
    )
    transport = AMQPTransport()
    transport.connected = True
    transport.channel = channel
    transport.exchange = object()

    temporary = await transport.subscribe("agent.client.*", AsyncMock())
    configured = await transport.subscribe_to_queue("configured.client", AsyncMock())

    await transport.unsubscribe_handler(temporary)
    await transport.unsubscribe_handler(configured)

    temporary_queue.cancel.assert_awaited_once_with("temporary-consumer")
    temporary_queue.delete.assert_awaited_once_with(if_unused=False, if_empty=False)
    configured_queue.cancel.assert_awaited_once_with("configured-consumer")
    configured_queue.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_amqp_shutdown_cancels_remaining_consumers():
    queue = SimpleNamespace(
        bind=AsyncMock(),
        consume=AsyncMock(return_value="consumer-1"),
        cancel=AsyncMock(),
        delete=AsyncMock(),
    )
    connection = SimpleNamespace(is_closed=False, close=AsyncMock())
    transport = AMQPTransport()
    transport.connected = True
    transport.channel = SimpleNamespace(declare_queue=AsyncMock(return_value=queue))
    transport.exchange = object()
    transport.connection = connection

    await transport.subscribe("agent.client.*", AsyncMock())
    await transport.close()

    queue.cancel.assert_awaited_once_with("consumer-1")
    queue.delete.assert_awaited_once()
    connection.close.assert_awaited_once()
    assert transport._subscription_handles == {}


@pytest.mark.asyncio
async def test_mqtt_failure_and_cleanup_paths():
    transport = MQTTTransport()
    with pytest.raises(PublishError, match="not connected"):
        await transport.publish("topic", b"message")
    with pytest.raises(ConnectionError, match="not connected"):
        await transport.subscribe("topic", AsyncMock())
    await transport.unsubscribe("topic")

    client = SimpleNamespace(
        publish=AsyncMock(side_effect=RuntimeError("publish failed")),
        subscribe=AsyncMock(side_effect=RuntimeError("subscribe failed")),
        unsubscribe=AsyncMock(side_effect=RuntimeError("unsubscribe failed")),
        __aexit__=AsyncMock(side_effect=RuntimeError("close failed")),
    )
    transport.connected = True
    transport.client = client
    with pytest.raises(PublishError, match="publish failed"):
        await transport.publish("topic", b"message")
    with pytest.raises(ConnectionError, match="subscribe failed"):
        await transport.subscribe("topic", AsyncMock())
    await transport.unsubscribe("topic")
    await transport.close()


@pytest.mark.asyncio
async def test_mqtt_listener_contains_callback_and_stream_errors():
    async def messages():
        yield SimpleNamespace(topic=SimpleNamespace(value="topic"), payload=b"message")
        raise RuntimeError("stream failed")

    callback = AsyncMock(side_effect=RuntimeError("callback failed"))
    transport = MQTTTransport()
    transport.client = SimpleNamespace(messages=messages())
    transport.subscriptions["topic"] = callback

    await transport._message_listener()
    callback.assert_awaited_once_with(b"message")


@pytest.mark.asyncio
async def test_stomp_failure_and_cleanup_paths():
    transport = STOMPTransport()
    with pytest.raises(PublishError, match="not connected"):
        await transport.publish("topic", b"message")
    with pytest.raises(ConnectionError, match="not connected"):
        await transport.subscribe("topic", AsyncMock())
    await transport.unsubscribe("topic")

    connection = SimpleNamespace(
        send=AsyncMock(side_effect=RuntimeError("send failed")),
        subscribe=AsyncMock(side_effect=RuntimeError("subscribe failed")),
        unsubscribe=AsyncMock(side_effect=RuntimeError("unsubscribe failed")),
        disconnect=AsyncMock(side_effect=RuntimeError("disconnect failed")),
    )
    transport.connected = True
    transport.connection = connection
    with pytest.raises(PublishError, match="send failed"):
        await transport.publish("topic", b"message", ttl=1)
    with pytest.raises(ConnectionError, match="subscribe failed"):
        await transport.subscribe("topic", AsyncMock())
    await transport.unsubscribe("topic")
    await transport.close()


def test_tls_context_loads_ca_and_client_certificates():
    context = Mock()
    with patch("ssl.create_default_context", return_value=context):
        AMQPTransport()._create_tls_context(
            {
                "ca_cert": "ca.pem",
                "client_cert": "client.pem",
                "client_key": "client.key",
            }
        )

    context.load_verify_locations.assert_called_once_with("ca.pem")
    context.load_cert_chain.assert_called_once_with("client.pem", keyfile="client.key")
