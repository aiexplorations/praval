"""
Decorator-based Agent API for Praval Framework.

This module provides a Pythonic decorator interface for creating agents
that automatically handle reef communication and coordination.

Example::

    from praval import agent, chat, broadcast, start_agents, get_reef

    @agent("explorer", responds_to=["concept_request"])
    def explore_concepts(spore):
        concepts = chat("Find concepts related to: " + spore.knowledge.get("concept",
        ""))
        broadcast({"type": "discovery", "discovered": concepts.split(",")})
        return {"discovered": concepts}

    # Start the agent system
    start_agents(explore_concepts, initial_data={"type": "concept_request", "concept":
    "AI"})
    get_reef().wait_for_completion()
    get_reef().shutdown()
"""

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Union, cast

from .core.agent import Agent
from .core.exceptions import InterventionRequired, ToolError
from .core.reef import get_reef
from .core.tool_registry import Tool, ToolMetadata, get_tool_registry

logger = logging.getLogger(__name__)

# Thread-local storage for current agent context
_agent_context = threading.local()


def _handle_agent_error(
    error: Exception,
    spore: Any,
    agent_name: str,
    on_error: Union[str, Callable[[Exception, Any], None]],
    context: str = "handler",
) -> None:
    """
    Handle errors in agent handlers based on the on_error configuration.

    Args:
        error: The exception that occurred
        spore: The spore being processed when error occurred
        agent_name: Name of the agent
        on_error: Error handling strategy ("log", "raise", "ignore", or callable)
        context: Context string for logging (e.g., "handler", "memory_storage")
    """
    if on_error == "ignore":
        return

    if on_error == "log":
        logger.error(
            (
                f"Error in agent '{agent_name}' ({context}): "
                f"{type(error).__name__}: {error}"
            ),
            exc_info=True,
        )
        return

    if on_error == "raise":
        raise error

    if callable(on_error):
        try:
            on_error(error, spore)
        except Exception as callback_error:
            logger.error(
                (
                    f"Error in custom error handler for agent '{agent_name}': "
                    f"{callback_error}"
                ),
                exc_info=True,
            )
        return

    # Unknown on_error value - default to logging
    logger.warning(
        (
            f"Unknown on_error value '{on_error}' for agent "
            f"'{agent_name}', defaulting to 'log'"
        )
    )
    logger.error(
        f"Error in agent '{agent_name}' ({context}): {type(error).__name__}: {error}",
        exc_info=True,
    )


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
            # Register the tool with its proper name from the registry,
            # not the function name. This preserves explicit tool names
            # like "calculator_add" instead of using "add" from func.__name__.
            tool_name = tool.metadata.tool_name
            tool_func = tool.func

            # Get function signature for parameter extraction
            import inspect

            sig = inspect.signature(tool_func)

            # Extract parameters from type hints
            parameters = {}
            for param_name, param in sig.parameters.items():
                param_type = param.annotation
                if param_type != inspect.Parameter.empty:
                    type_name = getattr(param_type, "__name__", str(param_type))
                else:
                    type_name = "any"
                parameters[param_name] = {
                    "type": type_name,
                    "required": param.default == inspect.Parameter.empty,
                }

            # Directly register with the proper tool name
            agent.tools[tool_name] = {
                "function": tool_func,
                "description": tool.metadata.description or tool_func.__doc__ or "",
                "parameters": parameters,
                "requires_approval": tool.metadata.requires_approval,
                "risk_level": tool.metadata.risk_level,
                "approval_reason": tool.metadata.approval_reason,
            }

    except Exception as e:
        # Don't fail agent creation if tool registration fails
        # Just log the error
        import logging

        logging.getLogger(__name__).debug(f"Tool auto-registration failed: {e}")


def _attach_tool(
    agent: Agent,
    tool_name: str,
    tool_func: Callable,
    description: str,
    parameters: Dict[str, Any],
) -> None:
    """
    Attach a tool to an agent's local map without overwriting existing entries.
    """
    if tool_name in agent.tools:
        return
    agent.tools[tool_name] = {
        "function": tool_func,
        "description": description or "",
        "parameters": parameters or {},
        "requires_approval": False,
        "risk_level": "low",
        "approval_reason": "",
    }


def _attach_registry_tool(agent: Agent, tool: Tool) -> None:
    """Attach a ToolRegistry tool to the agent's local tool map."""
    _attach_tool(
        agent,
        tool.metadata.tool_name,
        tool.func,
        tool.metadata.description or tool.func.__doc__ or "",
        tool.metadata.parameters or {},
    )
    agent.tools[tool.metadata.tool_name][
        "requires_approval"
    ] = tool.metadata.requires_approval
    agent.tools[tool.metadata.tool_name]["risk_level"] = tool.metadata.risk_level
    agent.tools[tool.metadata.tool_name][
        "approval_reason"
    ] = tool.metadata.approval_reason


def _register_callable_tool(agent_name: str, tool_func: Callable) -> Optional[Tool]:
    """
    Ensure a callable is registered in the tool registry and return the Tool object.
    """
    registry = get_tool_registry()

    if hasattr(tool_func, "_praval_tool"):
        tool_obj = tool_func._praval_tool
        # Ensure registry has it (in case registry was reset)
        existing = registry.get_tool(tool_obj.metadata.tool_name)
        if not existing:
            try:
                registry.register_tool(tool_obj)
            except ToolError:
                pass
        return cast(Optional[Tool], tool_obj)

    # Create and register tool from raw callable
    metadata = ToolMetadata(
        tool_name=tool_func.__name__,
        owned_by=agent_name,
        description=tool_func.__doc__ or "",
        category="general",
        shared=False,
    )
    try:
        tool_obj = Tool(tool_func, metadata)
        registry.register_tool(tool_obj)
        return tool_obj
    except ToolError:
        existing = registry.get_tool(metadata.tool_name)
        return existing
    except Exception:
        return None


def agent(
    name: Optional[str] = None,
    channel: Optional[str] = None,
    system_message: Optional[str] = None,
    auto_broadcast: bool = True,
    responds_to: Optional[List[str]] = None,
    memory: Union[bool, Dict[str, Any]] = False,
    knowledge_base: Optional[str] = None,
    tools: Optional[List[Union[str, Callable]]] = None,
    tool_categories: Optional[List[str]] = None,
    auto_discover_tools: bool = True,
    on_error: Union[str, Callable[[Exception, Any], None]] = "log",
    hitl: bool = False,
) -> Callable[[Callable], Callable]:
    """
    Decorator that turns a function into an autonomous agent.

    Args:
        name: Agent name (defaults to function name)
        channel: Channel to subscribe to (defaults to name + "_channel")
        system_message: System message (defaults to function docstring)
        auto_broadcast: Whether to auto-broadcast return values
        responds_to: List of message types this agent responds to (None = all messages)
        memory: Memory configuration - True for defaults, dict for custom config, False
        to disable
        knowledge_base: Path to knowledge base files for auto-indexing
        on_error: Error handling strategy:
            - "log" (default): Log error and continue processing
            - "raise": Re-raise exception to caller
            - "ignore": Silently ignore errors (not recommended)
            - callable: Custom error handler function(exception, spore)

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

    Agent with custom error handling::

        def my_error_handler(error, spore):
            print(f"Error in agent: {error}")
            # Custom recovery logic here

        @agent("processor", on_error=my_error_handler)
        def process_agent(spore):
            '''Process with custom error handling.'''
            return {"processed": True}
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
            knowledge_base=knowledge_base,
            hitl_enabled=hitl,
        )

        def agent_handler(spore: Any) -> Any:
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
            _agent_context.startup_channel = getattr(
                underlying_agent, "_startup_channel", None
            )

            result = None
            try:
                # Resolve knowledge references in spore if memory is enabled
                if memory_enabled and hasattr(spore, "has_knowledge_references"):
                    if spore.has_knowledge_references():
                        try:
                            resolved_knowledge = (
                                underlying_agent.resolve_spore_knowledge(spore)
                            )
                            spore.resolved_knowledge = resolved_knowledge
                        except Exception as e:
                            # Knowledge resolution errors are non-fatal, log and
                            # continue
                            _handle_agent_error(
                                e,
                                spore,
                                agent_name,
                                on_error,
                                context="knowledge_resolution",
                            )

                # Call the decorated function
                result = func(spore)

                # Store conversation turn in memory if enabled
                if memory_enabled and underlying_agent.memory:
                    try:
                        query = (
                            str(spore.knowledge) if spore.knowledge else "interaction"
                        )
                        response = str(result) if result else "no_response"

                        underlying_agent.memory.store_conversation_turn(
                            agent_id=agent_name,
                            user_message=query,
                            agent_response=response,
                            context={
                                "spore_id": spore.id,
                                "spore_type": spore.spore_type.value,
                            },
                        )
                    except Exception as e:
                        # Memory storage errors are non-fatal, log and continue
                        _handle_agent_error(
                            e, spore, agent_name, on_error, context="memory_storage"
                        )

                # Auto-broadcast return values if enabled and result exists
                if auto_broadcast and result and isinstance(result, dict):
                    underlying_agent.broadcast_knowledge(
                        {**result, "_from": agent_name, "_timestamp": time.time()},
                        channel=agent_channel,
                    )

            except InterventionRequired:
                raise
            except Exception as e:
                # Main handler error - use configured error handling strategy
                _handle_agent_error(e, spore, agent_name, on_error, context="handler")

            finally:
                # Clean up context
                _agent_context.agent = None
                _agent_context.channel = None
                _agent_context.startup_channel = None

            return result

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
        reef.subscribe(
            agent_name,
            underlying_agent.on_spore_received,
            channel=reef.default_channel,
            replace=True,
        )

        # Tool attachment based on decorator params
        registry = get_tool_registry()
        if tool_categories:
            for category in tool_categories:
                for tool in registry.get_tools_by_category(category):
                    _attach_registry_tool(underlying_agent, tool)

        if tools:
            for tool_entry in tools:
                if isinstance(tool_entry, str):
                    tool_obj = registry.get_tool(tool_entry)
                    if tool_obj:
                        _attach_registry_tool(underlying_agent, tool_obj)
                    else:
                        logger.debug("Tool '%s' not found in registry", tool_entry)
                elif callable(tool_entry):
                    tool_obj = _register_callable_tool(agent_name, tool_entry)
                    if tool_obj:
                        _attach_registry_tool(underlying_agent, tool_obj)
                    else:
                        logger.debug(
                            "Tool callable '%s' failed to register",
                            getattr(tool_entry, "__name__", str(tool_entry)),
                        )
                else:
                    logger.debug("Unsupported tool entry type: %s", type(tool_entry))

        if auto_discover_tools:
            # Auto-register tools from the tool registry
            _auto_register_tools(underlying_agent, agent_name)

        decorated_func: Any = func

        # Add memory methods to the function for easy access
        if memory_enabled:
            decorated_func.remember = underlying_agent.remember
            decorated_func.recall = underlying_agent.recall
            decorated_func.recall_by_id = underlying_agent.recall_by_id
            decorated_func.get_conversation_context = (
                underlying_agent.get_conversation_context
            )
            decorated_func.create_knowledge_reference = (
                underlying_agent.create_knowledge_reference
            )
            decorated_func.send_lightweight_knowledge = (
                underlying_agent.send_lightweight_knowledge
            )
            # Direct memory manager access
            decorated_func.memory = underlying_agent.memory

        # Add reef communication methods
        decorated_func.send_knowledge = underlying_agent.send_knowledge
        decorated_func.broadcast_knowledge = underlying_agent.broadcast_knowledge
        decorated_func.request_knowledge = underlying_agent.request_knowledge

        # Add HITL methods
        decorated_func.configure_hitl = underlying_agent.configure_hitl
        decorated_func.get_pending_interventions = (
            underlying_agent.get_pending_interventions
        )
        decorated_func.approve_intervention = underlying_agent.approve_intervention
        decorated_func.reject_intervention = underlying_agent.reject_intervention
        decorated_func.resume_run = underlying_agent.resume_run

        # Add tool management methods
        decorated_func.tool = underlying_agent.tool
        decorated_func.add_tool = underlying_agent.tool  # Alias for compatibility
        decorated_func.list_tools = lambda: list(underlying_agent.tools.keys())
        decorated_func.get_tool = lambda name: underlying_agent.tools.get(name)
        decorated_func.has_tool = lambda name: name in underlying_agent.tools

        # Store metadata on function for composition and introspection
        decorated_func._praval_agent = underlying_agent
        decorated_func._praval_name = agent_name
        decorated_func._praval_channel = agent_channel
        decorated_func._praval_auto_broadcast = auto_broadcast
        decorated_func._praval_responds_to = responds_to
        decorated_func._praval_memory_enabled = memory_enabled
        decorated_func._praval_knowledge_base = knowledge_base
        decorated_func._praval_on_error = on_error
        decorated_func._praval_hitl_enabled = hitl

        # Return the original function with metadata attached
        return cast(Callable, decorated_func)

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
    if not hasattr(_agent_context, "agent") or _agent_context.agent is None:
        raise RuntimeError("chat() can only be used within @agent decorated functions")

    import concurrent.futures

    def timeout_handler(signum: Any, frame: Any) -> None:
        raise TimeoutError(f"LLM call timed out after {timeout} seconds")

    # Use thread-based timeout for better cross-platform support
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_agent_context.agent.chat, message)
        try:
            return cast(str, future.result(timeout=timeout))
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
    if not hasattr(_agent_context, "agent") or _agent_context.agent is None:
        raise RuntimeError("achat() can only be used within @agent decorated functions")

    # Run the sync chat in a thread to avoid blocking the event loop
    import asyncio

    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, _agent_context.agent.chat, message),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        raise TimeoutError(f"LLM call timed out after {timeout} seconds")


def broadcast(
    data: Dict[str, Any],
    channel: Optional[str] = None,
    message_type: Optional[str] = None,
) -> str:
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
    if not hasattr(_agent_context, "agent") or _agent_context.agent is None:
        raise RuntimeError(
            "broadcast() can only be used within @agent decorated functions"
        )

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
        channel = getattr(_agent_context, "startup_channel", None)
        if channel is None:
            reef = get_reef()
            channel = reef.default_channel

    return cast(
        str, _agent_context.agent.broadcast_knowledge(broadcast_data, channel=channel)
    )


def get_agent_info(agent_func: Callable) -> Dict[str, Any]:
    """
    Get information about an @agent decorated function.

    Args:
        agent_func: Function decorated with @agent

    Returns:
        Dictionary with agent metadata
    """
    if not hasattr(agent_func, "_praval_agent"):
        raise ValueError("Function is not decorated with @agent")

    typed_agent_func = cast(Any, agent_func)
    return {
        "name": typed_agent_func._praval_name,
        "channel": typed_agent_func._praval_channel,
        "auto_broadcast": typed_agent_func._praval_auto_broadcast,
        "responds_to": typed_agent_func._praval_responds_to,
        "on_error": getattr(typed_agent_func, "_praval_on_error", "log"),
        "hitl": getattr(typed_agent_func, "_praval_hitl_enabled", False),
        "underlying_agent": typed_agent_func._praval_agent,
    }
