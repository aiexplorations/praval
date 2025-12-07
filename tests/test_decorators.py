"""
Comprehensive tests for the Praval decorators module.

This module ensures the @agent decorator system is bulletproof and handles
all edge cases correctly. Tests are strict and verify both functionality
and error conditions.
"""

import pytest
import threading
import time
from unittest.mock import Mock, patch, MagicMock, call
from concurrent.futures import TimeoutError as FutureTimeoutError
import asyncio

from praval.decorators import agent, chat, achat, broadcast, get_agent_info, _agent_context
from praval.core.agent import Agent
from praval.core.reef import Spore, SporeType


class TestAgentDecorator:
    """Test the @agent decorator with comprehensive coverage."""
    
    def setup_method(self):
        """Clean agent context before each test."""
        _agent_context.agent = None
        _agent_context.channel = None
    
    def test_agent_decorator_basic_usage(self):
        """Test basic @agent decorator functionality."""
        @agent("test_agent")
        def test_func(spore):
            return {"result": "success"}
        
        # Verify agent metadata is attached
        assert hasattr(test_func, '_praval_agent')
        assert hasattr(test_func, '_praval_name')
        assert hasattr(test_func, '_praval_channel')
        assert test_func._praval_name == "test_agent"
        assert test_func._praval_channel == "test_agent_channel"
        assert isinstance(test_func._praval_agent, Agent)
    
    def test_agent_decorator_name_defaults_to_function_name(self):
        """Test that agent name defaults to function name when not provided."""
        @agent()
        def my_custom_function(spore):
            return {"test": True}
        
        assert my_custom_function._praval_name == "my_custom_function"
        assert my_custom_function._praval_channel == "my_custom_function_channel"
    
    def test_agent_decorator_with_custom_channel(self):
        """Test @agent with custom channel."""
        @agent("agent1", channel="custom_channel")
        def test_func(spore):
            return {"data": "test"}
        
        assert test_func._praval_channel == "custom_channel"
    
    def test_agent_decorator_with_system_message(self):
        """Test @agent with explicit system message."""
        @agent("agent1", system_message="You are a helpful assistant.")
        def test_func(spore):
            """Original docstring"""
            return {"data": "test"}
        
        # Should use explicit system message
        agent_obj = test_func._praval_agent
        assert agent_obj.config.system_message == "You are a helpful assistant."
    
    def test_agent_decorator_system_message_from_docstring(self):
        """Test that system message auto-generates from docstring."""
        @agent("doc_agent")
        def test_func(spore):
            """This is a test agent that does testing."""
            return {"result": "ok"}
        
        expected = "You are doc_agent. This is a test agent that does testing."
        assert test_func._praval_agent.config.system_message == expected
    
    def test_agent_decorator_no_system_message_without_docstring(self):
        """Test behavior when no system message or docstring provided."""
        @agent("no_doc_agent")
        def test_func(spore):
            return {"result": "ok"}
        
        # Should be None when no docstring and no explicit system_message
        assert test_func._praval_agent.config.system_message is None
    
    def test_agent_decorator_auto_broadcast_default(self):
        """Test that auto_broadcast defaults to True."""
        @agent("broadcast_agent")
        def test_func(spore):
            return {"result": "test"}
        
        assert test_func._praval_auto_broadcast is True
    
    def test_agent_decorator_auto_broadcast_disabled(self):
        """Test disabling auto_broadcast."""
        @agent("no_broadcast_agent", auto_broadcast=False)
        def test_func(spore):
            return {"result": "test"}
        
        assert test_func._praval_auto_broadcast is False
    
    def test_agent_decorator_responds_to_filtering(self):
        """Test responds_to message type filtering."""
        @agent("filter_agent", responds_to=["query", "request"])
        def test_func(spore):
            return {"processed": True}
        
        assert test_func._praval_responds_to == ["query", "request"]
    
    def test_agent_decorator_memory_enabled_boolean(self):
        """Test enabling memory with boolean flag."""
        @agent("memory_agent", memory=True)
        def test_func(spore):
            return {"result": "test"}
        
        assert test_func._praval_memory_enabled is True
        assert hasattr(test_func, 'remember')
        assert hasattr(test_func, 'recall')
        assert hasattr(test_func, 'recall_by_id')
        assert hasattr(test_func, 'get_conversation_context')
        assert hasattr(test_func, 'memory')
    
    def test_agent_decorator_memory_enabled_with_config(self):
        """Test enabling memory with custom configuration."""
        memory_config = {"collection_name": "custom_collection"}
        
        @agent("memory_config_agent", memory=memory_config)
        def test_func(spore):
            return {"result": "test"}
        
        assert test_func._praval_memory_enabled is True
        assert hasattr(test_func, 'remember')
    
    def test_agent_decorator_memory_disabled(self):
        """Test that memory is disabled by default."""
        @agent("no_memory_agent")
        def test_func(spore):
            return {"result": "test"}
        
        assert test_func._praval_memory_enabled is False
        assert not hasattr(test_func, 'remember')
        assert not hasattr(test_func, 'recall')
    
    def test_agent_decorator_knowledge_base_path(self):
        """Test knowledge_base parameter."""
        @agent("kb_agent", knowledge_base="./test_kb/")
        def test_func(spore):
            return {"result": "test"}
        
        assert test_func._praval_knowledge_base == "./test_kb/"
    
    def test_agent_decorator_adds_reef_methods(self):
        """Test that reef communication methods are added."""
        @agent("reef_agent")
        def test_func(spore):
            return {"result": "test"}
        
        # All agents should have reef communication methods
        assert hasattr(test_func, 'send_knowledge')
        assert hasattr(test_func, 'broadcast_knowledge')
        assert hasattr(test_func, 'request_knowledge')
    
    @patch('praval.decorators.Agent')
    def test_agent_decorator_creates_underlying_agent(self, mock_agent_class):
        """Test that decorator creates Agent with correct parameters."""
        mock_agent_instance = Mock()
        mock_agent_class.return_value = mock_agent_instance
        
        @agent("test_agent", system_message="Test message", memory=True, knowledge_base="./kb/")
        def test_func(spore):
            return {"result": "test"}
        
        # Verify Agent was created with correct parameters
        mock_agent_class.assert_called_once_with(
            name="test_agent",
            system_message="Test message", 
            memory_enabled=True,
            memory_config={},
            knowledge_base="./kb/"
        )
    
    @patch('praval.decorators.Agent')
    def test_agent_decorator_sets_up_reef_integration(self, mock_agent_class):
        """Test that decorator properly sets up reef integration."""
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        
        @agent("reef_test_agent", channel="test_channel")
        def test_func(spore):
            return {"result": "test"}
        
        # Verify reef setup calls
        mock_agent.set_spore_handler.assert_called_once()
        mock_agent.subscribe_to_channel.assert_called_once_with("test_channel")


class TestAgentHandler:
    """Test the internal agent handler logic."""
    
    def setup_method(self):
        """Clean agent context before each test."""
        _agent_context.agent = None
        _agent_context.channel = None
    
    @patch('praval.decorators.Agent')
    def test_handler_responds_to_filtering_allows_matching_types(self, mock_agent_class):
        """Test that handler allows messages matching responds_to."""
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        
        func_called = False
        
        @agent("filter_agent", responds_to=["query", "request"])
        def test_func(spore):
            nonlocal func_called
            func_called = True
            return {"processed": True}
        
        # Create a spore with matching type
        spore = Mock()
        spore.knowledge = {"type": "query", "data": "test"}
        
        # Get the handler that was registered
        handler = mock_agent.set_spore_handler.call_args[0][0]
        
        # Call handler with matching message type
        handler(spore)
        
        assert func_called is True
    
    @patch('praval.decorators.Agent')
    def test_handler_responds_to_filtering_blocks_non_matching_types(self, mock_agent_class):
        """Test that handler blocks messages not matching responds_to."""
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        
        func_called = False
        
        @agent("filter_agent", responds_to=["query", "request"])
        def test_func(spore):
            nonlocal func_called
            func_called = True
            return {"processed": True}
        
        # Create a spore with non-matching type
        spore = Mock()
        spore.knowledge = {"type": "notification", "data": "test"}
        
        # Get the handler that was registered
        handler = mock_agent.set_spore_handler.call_args[0][0]
        
        # Call handler with non-matching message type
        result = handler(spore)
        
        assert func_called is False
        assert result is None
    
    @patch('praval.decorators.Agent')
    def test_handler_sets_agent_context(self, mock_agent_class):
        """Test that handler sets up agent context correctly."""
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        
        context_agent = None
        context_channel = None
        
        @agent("context_agent", channel="test_channel")
        def test_func(spore):
            nonlocal context_agent, context_channel
            context_agent = _agent_context.agent
            context_channel = _agent_context.channel
            return {"result": "ok"}
        
        spore = Mock()
        spore.knowledge = {"type": "test"}
        
        # Get and call the handler
        handler = mock_agent.set_spore_handler.call_args[0][0]
        handler(spore)
        
        # Verify context was set correctly during execution
        assert context_agent == mock_agent
        assert context_channel == "test_channel"
    
    @patch('praval.decorators.Agent')  
    def test_handler_cleans_up_context_after_execution(self, mock_agent_class):
        """Test that handler cleans up context after function execution."""
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        
        @agent("cleanup_agent")
        def test_func(spore):
            return {"result": "ok"}
        
        spore = Mock()
        spore.knowledge = {}
        
        # Get and call the handler
        handler = mock_agent.set_spore_handler.call_args[0][0]
        handler(spore)
        
        # Context should be cleaned up after execution
        assert _agent_context.agent is None
        assert _agent_context.channel is None
    
    @patch('praval.decorators.Agent')
    def test_handler_resolves_knowledge_references_when_memory_enabled(self, mock_agent_class):
        """Test knowledge reference resolution for memory-enabled agents."""
        mock_agent = Mock()
        mock_agent.resolve_spore_knowledge.return_value = {"resolved": "data"}
        mock_agent_class.return_value = mock_agent
        
        @agent("memory_agent", memory=True)
        def test_func(spore):
            return {"result": spore.resolved_knowledge}
        
        # Create spore with knowledge references
        spore = Mock()
        spore.knowledge = {"type": "test"}
        spore.has_knowledge_references.return_value = True
        
        # Get and call the handler
        handler = mock_agent.set_spore_handler.call_args[0][0]
        handler(spore)
        
        # Verify knowledge resolution was called
        mock_agent.resolve_spore_knowledge.assert_called_once_with(spore)
        assert spore.resolved_knowledge == {"resolved": "data"}
    
    @patch('praval.decorators.Agent')
    def test_handler_stores_conversation_when_memory_enabled(self, mock_agent_class):
        """Test conversation storage for memory-enabled agents."""
        mock_memory = Mock()
        mock_agent = Mock()
        mock_agent.memory = mock_memory
        mock_agent_class.return_value = mock_agent
        
        @agent("memory_agent", memory=True)
        def test_func(spore):
            return {"response": "test"}
        
        spore = Mock()
        spore.knowledge = {"query": "test question"}
        spore.id = "spore123"
        spore.spore_type = SporeType.BROADCAST
        
        # Get and call the handler  
        handler = mock_agent.set_spore_handler.call_args[0][0]
        handler(spore)
        
        # Verify conversation turn was stored
        mock_memory.store_conversation_turn.assert_called_once_with(
            agent_id="memory_agent",
            user_message="{'query': 'test question'}",
            agent_response="{'response': 'test'}",
            context={"spore_id": "spore123", "spore_type": "broadcast"}
        )
    
    @patch('praval.decorators.Agent')
    def test_handler_auto_broadcast_when_enabled(self, mock_agent_class):
        """Test auto-broadcast functionality."""
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        
        @agent("broadcast_agent", channel="test_channel")
        def test_func(spore):
            return {"result": "success", "data": "test"}
        
        spore = Mock()
        spore.knowledge = {"type": "test"}
        
        with patch('time.time', return_value=1234567890):
            # Get and call the handler
            handler = mock_agent.set_spore_handler.call_args[0][0]
            handler(spore)
        
        # Verify broadcast was called with enriched data
        expected_data = {
            "result": "success",
            "data": "test", 
            "_from": "broadcast_agent",
            "_timestamp": 1234567890
        }
        mock_agent.broadcast_knowledge.assert_called_once_with(
            expected_data, 
            channel="test_channel"
        )
    
    @patch('praval.decorators.Agent')
    def test_handler_skips_broadcast_when_disabled(self, mock_agent_class):
        """Test that auto-broadcast is skipped when disabled."""
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        
        @agent("no_broadcast_agent", auto_broadcast=False)
        def test_func(spore):
            return {"result": "success"}
        
        spore = Mock()
        spore.knowledge = {"type": "test"}
        
        # Get and call the handler
        handler = mock_agent.set_spore_handler.call_args[0][0]
        handler(spore)
        
        # Verify no broadcast was made
        mock_agent.broadcast_knowledge.assert_not_called()
    
    @patch('praval.decorators.Agent')
    def test_handler_skips_broadcast_for_none_result(self, mock_agent_class):
        """Test that auto-broadcast is skipped when function returns None."""
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        
        @agent("none_result_agent")
        def test_func(spore):
            return None  # Explicitly return None
        
        spore = Mock()
        spore.knowledge = {"type": "test"}
        
        # Get and call the handler
        handler = mock_agent.set_spore_handler.call_args[0][0]
        handler(spore)
        
        # Verify no broadcast was made
        mock_agent.broadcast_knowledge.assert_not_called()
    
    @patch('praval.decorators.Agent')
    def test_handler_skips_broadcast_for_non_dict_result(self, mock_agent_class):
        """Test that auto-broadcast is skipped when result is not a dict."""
        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent
        
        @agent("string_result_agent") 
        def test_func(spore):
            return "just a string"
        
        spore = Mock()
        spore.knowledge = {"type": "test"}
        
        # Get and call the handler
        handler = mock_agent.set_spore_handler.call_args[0][0]
        handler(spore)
        
        # Verify no broadcast was made
        mock_agent.broadcast_knowledge.assert_not_called()


class TestChatFunction:
    """Test the chat() function with comprehensive coverage."""
    
    def setup_method(self):
        """Clean agent context before each test."""
        _agent_context.agent = None
        _agent_context.channel = None
    
    def test_chat_requires_agent_context(self):
        """Test that chat() raises error when called outside agent context."""
        with pytest.raises(RuntimeError, match="chat\\(\\) can only be used within @agent decorated functions"):
            chat("test message")
    
    def test_chat_works_within_agent_context(self):
        """Test that chat() works when called within agent context."""
        mock_agent = Mock()
        mock_agent.chat.return_value = "LLM response"
        
        _agent_context.agent = mock_agent
        _agent_context.channel = "test_channel"
        
        result = chat("test message")
        
        assert result == "LLM response"
        mock_agent.chat.assert_called_once_with("test message")
    
    def test_chat_with_timeout(self):
        """Test chat() timeout functionality."""
        mock_agent = Mock()
        mock_agent.chat.return_value = "Quick response"
        
        _agent_context.agent = mock_agent
        
        result = chat("test message", timeout=5.0)
        
        assert result == "Quick response"
        mock_agent.chat.assert_called_once_with("test message")
    
    def test_chat_timeout_raises_error(self):
        """Test that chat() raises TimeoutError on timeout."""
        mock_agent = Mock()
        
        def slow_chat(message):
            time.sleep(0.2)  # Simulate slow response
            return "Delayed response"
        
        mock_agent.chat.side_effect = slow_chat
        _agent_context.agent = mock_agent
        
        with pytest.raises(TimeoutError, match="LLM call timed out after 0.1 seconds"):
            chat("test message", timeout=0.1)
    
    @patch('concurrent.futures.ThreadPoolExecutor')
    def test_chat_uses_thread_pool_executor(self, mock_executor_class):
        """Test that chat() uses ThreadPoolExecutor for timeout handling."""
        mock_executor = Mock()
        mock_future = Mock()
        mock_future.result.return_value = "Thread result"
        mock_executor.submit.return_value = mock_future
        mock_executor.__enter__ = Mock(return_value=mock_executor)
        mock_executor.__exit__ = Mock(return_value=None)
        mock_executor_class.return_value = mock_executor
        
        mock_agent = Mock()
        _agent_context.agent = mock_agent
        
        result = chat("test message", timeout=5.0)
        
        assert result == "Thread result"
        mock_executor_class.assert_called_once_with(max_workers=1)
        mock_executor.submit.assert_called_once_with(mock_agent.chat, "test message")
        mock_future.result.assert_called_once_with(timeout=5.0)
    
    @patch('concurrent.futures.ThreadPoolExecutor')
    def test_chat_converts_concurrent_timeout_error(self, mock_executor_class):
        """Test that chat() converts concurrent.futures.TimeoutError to TimeoutError."""
        mock_executor = Mock()
        mock_future = Mock()
        mock_future.result.side_effect = FutureTimeoutError()
        mock_executor.submit.return_value = mock_future
        mock_executor.__enter__ = Mock(return_value=mock_executor)
        mock_executor.__exit__ = Mock(return_value=None)
        mock_executor_class.return_value = mock_executor
        
        mock_agent = Mock()
        _agent_context.agent = mock_agent
        
        with pytest.raises(TimeoutError, match="LLM call timed out after 3.0 seconds"):
            chat("test message", timeout=3.0)


class TestAChatFunction:
    """Test the achat() async function with comprehensive coverage."""
    
    def setup_method(self):
        """Clean agent context before each test."""
        _agent_context.agent = None
        _agent_context.channel = None
    
    @pytest.mark.asyncio
    async def test_achat_requires_agent_context(self):
        """Test that achat() raises error when called outside agent context."""
        with pytest.raises(RuntimeError, match="achat\\(\\) can only be used within @agent decorated functions"):
            await achat("test message")
    
    @pytest.mark.asyncio
    async def test_achat_works_within_agent_context(self):
        """Test that achat() works when called within agent context."""
        mock_agent = Mock()
        mock_agent.chat.return_value = "Async LLM response"
        
        _agent_context.agent = mock_agent
        _agent_context.channel = "test_channel"
        
        result = await achat("test message")
        
        assert result == "Async LLM response"
        mock_agent.chat.assert_called_once_with("test message")
    
    @pytest.mark.asyncio
    async def test_achat_with_timeout(self):
        """Test achat() timeout functionality."""
        mock_agent = Mock()
        mock_agent.chat.return_value = "Quick async response"
        
        _agent_context.agent = mock_agent
        
        result = await achat("test message", timeout=5.0)
        
        assert result == "Quick async response"
    
    @pytest.mark.asyncio
    async def test_achat_timeout_raises_error(self):
        """Test that achat() raises TimeoutError on timeout."""
        mock_agent = Mock()
        
        def slow_chat(message):
            time.sleep(0.2)  # Simulate slow response
            return "Delayed async response"
        
        mock_agent.chat.side_effect = slow_chat
        _agent_context.agent = mock_agent
        
        with pytest.raises(TimeoutError, match="LLM call timed out after 0.1 seconds"):
            await achat("test message", timeout=0.1)
    
    @pytest.mark.asyncio 
    @patch('asyncio.get_event_loop')
    @patch('asyncio.wait_for')
    async def test_achat_uses_event_loop_executor(self, mock_wait_for, mock_get_loop):
        """Test that achat() uses asyncio event loop executor."""
        mock_loop = Mock()
        mock_get_loop.return_value = mock_loop
        mock_wait_for.return_value = "Executor result"
        
        mock_agent = Mock()
        _agent_context.agent = mock_agent
        
        result = await achat("test message", timeout=3.0)
        
        assert result == "Executor result"
        mock_loop.run_in_executor.assert_called_once_with(None, mock_agent.chat, "test message")
        mock_wait_for.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('asyncio.wait_for')
    async def test_achat_converts_asyncio_timeout_error(self, mock_wait_for):
        """Test that achat() converts asyncio.TimeoutError to TimeoutError."""
        mock_wait_for.side_effect = asyncio.TimeoutError()
        
        mock_agent = Mock()
        _agent_context.agent = mock_agent
        
        with pytest.raises(TimeoutError, match="LLM call timed out after 2.5 seconds"):
            await achat("test message", timeout=2.5)


class TestBroadcastFunction:
    """Test the broadcast() function with comprehensive coverage."""
    
    def setup_method(self):
        """Clean agent context before each test."""
        _agent_context.agent = None
        _agent_context.channel = None
    
    def test_broadcast_requires_agent_context(self):
        """Test that broadcast() raises error when called outside agent context."""
        with pytest.raises(RuntimeError, match="broadcast\\(\\) can only be used within @agent decorated functions"):
            broadcast({"test": "data"})
    
    def test_broadcast_works_within_agent_context(self):
        """Test that broadcast() works when called within agent context."""
        mock_agent = Mock()
        mock_agent.broadcast_knowledge.return_value = "spore_id_123"

        _agent_context.agent = mock_agent
        _agent_context.channel = "test_channel"

        result = broadcast({"test": "data"})

        assert result == "spore_id_123"
        # broadcast() defaults to reef's default channel ('main') for agent chaining
        mock_agent.broadcast_knowledge.assert_called_once_with(
            {"test": "data"},
            channel="main"
        )
    
    def test_broadcast_with_custom_channel(self):
        """Test broadcast() with custom channel override."""
        mock_agent = Mock()
        mock_agent.broadcast_knowledge.return_value = "spore_id_456"
        
        _agent_context.agent = mock_agent
        _agent_context.channel = "default_channel"
        
        result = broadcast({"test": "data"}, channel="custom_channel")
        
        assert result == "spore_id_456"
        mock_agent.broadcast_knowledge.assert_called_once_with(
            {"test": "data"},
            channel="custom_channel"
        )
    
    def test_broadcast_adds_message_type(self):
        """Test that broadcast() adds message type to data."""
        mock_agent = Mock()
        mock_agent.broadcast_knowledge.return_value = "spore_id_789"

        _agent_context.agent = mock_agent
        _agent_context.channel = "test_channel"

        result = broadcast({"content": "hello"}, message_type="greeting")

        assert result == "spore_id_789"
        # broadcast() defaults to reef's default channel ('main') for agent chaining
        mock_agent.broadcast_knowledge.assert_called_once_with(
            {"content": "hello", "type": "greeting"},
            channel="main"
        )
    
    def test_broadcast_preserves_original_data(self):
        """Test that broadcast() doesn't modify the original data dict."""
        mock_agent = Mock()
        mock_agent.broadcast_knowledge.return_value = "spore_id_000"
        
        _agent_context.agent = mock_agent
        _agent_context.channel = "test_channel"
        
        original_data = {"content": "hello"}
        broadcast(original_data, message_type="greeting")
        
        # Original data should be unchanged
        assert original_data == {"content": "hello"}
        assert "type" not in original_data
    
    def test_broadcast_overwrites_existing_type(self):
        """Test that message_type parameter overwrites existing 'type' key."""
        mock_agent = Mock()
        mock_agent.broadcast_knowledge.return_value = "spore_id_111"

        _agent_context.agent = mock_agent
        _agent_context.channel = "test_channel"

        broadcast({"type": "old_type", "data": "test"}, message_type="new_type")

        # broadcast() defaults to reef's default channel ('main') for agent chaining
        mock_agent.broadcast_knowledge.assert_called_once_with(
            {"type": "new_type", "data": "test"},
            channel="main"
        )


class TestGetAgentInfo:
    """Test the get_agent_info() function with comprehensive coverage."""
    
    def test_get_agent_info_success(self):
        """Test get_agent_info() returns correct metadata."""
        @agent("info_agent", channel="info_channel", auto_broadcast=False, responds_to=["info"])
        def test_func(spore):
            return {"result": "info"}
        
        info = get_agent_info(test_func)
        
        expected = {
            "name": "info_agent",
            "channel": "info_channel", 
            "auto_broadcast": False,
            "responds_to": ["info"],
            "underlying_agent": test_func._praval_agent
        }
        assert info == expected
    
    def test_get_agent_info_with_defaults(self):
        """Test get_agent_info() with default values."""
        @agent("default_agent")
        def test_func(spore):
            return {"result": "default"}
        
        info = get_agent_info(test_func)
        
        assert info["name"] == "default_agent"
        assert info["channel"] == "default_agent_channel"
        assert info["auto_broadcast"] is True
        assert info["responds_to"] is None
        assert isinstance(info["underlying_agent"], Agent)
    
    def test_get_agent_info_non_decorated_function_raises_error(self):
        """Test that get_agent_info() raises error for non-decorated functions."""
        def regular_function():
            return "not an agent"
        
        with pytest.raises(ValueError, match="Function is not decorated with @agent"):
            get_agent_info(regular_function)
    
    def test_get_agent_info_none_input_raises_error(self):
        """Test that get_agent_info() handles None input appropriately."""
        with pytest.raises(ValueError, match="Function is not decorated with @agent"):
            get_agent_info(None)


class TestIntegrationScenarios:
    """Test complex integration scenarios for the decorator system."""
    
    def setup_method(self):
        """Clean agent context before each test."""
        _agent_context.agent = None
        _agent_context.channel = None
    
    def test_multiple_agents_different_configs(self):
        """Test creating multiple agents with different configurations."""
        @agent("agent1", memory=True, responds_to=["query"])
        def agent1_func(spore):
            return {"agent": "1"}
        
        @agent("agent2", memory=False, auto_broadcast=False)
        def agent2_func(spore):
            return {"agent": "2"}
        
        # Verify both agents have distinct configurations
        assert agent1_func._praval_name == "agent1"
        assert agent1_func._praval_memory_enabled is True
        assert agent1_func._praval_responds_to == ["query"]
        
        assert agent2_func._praval_name == "agent2"
        assert agent2_func._praval_memory_enabled is False
        assert agent2_func._praval_auto_broadcast is False
        
        # Verify they have different underlying agent instances
        assert agent1_func._praval_agent != agent2_func._praval_agent
    
    @patch('praval.decorators.Agent')
    def test_memory_enabled_agent_full_workflow(self, mock_agent_class):
        """Test complete workflow for memory-enabled agent."""
        mock_agent = Mock()
        mock_memory = Mock()
        mock_agent.memory = mock_memory
        mock_agent.resolve_spore_knowledge.return_value = {"resolved": True}
        mock_agent_class.return_value = mock_agent
        
        @agent("memory_workflow_agent", memory=True, auto_broadcast=True)
        def memory_agent(spore):
            # Simulate accessing resolved knowledge
            resolved = getattr(spore, 'resolved_knowledge', {})
            return {"processed": True, "resolved": resolved}
        
        # Create spore with knowledge references
        spore = Mock()
        spore.knowledge = {"query": "test"}
        spore.id = "test_spore"
        spore.spore_type = SporeType.BROADCAST
        spore.has_knowledge_references.return_value = True
        
        with patch('time.time', return_value=1234567890):
            # Get and call the handler
            handler = mock_agent.set_spore_handler.call_args[0][0]
            handler(spore)
        
        # Verify complete workflow
        mock_agent.resolve_spore_knowledge.assert_called_once_with(spore)
        mock_memory.store_conversation_turn.assert_called_once()
        mock_agent.broadcast_knowledge.assert_called_once()
        
        # Verify broadcast data includes resolved knowledge
        broadcast_call = mock_agent.broadcast_knowledge.call_args
        broadcast_data = broadcast_call[0][0]
        assert broadcast_data["processed"] is True
        assert broadcast_data["resolved"] == {"resolved": True}
        assert broadcast_data["_from"] == "memory_workflow_agent"
        assert broadcast_data["_timestamp"] == 1234567890


class TestErrorHandling:
    """Test error handling and edge cases in the decorator system."""
    
    def setup_method(self):
        """Clean agent context before each test."""
        _agent_context.agent = None
        _agent_context.channel = None
    
    @patch('praval.decorators.Agent')
    def test_memory_storage_error_doesnt_fail_agent(self, mock_agent_class):
        """Test that memory storage errors don't cause agent failure."""
        mock_agent = Mock()
        mock_memory = Mock()
        mock_memory.store_conversation_turn.side_effect = Exception("Memory error")
        mock_agent.memory = mock_memory
        mock_agent_class.return_value = mock_agent
        
        function_executed = False
        
        @agent("error_resilient_agent", memory=True)
        def test_agent(spore):
            nonlocal function_executed
            function_executed = True
            return {"result": "success"}
        
        spore = Mock()
        spore.knowledge = {"test": "data"}
        spore.id = "test_id"
        spore.spore_type = SporeType.BROADCAST
        
        # Get and call the handler - should not raise exception
        handler = mock_agent.set_spore_handler.call_args[0][0]
        handler(spore)
        
        # Function should still execute successfully
        assert function_executed is True
        mock_memory.store_conversation_turn.assert_called_once()
    
    @patch('praval.decorators.Agent')
    def test_knowledge_resolution_error_handling(self, mock_agent_class):
        """Test handling of knowledge resolution errors."""
        mock_agent = Mock()
        mock_agent.resolve_spore_knowledge.side_effect = Exception("Resolution error")
        mock_agent_class.return_value = mock_agent
        
        function_executed = False
        
        @agent("resolution_error_agent", memory=True)
        def test_agent(spore):
            nonlocal function_executed
            function_executed = True
            return {"result": "success"}
        
        spore = Mock()
        spore.knowledge = {"test": "data"}
        spore.has_knowledge_references.return_value = True
        
        # Get and call the handler - should handle error gracefully
        handler = mock_agent.set_spore_handler.call_args[0][0]
        
        # This should not raise an exception despite resolution error
        handler(spore)
        
        # Function should still execute
        assert function_executed is True
    
    def test_thread_local_context_isolation(self):
        """Test that agent context is properly isolated between threads."""
        context_results = {}
        
        def thread_function(thread_id, mock_agent):
            _agent_context.agent = mock_agent
            _agent_context.channel = f"channel_{thread_id}"
            
            # Small delay to allow context mixing if isolation is broken
            time.sleep(0.01)
            
            context_results[thread_id] = {
                "agent": _agent_context.agent,
                "channel": _agent_context.channel
            }
        
        # Create mock agents for different threads
        mock_agent1 = Mock()
        mock_agent1.name = "agent1"
        mock_agent2 = Mock() 
        mock_agent2.name = "agent2"
        
        # Run threads concurrently
        thread1 = threading.Thread(target=thread_function, args=(1, mock_agent1))
        thread2 = threading.Thread(target=thread_function, args=(2, mock_agent2))
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        # Verify context isolation
        assert context_results[1]["agent"] == mock_agent1
        assert context_results[1]["channel"] == "channel_1"
        assert context_results[2]["agent"] == mock_agent2  
        assert context_results[2]["channel"] == "channel_2"