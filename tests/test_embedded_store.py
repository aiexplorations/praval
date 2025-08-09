"""
Comprehensive tests for Praval EmbeddedVectorStore.

This module ensures the embedded vector store is bulletproof and handles
all edge cases correctly. Tests are strict and verify both functionality
and error conditions, including dependency management.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from praval.memory.embedded_store import EmbeddedVectorStore, CHROMADB_AVAILABLE, SENTENCE_TRANSFORMERS_AVAILABLE
from praval.memory.memory_types import MemoryEntry, MemoryType, MemoryQuery, MemorySearchResult


class TestEmbeddedVectorStoreInitialization:
    """Test EmbeddedVectorStore initialization with comprehensive coverage."""
    
    @patch('praval.memory.embedded_store.chromadb')
    @patch('praval.memory.embedded_store.SentenceTransformer')
    def test_embedded_store_default_initialization(self, mock_sentence_transformer, mock_chromadb):
        """Test embedded store with default parameters."""
        # Mock ChromaDB
        mock_client = Mock()
        mock_collection = Mock()
        mock_client.create_collection.return_value = mock_collection
        mock_client.get_collection.side_effect = ValueError("Collection not found")
        mock_chromadb.PersistentClient.return_value = mock_client
        
        # Mock SentenceTransformer
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_sentence_transformer.return_value = mock_model
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                store = EmbeddedVectorStore()
        
        assert store.collection_name == "praval_memories"
        assert store.embedding_model_name == "all-MiniLM-L6-v2"
        assert store.embedding_size == 384
        assert store.storage_path.name == "praval_memory"
        
        # Verify ChromaDB initialization
        mock_chromadb.PersistentClient.assert_called_once()
        mock_client.create_collection.assert_called_once()
    
    @patch('praval.memory.embedded_store.chromadb')
    @patch('praval.memory.embedded_store.SentenceTransformer')
    def test_embedded_store_custom_initialization(self, mock_sentence_transformer, mock_chromadb):
        """Test embedded store with custom parameters."""
        # Setup mocks
        mock_client = Mock()
        mock_collection = Mock()
        mock_client.create_collection.return_value = mock_collection
        mock_client.get_collection.side_effect = ValueError("Collection not found")
        mock_chromadb.PersistentClient.return_value = mock_client
        
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_sentence_transformer.return_value = mock_model
        
        custom_path = tempfile.mkdtemp()
        try:
            with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
                with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                    store = EmbeddedVectorStore(
                        storage_path=custom_path,
                        collection_name="custom_collection",
                        embedding_model="custom-model"
                    )
            
            assert store.collection_name == "custom_collection"
            assert store.embedding_model_name == "custom-model"
            assert store.embedding_size == 768
            assert str(store.storage_path) == custom_path
            
        finally:
            shutil.rmtree(custom_path, ignore_errors=True)
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_embedded_store_existing_collection(self, mock_chromadb):
        """Test initialization with existing collection."""
        mock_client = Mock()
        mock_collection = Mock()
        mock_client.get_collection.return_value = mock_collection  # Collection exists
        mock_chromadb.PersistentClient.return_value = mock_client
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        # Should get existing collection instead of creating new one
        mock_client.get_collection.assert_called_once_with(name="praval_memories")
        mock_client.create_collection.assert_not_called()
    
    def test_embedded_store_chromadb_unavailable(self):
        """Test initialization when ChromaDB is not available."""
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', False):
            with pytest.raises(ImportError, match="ChromaDB is required for embedded vector store"):
                EmbeddedVectorStore()
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_embedded_store_chromadb_init_failure(self, mock_chromadb):
        """Test handling of ChromaDB initialization failure."""
        mock_chromadb.PersistentClient.side_effect = Exception("Connection failed")
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with pytest.raises(Exception, match="Connection failed"):
                EmbeddedVectorStore()
    
    @patch('praval.memory.embedded_store.chromadb')
    @patch('praval.memory.embedded_store.SentenceTransformer')
    def test_embedded_store_sentence_transformer_init_failure(self, mock_sentence_transformer, mock_chromadb):
        """Test handling of SentenceTransformer initialization failure."""
        # Mock ChromaDB success
        mock_client = Mock()
        mock_collection = Mock()
        mock_client.create_collection.return_value = mock_collection
        mock_client.get_collection.side_effect = ValueError("Collection not found")
        mock_chromadb.PersistentClient.return_value = mock_client
        
        # Mock SentenceTransformer failure
        mock_sentence_transformer.side_effect = Exception("Model load failed")
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                store = EmbeddedVectorStore()
        
        # Should fall back gracefully
        assert store.embedding_model is None
        assert store.embedding_size == 384  # Default size
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_embedded_store_sentence_transformer_unavailable(self, mock_chromadb):
        """Test initialization when SentenceTransformers is not available."""
        mock_client = Mock()
        mock_collection = Mock()
        mock_client.create_collection.return_value = mock_collection
        mock_client.get_collection.side_effect = ValueError("Collection not found")
        mock_chromadb.PersistentClient.return_value = mock_client
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        assert store.embedding_model is None
        assert store.embedding_size == 384


class TestEmbeddedVectorStoreStorage:
    """Test memory storage functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_client = Mock()
        self.mock_collection = Mock()
        self.mock_client.create_collection.return_value = self.mock_collection
        self.mock_client.get_collection.side_effect = ValueError("Collection not found")
        
        # Mock embedding model
        self.mock_model = Mock()
        self.mock_model.get_sentence_embedding_dimension.return_value = 384
        self.mock_embedding = [0.1, 0.2, 0.3] * 128  # 384 dimensions
        self.mock_model.encode.return_value = self.mock_embedding
    
    @patch('praval.memory.embedded_store.chromadb')
    @patch('praval.memory.embedded_store.SentenceTransformer')
    def test_store_memory_basic(self, mock_sentence_transformer, mock_chromadb):
        """Test basic memory storage."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        mock_sentence_transformer.return_value = self.mock_model
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                store = EmbeddedVectorStore()
        
        entry = MemoryEntry(
            id="store_test",
            agent_id="test_agent",
            memory_type=MemoryType.SEMANTIC,
            content="Test storage content",
            metadata={"test": True, "priority": "high"}
        )
        
        result_id = store.store(entry)
        
        assert result_id == "store_test"
        
        # Verify ChromaDB upsert was called correctly
        self.mock_collection.upsert.assert_called_once()
        call_args = self.mock_collection.upsert.call_args
        
        assert call_args[1]["ids"] == ["store_test"]
        assert call_args[1]["documents"] == ["Test storage content"]
        assert len(call_args[1]["embeddings"][0]) == 384
        
        # Verify metadata preparation
        metadata = call_args[1]["metadatas"][0]
        assert metadata["agent_id"] == "test_agent"
        assert metadata["memory_type"] == "semantic"
        assert metadata["meta_test"] == True
        assert metadata["meta_priority"] == "high"
    
    @patch('praval.memory.embedded_store.chromadb')
    @patch('praval.memory.embedded_store.SentenceTransformer')
    def test_store_memory_with_existing_embedding(self, mock_sentence_transformer, mock_chromadb):
        """Test storing memory with pre-existing embedding."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        mock_sentence_transformer.return_value = self.mock_model
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                store = EmbeddedVectorStore()
        
        existing_embedding = [0.5, 0.6, 0.7] * 128
        entry = MemoryEntry(
            id="embedding_test",
            agent_id="test_agent",
            memory_type=MemoryType.SEMANTIC,
            content="Content with embedding",
            metadata={},
            embedding=existing_embedding
        )
        
        store.store(entry)
        
        # Should use existing embedding, not generate new one
        self.mock_model.encode.assert_not_called()
        
        call_args = self.mock_collection.upsert.call_args
        assert call_args[1]["embeddings"][0] == existing_embedding
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_store_memory_complex_metadata(self, mock_chromadb):
        """Test storing memory with complex metadata."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        entry = MemoryEntry(
            id="complex_metadata",
            agent_id="test_agent",
            memory_type=MemoryType.SEMANTIC,
            content="Complex metadata test",
            metadata={
                "string_field": "text",
                "int_field": 42,
                "float_field": 3.14,
                "bool_field": True,
                "list_field": [1, 2, 3],  # Should be converted to string
                "dict_field": {"nested": "value"}  # Should be converted to string
            }
        )
        
        store.store(entry)
        
        call_args = self.mock_collection.upsert.call_args
        metadata = call_args[1]["metadatas"][0]
        
        # Simple types should be preserved
        assert metadata["meta_string_field"] == "text"
        assert metadata["meta_int_field"] == 42
        assert metadata["meta_float_field"] == 3.14
        assert metadata["meta_bool_field"] == True
        
        # Complex types should be converted to strings
        assert metadata["meta_list_field"] == "[1, 2, 3]"
        assert metadata["meta_dict_field"] == "{'nested': 'value'}"
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_store_memory_chromadb_failure(self, mock_chromadb):
        """Test handling of ChromaDB storage failure."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        self.mock_collection.upsert.side_effect = Exception("Storage failed")
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        entry = MemoryEntry(
            id="failure_test",
            agent_id="test_agent",
            memory_type=MemoryType.SEMANTIC,
            content="Failure test",
            metadata={}
        )
        
        with pytest.raises(Exception, match="Storage failed"):
            store.store(entry)


class TestEmbeddedVectorStoreRetrieval:
    """Test memory retrieval functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_client = Mock()
        self.mock_collection = Mock()
        self.mock_client.create_collection.return_value = self.mock_collection
        self.mock_client.get_collection.side_effect = ValueError("Collection not found")
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_retrieve_memory_existing(self, mock_chromadb):
        """Test retrieving existing memory."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        
        # Mock ChromaDB response
        mock_response = {
            "ids": [["retrieve_test"]],
            "metadatas": [[{
                "agent_id": "test_agent",
                "memory_type": "semantic",
                "created_at": "2023-01-01T12:00:00",
                "importance": 0.8,
                "access_count": 2,
                "meta_source": "test"
            }]],
            "documents": [["Test content"]],
            "embeddings": [[[0.1, 0.2, 0.3] * 128]]
        }
        self.mock_collection.get.return_value = mock_response
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        result = store.retrieve("retrieve_test")
        
        assert result is not None
        assert result.id == "retrieve_test"
        assert result.agent_id == "test_agent"
        assert result.memory_type == MemoryType.SEMANTIC
        assert result.content == "Test content"
        assert result.importance == 0.8
        assert result.access_count == 2
        assert result.metadata == {"source": "test"}
        
        # Verify ChromaDB call
        self.mock_collection.get.assert_called_once_with(
            ids=["retrieve_test"],
            include=["metadatas", "documents", "embeddings"]
        )
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_retrieve_memory_nonexistent(self, mock_chromadb):
        """Test retrieving non-existent memory."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        
        # Mock empty response
        mock_response = {"ids": [], "metadatas": [], "documents": [], "embeddings": []}
        self.mock_collection.get.return_value = mock_response
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        result = store.retrieve("nonexistent")
        
        assert result is None
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_retrieve_memory_chromadb_failure(self, mock_chromadb):
        """Test handling of ChromaDB retrieval failure."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        self.mock_collection.get.side_effect = Exception("Retrieval failed")
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        result = store.retrieve("failure_test")
        
        assert result is None


class TestEmbeddedVectorStoreSearch:
    """Test memory search functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_client = Mock()
        self.mock_collection = Mock()
        self.mock_client.create_collection.return_value = self.mock_collection
        self.mock_client.get_collection.side_effect = ValueError("Collection not found")
        
        # Mock successful search response
        self.mock_search_response = {
            "ids": [["search_1", "search_2"]],
            "metadatas": [[
                {
                    "agent_id": "test_agent",
                    "memory_type": "semantic",
                    "created_at": "2023-01-01T12:00:00",
                    "importance": 0.8,
                    "access_count": 1
                },
                {
                    "agent_id": "test_agent",
                    "memory_type": "semantic",
                    "created_at": "2023-01-02T12:00:00",
                    "importance": 0.6,
                    "access_count": 0
                }
            ]],
            "documents": [["First result", "Second result"]],
            "distances": [[0.1, 0.3]],  # ChromaDB returns distances (lower = more similar)
            "embeddings": [[[0.1] * 384, [0.2] * 384]]
        }
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_search_basic_query(self, mock_chromadb):
        """Test basic search query."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        self.mock_collection.query.return_value = self.mock_search_response
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        query = MemoryQuery(query_text="test search")
        result = store.search(query)
        
        assert isinstance(result, MemorySearchResult)
        assert len(result.entries) == 2
        assert len(result.scores) == 2
        assert result.total_found == 2
        
        # Scores should be converted from distances (1 - distance)
        assert result.scores[0] == 0.9  # 1 - 0.1
        assert result.scores[1] == 0.7  # 1 - 0.3
        
        # Verify ChromaDB query call
        self.mock_collection.query.assert_called_once()
        call_args = self.mock_collection.query.call_args
        assert call_args[1]["n_results"] == 10  # Default limit
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_search_with_agent_filter(self, mock_chromadb):
        """Test search with agent ID filter."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        self.mock_collection.query.return_value = self.mock_search_response
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        query = MemoryQuery(
            query_text="agent search",
            agent_id="specific_agent"
        )
        store.search(query)
        
        # Verify where clause includes agent filter
        call_args = self.mock_collection.query.call_args
        where_clause = call_args[1]["where"]
        assert where_clause["agent_id"] == "specific_agent"
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_search_with_memory_type_filter_single(self, mock_chromadb):
        """Test search with single memory type filter."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        self.mock_collection.query.return_value = self.mock_search_response
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        query = MemoryQuery(
            query_text="type search",
            memory_types=[MemoryType.SEMANTIC]
        )
        store.search(query)
        
        call_args = self.mock_collection.query.call_args
        where_clause = call_args[1]["where"]
        assert where_clause["memory_type"] == "semantic"
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_search_with_memory_type_filter_multiple(self, mock_chromadb):
        """Test search with multiple memory type filters."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        self.mock_collection.query.return_value = self.mock_search_response
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        query = MemoryQuery(
            query_text="multi-type search",
            memory_types=[MemoryType.SEMANTIC, MemoryType.EPISODIC]
        )
        store.search(query)
        
        call_args = self.mock_collection.query.call_args
        where_clause = call_args[1]["where"]
        assert where_clause["memory_type"] == {"$in": ["semantic", "episodic"]}
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_search_with_temporal_filter(self, mock_chromadb):
        """Test search with temporal constraints."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        self.mock_collection.query.return_value = self.mock_search_response
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        after_time = datetime(2023, 1, 1, 10, 0, 0)
        before_time = datetime(2023, 1, 2, 14, 0, 0)
        
        query = MemoryQuery(
            query_text="temporal search",
            temporal_filter={
                "after": after_time,
                "before": before_time
            }
        )
        store.search(query)
        
        call_args = self.mock_collection.query.call_args
        where_clause = call_args[1]["where"]
        
        expected_created_at = {
            "$gte": "2023-01-01T10:00:00",
            "$lte": "2023-01-02T14:00:00"
        }
        assert where_clause["created_at"] == expected_created_at
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_search_similarity_threshold(self, mock_chromadb):
        """Test search with similarity threshold filtering."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        
        # Mock response with one result below threshold
        response_with_low_similarity = {
            "ids": [["high_sim", "low_sim"]],
            "metadatas": [[
                {"agent_id": "test", "memory_type": "semantic", "created_at": "2023-01-01T12:00:00"},
                {"agent_id": "test", "memory_type": "semantic", "created_at": "2023-01-01T12:00:00"}
            ]],
            "documents": [["High similarity result", "Low similarity result"]],
            "distances": [[0.1, 0.6]],  # Second result has low similarity (0.4 after conversion)
            "embeddings": [[[0.1] * 384, [0.2] * 384]]
        }
        self.mock_collection.query.return_value = response_with_low_similarity
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        query = MemoryQuery(
            query_text="threshold test",
            similarity_threshold=0.5  # Should filter out second result (0.4 < 0.5)
        )
        result = store.search(query)
        
        # Should only return the high similarity result
        assert len(result.entries) == 1
        assert result.entries[0].content == "High similarity result"
        assert result.scores[0] == 0.9  # 1 - 0.1
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_search_no_results(self, mock_chromadb):
        """Test search with no matching results."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        
        empty_response = {
            "ids": [[]],
            "metadatas": [[]],
            "documents": [[]],
            "distances": [[]],
            "embeddings": [[]]
        }
        self.mock_collection.query.return_value = empty_response
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        query = MemoryQuery(query_text="no results")
        result = store.search(query)
        
        assert len(result.entries) == 0
        assert len(result.scores) == 0
        assert result.total_found == 0
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_search_chromadb_failure(self, mock_chromadb):
        """Test handling of ChromaDB search failure."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        self.mock_collection.query.side_effect = Exception("Search failed")
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        query = MemoryQuery(query_text="failure test")
        result = store.search(query)
        
        # Should return empty result on failure
        assert len(result.entries) == 0
        assert len(result.scores) == 0
        assert result.total_found == 0


class TestEmbeddedVectorStoreEmbeddings:
    """Test embedding generation functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_client = Mock()
        self.mock_collection = Mock()
        self.mock_client.create_collection.return_value = self.mock_collection
        self.mock_client.get_collection.side_effect = ValueError("Collection not found")
    
    @patch('praval.memory.embedded_store.chromadb')
    @patch('praval.memory.embedded_store.SentenceTransformer')
    def test_generate_embedding_with_model(self, mock_sentence_transformer, mock_chromadb):
        """Test embedding generation with SentenceTransformer model."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        
        # Mock SentenceTransformer
        mock_model = Mock()
        mock_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        mock_model.encode.return_value = mock_embedding
        mock_model.get_sentence_embedding_dimension.return_value = 5
        mock_sentence_transformer.return_value = mock_model
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                store = EmbeddedVectorStore()
        
        result = store._generate_embedding("test text")
        
        assert result == mock_embedding
        mock_model.encode.assert_called_once_with("test text", convert_to_tensor=False)
    
    @patch('praval.memory.embedded_store.chromadb')
    @patch('praval.memory.embedded_store.SentenceTransformer')
    def test_generate_embedding_model_failure_fallback(self, mock_sentence_transformer, mock_chromadb):
        """Test fallback when SentenceTransformer model fails."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        
        # Mock SentenceTransformer with failure
        mock_model = Mock()
        mock_model.encode.side_effect = Exception("Model failed")
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_sentence_transformer.return_value = mock_model
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                store = EmbeddedVectorStore()
        
        result = store._generate_embedding("test text")
        
        # Should fall back to hash-based embedding
        assert len(result) == 384
        assert all(isinstance(x, float) for x in result)
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_generate_embedding_fallback_method(self, mock_chromadb):
        """Test fallback embedding generation method."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        result = store._generate_embedding("test text")
        
        # Should generate hash-based embedding
        assert len(result) == 384
        assert all(-1.0 <= x <= 1.0 for x in result)  # Values should be normalized
        
        # Same text should produce same embedding
        result2 = store._generate_embedding("test text")
        assert result == result2
        
        # Different text should produce different embedding
        result3 = store._generate_embedding("different text")
        assert result != result3
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_generate_embedding_empty_text(self, mock_chromadb):
        """Test embedding generation for empty text."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        result = store._generate_embedding("")
        
        # Should return zero vector
        assert len(result) == 384
        assert all(x == 0.0 for x in result)


class TestEmbeddedVectorStoreUtilityMethods:
    """Test utility methods of EmbeddedVectorStore."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_client = Mock()
        self.mock_collection = Mock()
        self.mock_client.create_collection.return_value = self.mock_collection
        self.mock_client.get_collection.side_effect = ValueError("Collection not found")
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_delete_memory_success(self, mock_chromadb):
        """Test successful memory deletion."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        result = store.delete("delete_test")
        
        assert result is True
        self.mock_collection.delete.assert_called_once_with(ids=["delete_test"])
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_delete_memory_failure(self, mock_chromadb):
        """Test memory deletion failure."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        self.mock_collection.delete.side_effect = Exception("Delete failed")
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        result = store.delete("delete_test")
        
        assert result is False
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_clear_agent_memories_success(self, mock_chromadb):
        """Test successful clearing of agent memories."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        store.clear_agent_memories("test_agent")
        
        self.mock_collection.delete.assert_called_once_with(where={"agent_id": "test_agent"})
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_clear_agent_memories_failure(self, mock_chromadb):
        """Test agent memory clearing failure."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        self.mock_collection.delete.side_effect = Exception("Clear failed")
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        with pytest.raises(Exception, match="Clear failed"):
            store.clear_agent_memories("test_agent")
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_get_stats_success(self, mock_chromadb):
        """Test getting storage statistics."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        self.mock_collection.count.return_value = 42
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        stats = store.get_stats()
        
        assert stats["backend"] == "chromadb"
        assert stats["total_memories"] == 42
        assert "storage_path" in stats
        assert stats["collection_name"] == "praval_memories"
        assert stats["embedding_model"] == "all-MiniLM-L6-v2"
        assert stats["embedding_size"] == 384
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_get_stats_failure(self, mock_chromadb):
        """Test statistics retrieval failure."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        self.mock_collection.count.side_effect = Exception("Stats failed")
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        stats = store.get_stats()
        
        assert stats["backend"] == "chromadb"
        assert "error" in stats
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_health_check_healthy(self, mock_chromadb):
        """Test health check when system is healthy."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        self.mock_collection.count.return_value = 10
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        assert store.health_check() is True
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_health_check_unhealthy(self, mock_chromadb):
        """Test health check when system is unhealthy."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        self.mock_collection.count.side_effect = Exception("Health check failed")
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        assert store.health_check() is False


class TestEmbeddedVectorStoreKnowledgeIndexing:
    """Test knowledge base file indexing functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_client = Mock()
        self.mock_collection = Mock()
        self.mock_client.create_collection.return_value = self.mock_collection
        self.mock_client.get_collection.side_effect = ValueError("Collection not found")
        
        # Create temporary directory with test files
        self.test_dir = Path(tempfile.mkdtemp())
        self.knowledge_dir = self.test_dir / "knowledge"
        self.knowledge_dir.mkdir()
        
        # Create test files
        (self.knowledge_dir / "test.txt").write_text("Text file content")
        (self.knowledge_dir / "readme.md").write_text("# Markdown content\nSome documentation")
        (self.knowledge_dir / "config.json").write_text('{"key": "value"}')
        (self.knowledge_dir / "script.py").write_text('print("Hello, world!")')
        (self.knowledge_dir / "unsupported.xyz").write_text("Unsupported format")
        
        # Create subdirectory with more files
        subdir = self.knowledge_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("Nested file content")
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_index_knowledge_files_success(self, mock_chromadb):
        """Test successful knowledge file indexing."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        indexed_count = store.index_knowledge_files(self.knowledge_dir, "knowledge_agent")
        
        # Should index 5 supported files (txt, md, json, py, nested.txt)
        assert indexed_count == 5
        
        # Verify store was called for each file
        assert self.mock_collection.upsert.call_count == 5
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_index_knowledge_files_nonexistent_path(self, mock_chromadb):
        """Test indexing with non-existent path."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        with pytest.raises(ValueError, match="Knowledge base path does not exist"):
            store.index_knowledge_files("/nonexistent/path", "agent")
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_index_knowledge_files_file_as_path(self, mock_chromadb):
        """Test indexing with file path instead of directory."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        # Point to a file instead of directory
        file_path = self.knowledge_dir / "test.txt"
        indexed_count = store.index_knowledge_files(file_path, "agent")
        
        # Should index 0 files since it's not a directory
        assert indexed_count == 0
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_index_knowledge_files_with_read_errors(self, mock_chromadb):
        """Test indexing when some files cannot be read."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        
        # Create file with restricted permissions (simulate read error)
        restricted_file = self.knowledge_dir / "restricted.txt"
        restricted_file.write_text("Restricted content")
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        # Mock read_text to fail for specific file
        original_read_text = Path.read_text
        def mock_read_text(self, *args, **kwargs):
            if self.name == "restricted.txt":
                raise PermissionError("Cannot read file")
            return original_read_text(self, *args, **kwargs)
        
        with patch.object(Path, 'read_text', mock_read_text):
            indexed_count = store.index_knowledge_files(self.knowledge_dir, "agent")
        
        # Should index all files except the restricted one
        assert indexed_count == 5  # All supported files except restricted


class TestEmbeddedVectorStoreIntegration:
    """Test integration scenarios for EmbeddedVectorStore."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_client = Mock()
        self.mock_collection = Mock()
        self.mock_client.create_collection.return_value = self.mock_collection
        self.mock_client.get_collection.side_effect = ValueError("Collection not found")
    
    @patch('praval.memory.embedded_store.chromadb')
    def test_full_memory_lifecycle_without_dependencies(self, mock_chromadb):
        """Test complete memory lifecycle without external dependencies."""
        mock_chromadb.PersistentClient.return_value = self.mock_client
        
        # Mock successful operations
        self.mock_collection.count.return_value = 1
        
        # Mock retrieve response
        retrieve_response = {
            "ids": [["lifecycle_test"]],
            "metadatas": [[{
                "agent_id": "lifecycle_agent",
                "memory_type": "semantic",
                "created_at": "2023-01-01T12:00:00",
                "importance": 0.8,
                "access_count": 0
            }]],
            "documents": [["Lifecycle test content"]],
            "embeddings": [[[0.1] * 384]]
        }
        self.mock_collection.get.return_value = retrieve_response
        
        # Mock search response
        search_response = {
            "ids": [["lifecycle_test"]],
            "metadatas": [[{
                "agent_id": "lifecycle_agent",
                "memory_type": "semantic",
                "created_at": "2023-01-01T12:00:00",
                "importance": 0.8,
                "access_count": 0
            }]],
            "documents": [["Lifecycle test content"]],
            "distances": [[0.2]],
            "embeddings": [[[0.1] * 384]]
        }
        self.mock_collection.query.return_value = search_response
        
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', True):
            with patch('praval.memory.embedded_store.SENTENCE_TRANSFORMERS_AVAILABLE', False):
                store = EmbeddedVectorStore()
        
        # Test complete lifecycle
        entry = MemoryEntry(
            id="lifecycle_test",
            agent_id="lifecycle_agent",
            memory_type=MemoryType.SEMANTIC,
            content="Lifecycle test content",
            metadata={"test": True}
        )
        
        # Store
        store_result = store.store(entry)
        assert store_result == "lifecycle_test"
        
        # Retrieve
        retrieved = store.retrieve("lifecycle_test")
        assert retrieved is not None
        assert retrieved.content == "Lifecycle test content"
        
        # Search
        query = MemoryQuery(query_text="lifecycle test")
        search_results = store.search(query)
        assert len(search_results.entries) == 1
        
        # Get stats
        stats = store.get_stats()
        assert stats["total_memories"] == 1
        
        # Health check
        assert store.health_check() is True
        
        # Delete
        delete_result = store.delete("lifecycle_test")
        assert delete_result is True
    
    def test_fallback_embedding_consistency(self):
        """Test that fallback embedding method is consistent and deterministic."""
        with patch('praval.memory.embedded_store.CHROMADB_AVAILABLE', False):
            pass  # Can't test without mocking since ChromaDB is required
        
        # Test fallback embedding directly
        from praval.memory.embedded_store import EmbeddedVectorStore
        
        # Create a mock store instance to test the fallback method
        store = Mock()
        store.embedding_size = 384
        
        # Bind the method to our mock
        fallback_method = EmbeddedVectorStore._fallback_embedding.__get__(store)
        
        # Test consistency
        text1 = "consistent test text"
        embedding1 = fallback_method(text1)
        embedding2 = fallback_method(text1)
        assert embedding1 == embedding2
        
        # Test different inputs produce different outputs
        text2 = "different test text"
        embedding3 = fallback_method(text2)
        assert embedding1 != embedding3
        
        # Test properties
        assert len(embedding1) == 384
        assert all(-1.0 <= x <= 1.0 for x in embedding1)
        assert not all(x == 0.0 for x in embedding1)  # Should not be all zeros