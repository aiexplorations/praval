"""
Tool decorator and utilities for Praval Framework.

This module provides the @tool decorator for creating tools that can be
registered and used by agents. Tools are automatically registered in the
global tool registry and can be associated with specific agents.
"""

import inspect
from typing import Optional, List, Callable, Union, Any
from functools import wraps

from .core.tool_registry import Tool, ToolMetadata, get_tool_registry, ToolRegistry
from .core.exceptions import ToolError


def tool(
    tool_name: Optional[str] = None,
    owned_by: Optional[str] = None,
    description: Optional[str] = None,
    category: str = "general",
    shared: bool = False,
    version: str = "1.0.0",
    author: str = "",
    tags: Optional[List[str]] = None
) -> Callable:
    """
    Decorator to register a function as a tool in the Praval framework.
    
    The @tool decorator automatically registers functions as tools that can
    be used by agents. Tools can be owned by specific agents, shared across
    all agents, or organized by category.
    
    Args:
        tool_name: Name of the tool (defaults to function name)
        owned_by: Agent that owns this tool
        description: Description of what the tool does (defaults to docstring)
        category: Category for organizing tools
        shared: Whether this tool is available to all agents
        version: Version of the tool
        author: Author of the tool
        tags: Tags for tool discovery
        
    Returns:
        Decorated function with tool metadata attached
        
    Raises:
        ToolError: If tool registration fails or validation errors occur
        
    Examples:
        Basic tool owned by specific agent:
        ```python
        @tool("add_numbers", owned_by="calculator")
        def add(x: float, y: float) -> float:
            '''Add two numbers together.'''
            return x + y
        ```
        
        Shared tool available to all agents:
        ```python
        @tool("logger", shared=True, category="utility")
        def log_message(level: str, message: str) -> str:
            '''Log a message at the specified level.'''
            import logging
            logger = logging.getLogger("praval.tools")
            getattr(logger, level.lower())(message)
            return f"Logged: {message}"
        ```
        
        Tool with metadata:
        ```python
        @tool(
            "validate_email",
            owned_by="data_processor", 
            category="validation",
            tags=["email", "validation", "data"],
            version="2.0.0",
            author="Praval Team"
        )
        def validate_email(email: str) -> bool:
            '''Validate email address format.'''
            import re
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
            return bool(re.match(pattern, email))
        ```
    """
    def decorator(func: Callable) -> Callable:
        # Auto-generate tool name from function name if not provided
        actual_tool_name = tool_name or func.__name__
        
        # Auto-generate description from docstring if not provided
        actual_description = description
        if not actual_description and func.__doc__:
            actual_description = func.__doc__.strip()
        
        # Prepare tags list
        actual_tags = tags or []
        
        # Create tool metadata
        metadata = ToolMetadata(
            tool_name=actual_tool_name,
            owned_by=owned_by,
            description=actual_description or "",
            category=category,
            shared=shared,
            version=version,
            author=author,
            tags=actual_tags
        )
        
        # Create tool instance
        try:
            tool_instance = Tool(func, metadata)
        except Exception as e:
            raise ToolError(f"Failed to create tool '{actual_tool_name}': {str(e)}") from e
        
        # Register the tool in the global registry
        registry = get_tool_registry()
        try:
            registry.register_tool(tool_instance)
        except Exception as e:
            raise ToolError(f"Failed to register tool '{actual_tool_name}': {str(e)}") from e
        
        # Add tool metadata to the function for introspection
        func._praval_tool = tool_instance
        func._praval_tool_name = actual_tool_name
        func._praval_tool_metadata = metadata
        
        # Add utility methods to the function
        func.get_metadata = lambda: metadata
        func.get_tool_info = lambda: tool_instance.to_dict()
        func.execute_as_tool = tool_instance.execute
        
        return func
    
    return decorator


def get_tool_info(tool_func: Callable) -> dict:
    """
    Get information about a @tool decorated function.
    
    Args:
        tool_func: Function decorated with @tool
        
    Returns:
        Dictionary with tool metadata
        
    Raises:
        ValueError: If function is not decorated with @tool
    """
    if not hasattr(tool_func, '_praval_tool'):
        raise ValueError("Function is not decorated with @tool")
    
    return tool_func._praval_tool.to_dict()


def is_tool(func: Callable) -> bool:
    """
    Check if a function is decorated with @tool.
    
    Args:
        func: Function to check
        
    Returns:
        True if function is a tool, False otherwise
    """
    return hasattr(func, '_praval_tool')


def discover_tools(
    module: Optional[str] = None,
    pattern: Optional[str] = None,
    category: Optional[str] = None
) -> List[Tool]:
    """
    Discover tools based on various criteria.
    
    Args:
        module: Module name to search for tools
        pattern: File pattern to search (e.g., "*_tool.py")
        category: Category to filter by
        
    Returns:
        List of discovered Tool instances
    """
    registry = get_tool_registry()
    
    if category:
        return registry.get_tools_by_category(category)
    
    # For module and pattern discovery, we'd need to implement
    # module introspection and file system scanning
    # For now, return all tools as a basic implementation
    return registry.list_all_tools()


def list_tools(
    agent_name: Optional[str] = None,
    category: Optional[str] = None,
    shared_only: bool = False
) -> List[dict]:
    """
    List tools with optional filtering.
    
    Args:
        agent_name: Filter by agent owner
        category: Filter by category
        shared_only: Only show shared tools
        
    Returns:
        List of tool information dictionaries
    """
    registry = get_tool_registry()
    
    if agent_name:
        tools = registry.get_tools_for_agent(agent_name)
    elif category:
        tools = registry.get_tools_by_category(category)
    elif shared_only:
        tools = registry.get_shared_tools()
    else:
        tools = registry.list_all_tools()
    
    return [tool.to_dict() for tool in tools]


def register_tool_with_agent(tool_name: str, agent_name: str) -> bool:
    """
    Register an existing tool with an agent at runtime.
    
    Args:
        tool_name: Name of the tool to register
        agent_name: Name of the agent to register with
        
    Returns:
        True if registration successful, False otherwise
    """
    registry = get_tool_registry()
    return registry.assign_tool_to_agent(tool_name, agent_name)


def unregister_tool_from_agent(tool_name: str, agent_name: str) -> bool:
    """
    Unregister a tool from an agent at runtime.
    
    Args:
        tool_name: Name of the tool to unregister
        agent_name: Name of the agent to unregister from
        
    Returns:
        True if unregistration successful, False otherwise
    """
    registry = get_tool_registry()
    return registry.remove_tool_from_agent(tool_name, agent_name)


class ToolCollection:
    """
    A collection of related tools that can be managed as a group.
    
    Useful for organizing tools by functionality or creating tool suites
    that can be easily assigned to agents.
    """
    
    def __init__(self, name: str, description: str = ""):
        """
        Initialize a tool collection.
        
        Args:
            name: Name of the collection
            description: Description of the collection
        """
        self.name = name
        self.description = description
        self.tools: List[str] = []
    
    def add_tool(self, tool_name: str) -> None:
        """
        Add a tool to the collection.
        
        Args:
            tool_name: Name of the tool to add
            
        Raises:
            ToolError: If tool doesn't exist
        """
        registry = get_tool_registry()
        if not registry.get_tool(tool_name):
            raise ToolError(f"Tool '{tool_name}' not found in registry")
        
        if tool_name not in self.tools:
            self.tools.append(tool_name)
    
    def remove_tool(self, tool_name: str) -> bool:
        """
        Remove a tool from the collection.
        
        Args:
            tool_name: Name of the tool to remove
            
        Returns:
            True if removal successful, False if tool wasn't in collection
        """
        if tool_name in self.tools:
            self.tools.remove(tool_name)
            return True
        return False
    
    def assign_to_agent(self, agent_name: str) -> int:
        """
        Assign all tools in the collection to an agent.
        
        Args:
            agent_name: Name of the agent to assign tools to
            
        Returns:
            Number of tools successfully assigned
        """
        registry = get_tool_registry()
        successful = 0
        
        for tool_name in self.tools:
            if registry.assign_tool_to_agent(tool_name, agent_name):
                successful += 1
        
        return successful
    
    def get_tools(self) -> List[Tool]:
        """
        Get all tools in the collection.
        
        Returns:
            List of Tool instances in the collection
        """
        registry = get_tool_registry()
        result = []
        
        for tool_name in self.tools:
            tool = registry.get_tool(tool_name)
            if tool:
                result.append(tool)
        
        return result