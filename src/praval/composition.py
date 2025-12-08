"""
Composition utilities for decorator-based agents.

This module provides utilities for composing and orchestrating agents
decorated with the @agent decorator.

Key Functions:
- start_agents(): Local agents with initial data (InMemoryBackend)
- run_agents(): Distributed agents with RabbitMQ (use AgentRunner)
- agent_pipeline(): Sequential agent processing
- AgentSession: Grouped agent communication
"""

from typing import Callable, List, Dict, Any, Optional
import time
import threading

from .core.reef import get_reef
from .decorators import get_agent_info
from .core.agent_runner import run_agents as _run_agents_impl


def agent_pipeline(*agents: Callable, channel: str = "pipeline") -> Callable:
    """
    Compose agents into a pipeline that processes data sequentially.
    
    Args:
        *agents: Functions decorated with @agent
        channel: Channel name for pipeline communication
        
    Returns:
        Function that triggers the pipeline with initial data
        
    Example:
        pipeline = agent_pipeline(explorer, analyzer, reporter)
        pipeline({"task": "analyze sentiment"})
    """
    # Validate all functions are agents
    for agent_func in agents:
        if not hasattr(agent_func, '_praval_agent'):
            raise ValueError(f"Function {agent_func.__name__} is not decorated with @agent")
    
    def pipeline_trigger(initial_data: Dict[str, Any]) -> str:
        """Trigger the pipeline with initial data."""
        # Subscribe all agents to pipeline channel
        for agent_func in agents:
            agent_info = get_agent_info(agent_func)
            agent_info["underlying_agent"].subscribe_to_channel(channel)
        
        # Broadcast initial data to start pipeline
        reef = get_reef()
        reef.create_channel(channel)  # Ensure channel exists
        return reef.system_broadcast(initial_data, channel)
    
    # Store metadata
    pipeline_trigger._praval_pipeline = True
    pipeline_trigger._praval_agents = agents
    pipeline_trigger._praval_channel = channel
    
    return pipeline_trigger


def conditional_agent(condition_func: Callable[[Any], bool]):
    """
    Decorator for conditional agent execution.
    
    Args:
        condition_func: Function that takes a spore and returns bool
        
    Example:
        @conditional_agent(lambda spore: spore.knowledge.get("priority") == "high")
        @agent("urgent_processor")
        def process_urgent(spore):
            return {"processed": True}
    """
    def decorator(agent_func: Callable) -> Callable:
        if not hasattr(agent_func, '_praval_agent'):
            raise ValueError("conditional_agent must be applied to @agent decorated functions")
        
        # Get the original handler
        underlying_agent = agent_func._praval_agent
        original_handler = underlying_agent._custom_spore_handler
        
        def conditional_handler(spore):
            """Only execute if condition is met."""
            if condition_func(spore):
                return original_handler(spore)
        
        # Replace handler with conditional version
        underlying_agent.set_spore_handler(conditional_handler)
        
        return agent_func
    
    return decorator


def throttled_agent(delay_seconds: float):
    """
    Decorator to throttle agent execution.
    
    Args:
        delay_seconds: Minimum seconds between executions
        
    Example:
        @throttled_agent(2.0)  # Max once every 2 seconds
        @agent("slow_processor")  
        def process_slowly(spore):
            return {"processed": True}
    """
    def decorator(agent_func: Callable) -> Callable:
        if not hasattr(agent_func, '_praval_agent'):
            raise ValueError("throttled_agent must be applied to @agent decorated functions")
        
        last_execution = {"time": 0}
        lock = threading.Lock()
        
        # Get the original handler
        underlying_agent = agent_func._praval_agent
        original_handler = underlying_agent._custom_spore_handler
        
        def throttled_handler(spore):
            """Only execute if enough time has passed."""
            with lock:
                now = time.time()
                if now - last_execution["time"] >= delay_seconds:
                    last_execution["time"] = now
                    return original_handler(spore)
        
        # Replace handler with throttled version
        underlying_agent.set_spore_handler(throttled_handler)
        
        return agent_func
    
    return decorator


class AgentSession:
    """
    Context manager for coordinated agent sessions.
    
    Example:
        with AgentSession("knowledge_mining") as session:
            session.add_agents(explorer, analyzer, curator)
            session.broadcast({"task": "mine concepts about AI"})
    """
    
    def __init__(self, session_name: str):
        self.session_name = session_name
        self.channel_name = f"session_{session_name}"
        self.agents = []
    
    def __enter__(self):
        # Create session channel
        reef = get_reef()
        reef.create_channel(self.channel_name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Cleanup if needed (agents will remain subscribed)
        pass
    
    def add_agent(self, agent_func: Callable) -> 'AgentSession':
        """Add an agent to this session."""
        if not hasattr(agent_func, '_praval_agent'):
            raise ValueError(f"Function {agent_func.__name__} is not decorated with @agent")
        
        agent_info = get_agent_info(agent_func)
        underlying_agent = agent_info["underlying_agent"]
        
        # Subscribe agent to session channel
        underlying_agent.subscribe_to_channel(self.channel_name)
        self.agents.append(agent_func)
        
        return self
    
    def add_agents(self, *agent_funcs: Callable) -> 'AgentSession':
        """Add multiple agents to this session."""
        for agent_func in agent_funcs:
            self.add_agent(agent_func)
        return self
    
    def broadcast(self, data: Dict[str, Any]) -> str:
        """Broadcast data to all agents in this session."""
        reef = get_reef()
        return reef.system_broadcast(
            {**data, "_session": self.session_name},
            self.channel_name
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        return {
            "session_name": self.session_name,
            "channel": self.channel_name,
            "agent_count": len(self.agents),
            "agent_names": [get_agent_info(agent)["name"] for agent in self.agents]
        }


def start_agents(*agent_funcs: Callable, initial_data: Optional[Dict[str, Any]] = None,
                 channel: str = "startup") -> str:
    """
    Convenience function to start multiple agents with initial data.

    Use this for LOCAL agents (InMemoryBackend). For DISTRIBUTED agents with RabbitMQ,
    use run_agents() instead.

    Args:
        *agent_funcs: Functions decorated with @agent
        initial_data: Initial data to broadcast (optional)
        channel: Channel to use for agent communication (default: "startup").
                 All agents will be subscribed to this channel and broadcast()
                 will default to this channel.

    Returns:
        Spore ID of startup broadcast

    Example:
        start_agents(explorer, analyzer, curator,
                    initial_data={"task": "analyze market trends"})
    """
    # Subscribe all agents to startup channel
    reef = get_reef()
    reef.create_channel(channel)

    for agent_func in agent_funcs:
        if not hasattr(agent_func, '_praval_agent'):
            raise ValueError(f"Function {agent_func.__name__} is not decorated with @agent")

        agent_info = get_agent_info(agent_func)
        underlying_agent = agent_info["underlying_agent"]

        # Subscribe agent to the startup channel
        underlying_agent.subscribe_to_channel(channel)

        # Store the startup channel on the agent so broadcast() can use it
        # This ensures broadcast() defaults to the same channel agents are subscribed to
        underlying_agent._startup_channel = channel

    # Broadcast initial data if provided
    if initial_data:
        return reef.system_broadcast(initial_data, channel)
    else:
        return reef.system_broadcast({"type": "agents_started"}, channel)


def run_agents(
    *agent_funcs: Callable,
    backend_config: Optional[Dict[str, Any]] = None,
    channel_queue_map: Optional[Dict[str, str]] = None
) -> None:
    """
    Run distributed agents with proper async lifecycle management.

    This is the recommended way to run agents with RabbitMQ backend. It:
    1. Creates and manages an asyncio event loop
    2. Initializes the RabbitMQ backend
    3. Ensures agents consume messages from the broker
    4. Handles graceful shutdown on signals (SIGTERM, SIGINT)

    Args:
        *agent_funcs: Functions decorated with @agent
        backend_config: RabbitMQ configuration dict:
            {
                'url': 'amqp://user:pass@host:5672/',
                'exchange_name': 'praval.agents',
                'verify_tls': True/False
            }
        channel_queue_map: Optional mapping of Praval channels to RabbitMQ queues.
            Use this when agents should consume from pre-configured queues instead
            of topic-based subscriptions.
            Example: {"data_received": "agent.data_analyzer"}

    Example (Topic-based, Praval-managed routing):
        run_agents(
            processor,
            analyzer,
            backend_config={
                'url': 'amqp://localhost:5672/',
                'exchange_name': 'praval.agents'
            }
        )

    Example (Queue-based, pre-configured RabbitMQ):
        run_agents(
            processor,
            analyzer,
            backend_config={
                'url': 'amqp://localhost:5672/',
                'exchange_name': 'praval.agents'
            },
            channel_queue_map={
                "data_received": "agent.data_analyzer",
                "qc_inspection_received": "agent.vision_inspector"
            }
        )
    """
    return _run_agents_impl(
        *agent_funcs,
        backend_config=backend_config,
        channel_queue_map=channel_queue_map
    )