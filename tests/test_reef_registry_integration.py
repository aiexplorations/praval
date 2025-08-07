"""
Tests for Reef integration with the Praval Registry system.

These tests verify that the reef communication system integrates
seamlessly with agent and tool discovery through the registry.
"""

import pytest
from typing import Dict, Any, List
from unittest.mock import Mock, patch

from praval import Agent, register_agent, get_registry
from praval.core.reef import Spore, SporeType, get_reef
from praval.core.registry import PravalRegistry


class TestReefRegistryIntegration:
    """Test integration between Reef and Registry systems."""
    
    def test_registry_tracks_reef_enabled_agents(self):
        """Test that registry can track agents with reef capabilities."""
        # Create agents with reef capabilities
        researcher = Agent("researcher", system_message="Research specialist")
        analyzer = Agent("analyzer", system_message="Data analysis expert")
        
        # Register agents
        register_agent(researcher)
        register_agent(analyzer)
        
        registry = get_registry()
        
        # Registry should track all agents
        agents = registry.list_agents()
        assert "researcher" in agents
        assert "analyzer" in agents
        
        # Should be able to retrieve agents
        retrieved_researcher = registry.get_agent("researcher")
        retrieved_analyzer = registry.get_agent("analyzer")
        
        assert retrieved_researcher is researcher
        assert retrieved_analyzer is analyzer
        
        # Retrieved agents should have reef capabilities
        assert hasattr(retrieved_researcher, 'send_knowledge')
        assert hasattr(retrieved_analyzer, 'broadcast_knowledge')
    
    def test_agent_discovery_for_reef_communication(self):
        """Test discovering agents through registry for reef communication."""
        # Create specialized agents
        weather_agent = Agent("weather_service", system_message="Weather information provider")
        news_agent = Agent("news_service", system_message="News information provider")
        client_agent = Agent("client", system_message="Service consumer")
        
        # Register all agents
        register_agent(weather_agent)
        register_agent(news_agent)
        register_agent(client_agent)
        
        # Client discovers available services through registry
        registry = get_registry()
        available_agents = registry.list_agents()
        
        # Find service agents
        service_agents = [name for name in available_agents if name.endswith("_service")]
        assert "weather_service" in service_agents
        assert "news_service" in service_agents
        
        # Client can communicate with discovered services
        received_responses = []
        def response_handler(spore: Spore) -> None:
            if spore.spore_type == SporeType.RESPONSE:
                received_responses.append(spore.knowledge)
        
        client_agent.subscribe_to_channel("main")
        
        # Mock weather service to respond
        def weather_responder(spore: Spore) -> None:
            if spore.spore_type == SporeType.REQUEST and spore.knowledge.get("service") == "weather":
                get_reef().reply(
                    from_agent="weather_service",
                    to_agent=spore.from_agent,
                    response={"temperature": 25, "condition": "sunny"},
                    reply_to_spore_id=spore.id
                )
        
        weather_agent.subscribe_to_channel("main")
        
        with patch.object(client_agent, 'on_spore_received', side_effect=response_handler), \
             patch.object(weather_agent, 'on_spore_received', side_effect=weather_responder):
            
            # Client requests weather from discovered service
            client_agent.request_knowledge(
                from_agent="weather_service",
                request={
                    "service": "weather",
                    "location": "san_francisco"
                },
                timeout=5
            )
            
            # Should receive response
            assert len(received_responses) == 1
            assert received_responses[0]["temperature"] == 25
    
    def test_tool_discovery_with_reef_communication(self):
        """Test discovering and using agent tools through reef communication."""
        # Create agent with useful tools
        math_agent = Agent("math_service")
        
        @math_agent.tool
        def fibonacci(n: int) -> int:
            """Calculate fibonacci number."""
            if n <= 1:
                return n
            return fibonacci(n-1) + fibonacci(n-2)
        
        @math_agent.tool  
        def factorial(n: int) -> int:
            """Calculate factorial."""
            if n <= 1:
                return 1
            return n * factorial(n-1)
        
        register_agent(math_agent)
        
        # Client discovers available tools through registry
        registry = get_registry()
        math_tools = registry.get_tools_by_agent("math_service")
        
        assert "math_service.fibonacci" in math_tools
        assert "math_service.factorial" in math_tools
        
        # Verify tool metadata
        fib_tool = registry.get_tool("math_service.fibonacci")
        assert fib_tool["description"] == "Calculate fibonacci number."
        assert fib_tool["agent"] == "math_service"
        
        # Client can request tool execution via reef
        client_agent = Agent("client")
        register_agent(client_agent)
        client_agent.subscribe_to_channel("main")
        
        received_results = []
        def result_handler(spore: Spore) -> None:
            if spore.spore_type == SporeType.RESPONSE:
                received_results.append(spore.knowledge)
        
        # Mock math agent to execute tools on request
        def tool_executor(spore: Spore) -> None:
            if spore.spore_type == SporeType.REQUEST:
                tool_name = spore.knowledge.get("tool")
                params = spore.knowledge.get("params", {})
                
                if tool_name == "fibonacci":
                    result = math_agent.tools["fibonacci"]["function"](**params)
                    get_reef().reply(
                        from_agent="math_service",
                        to_agent=spore.from_agent,
                        response={"tool": tool_name, "result": result},
                        reply_to_spore_id=spore.id
                    )
        
        math_agent.subscribe_to_channel("main")
        
        with patch.object(client_agent, 'on_spore_received', side_effect=result_handler), \
             patch.object(math_agent, 'on_spore_received', side_effect=tool_executor):
            
            # Request tool execution
            client_agent.request_knowledge(
                from_agent="math_service",
                request={
                    "tool": "fibonacci",
                    "params": {"n": 8}
                },
                timeout=5
            )
            
            # Should receive tool result
            assert len(received_results) == 1
            assert received_results[0]["tool"] == "fibonacci"
            assert received_results[0]["result"] == 21  # fibonacci(8)
    
    def test_broadcast_to_registered_agents(self):
        """Test broadcasting to all registered agents."""
        # Create multiple agents with different specializations
        agents = {}
        agent_types = ["research", "analysis", "monitoring", "reporting"]
        
        for agent_type in agent_types:
            agent = Agent(f"{agent_type}_agent")
            register_agent(agent)
            agent.subscribe_to_channel("main")
            agents[agent_type] = agent
        
        # Track broadcasts received by each agent
        broadcasts_received = {agent_type: [] for agent_type in agent_types}
        
        def create_broadcast_handler(agent_type: str):
            def handler(spore: Spore) -> None:
                if spore.spore_type == SporeType.BROADCAST:
                    broadcasts_received[agent_type].append(spore.knowledge)
            return handler
        
        # Set up broadcast handlers for all agents
        patches = []
        for agent_type in agent_types:
            patch_obj = patch.object(
                agents[agent_type], 
                'on_spore_received', 
                side_effect=create_broadcast_handler(agent_type)
            )
            patches.append(patch_obj)
        
        # Apply all patches and broadcast
        with patch.multiple(*patches):
            # Create broadcaster agent
            broadcaster = Agent("system_broadcaster")
            register_agent(broadcaster)
            
            # Broadcast system-wide announcement
            broadcaster.broadcast_knowledge({
                "announcement": "system_maintenance_scheduled",
                "time": "2024-01-15T02:00:00Z",
                "duration": "2_hours",
                "affected_services": ["all"]
            })
            
            # All registered agents should receive broadcast
            for agent_type in agent_types:
                assert len(broadcasts_received[agent_type]) == 1
                broadcast = broadcasts_received[agent_type][0]
                assert broadcast["announcement"] == "system_maintenance_scheduled"
                assert broadcast["duration"] == "2_hours"
    
    def test_registry_based_agent_lookup_for_messaging(self):
        """Test using registry to look up agents for direct messaging."""
        # Create agents in different domains
        agents_config = {
            "nlp_specialist": "Natural language processing expert",
            "cv_specialist": "Computer vision expert", 
            "ml_generalist": "General machine learning practitioner",
            "data_engineer": "Data pipeline and ETL specialist"
        }
        
        created_agents = {}
        for name, description in agents_config.items():
            agent = Agent(name, system_message=description)
            register_agent(agent)
            agent.subscribe_to_channel("main")
            created_agents[name] = agent
        
        # Create coordinator that uses registry to find specialists
        coordinator = Agent("project_coordinator")
        register_agent(coordinator)
        
        # Coordinator discovers specialists through registry
        registry = get_registry()
        all_agents = registry.list_agents()
        
        # Find specialists
        specialists = [name for name in all_agents if name.endswith("_specialist")]
        assert "nlp_specialist" in specialists
        assert "cv_specialist" in specialists
        
        # Send targeted messages to specialists
        messages_received = {name: [] for name in specialists}
        
        def create_message_handler(agent_name: str):
            def handler(spore: Spore) -> None:
                if spore.to_agent == agent_name:
                    messages_received[agent_name].append(spore.knowledge)
            return handler
        
        patches = []
        for specialist in specialists:
            agent = created_agents[specialist]
            patch_obj = patch.object(
                agent,
                'on_spore_received',
                side_effect=create_message_handler(specialist)
            )
            patches.append(patch_obj)
        
        with patch.multiple(*patches):
            # Send specific tasks to specialists
            coordinator.send_knowledge(
                to_agent="nlp_specialist",
                knowledge={
                    "task": "sentiment_analysis",
                    "dataset": "customer_reviews",
                    "deadline": "2024-01-20"
                }
            )
            
            coordinator.send_knowledge(
                to_agent="cv_specialist", 
                knowledge={
                    "task": "object_detection",
                    "dataset": "security_cameras",
                    "deadline": "2024-01-25"
                }
            )
            
            # Verify targeted delivery
            assert len(messages_received["nlp_specialist"]) == 1
            assert len(messages_received["cv_specialist"]) == 1
            
            nlp_task = messages_received["nlp_specialist"][0]
            cv_task = messages_received["cv_specialist"][0]
            
            assert nlp_task["task"] == "sentiment_analysis"
            assert cv_task["task"] == "object_detection"
    
    def test_registry_statistics_with_reef_activity(self):
        """Test that registry can provide statistics including reef activity."""
        # Create agents and generate reef activity
        agent_names = ["producer", "consumer", "processor"]
        agents = {}
        
        for name in agent_names:
            agent = Agent(name)
            register_agent(agent)
            agent.subscribe_to_channel("main")
            agents[name] = agent
        
        # Generate some reef activity
        reef = get_reef()
        
        # Send various types of messages
        reef.send("producer", "consumer", {"data": "sample1"})
        reef.send("producer", "processor", {"data": "sample2"})
        reef.broadcast("producer", {"announcement": "batch_complete"})
        reef.request("consumer", "processor", {"query": "status"})
        
        # Get registry stats
        registry = get_registry()
        registry_stats = {
            "total_agents": len(registry.list_agents()),
            "total_tools": len(registry.list_tools()),
            "agent_names": registry.list_agents()
        }
        
        # Get reef stats
        reef_stats = reef.get_network_stats()
        
        # Verify integration
        assert registry_stats["total_agents"] == 3
        assert all(name in registry_stats["agent_names"] for name in agent_names)
        
        # Reef should show activity
        main_channel_stats = reef_stats["channel_stats"]["main"]
        assert main_channel_stats["spores_carried"] == 4  # 2 direct + 1 broadcast + 1 request
        assert main_channel_stats["active_spores"] == 4
    
    def test_dynamic_agent_registration_with_reef(self):
        """Test dynamically registering agents and using reef immediately."""
        # Start with empty registry
        registry = get_registry()
        initial_agent_count = len(registry.list_agents())
        
        # Dynamically create and register new agent
        dynamic_agent = Agent("dynamic_service")
        
        @dynamic_agent.tool
        def process_data(data: str) -> str:
            """Process input data."""
            return f"processed_{data}"
        
        register_agent(dynamic_agent)
        dynamic_agent.subscribe_to_channel("main")
        
        # Verify registration
        assert len(registry.list_agents()) == initial_agent_count + 1
        assert "dynamic_service" in registry.list_agents()
        assert "dynamic_service.process_data" in registry.list_tools()
        
        # Use newly registered agent immediately via reef
        client = Agent("dynamic_client")
        register_agent(client)
        client.subscribe_to_channel("main")
        
        responses_received = []
        def response_collector(spore: Spore) -> None:
            if spore.spore_type == SporeType.RESPONSE:
                responses_received.append(spore.knowledge)
        
        # Mock dynamic service to respond to requests
        def service_handler(spore: Spore) -> None:
            if spore.spore_type == SporeType.REQUEST and spore.knowledge.get("service") == "process":
                tool_result = dynamic_agent.tools["process_data"]["function"](
                    spore.knowledge["input"]
                )
                get_reef().reply(
                    from_agent="dynamic_service",
                    to_agent=spore.from_agent,
                    response={"result": tool_result},
                    reply_to_spore_id=spore.id
                )
        
        with patch.object(client, 'on_spore_received', side_effect=response_collector), \
             patch.object(dynamic_agent, 'on_spore_received', side_effect=service_handler):
            
            # Client uses newly registered service
            client.request_knowledge(
                from_agent="dynamic_service",
                request={
                    "service": "process",
                    "input": "test_data"
                },
                timeout=5
            )
            
            # Should get response from dynamic service
            assert len(responses_received) == 1
            assert responses_received[0]["result"] == "processed_test_data"


class TestReefRegistryErrorHandling:
    """Test error handling in reef-registry integration."""
    
    def test_messaging_nonexistent_agent(self):
        """Test sending messages to non-existent agents."""
        sender = Agent("sender")
        register_agent(sender)
        
        # Send to non-existent agent should not raise error
        # (reef system should handle gracefully)
        spore_id = sender.send_knowledge(
            to_agent="nonexistent_agent",
            knowledge={"message": "hello nobody"}
        )
        
        assert isinstance(spore_id, str)
        
        # Message should be in reef but no agent will receive it
        reef = get_reef()
        main_channel = reef.get_channel("main")
        assert len(main_channel.spores) == 1
        assert main_channel.spores[0].to_agent == "nonexistent_agent"
    
    def test_registry_corruption_resilience(self):
        """Test that reef works even if registry has issues."""
        # Create agents normally
        agent1 = Agent("agent1")
        agent2 = Agent("agent2")
        
        register_agent(agent1)
        register_agent(agent2)
        
        agent2.subscribe_to_channel("main")
        
        # Mock registry failure
        with patch('praval.core.registry.get_registry') as mock_registry:
            mock_registry.side_effect = Exception("Registry unavailable")
            
            # Reef communication should still work
            received_messages = []
            def message_handler(spore: Spore) -> None:
                received_messages.append(spore.knowledge)
            
            with patch.object(agent2, 'on_spore_received', side_effect=message_handler):
                # Direct reef communication bypasses registry
                reef = get_reef()
                reef.send(
                    from_agent="agent1",
                    to_agent="agent2",
                    knowledge={"message": "registry_independent"}
                )
                
                assert len(received_messages) == 1
                assert received_messages[0]["message"] == "registry_independent"


# Fixtures for registry + reef integration tests
@pytest.fixture
def populated_registry():
    """Create a registry with various types of agents and tools."""
    agents = {}
    
    # Create different types of agents
    agent_configs = [
        ("calculator", "Mathematical computation service"),
        ("translator", "Language translation service"),
        ("analyzer", "Data analysis service"),
        ("monitor", "System monitoring service")
    ]
    
    for name, description in agent_configs:
        agent = Agent(name, system_message=description)
        
        # Add some tools to each agent
        if name == "calculator":
            @agent.tool
            def add(x: int, y: int) -> int:
                return x + y
            
            @agent.tool
            def multiply(x: int, y: int) -> int:
                return x * y
        
        elif name == "analyzer":
            @agent.tool
            def analyze_data(data: List[int]) -> Dict[str, float]:
                return {
                    "mean": sum(data) / len(data),
                    "max": max(data),
                    "min": min(data)
                }
        
        register_agent(agent)
        agent.subscribe_to_channel("main")
        agents[name] = agent
    
    return agents


@pytest.fixture
def reef_with_activity():
    """Create a reef with some existing activity."""
    reef = get_reef()
    
    # Create some channels with activity
    reef.create_channel("research")
    reef.create_channel("alerts")
    
    # Generate some activity
    reef.send("system", "user1", {"welcome": "message"})
    reef.broadcast("system", {"status": "online"})
    reef.send("user1", "service", {"request": "data"}, channel="research")
    
    return reef