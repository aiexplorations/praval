"""
Tests for self-organizing agent behavior.

Following TDD principles, these tests define the expected behavior
for agents that autonomously coordinate through reef communication.
"""

import pytest
import time
import threading
import asyncio
import os
from unittest.mock import Mock, patch
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from praval import Agent, register_agent, get_registry, get_reef, agent, chat, achat, broadcast, start_agents
from praval.core.reef import SporeType


@pytest.fixture(autouse=True)
def mock_llm_provider():
    """Mock LLM provider for testing."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        yield


class TestSystemLevelReefBroadcasting:
    """Test system-level broadcasting to all agents."""
    
    def test_reef_system_broadcast(self):
        """Test that reef can broadcast system messages."""
        reef = get_reef()
        reef.create_channel("test_channel")
        
        # Should be able to broadcast from system
        message_id = reef.system_broadcast(
            knowledge={"type": "system_start", "goal": "test"},
            channel="test_channel"
        )
        
        assert message_id is not None
        assert isinstance(message_id, str)
    
    def test_agents_receive_system_broadcasts(self):
        """Test that agents receive system broadcasts."""
        reef = get_reef()
        reef.create_channel("coordination")
        
        # Create agent with custom handler
        received_messages = []
        
        def capture_handler(spore):
            received_messages.append(spore.knowledge)
        
        agent = Agent("test_agent", system_message="Test agent")
        agent.subscribe_to_channel("coordination")
        agent.set_spore_handler(capture_handler)
        
        # System broadcasts a message
        reef.system_broadcast(
            knowledge={"type": "mission_start", "target": "test"},
            channel="coordination"
        )
        
        # Give a moment for async processing
        time.sleep(0.1)
        
        assert len(received_messages) == 1
        assert received_messages[0]["type"] == "mission_start"
        assert received_messages[0]["target"] == "test"


class TestAgentSporeHandlerOverrides:
    """Test custom spore handler functionality."""
    
    def test_agent_custom_spore_handler(self):
        """Test that agents can override spore handling behavior."""
        reef = get_reef()
        reef.create_channel("test_channel")
        
        # Create agent with custom handler
        handled_spores = []
        
        def custom_handler(spore):
            handled_spores.append({
                "type": spore.spore_type,
                "from": spore.from_agent,
                "knowledge": spore.knowledge
            })
        
        agent = Agent("handler_agent", system_message="Test")
        agent.subscribe_to_channel("test_channel")
        agent.set_spore_handler(custom_handler)
        
        # Send a message to the agent
        reef.send(
            from_agent="sender",
            to_agent="handler_agent",
            knowledge={"message": "hello"},
            channel="test_channel"
        )
        
        time.sleep(0.1)  # Allow processing
        
        assert len(handled_spores) == 1
        assert handled_spores[0]["from"] == "sender"
        assert handled_spores[0]["knowledge"]["message"] == "hello"
    
    def test_agent_autonomous_behavior_activation(self):
        """Test that agents can start autonomous behavior from broadcasts."""
        reef = get_reef()
        reef.create_channel("activation")
        
        # Create agent that activates on specific broadcast
        autonomous_started = threading.Event()
        
        def autonomous_behavior():
            autonomous_started.set()
        
        def activation_handler(spore):
            if (spore.spore_type == SporeType.BROADCAST and 
                spore.knowledge.get("type") == "start_autonomous"):
                threading.Thread(target=autonomous_behavior, daemon=True).start()
        
        agent = Agent("autonomous_agent", system_message="Test")
        agent.subscribe_to_channel("activation")
        agent.set_spore_handler(activation_handler)
        
        # Broadcast activation message
        reef.system_broadcast(
            knowledge={"type": "start_autonomous", "goal": "explore"},
            channel="activation"
        )
        
        # Wait for autonomous behavior to start
        assert autonomous_started.wait(timeout=1.0)


class TestAgentCoordination:
    """Test autonomous agent coordination patterns."""
    
    def test_agents_coordinate_through_broadcasts(self):
        """Test that agents coordinate work through broadcast messages."""
        reef = get_reef()
        reef.create_channel("coordination")
        
        # Track coordination events
        coordination_events = []
        
        # Explorer agent - discovers and broadcasts findings
        def explorer_handler(spore):
            if (spore.spore_type == SporeType.BROADCAST and 
                spore.knowledge.get("type") == "start_exploration"):
                
                # Simulate discovery
                coordination_events.append("explorer_discovered")
                
                # Broadcast discovery
                explorer.broadcast_knowledge({
                    "type": "discovery_made",
                    "item": "test_concept",
                    "discoverer": "explorer"
                }, channel="coordination")
        
        # Processor agent - processes discoveries
        def processor_handler(spore):
            if (spore.spore_type == SporeType.BROADCAST and 
                spore.knowledge.get("type") == "discovery_made"):
                
                coordination_events.append("processor_activated")
                
                # Broadcast processing complete
                processor.broadcast_knowledge({
                    "type": "processing_complete",
                    "item": spore.knowledge.get("item"),
                    "processor": "processor"
                }, channel="coordination")
        
        explorer = Agent("explorer", system_message="Explorer agent")
        processor = Agent("processor", system_message="Processor agent")
        
        explorer.subscribe_to_channel("coordination")
        processor.subscribe_to_channel("coordination")
        
        explorer.set_spore_handler(explorer_handler)
        processor.set_spore_handler(processor_handler)
        
        # Start coordination
        reef.system_broadcast(
            knowledge={"type": "start_exploration", "target": "concepts"},
            channel="coordination"
        )
        
        # Allow coordination to happen
        time.sleep(0.2)
        
        assert "explorer_discovered" in coordination_events
        assert "processor_activated" in coordination_events
    
    def test_agents_self_organize_workload(self):
        """Test that agents can self-organize work distribution."""
        reef = get_reef()
        reef.create_channel("workload")
        
        work_assignments = []
        
        def create_worker_handler(worker_id, capacity):
            def handler(spore):
                if (spore.spore_type == SporeType.BROADCAST and 
                    spore.knowledge.get("type") == "work_available"):
                    
                    # Bid for work based on capacity
                    if len(work_assignments) < capacity:
                        work_assignments.append(f"worker_{worker_id}")
                        
                        # Announce work claimed
                        agent = get_registry().get_agent(f"worker_{worker_id}")
                        agent.broadcast_knowledge({
                            "type": "work_claimed",
                            "worker": f"worker_{worker_id}",
                            "task": spore.knowledge.get("task_id")
                        }, channel="workload")
            
            return handler
        
        # Create workers with different capacities
        worker1 = Agent("worker_1", system_message="Worker 1")
        worker2 = Agent("worker_2", system_message="Worker 2")
        
        register_agent(worker1)
        register_agent(worker2)
        
        worker1.subscribe_to_channel("workload")
        worker2.subscribe_to_channel("workload")
        
        worker1.set_spore_handler(create_worker_handler(1, capacity=2))
        worker2.set_spore_handler(create_worker_handler(2, capacity=1))
        
        # Broadcast work availability
        for i in range(3):
            reef.system_broadcast(
                knowledge={"type": "work_available", "task_id": f"task_{i}"},
                channel="workload"
            )
            time.sleep(0.05)  # Small delay between tasks
        
        time.sleep(0.2)  # Allow work distribution
        
        # Work should be distributed based on capacity
        assert len(work_assignments) >= 2  # At least some work was claimed
        assert "worker_1" in work_assignments or "worker_2" in work_assignments


class TestEmergentBehavior:
    """Test emergent behaviors from simple agent interactions."""
    
    def test_knowledge_graph_emergence(self):
        """Test that knowledge graph structure emerges from agent interactions."""
        reef = get_reef()
        reef.create_channel("knowledge")
        
        # Shared knowledge state
        knowledge_graph = {"nodes": set(), "edges": []}
        
        # Concept discoverer
        def discoverer_handler(spore):
            if (spore.spore_type == SporeType.BROADCAST and 
                spore.knowledge.get("type") == "explore_concept"):
                
                concept = spore.knowledge.get("concept")
                # Simulate concept discovery
                new_concepts = [f"{concept}_related_1", f"{concept}_related_2"]
                
                for new_concept in new_concepts:
                    knowledge_graph["nodes"].add(new_concept)
                
                # Broadcast discovery
                discoverer.broadcast_knowledge({
                    "type": "concepts_discovered",
                    "source": concept,
                    "concepts": new_concepts
                }, channel="knowledge")
        
        # Relationship finder
        def relationship_handler(spore):
            if (spore.spore_type == SporeType.BROADCAST and 
                spore.knowledge.get("type") == "concepts_discovered"):
                
                source = spore.knowledge.get("source")
                concepts = spore.knowledge.get("concepts", [])
                
                # Create relationships
                for concept in concepts:
                    knowledge_graph["edges"].append({
                        "from": source,
                        "to": concept,
                        "type": "related_to"
                    })
                
                # Broadcast relationships
                relationship_finder.broadcast_knowledge({
                    "type": "relationships_created",
                    "count": len(concepts)
                }, channel="knowledge")
        
        discoverer = Agent("discoverer", system_message="Discovers concepts")
        relationship_finder = Agent("relationship_finder", system_message="Finds relationships")
        
        discoverer.subscribe_to_channel("knowledge")
        relationship_finder.subscribe_to_channel("knowledge")
        
        discoverer.set_spore_handler(discoverer_handler)
        relationship_finder.set_spore_handler(relationship_handler)
        
        # Start knowledge graph construction
        reef.system_broadcast(
            knowledge={"type": "explore_concept", "concept": "AI"},
            channel="knowledge"
        )
        
        time.sleep(0.2)  # Allow emergence
        
        # Verify emergent structure
        assert len(knowledge_graph["nodes"]) >= 2
        assert len(knowledge_graph["edges"]) >= 2
        assert any(edge["from"] == "AI" for edge in knowledge_graph["edges"])


class TestPravalSimplicityPrinciples:
    """Test that self-organization maintains Praval's simplicity principles."""
    
    def test_simple_agent_creation(self):
        """Test that self-organizing agents are still simple to create."""
        # Should be able to create agents in 3-5 lines
        agent = Agent("simple", system_message="I am simple")
        agent.subscribe_to_channel("test")
        
        handled_messages = []
        agent.set_spore_handler(lambda spore: handled_messages.append(spore))
        
        assert agent.name == "simple"
        assert len(handled_messages) == 0
    
    def test_no_complex_inheritance_required(self):
        """Test that agents don't require complex inheritance for self-organization."""
        # Standard Agent class should be sufficient
        agent = Agent("autonomous", system_message="I work autonomously")
        
        # Should be able to add autonomous behavior with simple functions
        behavior_activated = threading.Event()
        
        def simple_handler(spore):
            if spore.knowledge.get("activate"):
                behavior_activated.set()
        
        agent.set_spore_handler(simple_handler)
        agent.subscribe_to_channel("simple_test")
        
        # Trigger behavior
        reef = get_reef()
        reef.create_channel("simple_test")
        reef.system_broadcast(
            knowledge={"activate": True},
            channel="simple_test"
        )
        
        assert behavior_activated.wait(timeout=0.5)
    
    def test_composable_behaviors(self):
        """Test that agent behaviors compose naturally."""
        reef = get_reef()
        reef.create_channel("composition")
        
        # Behaviors should compose without complex setup
        behaviors_executed = []
        
        def behavior_a(spore):
            if spore.knowledge.get("trigger") == "a":
                behaviors_executed.append("a")
        
        def behavior_b(spore):
            if spore.knowledge.get("trigger") == "b":
                behaviors_executed.append("b")
        
        def combined_handler(spore):
            behavior_a(spore)
            behavior_b(spore)
        
        agent = Agent("composed", system_message="I have composed behaviors")
        agent.subscribe_to_channel("composition")
        agent.set_spore_handler(combined_handler)
        
        # Test both behaviors
        reef.system_broadcast(knowledge={"trigger": "a"}, channel="composition")
        reef.system_broadcast(knowledge={"trigger": "b"}, channel="composition")
        
        time.sleep(0.1)
        
        assert "a" in behaviors_executed
        assert "b" in behaviors_executed


class TestAsyncAgentExecution:
    """Test async agent execution and concurrency."""
    
    def test_concurrent_agent_execution_faster(self):
        """Test that concurrent agents execute faster than sequential processing."""
        results = []
        
        @agent("performance_processor", channel="perf_test", responds_to=["perf_task"])
        def performance_agent(spore):
            task_id = spore.knowledge.get("task_id")
            start_time = time.time()
            
            # Mock LLM call with sleep - runs in parallel due to ThreadPool
            time.sleep(0.3)  # Simulate LLM processing time
            
            elapsed = time.time() - start_time
            results.append({"task_id": task_id, "elapsed": elapsed})
            return {"type": "perf_complete", "task_id": task_id}
        
        # Start agents
        start_agents(performance_agent, channel="perf_test")
        
        # Get reef for direct broadcasting 
        reef = get_reef()
        
        # Send 3 tasks simultaneously - they should run in parallel
        start_time = time.time()
        for i in range(3):
            reef.system_broadcast({
                "type": "perf_task", 
                "task_id": f"task_{i}"
            }, channel="perf_test")
        
        # Wait for completion
        time.sleep(1.0)  # Should complete in ~0.3s due to parallel execution
        total_time = time.time() - start_time
        
        # All 3 tasks should complete
        assert len(results) == 3
        
        # Total time should be close to single task time (not 3x) due to parallelism
        # With parallel execution: ~0.3s total vs sequential ~0.9s
        assert total_time < 0.8  # Much less than 3 * 0.3s if run sequentially
        
        # Each individual task should take roughly the expected time
        for result in results:
            assert 0.25 < result["elapsed"] < 0.4  # Around 0.3s +/- overhead
    
    def test_async_agent_with_achat(self):
        """Test async agent using achat function."""
        results = []
        
        @agent("async_processor", channel="async_test", responds_to=["async_task"])
        async def async_agent(spore):
            task_id = spore.knowledge.get("task_id")
            start_time = time.time()
            
            # Mock async LLM call
            await asyncio.sleep(0.2)  # Simulate async LLM processing
            
            elapsed = time.time() - start_time
            results.append({"task_id": task_id, "elapsed": elapsed})
            return {"type": "async_complete", "task_id": task_id}
        
        # Start async agent
        start_agents(async_agent, channel="async_test")
        
        reef = get_reef()
        
        # Send multiple async tasks
        for i in range(2):
            reef.system_broadcast({
                "type": "async_task",
                "task_id": f"async_{i}"
            }, channel="async_test")
        
        time.sleep(1.0)  # Wait for completion
        
        assert len(results) == 2
        # Both tasks should complete in roughly the same time due to async execution
        for result in results:
            assert 0.1 < result["elapsed"] < 0.5
    
    def test_message_type_filtering_with_threads(self):
        """Test message type filtering works correctly with concurrent execution."""
        responses = {"filtered": 0, "processed": 0}
        
        @agent("filtered_processor", channel="filter_test", responds_to=["process_only"])
        def filtered_agent(spore):
            msg_type = spore.knowledge.get("type")
            if msg_type == "process_only":
                responses["processed"] += 1
            else:
                responses["filtered"] += 1  # This shouldn't happen
            return {"processed": msg_type}
        
        start_agents(filtered_agent, channel="filter_test")
        
        reef = get_reef()
        
        # Send mixed message types
        reef.system_broadcast({"type": "process_only", "data": "should_process_1"}, channel="filter_test")
        reef.system_broadcast({"type": "ignore_me", "data": "should_ignore_1"}, channel="filter_test")
        reef.system_broadcast({"type": "process_only", "data": "should_process_2"}, channel="filter_test")
        reef.system_broadcast({"type": "skip_this", "data": "should_ignore_2"}, channel="filter_test")
        
        time.sleep(0.5)  # Wait for processing
        
        # Only "process_only" messages should be processed
        assert responses["processed"] == 2
        assert responses["filtered"] == 0  # Message filtering should prevent these
    
    def test_channel_statistics_with_threading(self):
        """Test that channel statistics correctly report thread usage."""
        @agent("stats_agent", channel="stats_test")
        def stats_agent(spore):
            time.sleep(0.1)  # Brief processing time
            return {"processed": True}
        
        start_agents(stats_agent, channel="stats_test")
        
        reef = get_reef()
        channel = reef.get_channel("stats_test")
        
        # Send some work to create thread activity
        for i in range(3):
            reef.system_broadcast({"data": f"task_{i}"}, channel="stats_test")
        
        time.sleep(0.2)  # Let threads start
        
        stats = channel.get_stats()
        assert "active_threads" in stats
        assert "shutdown" in stats
        assert stats["shutdown"] is False
        assert isinstance(stats["active_threads"], int)