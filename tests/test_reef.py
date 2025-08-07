"""
Tests for the Reef communication system.

Following TDD principles, these tests define the expected behavior
before implementing the actual Reef system.
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from typing import Dict, Any, List

# Import the classes we'll implement
from praval.core.reef import Spore, SporeType, ReefChannel, Reef, get_reef


class TestSpore:
    """Test the Spore message class."""
    
    def test_spore_creation(self):
        """Test basic spore creation."""
        spore = Spore(
            id="test-123",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="agent1",
            to_agent="agent2",
            knowledge={"fact": "water is wet"},
            created_at=datetime.now()
        )
        
        assert spore.id == "test-123"
        assert spore.spore_type == SporeType.KNOWLEDGE
        assert spore.from_agent == "agent1"
        assert spore.to_agent == "agent2"
        assert spore.knowledge == {"fact": "water is wet"}
        assert spore.priority == 5  # default
        assert spore.reply_to is None
        assert spore.metadata == {}
    
    def test_spore_with_expiration(self):
        """Test spore with expiration time."""
        expires_at = datetime.now() + timedelta(minutes=5)
        spore = Spore(
            id="test-456",
            spore_type=SporeType.REQUEST,
            from_agent="agent1",
            to_agent="agent2",
            knowledge={"question": "what is 2+2?"},
            created_at=datetime.now(),
            expires_at=expires_at,
            priority=8
        )
        
        assert not spore.is_expired()
        assert spore.priority == 8
        assert spore.expires_at == expires_at
    
    def test_spore_expiration_check(self):
        """Test spore expiration logic."""
        # Create expired spore
        expired_spore = Spore(
            id="expired",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="agent1",
            to_agent="agent2",
            knowledge={"old": "data"},
            created_at=datetime.now() - timedelta(hours=1),
            expires_at=datetime.now() - timedelta(minutes=30)
        )
        
        assert expired_spore.is_expired()
        
        # Create non-expiring spore
        no_expiry_spore = Spore(
            id="forever",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="agent1",
            to_agent="agent2",
            knowledge={"permanent": "data"},
            created_at=datetime.now()
        )
        
        assert not no_expiry_spore.is_expired()
    
    def test_spore_json_serialization(self):
        """Test spore JSON serialization and deserialization."""
        original = Spore(
            id="json-test",
            spore_type=SporeType.BROADCAST,
            from_agent="sender",
            to_agent=None,
            knowledge={"message": "hello reef", "number": 42},
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1),
            priority=7,
            reply_to="original-request",
            metadata={"source": "test"}
        )
        
        # Serialize to JSON
        json_str = original.to_json()
        assert isinstance(json_str, str)
        assert "json-test" in json_str
        assert "hello reef" in json_str
        
        # Deserialize from JSON
        restored = Spore.from_json(json_str)
        
        assert restored.id == original.id
        assert restored.spore_type == original.spore_type
        assert restored.from_agent == original.from_agent
        assert restored.to_agent == original.to_agent
        assert restored.knowledge == original.knowledge
        assert restored.priority == original.priority
        assert restored.reply_to == original.reply_to
        assert restored.metadata == original.metadata
        # Note: datetime comparison might need tolerance for microseconds


class TestReefChannel:
    """Test the ReefChannel message channel class."""
    
    def test_channel_creation(self):
        """Test basic channel creation."""
        channel = ReefChannel("test-channel", max_capacity=100)
        
        assert channel.name == "test-channel"
        assert channel.max_capacity == 100
        assert len(channel.spores) == 0
        assert len(channel.subscribers) == 0
    
    def test_send_spore_to_channel(self):
        """Test sending a spore to a channel."""
        channel = ReefChannel("test")
        
        spore = Spore(
            id="test-spore",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"data": "test"},
            created_at=datetime.now()
        )
        
        result = channel.send_spore(spore)
        assert result is True
        assert len(channel.spores) == 1
        assert channel.stats["spores_carried"] == 1
    
    def test_channel_capacity_limit(self):
        """Test that channel respects max capacity."""
        channel = ReefChannel("limited", max_capacity=2)
        
        # Send 3 spores to a capacity-2 channel
        for i in range(3):
            spore = Spore(
                id=f"spore-{i}",
                spore_type=SporeType.KNOWLEDGE,
                from_agent="sender",
                to_agent="receiver",
                knowledge={"index": i},
                created_at=datetime.now()
            )
            channel.send_spore(spore)
        
        # Should only have 2 spores (oldest dropped)
        assert len(channel.spores) == 2
        assert channel.stats["spores_carried"] == 3
        # First spore should be dropped, should have spores 1 and 2
        spore_ids = [s.id for s in channel.spores]
        assert "spore-1" in spore_ids
        assert "spore-2" in spore_ids
        assert "spore-0" not in spore_ids
    
    def test_subscribe_and_delivery(self):
        """Test subscribing to channel and receiving spores."""
        channel = ReefChannel("delivery-test")
        received_spores = []
        
        def handler(spore: Spore) -> None:
            received_spores.append(spore)
        
        # Subscribe agent to channel
        channel.subscribe("receiver", handler)
        assert "receiver" in channel.subscribers
        
        # Send targeted spore
        spore = Spore(
            id="targeted",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"message": "direct"},
            created_at=datetime.now()
        )
        
        channel.send_spore(spore)
        
        # Handler should have been called
        assert len(received_spores) == 1
        assert received_spores[0].id == "targeted"
        assert channel.stats["spores_delivered"] == 1
    
    def test_broadcast_delivery(self):
        """Test broadcast spore delivery to all subscribers."""
        channel = ReefChannel("broadcast-test")
        
        # Multiple subscribers
        received_by_agent1 = []
        received_by_agent2 = []
        
        channel.subscribe("agent1", lambda s: received_by_agent1.append(s))
        channel.subscribe("agent2", lambda s: received_by_agent2.append(s))
        
        # Send broadcast spore
        broadcast_spore = Spore(
            id="broadcast",
            spore_type=SporeType.BROADCAST,
            from_agent="broadcaster",
            to_agent=None,  # Broadcast has no specific target
            knowledge={"announcement": "important news"},
            created_at=datetime.now()
        )
        
        channel.send_spore(broadcast_spore)
        
        # Both agents should receive (but not the sender)
        assert len(received_by_agent1) == 1
        assert len(received_by_agent2) == 1
        assert received_by_agent1[0].id == "broadcast"
        assert received_by_agent2[0].id == "broadcast"
    
    def test_get_spores_for_agent(self):
        """Test retrieving spores for a specific agent."""
        channel = ReefChannel("retrieval-test")
        
        # Send multiple spores
        spores_data = [
            ("targeted", "agent1", SporeType.KNOWLEDGE),
            ("broadcast", None, SporeType.BROADCAST),
            ("other", "agent2", SporeType.KNOWLEDGE),
            ("another-targeted", "agent1", SporeType.REQUEST)
        ]
        
        for spore_id, to_agent, spore_type in spores_data:
            spore = Spore(
                id=spore_id,
                spore_type=spore_type,
                from_agent="sender",
                to_agent=to_agent,
                knowledge={"test": spore_id},
                created_at=datetime.now()
            )
            channel.send_spore(spore)
        
        # Get spores for agent1
        agent1_spores = channel.get_spores_for_agent("agent1", limit=10)
        
        # Should get targeted spores and broadcasts (but not other agent's spores)
        assert len(agent1_spores) == 3  # 2 targeted + 1 broadcast
        spore_ids = [s.id for s in agent1_spores]
        assert "targeted" in spore_ids
        assert "broadcast" in spore_ids
        assert "another-targeted" in spore_ids
        assert "other" not in spore_ids
    
    def test_cleanup_expired_spores(self):
        """Test cleanup of expired spores."""
        channel = ReefChannel("cleanup-test")
        
        # Send mix of expired and valid spores
        expired_spore = Spore(
            id="expired",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"old": "data"},
            created_at=datetime.now() - timedelta(hours=2),
            expires_at=datetime.now() - timedelta(hours=1)
        )
        
        valid_spore = Spore(
            id="valid",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"fresh": "data"},
            created_at=datetime.now()
        )
        
        channel.send_spore(expired_spore)
        channel.send_spore(valid_spore)
        
        assert len(channel.spores) == 2
        
        # Cleanup expired
        expired_count = channel.cleanup_expired()
        
        assert expired_count == 1
        assert len(channel.spores) == 1
        assert channel.spores[0].id == "valid"
    
    def test_unsubscribe(self):
        """Test unsubscribing from channel."""
        channel = ReefChannel("unsubscribe-test")
        received_spores = []
        
        def handler(spore: Spore) -> None:
            received_spores.append(spore)
        
        # Subscribe and send spore
        channel.subscribe("agent1", handler)
        
        spore1 = Spore(
            id="spore1",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="agent1",
            knowledge={"test": 1},
            created_at=datetime.now()
        )
        channel.send_spore(spore1)
        assert len(received_spores) == 1
        
        # Unsubscribe and send another spore
        channel.unsubscribe("agent1")
        
        spore2 = Spore(
            id="spore2",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="agent1",
            knowledge={"test": 2},
            created_at=datetime.now()
        )
        channel.send_spore(spore2)
        
        # Should not receive second spore
        assert len(received_spores) == 1
        assert "agent1" not in channel.subscribers


class TestReef:
    """Test the main Reef communication system."""
    
    def test_reef_creation(self):
        """Test basic reef creation."""
        reef = Reef()
        
        # Should have default main channel
        assert "main" in reef.channels
        assert isinstance(reef.get_channel("main"), ReefChannel)
    
    def test_create_channel(self):
        """Test creating new channels."""
        reef = Reef()
        
        channel = reef.create_channel("research", max_capacity=500)
        
        assert channel.name == "research"
        assert channel.max_capacity == 500
        assert reef.get_channel("research") == channel
        
        # Creating existing channel should return same instance
        same_channel = reef.create_channel("research")
        assert same_channel == channel
    
    def test_send_knowledge(self):
        """Test sending knowledge between agents."""
        reef = Reef()
        
        spore_id = reef.send(
            from_agent="researcher",
            to_agent="analyzer",
            knowledge={
                "discovery": "new algorithm",
                "performance": 0.95,
                "verified": True
            }
        )
        
        assert isinstance(spore_id, str)
        assert len(spore_id) > 0
        
        # Check spore exists in main channel
        main_channel = reef.get_channel("main")
        assert len(main_channel.spores) == 1
        
        sent_spore = main_channel.spores[0]
        assert sent_spore.from_agent == "researcher"
        assert sent_spore.to_agent == "analyzer"
        assert sent_spore.spore_type == SporeType.KNOWLEDGE
        assert sent_spore.knowledge["discovery"] == "new algorithm"
    
    def test_broadcast_knowledge(self):
        """Test broadcasting knowledge to all agents."""
        reef = Reef()
        
        spore_id = reef.broadcast(
            from_agent="news_agent",
            knowledge={
                "breaking": "major breakthrough",
                "impact": "significant",
                "urgency": "high"
            }
        )
        
        # Check broadcast spore
        main_channel = reef.get_channel("main")
        broadcast_spore = main_channel.spores[0]
        
        assert broadcast_spore.spore_type == SporeType.BROADCAST
        assert broadcast_spore.to_agent is None
        assert broadcast_spore.knowledge["breaking"] == "major breakthrough"
    
    def test_request_and_reply(self):
        """Test request-response pattern."""
        reef = Reef()
        
        # Send request
        request_id = reef.request(
            from_agent="client",
            to_agent="service", 
            request={
                "query": "calculate_fibonacci",
                "params": {"n": 10}
            },
            expires_in_seconds=60
        )
        
        # Send reply
        reply_id = reef.reply(
            from_agent="service",
            to_agent="client",
            response={
                "result": 55,
                "computation_time": 0.001
            },
            reply_to_spore_id=request_id
        )
        
        main_channel = reef.get_channel("main")
        assert len(main_channel.spores) == 2
        
        # Check request spore
        request_spore = main_channel.spores[0]
        assert request_spore.spore_type == SporeType.REQUEST
        assert request_spore.knowledge["query"] == "calculate_fibonacci"
        assert request_spore.expires_at is not None
        
        # Check reply spore
        reply_spore = main_channel.spores[1]
        assert reply_spore.spore_type == SporeType.RESPONSE
        assert reply_spore.reply_to == request_id
        assert reply_spore.knowledge["result"] == 55
    
    def test_subscribe_to_reef(self):
        """Test subscribing agents to the reef."""
        reef = Reef()
        received_messages = []
        
        def message_handler(spore: Spore) -> None:
            received_messages.append(spore.knowledge)
        
        # Subscribe agent to main channel
        reef.subscribe("listener", message_handler)
        
        # Send message
        reef.send(
            from_agent="speaker",
            to_agent="listener",
            knowledge={"message": "hello listener"}
        )
        
        assert len(received_messages) == 1
        assert received_messages[0]["message"] == "hello listener"
    
    def test_multi_channel_communication(self):
        """Test communication across multiple channels."""
        reef = Reef()
        
        # Create specialized channels
        reef.create_channel("alerts")
        reef.create_channel("research")
        
        # Send to different channels
        alert_id = reef.send(
            from_agent="monitor",
            to_agent="admin",
            knowledge={"alert": "system overload"},
            channel="alerts"
        )
        
        research_id = reef.send(
            from_agent="scientist",
            to_agent="peer", 
            knowledge={"finding": "interesting pattern"},
            channel="research"
        )
        
        # Check messages went to correct channels
        alerts_channel = reef.get_channel("alerts")
        research_channel = reef.get_channel("research")
        main_channel = reef.get_channel("main")
        
        assert len(alerts_channel.spores) == 1
        assert len(research_channel.spores) == 1
        assert len(main_channel.spores) == 0  # Nothing sent to main
        
        assert alerts_channel.spores[0].knowledge["alert"] == "system overload"
        assert research_channel.spores[0].knowledge["finding"] == "interesting pattern"
    
    def test_get_reef_stats(self):
        """Test getting reef network statistics."""
        reef = Reef()
        
        # Create some activity
        reef.create_channel("test1")
        reef.create_channel("test2", max_capacity=50)
        
        reef.send("agent1", "agent2", {"test": "data"})
        reef.broadcast("agent1", {"news": "update"})
        
        stats = reef.get_network_stats()
        
        assert stats["total_channels"] == 3  # main + test1 + test2
        assert "main" in stats["channel_stats"]
        assert "test1" in stats["channel_stats"]
        assert "test2" in stats["channel_stats"]
        
        main_stats = stats["channel_stats"]["main"]
        assert main_stats["active_spores"] == 2
        assert main_stats["spores_carried"] == 2


class TestReefIntegration:
    """Integration tests for the reef system."""
    
    def test_global_reef_instance(self):
        """Test the global reef instance."""
        reef1 = get_reef()
        reef2 = get_reef()
        
        # Should be same instance
        assert reef1 is reef2
        
        # Should have main channel
        assert reef1.get_channel("main") is not None
    
    def test_concurrent_access(self):
        """Test thread-safe concurrent access to reef."""
        reef = Reef()
        results = {"sent": 0, "received": 0}
        received_spores = []
        
        def spore_handler(spore: Spore) -> None:
            received_spores.append(spore)
            results["received"] += 1
        
        reef.subscribe("receiver", spore_handler)
        
        def sender_thread():
            for i in range(10):
                reef.send(
                    from_agent="sender",
                    to_agent="receiver", 
                    knowledge={"index": i}
                )
                results["sent"] += 1
                time.sleep(0.01)  # Small delay to encourage race conditions
        
        # Start multiple sender threads
        threads = [threading.Thread(target=sender_thread) for _ in range(3)]
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # All messages should be sent and received
        assert results["sent"] == 30
        assert results["received"] == 30
        assert len(received_spores) == 30
    
    def test_error_handling_in_handlers(self):
        """Test that errors in message handlers don't break the system."""
        reef = Reef()
        good_messages = []
        
        def failing_handler(spore: Spore) -> None:
            raise ValueError("Handler intentionally failed")
        
        def good_handler(spore: Spore) -> None:
            good_messages.append(spore.knowledge)
        
        # Subscribe both handlers
        reef.subscribe("bad_agent", failing_handler)
        reef.subscribe("good_agent", good_handler)
        
        # Send broadcast (should trigger both handlers)
        reef.broadcast(
            from_agent="sender",
            knowledge={"test": "error handling"}
        )
        
        # Good handler should still work despite failing handler
        assert len(good_messages) == 1
        assert good_messages[0]["test"] == "error handling"
    
    def test_performance_with_many_spores(self):
        """Test performance with many spores."""
        reef = Reef()
        
        # Send many spores quickly
        start_time = time.time()
        for i in range(1000):
            reef.send(
                from_agent="sender",
                to_agent="receiver",
                knowledge={"index": i}
            )
        end_time = time.time()
        
        # Should complete in reasonable time (< 1 second)
        duration = end_time - start_time
        assert duration < 1.0
        
        # All spores should be in the channel
        main_channel = reef.get_channel("main")
        assert len(main_channel.spores) == 1000


# Fixtures for test setup
@pytest.fixture
def sample_spore():
    """Create a sample spore for testing."""
    return Spore(
        id="test-spore-123",
        spore_type=SporeType.KNOWLEDGE,
        from_agent="test_sender",
        to_agent="test_receiver",
        knowledge={"test_data": "sample knowledge"},
        created_at=datetime.now()
    )


@pytest.fixture
def reef_with_channels():
    """Create a reef with multiple channels for testing."""
    reef = Reef()
    reef.create_channel("alerts", max_capacity=100)
    reef.create_channel("research", max_capacity=500)
    reef.create_channel("social", max_capacity=200)
    return reef