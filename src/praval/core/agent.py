"""
Core Agent class for the Praval framework.

The Agent class provides a simple, composable interface for LLM-based
conversations with support for multiple providers, tools, and state persistence.
"""

import os
import inspect
import time
import threading
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field

# Auto-load .env files if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not available, continue without it
    pass

from .exceptions import PravalError, ProviderError, ConfigurationError, ToolError
from .storage import StateStorage
from ..providers.factory import ProviderFactory


@dataclass
class AgentConfig:
    """Configuration for Agent behavior and LLM parameters."""
    provider: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1000
    system_message: Optional[str] = None
    
    def __post_init__(self):
        """Validate configuration parameters."""
        if not (0 <= self.temperature <= 2):
            raise ValueError("temperature must be between 0 and 2")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")


class Agent:
    """
    A simple, composable LLM agent.
    
    The Agent class provides the core functionality for LLM-based conversations
    with support for multiple providers, conversation history, tools, and
    state persistence.
    
    Examples:
        Basic usage:
        >>> agent = Agent("assistant")
        >>> response = agent.chat("Hello!")
        
        With persistence:
        >>> agent = Agent("my_agent", persist_state=True)
        >>> agent.chat("Remember this conversation")
        
        With tools:
        >>> agent = Agent("calculator")
        >>> @agent.tool
        >>> def add(x: int, y: int) -> int:
        ...     return x + y
    """
    
    def __init__(
        self,
        name: str,
        provider: Optional[str] = None,
        persist_state: bool = False,
        system_message: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        memory_enabled: bool = False,
        memory_config: Optional[Dict[str, Any]] = None,
        knowledge_base: Optional[str] = None
    ):
        """
        Initialize a new Agent.
        
        Args:
            name: Unique identifier for this agent
            provider: LLM provider to use (openai, anthropic, cohere)
            persist_state: Whether to persist conversation state
            system_message: System message to set agent behavior
            config: Additional configuration parameters
            memory_enabled: Whether to enable vector memory capabilities
            memory_config: Configuration for memory system
            knowledge_base: Path to knowledge base files to auto-index
            
        Raises:
            ValueError: If name is empty or configuration is invalid
            ProviderError: If provider setup fails
        """
        if not name:
            raise ValueError("Agent name cannot be empty")
            
        self.name = name
        self.persist_state = persist_state
        self.memory_enabled = memory_enabled
        self.knowledge_base = knowledge_base
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.conversation_history: List[Dict[str, str]] = []
        
        # Setup configuration
        config_dict = config or {}
        if system_message:
            config_dict["system_message"] = system_message
        if provider:
            config_dict["provider"] = provider
            
        self.config = AgentConfig(**config_dict)
        
        # Setup provider
        self.provider_name = self._detect_provider()
        self.provider = ProviderFactory.create_provider(
            self.provider_name,
            self.config
        )
        
        # Setup memory system
        if self.memory_enabled:
            self._init_memory_system(memory_config)
        else:
            self.memory = None
        
        # Setup state storage
        if self.persist_state:
            self._storage = StateStorage()
            self._load_state()
        else:
            self._storage = None
            
        # Add system message to conversation if provided
        if self.config.system_message:
            self.conversation_history.append({
                "role": "system",
                "content": self.config.system_message
            })
    
    def _detect_provider(self) -> str:
        """
        Automatically detect LLM provider from environment variables or config.
        
        Returns:
            Provider name (openai, anthropic, cohere)
            
        Raises:
            ProviderError: If no provider credentials are found
        """
        if self.config.provider:
            return self.config.provider
            
        # Check environment variables for API keys
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        elif os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"
        elif os.getenv("COHERE_API_KEY"):
            return "cohere"
        else:
            raise ProviderError(
                "No LLM provider credentials found. Set OPENAI_API_KEY, "
                "ANTHROPIC_API_KEY, or COHERE_API_KEY environment variable, "
                "or specify provider explicitly."
            )
    
    def chat(self, message: Union[str, None]) -> str:
        """
        Send a message to the agent and get a response.
        
        Args:
            message: User message to send to the agent
            
        Returns:
            Agent's response as a string
            
        Raises:
            ValueError: If message is empty or None
            PravalError: If response generation fails
        """
        if not message:
            raise ValueError("Message cannot be empty")
            
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": message
        })
        
        try:
            # Generate response using provider
            response = self.provider.generate(
                messages=self.conversation_history,
                tools=list(self.tools.values()) if self.tools else None
            )
            
            # Add assistant response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            # Save state if persistence is enabled
            if self.persist_state:
                self._save_state()
                
            return response
            
        except Exception as e:
            raise PravalError(f"Failed to generate response: {str(e)}") from e
    
    def tool(self, func: Callable) -> Callable:
        """
        Decorator to register a function as a tool for the agent.
        
        Args:
            func: Function to register as a tool
            
        Returns:
            The original function (unchanged)
            
        Raises:
            ValueError: If function lacks proper type hints
        """
        # Validate function signature
        sig = inspect.signature(func)
        for param in sig.parameters.values():
            if param.annotation == inspect.Parameter.empty:
                raise ValueError(
                    "Tool functions must have type hints for all parameters"
                )
        
        if sig.return_annotation == inspect.Signature.empty:
            raise ValueError("Tool functions must have a return type hint")
        
        # Register tool
        self.tools[func.__name__] = {
            "function": func,
            "description": func.__doc__ or "",
            "parameters": self._extract_parameters(sig)
        }
        
        return func
    
    def _extract_parameters(self, signature: inspect.Signature) -> Dict[str, Any]:
        """Extract parameter information from function signature."""
        parameters = {}
        for name, param in signature.parameters.items():
            parameters[name] = {
                "type": param.annotation.__name__ if hasattr(param.annotation, "__name__") else str(param.annotation),
                "required": param.default == inspect.Parameter.empty
            }
        return parameters
    
    def _save_state(self) -> None:
        """Save current conversation state to storage."""
        if self._storage:
            self._storage.save(self.name, self.conversation_history)
    
    def _load_state(self) -> None:
        """Load conversation state from storage."""
        if self._storage:
            saved_state = self._storage.load(self.name)
            if saved_state:
                self.conversation_history = saved_state
    
    # ==========================================
    # REEF COMMUNICATION METHODS
    # ==========================================
    
    def send_knowledge(self, to_agent: str, knowledge: Dict[str, Any], 
                      channel: str = "main") -> str:
        """
        Send knowledge to another agent through the reef.
        
        Args:
            to_agent: Name of the target agent
            knowledge: Knowledge data to send
            channel: Reef channel to use (default: "main")
            
        Returns:
            Spore ID of the sent message
        """
        from .reef import get_reef
        
        return get_reef().send(
            from_agent=self.name,
            to_agent=to_agent,
            knowledge=knowledge,
            channel=channel
        )
    
    def broadcast_knowledge(self, knowledge: Dict[str, Any], 
                           channel: str = "main") -> str:
        """
        Broadcast knowledge to all agents in the reef.
        
        Args:
            knowledge: Knowledge data to broadcast
            channel: Reef channel to use (default: "main")
            
        Returns:
            Spore ID of the broadcast message
        """
        from .reef import get_reef
        
        return get_reef().broadcast(
            from_agent=self.name,
            knowledge=knowledge,
            channel=channel
        )
    
    def request_knowledge(self, from_agent: str, request: Dict[str, Any], 
                         timeout: int = 30) -> Optional[Dict[str, Any]]:
        """
        Request knowledge from another agent with timeout.
        
        Args:
            from_agent: Name of the agent to request from
            request: Request data
            timeout: Timeout in seconds
            
        Returns:
            Response data or None if timeout
        """
        from .reef import get_reef, SporeType
        
        # Set up response collection
        response_received = threading.Event()
        response_data = {"result": None}
        
        def response_handler(spore):
            """Handle response spore."""
            if (spore.spore_type == SporeType.RESPONSE and 
                spore.to_agent == self.name and
                spore.from_agent == from_agent):
                response_data["result"] = spore.knowledge
                response_received.set()
        
        # Subscribe to receive response
        reef = get_reef()
        reef.subscribe(self.name, response_handler)
        
        try:
            # Send request
            reef.request(
                from_agent=self.name,
                to_agent=from_agent,
                request=request,
                expires_in_seconds=timeout
            )
            
            # Wait for response
            if response_received.wait(timeout):
                return response_data["result"]
            else:
                return None
                
        finally:
            # Note: In a full implementation, we'd want proper cleanup
            # of the subscription, but for now this basic approach works
            pass
    
    def on_spore_received(self, spore) -> None:
        """
        Handle received spores from the reef.
        
        This is a default implementation that can be overridden
        by subclasses for custom spore handling.
        
        Args:
            spore: The received Spore object
        """
        # Use custom handler if set, otherwise do nothing
        if hasattr(self, '_custom_spore_handler') and self._custom_spore_handler:
            self._custom_spore_handler(spore)
        # Default implementation does nothing
        # Subclasses can override for custom behavior
    
    def subscribe_to_channel(self, channel_name: str) -> None:
        """
        Subscribe this agent to a reef channel.
        
        Args:
            channel_name: Name of the channel to subscribe to
        """
        from .reef import get_reef
        
        reef = get_reef()
        # Create channel if it doesn't exist
        reef.create_channel(channel_name)
        reef.subscribe(self.name, self.on_spore_received, channel_name)
    
    def unsubscribe_from_channel(self, channel_name: str) -> None:
        """
        Unsubscribe this agent from a reef channel.
        
        Args:
            channel_name: Name of the channel to unsubscribe from
        """
        from .reef import get_reef
        
        reef = get_reef()
        channel = reef.get_channel(channel_name)
        if channel:
            channel.unsubscribe(self.name)
    
    def set_spore_handler(self, handler: Callable) -> None:
        """
        Set a custom spore handler for this agent.
        
        Args:
            handler: Function that takes a Spore object and handles it
        """
        self._custom_spore_handler = handler
    
    # ==========================================
    # MEMORY SYSTEM METHODS
    # ==========================================
    
    def _init_memory_system(self, memory_config: Optional[Dict[str, Any]] = None):
        """Initialize the memory system for this agent"""
        try:
            from ..memory import MemoryManager
            
            # Default memory configuration
            default_config = {
                "backend": "auto",
                "collection_name": f"praval_memories_{self.name}",
                "knowledge_base_path": self.knowledge_base
            }
            
            # Merge with provided config
            if memory_config:
                default_config.update(memory_config)
            
            # Initialize memory manager
            self.memory = MemoryManager(
                agent_id=self.name,
                **default_config
            )
            
            # Note: logger not imported, using print for now
            print(f"Memory system initialized for agent {self.name}")
            
        except ImportError as e:
            print(f"Memory system not available: {e}")
            self.memory = None
            self.memory_enabled = False
        except Exception as e:
            print(f"Failed to initialize memory system for {self.name}: {e}")
            self.memory = None
            self.memory_enabled = False
    
    def remember(self, content: str, 
                 importance: float = 0.5,
                 memory_type: str = "short_term") -> Optional[str]:
        """
        Store a memory
        
        Args:
            content: The content to remember
            importance: Importance score (0.0 to 1.0)
            memory_type: Type of memory ("short_term", "semantic", "episodic")
            
        Returns:
            Memory ID if successful, None otherwise
        """
        if not self.memory:
            print(f"Memory not enabled for agent {self.name}")
            return None
        
        try:
            from ..memory import MemoryType
            
            # Map string to MemoryType enum
            type_mapping = {
                "short_term": MemoryType.SHORT_TERM,
                "semantic": MemoryType.SEMANTIC,
                "episodic": MemoryType.EPISODIC,
                "working": MemoryType.SHORT_TERM
            }
            
            mem_type = type_mapping.get(memory_type, MemoryType.SHORT_TERM)
            
            return self.memory.store_memory(
                agent_id=self.name,
                content=content,
                memory_type=mem_type,
                importance=importance
            )
            
        except Exception as e:
            print(f"Failed to store memory: {e}")
            return None
    
    def recall(self, query: str, limit: int = 5, 
              similarity_threshold: float = 0.1) -> List:
        """
        Recall memories based on a query
        
        Args:
            query: Search query
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of MemoryEntry objects
        """
        if not self.memory:
            print(f"Memory not enabled for agent {self.name}")
            return []
        
        try:
            from ..memory import MemoryQuery
            
            memory_query = MemoryQuery(
                query_text=query,
                agent_id=self.name,
                limit=limit,
                similarity_threshold=similarity_threshold
            )
            
            results = self.memory.search_memories(memory_query)
            return results.entries
            
        except Exception as e:
            print(f"Failed to recall memories: {e}")
            return []
    
    def recall_by_id(self, memory_id: str) -> List:
        """Recall a specific memory by ID (for resolving spore references)"""
        if not self.memory:
            return []
        
        return self.memory.recall_by_id(memory_id)
    
    def get_conversation_context(self, turns: int = 10) -> List:
        """Get recent conversation context"""
        if not self.memory:
            return []
        
        return self.memory.get_conversation_context(self.name, turns)
    
    def create_knowledge_reference(self, content: str, 
                                  importance: float = 0.8) -> List[str]:
        """
        Create knowledge references for lightweight spores
        
        Args:
            content: Knowledge content to store and reference
            importance: Importance threshold
            
        Returns:
            List of knowledge reference IDs
        """
        if not self.memory:
            return []
        
        try:
            return self.memory.get_knowledge_references(content, importance)
        except Exception as e:
            print(f"Failed to create knowledge reference: {e}")
            return []
    
    def resolve_spore_knowledge(self, spore) -> Dict[str, Any]:
        """
        Resolve knowledge references in a spore
        
        Args:
            spore: Spore object with potential knowledge references
            
        Returns:
            Complete knowledge including resolved references
        """
        if not self.memory:
            return spore.knowledge
        
        try:
            from .reef import get_reef
            reef = get_reef()
            return reef.resolve_knowledge_references(spore, self.memory)
        except Exception as e:
            print(f"Failed to resolve spore knowledge: {e}")
            return spore.knowledge
    
    def send_lightweight_knowledge(self, to_agent: str, 
                                  large_content: str,
                                  summary: str,
                                  channel: str = "main") -> str:
        """
        Send large knowledge as lightweight spore with references
        
        Args:
            to_agent: Target agent
            large_content: Large content to reference
            summary: Brief summary for the spore
            channel: Communication channel
            
        Returns:
            Spore ID
        """
        # Create knowledge reference
        refs = self.create_knowledge_reference(large_content)
        
        if not refs:
            # Fallback to direct send if referencing fails
            return self.send_knowledge(to_agent, {"content": large_content}, channel)
        
        # Send lightweight spore with reference
        from .reef import get_reef
        reef = get_reef()
        return reef.create_knowledge_reference_spore(
            from_agent=self.name,
            to_agent=to_agent,
            knowledge_summary=summary,
            knowledge_references=refs,
            channel=channel
        )