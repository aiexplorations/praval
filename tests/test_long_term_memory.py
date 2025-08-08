"""
Comprehensive tests for Praval LongTermMemory.

This module ensures the long-term memory system with Qdrant is bulletproof and handles
all edge cases correctly. Tests are strict and verify both functionality
and error conditions, including dependency management.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any
import uuid

from praval.memory.long_term_memory import LongTermMemory, QDRANT_AVAILABLE, OPENAI_AVAILABLE
from praval.memory.memory_types import MemoryEntry, MemoryType, MemoryQuery, MemorySearchResult


class TestLongTermMemoryInitialization:
    """Test LongTermMemory initialization with comprehensive coverage."""
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_long_term_memory_default_initialization(self, mock_qdrant_client):
        """Test long-term memory with default parameters."""
        mock_client = Mock()
        mock_qdrant_client.return_value = mock_client
        
        # Mock collection check
        mock_collections = Mock()
        mock_collections.collections = []
        mock_client.get_collections.return_value = mock_collections
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        assert memory.qdrant_url == "http://localhost:6333"
        assert memory.collection_name == "praval_memories"
        assert memory.vector_size == 1536
        assert memory.distance_metric == "cosine"
        
        # Verify Qdrant client initialization
        mock_qdrant_client.assert_called_once_with(url="http://localhost:6333")
        mock_client.create_collection.assert_called_once()
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_long_term_memory_custom_initialization(self, mock_qdrant_client):
        """Test long-term memory with custom parameters."""
        mock_client = Mock()
        mock_qdrant_client.return_value = mock_client
        
        # Mock collection check
        mock_collections = Mock()
        mock_collections.collections = []
        mock_client.get_collections.return_value = mock_collections
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory(
                qdrant_url="http://custom:6334",
                collection_name="custom_memories",
                vector_size=768,
                distance_metric="euclidean"
            )
        
        assert memory.qdrant_url == "http://custom:6334"
        assert memory.collection_name == "custom_memories"
        assert memory.vector_size == 768
        assert memory.distance_metric == "euclidean"
        
        mock_qdrant_client.assert_called_once_with(url="http://custom:6334")
    
    def test_long_term_memory_qdrant_unavailable(self):
        """Test initialization when Qdrant is not available."""
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', False):
            with pytest.raises(ImportError, match="qdrant-client is required for long-term memory"):
                LongTermMemory()
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_long_term_memory_existing_collection(self, mock_qdrant_client):
        """Test initialization with existing collection."""
        mock_client = Mock()
        mock_qdrant_client.return_value = mock_client
        
        # Mock existing collection
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        mock_client.get_collections.return_value = mock_collections
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            LongTermMemory()
        
        # Should not create collection since it exists
        mock_client.create_collection.assert_not_called()
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_long_term_memory_collection_creation_failure(self, mock_qdrant_client):
        """Test handling of collection creation failure."""
        mock_client = Mock()
        mock_qdrant_client.return_value = mock_client
        
        # Mock collection check failure
        mock_client.get_collections.side_effect = Exception("Connection failed")
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            with pytest.raises(Exception, match="Connection failed"):
                LongTermMemory()
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_long_term_memory_distance_metric_mapping(self, mock_qdrant_client):
        """Test distance metric mapping to Qdrant types."""
        mock_client = Mock()
        mock_qdrant_client.return_value = mock_client
        
        # Mock collection check
        mock_collections = Mock()
        mock_collections.collections = []
        mock_client.get_collections.return_value = mock_collections
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            with patch('praval.memory.long_term_memory.models') as mock_models:
                memory = LongTermMemory(distance_metric="dot")
        
        # Verify create_collection was called with correct distance
        mock_client.create_collection.assert_called_once()


class TestLongTermMemoryStorage:
    """Test memory storage functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_client = Mock()
        self.mock_embedding = [0.1, 0.2, 0.3] * 512  # 1536 dimensions
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_store_memory_basic(self, mock_qdrant_client):
        """Test basic memory storage."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        # Mock embedding generation
        with patch.object(memory, '_generate_embedding') as mock_generate:
            mock_generate.return_value = self.mock_embedding
            
            entry = MemoryEntry(
                id="store_test",
                agent_id="test_agent",
                memory_type=MemoryType.SEMANTIC,
                content="Test storage content",
                metadata={"test": True}
            )
            
            result_id = memory.store(entry)
            
            assert result_id == "store_test"
            
            # Verify Qdrant upsert was called
            self.mock_client.upsert.assert_called_once()
            call_args = self.mock_client.upsert.call_args
            
            assert call_args[1]["collection_name"] == "praval_memories"
            points = call_args[1]["points"]
            assert len(points) == 1
            
            point = points[0]
            assert point.id == "store_test"
            assert point.vector == self.mock_embedding
            assert point.payload["agent_id"] == "test_agent"
            assert point.payload["memory_type"] == "semantic"
            assert point.payload["content"] == "Test storage content"
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_store_memory_with_existing_embedding(self, mock_qdrant_client):
        """Test storing memory with pre-existing embedding."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        existing_embedding = [0.5, 0.6, 0.7] * 512
        entry = MemoryEntry(
            id="embedding_test",
            agent_id="test_agent",
            memory_type=MemoryType.SEMANTIC,
            content="Content with embedding",
            metadata={},
            embedding=existing_embedding
        )
        
        # Mock embedding generation to ensure it's not called
        with patch.object(memory, '_generate_embedding') as mock_generate:
            memory.store(entry)
            
            # Should not generate new embedding
            mock_generate.assert_not_called()
            
            call_args = self.mock_client.upsert.call_args
            point = call_args[1]["points"][0]
            assert point.vector == existing_embedding
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_store_memory_qdrant_failure(self, mock_qdrant_client):
        """Test handling of Qdrant storage failure."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        # Mock upsert failure
        self.mock_client.upsert.side_effect = Exception("Storage failed")
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        with patch.object(memory, '_generate_embedding', return_value=self.mock_embedding):
            entry = MemoryEntry(
                id="failure_test",
                agent_id="test_agent",
                memory_type=MemoryType.SEMANTIC,
                content="Failure test",
                metadata={}
            )
            
            with pytest.raises(Exception, match="Storage failed"):
                memory.store(entry)


class TestLongTermMemoryRetrieval:
    """Test memory retrieval functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_client = Mock()
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_retrieve_memory_existing(self, mock_qdrant_client):
        """Test retrieving existing memory."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        # Mock retrieve response
        mock_point = Mock()
        mock_point.id = "retrieve_test"
        mock_point.vector = [0.1, 0.2, 0.3] * 512
        mock_point.payload = {
            "agent_id": "test_agent",
            "memory_type": "semantic",
            "content": "Test content",
            "metadata": {"source": "test"},
            "created_at": "2023-01-01T12:00:00",
            "accessed_at": "2023-01-01T12:00:00",
            "access_count": 0,
            "importance": 0.8
        }
        self.mock_client.retrieve.return_value = [mock_point]
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        with patch.object(memory, '_update_access_info') as mock_update:
            result = memory.retrieve("retrieve_test")
            
            assert result is not None
            assert result.id == "retrieve_test"
            assert result.agent_id == "test_agent"
            assert result.memory_type == MemoryType.SEMANTIC
            assert result.content == "Test content"
            assert result.metadata == {"source": "test"}
            assert result.importance == 0.8
            assert result.access_count == 1  # Should be incremented by mark_accessed()
            
            # Verify Qdrant retrieve call
            self.mock_client.retrieve.assert_called_once_with(
                collection_name="praval_memories",
                ids=["retrieve_test"],
                with_payload=True,
                with_vectors=True
            )
            
            # Verify access info was updated
            mock_update.assert_called_once_with(result)
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_retrieve_memory_nonexistent(self, mock_qdrant_client):
        """Test retrieving non-existent memory."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        # Mock empty response
        self.mock_client.retrieve.return_value = []
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        result = memory.retrieve("nonexistent")
        
        assert result is None
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_retrieve_memory_qdrant_failure(self, mock_qdrant_client):
        """Test handling of Qdrant retrieval failure."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        # Mock retrieve failure
        self.mock_client.retrieve.side_effect = Exception("Retrieval failed")
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        result = memory.retrieve("failure_test")
        
        assert result is None


class TestLongTermMemorySearch:
    """Test memory search functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_client = Mock()
        
        # Mock search response
        self.mock_search_response = []
        for i in range(2):
            mock_scored_point = Mock()
            mock_scored_point.id = f"search_{i}"
            mock_scored_point.score = 0.9 - (i * 0.1)  # Descending scores
            mock_scored_point.payload = {
                "agent_id": "test_agent",
                "memory_type": "semantic",
                "content": f"Search result {i}",
                "metadata": {"index": i},
                "created_at": "2023-01-01T12:00:00",
                "accessed_at": "2023-01-01T12:00:00",
                "access_count": 0,
                "importance": 0.5
            }
            mock_scored_point.vector = [0.1 * (i + 1)] * 1536
            self.mock_search_response.append(mock_scored_point)
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_search_basic_query(self, mock_qdrant_client):
        """Test basic search query."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        self.mock_client.search.return_value = self.mock_search_response
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        query_embedding = [0.5] * 1536
        with patch.object(memory, '_generate_embedding', return_value=query_embedding):
            with patch.object(memory, '_update_access_info') as mock_update:
                query = MemoryQuery(query_text="test search")
                result = memory.search(query)
                
                assert isinstance(result, MemorySearchResult)
                assert len(result.entries) == 2
                assert len(result.scores) == 2
                assert result.total_found == 2
                
                # Scores should match mock response
                assert result.scores[0] == 0.9
                assert result.scores[1] == 0.8
                
                # Verify Qdrant search call
                self.mock_client.search.assert_called_once()
                call_args = self.mock_client.search.call_args
                
                assert call_args[1]["collection_name"] == "praval_memories"
                assert call_args[1]["query_vector"] == query_embedding
                assert call_args[1]["limit"] == 10  # Default limit
                assert call_args[1]["score_threshold"] == 0.7  # Default threshold
                
                # Verify access info updates
                assert mock_update.call_count == 2
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_search_with_agent_filter(self, mock_qdrant_client):
        """Test search with agent ID filter."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        self.mock_client.search.return_value = self.mock_search_response
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        query_embedding = [0.5] * 1536
        with patch.object(memory, '_generate_embedding', return_value=query_embedding):
            with patch.object(memory, '_update_access_info'):
                with patch('praval.memory.long_term_memory.models') as mock_models:
                    query = MemoryQuery(
                        query_text="agent search",
                        agent_id="specific_agent"
                    )
                    memory.search(query)
                    
                    # Verify search was called with filter
                    call_args = self.mock_client.search.call_args
                    assert call_args[1]["query_filter"] is not None
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_search_with_memory_type_filter(self, mock_qdrant_client):
        """Test search with memory type filter."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        self.mock_client.search.return_value = self.mock_search_response
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        query_embedding = [0.5] * 1536
        with patch.object(memory, '_generate_embedding', return_value=query_embedding):
            with patch.object(memory, '_update_access_info'):
                with patch('praval.memory.long_term_memory.models') as mock_models:
                    query = MemoryQuery(
                        query_text="type search",
                        memory_types=[MemoryType.SEMANTIC, MemoryType.EPISODIC]
                    )
                    memory.search(query)
                    
                    # Verify search was called with memory type filter
                    call_args = self.mock_client.search.call_args
                    assert call_args[1]["query_filter"] is not None
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_search_with_temporal_filter(self, mock_qdrant_client):
        """Test search with temporal constraints."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        self.mock_client.search.return_value = self.mock_search_response
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        query_embedding = [0.5] * 1536
        with patch.object(memory, '_generate_embedding', return_value=query_embedding):
            with patch.object(memory, '_update_access_info'):
                with patch('praval.memory.long_term_memory.models') as mock_models:
                    after_time = datetime(2023, 1, 1, 10, 0, 0)
                    before_time = datetime(2023, 1, 2, 14, 0, 0)
                    
                    query = MemoryQuery(
                        query_text="temporal search",
                        temporal_filter={
                            "after": after_time,
                            "before": before_time
                        }
                    )
                    memory.search(query)
                    
                    # Verify search was called with temporal filters
                    call_args = self.mock_client.search.call_args
                    assert call_args[1]["query_filter"] is not None
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_search_no_results(self, mock_qdrant_client):
        """Test search with no matching results."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        # Mock empty search response
        self.mock_client.search.return_value = []
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        query_embedding = [0.5] * 1536
        with patch.object(memory, '_generate_embedding', return_value=query_embedding):
            query = MemoryQuery(query_text="no results")
            result = memory.search(query)
            
            assert len(result.entries) == 0
            assert len(result.scores) == 0
            assert result.total_found == 0
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_search_qdrant_failure(self, mock_qdrant_client):
        """Test handling of Qdrant search failure."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        # Mock search failure
        self.mock_client.search.side_effect = Exception("Search failed")
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        query_embedding = [0.5] * 1536
        with patch.object(memory, '_generate_embedding', return_value=query_embedding):
            query = MemoryQuery(query_text="failure test")
            result = memory.search(query)
            
            # Should return empty result on failure
            assert len(result.entries) == 0
            assert len(result.scores) == 0
            assert result.total_found == 0


class TestLongTermMemoryEmbeddings:
    """Test embedding generation functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_client = Mock()
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    @patch('praval.memory.long_term_memory.openai')
    def test_generate_embedding_with_openai(self, mock_openai, mock_qdrant_client):
        """Test embedding generation with OpenAI."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        # Mock OpenAI response
        mock_embedding_response = Mock()
        mock_embedding_data = Mock()
        mock_embedding_data.embedding = [0.1, 0.2, 0.3] * 512
        mock_embedding_response.data = [mock_embedding_data]
        mock_openai.embeddings.create.return_value = mock_embedding_response
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            with patch('praval.memory.long_term_memory.OPENAI_AVAILABLE', True):
                memory = LongTermMemory()
        
        result = memory._generate_embedding("test text")
        
        assert result == [0.1, 0.2, 0.3] * 512
        mock_openai.embeddings.create.assert_called_once_with(
            model="text-embedding-ada-002",
            input="test text"
        )
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    @patch('praval.memory.long_term_memory.openai')
    def test_generate_embedding_openai_failure_fallback(self, mock_openai, mock_qdrant_client):
        """Test fallback when OpenAI embedding fails."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        # Mock OpenAI failure
        mock_openai.embeddings.create.side_effect = Exception("API error")
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            with patch('praval.memory.long_term_memory.OPENAI_AVAILABLE', True):
                with patch('praval.memory.long_term_memory.np') as mock_np:
                    mock_np.random.random.return_value.tolist.return_value = [0.5] * 1536
                    
                    memory = LongTermMemory()
                    result = memory._generate_embedding("test text")
                    
                    # Should fall back to random embedding
                    assert len(result) == 1536
                    mock_np.random.random.assert_called_once_with(1536)
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_generate_embedding_openai_unavailable(self, mock_qdrant_client):
        """Test embedding generation when OpenAI is not available."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            with patch('praval.memory.long_term_memory.OPENAI_AVAILABLE', False):
                with patch('praval.memory.long_term_memory.np') as mock_np:
                    mock_np.random.random.return_value.tolist.return_value = [0.5] * 1536
                    
                    memory = LongTermMemory()
                    result = memory._generate_embedding("test text")
                    
                    # Should use random embedding
                    assert len(result) == 1536
                    mock_np.random.random.assert_called_once_with(1536)


class TestLongTermMemoryUtilityMethods:
    """Test utility methods of LongTermMemory."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_client = Mock()
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_delete_memory_success(self, mock_qdrant_client):
        """Test successful memory deletion."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        result = memory.delete("delete_test")
        
        assert result is True
        self.mock_client.delete.assert_called_once()
        call_args = self.mock_client.delete.call_args
        assert call_args[1]["collection_name"] == "praval_memories"
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_delete_memory_failure(self, mock_qdrant_client):
        """Test memory deletion failure."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        # Mock delete failure
        self.mock_client.delete.side_effect = Exception("Delete failed")
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        result = memory.delete("delete_test")
        
        assert result is False
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_clear_agent_memories_success(self, mock_qdrant_client):
        """Test successful clearing of agent memories."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        with patch('praval.memory.long_term_memory.models') as mock_models:
            memory.clear_agent_memories("test_agent")
            
            self.mock_client.delete.assert_called_once()
            call_args = self.mock_client.delete.call_args
            assert call_args[1]["collection_name"] == "praval_memories"
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_clear_agent_memories_failure(self, mock_qdrant_client):
        """Test agent memory clearing failure."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        # Mock delete failure
        self.mock_client.delete.side_effect = Exception("Clear failed")
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        with patch('praval.memory.long_term_memory.models'):
            with pytest.raises(Exception, match="Clear failed"):
                memory.clear_agent_memories("test_agent")
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_get_stats_success(self, mock_qdrant_client):
        """Test getting memory statistics."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        # Mock collection info
        mock_collection_info = Mock()
        mock_collection_info.points_count = 42
        mock_collection_info.config.params.vectors.size = 1536
        mock_collection_info.config.params.vectors.distance.name = "Cosine"
        self.mock_client.get_collection.return_value = mock_collection_info
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        stats = memory.get_stats()
        
        assert stats["total_memories"] == 42
        assert stats["vector_size"] == 1536
        assert stats["distance_metric"] == "Cosine"
        assert stats["collection_name"] == "praval_memories"
        assert stats["qdrant_url"] == "http://localhost:6333"
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_get_stats_failure(self, mock_qdrant_client):
        """Test statistics retrieval failure."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        # Mock get_collection failure
        self.mock_client.get_collection.side_effect = Exception("Stats failed")
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        stats = memory.get_stats()
        
        assert stats == {}
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_health_check_healthy(self, mock_qdrant_client):
        """Test health check when system is healthy."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        assert memory.health_check() is True
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_health_check_unhealthy(self, mock_qdrant_client):
        """Test health check when system is unhealthy."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists for init
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        # Mock health check failure
        self.mock_client.get_collections.side_effect = Exception("Health check failed")
        
        assert memory.health_check() is False
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_update_access_info_success(self, mock_qdrant_client):
        """Test successful access info update."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        entry = MemoryEntry(
            id="update_test",
            agent_id="test_agent",
            memory_type=MemoryType.SEMANTIC,
            content="Update test",
            metadata={},
            access_count=3
        )
        
        memory._update_access_info(entry)
        
        self.mock_client.set_payload.assert_called_once()
        call_args = self.mock_client.set_payload.call_args
        
        assert call_args[1]["collection_name"] == "praval_memories"
        assert call_args[1]["points"] == ["update_test"]
        assert "accessed_at" in call_args[1]["payload"]
        assert call_args[1]["payload"]["access_count"] == 3
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_update_access_info_failure(self, mock_qdrant_client):
        """Test access info update failure handling."""
        mock_qdrant_client.return_value = self.mock_client
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        self.mock_client.get_collections.return_value = mock_collections
        
        # Mock set_payload failure
        self.mock_client.set_payload.side_effect = Exception("Update failed")
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        entry = MemoryEntry(
            id="update_fail_test",
            agent_id="test_agent",
            memory_type=MemoryType.SEMANTIC,
            content="Update fail test",
            metadata={},
            access_count=1
        )
        
        # Should not raise exception, just log warning
        memory._update_access_info(entry)


class TestLongTermMemoryIntegration:
    """Test integration scenarios for LongTermMemory."""
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_point_to_memory_entry_conversion(self, mock_qdrant_client):
        """Test conversion from Qdrant point to MemoryEntry."""
        mock_qdrant_client.return_value = Mock()
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        mock_qdrant_client.return_value.get_collections.return_value = mock_collections
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        # Mock Qdrant point
        mock_point = Mock()
        mock_point.id = "conversion_test"
        mock_point.vector = [0.1, 0.2, 0.3] * 512
        mock_point.payload = {
            "agent_id": "conversion_agent",
            "memory_type": "episodic",
            "content": "Conversion test content",
            "metadata": {"test": True, "value": 42},
            "created_at": "2023-06-15T14:30:00",
            "accessed_at": "2023-06-16T10:15:00",
            "access_count": 5,
            "importance": 0.85
        }
        
        result = memory._point_to_memory_entry(mock_point)
        
        assert result.id == "conversion_test"
        assert result.agent_id == "conversion_agent"
        assert result.memory_type == MemoryType.EPISODIC
        assert result.content == "Conversion test content"
        assert result.metadata == {"test": True, "value": 42}
        assert result.embedding == [0.1, 0.2, 0.3] * 512
        assert result.created_at == datetime(2023, 6, 15, 14, 30, 0)
        assert result.accessed_at == datetime(2023, 6, 16, 10, 15, 0)
        assert result.access_count == 5
        assert result.importance == 0.85
    
    @patch('praval.memory.long_term_memory.QdrantClient')
    def test_point_to_memory_entry_without_vector(self, mock_qdrant_client):
        """Test conversion when point doesn't have vector."""
        mock_qdrant_client.return_value = Mock()
        
        # Mock collection exists
        mock_collection = Mock()
        mock_collection.name = "praval_memories"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        mock_qdrant_client.return_value.get_collections.return_value = mock_collections
        
        with patch('praval.memory.long_term_memory.QDRANT_AVAILABLE', True):
            memory = LongTermMemory()
        
        # Mock Qdrant point without vector attribute
        mock_point = Mock()
        mock_point.id = "no_vector_test"
        # Don't set vector attribute
        del mock_point.vector
        mock_point.payload = {
            "agent_id": "test_agent",
            "memory_type": "semantic",
            "content": "No vector test",
            "metadata": {},
            "created_at": "2023-01-01T12:00:00",
            "accessed_at": "2023-01-01T12:00:00",
            "access_count": 0,
            "importance": 0.5
        }
        
        result = memory._point_to_memory_entry(mock_point)
        
        assert result.embedding is None
        assert result.content == "No vector test"