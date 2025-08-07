"""
MemoryManager - Unified interface for all Praval agent memory systems

This coordinates:
- Short-term working memory
- Long-term vector memory
- Episodic conversation memory  
- Semantic knowledge memory
"""

from typing import Dict, List, Optional, Any, Union
import logging
from datetime import datetime

from .memory_types import MemoryEntry, MemoryType, MemoryQuery, MemorySearchResult
from .short_term_memory import ShortTermMemory
from .long_term_memory import LongTermMemory
from .episodic_memory import EpisodicMemory
from .semantic_memory import SemanticMemory


logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Unified memory management system for Praval agents
    
    Provides a single interface to:
    - Store and retrieve memories across all systems
    - Coordinate between short-term and long-term storage
    - Manage different types of memory (episodic, semantic, etc.)
    - Optimize memory access patterns
    """
    
    def __init__(self,
                 qdrant_url: str = "http://localhost:6333",
                 collection_name: str = "praval_memories",
                 short_term_max_entries: int = 1000,
                 short_term_retention_hours: int = 24):
        """
        Initialize the unified memory manager
        
        Args:
            qdrant_url: URL for Qdrant vector database
            collection_name: Qdrant collection name
            short_term_max_entries: Max entries in short-term memory
            short_term_retention_hours: Short-term memory retention time
        """
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        
        # Initialize memory subsystems
        try:
            self.long_term_memory = LongTermMemory(
                qdrant_url=qdrant_url,
                collection_name=collection_name
            )
            logger.info("Long-term memory initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize long-term memory: {e}")
            self.long_term_memory = None
        
        self.short_term_memory = ShortTermMemory(
            max_entries=short_term_max_entries,
            retention_hours=short_term_retention_hours
        )
        
        # Initialize specialized memory managers
        if self.long_term_memory:
            self.episodic_memory = EpisodicMemory(
                long_term_memory=self.long_term_memory,
                short_term_memory=self.short_term_memory
            )
            self.semantic_memory = SemanticMemory(
                long_term_memory=self.long_term_memory
            )
        else:
            self.episodic_memory = None
            self.semantic_memory = None
            logger.warning("Episodic and semantic memory disabled due to long-term memory failure")
    
    def store_memory(self,
                    agent_id: str,
                    content: str,
                    memory_type: MemoryType = MemoryType.SHORT_TERM,
                    metadata: Optional[Dict[str, Any]] = None,
                    importance: float = 0.5,
                    store_long_term: bool = None) -> str:
        """
        Store a memory entry
        
        Args:
            agent_id: The agent storing the memory
            content: The memory content
            memory_type: Type of memory
            metadata: Additional metadata
            importance: Importance score (0.0 to 1.0)
            store_long_term: Whether to store in long-term memory (auto-decided if None)
            
        Returns:
            Memory ID
        """
        memory = MemoryEntry(
            id=None,
            agent_id=agent_id,
            memory_type=memory_type,
            content=content,
            metadata=metadata or {},
            importance=importance
        )
        
        # Always store in short-term memory
        memory_id = self.short_term_memory.store(memory)
        
        # Decide whether to store in long-term memory
        if store_long_term is None:
            store_long_term = self._should_store_long_term(memory)
        
        if store_long_term and self.long_term_memory:
            try:
                self.long_term_memory.store(memory)
                logger.debug(f"Memory {memory_id} stored in both short-term and long-term memory")
            except Exception as e:
                logger.error(f"Failed to store memory {memory_id} in long-term storage: {e}")
        
        return memory_id
    
    def retrieve_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """
        Retrieve a specific memory by ID
        
        Args:
            memory_id: The memory ID
            
        Returns:
            The memory entry if found
        """
        # Try short-term memory first (faster)
        memory = self.short_term_memory.retrieve(memory_id)
        
        if memory is None and self.long_term_memory:
            # Fallback to long-term memory
            memory = self.long_term_memory.retrieve(memory_id)
            
            # Cache in short-term memory for future access
            if memory:
                self.short_term_memory.store(memory)
        
        return memory
    
    def search_memories(self, query: MemoryQuery) -> MemorySearchResult:
        """
        Search memories across all systems
        
        Args:
            query: The search query
            
        Returns:
            Combined search results
        """
        results = []
        
        # Search short-term memory
        st_results = self.short_term_memory.search(query)
        results.append(("short_term", st_results))
        
        # Search long-term memory if available
        if self.long_term_memory:
            try:
                lt_results = self.long_term_memory.search(query)
                results.append(("long_term", lt_results))
            except Exception as e:
                logger.error(f"Long-term memory search failed: {e}")
                lt_results = MemorySearchResult(entries=[], scores=[], query=query, total_found=0)
                results.append(("long_term", lt_results))
        
        # Combine and deduplicate results
        return self._combine_search_results(results, query)
    
    def get_conversation_context(self,
                               agent_id: str,
                               turns: int = 10) -> List[MemoryEntry]:
        """
        Get recent conversation context for an agent
        
        Args:
            agent_id: The agent ID
            turns: Number of conversation turns
            
        Returns:
            List of conversation memories
        """
        if self.episodic_memory:
            return self.episodic_memory.get_conversation_context(agent_id, turns)
        else:
            # Fallback to general recent memories
            return self.short_term_memory.get_recent(agent_id=agent_id, limit=turns)
    
    def store_conversation_turn(self,
                              agent_id: str,
                              user_message: str,
                              agent_response: str,
                              context: Optional[Dict[str, Any]] = None) -> str:
        """
        Store a conversation turn
        
        Args:
            agent_id: The agent ID
            user_message: User's message
            agent_response: Agent's response
            context: Additional context
            
        Returns:
            Memory ID
        """
        if self.episodic_memory:
            return self.episodic_memory.store_conversation_turn(
                agent_id, user_message, agent_response, context
            )
        else:
            # Fallback to basic memory storage
            content = f"User: {user_message}\nAgent: {agent_response}"
            return self.store_memory(
                agent_id=agent_id,
                content=content,
                memory_type=MemoryType.EPISODIC,
                metadata={"type": "conversation", "context": context},
                importance=0.7
            )
    
    def store_knowledge(self,
                       agent_id: str,
                       knowledge: str,
                       domain: str = "general",
                       confidence: float = 1.0,
                       knowledge_type: str = "fact") -> str:
        """
        Store knowledge or facts
        
        Args:
            agent_id: The agent ID
            knowledge: The knowledge content
            domain: Domain of knowledge
            confidence: Confidence in the knowledge
            knowledge_type: Type of knowledge (fact, concept, rule)
            
        Returns:
            Memory ID
        """
        if self.semantic_memory:
            if knowledge_type == "fact":
                return self.semantic_memory.store_fact(
                    agent_id, knowledge, domain, confidence
                )
            else:
                return self.semantic_memory.store_concept(
                    agent_id, knowledge, knowledge, domain
                )
        else:
            # Fallback to basic memory storage
            return self.store_memory(
                agent_id=agent_id,
                content=knowledge,
                memory_type=MemoryType.SEMANTIC,
                metadata={
                    "domain": domain,
                    "confidence": confidence,
                    "knowledge_type": knowledge_type
                },
                importance=0.8
            )
    
    def get_domain_knowledge(self,
                           agent_id: str,
                           domain: str,
                           limit: int = 20) -> List[MemoryEntry]:
        """
        Get knowledge in a specific domain
        
        Args:
            agent_id: The agent ID
            domain: The domain
            limit: Maximum results
            
        Returns:
            List of knowledge entries
        """
        if self.semantic_memory:
            return self.semantic_memory.get_knowledge_in_domain(agent_id, domain, limit)
        else:
            # Fallback search
            query = MemoryQuery(
                query_text=domain,
                memory_types=[MemoryType.SEMANTIC],
                agent_id=agent_id,
                limit=limit
            )
            results = self.search_memories(query)
            return results.entries
    
    def clear_agent_memories(self, agent_id: str, memory_types: Optional[List[MemoryType]] = None):
        """
        Clear memories for a specific agent
        
        Args:
            agent_id: The agent ID
            memory_types: Types of memory to clear (all if None)
        """
        # Clear short-term memory
        self.short_term_memory.clear_agent_memories(agent_id)
        
        # Clear long-term memory
        if self.long_term_memory:
            try:
                self.long_term_memory.clear_agent_memories(agent_id)
            except Exception as e:
                logger.error(f"Failed to clear long-term memories for {agent_id}: {e}")
        
        logger.info(f"Cleared memories for agent {agent_id}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics"""
        stats = {
            "short_term_memory": self.short_term_memory.get_stats(),
            "qdrant_url": self.qdrant_url,
            "collection_name": self.collection_name
        }
        
        if self.long_term_memory:
            try:
                stats["long_term_memory"] = self.long_term_memory.get_stats()
                stats["long_term_memory"]["available"] = True
            except Exception as e:
                stats["long_term_memory"] = {"available": False, "error": str(e)}
        else:
            stats["long_term_memory"] = {"available": False, "error": "Not initialized"}
        
        if self.episodic_memory:
            stats["episodic_memory"] = self.episodic_memory.get_stats()
        
        if self.semantic_memory:
            stats["semantic_memory"] = self.semantic_memory.get_stats()
        
        return stats
    
    def health_check(self) -> Dict[str, bool]:
        """Check health of all memory systems"""
        health = {
            "short_term_memory": True,  # Always available
            "long_term_memory": False,
            "episodic_memory": False,
            "semantic_memory": False
        }
        
        if self.long_term_memory:
            health["long_term_memory"] = self.long_term_memory.health_check()
            health["episodic_memory"] = health["long_term_memory"]  # Depends on long-term
            health["semantic_memory"] = health["long_term_memory"]  # Depends on long-term
        
        return health
    
    def _should_store_long_term(self, memory: MemoryEntry) -> bool:
        """Decide whether a memory should be stored long-term"""
        # Store important memories
        if memory.importance >= 0.7:
            return True
        
        # Store semantic and episodic memories
        if memory.memory_type in [MemoryType.SEMANTIC, MemoryType.EPISODIC]:
            return True
        
        # Store long content
        if len(memory.content) > 200:
            return True
        
        return False
    
    def _combine_search_results(self, 
                              results: List[tuple], 
                              query: MemoryQuery) -> MemorySearchResult:
        """Combine search results from multiple memory systems"""
        all_entries = []
        all_scores = []
        seen_ids = set()
        
        # Combine results, preferring short-term (more recent/relevant)
        for source, result in results:
            for entry, score in zip(result.entries, result.scores):
                if entry.id not in seen_ids:
                    all_entries.append(entry)
                    all_scores.append(score)
                    seen_ids.add(entry.id)
        
        # Sort by score (descending)
        combined = list(zip(all_entries, all_scores))
        combined.sort(key=lambda x: x[1], reverse=True)
        
        # Apply limit
        combined = combined[:query.limit]
        
        if combined:
            final_entries, final_scores = zip(*combined)
        else:
            final_entries, final_scores = [], []
        
        return MemorySearchResult(
            entries=list(final_entries),
            scores=list(final_scores),
            query=query,
            total_found=len(all_entries)
        )
    
    def shutdown(self):
        """Shutdown all memory systems"""
        self.short_term_memory.shutdown()
        logger.info("Memory manager shutdown complete")