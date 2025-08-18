"""
Transport Abstraction Layer for Secure Spore Communication.

This module provides protocol-agnostic message transport supporting:
- AMQP (RabbitMQ, ActiveMQ, etc.) with TLS
- MQTT with TLS/SSL
- STOMP with TLS
- Extensible for Redis, NATS, and other protocols

All transports enforce TLS/SSL by default for security.
"""

import asyncio
import ssl
import time
import uuid
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, Callable, Union
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class TransportProtocol(Enum):
    """Supported message queue protocols."""
    AMQP = "amqp"
    MQTT = "mqtt"
    STOMP = "stomp"
    REDIS = "redis"  # Future
    NATS = "nats"    # Future


class TransportError(Exception):
    """Base exception for transport-related errors."""
    pass


class ConnectionError(TransportError):
    """Raised when transport connection fails."""
    pass


class PublishError(TransportError):
    """Raised when message publishing fails."""
    pass


class MessageTransport(ABC):
    """Abstract base class for message queue transports."""
    
    def __init__(self):
        self.connected = False
        self.config = {}
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the transport connection with TLS."""
        pass
    
    @abstractmethod
    async def publish(self, topic: str, message: bytes, 
                     priority: int = 5, ttl: Optional[int] = None) -> None:
        """Publish a message to a topic/queue."""
        pass
    
    @abstractmethod
    async def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to a topic/queue with callback."""
        pass
    
    @abstractmethod
    async def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic/queue."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the transport connection."""
        pass
    
    def _create_tls_context(self, config: Dict[str, Any]) -> ssl.SSLContext:
        """Create SSL/TLS context with certificates."""
        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        
        # Configure certificate verification
        if config.get('verify_certs', True):
            ssl_context.check_hostname = config.get('check_hostname', True)
            if ca_cert := config.get('ca_cert'):
                ssl_context.load_verify_locations(ca_cert)
        else:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        
        # Load client certificates for mutual TLS
        if client_cert := config.get('client_cert'):
            ssl_context.load_cert_chain(
                client_cert,
                keyfile=config.get('client_key')
            )
        
        return ssl_context


class AMQPTransport(MessageTransport):
    """
    AMQP transport implementation supporting RabbitMQ, ActiveMQ, etc.
    
    Features:
    - TLS/SSL by default
    - Automatic reconnection
    - Message persistence
    - Topic-based routing
    """
    
    def __init__(self):
        super().__init__()
        self.connection = None
        self.channel = None
        self.exchange = None
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize AMQP connection with TLS."""
        try:
            import aio_pika
        except ImportError:
            raise TransportError("aio-pika package required for AMQP transport")
        
        self.config = config
        
        # Default AMQP configuration
        connection_params = {
            'url': config.get('url', 'amqps://localhost:5671/'),
            'ssl': True,
        }
        
        # Add SSL configuration if certificates provided
        if any(key in config for key in ['ca_cert', 'client_cert', 'client_key']):
            ssl_context = self._create_tls_context(config)
            connection_params['ssl_context'] = ssl_context
        
        try:
            self.connection = await aio_pika.connect_robust(
                **connection_params,
                heartbeat=600,  # 10 minutes
                client_properties={"connection_name": f"praval-{uuid.uuid4().hex[:8]}"}
            )
            
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=config.get('prefetch_count', 100))
            
            # Declare exchange
            self.exchange = await self.channel.declare_exchange(
                config.get('exchange_name', 'praval.spores'),
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            
            self.connected = True
            logger.info(f"AMQP transport initialized: {connection_params['url']}")
            
        except Exception as e:
            raise ConnectionError(f"Failed to initialize AMQP transport: {e}")
    
    async def publish(self, topic: str, message: bytes, 
                     priority: int = 5, ttl: Optional[int] = None) -> None:
        """Publish message to AMQP exchange."""
        if not self.connected or not self.exchange:
            raise PublishError("AMQP transport not connected")
        
        try:
            amqp_message = aio_pika.Message(
                message,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                priority=min(max(priority, 0), 255),  # AMQP priority range
                expiration=ttl * 1000 if ttl else None,  # TTL in milliseconds
                message_id=str(uuid.uuid4()),
                timestamp=time.time()
            )
            
            await self.exchange.publish(amqp_message, routing_key=topic)
            logger.debug(f"Published AMQP message to topic: {topic}")
            
        except Exception as e:
            raise PublishError(f"Failed to publish AMQP message: {e}")
    
    async def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to AMQP topic with wildcard support."""
        if not self.connected or not self.channel:
            raise ConnectionError("AMQP transport not connected")
        
        try:
            # Create unique queue for this subscription
            queue_name = f"praval.{uuid.uuid4().hex[:8]}.{topic.replace('#', 'all').replace('*', 'any')}"
            queue = await self.channel.declare_queue(
                queue_name,
                durable=True,
                exclusive=False,
                auto_delete=True
            )
            
            # Bind queue to exchange with routing key
            await queue.bind(self.exchange, routing_key=topic)
            
            # Setup consumer
            async def message_handler(message):
                async with message.process():
                    try:
                        await callback(message.body)
                    except Exception as e:
                        logger.error(f"AMQP message callback error: {e}")
            
            await queue.consume(message_handler)
            logger.info(f"Subscribed to AMQP topic: {topic}")
            
        except Exception as e:
            raise ConnectionError(f"Failed to subscribe to AMQP topic: {e}")
    
    async def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from AMQP topic."""
        # In AMQP, we would need to track queue names and cancel consumers
        # This is a simplified implementation
        logger.info(f"Unsubscribed from AMQP topic: {topic}")
    
    async def close(self) -> None:
        """Close AMQP connection."""
        try:
            if self.connection and not self.connection.is_closed:
                await self.connection.close()
            self.connected = False
            logger.info("AMQP transport closed")
        except Exception as e:
            logger.error(f"Error closing AMQP transport: {e}")


class MQTTTransport(MessageTransport):
    """
    MQTT transport implementation with TLS/SSL support.
    
    Features:
    - MQTT over TLS (port 8883)
    - QoS levels mapped from priority
    - Automatic reconnection
    - Topic-based pub/sub
    """
    
    def __init__(self):
        super().__init__()
        self.client = None
        self.subscriptions = {}
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize MQTT connection with TLS."""
        try:
            import asyncio_mqtt
        except ImportError:
            raise TransportError("asyncio-mqtt package required for MQTT transport")
        
        self.config = config
        
        # Create TLS context
        tls_context = self._create_tls_context(config)
        
        # MQTT connection parameters
        client_params = {
            'hostname': config.get('host', 'localhost'),
            'port': config.get('port', 8883),  # MQTT over TLS
            'tls_context': tls_context,
            'client_id': config.get('client_id', f'praval-{uuid.uuid4().hex[:8]}'),
            'keepalive': config.get('keepalive', 60),
            'username': config.get('username'),
            'password': config.get('password'),
        }
        
        # Remove None values
        client_params = {k: v for k, v in client_params.items() if v is not None}
        
        try:
            self.client = asyncio_mqtt.Client(**client_params)
            await self.client.__aenter__()
            
            self.connected = True
            logger.info(f"MQTT transport initialized: {client_params['hostname']}:{client_params['port']}")
            
        except Exception as e:
            raise ConnectionError(f"Failed to initialize MQTT transport: {e}")
    
    async def publish(self, topic: str, message: bytes, 
                     priority: int = 5, ttl: Optional[int] = None) -> None:
        """Publish message to MQTT topic."""
        if not self.connected or not self.client:
            raise PublishError("MQTT transport not connected")
        
        # Map priority to MQTT QoS (1-10 -> 0-2)
        qos_map = {
            1: 0, 2: 0, 3: 0, 4: 0,  # Low priority -> QoS 0
            5: 1, 6: 1, 7: 1,         # Medium priority -> QoS 1
            8: 2, 9: 2, 10: 2         # High priority -> QoS 2
        }
        qos = qos_map.get(priority, 1)
        
        try:
            full_topic = f"praval/spores/{topic}"
            
            await self.client.publish(
                topic=full_topic,
                payload=message,
                qos=qos,
                retain=False
            )
            
            logger.debug(f"Published MQTT message to topic: {full_topic} (QoS: {qos})")
            
        except Exception as e:
            raise PublishError(f"Failed to publish MQTT message: {e}")
    
    async def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to MQTT topic with wildcard support."""
        if not self.connected or not self.client:
            raise ConnectionError("MQTT transport not connected")
        
        try:
            full_topic = f"praval/spores/{topic}"
            
            await self.client.subscribe(full_topic, qos=2)
            
            # Store subscription for message handling
            self.subscriptions[full_topic] = callback
            
            # Start message listener if not already running
            if not hasattr(self, '_message_task'):
                self._message_task = asyncio.create_task(self._message_listener())
            
            logger.info(f"Subscribed to MQTT topic: {full_topic}")
            
        except Exception as e:
            raise ConnectionError(f"Failed to subscribe to MQTT topic: {e}")
    
    async def _message_listener(self):
        """Listen for incoming MQTT messages."""
        try:
            async for message in self.client.messages:
                topic = message.topic.value
                if callback := self.subscriptions.get(topic):
                    try:
                        await callback(message.payload)
                    except Exception as e:
                        logger.error(f"MQTT message callback error: {e}")
        except Exception as e:
            logger.error(f"MQTT message listener error: {e}")
    
    async def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from MQTT topic."""
        if not self.connected or not self.client:
            return
        
        try:
            full_topic = f"praval/spores/{topic}"
            await self.client.unsubscribe(full_topic)
            self.subscriptions.pop(full_topic, None)
            logger.info(f"Unsubscribed from MQTT topic: {full_topic}")
        except Exception as e:
            logger.error(f"Failed to unsubscribe from MQTT topic: {e}")
    
    async def close(self) -> None:
        """Close MQTT connection."""
        try:
            if hasattr(self, '_message_task'):
                self._message_task.cancel()
            
            if self.client:
                await self.client.__aexit__(None, None, None)
            
            self.connected = False
            logger.info("MQTT transport closed")
        except Exception as e:
            logger.error(f"Error closing MQTT transport: {e}")


class STOMPTransport(MessageTransport):
    """
    STOMP transport implementation with TLS support.
    
    Features:
    - STOMP over TLS
    - Message persistence
    - Topic-based messaging
    - Priority headers
    """
    
    def __init__(self):
        super().__init__()
        self.connection = None
        self.subscriptions = {}
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize STOMP connection with TLS."""
        try:
            import aiostomp
        except ImportError:
            raise TransportError("aiostomp package required for STOMP transport")
        
        self.config = config
        
        # Create TLS context
        tls_context = self._create_tls_context(config)
        
        try:
            self.connection = aiostomp.AioStomp(
                config.get('host', 'localhost'),
                config.get('port', 61614),  # STOMP over TLS
                ssl_context=tls_context,
                username=config.get('username'),
                passcode=config.get('password'),
            )
            
            await self.connection.connect()
            
            self.connected = True
            logger.info(f"STOMP transport initialized: {config.get('host', 'localhost')}:{config.get('port', 61614)}")
            
        except Exception as e:
            raise ConnectionError(f"Failed to initialize STOMP transport: {e}")
    
    async def publish(self, topic: str, message: bytes, 
                     priority: int = 5, ttl: Optional[int] = None) -> None:
        """Publish message to STOMP destination."""
        if not self.connected or not self.connection:
            raise PublishError("STOMP transport not connected")
        
        try:
            destination = f"/topic/praval.spores.{topic}"
            
            headers = {
                'priority': str(priority),
                'persistent': 'true'
            }
            
            if ttl:
                headers['expires'] = str(int(time.time() * 1000) + (ttl * 1000))
            
            await self.connection.send(
                destination=destination,
                body=message.decode('utf-8') if isinstance(message, bytes) else message,
                headers=headers
            )
            
            logger.debug(f"Published STOMP message to destination: {destination}")
            
        except Exception as e:
            raise PublishError(f"Failed to publish STOMP message: {e}")
    
    async def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to STOMP destination."""
        if not self.connected or not self.connection:
            raise ConnectionError("STOMP transport not connected")
        
        try:
            destination = f"/topic/praval.spores.{topic}"
            
            # Setup subscription handler
            async def message_handler(frame):
                try:
                    body = frame.body.encode('utf-8') if isinstance(frame.body, str) else frame.body
                    await callback(body)
                except Exception as e:
                    logger.error(f"STOMP message callback error: {e}")
            
            await self.connection.subscribe(destination, handler=message_handler)
            self.subscriptions[destination] = callback
            
            logger.info(f"Subscribed to STOMP destination: {destination}")
            
        except Exception as e:
            raise ConnectionError(f"Failed to subscribe to STOMP destination: {e}")
    
    async def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from STOMP destination."""
        if not self.connected or not self.connection:
            return
        
        try:
            destination = f"/topic/praval.spores.{topic}"
            await self.connection.unsubscribe(destination)
            self.subscriptions.pop(destination, None)
            logger.info(f"Unsubscribed from STOMP destination: {destination}")
        except Exception as e:
            logger.error(f"Failed to unsubscribe from STOMP destination: {e}")
    
    async def close(self) -> None:
        """Close STOMP connection."""
        try:
            if self.connection:
                await self.connection.disconnect()
            self.connected = False
            logger.info("STOMP transport closed")
        except Exception as e:
            logger.error(f"Error closing STOMP transport: {e}")


class TransportFactory:
    """Factory for creating message transport instances."""
    
    _transport_registry = {
        TransportProtocol.AMQP: AMQPTransport,
        TransportProtocol.MQTT: MQTTTransport,
        TransportProtocol.STOMP: STOMPTransport,
    }
    
    @classmethod
    def create_transport(cls, protocol: TransportProtocol) -> MessageTransport:
        """Create a transport instance for the specified protocol."""
        transport_class = cls._transport_registry.get(protocol)
        if not transport_class:
            raise ValueError(f"Unsupported transport protocol: {protocol}")
        
        return transport_class()
    
    @classmethod
    def register_transport(cls, protocol: TransportProtocol, transport_class: type):
        """Register a custom transport implementation."""
        if not issubclass(transport_class, MessageTransport):
            raise ValueError("Transport class must inherit from MessageTransport")
        
        cls._transport_registry[protocol] = transport_class
    
    @classmethod
    def get_supported_protocols(cls) -> list[TransportProtocol]:
        """Get list of supported transport protocols."""
        return list(cls._transport_registry.keys())


@asynccontextmanager
async def transport_connection(protocol: TransportProtocol, config: Dict[str, Any]):
    """
    Async context manager for transport connections.
    
    Usage:
        async with transport_connection(TransportProtocol.MQTT, config) as transport:
            await transport.publish("test/topic", b"Hello World!")
    """
    transport = TransportFactory.create_transport(protocol)
    try:
        await transport.initialize(config)
        yield transport
    finally:
        await transport.close()