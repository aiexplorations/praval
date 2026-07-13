"""Additional validation, lifecycle, and distributed-routing Reef contracts."""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from praval.core.reef import (
    MAX_SPORE_SIZE_BYTES,
    ReefChannel,
    ReefCore,
    Spore,
    SporeType,
    SporeValidationError,
    _contains_binary,
    _estimate_payload_size_bytes,
)
from praval.models import ContentPart


def _spore(**overrides):
    values = {
        "id": "spore-1",
        "spore_type": SporeType.KNOWLEDGE,
        "from_agent": "sender",
        "to_agent": "receiver",
        "knowledge": {"value": 1},
        "created_at": datetime.now(),
    }
    values.update(overrides)
    return Spore(**values)


def test_spore_validation_and_reference_edge_paths(monkeypatch):
    assert _estimate_payload_size_bytes({"bad": object()}) > MAX_SPORE_SIZE_BYTES
    assert _contains_binary([{"data": bytearray(b"x")}]) is True

    with pytest.raises(SporeValidationError, match="instances or mappings"):
        _spore(content_parts=[object()])
    with pytest.raises(SporeValidationError, match="invalid content_parts"):
        _spore(content_parts=[{"type": "text", "metadata": []}])
    unsafe_part = ContentPart.model_construct(type="file", data=b"binary")
    with pytest.warns(UserWarning):
        with pytest.raises(SporeValidationError, match="raw binary"):
            _spore(content_parts=[unsafe_part])

    spore = _spore()
    spore.data_references = "bad"
    with pytest.raises(SporeValidationError, match="data_references"):
        spore.validate()
    spore.data_references = []
    spore.knowledge_references = [1]
    with pytest.raises(SporeValidationError, match="knowledge_references"):
        spore.validate()

    spore = _spore(knowledge_references=["known"], data_references=["data://one"])
    assert spore.add_knowledge_reference("known") is spore
    assert spore.add_data_reference("data://one") is spore
    assert spore.has_any_references() is True

    spore.knowledge = {"bad": object()}
    assert spore.get_payload_size() == 0
    spore.knowledge = {"value": 1}
    monkeypatch.setattr(
        "praval.core.reef._estimate_payload_size_bytes",
        Mock(side_effect=RuntimeError("size failed")),
    )
    assert spore.get_spore_size_estimate() == len(spore.to_json())


def test_reef_channel_delivery_polling_expiry_and_capacity():
    channel = ReefChannel("edge", max_capacity=1, batch_size=2)
    received = []

    def first(spore):
        received.append(("first", spore.id))

    async def second(spore):
        await asyncio.sleep(0)
        received.append(("second", spore.id))

    channel.subscribe("receiver", first)
    channel.subscribe("receiver", second, replace=False)
    channel.send_spore(_spore(id="one"))
    assert channel.wait_for_completion(timeout=2)
    assert {name for name, _ in received} == {"first", "second"}

    channel.send_spore(_spore(id="two"))
    assert channel.wait_for_completion(timeout=2)
    assert [spore.id for spore in channel.get_spores_for_agent("receiver")] == ["two"]

    expired = _spore(id="expired", expires_at=datetime.now() - timedelta(seconds=1))
    assert channel._deliver_spore(expired) == []
    channel.spores.append(expired)
    assert channel.cleanup_expired() == 1
    assert channel.shutdown(wait=False) is True
    assert channel._deliver_spore(_spore(id="after-shutdown")) == []


@pytest.mark.asyncio
async def test_distributed_backend_initialization_routing_and_cleanup():
    backend = SimpleNamespace(
        initialize=AsyncMock(),
        shutdown=AsyncMock(),
        send=AsyncMock(),
        subscribe=AsyncMock(),
        get_stats=Mock(return_value={"sent": 1}),
    )
    reef = ReefCore(backend=backend, use_shared_pool=False)
    try:
        await reef.initialize_backend({"url": "memory://"})
        await reef.initialize_backend({"ignored": True})
        reef.send("sender", "receiver", {"payload": "x"})
        reef.subscribe("receiver", Mock())
        await asyncio.sleep(0)

        backend.initialize.assert_awaited_once_with({"url": "memory://"})
        backend.send.assert_awaited_once()
        backend.subscribe.assert_awaited_once()
        assert reef.get_network_stats()["backend_stats"] == {"sent": 1}

        await reef.close_backend()
        await reef.close_backend()
        backend.shutdown.assert_awaited_once()
    finally:
        reef.shutdown(wait=False)


def test_reef_authorization_rate_limit_references_and_wait_failures():
    denied = ReefCore(auth_provider=lambda action, context: False)
    try:
        with pytest.raises(PermissionError, match="Unauthorized"):
            denied.send("sender", "receiver", {"value": 1})
        denied.auth_provider = lambda action, context: (_ for _ in ()).throw(
            RuntimeError("auth unavailable")
        )
        with pytest.raises(PermissionError, match="Authorization error"):
            denied.subscribe("receiver", Mock())
    finally:
        denied.shutdown(wait=False)

    reef = ReefCore(use_shared_pool=False)
    try:
        with pytest.raises(ValueError, match="not found"):
            reef.send("sender", "receiver", {}, channel="missing")

        reef.broadcast_rate_limit_per_sec = 1
        reef.broadcast("sender", {"value": 1})
        with pytest.raises(RuntimeError, match="rate limit"):
            reef.broadcast("sender", {"value": 2})

        referenced_id = reef.create_knowledge_reference_spore(
            "sender", "receiver", "summary", ["ok", "missing", "broken"]
        )
        sent = reef.get_channel("main").get_spores_for_agent("receiver")[0]
        assert sent.id == referenced_id

        def recall(reference):
            if reference == "broken":
                raise RuntimeError("memory unavailable")
            if reference == "ok":
                return [SimpleNamespace(content="content", metadata={"id": reference})]
            return []

        memory = SimpleNamespace(recall_by_id=recall)
        resolved = reef.resolve_knowledge_references(sent, memory)
        assert resolved["referenced_knowledge"][0]["reference_id"] == "ok"
        assert reef.resolve_knowledge_references(_spore(), memory) == {"value": 1}

        failing_channel = Mock()
        failing_channel.wait_for_completion.return_value = False
        reef.channels["failing"] = failing_channel
        assert reef.wait_for_completion(timeout=1) is False
        del reef.channels["failing"]
    finally:
        reef.shutdown(wait=False)
