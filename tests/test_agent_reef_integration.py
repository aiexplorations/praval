"""
Tests for Agent integration with the Reef communication system.

These tests verify that agents can seamlessly communicate through the reef
while maintaining backward compatibility with existing functionality.
"""

import pytest
import time
from datetime import datetime
from unittest.mock import Mock, patch
from typing import Dict, Any, List, Optional

from praval import Agent, register_agent, get_registry
from praval.core.reef import Spore, SporeType, get_reef


class TestAgentReefIntegration:
    """Test integration between Agent class and Reef system."""
    
    def test_agent_has_reef_methods(self):
        """Test that Agent class has reef communication methods."""
        agent = Agent("test_agent")
        
        # Check that reef methods exist
        assert hasattr(agent, 'send_knowledge')
        assert hasattr(agent, 'broadcast_knowledge')  
        assert hasattr(agent, 'request_knowledge')
        assert hasattr(agent, 'on_spore_received')
        assert hasattr(agent, 'subscribe_to_channel')
        assert hasattr(agent, 'unsubscribe_from_channel')
    
    def test_agent_send_knowledge(self):
        """Test agent sending knowledge to another agent."""
        sender = Agent("sender")
        receiver = Agent("receiver")
        
        # Mock the receiver's spore handler to capture received messages
        received_spores = []
        def mock_handler(spore: Spore) -> None:
            received_spores.append(spore)
        
        # Register agents and subscribe receiver
        register_agent(sender)
        register_agent(receiver)
        receiver.subscribe_to_channel("main")
        
        # Patch the receiver's handler
        with patch.object(receiver, 'on_spore_received', side_effect=mock_handler):
            # Send knowledge
            spore_id = sender.send_knowledge(
                to_agent="receiver",
                knowledge={
                    "research_topic": "quantum computing",
                    "findings": ["coherence_improved", "error_rates_reduced"],
                    "confidence": 0.89
                }
            )
            
            assert isinstance(spore_id, str)
            assert len(spore_id) > 0
            
            # Verify spore was received
            assert len(received_spores) == 1
            received_spore = received_spores[0]
            
            assert received_spore.from_agent == "sender"
            assert received_spore.to_agent == "receiver"
            assert received_spore.spore_type == SporeType.KNOWLEDGE
            assert received_spore.knowledge["research_topic"] == "quantum computing"
            assert received_spore.knowledge["confidence"] == 0.89
    
    def test_agent_broadcast_knowledge(self):
        """Test agent broadcasting knowledge to all agents."""
        broadcaster = Agent("broadcaster")
        listener1 = Agent("listener1")
        listener2 = Agent("listener2")
        
        # Track received broadcasts
        listener1_received = []
        listener2_received = []
        
        def listener1_handler(spore: Spore) -> None:
            if spore.spore_type == SporeType.BROADCAST:
                listener1_received.append(spore)
        
        def listener2_handler(spore: Spore) -> None:
            if spore.spore_type == SporeType.BROADCAST:
                listener2_received.append(spore)
        
        # Register and subscribe agents
        register_agent(broadcaster)
        register_agent(listener1)
        register_agent(listener2)
        
        listener1.subscribe_to_channel("main")
        listener2.subscribe_to_channel("main")
        
        with patch.object(listener1, 'on_spore_received', side_effect=listener1_handler), \
             patch.object(listener2, 'on_spore_received', side_effect=listener2_handler):
            
            # Broadcast knowledge
            spore_id = broadcaster.broadcast_knowledge({
                "announcement": "system_upgrade_complete",
                "new_features": ["faster_processing", "better_accuracy"],
                "downtime": "none"
            })
            
            # Both listeners should receive the broadcast
            assert len(listener1_received) == 1
            assert len(listener2_received) == 1
            
            # Verify broadcast content
            broadcast1 = listener1_received[0]
            broadcast2 = listener2_received[0]
            
            assert broadcast1.id == broadcast2.id == spore_id
            assert broadcast1.from_agent == "broadcaster"
            assert broadcast1.to_agent is None  # Broadcasts have no specific target
            assert broadcast1.knowledge["announcement"] == "system_upgrade_complete"
    
    def test_agent_request_knowledge(self):
        """Test agent requesting knowledge from another agent."""
        requester = Agent("requester")
        responder = Agent("responder")
        
        # Mock responder to automatically reply to requests
        def auto_responder(spore: Spore) -> None:
            if spore.spore_type == SporeType.REQUEST and spore.to_agent == "responder":
                # Simulate processing the request
                if spore.knowledge.get("query") == "get_weather":
                    response_data = {
                        "temperature": 22,
                        "condition": "sunny",
                        "humidity": 65
                    }
                    
                    # Send response back
                    get_reef().reply(
                        from_agent="responder",
                        to_agent=spore.from_agent,
                        response=response_data,
                        reply_to_spore_id=spore.id
                    )
        
        register_agent(requester)
        register_agent(responder)
        responder.subscribe_to_channel("main")
        
        with patch.object(responder, 'on_spore_received', side_effect=auto_responder):
            # Request knowledge with timeout
            response = requester.request_knowledge(
                from_agent="responder",
                request={
                    "query": "get_weather",
                    "location": "san_francisco"
                },
                timeout=5
            )
            
            # Should receive response
            assert response is not None
            assert response["temperature"] == 22
            assert response["condition"] == "sunny"
    
    def test_agent_request_timeout(self):
        """Test agent request timeout when no response."""
        requester = Agent("requester")
        silent_agent = Agent("silent")
        
        register_agent(requester)
        register_agent(silent_agent)
        
        # Request from silent agent (no response expected)
        response = requester.request_knowledge(
            from_agent="silent",
            request={"query": "will_not_respond"},
            timeout=1  # Short timeout
        )
        
        # Should timeout and return None
        assert response is None
    
    def test_agent_channel_subscription(self):
        """Test agent subscribing to different channels."""
        agent = Agent("multi_channel_agent")
        register_agent(agent)
        
        # Subscribe to multiple channels
        agent.subscribe_to_channel("research")
        agent.subscribe_to_channel("alerts")
        agent.subscribe_to_channel("social")
        
        received_messages = []
        def message_collector(spore: Spore) -> None:
            received_messages.append((spore.knowledge, spore.metadata.get("channel")))
        
        with patch.object(agent, 'on_spore_received', side_effect=message_collector):
            reef = get_reef()
            
            # Send messages to different channels
            reef.send(
                from_agent="researcher",
                to_agent="multi_channel_agent",
                knowledge={"paper": "quantum_algorithms"},
                channel="research"
            )
            
            reef.send(
                from_agent="monitor",
                to_agent="multi_channel_agent", 
                knowledge={"alert": "cpu_high"},
                channel="alerts"
            )
            
            reef.send(
                from_agent="friend",
                to_agent="multi_channel_agent",
                knowledge={"message": "hello"},
                channel="social"
            )
            
            # Agent should receive all messages
            assert len(received_messages) == 3
            
            # Verify messages from different channels
            knowledge_items = [msg[0] for msg in received_messages]
            assert {"paper": "quantum_algorithms"} in knowledge_items
            assert {"alert": "cpu_high"} in knowledge_items
            assert {"message": "hello"} in knowledge_items
    
    def test_agent_unsubscribe_from_channel(self):
        """Test agent unsubscribing from channels."""
        agent = Agent("subscriber")
        register_agent(agent)
        
        received_count = 0
        def counter(spore: Spore) -> None:
            nonlocal received_count
            received_count += 1
        
        # Subscribe to channel
        agent.subscribe_to_channel("test_channel")
        
        with patch.object(agent, 'on_spore_received', side_effect=counter):
            reef = get_reef()
            
            # Send message while subscribed
            reef.send(
                from_agent="sender",
                to_agent="subscriber",
                knowledge={"test": "message1"},
                channel="test_channel"
            )
            
            assert received_count == 1
            
            # Unsubscribe
            agent.unsubscribe_from_channel("test_channel")
            
            # Send another message
            reef.send(
                from_agent="sender", 
                to_agent="subscriber",
                knowledge={"test": "message2"},
                channel="test_channel"
            )
            
            # Should not receive second message
            assert received_count == 1
    
    def test_agent_custom_spore_handler(self):
        """Test agent with custom spore handling logic."""
        class SmartAgent(Agent):
            def __init__(self, name: str):
                super().__init__(name)
                self.knowledge_base = {}
                self.pending_requests = {}
            
            def on_spore_received(self, spore: Spore) -> None:
                """Custom spore handling with knowledge base updates."""
                if spore.spore_type == SporeType.KNOWLEDGE:
                    # Store knowledge in base
                    topic = spore.knowledge.get("topic")
                    if topic:
                        self.knowledge_base[topic] = spore.knowledge
                
                elif spore.spore_type == SporeType.REQUEST:
                    # Auto-respond to knowledge requests
                    requested_topic = spore.knowledge.get("topic")
                    if requested_topic in self.knowledge_base:
                        get_reef().reply(
                            from_agent=self.name,
                            to_agent=spore.from_agent,
                            response=self.knowledge_base[requested_topic],
                            reply_to_spore_id=spore.id
                        )
                
                elif spore.spore_type == SporeType.RESPONSE:
                    # Handle responses to our requests
                    if spore.reply_to in self.pending_requests:
                        callback = self.pending_requests.pop(spore.reply_to)
                        if callback:
                            callback(spore.knowledge)
        
        smart_agent = SmartAgent("smart_agent")
        register_agent(smart_agent)
        smart_agent.subscribe_to_channel("main")
        
        # Send knowledge to build knowledge base
        reef = get_reef()
        reef.send(
            from_agent="teacher",
            to_agent="smart_agent",
            knowledge={
                "topic": "machine_learning",
                "definition": "AI technique for pattern recognition",
                "applications": ["nlp", "computer_vision"]
            }
        )
        
        # Verify knowledge was stored
        assert "machine_learning" in smart_agent.knowledge_base
        assert smart_agent.knowledge_base["machine_learning"]["definition"] == "AI technique for pattern recognition"
        
        # Request the knowledge back
        response_received = []
        def response_handler(spore: Spore) -> None:
            if spore.spore_type == SporeType.RESPONSE:
                response_received.append(spore.knowledge)
        
        requester = Agent("requester")
        register_agent(requester)
        requester.subscribe_to_channel("main")
        
        with patch.object(requester, 'on_spore_received', side_effect=response_handler):
            request_id = reef.request(
                from_agent="requester",
                to_agent="smart_agent",
                request={"topic": "machine_learning"}
            )
            
            # Should get automatic response
            time.sleep(0.1)  # Small delay for processing
            assert len(response_received) == 1
            assert response_received[0]["definition"] == "AI technique for pattern recognition"


class TestAgentReefCompatibility:
    """Test backward compatibility and integration with existing Agent features."""
    
    def test_existing_agent_functionality_preserved(self):
        """Test that existing agent functionality still works with reef integration."""
        agent = Agent("test_agent", system_message="You are a helpful assistant")
        
        # Existing functionality should still work
        assert agent.name == "test_agent"
        assert agent.config.system_message == "You are a helpful assistant"
        assert len(agent.conversation_history) == 1  # System message
        assert agent.tools == {}
        
        # Should be able to add tools
        @agent.tool
        def calculate(x: int, y: int) -> int:
            """Add two numbers."""
            return x + y
        
        assert "calculate" in agent.tools
        
        # Chat functionality should work (would need actual LLM for full test)
        # This tests the method exists and basic validation
        with pytest.raises(ValueError, match="Message cannot be empty"):
            agent.chat("")
    
    def test_agent_registry_with_reef(self):
        """Test that agent registry works with reef communication."""
        # Create and register agents
        agent1 = Agent("registry_agent1")
        agent2 = Agent("registry_agent2")
        
        register_agent(agent1)
        register_agent(agent2)
        
        # Should be able to discover agents through registry
        registry = get_registry()
        assert "registry_agent1" in registry.list_agents()
        assert "registry_agent2" in registry.list_agents()
        
        # Should be able to get agents and use reef communication
        retrieved_agent1 = registry.get_agent("registry_agent1")
        assert retrieved_agent1 is agent1
        
        # Test reef communication between registered agents
        received_messages = []
        def message_handler(spore: Spore) -> None:
            received_messages.append(spore.knowledge)
        
        agent2.subscribe_to_channel("main")
        
        with patch.object(agent2, 'on_spore_received', side_effect=message_handler):
            agent1.send_knowledge(
                to_agent="registry_agent2",
                knowledge={"registry_test": "communication_works"}
            )
            
            assert len(received_messages) == 1
            assert received_messages[0]["registry_test"] == "communication_works"
    
    def test_agent_tools_with_reef_communication(self):
        """Test that agent tools can use reef communication."""
        calculator_agent = Agent("calculator")
        
        @calculator_agent.tool
        def complex_calculation(operation: str, numbers: List[int]) -> Dict[str, Any]:
            """Perform complex calculations and broadcast results."""
            if operation == "sum":
                result = sum(numbers)
            elif operation == "product":
                result = 1
                for n in numbers:
                    result *= n
            else:
                result = None
            
            # Broadcast calculation result
            if result is not None:
                calculator_agent.broadcast_knowledge({
                    "calculation_completed": True,
                    "operation": operation,
                    "input": numbers,
                    "result": result,
                    "agent": "calculator"
                })
            
            return {"result": result, "broadcasted": result is not None}
        
        register_agent(calculator_agent)
        
        # Set up listener for broadcasts
        listener_agent = Agent("listener")
        register_agent(listener_agent)
        listener_agent.subscribe_to_channel("main")
        
        received_broadcasts = []
        def broadcast_listener(spore: Spore) -> None:
            if spore.spore_type == SporeType.BROADCAST:
                received_broadcasts.append(spore.knowledge)
        
        with patch.object(listener_agent, 'on_spore_received', side_effect=broadcast_listener):
            # Use tool that broadcasts
            tool_func = calculator_agent.tools["complex_calculation"]["function"]
            result = tool_func("sum", [1, 2, 3, 4, 5])
            
            assert result["result"] == 15
            assert result["broadcasted"] is True
            
            # Verify broadcast was sent
            assert len(received_broadcasts) == 1
            broadcast = received_broadcasts[0]
            assert broadcast["calculation_completed"] is True
            assert broadcast["operation"] == "sum"
            assert broadcast["result"] == 15


# Fixtures for Agent + Reef integration tests
@pytest.fixture
def connected_agents():
    """Create a set of connected agents for testing."""
    agents = {}
    
    for name in ["alice", "bob", "charlie"]:
        agent = Agent(name)
        register_agent(agent)
        agent.subscribe_to_channel("main")
        agents[name] = agent
    
    return agents


@pytest.fixture  
def multi_channel_setup():
    """Set up multiple channels with subscribed agents."""
    reef = get_reef()
    
    # Create channels
    reef.create_channel("research")
    reef.create_channel("alerts") 
    reef.create_channel("social")
    
    # Create agents with different subscriptions
    researcher = Agent("researcher")
    register_agent(researcher)
    researcher.subscribe_to_channel("research")
    researcher.subscribe_to_channel("main")
    
    admin = Agent("admin")
    register_agent(admin)
    admin.subscribe_to_channel("alerts")
    admin.subscribe_to_channel("main")
    
    social_agent = Agent("social_agent")
    register_agent(social_agent)
    social_agent.subscribe_to_channel("social")
    social_agent.subscribe_to_channel("main")
    
    return {
        "reef": reef,
        "researcher": researcher,
        "admin": admin, 
        "social_agent": social_agent
    }