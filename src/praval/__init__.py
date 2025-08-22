"""
Praval: A composable Python framework for LLM-based agents.

Inspired by coral ecosystems where simple organisms create complex structures
through collaboration, Praval enables simple agents to work together for
sophisticated behaviors.

Version 0.6.1 includes Unified Data Storage & Retrieval System with support for
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

__version__ = "0.6.1"
__all__ = [
    # Core classes
    "Agent", "register_agent", "get_registry", "get_reef", "Spore", "SporeType",
    
    # Enhanced decorator (now with memory support)
    "agent",
    
    # Communication and composition
    "chat", "achat", "broadcast", "get_agent_info",
    "agent_pipeline", "conditional_agent", "throttled_agent",
    "AgentSession", "start_agents",
    
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