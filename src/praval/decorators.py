"""
Decorator-based Agent API for Praval Framework.

This module provides a Pythonic decorator interface for creating agents
that automatically handle reef communication and coordination.

Example::

    from praval import agent, chat, broadcast, start_agents, get_reef

    @agent("explorer", responds_to=["concept_request"])
    def explore_concepts(spore):
        concepts = chat("Find concepts related to: " + spore.knowledge.get("concept", ""))
        broadcast({"type": "discovery", "discovered": concepts.split(",")})
        return {"discovered": concepts}

    # Start the agent system
    start_agents(explore_concepts, initial_data={"type": "concept_request", "concept": "AI"})
    get_reef().wait_for_completion()
    get_reef().shutdown()
"""

import inspect
import threading
import time
from typing import Dict, Any, Optional, Callable, Union, List
from functools import wraps

from .core.agent import Agent
from .core.reef import get_reef
from .core.tool_registry import get_tool_registry

# Thread-local storage for current agent context
_agent_context = threading.local()


def _auto_register_tools(agent: Agent, agent_name: str) -> None:
    """
    Auto-register tools from the tool registry for an agent.
    
    This function automatically registers tools that are:
    1. Owned by the agent
    2. Shared (available to all agents)
    3. Any tools already assigned to this agent in the registry
    
    Args:
        agent: The Agent instance to register tools for
        agent_name: Name of the agent
    """
    try:
        registry = get_tool_registry()
        available_tools = registry.get_tools_for_agent(agent_name)
        
        for tool in available_tools:
            # Register the tool function with the agent
            tool_func = tool.func
            
            # Add the tool to the agent using the existing tool decorator
            agent.tool(tool_func)
            
    except Exception as e:
        # Don't fail agent creation if tool registration fails
        # Just log the error (in a real implementation, we'd use proper logging)
        pass


def agent(name: Optional[str] = None, 
          channel: Optional[str] = None,
          system_message: Optional[str] = None,
          auto_broadcast: bool = True,
          responds_to: Optional[List[str]] = None,
          memory: Union[bool, Dict[str, Any]] = False,
          knowledge_base: Optional[str] = None):
    """
    Decorator that turns a function into an autonomous agent.
    
    Args:
        name: Agent name (defaults to function name)
        channel: Channel to subscribe to (defaults to name + "_channel")
        system_message: System message (defaults to function docstring)
        auto_broadcast: Whether to auto-broadcast return values
        responds_to: List of message types this agent responds to (None = all messages)
        memory: Memory configuration - True for defaults, dict for custom config, False to disable
        knowledge_base: Path to knowledge base files for auto-indexing
    
    Examples::

        # Basic agent with message filtering
        @agent("explorer", responds_to=["concept_request"])
        def explore_concepts(spore):
            '''Find related concepts and broadcast discoveries.'''
            concepts = chat("Related to: " + spore.knowledge.get("concept", ""))
            return {"type": "discovery", "discovered": concepts.split(",")}

    Memory-enabled agent::

        @agent("researcher", memory=True)
        def research_agent(spore):
            '''Research agent with memory capabilities.'''
            query = spore.knowledge.get("query")
            research_agent.remember(f"Researched: {query}")
            past_research = research_agent.recall(query)
            return {"research": "completed", "past_similar": len(past_research)}

    Agent with knowledge base::

        @agent("expert", memory=True, knowledge_base="./knowledge/")
        def expert_agent(spore):
            '''Expert with pre-loaded knowledge base.'''
            question = spore.knowledge.get("question")
            relevant = expert_agent.recall(question, limit=3)
            return {"answer": [r.content for r in relevant]}
    """
    def decorator(func: Callable) -> Callable:
        # Auto-generate name from function if not provided
        agent_name = name or func.__name__
        agent_channel = channel or f"{agent_name}_channel"
        
        # Auto-generate system message from docstring if not provided
        auto_system_message = system_message
        if not auto_system_message and func.__doc__:
            auto_system_message = f"You are {agent_name}. {func.__doc__.strip()}"
        
        # Parse memory configuration
        memory_enabled = False
        memory_config = None
        
        if memory is True:
            memory_enabled = True
            memory_config = {}
        elif isinstance(memory, dict):
            memory_enabled = True
            memory_config = memory
        
        # Create underlying agent with memory support
        underlying_agent = Agent(
            name=agent_name, 
            system_message=auto_system_message,
            memory_enabled=memory_enabled,
            memory_config=memory_config,
            knowledge_base=knowledge_base
        )
        
        def agent_handler(spore):
            """Handler that sets up context and calls the decorated function."""
            # Check message type filtering
            if responds_to is not None:
                spore_type = spore.knowledge.get("type")
                if spore_type not in responds_to:
                    # This agent doesn't respond to this message type
                    return

            # Set agent context for chat() and broadcast() functions
            _agent_context.agent = underlying_agent
            _agent_context.channel = agent_channel
            # Set startup channel if agent was registered via start_agents()
            # This allows broadcast() to default to the channel all agents share
            _agent_context.startup_channel = getattr(underlying_agent, '_startup_channel', None)
            
            try:
                # Resolve knowledge references in spore if memory is enabled
                if memory_enabled and hasattr(spore, 'has_knowledge_references'):
                    if spore.has_knowledge_references():
                        try:
                            resolved_knowledge = underlying_agent.resolve_spore_knowledge(spore)
                            spore.resolved_knowledge = resolved_knowledge
                        except Exception as e:
                            # If knowledge resolution fails, continue without resolved knowledge
                            pass
                
                # Call the decorated function
                result = func(spore)
                
                # Store conversation turn in memory if enabled
                if memory_enabled and underlying_agent.memory:
                    try:
                        query = str(spore.knowledge) if spore.knowledge else "interaction"
                        response = str(result) if result else "no_response"
                        
                        underlying_agent.memory.store_conversation_turn(
                            agent_id=agent_name,
                            user_message=query,
                            agent_response=response,
                            context={"spore_id": spore.id, "spore_type": spore.spore_type.value}
                        )
                    except Exception as e:
                        # Don't fail the agent if memory storage fails
                        pass
                
                # Auto-broadcast return values if enabled and result exists
                if auto_broadcast and result and isinstance(result, dict):
                    underlying_agent.broadcast_knowledge(
                        {**result, "_from": agent_name, "_timestamp": time.time()},
                        channel=agent_channel
                    )
            finally:
                # Clean up context
                _agent_context.agent = None
                _agent_context.channel = None
                _agent_context.startup_channel = None
        
        # Set up the agent
        underlying_agent.set_spore_handler(agent_handler)
        underlying_agent.subscribe_to_channel(agent_channel)

        # CRITICAL FIX for reef broadcast invocation:
        # Subscribe agent to the default broadcast channel so it receives
        # spores from reef.broadcast(). This ensures agents listening on their
        # own channel ALSO receive system-wide broadcasts.
        #
        # The handler is delegated through on_spore_received to the custom
        # agent_handler set above, preventing duplicate invocations.
        reef = get_reef()
        reef.subscribe(agent_name, underlying_agent.on_spore_received, channel=reef.default_channel, replace=True)

        # Auto-register tools from the tool registry
        _auto_register_tools(underlying_agent, agent_name)
        
        # Add memory methods to the function for easy access
        if memory_enabled:
            func.remember = underlying_agent.remember
            func.recall = underlying_agent.recall
            func.recall_by_id = underlying_agent.recall_by_id
            func.get_conversation_context = underlying_agent.get_conversation_context
            func.create_knowledge_reference = underlying_agent.create_knowledge_reference
            func.send_lightweight_knowledge = underlying_agent.send_lightweight_knowledge
            func.memory = underlying_agent.memory  # Direct memory manager access
        
        # Add reef communication methods
        func.send_knowledge = underlying_agent.send_knowledge
        func.broadcast_knowledge = underlying_agent.broadcast_knowledge
        func.request_knowledge = underlying_agent.request_knowledge
        
        # Add tool management methods
        func.tool = underlying_agent.tool
        func.add_tool = underlying_agent.tool  # Alias for compatibility
        func.list_tools = lambda: list(underlying_agent.tools.keys())
        func.get_tool = lambda name: underlying_agent.tools.get(name)
        func.has_tool = lambda name: name in underlying_agent.tools
        
        # Store metadata on function for composition and introspection
        func._praval_agent = underlying_agent
        func._praval_name = agent_name
        func._praval_channel = agent_channel
        func._praval_auto_broadcast = auto_broadcast
        func._praval_responds_to = responds_to
        func._praval_memory_enabled = memory_enabled
        func._praval_knowledge_base = knowledge_base
        
        # Return the original function with metadata attached
        return func
    
    return decorator


def chat(message: str, timeout: float = 10.0) -> str:
    """
    Quick chat function that uses the current agent's LLM with timeout support.
    Can only be used within @agent decorated functions.
    
    Args:
        message: Message to send to the LLM
        timeout: Maximum time to wait for response in seconds
        
    Returns:
        LLM response as string
        
    Raises:
        RuntimeError: If called outside of an @agent function
        TimeoutError: If LLM call exceeds timeout
    """
    if not hasattr(_agent_context, 'agent') or _agent_context.agent is None:
        raise RuntimeError("chat() can only be used within @agent decorated functions")
    
    import concurrent.futures
    import signal
    
    def timeout_handler(signum, frame):
        raise TimeoutError(f"LLM call timed out after {timeout} seconds")
    
    # Use thread-based timeout for better cross-platform support
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_agent_context.agent.chat, message)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"LLM call timed out after {timeout} seconds")


async def achat(message: str, timeout: float = 10.0) -> str:
    """
    Async version of chat function for use within async agent handlers.
    
    Args:
        message: Message to send to the LLM
        timeout: Maximum time to wait for response in seconds
        
    Returns:
        LLM response as string
        
    Raises:
        RuntimeError: If called outside of an @agent function
        TimeoutError: If LLM call exceeds timeout
    """
    if not hasattr(_agent_context, 'agent') or _agent_context.agent is None:
        raise RuntimeError("achat() can only be used within @agent decorated functions")
    
    # Run the sync chat in a thread to avoid blocking the event loop
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, _agent_context.agent.chat, message),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        raise TimeoutError(f"LLM call timed out after {timeout} seconds")


def broadcast(data: Dict[str, Any], channel: Optional[str] = None, message_type: Optional[str] = None) -> str:
    """
    Quick broadcast function that uses the current agent's communication.
    Can only be used within @agent decorated functions.

    Args:
        data: Data to broadcast
        channel: Channel to broadcast to. Defaults to the channel set by start_agents(),
                 or reef's default channel if not in a start_agents() context.
        message_type: Message type to set (automatically added to data)

    Returns:
        Spore ID of the broadcast message

    Raises:
        RuntimeError: If called outside of an @agent function

    Example:
        # Broadcast to all agents on the same channel (set by start_agents)
        broadcast({"type": "analysis_request", "data": findings})

        # Broadcast to a specific channel
        broadcast({"type": "alert"}, channel="urgent_alerts")
    """
    if not hasattr(_agent_context, 'agent') or _agent_context.agent is None:
        raise RuntimeError("broadcast() can only be used within @agent decorated functions")

    # Add message type to data if specified
    broadcast_data = data.copy()
    if message_type:
        broadcast_data["type"] = message_type

    # Channel resolution priority:
    # 1. Explicitly passed channel parameter
    # 2. Channel set by start_agents() (stored in _agent_context.startup_channel)
    # 3. Reef's default channel (fallback for standalone agents)
    if channel is None:
        # Check if we're in a start_agents() context with a specific channel
        channel = getattr(_agent_context, 'startup_channel', None)
        if channel is None:
            reef = get_reef()
            channel = reef.default_channel

    return _agent_context.agent.broadcast_knowledge(broadcast_data, channel=channel)


def get_agent_info(agent_func: Callable) -> Dict[str, Any]:
    """
    Get information about an @agent decorated function.
    
    Args:
        agent_func: Function decorated with @agent
        
    Returns:
        Dictionary with agent metadata
    """
    if not hasattr(agent_func, '_praval_agent'):
        raise ValueError("Function is not decorated with @agent")
    
    return {
        "name": agent_func._praval_name,
        "channel": agent_func._praval_channel,
        "auto_broadcast": agent_func._praval_auto_broadcast,
        "responds_to": agent_func._praval_responds_to,
        "underlying_agent": agent_func._praval_agent
    }


