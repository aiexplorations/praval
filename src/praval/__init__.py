"""
Praval: A composable Python framework for LLM-based agents.

Inspired by coral ecosystems where simple organisms create complex structures
through collaboration, Praval enables simple agents to work together for
sophisticated behaviors.
"""

from .core.agent import Agent
from .core.registry import register_agent, get_registry
from .core.reef import get_reef
from .decorators import agent, chat, achat, broadcast, get_agent_info
from .composition import (
    agent_pipeline, conditional_agent, throttled_agent, 
    AgentSession, start_agents
)

__version__ = "0.2.0"
__all__ = [
    "Agent", "register_agent", "get_registry", "get_reef",
    "agent", "chat", "achat", "broadcast", "get_agent_info",
    "agent_pipeline", "conditional_agent", "throttled_agent",
    "AgentSession", "start_agents"
]