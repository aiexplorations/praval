"""
Comprehensive tests for transport abstraction layer.

This module tests:
- Transport factory and protocol selection
- Mock transport implementations for testing
- Transport error handling
- Message publishing and subscription patterns
- TLS/SSL configuration
"""

import asyncio
import pytest
import ssl
import time
from typing import Dict, Any, Callable, List
from unittest.mock import Mock, AsyncMock, patch

from praval.core.transport import (
    TransportProtocol, MessageTransport, TransportFactory,
    AMQPTransport, MQTTTransport, STOMPTransport,
    TransportError, ConnectionError, PublishError,
    transport_connection
)


class MockTransport(MessageTransport):
    """Mock transport implementation for testing."""
    
    def __init__(self):
        super().__init__()
        self.messages = []
        self.subscriptions = {}
        self.should_fail_init = False
        self.should_fail_publish = False
        self.should_fail_subscribe = False
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        if self.should_fail_init:
            raise ConnectionError("Mock initialization failure")
        
        self.config = config
        self.connected = True
    
    async def publish(self, topic: str, message: bytes, 
                     priority: int = 5, ttl: int = None) -> None:
        if self.should_fail_publish:
            raise PublishError("Mock publish failure")
        
        if not self.connected:
            raise PublishError("Transport not connected")
        
        self.messages.append({
            'topic': topic,
            'message': message,
            'priority': priority,
            'ttl': ttl,
            'timestamp': time.time()
        })
    
    async def subscribe(self, topic: str, callback: Callable) -> None:
        if self.should_fail_subscribe:
            raise ConnectionError("Mock subscribe failure")
        
        if not self.connected:
            raise ConnectionError("Transport not connected")
        
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
        self.subscriptions[topic].append(callback)
    
    async def unsubscribe(self, topic: str) -> None:
        self.subscriptions.pop(topic, None)
    
    async def close(self) -> None:
        self.connected = False
        self.messages.clear()
        self.subscriptions.clear()
    
    async def simulate_message(self, topic: str, message: bytes):
        """Simulate receiving a message for testing."""
        callbacks = self.subscriptions.get(topic, [])
        for callback in callbacks:
            await callback(message)


class TestTransportFactory:
    """Test transport factory functionality."""
    
    def test_create_transport_amqp(self):
        """Test creating AMQP transport."""
        transport = TransportFactory.create_transport(TransportProtocol.AMQP)
        assert isinstance(transport, AMQPTransport)
    
    def test_create_transport_mqtt(self):
        """Test creating MQTT transport."""
        transport = TransportFactory.create_transport(TransportProtocol.MQTT)
        assert isinstance(transport, MQTTTransport)
    
    def test_create_transport_stomp(self):
        """Test creating STOMP transport."""
        transport = TransportFactory.create_transport(TransportProtocol.STOMP)
        assert isinstance(transport, STOMPTransport)
    
    def test_create_transport_unsupported(self):
        """Test creating transport with unsupported protocol."""
        with pytest.raises(ValueError, match="Unsupported transport protocol"):
            TransportFactory.create_transport("invalid_protocol")
    
    def test_register_custom_transport(self):
        """Test registering custom transport implementation."""
        # Register mock transport
        TransportFactory.register_transport(TransportProtocol.REDIS, MockTransport)
        
        # Verify it can be created
        transport = TransportFactory.create_transport(TransportProtocol.REDIS)
        assert isinstance(transport, MockTransport)
        
        # Clean up
        del TransportFactory._transport_registry[TransportProtocol.REDIS]
    
    def test_register_invalid_transport_class(self):
        """Test registering invalid transport class."""
        class InvalidTransport:
            pass
        
        with pytest.raises(ValueError, match="must inherit from MessageTransport"):
            TransportFactory.register_transport(TransportProtocol.REDIS, InvalidTransport)
    
    def test_get_supported_protocols(self):
        """Test getting list of supported protocols."""
        protocols = TransportFactory.get_supported_protocols()
        
        assert TransportProtocol.AMQP in protocols
        assert TransportProtocol.MQTT in protocols
        assert TransportProtocol.STOMP in protocols
        assert isinstance(protocols, list)


class TestMessageTransport:
    """Test base message transport functionality."""
    
    @pytest.fixture
    def mock_transport(self):
        """Create mock transport for testing."""
        return MockTransport()
    
    @pytest.mark.asyncio
    async def test_transport_initialization(self, mock_transport):
        """Test transport initialization."""
        config = {
            'host': 'localhost',
            'port': 5672,
            'username': 'test',
            'password': 'secret'
        }
        
        await mock_transport.initialize(config)
        
        assert mock_transport.connected
        assert mock_transport.config == config
    
    @pytest.mark.asyncio
    async def test_transport_initialization_failure(self, mock_transport):
        """Test transport initialization failure."""
        mock_transport.should_fail_init = True
        
        with pytest.raises(ConnectionError, match="Mock initialization failure"):
            await mock_transport.initialize({})
        
        assert not mock_transport.connected
    
    @pytest.mark.asyncio
    async def test_publish_message(self, mock_transport):
        """Test publishing messages."""
        await mock_transport.initialize({})
        
        message = b"test message"
        topic = "test.topic"
        priority = 7
        ttl = 300
        
        await mock_transport.publish(topic, message, priority, ttl)
        
        assert len(mock_transport.messages) == 1
        published = mock_transport.messages[0]
        assert published['topic'] == topic
        assert published['message'] == message
        assert published['priority'] == priority
        assert published['ttl'] == ttl
    
    @pytest.mark.asyncio
    async def test_publish_without_connection(self, mock_transport):
        """Test publishing without connection fails."""
        message = b"test message"
        
        with pytest.raises(PublishError, match="Transport not connected"):
            await mock_transport.publish("test.topic", message)
    
    @pytest.mark.asyncio
    async def test_publish_failure(self, mock_transport):
        """Test publish failure handling."""
        await mock_transport.initialize({})
        mock_transport.should_fail_publish = True
        
        with pytest.raises(PublishError, match="Mock publish failure"):
            await mock_transport.publish("test.topic", b"message")
    
    @pytest.mark.asyncio
    async def test_subscribe_to_topic(self, mock_transport):
        """Test subscribing to topics."""
        await mock_transport.initialize({})
        
        callback = AsyncMock()
        topic = "test.subscription"
        
        await mock_transport.subscribe(topic, callback)
        
        assert topic in mock_transport.subscriptions
        assert callback in mock_transport.subscriptions[topic]
    
    @pytest.mark.asyncio
    async def test_subscribe_without_connection(self, mock_transport):
        """Test subscribing without connection fails."""
        callback = AsyncMock()
        
        with pytest.raises(ConnectionError, match="Transport not connected"):
            await mock_transport.subscribe("test.topic", callback)
    
    @pytest.mark.asyncio
    async def test_subscribe_failure(self, mock_transport):
        """Test subscribe failure handling."""
        await mock_transport.initialize({})
        mock_transport.should_fail_subscribe = True
        
        callback = AsyncMock()
        
        with pytest.raises(ConnectionError, match="Mock subscribe failure"):
            await mock_transport.subscribe("test.topic", callback)
    
    @pytest.mark.asyncio
    async def test_message_delivery(self, mock_transport):
        """Test message delivery to subscribers."""
        await mock_transport.initialize({})
        
        # Setup subscription
        callback = AsyncMock()
        topic = "test.delivery"
        await mock_transport.subscribe(topic, callback)
        
        # Simulate message delivery
        test_message = b"delivered message"
        await mock_transport.simulate_message(topic, test_message)
        
        # Verify callback was called
        callback.assert_called_once_with(test_message)
    
    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, mock_transport):
        """Test multiple subscribers on same topic."""
        await mock_transport.initialize({})
        
        # Setup multiple subscriptions
        callback1 = AsyncMock()
        callback2 = AsyncMock()
        topic = "test.multi"
        
        await mock_transport.subscribe(topic, callback1)
        await mock_transport.subscribe(topic, callback2)
        
        # Simulate message delivery
        test_message = b"multi subscriber message"
        await mock_transport.simulate_message(topic, test_message)
        
        # Verify both callbacks were called
        callback1.assert_called_once_with(test_message)
        callback2.assert_called_once_with(test_message)
    
    @pytest.mark.asyncio
    async def test_unsubscribe(self, mock_transport):
        """Test unsubscribing from topics."""
        await mock_transport.initialize({})
        
        # Setup subscription
        callback = AsyncMock()
        topic = "test.unsubscribe"
        await mock_transport.subscribe(topic, callback)
        
        # Verify subscription exists
        assert topic in mock_transport.subscriptions
        
        # Unsubscribe
        await mock_transport.unsubscribe(topic)
        
        # Verify subscription removed
        assert topic not in mock_transport.subscriptions
    
    @pytest.mark.asyncio
    async def test_transport_close(self, mock_transport):
        """Test transport connection closing."""
        await mock_transport.initialize({})
        await mock_transport.publish("test", b"message")
        await mock_transport.subscribe("test", AsyncMock())
        
        # Verify transport is active
        assert mock_transport.connected
        assert len(mock_transport.messages) > 0
        assert len(mock_transport.subscriptions) > 0
        
        # Close transport
        await mock_transport.close()
        
        # Verify cleanup
        assert not mock_transport.connected
        assert len(mock_transport.messages) == 0
        assert len(mock_transport.subscriptions) == 0


class TestTLSConfiguration:
    """Test TLS/SSL configuration handling."""
    
    @pytest.fixture
    def tls_config(self):
        """Sample TLS configuration."""
        return {
            'ca_cert': '/path/to/ca.pem',
            'client_cert': '/path/to/client.pem',
            'client_key': '/path/to/client.key',
            'verify_certs': True,
            'check_hostname': True
        }
    
    def test_tls_context_creation(self, tls_config):
        """Test SSL context creation."""
        transport = MockTransport()
        
        # Mock SSL context creation
        with patch('ssl.create_default_context') as mock_ssl:
            mock_context = Mock()
            mock_ssl.return_value = mock_context
            
            context = transport._create_tls_context(tls_config)
            
            # Verify SSL context was configured
            mock_ssl.assert_called_once_with(ssl.Purpose.SERVER_AUTH)
            assert context == mock_context
    
    def test_tls_context_no_verification(self):
        """Test SSL context with verification disabled."""
        transport = MockTransport()
        config = {'verify_certs': False}
        
        with patch('ssl.create_default_context') as mock_ssl:
            mock_context = Mock()
            mock_ssl.return_value = mock_context
            
            transport._create_tls_context(config)
            
            # Verify verification was disabled
            assert mock_context.check_hostname == False
            assert mock_context.verify_mode == ssl.CERT_NONE


@pytest.mark.asyncio
class TestTransportConnectionManager:
    """Test transport connection context manager."""
    
    async def test_connection_context_manager(self):
        """Test transport connection context manager."""
        # Register mock transport for testing
        TransportFactory.register_transport(TransportProtocol.REDIS, MockTransport)
        
        config = {'host': 'localhost', 'port': 6379}
        
        # Test successful connection
        async with transport_connection(TransportProtocol.REDIS, config) as transport:
            assert isinstance(transport, MockTransport)
            assert transport.connected
            
            # Test operations within context
            await transport.publish("test", b"message")
            assert len(transport.messages) == 1
        
        # Verify cleanup after context exit
        assert not transport.connected
        
        # Clean up
        del TransportFactory._transport_registry[TransportProtocol.REDIS]
    
    async def test_connection_context_manager_failure(self):
        """Test transport connection context manager with failure."""
        # Register failing mock transport
        TransportFactory.register_transport(TransportProtocol.REDIS, MockTransport)
        
        config = {'host': 'localhost', 'port': 6379}
        
        # Create transport that fails initialization
        failing_transport = MockTransport()
        failing_transport.should_fail_init = True
        
        with patch.object(TransportFactory, 'create_transport', return_value=failing_transport):
            with pytest.raises(ConnectionError):
                async with transport_connection(TransportProtocol.REDIS, config) as transport:
                    pass
        
        # Clean up
        del TransportFactory._transport_registry[TransportProtocol.REDIS]


class TestTransportPerformance:
    """Test transport performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_message_throughput(self):
        """Test message publishing throughput."""
        transport = MockTransport()
        await transport.initialize({})
        
        # Publish many messages and measure time
        message_count = 1000
        message = b"performance test message"
        
        start_time = time.time()
        
        for i in range(message_count):
            await transport.publish(f"perf.test.{i}", message, priority=5)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Calculate throughput
        throughput = message_count / duration
        
        # Should handle at least 1000 messages per second
        assert throughput > 1000, f"Low throughput: {throughput:.2f} msg/sec"
        assert len(transport.messages) == message_count
    
    @pytest.mark.asyncio
    async def test_subscription_scalability(self):
        """Test subscription scalability."""
        transport = MockTransport()
        await transport.initialize({})
        
        # Create many subscriptions
        subscription_count = 100
        callbacks = []
        
        start_time = time.time()
        
        for i in range(subscription_count):
            callback = AsyncMock()
            callbacks.append(callback)
            await transport.subscribe(f"scale.test.{i}", callback)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Subscriptions should be fast
        assert duration < 1.0, f"Slow subscription setup: {duration:.3f}s"
        assert len(transport.subscriptions) == subscription_count
        
        # Test message delivery to all subscriptions
        delivery_start = time.time()
        
        for i in range(subscription_count):
            await transport.simulate_message(f"scale.test.{i}", b"scale test")
        
        delivery_end = time.time()
        delivery_duration = delivery_end - delivery_start
        
        # Message delivery should be fast
        assert delivery_duration < 2.0, f"Slow message delivery: {delivery_duration:.3f}s"
        
        # Verify all callbacks were called
        for callback in callbacks:
            callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent publish and subscribe operations."""
        transport = MockTransport()
        await transport.initialize({})
        
        # Setup subscription
        callback = AsyncMock()
        await transport.subscribe("concurrent.test", callback)
        
        # Concurrent publish tasks
        async def publish_messages(start_idx, count):
            for i in range(count):
                await transport.publish(
                    f"concurrent.test.{start_idx + i}", 
                    f"message_{start_idx + i}".encode()
                )
        
        # Run multiple publish tasks concurrently
        tasks = [
            asyncio.create_task(publish_messages(0, 100)),
            asyncio.create_task(publish_messages(100, 100)),
            asyncio.create_task(publish_messages(200, 100))
        ]
        
        start_time = time.time()
        await asyncio.gather(*tasks)
        end_time = time.time()
        
        duration = end_time - start_time
        assert duration < 2.0, f"Slow concurrent operations: {duration:.3f}s"
        assert len(transport.messages) == 300


if __name__ == "__main__":
    pytest.main([__file__, "-v"])