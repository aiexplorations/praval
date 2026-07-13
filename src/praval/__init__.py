"""
Praval: A composable Python framework for LLM-based agents.

Inspired by coral ecosystems where simple organisms create complex structures
through collaboration, Praval enables simple agents to work together for
sophisticated behaviors.

Version 0.8.0 adds the provider-neutral model runtime, structured model
contracts, local OpenAI-compatible providers, Gemini support, normalized
streaming events, multimodal request validation, and runtime-owned capability
checks while preserving legacy agent APIs.

"""

from typing import Any

from .app import PravalApp, get_default_app, reset_default_app
from .composition import (
    AgentSession,
    agent_pipeline,
    conditional_agent,
    start_agents,
    throttled_agent,
)
from .core.agent import Agent
from .core.exceptions import (
    EmbeddingConfigurationError,
    HITLConfigurationError,
    InterventionRequired,
)
from .core.reef import Spore, SporeType, get_reef
from .core.registry import get_registry, register_agent

# Enhanced agent decorator with memory support (v0.7.0+)
from .decorators import achat, agent, broadcast, chat, get_agent_info
from .embeddings import EmbeddingRuntime
from .hitl import (
    HITLService,
    HITLStore,
    InterventionDecision,
    InterventionPolicy,
    InterventionRequest,
    InterventionStatus,
    SuspendedRunState,
    get_hitl_store,
)
from .model_runtime import ModelRuntime
from .models import (
    AudioResponse,
    ContentPart,
    EmbeddingRequest,
    EmbeddingResponse,
    ModelEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ProviderAdapter,
    ProviderCapabilities,
    ProviderProfile,
    ReasoningConfig,
    SpeechRequest,
    StructuredOutputConfig,
    ToolCall,
    ToolResult,
    ToolSpec,
    TranscriptionRequest,
    Usage,
)
from .providers.registry import get_provider_registry, reset_provider_registry

tool: Any = None
get_tool_info: Any = None
is_tool: Any = None
discover_tools: Any = None
list_tools: Any = None
register_tool_with_agent: Any = None
unregister_tool_from_agent: Any = None
ToolCollection: Any = None
ToolRegistry: Any = None
Tool: Any = None
ToolMetadata: Any = None
get_tool_registry: Any = None
reset_tool_registry: Any = None

MemoryManager: Any = None
MemoryType: Any = None
MemoryEntry: Any = None
MemoryQuery: Any = None

BaseStorageProvider: Any = None
StorageRegistry: Any = None
DataManager: Any = None
storage_enabled: Any = None
requires_storage: Any = None
get_storage_registry: Any = None
get_data_manager: Any = None
PostgreSQLProvider: Any = None
RedisProvider: Any = None
S3Provider: Any = None
FileSystemProvider: Any = None
QdrantProvider: Any = None
DataReference: Any = None
StorageResult: Any = None
StorageType: Any = None

# Tool system imports (v0.7.2+)
try:
    from .core.tool_registry import (
        Tool,
        ToolMetadata,
        ToolRegistry,
        get_tool_registry,
        reset_tool_registry,
    )
    from .tools import (
        ToolCollection,
        discover_tools,
        get_tool_info,
        is_tool,
        list_tools,
        register_tool_with_agent,
        tool,
        unregister_tool_from_agent,
    )

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
    from .memory import MemoryEntry, MemoryManager, MemoryQuery, MemoryType

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
        BaseStorageProvider,
        DataManager,
        DataReference,
        FileSystemProvider,
        PostgreSQLProvider,
        QdrantProvider,
        RedisProvider,
        S3Provider,
        StorageRegistry,
        StorageResult,
        StorageType,
        get_data_manager,
        get_storage_registry,
        requires_storage,
        storage_enabled,
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

__version__ = "0.8.0"
__all__ = [
    # Core classes
    "Agent",
    "register_agent",
    "get_registry",
    "get_reef",
    "Spore",
    "SporeType",
    # Enhanced decorator (now with memory support)
    "agent",
    # Communication and composition
    "chat",
    "achat",
    "broadcast",
    "get_agent_info",
    "agent_pipeline",
    "conditional_agent",
    "throttled_agent",
    "AgentSession",
    "start_agents",
    # HITL
    "InterventionDecision",
    "InterventionPolicy",
    "InterventionRequest",
    "InterventionStatus",
    "SuspendedRunState",
    "HITLService",
    "HITLStore",
    "get_hitl_store",
    "InterventionRequired",
    "HITLConfigurationError",
    "EmbeddingConfigurationError",
    # Model runtime contracts
    "AudioResponse",
    "ContentPart",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "ModelEvent",
    "ModelMessage",
    "ModelRequest",
    "ModelResponse",
    "ProviderAdapter",
    "ProviderCapabilities",
    "ProviderProfile",
    "ReasoningConfig",
    "SpeechRequest",
    "StructuredOutputConfig",
    "ToolCall",
    "ToolResult",
    "ToolSpec",
    "TranscriptionRequest",
    "Usage",
    "ModelRuntime",
    "EmbeddingRuntime",
    "get_provider_registry",
    "reset_provider_registry",
    "PravalApp",
    "get_default_app",
    "reset_default_app",
    # Tool system (if available)
    "tool",
    "get_tool_info",
    "is_tool",
    "discover_tools",
    "list_tools",
    "register_tool_with_agent",
    "unregister_tool_from_agent",
    "ToolCollection",
    "ToolRegistry",
    "Tool",
    "ToolMetadata",
    "get_tool_registry",
    "reset_tool_registry",
    "TOOLS_AVAILABLE",
    # Memory system (if available)
    "MemoryManager",
    "MemoryType",
    "MemoryEntry",
    "MemoryQuery",
    "MEMORY_AVAILABLE",
    # Storage system (if available)
    "BaseStorageProvider",
    "StorageRegistry",
    "DataManager",
    "storage_enabled",
    "requires_storage",
    "get_storage_registry",
    "get_data_manager",
    "PostgreSQLProvider",
    "RedisProvider",
    "S3Provider",
    "FileSystemProvider",
    "QdrantProvider",
    "DataReference",
    "StorageResult",
    "StorageType",
    "STORAGE_AVAILABLE",
]
