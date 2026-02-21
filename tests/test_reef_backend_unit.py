import pytest

from praval.core.reef import Spore, SporeType
from praval.core.reef_backend import InMemoryBackend, RabbitMQBackend


@pytest.mark.asyncio
async def test_inmemory_backend_send_subscribe_roundtrip():
    backend = InMemoryBackend()
    await backend.initialize()
    received = []

    async def handler(spore):
        received.append(spore)

    await backend.subscribe("channel.test", handler)

    spore = Spore(
        id="s1",
        spore_type=SporeType.KNOWLEDGE,
        from_agent="a",
        to_agent=None,
        knowledge={"msg": "hi"},
        created_at=__import__("datetime").datetime.now(),
    )

    await backend.send(spore, "channel.test")

    assert received and received[0].knowledge["msg"] == "hi"

    await backend.unsubscribe("channel.test")
    await backend.shutdown()


class FakeTransport:
    def __init__(self):
        self.published = []
        self.subscriptions = []
        self.queue_subscriptions = []
        self.closed = False

    async def initialize(self, config=None):
        return None

    async def publish(self, routing_key, message):
        self.published.append((routing_key, message))

    async def subscribe(self, topic, handler):
        self.subscriptions.append(topic)

    async def subscribe_to_queue(self, queue_name, handler):
        self.queue_subscriptions.append(queue_name)

    async def unsubscribe(self, topic):
        return None

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_rabbitmq_backend_routing_key_generation():
    backend = RabbitMQBackend(transport=FakeTransport())
    await backend.initialize({})

    spore_direct = Spore(
        id="s2",
        spore_type=SporeType.REQUEST,
        from_agent="a",
        to_agent="b",
        knowledge={"q": "x"},
        created_at=__import__("datetime").datetime.now(),
    )
    spore_broadcast = Spore(
        id="s3",
        spore_type=SporeType.BROADCAST,
        from_agent="a",
        to_agent=None,
        knowledge={"q": "x"},
        created_at=__import__("datetime").datetime.now(),
    )

    assert backend._generate_routing_key(spore_direct, "chan") == "agent.b.request"
    assert (
        backend._generate_routing_key(spore_broadcast, "chan") == "broadcast.broadcast"
    )


@pytest.mark.asyncio
async def test_rabbitmq_backend_subscribe_modes():
    transport = FakeTransport()
    backend = RabbitMQBackend(
        transport=transport, channel_queue_map={"chan": "queue_a"}
    )
    await backend.initialize({})

    async def handler(spore):
        return None

    await backend.subscribe("chan", handler)
    assert "queue_a" in transport.queue_subscriptions

    # Topic-based when no mapping
    backend2 = RabbitMQBackend(transport=FakeTransport())
    await backend2.initialize({})
    await backend2.subscribe("topic_chan", handler)
    assert backend2.transport.subscriptions
