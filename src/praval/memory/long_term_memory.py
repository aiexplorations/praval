"""
Long-term vector memory using Qdrant for Praval agents

This provides persistent, vector-based storage for:
- Semantic knowledge and concepts
- Long-term conversation history
- Learned patterns and insights
- Cross-session memory persistence
"""

from typing import List, Optional, Dict, Any
import logging
import numpy as np
from datetime import datetime

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.models import Distance, VectorParams, PointStruct
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None
    models = None

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

from .memory_types import MemoryEntry, MemoryType, MemoryQuery, MemorySearchResult


logger = logging.getLogger(__name__)


class LongTermMemory:
    """
    Qdrant-based long-term memory for persistent vector storage
    
    Features:
    - Vector similarity search
    - Persistent storage across sessions
    - Scalable to millions of memories
    - Semantic search capabilities
    - Memory importance scoring
    """
    
    def __init__(self,
                 qdrant_url: str = "http://localhost:6333",
                 collection_name: str = "praval_memories",
                 vector_size: int = 1536,  # OpenAI embedding size
                 distance_metric: str = "cosine"):
        """
        Initialize long-term memory
        
        Args:
            qdrant_url: URL to Qdrant instance
            collection_name: Name of the collection to use
            vector_size: Size of embedding vectors
            distance_metric: Distance metric for similarity search
        """
        if not QDRANT_AVAILABLE:
            raise ImportError("qdrant-client is required for long-term memory. Install with: pip install qdrant-client")
        
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.distance_metric = distance_metric
        
        # Initialize Qdrant client
        self.client = QdrantClient(url=qdrant_url)
        
        # Initialize collection
        self._ensure_collection_exists()
        
        logger.info(f"Long-term memory initialized with Qdrant at {qdrant_url}")
    
    def _ensure_collection_exists(self):
        """Ensure the Qdrant collection exists"""
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.collection_name not in collection_names:
                # Create collection
                distance_map = {
                    "cosine": Distance.COSINE,
                    "euclidean": Distance.EUCLID,
                    "dot": Distance.DOT
                }
                
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=distance_map.get(self.distance_metric, Distance.COSINE)
                    )
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
            else:
                logger.info(f"Using existing Qdrant collection: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant collection: {e}")
            raise
    
    def store(self, memory: MemoryEntry) -> str:
        """
        Store a memory entry with vector embedding
        
        Args:
            memory: The memory entry to store
            
        Returns:
            The ID of the stored memory
        """
        try:
            # Generate embedding if not provided
            if memory.embedding is None:
                memory.embedding = self._generate_embedding(memory.content)
            
            # Create point for Qdrant
            point = PointStruct(
                id=memory.id,
                vector=memory.embedding,
                payload={
                    'agent_id': memory.agent_id,
                    'memory_type': memory.memory_type.value,
                    'content': memory.content,
                    'metadata': memory.metadata,
                    'created_at': memory.created_at.isoformat(),
                    'accessed_at': memory.accessed_at.isoformat(),
                    'access_count': memory.access_count,
                    'importance': memory.importance
                }
            )
            
            # Store in Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.debug(f"Stored memory {memory.id} in long-term memory")
            return memory.id
            
        except Exception as e:
            logger.error(f"Failed to store memory {memory.id}: {e}")
            raise
    
    def retrieve(self, memory_id: str) -> Optional[MemoryEntry]:
        """
        Retrieve a specific memory by ID
        
        Args:
            memory_id: The ID of the memory to retrieve
            
        Returns:
            The memory entry if found, None otherwise
        """
        try:
            # Retrieve from Qdrant
            result = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[memory_id],
                with_payload=True,
                with_vectors=True
            )
            
            if not result:
                return None
            
            point = result[0]
            memory = self._point_to_memory_entry(point)
            
            # Update access information
            memory.mark_accessed()
            self._update_access_info(memory)
            
            return memory
            
        except Exception as e:
            logger.error(f"Failed to retrieve memory {memory_id}: {e}")
            return None
    
    def search(self, query: MemoryQuery) -> MemorySearchResult:
        """
        Search memories using vector similarity
        
        Args:
            query: The search query
            
        Returns:
            Search results with matching memories
        """
        try:
            # Generate query embedding
            query_embedding = self._generate_embedding(query.query_text)
            
            # Build filter conditions
            filters = []
            
            if query.agent_id:
                filters.append(models.FieldCondition(
                    key="agent_id",
                    match=models.MatchValue(value=query.agent_id)
                ))
            
            if query.memory_types:
                memory_type_values = [mt.value for mt in query.memory_types]
                filters.append(models.FieldCondition(
                    key="memory_type",
                    match=models.MatchAny(any=memory_type_values)
                ))
            
            # Temporal filtering
            if query.temporal_filter:
                if 'after' in query.temporal_filter:
                    filters.append(models.FieldCondition(
                        key="created_at",
                        range=models.Range(gte=query.temporal_filter['after'].isoformat())
                    ))
                if 'before' in query.temporal_filter:
                    filters.append(models.FieldCondition(
                        key="created_at",
                        range=models.Range(lte=query.temporal_filter['before'].isoformat())
                    ))
            
            # Combine filters
            filter_condition = None
            if filters:
                filter_condition = models.Filter(must=filters)
            
            # Search in Qdrant
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=filter_condition,
                limit=query.limit,
                score_threshold=query.similarity_threshold,
                with_payload=True,
                with_vectors=True
            )
            
            # Convert results
            entries = []
            scores = []
            
            for scored_point in search_result:
                memory = self._point_to_memory_entry(scored_point)
                memory.mark_accessed()
                
                entries.append(memory)
                scores.append(scored_point.score)
            
            # Update access information for retrieved memories
            for memory in entries:
                self._update_access_info(memory)
            
            return MemorySearchResult(
                entries=entries,
                scores=scores,
                query=query,
                total_found=len(entries)
            )
            
        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return MemorySearchResult(entries=[], scores=[], query=query, total_found=0)
    
    def delete(self, memory_id: str) -> bool:
        """
        Delete a memory entry
        
        Args:
            memory_id: The ID of the memory to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(points=[memory_id])
            )
            logger.debug(f"Deleted memory {memory_id} from long-term memory")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id}: {e}")
            return False
    
    def clear_agent_memories(self, agent_id: str):
        """Clear all memories for a specific agent"""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[models.FieldCondition(
                            key="agent_id",
                            match=models.MatchValue(value=agent_id)
                        )]
                    )
                )
            )
            logger.info(f"Cleared all memories for agent {agent_id}")
            
        except Exception as e:
            logger.error(f"Failed to clear memories for agent {agent_id}: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            
            return {
                'total_memories': collection_info.points_count,
                'vector_size': collection_info.config.params.vectors.size,
                'distance_metric': collection_info.config.params.vectors.distance.name,
                'collection_name': self.collection_name,
                'qdrant_url': self.qdrant_url
            }
            
        except Exception as e:
            logger.error(f"Failed to get memory statistics: {e}")
            return {}
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI"""
        if not OPENAI_AVAILABLE:
            # Fallback to random embedding (for testing)
            logger.warning("OpenAI not available, using random embedding")
            return np.random.random(self.vector_size).tolist()
        
        try:
            response = openai.embeddings.create(
                model="text-embedding-ada-002",
                input=text
            )
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            # Fallback to random embedding
            return np.random.random(self.vector_size).tolist()
    
    def _point_to_memory_entry(self, point) -> MemoryEntry:
        """Convert Qdrant point to MemoryEntry"""
        payload = point.payload
        
        return MemoryEntry(
            id=point.id,
            agent_id=payload['agent_id'],
            memory_type=MemoryType(payload['memory_type']),
            content=payload['content'],
            metadata=payload['metadata'],
            embedding=point.vector if hasattr(point, 'vector') else None,
            created_at=datetime.fromisoformat(payload['created_at']),
            accessed_at=datetime.fromisoformat(payload['accessed_at']),
            access_count=payload.get('access_count', 0),
            importance=payload.get('importance', 0.5)
        )
    
    def _update_access_info(self, memory: MemoryEntry):
        """Update access information in Qdrant"""
        try:
            self.client.set_payload(
                collection_name=self.collection_name,
                payload={
                    'accessed_at': memory.accessed_at.isoformat(),
                    'access_count': memory.access_count
                },
                points=[memory.id]
            )
        except Exception as e:
            logger.warning(f"Failed to update access info for memory {memory.id}: {e}")
    
    def health_check(self) -> bool:
        """Check if Qdrant connection is healthy"""
        try:
            self.client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False