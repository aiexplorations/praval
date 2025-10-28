"""
Reef Communication System for Praval Framework.

Like coral reefs facilitate communication between polyps through chemical and biological signals,
this system enables knowledge-first communication between agents through structured JSON message queues.

Components:
- Spores: JSON messages containing knowledge, data, or requests
- ReefChannel: Named message channels within the reef
- Reef: The message queue network connecting all agents
"""

import json
import time
import uuid
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future
import asyncio
import inspect


logger = logging.getLogger(__name__)


class SporeType(Enum):
    """Types of spores that can flow through the reef."""
    KNOWLEDGE = "knowledge"      # Pure knowledge/data sharing
    REQUEST = "request"          # Request for information or action
    RESPONSE = "response"        # Response to a request
    BROADCAST = "broadcast"      # Message to all agents
    NOTIFICATION = "notification" # Event notification


@dataclass
class Spore:
    """
    A spore is a knowledge-carrying message that flows through the reef.
    
    Like biological spores, each carries:
    - Genetic material (knowledge/data)  
    - Identification markers (metadata)
    - Survival instructions (processing hints)
    
    Spores can carry either direct knowledge or lightweight references to
    knowledge stored in vector memory, following the principle that
    "light spores travel far."
    """
    id: str
    spore_type: SporeType
    from_agent: str
    to_agent: Optional[str]  # None for broadcasts
    knowledge: Dict[str, Any]  # The actual data payload
    created_at: datetime
    expires_at: Optional[datetime] = None
    priority: int = 5  # 1-10, higher = more urgent
    reply_to: Optional[str] = None  # For request-response patterns
    metadata: Dict[str, Any] = None
    knowledge_references: List[str] = None  # References to stored knowledge  
    data_references: List[str] = None  # References to storage system data
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.knowledge_references is None:
            self.knowledge_references = []
        if self.data_references is None:
            self.data_references = []
    
    def to_json(self) -> str:
        """Serialize spore to JSON for transmission."""
        data = asdict(self)
        # Handle datetime serialization
        data['created_at'] = self.created_at.isoformat()
        if self.expires_at:
            data['expires_at'] = self.expires_at.isoformat()
        data['spore_type'] = self.spore_type.value
        return json.dumps(data, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Spore':
        """Deserialize spore from JSON."""
        data = json.loads(json_str)
        # Handle datetime deserialization
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('expires_at'):
            data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        data['spore_type'] = SporeType(data['spore_type'])
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if spore has expired."""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at
    
    def add_knowledge_reference(self, reference_id: str):
        """Add a reference to stored knowledge"""
        if reference_id not in self.knowledge_references:
            self.knowledge_references.append(reference_id)
    
    def add_data_reference(self, reference_uri: str):
        """Add a reference to storage system data"""
        if reference_uri not in self.data_references:
            self.data_references.append(reference_uri)
    
    def has_knowledge_references(self) -> bool:
        """Check if spore has knowledge references"""
        return len(self.knowledge_references) > 0
    
    def has_data_references(self) -> bool:
        """Check if spore has data references"""
        return len(self.data_references) > 0
    
    def has_any_references(self) -> bool:
        """Check if spore has any kind of references"""
        return self.has_knowledge_references() or self.has_data_references()
    
    def get_spore_size_estimate(self) -> int:
        """Estimate spore size for lightweight transmission"""
        import json
        try:
            # Estimate JSON size without actually serializing (for performance)
            knowledge_size = len(str(self.knowledge)) if self.knowledge else 0
            metadata_size = len(str(self.metadata)) if self.metadata else 0
            refs_size = len(str(self.knowledge_references)) if self.knowledge_references else 0
            
            # Add approximate overhead for other fields
            overhead = 500  # Estimated JSON overhead
            
            return knowledge_size + metadata_size + refs_size + overhead
        except:
            # Fallback to actual serialization if estimation fails
            return len(self.to_json())


class ReefChannel:
    """
    A message channel within the reef.
    
    Like channels in a coral reef, they:
    - Have directional flow patterns
    - Can carry multiple spores simultaneously  
    - Have capacity limits (to prevent overwhelming)
    - Can experience turbulence (message loss/delays)
    """
    
    def __init__(self, name: str, max_capacity: int = 1000, max_workers: int = 4):
        self.name = name
        self.max_capacity = max_capacity
        self.spores: deque = deque(maxlen=max_capacity)
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=f"reef-{name}")
        self._shutdown = False
        self.stats = {
            'spores_carried': 0,
            'spores_delivered': 0,
            'spores_expired': 0,
            'created_at': datetime.now()
        }
    
    def send_spore(self, spore: Spore) -> bool:
        """Send a spore through this channel."""
        with self.lock:
            if len(self.spores) >= self.max_capacity:
                # Channel at capacity - oldest spores drift away
                self.spores.popleft()
            
            self.spores.append(spore)
            self.stats['spores_carried'] += 1
            
            # Immediately try to deliver to subscribers
            self._deliver_spore(spore)
            return True
    
    def _deliver_spore(self, spore: Spore) -> List[Future]:
        """Deliver spore to subscribed agents asynchronously."""
        if spore.is_expired():
            self.stats['spores_expired'] += 1
            return []
        
        if self._shutdown:
            return []
        
        futures = []
        
        # Deliver to specific agent if targeted
        if spore.to_agent and spore.to_agent in self.subscribers:
            for handler in self.subscribers[spore.to_agent]:
                future = self._execute_handler_async(handler, spore)
                if future:
                    futures.append(future)
        
        # Deliver broadcasts to all subscribers except sender
        elif spore.spore_type == SporeType.BROADCAST:
            for agent_name, handlers in self.subscribers.items():
                if agent_name != spore.from_agent:  # Don't deliver to sender
                    for handler in handlers:
                        future = self._execute_handler_async(handler, spore)
                        if future:
                            futures.append(future)
        
        return futures
    
    def _execute_handler_async(self, handler: Callable, spore: Spore) -> Optional[Future]:
        """Execute handler asynchronously, supporting both sync and async handlers."""
        if self._shutdown:
            return None
        
        def safe_handler_wrapper():
            try:
                # Check if handler is async
                if inspect.iscoroutinefunction(handler):
                    # Run async handler in new event loop
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result = loop.run_until_complete(handler(spore))
                        self.stats['spores_delivered'] += 1
                        return result
                    finally:
                        loop.close()
                else:
                    # Run sync handler directly
                    result = handler(spore)
                    self.stats['spores_delivered'] += 1
                    return result
            except Exception as e:
                # Log errors but don't break the system
                logger.warning(f"Agent handler error in channel {self.name}: {e}")
                return None
        
        return self.executor.submit(safe_handler_wrapper)
    
    def subscribe(self, agent_name: str, handler: Callable[[Spore], None], replace: bool = True) -> None:
        """
        Subscribe an agent to receive spores from this channel.

        Args:
            agent_name: Name of the agent subscribing
            handler: Callback function to handle received spores
            replace: If True (default), replaces existing handlers for this agent.
                    If False, adds handler to the list (useful for multiple handlers).

        Note:
            Default behavior (replace=True) ensures that re-registering an agent
            in interactive environments (like Jupyter notebooks) doesn't create
            duplicate subscriptions. Set replace=False if you intentionally want
            multiple handlers for the same agent.
        """
        with self.lock:
            if replace:
                # Replace all existing handlers with this new one
                self.subscribers[agent_name] = [handler]
            else:
                # Append to existing handlers
                self.subscribers[agent_name].append(handler)
    
    def unsubscribe(self, agent_name: str) -> None:
        """Unsubscribe an agent from this channel."""
        with self.lock:
            if agent_name in self.subscribers:
                del self.subscribers[agent_name]
    
    def get_spores_for_agent(self, agent_name: str, limit: int = 10) -> List[Spore]:
        """Get recent spores for a specific agent (polling interface)."""
        with self.lock:
            relevant_spores = []
            for spore in reversed(self.spores):  # Most recent first
                if len(relevant_spores) >= limit:
                    break
                
                if spore.is_expired():
                    continue
                
                # Include if targeted to this agent or is a broadcast
                if (spore.to_agent == agent_name or 
                    (spore.spore_type == SporeType.BROADCAST and 
                     spore.from_agent != agent_name)):
                    relevant_spores.append(spore)
            
            return relevant_spores
    
    def cleanup_expired(self) -> int:
        """Remove expired spores from the channel."""
        with self.lock:
            initial_count = len(self.spores)
            self.spores = deque([s for s in self.spores if not s.is_expired()], 
                              maxlen=self.max_capacity)
            expired_count = initial_count - len(self.spores)
            self.stats['spores_expired'] += expired_count
            return expired_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get channel statistics."""
        with self.lock:
            return {
                'name': self.name,
                'spores_in_channel': len(self.spores),
                'max_capacity': self.max_capacity,
                'subscriber_count': sum(len(handlers) for handlers in self.subscribers.values()),
                'active_threads': len(self.executor._threads) if hasattr(self.executor, '_threads') else 0,
                'shutdown': self._shutdown,
                **self.stats
            }
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the channel's thread pool."""
        self._shutdown = True
        self.executor.shutdown(wait=wait)


class Reef:
    """
    The Reef manages all communication channels and facilitates agent communication.
    
    Like a coral reef ecosystem, it:
    - Maintains multiple communication channels
    - Enables knowledge flow between polyps (agents)
    - Supports both direct and broadcast communication
    - Provides network health monitoring
    """
    
    def __init__(self, default_max_workers: int = 4):
        self.channels: Dict[str, ReefChannel] = {}
        self.default_channel = "main"
        self.default_max_workers = default_max_workers
        self.lock = threading.RLock()
        self._shutdown = False
        
        # Create default channel
        self.create_channel(self.default_channel)
        
        # Start background cleanup
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
    
    def create_channel(self, name: str, max_capacity: int = 1000, max_workers: Optional[int] = None) -> ReefChannel:
        """Create a new reef channel."""
        with self.lock:
            if name in self.channels:
                return self.channels[name]
            
            workers = max_workers or self.default_max_workers
            channel = ReefChannel(name, max_capacity, workers)
            self.channels[name] = channel
            return channel
    
    def get_channel(self, name: str) -> Optional[ReefChannel]:
        """Get a reef channel by name."""
        return self.channels.get(name)
    
    def send(self, 
             from_agent: str,
             to_agent: Optional[str],
             knowledge: Dict[str, Any],
             spore_type: SporeType = SporeType.KNOWLEDGE,
             channel: str = None,
             priority: int = 5,
             expires_in_seconds: Optional[int] = None,
             reply_to: Optional[str] = None,
             knowledge_references: Optional[List[str]] = None,
             auto_reference_large_knowledge: bool = True) -> str:
        """Send a spore through the reef."""
        
        # Use default channel if none specified
        if channel is None:
            channel = self.default_channel
        
        reef_channel = self.get_channel(channel)
        if not reef_channel:
            raise ValueError(f"Reef channel '{channel}' not found")
        
        # Create expiration time if specified
        expires_at = None
        if expires_in_seconds:
            expires_at = datetime.now() + timedelta(seconds=expires_in_seconds)
        
        # Handle knowledge references for lightweight spores
        final_knowledge = knowledge
        final_references = knowledge_references or []
        
        # Auto-reference large knowledge if enabled
        if auto_reference_large_knowledge and knowledge:
            knowledge_size = len(str(knowledge))
            if knowledge_size > 1000:  # Threshold for large knowledge
                # TODO: Store knowledge and replace with reference
                # This would require access to a memory manager
                logger.debug(f"Large knowledge detected ({knowledge_size} chars) - consider using references")
        
        # Create spore
        spore = Spore(
            id=str(uuid.uuid4()),
            spore_type=spore_type,
            from_agent=from_agent,
            to_agent=to_agent,
            knowledge=final_knowledge,
            created_at=datetime.now(),
            expires_at=expires_at,
            priority=priority,
            reply_to=reply_to,
            knowledge_references=final_references
        )
        
        # Send through channel
        reef_channel.send_spore(spore)
        return spore.id
    
    def broadcast(self, 
                  from_agent: str,
                  knowledge: Dict[str, Any],
                  channel: str = None) -> str:
        """Broadcast knowledge to all agents in the reef."""
        return self.send(
            from_agent=from_agent,
            to_agent=None,
            knowledge=knowledge,
            spore_type=SporeType.BROADCAST,
            channel=channel
        )
    
    def system_broadcast(self,
                        knowledge: Dict[str, Any],
                        channel: str = None) -> str:
        """Broadcast system-level messages to all agents in a channel."""
        return self.broadcast(
            from_agent="system",
            knowledge=knowledge,
            channel=channel
        )
    
    def request(self,
                from_agent: str,
                to_agent: str,
                request: Dict[str, Any],
                channel: str = None,
                expires_in_seconds: int = 300) -> str:
        """Send a knowledge request to another agent."""
        return self.send(
            from_agent=from_agent,
            to_agent=to_agent,
            knowledge=request,
            spore_type=SporeType.REQUEST,
            channel=channel,
            expires_in_seconds=expires_in_seconds
        )
    
    def reply(self,
              from_agent: str,
              to_agent: str,
              response: Dict[str, Any],
              reply_to_spore_id: str,
              channel: str = None) -> str:
        """Reply to a knowledge request."""
        return self.send(
            from_agent=from_agent,
            to_agent=to_agent,
            knowledge=response,
            spore_type=SporeType.RESPONSE,
            channel=channel,
            reply_to=reply_to_spore_id
        )
    
    def subscribe(self,
                  agent_name: str,
                  handler: Callable[[Spore], None],
                  channel: str = None,
                  replace: bool = True) -> None:
        """
        Subscribe an agent to receive spores from a channel.

        Args:
            agent_name: Name of the agent subscribing
            handler: Callback function to handle received spores
            channel: Channel name (uses default if None)
            replace: If True (default), replaces existing handlers for this agent.
                    If False, adds handler to the list.
        """
        if channel is None:
            channel = self.default_channel

        reef_channel = self.get_channel(channel)
        if reef_channel:
            reef_channel.subscribe(agent_name, handler, replace=replace)
    
    def get_network_stats(self) -> Dict[str, Any]:
        """Get statistics about the reef network."""
        with self.lock:
            stats = {
                'total_channels': len(self.channels),
                'channel_stats': {}
            }
            
            for name, channel in self.channels.items():
                stats['channel_stats'][name] = {
                    'active_spores': len(channel.spores),
                    'subscribers': len(channel.subscribers),
                    **channel.stats
                }
            
            return stats
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the reef and all its channels."""
        self._shutdown = True
        
        # Shutdown all channels
        for channel in self.channels.values():
            channel.shutdown(wait=wait)
        
        # Wait for cleanup thread to finish if requested
        if wait and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5.0)
    
    def create_knowledge_reference_spore(self,
                                        from_agent: str,
                                        to_agent: Optional[str],
                                        knowledge_summary: str,
                                        knowledge_references: List[str],
                                        spore_type: SporeType = SporeType.KNOWLEDGE,
                                        channel: str = None) -> str:
        """
        Create a lightweight spore with knowledge references
        
        This follows the reef principle: "light spores travel far"
        """
        return self.send(
            from_agent=from_agent,
            to_agent=to_agent,
            knowledge={
                "type": "knowledge_reference",
                "summary": knowledge_summary,
                "reference_count": len(knowledge_references)
            },
            spore_type=spore_type,
            channel=channel,
            knowledge_references=knowledge_references,
            auto_reference_large_knowledge=False  # Already handled
        )
    
    def resolve_knowledge_references(self, spore: Spore, memory_manager) -> Dict[str, Any]:
        """
        Resolve knowledge references in a spore to actual knowledge
        
        Args:
            spore: The spore with knowledge references
            memory_manager: Agent's memory manager to resolve references
            
        Returns:
            Combined knowledge from references
        """
        if not spore.has_knowledge_references():
            return spore.knowledge
        
        resolved_knowledge = dict(spore.knowledge) if spore.knowledge else {}
        resolved_knowledge["referenced_knowledge"] = []
        
        for ref_id in spore.knowledge_references:
            try:
                memories = memory_manager.recall_by_id(ref_id)
                if memories:
                    resolved_knowledge["referenced_knowledge"].append({
                        "reference_id": ref_id,
                        "content": memories[0].content,
                        "metadata": memories[0].metadata
                    })
            except Exception as e:
                logger.warning(f"Failed to resolve knowledge reference {ref_id}: {e}")
        
        return resolved_knowledge
    
    def _cleanup_loop(self) -> None:
        """Background thread to clean up expired spores."""
        while not self._shutdown:
            try:
                time.sleep(60)  # Cleanup every minute
                if not self._shutdown:  # Double-check before cleanup
                    for channel in self.channels.values():
                        channel.cleanup_expired()
            except Exception as e:
                # Silent cleanup failures to prevent thread death
                pass


# Global reef instance
_global_reef = Reef()


def get_reef() -> Reef:
    """Get the global reef instance."""
    return _global_reef