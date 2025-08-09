"""
Praval: A composable Python framework for LLM-based agents.

Inspired by coral ecosystems where simple organisms create complex structures
through collaboration, Praval enables simple agents to work together for
sophisticated behaviors.

Version 0.4.2 includes comprehensive memory system tests with 96% coverage on
MemoryManager, 100% coverage on semantic/episodic memory, and 99% coverage on
decorators. Significantly improved test coverage across all memory modules.
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

__version__ = "0.5.0"
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
    "MemoryManager", "MemoryType", "MemoryEntry", "MemoryQuery", "MEMORY_AVAILABLE"
]