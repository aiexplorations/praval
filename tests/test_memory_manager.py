"""
Comprehensive tests for Praval MemoryManager.

This module ensures the MemoryManager coordination system is bulletproof and handles
all edge cases correctly. Tests are strict and verify both functionality
and error conditions.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from praval.memory.memory_manager import MemoryManager
from praval.memory.memory_types import MemoryEntry, MemoryType, MemoryQuery, MemorySearchResult


class TestMemoryManagerInitialization:
    """Test MemoryManager initialization with comprehensive coverage."""
    
    def test_memory_manager_basic_initialization(self):
        """Test basic memory manager initialization with defaults."""
        manager = MemoryManager(agent_id="test_agent")

        assert manager.agent_id == "test_agent"
        # Backend depends on available dependencies (chromadb > qdrant > memory)
        assert manager.backend in ("memory", "qdrant", "chromadb")
        assert manager.qdrant_url == "http://localhost:6333"
        assert manager.collection_name == "praval_memories"
        assert manager.storage_path is None
        assert manager.knowledge_base_path is None
    
    def test_memory_manager_custom_parameters(self):
        """Test memory manager initialization with custom parameters."""
        # Test with memory backend which doesn't require dependencies
        manager = MemoryManager(
            agent_id="custom_agent",
            backend="memory",
            qdrant_url="http://custom:6333",
            storage_path="/tmp/custom_storage",
            collection_name="custom_collection",
            short_term_max_entries=500,
            short_term_retention_hours=12,
            knowledge_base_path="/path/to/kb"
        )
        
        assert manager.agent_id == "custom_agent"
        assert manager.backend == "memory"
        assert manager.qdrant_url == "http://custom:6333"
        assert manager.storage_path == "/tmp/custom_storage"
        assert manager.collection_name == "custom_collection"
        assert manager.knowledge_base_path == "/path/to/kb"
    
    def test_memory_manager_qdrant_backend_unavailable(self):
        """Test that explicit qdrant backend raises when dependencies unavailable."""
        # When qdrant backend is explicitly requested but dependencies aren't available,
        # it should raise an exception rather than fall back
        with pytest.raises(ImportError, match="qdrant-client is required"):
            MemoryManager(
                agent_id="qdrant_test_agent",
                backend="qdrant"
            )
    
    @patch.dict(os.environ, {'PRAVAL_KNOWLEDGE_BASE': '/env/knowledge/base'})
    def test_memory_manager_knowledge_base_from_env(self):
        """Test that knowledge base path is auto-detected from environment."""
        manager = MemoryManager(
            agent_id="env_agent",
            knowledge_base_path=None
        )
        
        assert manager.knowledge_base_path == "/env/knowledge/base"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_memory_manager_no_knowledge_base_env(self):
        """Test behavior when no knowledge base env var is set."""
        manager = MemoryManager(
            agent_id="no_env_agent",
            knowledge_base_path=None
        )
        
        assert manager.knowledge_base_path is None
    
    def test_memory_manager_explicit_knowledge_base_overrides_env(self):
        """Test that explicit knowledge base path overrides environment."""
        with patch.dict(os.environ, {'PRAVAL_KNOWLEDGE_BASE': '/env/path'}):
            manager = MemoryManager(
                agent_id="override_agent",
                knowledge_base_path="/explicit/path"
            )
            
            assert manager.knowledge_base_path == "/explicit/path"


class TestMemoryManagerBackendInitialization:
    """Test memory backend initialization logic."""
    
    @patch('praval.memory.memory_manager.EmbeddedVectorStore')
    @patch('praval.memory.memory_manager.ShortTermMemory')
    @patch('praval.memory.memory_manager.EpisodicMemory')
    @patch('praval.memory.memory_manager.SemanticMemory')
    def test_embedded_store_initialization_success(self, mock_semantic, mock_episodic, 
                                                   mock_short_term, mock_embedded_store):
        """Test successful embedded store initialization."""
        mock_store_instance = Mock()
        mock_embedded_store.return_value = mock_store_instance
        mock_short_term_instance = Mock()
        mock_short_term.return_value = mock_short_term_instance
        
        manager = MemoryManager(
            agent_id="embedded_test",
            backend="chromadb"
        )
        
        # Verify embedded store was created
        mock_embedded_store.assert_called_once_with(
            storage_path=None,
            collection_name="praval_memories"
        )
        
        # Verify backend is set correctly
        assert manager.backend == "chromadb"
        assert manager.embedded_store == mock_store_instance
        assert manager.long_term_memory is None
        
        # Verify subsystems initialized with embedded store
        mock_episodic.assert_called_once_with(
            long_term_memory=mock_store_instance,
            short_term_memory=mock_short_term_instance
        )
        mock_semantic.assert_called_once_with(
            long_term_memory=mock_store_instance
        )
    
    @patch('praval.memory.memory_manager.EmbeddedVectorStore')
    @patch('praval.memory.memory_manager.LongTermMemory')
    @patch('praval.memory.memory_manager.ShortTermMemory')
    @patch('praval.memory.memory_manager.EpisodicMemory')
    @patch('praval.memory.memory_manager.SemanticMemory')
    def test_qdrant_fallback_on_embedded_failure(self, mock_semantic, mock_episodic, 
                                                  mock_short_term, mock_long_term, mock_embedded_store):
        """Test fallback to Qdrant when embedded store fails in auto mode."""
        # Make embedded store fail
        mock_embedded_store.side_effect = Exception("ChromaDB not available")
        
        mock_long_term_instance = Mock()
        mock_long_term.return_value = mock_long_term_instance
        mock_short_term_instance = Mock()
        mock_short_term.return_value = mock_short_term_instance
        
        manager = MemoryManager(
            agent_id="fallback_test",
            backend="auto"
        )
        
        # Verify embedded store was attempted
        mock_embedded_store.assert_called_once()
        
        # Verify Qdrant was initialized as fallback
        mock_long_term.assert_called_once_with(
            qdrant_url="http://localhost:6333",
            collection_name="praval_memories"
        )
        
        assert manager.backend == "qdrant"
        assert manager.embedded_store is None
        assert manager.long_term_memory == mock_long_term_instance
        
        # Verify subsystems initialized with Qdrant
        mock_episodic.assert_called_once_with(
            long_term_memory=mock_long_term_instance,
            short_term_memory=mock_short_term_instance
        )
        mock_semantic.assert_called_once_with(
            long_term_memory=mock_long_term_instance
        )
    
    @patch('praval.memory.memory_manager.EmbeddedVectorStore')
    def test_embedded_store_failure_non_auto_raises(self, mock_embedded_store):
        """Test that embedded store failure raises exception in non-auto mode."""
        mock_embedded_store.side_effect = Exception("ChromaDB initialization failed")
        
        with pytest.raises(Exception, match="ChromaDB initialization failed"):
            MemoryManager(
                agent_id="fail_test",
                backend="chromadb"
            )
    
    @patch('praval.memory.memory_manager.LongTermMemory')
    def test_qdrant_failure_non_auto_raises(self, mock_long_term):
        """Test that Qdrant failure raises exception in non-auto mode."""
        mock_long_term.side_effect = Exception("Qdrant connection failed")
        
        with pytest.raises(Exception, match="Qdrant connection failed"):
            MemoryManager(
                agent_id="qdrant_fail_test",
                backend="qdrant"
            )
    
    @patch('praval.memory.memory_manager.EmbeddedVectorStore')
    @patch('praval.memory.memory_manager.LongTermMemory')
    @patch('praval.memory.memory_manager.ShortTermMemory')
    def test_memory_only_fallback(self, mock_short_term, mock_long_term, mock_embedded_store):
        """Test fallback to memory-only mode when both backends fail."""
        # Make both backends fail
        mock_embedded_store.side_effect = Exception("ChromaDB failed")
        mock_long_term.side_effect = Exception("Qdrant failed")
        
        mock_short_term_instance = Mock()
        mock_short_term.return_value = mock_short_term_instance
        
        manager = MemoryManager(
            agent_id="memory_only_test",
            backend="auto"
        )
        
        # Should fallback to memory-only mode
        assert manager.backend == "memory"
        assert manager.embedded_store is None
        assert manager.long_term_memory is None
        assert manager.episodic_memory is None
        assert manager.semantic_memory is None
        
        # Short-term memory should still be initialized
        mock_short_term.assert_called_once()
        assert manager.short_term_memory == mock_short_term_instance
    
    @patch('praval.memory.memory_manager.ShortTermMemory')
    def test_explicit_memory_backend(self, mock_short_term):
        """Test explicit memory-only backend selection."""
        mock_short_term_instance = Mock()
        mock_short_term.return_value = mock_short_term_instance
        
        manager = MemoryManager(
            agent_id="explicit_memory_test",
            backend="memory"
        )
        
        assert manager.backend == "memory"
        assert manager.embedded_store is None
        assert manager.long_term_memory is None
        assert manager.episodic_memory is None
        assert manager.semantic_memory is None
        assert manager.short_term_memory == mock_short_term_instance


class TestMemoryManagerStoreMemory:
    """Test memory storage functionality."""
    
    def setup_method(self):
        """Set up mock memory manager for testing."""
        with patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term:
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            self.manager = MemoryManager(
                agent_id="store_test_agent",
                backend="memory"
            )
            self.mock_short_term = mock_short_term_instance
    
    def test_store_memory_basic(self):
        """Test basic memory storage."""
        # Mock the store method to return a memory ID
        self.mock_short_term.store.return_value = "test_memory_id_123"
        
        result = self.manager.store_memory(
            agent_id="store_test_agent",
            content="Test memory content",
            memory_type=MemoryType.SEMANTIC,
            importance=0.8
        )
        
        # Should delegate to short-term memory store method
        self.mock_short_term.store.assert_called_once()
        call_args = self.mock_short_term.store.call_args[0][0]  # First positional argument (MemoryEntry)
        
        assert call_args.agent_id == "store_test_agent"
        assert call_args.content == "Test memory content"
        assert call_args.memory_type == MemoryType.SEMANTIC
        assert call_args.importance == 0.8
        assert result == "test_memory_id_123"
    
    @patch('praval.memory.memory_manager.EmbeddedVectorStore')
    @patch('praval.memory.memory_manager.ShortTermMemory')
    @patch('praval.memory.memory_manager.SemanticMemory')
    def test_store_memory_with_semantic_subsystem(self, mock_semantic_class, mock_short_term, mock_embedded_store):
        """Test memory storage with semantic memory subsystem."""
        mock_embedded_instance = Mock()
        mock_embedded_instance.store.return_value = "vector_memory_id"
        mock_embedded_store.return_value = mock_embedded_instance
        mock_short_term_instance = Mock()
        mock_short_term_instance.store.return_value = "short_term_id"
        mock_short_term.return_value = mock_short_term_instance
        mock_semantic_instance = Mock()
        mock_semantic_class.return_value = mock_semantic_instance
        
        manager = MemoryManager(
            agent_id="semantic_test_agent",
            backend="chromadb"
        )
        
        result = manager.store_memory(
            agent_id="semantic_test_agent",
            content="Semantic test content",
            memory_type=MemoryType.SEMANTIC,
            importance=0.9
        )
        
        # store_memory should use short-term memory and potentially embedded store
        # It doesn't automatically delegate to semantic memory subsystem
        mock_short_term_instance.store.assert_called_once()
        assert result == "short_term_id"
        
        # Semantic memory type should be preserved in the stored entry
        stored_entry = mock_short_term_instance.store.call_args[0][0]
        assert stored_entry.memory_type == MemoryType.SEMANTIC
        assert stored_entry.content == "Semantic test content"


class TestMemoryManagerSearchMemories:
    """Test memory search functionality."""
    
    def setup_method(self):
        """Set up mock memory manager for testing."""
        with patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term:
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            self.manager = MemoryManager(
                agent_id="search_test_agent",
                backend="memory"
            )
            self.mock_short_term = mock_short_term_instance
    
    def test_search_memories_basic(self):
        """Test basic memory search."""
        query = MemoryQuery(
            query_text="test query",
            agent_id="search_test_agent"
        )
        
        # Mock search result
        mock_result = MemorySearchResult(
            entries=[],
            scores=[],
            query=query,
            total_found=0
        )
        self.mock_short_term.search.return_value = mock_result
        
        result = self.manager.search_memories(query)
        
        # Result should be the combined result (which will just be short-term in memory-only mode)
        assert len(result.entries) == 0
        assert result.total_found == 0
        self.mock_short_term.search.assert_called_once_with(query)


class TestMemoryManagerConversationTracking:
    """Test conversation tracking functionality."""
    
    def setup_method(self):
        """Set up mock memory manager for testing."""
        with patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term:
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            self.manager = MemoryManager(
                agent_id="conversation_test_agent",
                backend="memory"
            )
            self.mock_short_term = mock_short_term_instance
    
    def test_store_conversation_turn_basic(self):
        """Test basic conversation turn storage."""
        # Mock the store method to return a memory ID
        self.mock_short_term.store.return_value = "conversation_memory_id"
        
        result = self.manager.store_conversation_turn(
            agent_id="conversation_test_agent",
            user_message="Hello, how are you?",
            agent_response="I'm doing well, thank you!",
            context={"session_id": "session_123"}
        )
        
        # In memory-only mode, this falls back to store_memory
        # Should delegate to short-term memory store method
        self.mock_short_term.store.assert_called_once()
        call_args = self.mock_short_term.store.call_args[0][0]  # First positional argument (MemoryEntry)
        
        assert call_args.agent_id == "conversation_test_agent"
        assert "Hello, how are you?" in call_args.content
        assert "I'm doing well, thank you!" in call_args.content
        assert call_args.memory_type == MemoryType.EPISODIC
        assert call_args.metadata["type"] == "conversation"
        assert call_args.metadata["context"] == {"session_id": "session_123"}
        assert result == "conversation_memory_id"
    
    @patch('praval.memory.memory_manager.EmbeddedVectorStore')
    @patch('praval.memory.memory_manager.ShortTermMemory')
    @patch('praval.memory.memory_manager.EpisodicMemory')
    def test_conversation_turn_with_episodic_subsystem(self, mock_episodic_class, mock_short_term, mock_embedded_store):
        """Test conversation turn storage with episodic memory subsystem."""
        mock_embedded_instance = Mock()
        mock_embedded_store.return_value = mock_embedded_instance
        mock_short_term_instance = Mock()
        mock_short_term.return_value = mock_short_term_instance
        mock_episodic_instance = Mock()
        mock_episodic_class.return_value = mock_episodic_instance
        
        manager = MemoryManager(
            agent_id="episodic_test_agent",
            backend="chromadb"
        )
        
        manager.store_conversation_turn(
            agent_id="episodic_test_agent",
            user_message="Episodic test message",
            agent_response="Episodic test response",
            context={"turn_id": "turn_456"}
        )
        
        # Should delegate to episodic memory
        mock_episodic_instance.store_conversation_turn.assert_called_once()


class TestMemoryManagerKnowledgeReferences:
    """Test knowledge reference functionality."""
    
    def setup_method(self):
        """Set up mock memory manager for testing."""
        with patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term:
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            self.manager = MemoryManager(
                agent_id="knowledge_test_agent",
                backend="memory"
            )
            self.mock_short_term = mock_short_term_instance
    
    def test_get_knowledge_references_memory_only(self):
        """Test knowledge references in memory-only mode."""
        # Mock the store method to return a memory ID
        self.mock_short_term.store.return_value = "knowledge_ref_123"
        
        references = self.manager.get_knowledge_references(
            content="Test knowledge content",
            importance_threshold=0.7
        )
        
        # Should store the content and return the memory ID
        assert references == ["knowledge_ref_123"]
        self.mock_short_term.store.assert_called_once()
        
        # Verify the stored memory entry
        call_args = self.mock_short_term.store.call_args[0][0]
        assert call_args.agent_id == "knowledge_test_agent"
        assert call_args.content == "Test knowledge content"
        assert call_args.memory_type == MemoryType.SEMANTIC
        assert call_args.importance == 0.7
    
    @patch('praval.memory.memory_manager.EmbeddedVectorStore')
    @patch('praval.memory.memory_manager.ShortTermMemory')
    def test_get_knowledge_references_with_vector_store(self, mock_short_term, mock_embedded_store):
        """Test knowledge references with vector store."""
        mock_embedded_instance = Mock()
        mock_embedded_store.return_value = mock_embedded_instance
        mock_short_term_instance = Mock()
        mock_short_term_instance.store.return_value = "vector_ref_123"
        mock_short_term.return_value = mock_short_term_instance
        
        manager = MemoryManager(
            agent_id="vector_knowledge_test_agent",
            backend="chromadb"
        )
        
        references = manager.get_knowledge_references(
            content="Vector knowledge content",
            importance_threshold=0.8
        )
        
        # Should still use the same store_memory logic and return memory ID
        assert references == ["vector_ref_123"]
        mock_short_term_instance.store.assert_called_once()


class TestMemoryManagerUtilityMethods:
    """Test utility methods of MemoryManager."""
    
    def setup_method(self):
        """Set up mock memory manager for testing."""
        with patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term:
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            self.manager = MemoryManager(
                agent_id="utility_test_agent",
                backend="memory"
            )
            self.mock_short_term = mock_short_term_instance
    
    def test_recall_by_id_basic(self):
        """Test recalling memory by ID."""
        mock_entry = MemoryEntry(
            id="recall_test_id",
            agent_id="utility_test_agent",
            memory_type=MemoryType.SHORT_TERM,
            content="Recalled content",
            metadata={}
        )
        self.mock_short_term.retrieve.return_value = mock_entry
        
        result = self.manager.recall_by_id("recall_test_id")
        
        assert result == [mock_entry]
        self.mock_short_term.retrieve.assert_called_once_with("recall_test_id")
    
    def test_get_conversation_context_basic(self):
        """Test getting conversation context."""
        mock_entry1 = MemoryEntry(
            id="conv_1",
            agent_id="utility_test_agent", 
            memory_type=MemoryType.EPISODIC,
            content="User: Hello\nAgent: Hi there",
            metadata={"type": "conversation"}
        )
        mock_entry2 = MemoryEntry(
            id="conv_2",
            agent_id="utility_test_agent",
            memory_type=MemoryType.EPISODIC, 
            content="User: How are you?\nAgent: I'm doing well",
            metadata={"type": "conversation"}
        )
        mock_context = [mock_entry1, mock_entry2]
        self.mock_short_term.get_recent.return_value = mock_context
        
        result = self.manager.get_conversation_context("utility_test_agent", turns=2)
        
        assert result == mock_context
        self.mock_short_term.get_recent.assert_called_once_with(agent_id="utility_test_agent", limit=2)
    
    def test_get_memory_stats_memory_only(self):
        """Test getting memory statistics in memory-only mode."""
        self.mock_short_term.get_stats.return_value = {
            "total_memories": 25,
            "agent_memories": 10
        }
        
        stats = self.manager.get_memory_stats()
        
        expected = {
            "agent_id": "utility_test_agent",
            "backend": "memory",
            "short_term_memory": {
                "total_memories": 25,
                "agent_memories": 10
            },
            "collection_name": "praval_memories",
            "persistent_memory": {"available": False, "error": "Not initialized"}
        }
        
        assert stats == expected


class TestMemoryManagerErrorHandling:
    """Test error handling in MemoryManager."""
    
    def test_initialization_with_invalid_backend(self):
        """Test that invalid backend falls back gracefully."""
        # Invalid backend should be treated as "memory" mode
        with patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term:
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            manager = MemoryManager(
                agent_id="invalid_backend_test",
                backend="invalid_backend"
            )
            
            # Should fallback to memory-only mode
            assert manager.backend == "memory"  # Falls back to memory mode
            assert manager.embedded_store is None
            assert manager.long_term_memory is None
            assert manager.episodic_memory is None
            assert manager.semantic_memory is None
    
    def test_store_memory_error_handling(self):
        """Test error handling in memory storage."""
        with patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term:
            mock_short_term_instance = Mock()
            mock_short_term_instance.store.side_effect = Exception("Storage error")
            mock_short_term.return_value = mock_short_term_instance
            
            manager = MemoryManager(
                agent_id="error_test_agent",
                backend="memory"
            )
            
            # Should propagate storage errors (not handled in current implementation)
            with pytest.raises(Exception, match="Storage error"):
                manager.store_memory(
                    agent_id="error_test_agent",
                    content="Error test content",
                    memory_type=MemoryType.SHORT_TERM,
                    importance=0.5
                )


class TestMemoryManagerIntegration:
    """Test integration scenarios for MemoryManager."""
    
    @patch('praval.memory.memory_manager.EmbeddedVectorStore')
    @patch('praval.memory.memory_manager.ShortTermMemory')
    @patch('praval.memory.memory_manager.EpisodicMemory')
    @patch('praval.memory.memory_manager.SemanticMemory')
    def test_full_memory_workflow(self, mock_semantic_class, mock_episodic_class, 
                                   mock_short_term, mock_embedded_store):
        """Test complete memory workflow with all subsystems."""
        # Set up mocks
        mock_embedded_instance = Mock()
        mock_embedded_store.return_value = mock_embedded_instance
        mock_short_term_instance = Mock()
        mock_short_term.return_value = mock_short_term_instance
        mock_episodic_instance = Mock()
        mock_episodic_class.return_value = mock_episodic_instance
        mock_semantic_instance = Mock()
        mock_semantic_class.return_value = mock_semantic_instance
        
        # Create manager with full capabilities
        manager = MemoryManager(
            agent_id="full_workflow_agent",
            backend="chromadb",
            knowledge_base_path="/path/to/knowledge"
        )
        
        # Verify all subsystems initialized
        assert manager.backend == "chromadb"
        assert manager.embedded_store == mock_embedded_instance
        assert manager.short_term_memory == mock_short_term_instance
        assert manager.episodic_memory == mock_episodic_instance
        assert manager.semantic_memory == mock_semantic_instance
        
        # Test integrated operations
        manager.store_conversation_turn(
            agent_id="full_workflow_agent",
            user_message="Integration test message",
            agent_response="Integration test response"
        )
        
        manager.store_knowledge(
            agent_id="full_workflow_agent",
            knowledge="Integration test knowledge",
            domain="testing",
            confidence=0.9
        )
        
        # Verify calls to appropriate subsystems
        mock_episodic_instance.store_conversation_turn.assert_called_once()
        mock_semantic_instance.store_fact.assert_called_once()