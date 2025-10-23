"""
Comprehensive tests for secure reef implementation.

This module tests:
- Secure reef initialization and configuration
- Key registry functionality
- End-to-end secure spore communication
- Backward compatibility with existing Reef API
- Error handling and security features
- Multi-protocol transport integration
"""

import asyncio
import pytest
import time
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import AsyncMock, patch

from praval.core.secure_reef import SecureReef, KeyRegistry
from praval.core.secure_spore import SporeKeyManager
from praval.core.transport import TransportProtocol
from praval.core.reef import SporeType
from test_transport import MockTransport


class TestKeyRegistry:
    """Test key registry functionality."""
    
    @pytest.fixture
    def key_registry(self):
        """Create key registry for testing."""
        return KeyRegistry()
    
    @pytest.fixture
    def sample_keys(self):
        """Sample public keys for testing."""
        km = SporeKeyManager("test_agent")
        return km.get_public_keys()
    
    @pytest.mark.asyncio
    async def test_register_agent(self, key_registry, sample_keys):
        """Test registering agent public keys."""
        agent_name = "test_agent"
        
        await key_registry.register_agent(agent_name, sample_keys)
        
        registered_keys = await key_registry.get_agent_keys(agent_name)
        assert registered_keys == sample_keys
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_agent(self, key_registry):
        """Test getting keys for non-existent agent."""
        keys = await key_registry.get_agent_keys("nonexistent")
        assert keys is None
    
    @pytest.mark.asyncio
    async def test_remove_agent(self, key_registry, sample_keys):
        """Test removing agent keys."""
        agent_name = "test_agent"
        
        # Register then remove
        await key_registry.register_agent(agent_name, sample_keys)
        await key_registry.remove_agent(agent_name)
        
        # Verify removal
        keys = await key_registry.get_agent_keys(agent_name)
        assert keys is None
    
    @pytest.mark.asyncio
    async def test_list_agents(self, key_registry):
        """Test listing registered agents."""
        # Initially empty
        agents = await key_registry.list_agents()
        assert agents == []
        
        # Register multiple agents
        km1 = SporeKeyManager("agent1")
        km2 = SporeKeyManager("agent2")
        
        await key_registry.register_agent("agent1", km1.get_public_keys())
        await key_registry.register_agent("agent2", km2.get_public_keys())
        
        # Verify listing
        agents = await key_registry.list_agents()
        assert set(agents) == {"agent1", "agent2"}
    
    @pytest.mark.asyncio
    async def test_concurrent_key_operations(self, key_registry):
        """Test concurrent key registry operations."""
        # Create multiple agents concurrently
        async def register_agent(name):
            km = SporeKeyManager(name)
            await key_registry.register_agent(name, km.get_public_keys())
        
        # Register 10 agents concurrently
        tasks = [register_agent(f"agent_{i}") for i in range(10)]
        await asyncio.gather(*tasks)
        
        # Verify all registered
        agents = await key_registry.list_agents()
        expected_agents = {f"agent_{i}" for i in range(10)}
        assert set(agents) == expected_agents


class TestSecureReef:
    """Test secure reef communication system."""
    
    @pytest.fixture
    def mock_transport_factory(self):
        """Mock transport factory for testing."""
        with patch('src.praval.core.secure_reef.TransportFactory') as mock_factory:
            mock_transport = MockTransport()
            mock_factory.create_transport.return_value = mock_transport
            yield mock_factory, mock_transport
    
    @pytest.fixture
    async def secure_reef(self, mock_transport_factory):
        """Create secure reef for testing."""
        factory, transport = mock_transport_factory
        
        reef = SecureReef(
            protocol=TransportProtocol.AMQP,
            transport_config={'host': 'localhost', 'port': 5672}
        )
        
        await reef.initialize("test_agent")
        return reef, transport
    
    @pytest.mark.asyncio
    async def test_secure_reef_initialization(self, mock_transport_factory):
        """Test secure reef initialization."""
        factory, transport = mock_transport_factory
        
        reef = SecureReef(
            protocol=TransportProtocol.MQTT,
            transport_config={'host': 'localhost', 'port': 1883}
        )
        
        await reef.initialize("test_agent")
        
        # Verify initialization
        assert reef.agent_name == "test_agent"
        assert reef.connected == True
        assert reef.key_manager is not None
        assert reef.spore_factory is not None
        
        # Verify transport initialization
        factory.create_transport.assert_called_once_with(TransportProtocol.MQTT)
        transport.initialize.assert_called_once()
        
        # Verify key registration
        keys = await reef.key_registry.get_agent_keys("test_agent")
        assert keys is not None
        assert 'verify_key' in keys
        assert 'public_key' in keys
    
    @pytest.mark.asyncio
    async def test_send_secure_spore_targeted(self, secure_reef):
        """Test sending secure spore to specific agent."""
        reef, transport = secure_reef
        
        # Register recipient keys
        recipient_km = SporeKeyManager("recipient")
        await reef.key_registry.register_agent(
            "recipient", 
            recipient_km.get_public_keys()
        )
        
        # Send secure spore
        knowledge = {"message": "Hello, secure world!", "timestamp": time.time()}
        spore_id = await reef.send_secure_spore(
            to_agent="recipient",
            knowledge=knowledge,
            spore_type=SporeType.REQUEST,
            priority=8,
            expires_in_seconds=300
        )
        
        # Verify spore was sent
        assert spore_id is not None
        assert len(transport.messages) == 1
        assert reef.stats['spores_sent'] == 1
        
        # Verify message content
        sent_message = transport.messages[0]
        assert sent_message['priority'] == 8
        assert sent_message['ttl'] == 300
        assert 'agent.recipient.request' in sent_message['topic']
    
    @pytest.mark.asyncio
    async def test_send_secure_spore_broadcast(self, secure_reef):
        """Test sending broadcast secure spore."""
        reef, transport = secure_reef
        
        # Send broadcast spore
        knowledge = {"announcement": "System maintenance in 1 hour"}
        spore_id = await reef.send_secure_spore(
            to_agent=None,
            knowledge=knowledge,
            spore_type=SporeType.BROADCAST,
            priority=10
        )
        
        # Verify spore was sent
        assert spore_id is not None
        assert len(transport.messages) == 1
        assert reef.stats['spores_sent'] == 1
        
        # Verify broadcast message
        sent_message = transport.messages[0]
        assert sent_message['priority'] == 10
        assert 'broadcast' in sent_message['topic']
    
    @pytest.mark.asyncio
    async def test_send_without_recipient_keys(self, secure_reef):
        """Test sending to agent without registered keys fails."""
        reef, transport = secure_reef
        
        knowledge = {"test": "data"}
        
        with pytest.raises(ValueError, match="No public keys found for agent"):
            await reef.send_secure_spore(
                to_agent="unknown_agent",
                knowledge=knowledge
            )
    
    @pytest.mark.asyncio
    async def test_send_without_connection(self, mock_transport_factory):
        """Test sending without connection fails."""
        factory, transport = mock_transport_factory
        
        reef = SecureReef(protocol=TransportProtocol.AMQP)
        # Don't initialize - should fail
        
        knowledge = {"test": "data"}
        
        with pytest.raises(ConnectionError, match="Secure reef not connected"):
            await reef.send_secure_spore(to_agent="test", knowledge=knowledge)
    
    @pytest.mark.asyncio
    async def test_receive_secure_spore(self, secure_reef):
        """Test receiving and processing secure spores."""
        reef, transport = secure_reef
        
        # Setup message handler
        received_spores = []
        
        def spore_handler(spore):
            received_spores.append(spore)
        
        reef.register_handler(SporeType.KNOWLEDGE, spore_handler)
        
        # Create secure spore from another agent
        sender_km = SporeKeyManager("sender")
        await reef.key_registry.register_agent("sender", sender_km.get_public_keys())
        
        # Create and serialize secure spore
        from src.praval.core.secure_spore import SecureSporeFactory
        sender_factory = SecureSporeFactory(sender_km)
        
        knowledge = {"received": "message", "data": [1, 2, 3]}
        secure_spore = sender_factory.create_secure_spore(
            to_agent="test_agent",
            knowledge=knowledge,
            spore_type=SporeType.KNOWLEDGE,
            recipient_public_keys=reef.key_manager.get_public_keys()
        )
        
        # Simulate message reception
        await reef._handle_incoming_message(secure_spore.to_bytes())
        
        # Verify message was processed
        assert len(received_spores) == 1
        assert reef.stats['spores_received'] == 1
        
        received_spore = received_spores[0]
        assert received_spore.from_agent == "sender"
        assert received_spore.to_agent == "test_agent"
        assert received_spore.knowledge == knowledge
    
    @pytest.mark.asyncio
    async def test_receive_expired_spore(self, secure_reef):
        """Test that expired spores are ignored."""
        reef, transport = secure_reef
        
        # Setup handler
        received_spores = []
        reef.register_handler(SporeType.KNOWLEDGE, lambda s: received_spores.append(s))
        
        # Create expired spore
        from src.praval.core.secure_spore import SecureSpore
        expired_spore = SecureSpore(
            id="expired-test",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="test_agent",
            created_at=datetime.now() - timedelta(hours=2),
            expires_at=datetime.now() - timedelta(hours=1),  # Expired
            encrypted_knowledge=b"test_data",
            knowledge_signature=b"signature",
            sender_public_key=b"public_key",
            nonce=b"nonce"
        )
        
        # Simulate reception
        await reef._handle_incoming_message(expired_spore.to_bytes())
        
        # Verify expired spore was ignored
        assert len(received_spores) == 0
        assert reef.stats['spores_received'] == 0
    
    @pytest.mark.asyncio
    async def test_receive_own_message(self, secure_reef):
        """Test that own messages are ignored."""
        reef, transport = secure_reef
        
        # Setup handler
        received_spores = []
        reef.register_handler(SporeType.KNOWLEDGE, lambda s: received_spores.append(s))
        
        # Create spore from same agent
        from src.praval.core.secure_spore import SecureSpore
        own_spore = SecureSpore(
            id="own-test",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="test_agent",  # Same as reef agent
            to_agent="other_agent",
            created_at=datetime.now(),
            encrypted_knowledge=b"test_data",
            knowledge_signature=b"signature",
            sender_public_key=b"public_key",
            nonce=b"nonce"
        )
        
        # Simulate reception
        await reef._handle_incoming_message(own_spore.to_bytes())
        
        # Verify own message was ignored
        assert len(received_spores) == 0
        assert reef.stats['spores_received'] == 0
    
    @pytest.mark.asyncio
    async def test_handle_malformed_message(self, secure_reef):
        """Test handling of malformed messages."""
        reef, transport = secure_reef
        
        # Simulate malformed message
        malformed_data = b"not_a_valid_secure_spore"
        
        # Should not crash
        await reef._handle_incoming_message(malformed_data)
        
        # Verify error was tracked
        assert reef.stats['encryption_errors'] == 1
        assert reef.stats['spores_received'] == 0
    
    @pytest.mark.asyncio
    async def test_handle_tampered_message(self, secure_reef):
        """Test handling of tampered messages."""
        reef, transport = secure_reef
        
        # Create valid spore then tamper with it
        sender_km = SporeKeyManager("sender")
        await reef.key_registry.register_agent("sender", sender_km.get_public_keys())
        
        from src.praval.core.secure_spore import SecureSporeFactory
        sender_factory = SecureSporeFactory(sender_km)
        
        secure_spore = sender_factory.create_secure_spore(
            to_agent="test_agent",
            knowledge={"test": "data"},
            recipient_public_keys=reef.key_manager.get_public_keys()
        )
        
        # Tamper with signature
        secure_spore.knowledge_signature = b"tampered_signature"
        
        # Should handle tampered message gracefully
        await reef._handle_incoming_message(secure_spore.to_bytes())
        
        # Verify error was tracked
        assert reef.stats['encryption_errors'] == 1
        assert reef.stats['spores_received'] == 0
    
    @pytest.mark.asyncio
    async def test_handler_registration(self, secure_reef):
        """Test spore handler registration and removal."""
        reef, transport = secure_reef
        
        handler1 = lambda s: None
        handler2 = lambda s: None
        
        # Register handlers
        reef.register_handler(SporeType.KNOWLEDGE, handler1)
        reef.register_handler(SporeType.KNOWLEDGE, handler2)
        reef.register_handler(SporeType.REQUEST, handler1)
        
        # Verify registration
        assert len(reef.message_handlers[SporeType.KNOWLEDGE.value]) == 2
        assert len(reef.message_handlers[SporeType.REQUEST.value]) == 1
        
        # Unregister handler
        reef.unregister_handler(SporeType.KNOWLEDGE, handler1)
        
        # Verify removal
        assert len(reef.message_handlers[SporeType.KNOWLEDGE.value]) == 1
        assert handler2 in reef.message_handlers[SporeType.KNOWLEDGE.value]
    
    @pytest.mark.asyncio
    async def test_backward_compatibility_methods(self, secure_reef):
        """Test backward compatibility with existing Reef API."""
        reef, transport = secure_reef
        
        # Register recipient
        recipient_km = SporeKeyManager("recipient")
        await reef.key_registry.register_agent(
            "recipient",
            recipient_km.get_public_keys()
        )
        
        # Test send method
        knowledge = {"compat": "test"}
        spore_id = await reef.send(
            from_agent="test_agent",  # Should be ignored
            to_agent="recipient",
            knowledge=knowledge,
            spore_type=SporeType.REQUEST,
            priority=7
        )
        
        assert spore_id is not None
        assert len(transport.messages) == 1
        
        # Test broadcast method
        broadcast_id = await reef.broadcast({"announcement": "test"})
        
        assert broadcast_id is not None
        assert len(transport.messages) == 2
        
        # Test request method
        request_id = await reef.request(
            to_agent="recipient",
            request={"query": "test"}
        )
        
        assert request_id is not None
        assert len(transport.messages) == 3
        
        # Test reply method
        reply_id = await reef.reply(
            to_agent="recipient",
            response={"result": "success"},
            reply_to_spore_id="original-id"
        )
        
        assert reply_id is not None
        assert len(transport.messages) == 4
    
    @pytest.mark.asyncio
    async def test_key_rotation(self, secure_reef):
        """Test cryptographic key rotation."""
        reef, transport = secure_reef
        
        # Get original keys
        original_keys = reef.key_manager.get_public_keys()
        
        # Rotate keys
        rotation_result = await reef.rotate_keys()
        
        # Verify keys changed
        new_keys = reef.key_manager.get_public_keys()
        assert new_keys != original_keys
        
        # Verify keys updated in registry
        registry_keys = await reef.key_registry.get_agent_keys("test_agent")
        assert registry_keys == new_keys
        
        # Verify rotation result
        assert 'old_signing_key' in rotation_result
        assert 'new_verify_key' in rotation_result
    
    @pytest.mark.asyncio
    async def test_key_export(self, secure_reef):
        """Test key export functionality."""
        reef, transport = secure_reef
        
        exported_keys = reef.export_keys()
        
        assert isinstance(exported_keys, dict)
        assert exported_keys['agent_name'] == "test_agent"
        assert 'signing_key' in exported_keys
        assert 'box_key' in exported_keys
        assert 'verify_key' in exported_keys
        assert 'public_key' in exported_keys
    
    @pytest.mark.asyncio
    async def test_reef_statistics(self, secure_reef):
        """Test reef statistics collection."""
        reef, transport = secure_reef
        
        # Register another agent for stats
        km = SporeKeyManager("other_agent")
        await reef.key_registry.register_agent("other_agent", km.get_public_keys())
        
        # Send some messages
        await reef.send_secure_spore(
            to_agent="other_agent",
            knowledge={"test": "stats"}
        )
        
        # Get statistics
        stats = reef.get_stats()
        
        assert stats['agent_name'] == "test_agent"
        assert stats['protocol'] == TransportProtocol.AMQP.value
        assert stats['connected'] == True
        assert stats['spores_sent'] == 1
        assert stats['spores_received'] == 0
        assert stats['registered_agents'] == 2
        assert 'uptime_seconds' in stats
        assert stats['uptime_seconds'] > 0
    
    @pytest.mark.asyncio
    async def test_reef_close(self, secure_reef):
        """Test reef connection closing."""
        reef, transport = secure_reef
        
        # Verify reef is active
        assert reef.connected
        
        # Close reef
        await reef.close()
        
        # Verify cleanup
        assert not reef.connected
        
        # Verify agent removed from registry
        keys = await reef.key_registry.get_agent_keys("test_agent")
        assert keys is None
    
    @pytest.mark.asyncio
    async def test_protocol_specific_topic_generation(self, mock_transport_factory):
        """Test protocol-specific topic generation."""
        factory, transport = mock_transport_factory
        
        # Test different protocols
        protocols_and_expected = [
            (TransportProtocol.AMQP, "agent.recipient.knowledge"),
            (TransportProtocol.MQTT, "agent/recipient/knowledge"),
            (TransportProtocol.STOMP, "agent.recipient.knowledge")
        ]
        
        for protocol, expected_topic in protocols_and_expected:
            reef = SecureReef(protocol=protocol)
            
            # Test topic generation
            topic = reef._generate_topic("recipient", "knowledge")
            assert topic == expected_topic
            
            # Test broadcast topic
            broadcast_topic = reef._generate_topic(None, "knowledge")
            if protocol == TransportProtocol.MQTT:
                assert broadcast_topic == "broadcast/knowledge"
            else:
                assert broadcast_topic == "broadcast.knowledge"


class TestSecureReefPerformance:
    """Test secure reef performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_message_throughput(self, mock_transport_factory):
        """Test secure spore throughput."""
        factory, transport = mock_transport_factory
        
        reef = SecureReef(protocol=TransportProtocol.AMQP)
        await reef.initialize("performance_test")
        
        # Register recipient
        recipient_km = SporeKeyManager("recipient")
        await reef.key_registry.register_agent(
            "recipient", 
            recipient_km.get_public_keys()
        )
        
        # Send many messages
        message_count = 100
        knowledge = {"perf": "test", "data": "x" * 100}
        
        start_time = time.time()
        
        tasks = []
        for i in range(message_count):
            task = reef.send_secure_spore(
                to_agent="recipient",
                knowledge={**knowledge, "index": i}
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Calculate throughput
        throughput = message_count / duration
        
        # Should handle reasonable throughput
        assert throughput > 10, f"Low throughput: {throughput:.2f} msg/sec"
        assert len(transport.messages) == message_count
        assert reef.stats['spores_sent'] == message_count
    
    @pytest.mark.asyncio
    async def test_concurrent_agents(self, mock_transport_factory):
        """Test multiple concurrent agents."""
        factory, transport = mock_transport_factory
        
        # Create multiple reefs
        agent_count = 10
        reefs = []
        
        for i in range(agent_count):
            reef = SecureReef(protocol=TransportProtocol.AMQP)
            await reef.initialize(f"agent_{i}")
            reefs.append(reef)
        
        # Cross-register all agents
        for reef in reefs:
            for other_reef in reefs:
                if reef != other_reef:
                    await reef.key_registry.register_agent(
                        other_reef.agent_name,
                        other_reef.key_manager.get_public_keys()
                    )
        
        # Send messages concurrently
        tasks = []
        for i, reef in enumerate(reefs):
            target_agent = f"agent_{(i + 1) % agent_count}"
            task = reef.send_secure_spore(
                to_agent=target_agent,
                knowledge={"from": reef.agent_name, "to": target_agent}
            )
            tasks.append(task)
        
        start_time = time.time()
        await asyncio.gather(*tasks)
        end_time = time.time()
        
        duration = end_time - start_time
        
        # Should handle concurrent operations efficiently
        assert duration < 5.0, f"Slow concurrent operations: {duration:.3f}s"
        
        # Verify all messages sent
        total_sent = sum(reef.stats['spores_sent'] for reef in reefs)
        assert total_sent == agent_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])