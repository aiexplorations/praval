"""
Memory-Storage Integration

Provides seamless integration between Praval's memory system and the
unified storage framework, enabling agents to access both memory and
storage through consistent interfaces.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from ..memory.memory_manager import MemoryManager
from ..memory.memory_types import MemoryEntry, MemoryType, MemoryQuery, MemorySearchResult
from .data_manager import DataManager
from .base_provider import DataReference, StorageResult
from .exceptions import StorageError

logger = logging.getLogger(__name__)


class MemoryStorageAdapter:
    """
    Adapter that makes the memory system accessible through the storage interface.
    
    This allows agents to access memory through the unified storage API,
    providing a consistent interface across all data sources.
    """
    
    def __init__(self, memory_manager: MemoryManager, agent_id: str):
        """
        Initialize the adapter.
        
        Args:
            memory_manager: The memory manager to adapt
            agent_id: ID of the agent using this adapter
        """
        self.memory_manager = memory_manager
        self.agent_id = agent_id
    
    async def store_memory_as_data(self, 
                                   memory_type: Union[MemoryType, str], 
                                   content: str,
                                   metadata: Optional[Dict[str, Any]] = None,
                                   importance: float = 0.5) -> StorageResult:
        """
        Store a memory entry through the storage interface.
        
        Args:
            memory_type: Type of memory to store
            content: Memory content
            metadata: Additional metadata
            importance: Memory importance score
            
        Returns:
            StorageResult with operation outcome
        """
        try:
            if isinstance(memory_type, str):
                memory_type = MemoryType(memory_type)
            
            memory_entry = MemoryEntry(
                id=None,  # Will be auto-generated
                agent_id=self.agent_id,
                memory_type=memory_type,
                content=content,
                metadata=metadata or {},
                importance=importance
            )
            
            # Store in appropriate memory system
            if memory_type == MemoryType.SHORT_TERM:
                success = self.memory_manager.short_term_memory.store(memory_entry)
            else:
                success = await self.memory_manager.store_memory(memory_entry)
            
            if success:
                return StorageResult(
                    success=True,
                    data={"memory_id": memory_entry.id, "memory_type": memory_type.value},
                    metadata={
                        "operation": "store_memory",
                        "memory_type": memory_type.value,
                        "agent_id": self.agent_id
                    },
                    data_reference=DataReference(
                        provider="memory",
                        storage_type="memory",
                        resource_id=memory_entry.id,
                        metadata={"memory_type": memory_type.value, "agent_id": self.agent_id}
                    )
                )
            else:
                return StorageResult(
                    success=False,
                    error="Failed to store memory"
                )
        
        except Exception as e:
            logger.error(f"Memory storage failed: {e}")
            return StorageResult(
                success=False,
                error=f"Memory storage failed: {str(e)}"
            )
    
    async def retrieve_memory_as_data(self, 
                                      memory_id: str,
                                      include_embedding: bool = False) -> StorageResult:
        """
        Retrieve a memory entry through the storage interface.
        
        Args:
            memory_id: ID of memory to retrieve
            include_embedding: Whether to include embedding data
            
        Returns:
            StorageResult with memory data
        """
        try:
            # Try short-term memory first
            memory_entry = self.memory_manager.short_term_memory.get(memory_id)
            
            if not memory_entry and self.memory_manager.long_term_memory:
                # Try long-term memory
                memory_entry = await self.memory_manager.long_term_memory.get_memory(memory_id)
            
            if memory_entry:
                data = {
                    "id": memory_entry.id,
                    "agent_id": memory_entry.agent_id,
                    "memory_type": memory_entry.memory_type.value,
                    "content": memory_entry.content,
                    "metadata": memory_entry.metadata,
                    "created_at": memory_entry.created_at.isoformat(),
                    "accessed_at": memory_entry.accessed_at.isoformat(),
                    "access_count": memory_entry.access_count,
                    "importance": memory_entry.importance
                }
                
                if include_embedding and memory_entry.embedding:
                    data["embedding"] = memory_entry.embedding
                
                return StorageResult(
                    success=True,
                    data=data,
                    metadata={
                        "operation": "retrieve_memory",
                        "memory_type": memory_entry.memory_type.value,
                        "agent_id": self.agent_id
                    }
                )
            else:
                return StorageResult(
                    success=False,
                    error=f"Memory '{memory_id}' not found"
                )
        
        except Exception as e:
            logger.error(f"Memory retrieval failed: {e}")
            return StorageResult(
                success=False,
                error=f"Memory retrieval failed: {str(e)}"
            )
    
    async def search_memory_as_data(self, 
                                    query: str,
                                    memory_types: Optional[List[MemoryType]] = None,
                                    limit: int = 10,
                                    min_similarity: float = 0.7) -> StorageResult:
        """
        Search memory through the storage interface.
        
        Args:
            query: Search query
            memory_types: Types of memory to search
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold
            
        Returns:
            StorageResult with search results
        """
        try:
            memory_query = MemoryQuery(
                query_text=query,
                memory_types=memory_types or list(MemoryType),
                limit=limit,
                min_similarity=min_similarity
            )
            
            results = await self.memory_manager.search_memories(memory_query)
            
            # Convert MemorySearchResult to storage format
            search_data = []
            for result in results:
                search_data.append({
                    "id": result.memory.id,
                    "content": result.memory.content,
                    "memory_type": result.memory.memory_type.value,
                    "similarity": result.similarity,
                    "metadata": result.memory.metadata,
                    "created_at": result.memory.created_at.isoformat(),
                    "importance": result.memory.importance
                })
            
            return StorageResult(
                success=True,
                data=search_data,
                metadata={
                    "operation": "search_memory",
                    "query": query,
                    "result_count": len(search_data),
                    "agent_id": self.agent_id
                }
            )
        
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return StorageResult(
                success=False,
                error=f"Memory search failed: {str(e)}"
            )


class UnifiedDataInterface:
    """
    Unified interface that combines memory and storage access.
    
    Provides a single interface for agents to access both memory
    and external storage systems seamlessly.
    """
    
    def __init__(self, 
                 agent_id: str,
                 memory_manager: Optional[MemoryManager] = None,
                 data_manager: Optional[DataManager] = None):
        """
        Initialize the unified interface.
        
        Args:
            agent_id: ID of the agent using this interface
            memory_manager: Memory manager instance
            data_manager: Data manager instance
        """
        self.agent_id = agent_id
        self.memory_manager = memory_manager
        self.data_manager = data_manager
        
        # Create memory adapter if memory manager is available
        self.memory_adapter = None
        if self.memory_manager:
            self.memory_adapter = MemoryStorageAdapter(self.memory_manager, agent_id)
    
    async def store(self, 
                   location: str, 
                   data: Any, 
                   **kwargs) -> StorageResult:
        """
        Store data in memory or storage.
        
        Args:
            location: Storage location - "memory:type" or "provider:resource"
            data: Data to store
            **kwargs: Additional parameters
            
        Returns:
            StorageResult with operation outcome
        """
        if location.startswith("memory:"):
            # Store in memory system
            if not self.memory_adapter:
                return StorageResult(
                    success=False,
                    error="Memory system not available"
                )
            
            memory_type = location.split(":", 1)[1]
            return await self.memory_adapter.store_memory_as_data(
                memory_type, str(data), kwargs.get("metadata"), kwargs.get("importance", 0.5)
            )
        
        else:
            # Store in external storage
            if not self.data_manager:
                return StorageResult(
                    success=False,
                    error="Storage system not available"
                )
            
            if ":" in location:
                provider, resource = location.split(":", 1)
            else:
                # Use smart storage selection
                return await self.data_manager.smart_store(data, location, **kwargs)
            
            return await self.data_manager.store(provider, resource, data, **kwargs)
    
    async def get(self, 
                  location: str, 
                  **kwargs) -> StorageResult:
        """
        Retrieve data from memory or storage.
        
        Args:
            location: Storage location - "memory:id" or "provider:resource"
            **kwargs: Additional parameters
            
        Returns:
            StorageResult with retrieved data
        """
        if location.startswith("memory:"):
            # Get from memory system
            if not self.memory_adapter:
                return StorageResult(
                    success=False,
                    error="Memory system not available"
                )
            
            memory_id = location.split(":", 1)[1]
            return await self.memory_adapter.retrieve_memory_as_data(
                memory_id, kwargs.get("include_embedding", False)
            )
        
        else:
            # Get from external storage
            if not self.data_manager:
                return StorageResult(
                    success=False,
                    error="Storage system not available"
                )
            
            provider, resource = location.split(":", 1)
            return await self.data_manager.get(provider, resource, **kwargs)
    
    async def search(self, 
                     query: Union[str, List[float]], 
                     locations: Optional[List[str]] = None,
                     **kwargs) -> List[StorageResult]:
        """
        Search across memory and storage systems.
        
        Args:
            query: Search query (text or vector)
            locations: Specific locations to search
            **kwargs: Search parameters
            
        Returns:
            List of StorageResult from different sources
        """
        results = []
        
        # Search memory if requested or no specific locations given
        if not locations or any(loc.startswith("memory") for loc in (locations or [])):
            if self.memory_adapter:
                try:
                    memory_result = await self.memory_adapter.search_memory_as_data(
                        str(query), 
                        kwargs.get("memory_types"),
                        kwargs.get("limit", 10),
                        kwargs.get("min_similarity", 0.7)
                    )
                    if memory_result.success:
                        results.append(memory_result)
                except Exception as e:
                    logger.warning(f"Memory search failed: {e}")
        
        # Search external storage
        if self.data_manager:
            try:
                # Determine which providers to search
                providers = []
                if locations:
                    providers = [loc.split(":")[0] for loc in locations if not loc.startswith("memory")]
                
                storage_results = await self.data_manager.smart_search(
                    query, providers, **kwargs
                )
                results.extend(storage_results)
            except Exception as e:
                logger.warning(f"Storage search failed: {e}")
        
        return results
    
    async def resolve_reference(self, 
                               reference: Union[str, DataReference],
                               **kwargs) -> StorageResult:
        """
        Resolve a data reference to actual data.
        
        Args:
            reference: Reference URI or DataReference object
            **kwargs: Resolution parameters
            
        Returns:
            StorageResult with resolved data
        """
        if isinstance(reference, str):
            if reference.startswith("memory:"):
                return await self.get(reference, **kwargs)
            else:
                # External storage reference
                if self.data_manager:
                    return await self.data_manager.resolve_data_reference(reference, **kwargs)
                else:
                    return StorageResult(
                        success=False,
                        error="Storage system not available"
                    )
        
        elif isinstance(reference, DataReference):
            if self.data_manager:
                return await self.data_manager.resolve_data_reference(reference, **kwargs)
            else:
                return StorageResult(
                    success=False,
                    error="Storage system not available"
                )
        
        else:
            return StorageResult(
                success=False,
                error=f"Invalid reference type: {type(reference)}"
            )