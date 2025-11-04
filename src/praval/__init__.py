"""
Praval: A composable Python framework for LLM-based agents.

Inspired by coral ecosystems where simple organisms create complex structures
through collaboration, Praval enables simple agents to work together for
sophisticated behaviors.

Version 0.7.6 includes comprehensive tool system with @tool decorator,
PDF support for knowledge base, Unified Data Storage & Retrieval System with support for
PostgreSQL, Redis, S3, Qdrant, and filesystem storage providers, plus enhanced
Secure Spores Enterprise Edition and comprehensive memory system integration.
"""

from .core.agent import Agent
from .core.registry import register_agent, get_registry
from .core.reef import get_reef, Spore, SporeType
from .decorators import chat, achat, broadcast, get_agent_info
from .composition import (
    agent_pipeline, conditional_agent, throttled_agent, 
    AgentSession, start_agents
)

# Enhanced agent decorator with memory support (v0.3.0)
from .decorators import agent, chat, achat, broadcast, get_agent_info

# Tool system imports (v0.7.2+)
try:
    from .tools import (
        tool, get_tool_info, is_tool, discover_tools, list_tools,
        register_tool_with_agent, unregister_tool_from_agent, ToolCollection
    )
    from .core.tool_registry import ToolRegistry, Tool, ToolMetadata, get_tool_registry, reset_tool_registry
    TOOLS_AVAILABLE = True
except ImportError:
    TOOLS_AVAILABLE = False
    tool = None
    get_tool_info = None
    is_tool = None
    discover_tools = None
    list_tools = None
    register_tool_with_agent = None
    unregister_tool_from_agent = None
    ToolCollection = None
    ToolRegistry = None
    Tool = None
    ToolMetadata = None
    get_tool_registry = None
    reset_tool_registry = None

# Memory system imports (optional - graceful fallback if dependencies missing)
try:
    from .memory import MemoryManager, MemoryType, MemoryEntry, MemoryQuery
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False
    MemoryManager = None
    MemoryType = None
    MemoryEntry = None
    MemoryQuery = None

# Storage system imports (optional - graceful fallback if dependencies missing)
try:
    from .storage import (
        BaseStorageProvider, StorageRegistry, DataManager,
        storage_enabled, requires_storage,
        get_storage_registry, get_data_manager,
        PostgreSQLProvider, RedisProvider, S3Provider, 
        FileSystemProvider, QdrantProvider,
        DataReference, StorageResult, StorageType
    )
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False
    BaseStorageProvider = None
    StorageRegistry = None
    DataManager = None
    storage_enabled = None
    requires_storage = None
    get_storage_registry = None
    get_data_manager = None
    PostgreSQLProvider = None
    RedisProvider = None
    S3Provider = None
    FileSystemProvider = None
    QdrantProvider = None
    DataReference = None
    StorageResult = None
    StorageType = None

__version__ = "0.7.11"
__all__ = [
    # Core classes
    "Agent", "register_agent", "get_registry", "get_reef", "Spore", "SporeType",
    
    # Enhanced decorator (now with memory support)
    "agent",
    
    # Communication and composition
    "chat", "achat", "broadcast", "get_agent_info",
    "agent_pipeline", "conditional_agent", "throttled_agent",
    "AgentSession", "start_agents",
    
    # Tool system (if available)
    "tool", "get_tool_info", "is_tool", "discover_tools", "list_tools",
    "register_tool_with_agent", "unregister_tool_from_agent", "ToolCollection",
    "ToolRegistry", "Tool", "ToolMetadata", "get_tool_registry", "reset_tool_registry",
    "TOOLS_AVAILABLE",
    
    # Memory system (if available)
    "MemoryManager", "MemoryType", "MemoryEntry", "MemoryQuery", "MEMORY_AVAILABLE",
    
    # Storage system (if available)
    "BaseStorageProvider", "StorageRegistry", "DataManager",
    "storage_enabled", "requires_storage",
    "get_storage_registry", "get_data_manager",
    "PostgreSQLProvider", "RedisProvider", "S3Provider", 
    "FileSystemProvider", "QdrantProvider",
    "DataReference", "StorageResult", "StorageType", "STORAGE_AVAILABLE"
]