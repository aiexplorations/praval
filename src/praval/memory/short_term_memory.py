"""
Short-term working memory for Praval agents

This provides fast, in-memory storage for:
- Current conversation context
- Recent agent interactions
- Active tasks and goals
- Temporary state information
"""

from typing import Dict, List, Optional, Any
from collections import deque, defaultdict
from datetime import datetime, timedelta
import threading
import time

from .memory_types import MemoryEntry, MemoryType, MemoryQuery, MemorySearchResult


class ShortTermMemory:
    """
    Fast, in-memory storage for short-term agent memory
    
    Features:
    - Thread-safe operations
    - Automatic cleanup of old memories
    - Context-aware retrieval
    - Working memory capacity limits
    """
    
    def __init__(self, 
                 max_entries: int = 1000,
                 retention_hours: int = 24,
                 cleanup_interval: int = 3600):  # 1 hour
        """
        Initialize short-term memory
        
        Args:
            max_entries: Maximum number of entries to keep
            retention_hours: How long to keep memories (hours)
            cleanup_interval: How often to cleanup old memories (seconds)
        """
        self.max_entries = max_entries
        self.retention_hours = retention_hours
        self.cleanup_interval = cleanup_interval
        
        # Thread-safe storage
        self._lock = threading.RLock()
        self._memories: Dict[str, MemoryEntry] = {}
        self._agent_memories: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_entries//10))
        self._recent_memories = deque(maxlen=max_entries)
        
        # Background cleanup
        self._cleanup_thread = None
        self._shutdown = False
        self._start_cleanup_thread()
    
    def store(self, memory: MemoryEntry) -> str:
        """
        Store a memory entry
        
        Args:
            memory: The memory entry to store
            
        Returns:
            The ID of the stored memory
        """
        with self._lock:
            # Set memory type if not specified
            if memory.memory_type is None:
                memory.memory_type = MemoryType.SHORT_TERM
            
            # Store in main index
            self._memories[memory.id] = memory
            
            # Store in agent-specific index
            self._agent_memories[memory.agent_id].append(memory.id)
            
            # Store in recency index
            self._recent_memories.append(memory.id)
            
            # Trigger cleanup if needed
            if len(self._memories) > self.max_entries:
                self._cleanup_old_memories()
                
            return memory.id
    
    def retrieve(self, memory_id: str) -> Optional[MemoryEntry]:
        """
        Retrieve a specific memory by ID
        
        Args:
            memory_id: The ID of the memory to retrieve
            
        Returns:
            The memory entry if found, None otherwise
        """
        with self._lock:
            memory = self._memories.get(memory_id)
            if memory:
                memory.mark_accessed()
            return memory
    
    def search(self, query: MemoryQuery) -> MemorySearchResult:
        """
        Search memories using text similarity
        
        Args:
            query: The search query
            
        Returns:
            Search results with matching memories
        """
        with self._lock:
            matching_entries = []
            scores = []
            
            # Get candidate memories
            candidates = []
            if query.agent_id:
                # Search agent-specific memories
                agent_memory_ids = list(self._agent_memories.get(query.agent_id, []))
                candidates = [self._memories[mid] for mid in agent_memory_ids if mid in self._memories]
            else:
                # Search all memories
                candidates = list(self._memories.values())
            
            # Filter by memory type
            if query.memory_types:
                candidates = [m for m in candidates if m.memory_type in query.memory_types]
            
            # Filter by temporal constraints
            if query.temporal_filter:
                candidates = self._apply_temporal_filter(candidates, query.temporal_filter)
            
            # Simple text-based similarity scoring
            for memory in candidates:
                score = self._calculate_similarity(query.query_text, memory.content)
                if score >= query.similarity_threshold:
                    matching_entries.append(memory)
                    scores.append(score)
            
            # Sort by score descending
            sorted_results = sorted(zip(matching_entries, scores), key=lambda x: x[1], reverse=True)
            matching_entries, scores = zip(*sorted_results) if sorted_results else ([], [])
            
            # Apply limit
            matching_entries = list(matching_entries[:query.limit])
            scores = list(scores[:query.limit])
            
            # Mark accessed
            for memory in matching_entries:
                memory.mark_accessed()
            
            return MemorySearchResult(
                entries=matching_entries,
                scores=scores,
                query=query,
                total_found=len(matching_entries)
            )
    
    def get_recent(self, agent_id: Optional[str] = None, limit: int = 10) -> List[MemoryEntry]:
        """
        Get recent memories
        
        Args:
            agent_id: Filter by specific agent
            limit: Maximum number of memories to return
            
        Returns:
            List of recent memory entries
        """
        with self._lock:
            if agent_id:
                # Get recent memories for specific agent
                agent_memory_ids = list(self._agent_memories.get(agent_id, []))[-limit:]
                memories = [self._memories[mid] for mid in reversed(agent_memory_ids) if mid in self._memories]
            else:
                # Get globally recent memories
                recent_ids = list(self._recent_memories)[-limit:]
                memories = [self._memories[mid] for mid in reversed(recent_ids) if mid in self._memories]
            
            return memories
    
    def get_context(self, agent_id: str, context_size: int = 5) -> List[MemoryEntry]:
        """
        Get contextual memories for an agent
        
        Args:
            agent_id: The agent to get context for
            context_size: Number of contextual memories
            
        Returns:
            List of contextual memory entries
        """
        return self.get_recent(agent_id=agent_id, limit=context_size)
    
    def clear_agent_memories(self, agent_id: str):
        """Clear all memories for a specific agent"""
        with self._lock:
            if agent_id in self._agent_memories:
                # Remove from main storage
                for memory_id in self._agent_memories[agent_id]:
                    self._memories.pop(memory_id, None)
                
                # Clear agent index
                del self._agent_memories[agent_id]
                
                # Clean up recent memories
                self._recent_memories = deque(
                    [mid for mid in self._recent_memories if mid in self._memories],
                    maxlen=self.max_entries
                )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        with self._lock:
            return {
                'total_memories': len(self._memories),
                'agents_with_memories': len(self._agent_memories),
                'max_capacity': self.max_entries,
                'retention_hours': self.retention_hours,
                'memory_types': {
                    mtype.value: sum(1 for m in self._memories.values() if m.memory_type == mtype)
                    for mtype in MemoryType
                }
            }
    
    def _calculate_similarity(self, query: str, content: str) -> float:
        """Simple text similarity calculation"""
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        
        if not query_words or not content_words:
            return 0.0
        
        intersection = query_words & content_words
        union = query_words | content_words
        
        # Jaccard similarity
        return len(intersection) / len(union) if union else 0.0
    
    def _apply_temporal_filter(self, memories: List[MemoryEntry], 
                             temporal_filter: Dict[str, datetime]) -> List[MemoryEntry]:
        """Apply temporal filtering to memories"""
        filtered = memories
        
        if 'after' in temporal_filter:
            filtered = [m for m in filtered if m.created_at >= temporal_filter['after']]
        
        if 'before' in temporal_filter:
            filtered = [m for m in filtered if m.created_at <= temporal_filter['before']]
        
        return filtered
    
    def _cleanup_old_memories(self):
        """Clean up old memories"""
        cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)
        
        old_memory_ids = [
            memory_id for memory_id, memory in self._memories.items()
            if memory.created_at < cutoff_time and memory.importance < 0.8  # Keep important memories longer
        ]
        
        for memory_id in old_memory_ids:
            memory = self._memories.pop(memory_id, None)
            if memory and memory.agent_id in self._agent_memories:
                try:
                    self._agent_memories[memory.agent_id].remove(memory_id)
                except ValueError:
                    pass  # Already removed
        
        # Clean up recent memories deque
        self._recent_memories = deque(
            [mid for mid in self._recent_memories if mid in self._memories],
            maxlen=self.max_entries
        )
    
    def _start_cleanup_thread(self):
        """Start background cleanup thread"""
        def cleanup_worker():
            while not self._shutdown:
                time.sleep(self.cleanup_interval)
                if not self._shutdown:
                    with self._lock:
                        self._cleanup_old_memories()
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
    
    def shutdown(self):
        """Shutdown the memory system"""
        self._shutdown = True
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=1.0)