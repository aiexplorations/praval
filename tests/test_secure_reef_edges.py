"""Public failure and compatibility behavior for the secure Reef layer."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

import praval.core.secure_reef as secure_reef_module
from praval.core.reef import SporeType
from praval.core.secure_reef import SecureReef, SecureReefAdapter
from praval.core.transport import TransportProtocol


def _reef(protocol=TransportProtocol.AMQP):
    transport = SimpleNamespace(
        initialize=AsyncMock(),
        subscribe=AsyncMock(),
        publish=AsyncMock(),
        close=AsyncMock(),
    )
    with patch(
        "praval.core.secure_reef.TransportFactory.create_transport",
        return_value=transport,
    ):
        reef = SecureReef(protocol=protocol)
    return reef, transport


@pytest.mark.asyncio
async def test_secure_reef_initialization_wraps_transport_error():
    reef, transport = _reef()
    transport.initialize.side_effect = RuntimeError("broker unavailable")
    with patch("praval.core.secure_reef.SporeKeyManager") as manager_class:
        manager_class.return_value.get_public_keys.return_value = {"key": b"value"}
        with pytest.raises(ConnectionError, match="broker unavailable"):
            await reef.initialize("agent-a")


@pytest.mark.asyncio
async def test_secure_reef_stomp_subscriptions_and_unsupported_topic():
    reef, transport = _reef(TransportProtocol.STOMP)
    reef.agent_name = "agent-a"
    await reef._setup_subscriptions()
    assert [call.args[0] for call in transport.subscribe.await_args_list] == [
        "agent.agent-a",
        "broadcast",
    ]

    reef.protocol = "unsupported"
    with pytest.raises(ValueError, match="Unsupported protocol"):
        reef._generate_topic("agent-b", "knowledge")


@pytest.mark.asyncio
async def test_secure_reef_decrypts_plaintext_and_requires_sender_keys():
    reef, _ = _reef()
    plaintext = SimpleNamespace(
        nonce=b"",
        knowledge_signature=b"",
        encrypted_knowledge=json.dumps({"safe": True}).encode(),
        from_agent="agent-b",
    )
    assert await reef._decrypt_spore(plaintext) == {"safe": True}

    encrypted = SimpleNamespace(
        nonce=b"nonce",
        knowledge_signature=b"signature",
        encrypted_knowledge=b"ciphertext",
        from_agent="missing",
    )
    with pytest.raises(ValueError, match="No public keys"):
        await reef._decrypt_spore(encrypted)

    reef.key_manager = Mock()
    await reef.key_registry.register_agent(
        "agent-b", {"public_key": b"public", "verify_key": b"verify"}
    )
    encrypted.from_agent = "agent-b"
    reef.key_manager.decrypt_and_verify.return_value = {"decoded": True}
    assert await reef._decrypt_spore(encrypted) == {"decoded": True}


@pytest.mark.asyncio
async def test_secure_reef_notifies_sync_and_async_handlers_independently():
    reef, _ = _reef()
    spore = SimpleNamespace(
        id="spore-1",
        from_agent="source",
        knowledge={"value": 1},
        spore_type=SporeType.KNOWLEDGE,
    )
    sync_handler = Mock()
    failing_handler = Mock(side_effect=RuntimeError("handler failed"))
    async_handler = AsyncMock()
    reef.register_handler(SporeType.KNOWLEDGE, sync_handler)
    reef.register_handler(SporeType.KNOWLEDGE, failing_handler)
    reef.register_handler(SporeType.KNOWLEDGE, async_handler)

    await reef._notify_handlers(spore)
    sync_handler.assert_called_once_with(spore)
    failing_handler.assert_called_once_with(spore)
    async_handler.assert_awaited_once_with(spore)

    reef.unregister_handler(SporeType.KNOWLEDGE, Mock())
    reef.unregister_handler(SporeType.REQUEST, Mock())


def test_secure_reef_key_operations_require_initialization():
    reef, _ = _reef()
    with pytest.raises(ValueError, match="not initialized"):
        import asyncio

        asyncio.run(reef.rotate_keys())
    with pytest.raises(ValueError, match="not initialized"):
        reef.export_keys()


@pytest.mark.asyncio
async def test_secure_reef_global_helpers_create_initialize_and_reuse():
    secure_reef_module._global_secure_reef = None
    fake = Mock()
    fake.initialize = AsyncMock()
    with patch("praval.core.secure_reef.SecureReef", return_value=fake) as reef_class:
        first = await secure_reef_module.get_secure_reef(
            TransportProtocol.MQTT, {"host": "test"}
        )
        second = await secure_reef_module.get_secure_reef()
        initialized = await secure_reef_module.initialize_secure_reef("agent-a")

    assert first is second is initialized is fake
    reef_class.assert_called_once_with(TransportProtocol.MQTT, {"host": "test"})
    fake.initialize.assert_awaited_once_with("agent-a")
    secure_reef_module._global_secure_reef = None


def test_secure_reef_adapter_runs_legacy_send_and_broadcast():
    class FakeSecureReef:
        async def send(self, from_agent, to_agent, knowledge, **kwargs):
            return f"sent:{from_agent}:{to_agent}:{knowledge['value']}"

        async def broadcast(self, knowledge, **kwargs):
            return f"broadcast:{knowledge['value']}"

    adapter = SecureReefAdapter(FakeSecureReef())
    assert adapter.send("a", "b", {"value": 1}) == "sent:a:b:1"
    assert adapter.broadcast("a", {"value": 2}) == "broadcast:2"
    assert adapter.subscribe("a", Mock()) is None
