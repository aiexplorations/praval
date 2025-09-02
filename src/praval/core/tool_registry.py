"""
Tool Registry for Praval Framework.

This module provides a centralized registry for managing tools and their
relationships to agents. Tools can be registered, discovered, and assigned
to agents dynamically.
"""

import inspect
import threading
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from collections import defaultdict

from .exceptions import ToolError


@dataclass
class ToolMetadata:
    """Metadata for a registered tool."""
    tool_name: str
    owned_by: Optional[str] = None
    description: str = ""
    category: str = "general"
    shared: bool = False
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    return_type: str = "Any"


class Tool:
    """
    Wrapper class for a registered tool function.
    
    Provides metadata, validation, and execution capabilities
    for functions registered as tools in the Praval framework.
    """
    
    def __init__(self, func: Callable, metadata: ToolMetadata):
        """
        Initialize a Tool instance.
        
        Args:
            func: The function to wrap as a tool
            metadata: Metadata describing the tool
            
        Raises:
            ToolError: If function validation fails
        """
        self.func = func
        self.metadata = metadata
        self._validate_function()
        self._extract_parameters()
    
    def _validate_function(self):
        """Validate that the function has proper type hints and structure."""
        sig = inspect.signature(self.func)
        
        # Check that all parameters have type hints
        for param_name, param in sig.parameters.items():
            if param.annotation == inspect.Parameter.empty:
                raise ToolError(
                    f"Tool '{self.metadata.tool_name}' parameter '{param_name}' "
                    f"must have a type hint"
                )
        
        # Check return type annotation
        if sig.return_annotation == inspect.Signature.empty:
            raise ToolError(
                f"Tool '{self.metadata.tool_name}' must have a return type hint"
            )
    
    def _extract_parameters(self):
        """Extract parameter information from function signature."""
        sig = inspect.signature(self.func)
        parameters = {}
        
        for name, param in sig.parameters.items():
            param_type = param.annotation
            type_name = getattr(param_type, '__name__', str(param_type))
            
            parameters[name] = {
                "type": type_name,
                "required": param.default == inspect.Parameter.empty,
                "default": param.default if param.default != inspect.Parameter.empty else None
            }
        
        self.metadata.parameters = parameters
        
        # Update return type
        sig = inspect.signature(self.func)
        return_type = sig.return_annotation
        self.metadata.return_type = getattr(return_type, '__name__', str(return_type))
    
    def execute(self, *args, **kwargs) -> Any:
        """
        Execute the tool function with given arguments.
        
        Args:
            *args: Positional arguments for the tool function
            **kwargs: Keyword arguments for the tool function
            
        Returns:
            Result of tool function execution
            
        Raises:
            ToolError: If execution fails
        """
        try:
            return self.func(*args, **kwargs)
        except Exception as e:
            raise ToolError(
                f"Tool '{self.metadata.tool_name}' execution failed: {str(e)}"
            ) from e
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to dictionary representation for serialization."""
        return {
            "tool_name": self.metadata.tool_name,
            "owned_by": self.metadata.owned_by,
            "description": self.metadata.description,
            "category": self.metadata.category,
            "shared": self.metadata.shared,
            "version": self.metadata.version,
            "author": self.metadata.author,
            "tags": self.metadata.tags,
            "parameters": self.metadata.parameters,
            "return_type": self.metadata.return_type
        }


class ToolRegistry:
    """
    Centralized registry for managing tools and their relationships to agents.
    
    The registry provides functionality to:
    - Register and retrieve tools
    - Associate tools with agents
    - Manage shared tools
    - Query tools by category
    - Handle tool lifecycle
    """
    
    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, Tool] = {}
        self._agent_tools: Dict[str, Set[str]] = defaultdict(set)
        self._category_tools: Dict[str, Set[str]] = defaultdict(set)
        self._shared_tools: Set[str] = set()
        self._lock = threading.RLock()
    
    def register_tool(self, tool: Tool) -> None:
        """
        Register a tool in the registry.
        
        Args:
            tool: Tool instance to register
            
        Raises:
            ToolError: If tool name already exists or registration fails
        """
        with self._lock:
            tool_name = tool.metadata.tool_name
            
            if tool_name in self._tools:
                raise ToolError(f"Tool '{tool_name}' is already registered")
            
            # Register the tool
            self._tools[tool_name] = tool
            
            # Handle ownership
            if tool.metadata.owned_by:
                self._agent_tools[tool.metadata.owned_by].add(tool_name)
            
            # Handle categories
            if tool.metadata.category:
                self._category_tools[tool.metadata.category].add(tool_name)
            
            # Handle shared tools
            if tool.metadata.shared:
                self._shared_tools.add(tool_name)
    
    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """
        Retrieve a tool by name.
        
        Args:
            tool_name: Name of the tool to retrieve
            
        Returns:
            Tool instance if found, None otherwise
        """
        with self._lock:
            return self._tools.get(tool_name)
    
    def get_tools_for_agent(self, agent_name: str) -> List[Tool]:
        """
        Get all tools available to a specific agent.
        
        This includes:
        - Tools owned by the agent
        - Shared tools
        - Tools explicitly assigned to the agent
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            List of Tool instances available to the agent
        """
        with self._lock:
            tool_names = set()
            
            # Add owned tools
            tool_names.update(self._agent_tools.get(agent_name, set()))
            
            # Add shared tools
            tool_names.update(self._shared_tools)
            
            # Return Tool instances
            return [self._tools[name] for name in tool_names if name in self._tools]
    
    def get_tools_by_category(self, category: str) -> List[Tool]:
        """
        Get all tools in a specific category.
        
        Args:
            category: Category name
            
        Returns:
            List of Tool instances in the category
        """
        with self._lock:
            tool_names = self._category_tools.get(category, set())
            return [self._tools[name] for name in tool_names if name in self._tools]
    
    def get_shared_tools(self) -> List[Tool]:
        """
        Get all shared tools.
        
        Returns:
            List of all shared Tool instances
        """
        with self._lock:
            return [self._tools[name] for name in self._shared_tools if name in self._tools]
    
    def list_all_tools(self) -> List[Tool]:
        """
        List all registered tools.
        
        Returns:
            List of all Tool instances
        """
        with self._lock:
            return list(self._tools.values())
    
    def assign_tool_to_agent(self, tool_name: str, agent_name: str) -> bool:
        """
        Assign a tool to an agent at runtime.
        
        Args:
            tool_name: Name of the tool to assign
            agent_name: Name of the agent to assign to
            
        Returns:
            True if assignment successful, False if tool doesn't exist
        """
        with self._lock:
            if tool_name not in self._tools:
                return False
            
            self._agent_tools[agent_name].add(tool_name)
            return True
    
    def remove_tool_from_agent(self, tool_name: str, agent_name: str) -> bool:
        """
        Remove a tool assignment from an agent.
        
        Args:
            tool_name: Name of the tool to remove
            agent_name: Name of the agent to remove from
            
        Returns:
            True if removal successful, False if assignment didn't exist
        """
        with self._lock:
            if agent_name not in self._agent_tools:
                return False
            
            if tool_name not in self._agent_tools[agent_name]:
                return False
            
            self._agent_tools[agent_name].discard(tool_name)
            return True
    
    def unregister_tool(self, tool_name: str) -> bool:
        """
        Unregister a tool from the registry.
        
        Args:
            tool_name: Name of the tool to unregister
            
        Returns:
            True if unregistration successful, False if tool didn't exist
        """
        with self._lock:
            if tool_name not in self._tools:
                return False
            
            tool = self._tools[tool_name]
            
            # Remove from all collections
            del self._tools[tool_name]
            
            # Remove from agent assignments
            for agent_tools in self._agent_tools.values():
                agent_tools.discard(tool_name)
            
            # Remove from category
            if tool.metadata.category:
                self._category_tools[tool.metadata.category].discard(tool_name)
            
            # Remove from shared tools
            self._shared_tools.discard(tool_name)
            
            return True
    
    def clear_registry(self) -> None:
        """Clear all tools from the registry."""
        with self._lock:
            self._tools.clear()
            self._agent_tools.clear()
            self._category_tools.clear()
            self._shared_tools.clear()
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the registry.
        
        Returns:
            Dictionary with registry statistics
        """
        with self._lock:
            return {
                "total_tools": len(self._tools),
                "shared_tools": len(self._shared_tools),
                "agents_with_tools": len(self._agent_tools),
                "categories": len(self._category_tools),
                "tools_by_category": {
                    cat: len(tools) for cat, tools in self._category_tools.items()
                }
            }
    
    def search_tools(self, 
                    name_pattern: Optional[str] = None,
                    category: Optional[str] = None,
                    owned_by: Optional[str] = None,
                    shared_only: bool = False,
                    tags: Optional[List[str]] = None) -> List[Tool]:
        """
        Search for tools based on multiple criteria.
        
        Args:
            name_pattern: Pattern to match in tool names (case-insensitive)
            category: Specific category to filter by
            owned_by: Specific owner to filter by
            shared_only: Only return shared tools
            tags: Tags that tools must have (any match)
            
        Returns:
            List of Tool instances matching the criteria
        """
        with self._lock:
            results = []
            
            for tool in self._tools.values():
                # Check name pattern
                if name_pattern and name_pattern.lower() not in tool.metadata.tool_name.lower():
                    continue
                
                # Check category
                if category and tool.metadata.category != category:
                    continue
                
                # Check owner
                if owned_by and tool.metadata.owned_by != owned_by:
                    continue
                
                # Check shared only
                if shared_only and not tool.metadata.shared:
                    continue
                
                # Check tags
                if tags and not any(tag in tool.metadata.tags for tag in tags):
                    continue
                
                results.append(tool)
            
            return results


# Global registry instance
_global_registry: Optional[ToolRegistry] = None
_registry_lock = threading.Lock()


def get_tool_registry() -> ToolRegistry:
    """
    Get the global tool registry instance.
    
    Returns:
        Global ToolRegistry instance
    """
    global _global_registry
    
    if _global_registry is None:
        with _registry_lock:
            if _global_registry is None:
                _global_registry = ToolRegistry()
    
    return _global_registry


def reset_tool_registry() -> None:
    """
    Reset the global tool registry (primarily for testing).
    
    Warning: This will clear all registered tools.
    """
    global _global_registry
    
    with _registry_lock:
        if _global_registry is not None:
            _global_registry.clear_registry()
        _global_registry = None