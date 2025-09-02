"""
Unit tests for Praval Tool System.

Tests the tool registry, @tool decorator, and integration with agents.
"""

import pytest
from unittest.mock import Mock, patch
from typing import List

from praval.tools import (
    tool, get_tool_info, is_tool, list_tools, register_tool_with_agent,
    unregister_tool_from_agent, ToolCollection
)
from praval.core.tool_registry import (
    ToolRegistry, Tool, ToolMetadata, get_tool_registry, reset_tool_registry
)
from praval.core.exceptions import ToolError


class TestToolMetadata:
    """Test ToolMetadata class."""
    
    def test_tool_metadata_creation(self):
        """Test creating tool metadata."""
        metadata = ToolMetadata(
            tool_name="test_tool",
            owned_by="test_agent",
            description="A test tool",
            category="testing",
            shared=True,
            tags=["test", "demo"]
        )
        
        assert metadata.tool_name == "test_tool"
        assert metadata.owned_by == "test_agent"
        assert metadata.description == "A test tool"
        assert metadata.category == "testing"
        assert metadata.shared is True
        assert metadata.tags == ["test", "demo"]
    
    def test_tool_metadata_defaults(self):
        """Test tool metadata with default values."""
        metadata = ToolMetadata(tool_name="simple_tool")
        
        assert metadata.tool_name == "simple_tool"
        assert metadata.owned_by is None
        assert metadata.description == ""
        assert metadata.category == "general"
        assert metadata.shared is False
        assert metadata.version == "1.0.0"
        assert metadata.author == ""
        assert metadata.tags == []


class TestTool:
    """Test Tool class."""
    
    def test_tool_creation(self):
        """Test creating a Tool instance."""
        def sample_func(x: int, y: int) -> int:
            """Add two numbers."""
            return x + y
        
        metadata = ToolMetadata(tool_name="add", description="Add two numbers")
        tool_instance = Tool(sample_func, metadata)
        
        assert tool_instance.func == sample_func
        assert tool_instance.metadata == metadata
        assert tool_instance.metadata.parameters["x"]["type"] == "int"
        assert tool_instance.metadata.parameters["y"]["type"] == "int"
        assert tool_instance.metadata.return_type == "int"
    
    def test_tool_validation_missing_type_hints(self):
        """Test that tools without type hints raise ToolError."""
        def bad_func(x, y):  # No type hints
            return x + y
        
        metadata = ToolMetadata(tool_name="bad_tool")
        
        with pytest.raises(ToolError, match="must have a type hint"):
            Tool(bad_func, metadata)
    
    def test_tool_validation_missing_return_type(self):
        """Test that tools without return type hint raise ToolError."""
        def bad_func(x: int, y: int):  # No return type
            return x + y
        
        metadata = ToolMetadata(tool_name="bad_tool")
        
        with pytest.raises(ToolError, match="must have a return type hint"):
            Tool(bad_func, metadata)
    
    def test_tool_execution(self):
        """Test tool execution."""
        def add_func(x: int, y: int) -> int:
            return x + y
        
        metadata = ToolMetadata(tool_name="add")
        tool_instance = Tool(add_func, metadata)
        
        result = tool_instance.execute(5, 3)
        assert result == 8
    
    def test_tool_execution_error(self):
        """Test tool execution error handling."""
        def error_func(x: int) -> int:
            raise ValueError("Test error")
        
        metadata = ToolMetadata(tool_name="error_tool")
        tool_instance = Tool(error_func, metadata)
        
        with pytest.raises(ToolError, match="execution failed"):
            tool_instance.execute(5)
    
    def test_tool_to_dict(self):
        """Test tool serialization to dictionary."""
        def sample_func(x: int, y: str) -> bool:
            return True
        
        metadata = ToolMetadata(
            tool_name="test_tool",
            owned_by="agent1",
            description="Test tool",
            category="testing",
            shared=True,
            tags=["test"]
        )
        tool_instance = Tool(sample_func, metadata)
        
        tool_dict = tool_instance.to_dict()
        
        assert tool_dict["tool_name"] == "test_tool"
        assert tool_dict["owned_by"] == "agent1"
        assert tool_dict["description"] == "Test tool"
        assert tool_dict["category"] == "testing"
        assert tool_dict["shared"] is True
        assert tool_dict["tags"] == ["test"]
        assert tool_dict["return_type"] == "bool"
        assert "x" in tool_dict["parameters"]
        assert "y" in tool_dict["parameters"]


class TestToolRegistry:
    """Test ToolRegistry class."""
    
    def setup_method(self):
        """Setup for each test method."""
        self.registry = ToolRegistry()
        
        # Create sample tools
        def add_func(x: int, y: int) -> int:
            return x + y
        
        def multiply_func(x: float, y: float) -> float:
            return x * y
        
        def shared_func(msg: str) -> str:
            return f"Shared: {msg}"
        
        self.add_metadata = ToolMetadata(tool_name="add", owned_by="calculator")
        self.multiply_metadata = ToolMetadata(tool_name="multiply", owned_by="calculator", category="math")
        self.shared_metadata = ToolMetadata(tool_name="shared_tool", shared=True, category="utility")
        
        self.add_tool = Tool(add_func, self.add_metadata)
        self.multiply_tool = Tool(multiply_func, self.multiply_metadata)
        self.shared_tool = Tool(shared_func, self.shared_metadata)
    
    def test_register_tool(self):
        """Test tool registration."""
        self.registry.register_tool(self.add_tool)
        
        retrieved = self.registry.get_tool("add")
        assert retrieved is not None
        assert retrieved.metadata.tool_name == "add"
    
    def test_register_duplicate_tool(self):
        """Test registering duplicate tool raises error."""
        self.registry.register_tool(self.add_tool)
        
        with pytest.raises(ToolError, match="already registered"):
            self.registry.register_tool(self.add_tool)
    
    def test_get_tools_for_agent(self):
        """Test getting tools for specific agent."""
        self.registry.register_tool(self.add_tool)
        self.registry.register_tool(self.multiply_tool)
        self.registry.register_tool(self.shared_tool)
        
        agent_tools = self.registry.get_tools_for_agent("calculator")
        tool_names = [tool.metadata.tool_name for tool in agent_tools]
        
        # Should include owned tools and shared tools
        assert "add" in tool_names
        assert "multiply" in tool_names
        assert "shared_tool" in tool_names
        assert len(agent_tools) == 3
    
    def test_get_tools_by_category(self):
        """Test getting tools by category."""
        self.registry.register_tool(self.add_tool)
        self.registry.register_tool(self.multiply_tool)
        self.registry.register_tool(self.shared_tool)
        
        math_tools = self.registry.get_tools_by_category("math")
        utility_tools = self.registry.get_tools_by_category("utility")
        
        assert len(math_tools) == 1
        assert math_tools[0].metadata.tool_name == "multiply"
        
        assert len(utility_tools) == 1
        assert utility_tools[0].metadata.tool_name == "shared_tool"
    
    def test_get_shared_tools(self):
        """Test getting shared tools."""
        self.registry.register_tool(self.add_tool)
        self.registry.register_tool(self.shared_tool)
        
        shared_tools = self.registry.get_shared_tools()
        assert len(shared_tools) == 1
        assert shared_tools[0].metadata.tool_name == "shared_tool"
    
    def test_assign_tool_to_agent(self):
        """Test runtime tool assignment."""
        self.registry.register_tool(self.add_tool)
        
        success = self.registry.assign_tool_to_agent("add", "other_agent")
        assert success is True
        
        other_agent_tools = self.registry.get_tools_for_agent("other_agent")
        tool_names = [tool.metadata.tool_name for tool in other_agent_tools]
        assert "add" in tool_names
    
    def test_assign_nonexistent_tool(self):
        """Test assigning nonexistent tool returns False."""
        success = self.registry.assign_tool_to_agent("nonexistent", "agent")
        assert success is False
    
    def test_remove_tool_from_agent(self):
        """Test removing tool assignment from agent."""
        self.registry.register_tool(self.add_tool)
        self.registry.assign_tool_to_agent("add", "other_agent")
        
        success = self.registry.remove_tool_from_agent("add", "other_agent")
        assert success is True
        
        other_agent_tools = self.registry.get_tools_for_agent("other_agent")
        tool_names = [tool.metadata.tool_name for tool in other_agent_tools]
        assert "add" not in tool_names
    
    def test_unregister_tool(self):
        """Test tool unregistration."""
        self.registry.register_tool(self.add_tool)
        
        success = self.registry.unregister_tool("add")
        assert success is True
        
        retrieved = self.registry.get_tool("add")
        assert retrieved is None
    
    def test_search_tools(self):
        """Test tool search functionality."""
        self.registry.register_tool(self.add_tool)
        self.registry.register_tool(self.multiply_tool)
        self.registry.register_tool(self.shared_tool)
        
        # Search by name pattern
        results = self.registry.search_tools(name_pattern="add")
        assert len(results) == 1
        assert results[0].metadata.tool_name == "add"
        
        # Search by category
        results = self.registry.search_tools(category="math")
        assert len(results) == 1
        assert results[0].metadata.tool_name == "multiply"
        
        # Search by owner
        results = self.registry.search_tools(owned_by="calculator")
        assert len(results) == 2
        
        # Search shared only
        results = self.registry.search_tools(shared_only=True)
        assert len(results) == 1
        assert results[0].metadata.tool_name == "shared_tool"
    
    def test_get_registry_stats(self):
        """Test registry statistics."""
        self.registry.register_tool(self.add_tool)
        self.registry.register_tool(self.multiply_tool)
        self.registry.register_tool(self.shared_tool)
        
        stats = self.registry.get_registry_stats()
        
        assert stats["total_tools"] == 3
        assert stats["shared_tools"] == 1
        assert stats["agents_with_tools"] == 1
        assert stats["categories"] == 2


class TestToolDecorator:
    """Test @tool decorator."""
    
    def setup_method(self):
        """Setup for each test method."""
        reset_tool_registry()
    
    def test_basic_tool_decoration(self):
        """Test basic @tool decorator usage."""
        @tool("test_add", owned_by="calculator")
        def add_numbers(x: int, y: int) -> int:
            """Add two numbers."""
            return x + y
        
        # Check tool was registered
        registry = get_tool_registry()
        tool_instance = registry.get_tool("test_add")
        assert tool_instance is not None
        assert tool_instance.metadata.owned_by == "calculator"
        
        # Check function still works
        result = add_numbers(5, 3)
        assert result == 8
        
        # Check tool metadata attached to function
        assert hasattr(add_numbers, '_praval_tool')
        assert add_numbers._praval_tool_name == "test_add"
    
    def test_tool_auto_naming(self):
        """Test tool auto-naming from function name."""
        @tool(owned_by="calculator")
        def multiply_numbers(x: int, y: int) -> int:
            return x * y
        
        registry = get_tool_registry()
        tool_instance = registry.get_tool("multiply_numbers")
        assert tool_instance is not None
    
    def test_tool_auto_description(self):
        """Test tool auto-description from docstring."""
        @tool("test_tool")
        def sample_function(x: int) -> int:
            """This is a sample function for testing."""
            return x * 2
        
        registry = get_tool_registry()
        tool_instance = registry.get_tool("test_tool")
        assert tool_instance.metadata.description == "This is a sample function for testing."
    
    def test_shared_tool(self):
        """Test shared tool creation."""
        @tool("shared_logger", shared=True, category="utility")
        def log_message(level: str, message: str) -> str:
            return f"{level}: {message}"
        
        registry = get_tool_registry()
        tool_instance = registry.get_tool("shared_logger")
        assert tool_instance.metadata.shared is True
        assert tool_instance.metadata.category == "utility"
        
        shared_tools = registry.get_shared_tools()
        assert len(shared_tools) == 1
        assert shared_tools[0].metadata.tool_name == "shared_logger"
    
    def test_tool_with_metadata(self):
        """Test tool with full metadata."""
        @tool(
            "advanced_tool",
            owned_by="processor",
            description="Advanced processing tool",
            category="processing",
            version="2.0.0",
            author="Test Author",
            tags=["advanced", "processing"]
        )
        def advanced_function(data: str) -> bool:
            return len(data) > 0
        
        registry = get_tool_registry()
        tool_instance = registry.get_tool("advanced_tool")
        
        assert tool_instance.metadata.owned_by == "processor"
        assert tool_instance.metadata.description == "Advanced processing tool"
        assert tool_instance.metadata.category == "processing"
        assert tool_instance.metadata.version == "2.0.0"
        assert tool_instance.metadata.author == "Test Author"
        assert tool_instance.metadata.tags == ["advanced", "processing"]
    
    def test_tool_invalid_function(self):
        """Test tool decorator with invalid function."""
        with pytest.raises(ToolError):
            @tool("invalid_tool")
            def invalid_function(x, y):  # No type hints
                return x + y


class TestToolUtilities:
    """Test tool utility functions."""
    
    def setup_method(self):
        """Setup for each test method."""
        reset_tool_registry()
    
    def test_get_tool_info(self):
        """Test get_tool_info function."""
        @tool("info_tool", owned_by="agent1")
        def info_function(x: int) -> str:
            """Info function."""
            return str(x)
        
        info = get_tool_info(info_function)
        
        assert info["tool_name"] == "info_tool"
        assert info["owned_by"] == "agent1"
        assert info["description"] == "Info function."
    
    def test_get_tool_info_non_tool(self):
        """Test get_tool_info with non-tool function."""
        def regular_function(x: int) -> int:
            return x * 2
        
        with pytest.raises(ValueError, match="not decorated with @tool"):
            get_tool_info(regular_function)
    
    def test_is_tool(self):
        """Test is_tool function."""
        @tool("check_tool")
        def tool_function(x: int) -> int:
            return x
        
        def regular_function(x: int) -> int:
            return x
        
        assert is_tool(tool_function) is True
        assert is_tool(regular_function) is False
    
    def test_list_tools(self):
        """Test list_tools function."""
        @tool("tool1", owned_by="agent1")
        def func1(x: int) -> int:
            return x
        
        @tool("tool2", category="math")
        def func2(x: int) -> int:
            return x
        
        @tool("tool3", shared=True)
        def func3(x: int) -> int:
            return x
        
        # List all tools
        all_tools = list_tools()
        assert len(all_tools) == 3
        
        # List by agent
        agent_tools = list_tools(agent_name="agent1")
        assert len(agent_tools) == 2  # owned + shared
        
        # List by category
        math_tools = list_tools(category="math")
        assert len(math_tools) == 1
        
        # List shared only
        shared_tools = list_tools(shared_only=True)
        assert len(shared_tools) == 1
    
    def test_register_tool_with_agent(self):
        """Test register_tool_with_agent function."""
        @tool("runtime_tool")
        def runtime_function(x: int) -> int:
            return x
        
        success = register_tool_with_agent("runtime_tool", "new_agent")
        assert success is True
        
        registry = get_tool_registry()
        agent_tools = registry.get_tools_for_agent("new_agent")
        tool_names = [tool.metadata.tool_name for tool in agent_tools]
        assert "runtime_tool" in tool_names
    
    def test_unregister_tool_from_agent(self):
        """Test unregister_tool_from_agent function."""
        @tool("removable_tool")
        def removable_function(x: int) -> int:
            return x
        
        register_tool_with_agent("removable_tool", "test_agent")
        success = unregister_tool_from_agent("removable_tool", "test_agent")
        assert success is True
        
        registry = get_tool_registry()
        agent_tools = registry.get_tools_for_agent("test_agent")
        tool_names = [tool.metadata.tool_name for tool in agent_tools]
        assert "removable_tool" not in tool_names


class TestToolCollection:
    """Test ToolCollection class."""
    
    def setup_method(self):
        """Setup for each test method."""
        reset_tool_registry()
        
        @tool("collection_tool1")
        def func1(x: int) -> int:
            return x
        
        @tool("collection_tool2") 
        def func2(x: int) -> int:
            return x
        
        self.collection = ToolCollection("math_tools", "Mathematical tools")
    
    def test_collection_creation(self):
        """Test tool collection creation."""
        assert self.collection.name == "math_tools"
        assert self.collection.description == "Mathematical tools"
        assert len(self.collection.tools) == 0
    
    def test_add_tool_to_collection(self):
        """Test adding tool to collection."""
        self.collection.add_tool("collection_tool1")
        assert "collection_tool1" in self.collection.tools
        assert len(self.collection.tools) == 1
    
    def test_add_nonexistent_tool(self):
        """Test adding nonexistent tool raises error."""
        with pytest.raises(ToolError, match="not found"):
            self.collection.add_tool("nonexistent_tool")
    
    def test_remove_tool_from_collection(self):
        """Test removing tool from collection."""
        self.collection.add_tool("collection_tool1")
        success = self.collection.remove_tool("collection_tool1")
        assert success is True
        assert "collection_tool1" not in self.collection.tools
    
    def test_assign_collection_to_agent(self):
        """Test assigning entire collection to agent."""
        self.collection.add_tool("collection_tool1")
        self.collection.add_tool("collection_tool2")
        
        count = self.collection.assign_to_agent("test_agent")
        assert count == 2
        
        registry = get_tool_registry()
        agent_tools = registry.get_tools_for_agent("test_agent")
        tool_names = [tool.metadata.tool_name for tool in agent_tools]
        assert "collection_tool1" in tool_names
        assert "collection_tool2" in tool_names
    
    def test_get_collection_tools(self):
        """Test getting tools from collection."""
        self.collection.add_tool("collection_tool1")
        self.collection.add_tool("collection_tool2")
        
        tools = self.collection.get_tools()
        assert len(tools) == 2
        tool_names = [tool.metadata.tool_name for tool in tools]
        assert "collection_tool1" in tool_names
        assert "collection_tool2" in tool_names


class TestGlobalRegistry:
    """Test global registry functions."""
    
    def test_get_tool_registry_singleton(self):
        """Test that get_tool_registry returns singleton."""
        registry1 = get_tool_registry()
        registry2 = get_tool_registry()
        assert registry1 is registry2
    
    def test_reset_tool_registry(self):
        """Test resetting global registry."""
        registry1 = get_tool_registry()
        
        @tool("temp_tool")
        def temp_func(x: int) -> int:
            return x
        
        assert len(registry1.list_all_tools()) == 1
        
        reset_tool_registry()
        registry2 = get_tool_registry()
        
        # Should be new instance with no tools
        assert len(registry2.list_all_tools()) == 0
        assert registry1 is not registry2