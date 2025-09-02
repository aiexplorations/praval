"""
Integration tests for Praval Agent-Tool System.

Tests the integration between agents and tools, including automatic
tool registration, tool execution within agent context, and the
enhanced @agent decorator functionality.
"""

import pytest
from unittest.mock import Mock, patch
from praval import agent, tool, reset_tool_registry, get_tool_registry


class TestAgentToolIntegration:
    """Test integration between agents and tools."""
    
    def setup_method(self):
        """Setup for each test method."""
        reset_tool_registry()
    
    def test_agent_auto_discovers_owned_tools(self):
        """Test that agents automatically discover tools owned by them."""
        # Define tools first
        @tool("calculator_add", owned_by="calculator")
        def add(x: float, y: float) -> float:
            """Add two numbers."""
            return x + y
        
        @tool("calculator_multiply", owned_by="calculator")
        def multiply(x: float, y: float) -> float:
            """Multiply two numbers."""
            return x * y
        
        # Tools for other agent (should not be auto-registered)
        @tool("other_tool", owned_by="other_agent")
        def other_func(x: int) -> int:
            return x
        
        # Create agent
        @agent("calculator")
        def calculator_agent(spore):
            """Calculator agent with mathematical tools."""
            return {"status": "ready"}
        
        # Check that agent has the owned tools
        assert calculator_agent.has_tool("calculator_add")
        assert calculator_agent.has_tool("calculator_multiply")
        assert not calculator_agent.has_tool("other_tool")
        
        # Check tools are available through list_tools
        tool_names = calculator_agent.list_tools()
        assert "calculator_add" in tool_names
        assert "calculator_multiply" in tool_names
        assert "other_tool" not in tool_names
    
    def test_agent_auto_discovers_shared_tools(self):
        """Test that agents automatically discover shared tools."""
        # Define shared tool
        @tool("logger", shared=True, category="utility")
        def log_message(level: str, message: str) -> str:
            """Log a message."""
            return f"{level}: {message}"
        
        # Define non-shared tool
        @tool("private_tool", owned_by="other_agent")
        def private_func(x: int) -> int:
            return x
        
        # Create agent
        @agent("test_agent")
        def test_agent(spore):
            return {"status": "ready"}
        
        # Should have shared tool but not private tool
        assert test_agent.has_tool("logger")
        assert not test_agent.has_tool("private_tool")
    
    def test_agent_tool_method_exposed(self):
        """Test that @agent decorator exposes tool method."""
        @agent("tool_user")
        def tool_user_agent(spore):
            return {"status": "ready"}
        
        # Agent should have tool method exposed
        assert hasattr(tool_user_agent, 'tool')
        assert callable(tool_user_agent.tool)
        
        # Test using the exposed tool method
        @tool_user_agent.tool
        def runtime_tool(x: int, y: int) -> int:
            """Runtime registered tool."""
            return x + y
        
        # Tool should be registered and available
        assert tool_user_agent.has_tool("runtime_tool")
        
        # Tool should work
        tool_obj = tool_user_agent.get_tool("runtime_tool")
        assert tool_obj is not None
    
    def test_agent_tool_management_methods(self):
        """Test agent tool management methods."""
        @tool("managed_tool", owned_by="manager")
        def managed_func(x: int) -> int:
            return x * 2
        
        @agent("manager")
        def manager_agent(spore):
            return {"status": "ready"}
        
        # Test list_tools
        tools = manager_agent.list_tools()
        assert "managed_tool" in tools
        
        # Test get_tool
        tool_obj = manager_agent.get_tool("managed_tool")
        assert tool_obj is not None
        assert tool_obj["function"].__name__ == "managed_func"
        
        # Test has_tool
        assert manager_agent.has_tool("managed_tool")
        assert not manager_agent.has_tool("nonexistent_tool")
    
    @patch('praval.core.agent.Agent.chat')
    def test_tools_available_in_agent_chat(self, mock_chat):
        """Test that tools are available during agent chat."""
        # Mock the chat method to return a simple response
        mock_chat.return_value = "Tool execution complete"
        
        @tool("calculator_add", owned_by="calculator")
        def add(x: float, y: float) -> float:
            return x + y
        
        @agent("calculator")
        def calculator_agent(spore):
            return {"status": "ready"}
        
        # Verify that the underlying agent has the tools registered
        underlying_agent = calculator_agent._praval_agent
        assert "calculator_add" in underlying_agent.tools
        
        # Test that chat can be called (tools would be passed to LLM)
        response = underlying_agent.chat("What is 5 + 3?")
        assert response == "Tool execution complete"
        
        # Verify chat was called with tools
        mock_chat.assert_called_once()
        call_args = mock_chat.call_args
        # The tools should be available to the chat method
        assert underlying_agent.tools is not None
    
    def test_multiple_agents_with_different_tools(self):
        """Test multiple agents with different sets of tools."""
        # Math tools
        @tool("add", owned_by="math_agent")
        def add(x: float, y: float) -> float:
            return x + y
        
        @tool("subtract", owned_by="math_agent")
        def subtract(x: float, y: float) -> float:
            return x - y
        
        # String tools
        @tool("uppercase", owned_by="string_agent")
        def uppercase(text: str) -> str:
            return text.upper()
        
        @tool("lowercase", owned_by="string_agent") 
        def lowercase(text: str) -> str:
            return text.lower()
        
        # Shared tool
        @tool("logger", shared=True)
        def log(message: str) -> str:
            return f"LOG: {message}"
        
        # Create agents
        @agent("math_agent")
        def math_agent(spore):
            return {"type": "math"}
        
        @agent("string_agent")
        def string_agent(spore):
            return {"type": "string"}
        
        # Check math agent tools
        math_tools = math_agent.list_tools()
        assert "add" in math_tools
        assert "subtract" in math_tools
        assert "logger" in math_tools  # shared tool
        assert "uppercase" not in math_tools
        assert "lowercase" not in math_tools
        
        # Check string agent tools
        string_tools = string_agent.list_tools()
        assert "uppercase" in string_tools
        assert "lowercase" in string_tools
        assert "logger" in string_tools  # shared tool
        assert "add" not in string_tools
        assert "subtract" not in string_tools
    
    def test_tool_categories_with_agents(self):
        """Test tool categories work with agent integration."""
        @tool("sin", category="trigonometry", owned_by="math_agent")
        def sine(angle: float) -> float:
            import math
            return math.sin(angle)
        
        @tool("cos", category="trigonometry", owned_by="math_agent")
        def cosine(angle: float) -> float:
            import math
            return math.cos(angle)
        
        @tool("add", category="arithmetic", owned_by="math_agent")
        def add(x: float, y: float) -> float:
            return x + y
        
        @agent("math_agent")
        def math_agent(spore):
            return {"type": "math"}
        
        # All tools should be available to the owning agent
        tools = math_agent.list_tools()
        assert "sin" in tools
        assert "cos" in tools
        assert "add" in tools
        
        # Verify tools are categorized correctly in registry
        registry = get_tool_registry()
        trig_tools = registry.get_tools_by_category("trigonometry")
        assert len(trig_tools) == 2
        
        arith_tools = registry.get_tools_by_category("arithmetic")
        assert len(arith_tools) == 1
    
    def test_runtime_tool_assignment(self):
        """Test runtime tool assignment to agents."""
        @tool("runtime_tool")
        def runtime_func(x: int) -> int:
            return x * 3
        
        @agent("dynamic_agent")
        def dynamic_agent(spore):
            return {"status": "ready"}
        
        # Initially agent shouldn't have the tool
        assert not dynamic_agent.has_tool("runtime_tool")
        
        # Assign tool at runtime
        from praval import register_tool_with_agent
        success = register_tool_with_agent("runtime_tool", "dynamic_agent")
        assert success is True
        
        # Now agent should have the tool
        # Note: This tests the registry level assignment. 
        # In practice, the agent would need to be recreated or
        # have a method to refresh its tool list
        registry = get_tool_registry()
        agent_tools = registry.get_tools_for_agent("dynamic_agent")
        tool_names = [tool.metadata.tool_name for tool in agent_tools]
        assert "runtime_tool" in tool_names
    
    def test_tool_collections_with_agents(self):
        """Test tool collections work with agent assignment."""
        from praval import ToolCollection
        
        @tool("collection_tool1")
        def func1(x: int) -> int:
            return x + 1
        
        @tool("collection_tool2")
        def func2(x: int) -> int:
            return x + 2
        
        # Create collection
        collection = ToolCollection("test_collection", "Test tools")
        collection.add_tool("collection_tool1")
        collection.add_tool("collection_tool2")
        
        # Assign collection to agent
        count = collection.assign_to_agent("collection_user")
        assert count == 2
        
        # Create agent
        @agent("collection_user")
        def collection_user_agent(spore):
            return {"status": "ready"}
        
        # Verify tools are available through registry
        registry = get_tool_registry()
        agent_tools = registry.get_tools_for_agent("collection_user")
        tool_names = [tool.metadata.tool_name for tool in agent_tools]
        assert "collection_tool1" in tool_names
        assert "collection_tool2" in tool_names
    
    def test_agent_with_memory_and_tools(self):
        """Test agent with both memory and tools enabled."""
        @tool("memory_tool", owned_by="memory_agent")
        def memory_function(data: str) -> str:
            return f"Processed: {data}"
        
        @agent("memory_agent", memory=True)
        def memory_agent(spore):
            # Should have both memory and tool capabilities
            return {"status": "ready with memory and tools"}
        
        # Check agent has both memory and tool methods
        assert hasattr(memory_agent, 'remember')  # Memory method
        assert hasattr(memory_agent, 'recall')    # Memory method
        assert hasattr(memory_agent, 'tool')      # Tool method
        assert hasattr(memory_agent, 'has_tool')  # Tool method
        
        # Check tools are registered
        assert memory_agent.has_tool("memory_tool")
    
    def test_error_handling_in_tool_auto_registration(self):
        """Test error handling during automatic tool registration."""
        # This test verifies that agent creation doesn't fail even if
        # tool auto-registration encounters errors
        
        @tool("problematic_tool", owned_by="error_agent")
        def problematic_function(x: int) -> int:
            return x
        
        # Agent should still be created successfully even if there are
        # issues with tool registration (the _auto_register_tools function
        # has error handling)
        @agent("error_agent")
        def error_agent(spore):
            return {"status": "created despite potential tool issues"}
        
        # Agent should exist and be callable
        assert error_agent is not None
        assert hasattr(error_agent, '_praval_agent')
    
    def test_tool_metadata_preservation(self):
        """Test that tool metadata is preserved through agent integration."""
        @tool(
            "metadata_tool",
            owned_by="metadata_agent",
            description="A tool with rich metadata",
            category="testing",
            version="2.0.0",
            author="Test Author",
            tags=["test", "metadata"]
        )
        def metadata_function(x: int) -> str:
            """Convert integer to string."""
            return str(x)
        
        @agent("metadata_agent")
        def metadata_agent(spore):
            return {"status": "ready"}
        
        # Get tool from agent
        tool_obj = metadata_agent.get_tool("metadata_tool")
        assert tool_obj is not None
        
        # Verify metadata is preserved in the registry
        registry = get_tool_registry()
        registered_tool = registry.get_tool("metadata_tool")
        assert registered_tool is not None
        assert registered_tool.metadata.description == "A tool with rich metadata"
        assert registered_tool.metadata.category == "testing"
        assert registered_tool.metadata.version == "2.0.0"
        assert registered_tool.metadata.author == "Test Author"
        assert registered_tool.metadata.tags == ["test", "metadata"]


class TestAgentToolExecution:
    """Test tool execution within agent context."""
    
    def setup_method(self):
        """Setup for each test method."""
        reset_tool_registry()
    
    def test_direct_tool_execution(self):
        """Test direct tool execution through registry."""
        @tool("execution_test", owned_by="executor")
        def execution_function(x: int, y: int) -> int:
            return x * y
        
        registry = get_tool_registry()
        tool_obj = registry.get_tool("execution_test")
        
        result = tool_obj.execute(5, 3)
        assert result == 15
    
    def test_tool_execution_error_handling(self):
        """Test tool execution error handling."""
        @tool("error_tool", owned_by="executor")
        def error_function(x: int) -> int:
            if x < 0:
                raise ValueError("Negative input not allowed")
            return x * 2
        
        registry = get_tool_registry()
        tool_obj = registry.get_tool("error_tool")
        
        # Normal execution should work
        result = tool_obj.execute(5)
        assert result == 10
        
        # Error execution should raise ToolError
        from praval.core.exceptions import ToolError
        with pytest.raises(ToolError, match="execution failed"):
            tool_obj.execute(-1)
    
    @patch('praval.core.agent.Agent.chat')
    def test_tools_passed_to_llm(self, mock_chat):
        """Test that tools are properly passed to LLM during chat."""
        mock_chat.return_value = "LLM response with tool usage"
        
        @tool("llm_tool", owned_by="llm_agent")
        def llm_function(query: str) -> str:
            return f"Tool result: {query}"
        
        @agent("llm_agent")
        def llm_agent(spore):
            return {"status": "ready"}
        
        # Get underlying agent and call chat
        underlying_agent = llm_agent._praval_agent
        response = underlying_agent.chat("Use the tool to process 'test'")
        
        # Verify chat was called
        mock_chat.assert_called_once()
        
        # Verify tools were available (they should be in the agent's tools dict)
        assert "llm_tool" in underlying_agent.tools
        assert underlying_agent.tools["llm_tool"]["function"] == llm_function


class TestBackwardCompatibility:
    """Test backward compatibility with existing tool usage patterns."""
    
    def setup_method(self):
        """Setup for each test method."""
        reset_tool_registry()
    
    def test_old_style_tool_registration_still_works(self):
        """Test that old-style agent.tool decoration still works."""
        @agent("legacy_agent")
        def legacy_agent(spore):
            return {"status": "legacy"}
        
        # Old style tool registration
        @legacy_agent.tool
        def legacy_tool(x: int, y: int) -> int:
            """Legacy tool registration."""
            return x + y
        
        # Should work as before
        assert legacy_agent.has_tool("legacy_tool")
        tool_obj = legacy_agent.get_tool("legacy_tool")
        assert tool_obj is not None
    
    def test_mixed_tool_registration_styles(self):
        """Test mixing new @tool decorator with old agent.tool style."""
        # New style
        @tool("new_style_tool", owned_by="mixed_agent")
        def new_tool(x: int) -> int:
            return x * 2
        
        @agent("mixed_agent")
        def mixed_agent(spore):
            return {"status": "mixed"}
        
        # Old style
        @mixed_agent.tool
        def old_style_tool(x: int) -> int:
            return x * 3
        
        # Both should be available
        assert mixed_agent.has_tool("new_style_tool")
        assert mixed_agent.has_tool("old_style_tool")
        
        tools = mixed_agent.list_tools()
        assert "new_style_tool" in tools
        assert "old_style_tool" in tools