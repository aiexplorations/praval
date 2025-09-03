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
import os
from datetime import datetime

from .memory_types import MemoryEntry, MemoryType, MemoryQuery, MemorySearchResult
from .short_term_memory import ShortTermMemory
from .long_term_memory import LongTermMemory
from .episodic_memory import EpisodicMemory
from .semantic_memory import SemanticMemory
from .embedded_store import EmbeddedVectorStore


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
                 agent_id: str,
                 backend: str = "auto",
                 qdrant_url: str = "http://localhost:6333",
                 storage_path: Optional[str] = None,
                 collection_name: str = "praval_memories",
                 short_term_max_entries: int = 1000,
                 short_term_retention_hours: int = 24,
                 knowledge_base_path: Optional[str] = None):
        """
        Initialize the unified memory manager
        
        Args:
            agent_id: ID of the agent using this memory
            backend: Memory backend ("auto", "chromadb", "qdrant", "memory")
            qdrant_url: URL for Qdrant vector database
            storage_path: Path for persistent storage
            collection_name: Collection name for vector storage
            short_term_max_entries: Max entries in short-term memory
            short_term_retention_hours: Short-term memory retention time
            knowledge_base_path: Path to knowledge base files to auto-index
        """
        self.agent_id = agent_id
        self.backend = backend
        self.qdrant_url = qdrant_url
        self.storage_path = storage_path
        self.collection_name = collection_name
        self.knowledge_base_path = knowledge_base_path
        
        # Auto-detect knowledge base from environment if not provided
        if not self.knowledge_base_path:
            self.knowledge_base_path = os.getenv('PRAVAL_KNOWLEDGE_BASE')
        
        # Initialize memory subsystems based on backend preference
        self.long_term_memory = None
        self.embedded_store = None
        
        if backend in ["auto", "chromadb", "embedded"]:
            try:
                self.embedded_store = EmbeddedVectorStore(
                    storage_path=storage_path,
                    collection_name=collection_name,
                    enable_collection_separation=True  # Enable separated collections by default
                )
                self.backend = "chromadb"
                logger.info("Embedded ChromaDB memory initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize embedded memory: {e}")
                if backend != "auto":
                    raise
        
        # Fallback to Qdrant if embedded fails and auto mode
        if backend in ["auto", "qdrant"] and self.embedded_store is None:
            try:
                self.long_term_memory = LongTermMemory(
                    qdrant_url=qdrant_url,
                    collection_name=collection_name
                )
                self.backend = "qdrant"
                logger.info("Qdrant long-term memory initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Qdrant memory: {e}")
                if backend != "auto":
                    raise
        
        self.short_term_memory = ShortTermMemory(
            max_entries=short_term_max_entries,
            retention_hours=short_term_retention_hours
        )
        
        # Initialize specialized memory managers
        vector_store = self.embedded_store or self.long_term_memory
        if vector_store:
            self.episodic_memory = EpisodicMemory(
                long_term_memory=vector_store,
                short_term_memory=self.short_term_memory
            )
            self.semantic_memory = SemanticMemory(
                long_term_memory=vector_store
            )
        else:
            self.episodic_memory = None
            self.semantic_memory = None
            self.backend = "memory"
            logger.warning("Using memory-only backend - no persistent storage")
        
        # Auto-index knowledge base if provided
        if self.knowledge_base_path and vector_store:
            self._index_knowledge_base()
    
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
        
        # Store in persistent storage (embedded or qdrant)
        vector_store = self.embedded_store or self.long_term_memory
        if store_long_term and vector_store:
            try:
                vector_store.store(memory)
                logger.debug(f"Memory {memory_id} stored in both short-term and persistent memory")
            except Exception as e:
                logger.error(f"Failed to store memory {memory_id} in persistent storage: {e}")
        
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
        
        # Fallback to persistent storage
        vector_store = self.embedded_store or self.long_term_memory
        if memory is None and vector_store:
            memory = vector_store.retrieve(memory_id)
            
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
        
        # Search persistent memory if available
        vector_store = self.embedded_store or self.long_term_memory
        if vector_store:
            try:
                persistent_results = vector_store.search(query)
                results.append(("persistent", persistent_results))
            except Exception as e:
                logger.error(f"Persistent memory search failed: {e}")
                persistent_results = MemorySearchResult(entries=[], scores=[], query=query, total_found=0)
                results.append(("persistent", persistent_results))
        
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
        
        # Clear persistent memory
        vector_store = self.embedded_store or self.long_term_memory
        if vector_store:
            try:
                vector_store.clear_agent_memories(agent_id)
            except Exception as e:
                logger.error(f"Failed to clear persistent memories for {agent_id}: {e}")
        
        logger.info(f"Cleared memories for agent {agent_id}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics"""
        stats = {
            "agent_id": self.agent_id,
            "backend": self.backend,
            "short_term_memory": self.short_term_memory.get_stats(),
            "collection_name": self.collection_name
        }
        
        # Add backend-specific stats
        vector_store = self.embedded_store or self.long_term_memory
        if vector_store:
            try:
                persistent_stats = vector_store.get_stats()
                stats["persistent_memory"] = {**persistent_stats, "available": True}
            except Exception as e:
                stats["persistent_memory"] = {"available": False, "error": str(e)}
        else:
            stats["persistent_memory"] = {"available": False, "error": "Not initialized"}
        
        # Add knowledge base info
        if self.knowledge_base_path:
            stats["knowledge_base"] = {
                "path": self.knowledge_base_path,
                "indexed": True
            }
        
        if self.episodic_memory:
            stats["episodic_memory"] = self.episodic_memory.get_stats()
        
        if self.semantic_memory:
            stats["semantic_memory"] = self.semantic_memory.get_stats()
        
        return stats
    
    def health_check(self) -> Dict[str, bool]:
        """Check health of all memory systems"""
        health = {
            "short_term_memory": True,  # Always available
            "persistent_memory": False,
            "episodic_memory": False,
            "semantic_memory": False
        }
        
        vector_store = self.embedded_store or self.long_term_memory
        if vector_store:
            health["persistent_memory"] = vector_store.health_check()
            health["episodic_memory"] = health["persistent_memory"]  # Depends on persistent
            health["semantic_memory"] = health["persistent_memory"]  # Depends on persistent
        
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
    
    def _index_knowledge_base(self):
        """Index knowledge base files if path is provided"""
        from pathlib import Path
        
        if not self.knowledge_base_path:
            return
        
        kb_path = Path(self.knowledge_base_path)
        if not kb_path.exists():
            logger.warning(f"Knowledge base path does not exist: {kb_path}")
            return
        
        if not kb_path.is_dir():
            logger.warning(f"Knowledge base path is not a directory: {kb_path}")
            return
        
        try:
            vector_store = self.embedded_store or self.long_term_memory
            if hasattr(vector_store, 'index_knowledge_files'):
                indexed_count = vector_store.index_knowledge_files(kb_path, self.agent_id)
                logger.info(f"Indexed {indexed_count} knowledge base files for agent {self.agent_id}")
            else:
                logger.warning("Vector store does not support knowledge file indexing")
        except Exception as e:
            logger.error(f"Failed to index knowledge base: {e}")
    
    def recall_by_id(self, memory_id: str) -> List[MemoryEntry]:
        """Recall a specific memory by ID (for spore references)"""
        memory = self.retrieve_memory(memory_id)
        return [memory] if memory else []
    
    def get_knowledge_references(self, content: str, importance_threshold: float = 0.7) -> List[str]:
        """Get knowledge references for lightweight spores"""
        # Store the content and return reference ID
        memory_id = self.store_memory(
            agent_id=self.agent_id,
            content=content,
            memory_type=MemoryType.SEMANTIC,
            importance=importance_threshold,
            store_long_term=True
        )
        return [memory_id]
    
    def shutdown(self):
        """Shutdown all memory systems"""
        self.short_term_memory.shutdown()
        
        # No explicit shutdown needed for ChromaDB (files are auto-saved)
        # Qdrant connections will be closed automatically
        
        logger.info("Memory manager shutdown complete")