"""
Praval: A composable Python framework for LLM-based agents.

Inspired by coral ecosystems where simple organisms create complex structures
through collaboration, Praval enables simple agents to work together for
sophisticated behaviors.
"""

from .core.agent import Agent
from .core.registry import register_agent, get_registry

__version__ = "0.1.0"
__all__ = ["Agent", "register_agent", "get_registry"]