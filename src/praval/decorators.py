"""
Decorator-based Agent API for Praval Framework.

This module provides a Pythonic decorator interface for creating agents
that automatically handle reef communication and coordination.

Example:
    @agent("explorer", channel="knowledge")
    def explore_concepts(spore):
        concepts = chat("Find concepts related to: " + spore.knowledge.get("concept", ""))
        return {"discovered": concepts.split(",")}
"""

import inspect
import threading
from typing import Dict, Any, Optional, Callable, Union, List
from functools import wraps

from .core.agent import Agent
from .core.reef import get_reef

# Thread-local storage for current agent context
_agent_context = threading.local()


def agent(name: Optional[str] = None, 
          channel: Optional[str] = None,
          system_message: Optional[str] = None,
          auto_broadcast: bool = True,
          responds_to: Optional[List[str]] = None):
    """
    Decorator that turns a function into an autonomous agent.
    
    Args:
        name: Agent name (defaults to function name)
        channel: Channel to subscribe to (defaults to name + "_channel")
        system_message: System message (defaults to function docstring)
        auto_broadcast: Whether to auto-broadcast return values
        responds_to: List of message types this agent responds to (None = all messages)
    
    Example:
        @agent("explorer", channel="knowledge", responds_to=["concept_request"])
        def explore_concepts(spore):
            '''Find related concepts and broadcast discoveries.'''
            concepts = chat("Related to: " + spore.knowledge.get("concept", ""))
            return {"type": "discovery", "discovered": concepts.split(",")}
    """
    def decorator(func: Callable) -> Callable:
        # Auto-generate name from function if not provided
        agent_name = name or func.__name__
        agent_channel = channel or f"{agent_name}_channel"
        
        # Auto-generate system message from docstring if not provided
        auto_system_message = system_message
        if not auto_system_message and func.__doc__:
            auto_system_message = f"You are {agent_name}. {func.__doc__.strip()}"
        
        # Create underlying agent
        underlying_agent = Agent(agent_name, system_message=auto_system_message)
        
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
            
            try:
                # Call the decorated function
                result = func(spore)
                
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
        
        # Set up the agent
        underlying_agent.set_spore_handler(agent_handler)
        underlying_agent.subscribe_to_channel(agent_channel)
        
        # Store metadata on function for composition and introspection
        func._praval_agent = underlying_agent
        func._praval_name = agent_name
        func._praval_channel = agent_channel
        func._praval_auto_broadcast = auto_broadcast
        func._praval_responds_to = responds_to
        
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
        channel: Channel to broadcast to (defaults to agent's channel)
        message_type: Message type to set (automatically added to data)
        
    Returns:
        Spore ID of the broadcast message
        
    Raises:
        RuntimeError: If called outside of an @agent function
    """
    if not hasattr(_agent_context, 'agent') or _agent_context.agent is None:
        raise RuntimeError("broadcast() can only be used within @agent decorated functions")
    
    # Add message type to data if specified
    broadcast_data = data.copy()
    if message_type:
        broadcast_data["type"] = message_type
    
    target_channel = channel or _agent_context.channel
    return _agent_context.agent.broadcast_knowledge(broadcast_data, channel=target_channel)


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


# Import time at the top to fix the NameError
import time