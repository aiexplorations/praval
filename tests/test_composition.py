"""
Comprehensive tests for the Praval composition module.

This module ensures the agent composition utilities are bulletproof and handle
all edge cases correctly. Tests are strict and verify both functionality
and error conditions.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock, call

from praval.composition import (
    agent_pipeline, conditional_agent, throttled_agent, 
    AgentSession, start_agents
)
from praval.decorators import agent, get_agent_info
from praval.core.reef import get_reef, Spore, SporeType


class TestAgentPipeline:
    """Test the agent_pipeline function with comprehensive coverage."""
    
    def setup_method(self):
        """Set up test environment."""
        # Create mock agents for testing
        self.mock_agents = []
        for i in range(3):
            mock_func = Mock()
            mock_func.__name__ = f"test_agent_{i}"
            mock_func._praval_agent = Mock()
            mock_func._praval_name = f"agent_{i}"
            mock_func._praval_channel = f"agent_{i}_channel"
            self.mock_agents.append(mock_func)
    
    def test_agent_pipeline_basic_creation(self):
        """Test basic pipeline creation with valid agents."""
        pipeline = agent_pipeline(*self.mock_agents, channel="test_pipeline")
        
        # Verify pipeline metadata
        assert hasattr(pipeline, '_praval_pipeline')
        assert pipeline._praval_pipeline is True
        assert pipeline._praval_agents == tuple(self.mock_agents)
        assert pipeline._praval_channel == "test_pipeline"
    
    def test_agent_pipeline_default_channel(self):
        """Test pipeline creation with default channel name."""
        pipeline = agent_pipeline(*self.mock_agents)
        
        assert pipeline._praval_channel == "pipeline"
    
    def test_agent_pipeline_validates_agents(self):
        """Test that pipeline validates all functions are agents."""
        # Create a non-agent function
        def not_an_agent():
            pass
        
        with pytest.raises(ValueError, match="Function not_an_agent is not decorated with @agent"):
            agent_pipeline(self.mock_agents[0], not_an_agent, self.mock_agents[1])
    
    def test_agent_pipeline_empty_agents_allowed(self):
        """Test that creating pipeline with no agents is allowed."""
        pipeline = agent_pipeline(channel="empty_pipeline")
        
        assert pipeline._praval_agents == ()
        assert pipeline._praval_channel == "empty_pipeline"
    
    @patch('praval.composition.get_reef')
    @patch('praval.composition.get_agent_info')
    def test_pipeline_trigger_subscribes_agents(self, mock_get_agent_info, mock_get_reef):
        """Test that pipeline trigger subscribes agents to channel."""
        mock_reef = Mock()
        mock_get_reef.return_value = mock_reef
        
        # Set up mock agent info
        mock_agent_infos = []
        for mock_agent in self.mock_agents:
            mock_info = {
                "underlying_agent": Mock(),
                "name": mock_agent._praval_name,
                "channel": mock_agent._praval_channel
            }
            mock_agent_infos.append(mock_info)
        
        mock_get_agent_info.side_effect = mock_agent_infos
        
        pipeline = agent_pipeline(*self.mock_agents, channel="test_channel")
        result = pipeline({"initial": "data"})
        
        # Verify all agents were subscribed to pipeline channel
        for mock_info in mock_agent_infos:
            mock_info["underlying_agent"].subscribe_to_channel.assert_called_once_with("test_channel")
        
        # Verify channel creation and broadcast
        mock_reef.create_channel.assert_called_once_with("test_channel")
        mock_reef.system_broadcast.assert_called_once_with({"initial": "data"}, "test_channel")
    
    @patch('praval.composition.get_reef')
    @patch('praval.composition.get_agent_info')
    def test_pipeline_trigger_returns_spore_id(self, mock_get_agent_info, mock_get_reef):
        """Test that pipeline trigger returns spore ID from broadcast."""
        mock_reef = Mock()
        mock_reef.system_broadcast.return_value = "spore_123"
        mock_get_reef.return_value = mock_reef
        
        mock_get_agent_info.side_effect = [{"underlying_agent": Mock()} for _ in self.mock_agents]
        
        pipeline = agent_pipeline(*self.mock_agents)
        result = pipeline({"test": "data"})
        
        assert result == "spore_123"
    
    def test_pipeline_function_name_preservation(self):
        """Test that pipeline preserves function metadata."""
        @agent("test_agent_1")
        def agent_1(spore):
            return {"step": 1}
        
        @agent("test_agent_2")
        def agent_2(spore):
            return {"step": 2}
        
        pipeline = agent_pipeline(agent_1, agent_2, channel="sequence")
        
        # Pipeline should be callable
        assert callable(pipeline)
        # Should have pipeline metadata
        assert pipeline._praval_pipeline is True


class TestConditionalAgent:
    """Test the conditional_agent decorator with comprehensive coverage."""
    
    def setup_method(self):
        """Set up test environment."""
        self.condition_call_count = 0
    
    def test_conditional_agent_basic_functionality(self):
        """Test basic conditional agent decoration."""
        def priority_condition(spore):
            return spore.knowledge.get("priority") == "high"
        
        @agent("base_agent")
        def base_agent_func(spore):
            return {"processed": True}
        
        # Apply conditional decorator
        conditional_func = conditional_agent(priority_condition)(base_agent_func)
        
        # Should return the same function with modified behavior
        assert conditional_func is base_agent_func
        assert hasattr(conditional_func, '_praval_agent')
    
    def test_conditional_agent_requires_agent_decorator(self):
        """Test that conditional_agent requires @agent decorated function."""
        def condition(spore):
            return True
        
        def not_an_agent():
            pass
        
        with pytest.raises(ValueError, match="conditional_agent must be applied to @agent decorated functions"):
            conditional_agent(condition)(not_an_agent)
    
    @patch('praval.decorators.Agent')
    def test_conditional_agent_modifies_handler(self, mock_agent_class):
        """Test that conditional agent properly modifies the spore handler."""
        mock_agent = Mock()
        mock_original_handler = Mock()
        mock_agent._custom_spore_handler = mock_original_handler
        mock_agent_class.return_value = mock_agent
        
        condition_called = []
        
        def test_condition(spore):
            condition_called.append(spore)
            return spore.knowledge.get("execute", False)
        
        @agent("conditional_test")
        def test_agent(spore):
            return {"result": "success"}
        
        # Apply conditional decorator
        conditional_agent(test_condition)(test_agent)
        
        # Verify handler was replaced
        mock_agent.set_spore_handler.assert_called()
        new_handler = mock_agent.set_spore_handler.call_args[0][0]
        
        # Test condition evaluation - should execute
        spore_execute = Mock()
        spore_execute.knowledge = {"execute": True, "data": "test"}
        new_handler(spore_execute)
        
        # Verify condition was called and original handler executed
        assert len(condition_called) == 1
        assert condition_called[0] == spore_execute
        mock_original_handler.assert_called_once_with(spore_execute)
    
    @patch('praval.decorators.Agent')
    def test_conditional_agent_blocks_execution_when_false(self, mock_agent_class):
        """Test that conditional agent blocks execution when condition is False."""
        mock_agent = Mock()
        mock_original_handler = Mock()
        mock_agent._custom_spore_handler = mock_original_handler
        mock_agent_class.return_value = mock_agent
        
        def blocking_condition(spore):
            return spore.knowledge.get("allowed", False)
        
        @agent("blocked_agent")
        def test_agent(spore):
            return {"result": "success"}
        
        # Apply conditional decorator
        conditional_agent(blocking_condition)(test_agent)
        
        # Get the new handler
        new_handler = mock_agent.set_spore_handler.call_args[0][0]
        
        # Test condition evaluation - should NOT execute
        spore_blocked = Mock()
        spore_blocked.knowledge = {"allowed": False, "data": "test"}
        result = new_handler(spore_blocked)
        
        # Verify original handler was NOT called
        mock_original_handler.assert_not_called()
        assert result is None
    
    def test_conditional_agent_preserves_function_metadata(self):
        """Test that conditional decorator preserves function metadata."""
        def simple_condition(spore):
            return True
        
        @agent("metadata_agent")
        def original_agent(spore):
            """Original docstring"""
            return {"result": "ok"}
        
        original_name = original_agent._praval_name
        original_channel = original_agent._praval_channel
        
        # Apply conditional decorator
        decorated = conditional_agent(simple_condition)(original_agent)
        
        # Metadata should be preserved
        assert decorated._praval_name == original_name
        assert decorated._praval_channel == original_channel
        assert decorated is original_agent


class TestThrottledAgent:
    """Test the throttled_agent decorator with comprehensive coverage."""
    
    @patch('praval.decorators.Agent')
    def test_throttled_agent_basic_functionality(self, mock_agent_class):
        """Test basic throttled agent decoration."""
        mock_agent = Mock()
        mock_original_handler = Mock()
        mock_agent._custom_spore_handler = mock_original_handler
        mock_agent_class.return_value = mock_agent
        
        @agent("throttled_test")
        def test_agent(spore):
            return {"processed": True}
        
        # Apply throttled decorator (1 second delay)
        throttled_func = throttled_agent(1.0)(test_agent)
        
        # Should return the same function
        assert throttled_func is test_agent
        
        # Handler should have been replaced
        mock_agent.set_spore_handler.assert_called()
    
    def test_throttled_agent_requires_agent_decorator(self):
        """Test that throttled_agent requires @agent decorated function."""
        def not_an_agent():
            pass
        
        with pytest.raises(ValueError, match="throttled_agent must be applied to @agent decorated functions"):
            throttled_agent(1.0)(not_an_agent)
    
    @patch('time.time')
    @patch('praval.decorators.Agent')
    def test_throttled_agent_allows_first_execution(self, mock_agent_class, mock_time):
        """Test that throttled agent allows first execution immediately."""
        mock_agent = Mock()
        mock_original_handler = Mock(return_value="first_result")
        mock_agent._custom_spore_handler = mock_original_handler
        mock_agent_class.return_value = mock_agent
        
        mock_time.return_value = 1000.0  # Fixed time
        
        @agent("throttled_first")
        def test_agent(spore):
            return {"processed": True}
        
        # Apply throttled decorator (2 second delay)
        throttled_agent(2.0)(test_agent)
        
        # Get the new handler
        new_handler = mock_agent.set_spore_handler.call_args[0][0]
        
        # First execution should proceed immediately
        spore = Mock()
        result = new_handler(spore)
        
        mock_original_handler.assert_called_once_with(spore)
        assert result == "first_result"
    
    @patch('time.time')
    @patch('praval.decorators.Agent')
    def test_throttled_agent_blocks_rapid_execution(self, mock_agent_class, mock_time):
        """Test that throttled agent blocks execution within delay period."""
        mock_agent = Mock()
        mock_original_handler = Mock(return_value="handler_result")
        mock_agent._custom_spore_handler = mock_original_handler
        mock_agent_class.return_value = mock_agent
        
        # Simulate time progression
        time_sequence = [1000.0, 1001.0, 1003.0]  # 0s, 1s, 3s
        mock_time.side_effect = time_sequence
        
        @agent("throttled_blocked")
        def test_agent(spore):
            return {"processed": True}
        
        # Apply throttled decorator (2 second delay)
        throttled_agent(2.0)(test_agent)
        
        # Get the new handler
        new_handler = mock_agent.set_spore_handler.call_args[0][0]
        
        # First execution at t=0 - should proceed
        spore1 = Mock()
        result1 = new_handler(spore1)
        assert result1 == "handler_result"
        
        # Second execution at t=1 (within 2s delay) - should be blocked
        spore2 = Mock()
        result2 = new_handler(spore2)
        assert result2 is None
        
        # Third execution at t=3 (after 2s delay) - should proceed
        spore3 = Mock()
        result3 = new_handler(spore3)
        assert result3 == "handler_result"
        
        # Verify call count
        assert mock_original_handler.call_count == 2
        mock_original_handler.assert_has_calls([call(spore1), call(spore3)])
    
    @patch('praval.decorators.Agent')
    def test_throttled_agent_thread_safety(self, mock_agent_class):
        """Test that throttled agent is thread-safe."""
        mock_agent = Mock()
        execution_count = {"count": 0}
        
        def counting_handler(spore):
            execution_count["count"] += 1
            time.sleep(0.01)  # Small delay to test concurrency
            return f"execution_{execution_count['count']}"
        
        mock_agent._custom_spore_handler = counting_handler
        mock_agent_class.return_value = mock_agent
        
        @agent("thread_safe_throttled")
        def test_agent(spore):
            return {"processed": True}
        
        # Apply throttled decorator (0.1 second delay)
        throttled_agent(0.1)(test_agent)
        
        # Get the new handler
        new_handler = mock_agent.set_spore_handler.call_args[0][0]
        
        results = []
        
        def thread_worker():
            spore = Mock()
            result = new_handler(spore)
            results.append(result)
        
        # Start multiple threads rapidly
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=thread_worker)
            threads.append(thread)
            thread.start()
            time.sleep(0.02)  # Small stagger
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Only some executions should have proceeded due to throttling
        successful_results = [r for r in results if r is not None]
        assert len(successful_results) >= 1  # At least first should succeed
        assert len(successful_results) < len(threads)  # But not all due to throttling
    
    def test_throttled_agent_preserves_function_metadata(self):
        """Test that throttled decorator preserves function metadata."""
        @agent("throttled_metadata")
        def original_agent(spore):
            """Original docstring"""
            return {"result": "ok"}
        
        original_name = original_agent._praval_name
        original_channel = original_agent._praval_channel
        
        # Apply throttled decorator
        decorated = throttled_agent(0.5)(original_agent)
        
        # Metadata should be preserved
        assert decorated._praval_name == original_name
        assert decorated._praval_channel == original_channel
        assert decorated is original_agent


class TestAgentSession:
    """Test the AgentSession class with comprehensive coverage."""
    
    def setup_method(self):
        """Set up test environment."""
        # Create mock agents for testing
        self.mock_agents = []
        for i in range(3):
            mock_func = Mock()
            mock_func.__name__ = f"session_agent_{i}"
            mock_func._praval_agent = Mock()
            mock_func._praval_name = f"session_agent_{i}"
            mock_func._praval_channel = f"agent_{i}_channel"
            self.mock_agents.append(mock_func)
    
    def test_agent_session_initialization(self):
        """Test AgentSession initialization."""
        session = AgentSession("test_session")
        
        assert session.session_name == "test_session"
        assert session.channel_name == "session_test_session"
        assert session.agents == []
    
    @patch('praval.composition.get_reef')
    def test_agent_session_context_manager(self, mock_get_reef):
        """Test AgentSession as context manager."""
        mock_reef = Mock()
        mock_get_reef.return_value = mock_reef
        
        with AgentSession("ctx_test") as session:
            assert session.session_name == "ctx_test"
            assert session.channel_name == "session_ctx_test"
        
        # Verify channel creation
        mock_reef.create_channel.assert_called_once_with("session_ctx_test")
    
    def test_agent_session_add_agent_single(self):
        """Test adding a single agent to session."""
        session = AgentSession("single_test")
        mock_agent = self.mock_agents[0]
        
        with patch('praval.composition.get_agent_info') as mock_get_info:
            mock_get_info.return_value = {"underlying_agent": mock_agent._praval_agent}
            
            result = session.add_agent(mock_agent)
            
            # Should return self for chaining
            assert result is session
            assert mock_agent in session.agents
            
            # Verify subscription
            mock_agent._praval_agent.subscribe_to_channel.assert_called_once_with(session.channel_name)
    
    def test_agent_session_add_agent_invalid(self):
        """Test adding non-agent function to session raises error."""
        session = AgentSession("invalid_test")
        
        def not_an_agent():
            pass
        
        with pytest.raises(ValueError, match="Function not_an_agent is not decorated with @agent"):
            session.add_agent(not_an_agent)
    
    def test_agent_session_add_agents_multiple(self):
        """Test adding multiple agents to session."""
        session = AgentSession("multiple_test")
        
        with patch('praval.composition.get_agent_info') as mock_get_info:
            mock_get_info.side_effect = [
                {"underlying_agent": agent._praval_agent} 
                for agent in self.mock_agents
            ]
            
            result = session.add_agents(*self.mock_agents)
            
            # Should return self for chaining
            assert result is session
            assert len(session.agents) == len(self.mock_agents)
            
            # Verify all agents are subscribed
            for mock_agent in self.mock_agents:
                mock_agent._praval_agent.subscribe_to_channel.assert_called_with(session.channel_name)
    
    @patch('praval.composition.get_reef')
    def test_agent_session_broadcast(self, mock_get_reef):
        """Test broadcasting data in session."""
        mock_reef = Mock()
        mock_reef.system_broadcast.return_value = "broadcast_spore_123"
        mock_get_reef.return_value = mock_reef
        
        session = AgentSession("broadcast_test")
        data = {"message": "hello", "priority": "high"}
        
        result = session.broadcast(data)
        
        assert result == "broadcast_spore_123"
        
        # Verify broadcast with session data added
        expected_data = {"message": "hello", "priority": "high", "_session": "broadcast_test"}
        mock_reef.system_broadcast.assert_called_once_with(
            expected_data, 
            "session_broadcast_test"
        )
    
    def test_agent_session_get_stats_empty(self):
        """Test getting statistics from empty session."""
        session = AgentSession("stats_empty")
        
        stats = session.get_stats()
        
        expected = {
            "session_name": "stats_empty",
            "channel": "session_stats_empty", 
            "agent_count": 0,
            "agent_names": []
        }
        assert stats == expected
    
    def test_agent_session_get_stats_with_agents(self):
        """Test getting statistics from session with agents."""
        session = AgentSession("stats_full")
        
        with patch('praval.composition.get_agent_info') as mock_get_info:
            # Mock agent info responses
            mock_infos = [
                {"underlying_agent": agent._praval_agent, "name": agent._praval_name}
                for agent in self.mock_agents
            ]
            mock_get_info.side_effect = mock_infos + mock_infos  # Called twice (add + stats)
            
            # Add agents to session
            session.add_agents(*self.mock_agents)
            
            # Get stats
            stats = session.get_stats()
            
            expected = {
                "session_name": "stats_full",
                "channel": "session_stats_full",
                "agent_count": 3,
                "agent_names": ["session_agent_0", "session_agent_1", "session_agent_2"]
            }
            assert stats == expected
    
    def test_agent_session_fluent_interface(self):
        """Test AgentSession fluent interface chaining."""
        session = AgentSession("fluent_test")
        
        with patch('praval.composition.get_agent_info') as mock_get_info:
            mock_get_info.side_effect = [
                {"underlying_agent": agent._praval_agent}
                for agent in self.mock_agents
            ]
            
            # Should be able to chain operations
            result = (session
                     .add_agent(self.mock_agents[0])
                     .add_agents(*self.mock_agents[1:]))
            
            assert result is session
            assert len(session.agents) == 3


class TestStartAgents:
    """Test the start_agents function with comprehensive coverage."""
    
    def setup_method(self):
        """Set up test environment."""
        # Create mock agents for testing
        self.mock_agents = []
        for i in range(3):
            mock_func = Mock()
            mock_func.__name__ = f"start_agent_{i}"
            mock_func._praval_agent = Mock()
            mock_func._praval_name = f"start_agent_{i}"
            mock_func._praval_channel = f"agent_{i}_channel"
            self.mock_agents.append(mock_func)
    
    @patch('praval.composition.get_reef')
    @patch('praval.composition.get_agent_info')
    def test_start_agents_basic_functionality(self, mock_get_agent_info, mock_get_reef):
        """Test basic start_agents functionality."""
        mock_reef = Mock()
        mock_reef.system_broadcast.return_value = "startup_spore_456"
        mock_get_reef.return_value = mock_reef
        
        mock_get_agent_info.side_effect = [
            {"underlying_agent": agent._praval_agent}
            for agent in self.mock_agents
        ]
        
        initial_data = {"task": "startup_test", "priority": "normal"}
        result = start_agents(*self.mock_agents, initial_data=initial_data, channel="startup_test")
        
        assert result == "startup_spore_456"
        
        # Verify channel creation
        mock_reef.create_channel.assert_called_once_with("startup_test")
        
        # Verify all agents subscribed
        for mock_agent in self.mock_agents:
            mock_agent._praval_agent.subscribe_to_channel.assert_called_once_with("startup_test")
        
        # Verify broadcast with provided data
        mock_reef.system_broadcast.assert_called_once_with(initial_data, "startup_test")
    
    @patch('praval.composition.get_reef')
    @patch('praval.composition.get_agent_info')
    def test_start_agents_default_channel(self, mock_get_agent_info, mock_get_reef):
        """Test start_agents with default channel."""
        mock_reef = Mock()
        mock_reef.system_broadcast.return_value = "default_spore"
        mock_get_reef.return_value = mock_reef
        
        mock_get_agent_info.side_effect = [
            {"underlying_agent": agent._praval_agent}
            for agent in self.mock_agents
        ]
        
        result = start_agents(*self.mock_agents, initial_data={"test": "default"})
        
        # Should use default channel "startup"
        mock_reef.create_channel.assert_called_once_with("startup")
        for mock_agent in self.mock_agents:
            mock_agent._praval_agent.subscribe_to_channel.assert_called_once_with("startup")
        mock_reef.system_broadcast.assert_called_once_with({"test": "default"}, "startup")
    
    @patch('praval.composition.get_reef')
    @patch('praval.composition.get_agent_info')
    def test_start_agents_no_initial_data(self, mock_get_agent_info, mock_get_reef):
        """Test start_agents without initial data."""
        mock_reef = Mock()
        mock_reef.system_broadcast.return_value = "no_data_spore"
        mock_get_reef.return_value = mock_reef
        
        mock_get_agent_info.side_effect = [
            {"underlying_agent": agent._praval_agent}
            for agent in self.mock_agents
        ]
        
        result = start_agents(*self.mock_agents, channel="no_data_test")
        
        # Should broadcast default startup message
        mock_reef.system_broadcast.assert_called_once_with(
            {"type": "agents_started"}, 
            "no_data_test"
        )
    
    def test_start_agents_validates_all_functions(self):
        """Test that start_agents validates all functions are agents."""
        def not_an_agent():
            pass
        
        with pytest.raises(ValueError, match="Function not_an_agent is not decorated with @agent"):
            start_agents(self.mock_agents[0], not_an_agent, self.mock_agents[1])
    
    @patch('praval.composition.get_reef')
    def test_start_agents_empty_list_allowed(self, mock_get_reef):
        """Test that start_agents allows empty agent list."""
        mock_reef = Mock()
        mock_reef.system_broadcast.return_value = "empty_spore"
        mock_get_reef.return_value = mock_reef
        
        result = start_agents(initial_data={"empty": True})
        
        assert result == "empty_spore"
        mock_reef.create_channel.assert_called_once_with("startup")
        mock_reef.system_broadcast.assert_called_once_with({"empty": True}, "startup")
    
    @patch('praval.composition.get_reef')  
    @patch('praval.composition.get_agent_info')
    def test_start_agents_handles_single_agent(self, mock_get_agent_info, mock_get_reef):
        """Test start_agents with single agent."""
        mock_reef = Mock()
        mock_reef.system_broadcast.return_value = "single_spore"
        mock_get_reef.return_value = mock_reef
        
        mock_get_agent_info.return_value = {"underlying_agent": self.mock_agents[0]._praval_agent}
        
        result = start_agents(self.mock_agents[0], initial_data={"single": True})
        
        assert result == "single_spore"
        
        # Verify single agent was handled correctly
        mock_get_agent_info.assert_called_once_with(self.mock_agents[0])
        self.mock_agents[0]._praval_agent.subscribe_to_channel.assert_called_once_with("startup")


class TestIntegrationScenarios:
    """Test complex integration scenarios for the composition system."""
    
    @patch('praval.composition.get_reef')
    @patch('praval.composition.get_agent_info')
    def test_pipeline_with_session_integration(self, mock_get_agent_info, mock_get_reef):
        """Test integration between pipeline and session."""
        mock_reef = Mock()
        mock_get_reef.return_value = mock_reef
        
        # Create mock agents
        mock_agents = []
        for i in range(2):
            mock_func = Mock()
            mock_func.__name__ = f"integration_agent_{i}"
            mock_func._praval_agent = Mock()
            mock_agents.append(mock_func)
        
        mock_get_agent_info.side_effect = [
            {"underlying_agent": agent._praval_agent}
            for agent in mock_agents
        ] * 3  # Called multiple times
        
        # Create pipeline
        pipeline = agent_pipeline(*mock_agents, channel="integration_pipeline")
        
        # Create session and add agents
        with AgentSession("integration_session") as session:
            session.add_agents(*mock_agents)
            
            # Trigger pipeline
            pipeline_result = pipeline({"integration": "test"})
            
            # Session broadcast  
            session_result = session.broadcast({"session": "data"})
        
        # Verify both pipeline and session operations worked
        assert mock_reef.system_broadcast.call_count >= 2
        
        # Verify agents were subscribed to multiple channels
        for mock_agent in mock_agents:
            calls = mock_agent._praval_agent.subscribe_to_channel.call_args_list
            channel_calls = [call[0][0] for call in calls]
            assert "integration_pipeline" in channel_calls
            assert "session_integration_session" in channel_calls
    
    def test_conditional_and_throttled_composition(self):
        """Test combining conditional and throttled decorators."""
        @agent("combo_agent")
        def base_agent(spore):
            return {"processed": True}
        
        # Apply both decorators
        def high_priority_condition(spore):
            return spore.knowledge.get("priority") == "high"
        
        decorated_agent = throttled_agent(0.1)(
            conditional_agent(high_priority_condition)(base_agent)
        )
        
        # Should still be the same function with both behaviors
        assert decorated_agent is base_agent
        assert hasattr(decorated_agent, '_praval_agent')
    
    @patch('praval.composition.get_reef')
    @patch('praval.composition.get_agent_info')
    def test_start_agents_with_decorated_agents(self, mock_get_agent_info, mock_get_reef):
        """Test start_agents with various decorated agents."""
        mock_reef = Mock()
        mock_reef.system_broadcast.return_value = "decorated_spore"
        mock_get_reef.return_value = mock_reef
        
        # Create base agent
        @agent("decorated_base")
        def base_agent(spore):
            return {"base": True}
        
        # Apply decorations
        def always_true(spore):
            return True
        
        conditional_decorated = conditional_agent(always_true)(base_agent)
        throttled_decorated = throttled_agent(0.1)(conditional_decorated)
        
        mock_get_agent_info.return_value = {"underlying_agent": base_agent._praval_agent}
        
        # Start agents should work with decorated agents
        result = start_agents(throttled_decorated, initial_data={"decorated": True})
        
        assert result == "decorated_spore"
        mock_reef.system_broadcast.assert_called_once_with({"decorated": True}, "startup")


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases in composition utilities."""
    
    def test_pipeline_with_none_agents(self):
        """Test pipeline creation with None values."""
        mock_agent = Mock()
        mock_agent.__name__ = "valid_agent"
        mock_agent._praval_agent = Mock()
        
        # None should cause AttributeError when checking for _praval_agent
        with pytest.raises(AttributeError):
            agent_pipeline(mock_agent, None)
    
    def test_session_with_duplicate_agents(self):
        """Test session behavior with duplicate agents."""
        mock_agent = Mock()
        mock_agent.__name__ = "duplicate_agent"
        mock_agent._praval_agent = Mock()
        
        session = AgentSession("duplicate_test")
        
        with patch('praval.composition.get_agent_info') as mock_get_info:
            mock_get_info.return_value = {"underlying_agent": mock_agent._praval_agent}
            
            # Add same agent twice
            session.add_agent(mock_agent)
            session.add_agent(mock_agent)
            
            # Should have two references to same agent
            assert len(session.agents) == 2
            assert session.agents[0] is mock_agent
            assert session.agents[1] is mock_agent
    
    @patch('time.time')
    @patch('praval.decorators.Agent')
    def test_throttled_agent_with_zero_delay(self, mock_agent_class, mock_time):
        """Test throttled agent with zero delay (should always execute)."""
        mock_agent = Mock()
        mock_original_handler = Mock(return_value="zero_delay_result")
        mock_agent._custom_spore_handler = mock_original_handler
        mock_agent_class.return_value = mock_agent
        
        mock_time.return_value = 1000.0
        
        @agent("zero_delay_agent")
        def test_agent(spore):
            return {"processed": True}
        
        # Apply throttled decorator with 0 delay
        throttled_agent(0.0)(test_agent)
        
        # Get the new handler
        new_handler = mock_agent.set_spore_handler.call_args[0][0]
        
        # Multiple rapid executions should all succeed with 0 delay
        for i in range(3):
            spore = Mock()
            result = new_handler(spore)
            assert result == "zero_delay_result"
        
        # All calls should have been executed
        assert mock_original_handler.call_count == 3
    
    def test_session_broadcast_preserves_original_data(self):
        """Test that session broadcast doesn't modify original data dict."""
        session = AgentSession("preserve_test")
        
        original_data = {"message": "test", "count": 42}
        
        with patch('praval.composition.get_reef') as mock_get_reef:
            mock_reef = Mock()
            mock_get_reef.return_value = mock_reef
            
            session.broadcast(original_data)
            
            # Original data should be unchanged
            assert original_data == {"message": "test", "count": 42}
            assert "_session" not in original_data
            
            # But broadcast should have included session info
            broadcast_call = mock_reef.system_broadcast.call_args
            broadcast_data = broadcast_call[0][0]
            assert broadcast_data["_session"] == "preserve_test"
            assert broadcast_data["message"] == "test"
            assert broadcast_data["count"] == 42