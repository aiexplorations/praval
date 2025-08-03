"""
Agent and Tool Registry for Praval Framework.

Provides a global registry for tracking agents and tools across the system,
enabling better coordination and discovery in multi-agent applications.
"""

from typing import Dict, List, Any, Optional
from .agent import Agent


class PravalRegistry:
    """Global registry for agents and tools in Praval applications."""
    
    def __init__(self):
        self._agents: Dict[str, Agent] = {}
        self._tools: Dict[str, Dict[str, Any]] = {}
    
    def register_agent(self, agent: Agent) -> Agent:
        """
        Register an agent in the global registry.
        
        Args:
            agent: Agent instance to register
            
        Returns:
            The registered agent
        """
        self._agents[agent.name] = agent
        
        # Also register all tools from this agent
        for tool_name, tool_info in agent.tools.items():
            full_tool_name = f"{agent.name}.{tool_name}"
            self._tools[full_tool_name] = {
                **tool_info,
                "agent": agent.name
            }
        
        return agent
    
    def get_agent(self, name: str) -> Optional[Agent]:
        """Get an agent by name from the registry."""
        return self._agents.get(name)
    
    def get_all_agents(self) -> Dict[str, Agent]:
        """Get all registered agents."""
        return self._agents.copy()
    
    def get_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get a tool by name from the registry."""
        return self._tools.get(tool_name)
    
    def get_tools_by_agent(self, agent_name: str) -> Dict[str, Dict[str, Any]]:
        """Get all tools for a specific agent."""
        return {
            tool_name: tool_info 
            for tool_name, tool_info in self._tools.items()
            if tool_info.get("agent") == agent_name
        }
    
    def list_agents(self) -> List[str]:
        """List names of all registered agents."""
        return list(self._agents.keys())
    
    def list_tools(self) -> List[str]:
        """List names of all registered tools."""
        return list(self._tools.keys())
    
    def clear(self):
        """Clear all registered agents and tools."""
        self._agents.clear()
        self._tools.clear()


# Global registry instance
_global_registry = PravalRegistry()


def register_agent(agent: Agent) -> Agent:
    """Register an agent in the global registry."""
    return _global_registry.register_agent(agent)


def get_registry() -> PravalRegistry:
    """Get the global registry instance."""
    return _global_registry