"""
Abstract backend interface for Reef communication system.

Allows Reef to work with multiple transport backends:
- InMemory: Local agents (current behavior)
- RabbitMQ: Distributed agents via AMQP
- Future: HTTP, gRPC, Kafka, etc.

Design:
  Agents work unchanged regardless of backend. The Reef delegates all
  channel operations to the backend, which handles transport details.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from collections import defaultdict, deque

from .reef import Spore, SporeType, ReefChannel

logger = logging.getLogger(__name__)


class ReefBackend(ABC):
    """
    Abstract base class for Reef backends.

    A backend implements the actual message routing and delivery logic.
    The Reef class delegates all channel operations to the backend.
    """

    def __init__(self):
        self.connected = False
        self.stats = {
            'spores_sent': 0,
            'spores_received': 0,
            'errors': 0,
        }

    @abstractmethod
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the backend.

        Args:
            config: Backend-specific configuration dictionary

        Raises:
            ConnectionError: If initialization fails
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """
        Shutdown the backend and cleanup resources.
        """
        pass

    @abstractmethod
    async def send(self, spore: Spore, channel: str) -> None:
        """
        Send a spore through the backend.

        Args:
            spore: Spore to send
            channel: Channel/queue name for routing

        Raises:
            PublishError: If send fails
        """
        pass

    @abstractmethod
    async def subscribe(self, channel: str, handler: Callable) -> None:
        """
        Subscribe to a channel with a message handler.

        Args:
            channel: Channel/queue name (may include wildcards for some backends)
            handler: Async function(spore: Spore) called on message receipt

        Raises:
            ConnectionError: If subscription fails
        """
        pass

    @abstractmethod
    async def unsubscribe(self, channel: str) -> None:
        """
        Unsubscribe from a channel.

        Args:
            channel: Channel/queue name
        """
        pass

    def get_stats(self) -> Dict[str, Any]:
        """Get backend statistics."""
        return self.stats.copy()


class InMemoryBackend(ReefBackend):
    """
    In-memory backend for local agent communication.

    All agents in the same process communicate via shared Python data structures.
    This is fast but not suitable for distributed systems.

    Features:
    - Zero-copy message passing
    - Fast delivery (microseconds)
    - Thread-safe with locks
    - Supports wildcards in subscriptions (not standard for in-memory)
    """

    def __init__(self):
        super().__init__()
        self.channels: Dict[str, ReefChannel] = {}
        self._lock = asyncio.Lock()
        self._subscriptions: Dict[str, List[Callable]] = defaultdict(list)

    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize in-memory backend (no-op)."""
        self.connected = True
        logger.info("InMemoryBackend initialized")

    async def shutdown(self) -> None:
        """Cleanup all channels."""
        async with self._lock:
            for channel in self.channels.values():
                channel.shutdown(wait=False)
            self.channels.clear()
            self._subscriptions.clear()
        self.connected = False
        logger.info("InMemoryBackend shutdown")

    async def send(self, spore: Spore, channel: str) -> None:
        """
        Send spore to in-memory channel.

        Immediately delivers to all subscribed handlers in this process.
        """
        if not self.connected:
            raise RuntimeError("InMemoryBackend not connected")

        try:
            async with self._lock:
                # Create channel if it doesn't exist
                if channel not in self.channels:
                    self.channels[channel] = ReefChannel(channel)

                channel_obj = self.channels[channel]

            # Deliver asynchronously (outside lock to prevent deadlock)
            futures = channel_obj._deliver_spore(spore)

            # Wait for handlers to complete
            if futures:
                await asyncio.gather(*[asyncio.create_task(
                    asyncio.to_thread(f.result)
                ) for f in futures], return_exceptions=True)

            self.stats['spores_sent'] += 1

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"InMemoryBackend send error: {e}")
            raise RuntimeError(f"Failed to send spore: {e}")

    async def subscribe(self, channel: str, handler: Callable) -> None:
        """
        Subscribe to in-memory channel.

        Handler will be called immediately when spores arrive.
        """
        if not self.connected:
            raise RuntimeError("InMemoryBackend not connected")

        try:
            async with self._lock:
                # Create channel if it doesn't exist
                if channel not in self.channels:
                    self.channels[channel] = ReefChannel(channel)

                channel_obj = self.channels[channel]

            # Register handler
            # Extract agent name from channel (format: "agent.{agent_name}" or generic)
            agent_name = channel.replace("agent.", "") if channel.startswith("agent.") else "subscriber"

            # Subscribe to the channel
            channel_obj.subscribe(agent_name, handler, replace=False)

            logger.debug(f"InMemoryBackend subscribed to channel: {channel}")

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"InMemoryBackend subscribe error: {e}")
            raise RuntimeError(f"Failed to subscribe: {e}")

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from in-memory channel."""
        try:
            async with self._lock:
                if channel in self.channels:
                    agent_name = channel.replace("agent.", "") if channel.startswith("agent.") else "subscriber"
                    self.channels[channel].unsubscribe(agent_name)

                    logger.debug(f"InMemoryBackend unsubscribed from channel: {channel}")

        except Exception as e:
            logger.error(f"InMemoryBackend unsubscribe error: {e}")


class RabbitMQBackend(ReefBackend):
    """
    RabbitMQ backend for distributed agent communication.

    Agents across multiple processes/machines communicate via RabbitMQ.
    Leverages native Spore AMQP serialization for efficiency.

    Features:
    - Distributed message routing
    - Persistent message delivery
    - Topic-based wildcards (AMQP routing keys)
    - Native Spore wire format
    - Automatic reconnection handling
    """

    def __init__(self, transport=None):
        super().__init__()
        self.transport = transport
        self.subscriptions: Dict[str, List[str]] = {}  # channel -> [routing_keys]

    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize RabbitMQ backend.

        Args:
            config: RabbitMQ connection config
                {
                    'url': 'amqp://user:pass@host:5672/',
                    'exchange_name': 'praval.agents',
                    'verify_tls': True,
                    'ca_cert': '/path/to/ca.crt',
                    'client_cert': '/path/to/client.crt',
                    'client_key': '/path/to/client.key'
                }

        Raises:
            ConnectionError: If RabbitMQ connection fails
        """
        if not self.transport:
            try:
                from .transport import TransportFactory, TransportProtocol
                self.transport = TransportFactory.create_transport(TransportProtocol.AMQP)
            except Exception as e:
                raise RuntimeError(f"Failed to create AMQP transport: {e}")

        try:
            await self.transport.initialize(config or {})
            self.connected = True
            logger.info("RabbitMQBackend initialized")

        except Exception as e:
            self.stats['errors'] += 1
            raise RuntimeError(f"Failed to initialize RabbitMQ backend: {e}")

    async def shutdown(self) -> None:
        """Close RabbitMQ connection and cleanup."""
        try:
            if self.transport:
                await self.transport.close()
            self.connected = False
            logger.info("RabbitMQBackend shutdown")
        except Exception as e:
            logger.error(f"Error during RabbitMQ shutdown: {e}")

    async def send(self, spore: Spore, channel: str) -> None:
        """
        Send spore to RabbitMQ.

        Spore is converted to native AMQP message format and published.
        Routing key is derived from spore metadata and channel.
        """
        if not self.connected:
            raise RuntimeError("RabbitMQ backend not connected")

        try:
            # Generate routing key from spore metadata
            routing_key = self._generate_routing_key(spore, channel)

            # Use native Spore AMQP serialization
            await self.transport.publish(spore, routing_key)

            self.stats['spores_sent'] += 1

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"RabbitMQBackend send error: {e}")
            raise RuntimeError(f"Failed to send spore via RabbitMQ: {e}")

    async def subscribe(self, channel: str, handler: Callable) -> None:
        """
        Subscribe to RabbitMQ channel.

        Messages are received as Spore objects via native AMQP format.
        """
        if not self.connected:
            raise RuntimeError("RabbitMQ backend not connected")

        try:
            # Handler wrapper that filters by channel
            async def spore_handler(spore: Spore):
                # Filter by channel if needed
                if self._spore_matches_channel(spore, channel):
                    await handler(spore)

            # Generate topic with wildcards
            topic = self._generate_topic(channel)

            # Subscribe to topic
            await self.transport.subscribe(topic, spore_handler)

            # Track subscription
            if channel not in self.subscriptions:
                self.subscriptions[channel] = []
            self.subscriptions[channel].append(topic)

            logger.debug(f"RabbitMQBackend subscribed to channel: {channel} (topic: {topic})")

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"RabbitMQBackend subscribe error: {e}")
            raise RuntimeError(f"Failed to subscribe to RabbitMQ: {e}")

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from RabbitMQ channel."""
        try:
            if channel in self.subscriptions:
                for topic in self.subscriptions[channel]:
                    await self.transport.unsubscribe(topic)
                del self.subscriptions[channel]

                logger.debug(f"RabbitMQBackend unsubscribed from channel: {channel}")

        except Exception as e:
            logger.error(f"RabbitMQBackend unsubscribe error: {e}")

    def _generate_routing_key(self, spore: Spore, channel: str) -> str:
        """
        Generate AMQP routing key from spore metadata.

        Routing key pattern:
        - For direct messages: "agent.{to_agent}.{spore_type}"
        - For broadcasts: "broadcast.{spore_type}"
        - Falls back to channel name if spore metadata is absent

        Args:
            spore: Spore being sent
            channel: Channel name

        Returns:
            AMQP routing key suitable for topic-based exchanges
        """
        if spore.to_agent:
            return f"agent.{spore.to_agent}.{spore.spore_type.value}"
        else:
            # Broadcast message
            return f"broadcast.{spore.spore_type.value}"

    def _generate_topic(self, channel: str) -> str:
        """
        Generate AMQP topic for subscription with wildcards.

        Converts channel names to AMQP topic patterns:
        - "agent.{name}" -> "agent.{name}.*"
        - "broadcast" -> "broadcast.*"
        - Other -> "{channel}.*"

        Args:
            channel: Channel name

        Returns:
            AMQP topic pattern with wildcards
        """
        if channel.startswith("agent."):
            return f"{channel}.*"
        elif channel == "broadcast":
            return "broadcast.*"
        else:
            return f"{channel}.*"

    def _spore_matches_channel(self, spore: Spore, channel: str) -> bool:
        """
        Check if spore matches subscription channel.

        Determines if a received spore should be delivered to a handler
        subscribed to a particular channel.

        Args:
            spore: Received spore
            channel: Channel name we're checking

        Returns:
            True if spore should be delivered to this channel's handlers
        """
        if channel.startswith("agent."):
            # Direct message channel - only deliver if targeted to this agent
            agent_name = channel.replace("agent.", "")
            return spore.to_agent == agent_name
        elif channel == "broadcast":
            # Broadcast channel - deliver if it's actually a broadcast
            return spore.to_agent is None
        else:
            # Generic channel - deliver all messages
            return True
