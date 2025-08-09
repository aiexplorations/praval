"""
Extended comprehensive tests for Praval MemoryManager to achieve 90%+ coverage.

This module focuses on the missing coverage areas identified in the coverage analysis:
- Error handling paths in persistent storage
- Vector store retrieval and caching
- Search error handling
- Semantic memory integration paths
- Clear agent memories functionality
- Memory stats error handling
- Health check logic
- Knowledge base indexing
- Shutdown procedures
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from praval.memory.memory_manager import MemoryManager
from praval.memory.memory_types import MemoryEntry, MemoryType, MemoryQuery, MemorySearchResult


class TestMemoryManagerErrorHandling:
    """Test error handling paths in MemoryManager."""
    
    def test_persistent_storage_error_handling(self):
        """Test error handling when persistent storage fails during store."""
        with patch('praval.memory.memory_manager.EmbeddedVectorStore') as mock_embedded, \
             patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term, \
             patch('praval.memory.memory_manager.SemanticMemory') as mock_semantic:
            
            # Setup mocks
            mock_embedded_instance = Mock()
            mock_embedded_instance.store.side_effect = Exception("Storage failure")
            mock_embedded.return_value = mock_embedded_instance
            
            mock_short_term_instance = Mock()
            mock_short_term_instance.store.return_value = "short_term_id"
            mock_short_term.return_value = mock_short_term_instance
            
            mock_semantic_instance = Mock()
            mock_semantic.return_value = mock_semantic_instance
            
            manager = MemoryManager(
                agent_id="error_test_agent",
                backend="chromadb"
            )
            
            # This should handle the persistent storage error gracefully
            result = manager.store_memory(
                agent_id="error_test_agent",
                content="Test content for error handling",
                memory_type=MemoryType.SEMANTIC,
                importance=0.9,
                store_long_term=True
            )
            
            # Should still return short-term ID despite persistent storage failure
            assert result == "short_term_id"
            mock_short_term_instance.store.assert_called_once()
            mock_embedded_instance.store.assert_called_once()
    
    def test_retrieve_memory_with_vector_store_caching(self):
        """Test memory retrieval with vector store fallback and caching."""
        with patch('praval.memory.memory_manager.EmbeddedVectorStore') as mock_embedded, \
             patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term, \
             patch('praval.memory.memory_manager.SemanticMemory') as mock_semantic:
            
            # Setup mocks
            mock_embedded_instance = Mock()
            mock_embedded.return_value = mock_embedded_instance
            
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            mock_semantic_instance = Mock()
            mock_semantic.return_value = mock_semantic_instance
            
            # Create test memory entry
            test_memory = MemoryEntry(
                id="vector_memory_123",
                agent_id="retrieval_agent",
                memory_type=MemoryType.SEMANTIC,
                content="Retrieved from vector store",
                metadata={"source": "vector_db"}
            )
            
            # Short-term returns None, vector store returns memory
            mock_short_term_instance.retrieve.return_value = None
            mock_embedded_instance.retrieve.return_value = test_memory
            
            manager = MemoryManager(
                agent_id="retrieval_agent",
                backend="chromadb"
            )
            
            result = manager.retrieve_memory("vector_memory_123")
            
            # Should retrieve from vector store and cache in short-term
            assert result == test_memory
            mock_short_term_instance.retrieve.assert_called_once_with("vector_memory_123")
            mock_embedded_instance.retrieve.assert_called_once_with("vector_memory_123")
            mock_short_term_instance.store.assert_called_once_with(test_memory)
    
    def test_search_memories_error_handling(self):
        """Test error handling during memory search."""
        with patch('praval.memory.memory_manager.EmbeddedVectorStore') as mock_embedded, \
             patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term, \
             patch('praval.memory.memory_manager.SemanticMemory') as mock_semantic:
            
            # Setup mocks
            mock_embedded_instance = Mock()
            mock_embedded_instance.search.side_effect = Exception("Search error")
            mock_embedded.return_value = mock_embedded_instance
            
            mock_short_term_instance = Mock()
            mock_short_term_result = MemorySearchResult(
                entries=[],
                scores=[],
                query=Mock(),
                total_found=0
            )
            mock_short_term_instance.search.return_value = mock_short_term_result
            mock_short_term.return_value = mock_short_term_instance
            
            mock_semantic_instance = Mock()
            mock_semantic.return_value = mock_semantic_instance
            
            manager = MemoryManager(
                agent_id="search_error_agent",
                backend="chromadb"
            )
            
            query = MemoryQuery(query_text="test query")
            result = manager.search_memories(query)
            
            # Should handle persistent search error gracefully
            assert isinstance(result, MemorySearchResult)
            assert result.total_found == 0
            mock_short_term_instance.search.assert_called_once()
            mock_embedded_instance.search.assert_called_once()


class TestMemoryManagerSemanticIntegration:
    """Test semantic memory integration paths."""
    
    def test_store_knowledge_with_semantic_subsystem(self):
        """Test store_knowledge method with semantic subsystem."""
        with patch('praval.memory.memory_manager.EmbeddedVectorStore') as mock_embedded, \
             patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term, \
             patch('praval.memory.memory_manager.SemanticMemory') as mock_semantic:
            
            # Setup mocks
            mock_embedded_instance = Mock()
            mock_embedded.return_value = mock_embedded_instance
            
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            mock_semantic_instance = Mock()
            mock_semantic_instance.store_fact.return_value = "semantic_fact_id"
            mock_semantic_instance.store_concept.return_value = "semantic_concept_id"
            mock_semantic.return_value = mock_semantic_instance
            
            manager = MemoryManager(
                agent_id="semantic_agent",
                backend="chromadb"
            )
            
            # Test storing fact
            fact_result = manager.store_knowledge(
                agent_id="semantic_agent",
                knowledge="The sky is blue",
                domain="general",
                confidence=0.9,
                knowledge_type="fact"
            )
            
            assert fact_result == "semantic_fact_id"
            mock_semantic_instance.store_fact.assert_called_once_with(
                "semantic_agent", "The sky is blue", "general", 0.9
            )
            
            # Test storing concept  
            concept_result = manager.store_knowledge(
                agent_id="semantic_agent",
                knowledge="Machine Learning",
                domain="ai",
                confidence=0.8,
                knowledge_type="concept"
            )
            
            assert concept_result == "semantic_concept_id"
            mock_semantic_instance.store_concept.assert_called_once_with(
                "semantic_agent", "Machine Learning", "Machine Learning", "ai"
            )
    
    def test_store_knowledge_fallback_to_basic_storage(self):
        """Test store_knowledge fallback when no semantic subsystem."""
        with patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term:
            
            mock_short_term_instance = Mock()
            mock_short_term_instance.store.return_value = "fallback_knowledge_id"
            mock_short_term.return_value = mock_short_term_instance
            
            manager = MemoryManager(
                agent_id="fallback_agent",
                backend="memory"
            )
            
            result = manager.store_knowledge(
                agent_id="fallback_agent",
                knowledge="Fallback knowledge",
                domain="test",
                confidence=0.7,
                knowledge_type="fact"
            )
            
            assert result == "fallback_knowledge_id"
            mock_short_term_instance.store.assert_called_once()
            
            # Verify fallback storage parameters
            stored_entry = mock_short_term_instance.store.call_args[0][0]
            assert stored_entry.content == "Fallback knowledge"
            assert stored_entry.memory_type == MemoryType.SEMANTIC
            assert stored_entry.metadata["domain"] == "test"
            assert stored_entry.metadata["confidence"] == 0.7
            assert stored_entry.metadata["knowledge_type"] == "fact"
    
    def test_get_domain_knowledge_with_semantic_subsystem(self):
        """Test get_domain_knowledge with semantic subsystem."""
        with patch('praval.memory.memory_manager.EmbeddedVectorStore') as mock_embedded, \
             patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term, \
             patch('praval.memory.memory_manager.SemanticMemory') as mock_semantic:
            
            # Setup mocks
            mock_embedded_instance = Mock()
            mock_embedded.return_value = mock_embedded_instance
            
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            test_entries = [
                MemoryEntry(id="domain_1", agent_id="test", memory_type=MemoryType.SEMANTIC, 
                           content="Domain knowledge 1", metadata={}),
                MemoryEntry(id="domain_2", agent_id="test", memory_type=MemoryType.SEMANTIC,
                           content="Domain knowledge 2", metadata={})
            ]
            
            mock_semantic_instance = Mock()
            mock_semantic_instance.get_knowledge_in_domain.return_value = test_entries
            mock_semantic.return_value = mock_semantic_instance
            
            manager = MemoryManager(
                agent_id="domain_agent",
                backend="chromadb"
            )
            
            result = manager.get_domain_knowledge(
                agent_id="domain_agent",
                domain="ai",
                limit=10
            )
            
            assert result == test_entries
            mock_semantic_instance.get_knowledge_in_domain.assert_called_once_with(
                "domain_agent", "ai", 10
            )
    
    def test_get_domain_knowledge_fallback_search(self):
        """Test get_domain_knowledge fallback search when no semantic subsystem."""
        with patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term:
            
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            test_entries = [
                MemoryEntry(id="fallback_1", agent_id="test", memory_type=MemoryType.SEMANTIC,
                           content="Fallback knowledge", metadata={})
            ]
            
            search_result = MemorySearchResult(
                entries=test_entries,
                scores=[0.8],
                query=Mock(),
                total_found=1
            )
            
            manager = MemoryManager(
                agent_id="fallback_agent",
                backend="memory"
            )
            
            # Mock the search_memories method
            manager.search_memories = Mock(return_value=search_result)
            
            result = manager.get_domain_knowledge(
                agent_id="fallback_agent",
                domain="test_domain",
                limit=5
            )
            
            assert result == test_entries
            manager.search_memories.assert_called_once()
            
            # Verify query parameters
            query_call = manager.search_memories.call_args[0][0]
            assert query_call.query_text == "test_domain"
            assert query_call.memory_types == [MemoryType.SEMANTIC]
            assert query_call.agent_id == "fallback_agent"
            assert query_call.limit == 5


class TestMemoryManagerUtilityMethods:
    """Test utility methods and maintenance operations."""
    
    def test_clear_agent_memories_with_vector_store(self):
        """Test clearing agent memories with vector store."""
        with patch('praval.memory.memory_manager.EmbeddedVectorStore') as mock_embedded, \
             patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term, \
             patch('praval.memory.memory_manager.SemanticMemory') as mock_semantic:
            
            # Setup mocks
            mock_embedded_instance = Mock()
            mock_embedded.return_value = mock_embedded_instance
            
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            mock_semantic_instance = Mock()
            mock_semantic.return_value = mock_semantic_instance
            
            manager = MemoryManager(
                agent_id="clear_test_agent",
                backend="chromadb"
            )
            
            manager.clear_agent_memories("target_agent")
            
            # Should clear both short-term and persistent memory
            mock_short_term_instance.clear_agent_memories.assert_called_once_with("target_agent")
            mock_embedded_instance.clear_agent_memories.assert_called_once_with("target_agent")
    
    def test_clear_agent_memories_error_handling(self):
        """Test error handling during agent memory clearing."""
        with patch('praval.memory.memory_manager.EmbeddedVectorStore') as mock_embedded, \
             patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term, \
             patch('praval.memory.memory_manager.SemanticMemory') as mock_semantic:
            
            # Setup mocks
            mock_embedded_instance = Mock()
            mock_embedded_instance.clear_agent_memories.side_effect = Exception("Clear error")
            mock_embedded.return_value = mock_embedded_instance
            
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            mock_semantic_instance = Mock()
            mock_semantic.return_value = mock_semantic_instance
            
            manager = MemoryManager(
                agent_id="clear_error_agent",
                backend="chromadb"
            )
            
            # Should handle persistent clear error gracefully
            manager.clear_agent_memories("target_agent")
            
            mock_short_term_instance.clear_agent_memories.assert_called_once_with("target_agent")
            mock_embedded_instance.clear_agent_memories.assert_called_once_with("target_agent")
    
    def test_get_memory_stats_with_vector_store_error(self):
        """Test memory stats with vector store error."""
        with patch('praval.memory.memory_manager.EmbeddedVectorStore') as mock_embedded, \
             patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term, \
             patch('praval.memory.memory_manager.SemanticMemory') as mock_semantic, \
             patch('praval.memory.memory_manager.EpisodicMemory') as mock_episodic:
            
            # Setup mocks
            mock_embedded_instance = Mock()
            mock_embedded_instance.get_stats.side_effect = Exception("Stats error")
            mock_embedded.return_value = mock_embedded_instance
            
            mock_short_term_instance = Mock()
            mock_short_term_instance.get_stats.return_value = {"total": 10}
            mock_short_term.return_value = mock_short_term_instance
            
            mock_semantic_instance = Mock()
            mock_semantic_instance.get_stats.return_value = {"type": "semantic"}
            mock_semantic.return_value = mock_semantic_instance
            
            mock_episodic_instance = Mock() 
            mock_episodic_instance.get_stats.return_value = {"type": "episodic"}
            mock_episodic.return_value = mock_episodic_instance
            
            manager = MemoryManager(
                agent_id="stats_error_agent",
                backend="chromadb"
            )
            
            stats = manager.get_memory_stats()
            
            # Should handle stats error gracefully
            assert stats["agent_id"] == "stats_error_agent"
            assert stats["backend"] == "chromadb"
            assert stats["short_term_memory"] == {"total": 10}
            assert stats["persistent_memory"]["available"] is False
            assert "error" in stats["persistent_memory"]
            assert stats["episodic_memory"] == {"type": "episodic"}
            assert stats["semantic_memory"] == {"type": "semantic"}
    
    def test_health_check_all_systems(self):
        """Test comprehensive health check."""
        with patch('praval.memory.memory_manager.EmbeddedVectorStore') as mock_embedded, \
             patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term, \
             patch('praval.memory.memory_manager.SemanticMemory') as mock_semantic:
            
            # Setup mocks
            mock_embedded_instance = Mock()
            mock_embedded_instance.health_check.return_value = True
            mock_embedded.return_value = mock_embedded_instance
            
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            mock_semantic_instance = Mock()
            mock_semantic.return_value = mock_semantic_instance
            
            manager = MemoryManager(
                agent_id="health_agent",
                backend="chromadb"
            )
            
            health = manager.health_check()
            
            # All systems should be healthy
            assert health["short_term_memory"] is True
            assert health["persistent_memory"] is True
            assert health["episodic_memory"] is True
            assert health["semantic_memory"] is True
            
            mock_embedded_instance.health_check.assert_called_once()
    
    def test_health_check_vector_store_unhealthy(self):
        """Test health check when vector store is unhealthy."""
        with patch('praval.memory.memory_manager.EmbeddedVectorStore') as mock_embedded, \
             patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term, \
             patch('praval.memory.memory_manager.SemanticMemory') as mock_semantic:
            
            # Setup mocks
            mock_embedded_instance = Mock()
            mock_embedded_instance.health_check.return_value = False
            mock_embedded.return_value = mock_embedded_instance
            
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            mock_semantic_instance = Mock()
            mock_semantic.return_value = mock_semantic_instance
            
            manager = MemoryManager(
                agent_id="unhealthy_agent",
                backend="chromadb"
            )
            
            health = manager.health_check()
            
            # Vector store dependent systems should be unhealthy
            assert health["short_term_memory"] is True
            assert health["persistent_memory"] is False
            assert health["episodic_memory"] is False
            assert health["semantic_memory"] is False


class TestMemoryManagerKnowledgeBase:
    """Test knowledge base indexing functionality."""
    
    def test_knowledge_base_indexing_success(self):
        """Test successful knowledge base indexing."""
        with patch('praval.memory.memory_manager.EmbeddedVectorStore') as mock_embedded, \
             patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term, \
             patch('praval.memory.memory_manager.SemanticMemory') as mock_semantic:
            
            # Create temporary knowledge base directory
            with tempfile.TemporaryDirectory() as temp_dir:
                kb_path = Path(temp_dir)
                
                # Create test knowledge files
                (kb_path / "doc1.txt").write_text("Knowledge document 1")
                (kb_path / "doc2.md").write_text("# Knowledge document 2")
                
                # Setup mocks
                mock_embedded_instance = Mock()
                mock_embedded_instance.index_knowledge_files.return_value = 2
                mock_embedded.return_value = mock_embedded_instance
                
                mock_short_term_instance = Mock()
                mock_short_term.return_value = mock_short_term_instance
                
                mock_semantic_instance = Mock()
                mock_semantic.return_value = mock_semantic_instance
                
                manager = MemoryManager(
                    agent_id="kb_agent",
                    backend="chromadb",
                    knowledge_base_path=str(kb_path)
                )
                
                # Indexing should have been called during initialization
                mock_embedded_instance.index_knowledge_files.assert_called_once_with(
                    kb_path, "kb_agent"
                )
    
    def test_knowledge_base_indexing_nonexistent_path(self):
        """Test knowledge base indexing with nonexistent path."""
        with patch('praval.memory.memory_manager.EmbeddedVectorStore') as mock_embedded, \
             patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term, \
             patch('praval.memory.memory_manager.SemanticMemory') as mock_semantic:
            
            # Setup mocks
            mock_embedded_instance = Mock()
            mock_embedded.return_value = mock_embedded_instance
            
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            mock_semantic_instance = Mock()
            mock_semantic.return_value = mock_semantic_instance
            
            manager = MemoryManager(
                agent_id="nonexistent_kb_agent",
                backend="chromadb",
                knowledge_base_path="/nonexistent/path"
            )
            
            # Should handle nonexistent path gracefully
            mock_embedded_instance.index_knowledge_files.assert_not_called()
    
    def test_knowledge_base_indexing_error(self):
        """Test error handling during knowledge base indexing."""
        with patch('praval.memory.memory_manager.EmbeddedVectorStore') as mock_embedded, \
             patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term, \
             patch('praval.memory.memory_manager.SemanticMemory') as mock_semantic:
            
            # Create temporary knowledge base directory
            with tempfile.TemporaryDirectory() as temp_dir:
                kb_path = Path(temp_dir)
                (kb_path / "doc.txt").write_text("Test document")
                
                # Setup mocks
                mock_embedded_instance = Mock()
                mock_embedded_instance.index_knowledge_files.side_effect = Exception("Indexing error")
                mock_embedded.return_value = mock_embedded_instance
                
                mock_short_term_instance = Mock()
                mock_short_term.return_value = mock_short_term_instance
                
                mock_semantic_instance = Mock()
                mock_semantic.return_value = mock_semantic_instance
                
                # Should handle indexing error gracefully
                manager = MemoryManager(
                    agent_id="kb_error_agent", 
                    backend="chromadb",
                    knowledge_base_path=str(kb_path)
                )
                
                # Manager should still be initialized despite indexing error
                assert manager.agent_id == "kb_error_agent"
                mock_embedded_instance.index_knowledge_files.assert_called_once()


class TestMemoryManagerAdvancedFeatures:
    """Test advanced features and edge cases."""
    
    def test_get_conversation_context_episodic_fallback(self):
        """Test conversation context fallback when no episodic memory."""
        with patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term:
            
            mock_short_term_instance = Mock()
            test_memories = [
                MemoryEntry(id="conv_1", agent_id="agent", memory_type=MemoryType.EPISODIC,
                           content="Conversation 1", metadata={}),
                MemoryEntry(id="conv_2", agent_id="agent", memory_type=MemoryType.EPISODIC,
                           content="Conversation 2", metadata={})
            ]
            mock_short_term_instance.get_recent.return_value = test_memories
            mock_short_term.return_value = mock_short_term_instance
            
            manager = MemoryManager(
                agent_id="fallback_conv_agent",
                backend="memory"
            )
            
            result = manager.get_conversation_context("test_agent", turns=5)
            
            assert result == test_memories
            mock_short_term_instance.get_recent.assert_called_once_with(agent_id="test_agent", limit=5)
    
    def test_should_store_long_term_logic(self):
        """Test _should_store_long_term decision logic."""
        with patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term:
            
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            manager = MemoryManager(
                agent_id="long_term_agent",
                backend="memory"
            )
            
            # Test high importance
            high_imp_memory = MemoryEntry(
                id="high_imp", agent_id="test", memory_type=MemoryType.SHORT_TERM,
                content="High importance", metadata={}, importance=0.8
            )
            assert manager._should_store_long_term(high_imp_memory) is True
            
            # Test semantic type
            semantic_memory = MemoryEntry(
                id="semantic", agent_id="test", memory_type=MemoryType.SEMANTIC,
                content="Semantic content", metadata={}, importance=0.3
            )
            assert manager._should_store_long_term(semantic_memory) is True
            
            # Test episodic type
            episodic_memory = MemoryEntry(
                id="episodic", agent_id="test", memory_type=MemoryType.EPISODIC,
                content="Episodic content", metadata={}, importance=0.3
            )
            assert manager._should_store_long_term(episodic_memory) is True
            
            # Test long content
            long_content_memory = MemoryEntry(
                id="long", agent_id="test", memory_type=MemoryType.SHORT_TERM,
                content="A" * 300, metadata={}, importance=0.3
            )
            assert manager._should_store_long_term(long_content_memory) is True
            
            # Test low importance, short content, short-term type
            low_memory = MemoryEntry(
                id="low", agent_id="test", memory_type=MemoryType.SHORT_TERM,
                content="Short", metadata={}, importance=0.3
            )
            assert manager._should_store_long_term(low_memory) is False
    
    def test_combine_search_results_deduplication(self):
        """Test search result combination and deduplication."""
        with patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term:
            
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            manager = MemoryManager(
                agent_id="combine_agent",
                backend="memory"
            )
            
            # Create test memories with overlapping IDs
            memory1 = MemoryEntry(id="mem_1", agent_id="test", memory_type=MemoryType.SHORT_TERM,
                                 content="Memory 1", metadata={})
            memory2 = MemoryEntry(id="mem_2", agent_id="test", memory_type=MemoryType.SHORT_TERM,
                                 content="Memory 2", metadata={})
            memory3 = MemoryEntry(id="mem_1", agent_id="test", memory_type=MemoryType.SHORT_TERM,
                                 content="Memory 1 duplicate", metadata={})
            
            # Create search results with duplicates
            short_term_result = MemorySearchResult(
                entries=[memory1, memory2],
                scores=[0.9, 0.8],
                query=Mock(),
                total_found=2
            )
            
            persistent_result = MemorySearchResult(
                entries=[memory3],  # Duplicate ID
                scores=[0.7],
                query=Mock(),
                total_found=1
            )
            
            query = MemoryQuery(query_text="test", limit=5)
            results = [("short_term", short_term_result), ("persistent", persistent_result)]
            
            combined = manager._combine_search_results(results, query)
            
            # Should deduplicate and sort by score
            assert len(combined.entries) == 2
            assert combined.entries[0].id == "mem_1"  # Higher score from short-term
            assert combined.entries[1].id == "mem_2"
            assert combined.scores == [0.9, 0.8]
            assert combined.total_found == 2
    
    def test_shutdown_procedure(self):
        """Test shutdown procedure."""
        with patch('praval.memory.memory_manager.ShortTermMemory') as mock_short_term:
            
            mock_short_term_instance = Mock()
            mock_short_term.return_value = mock_short_term_instance
            
            manager = MemoryManager(
                agent_id="shutdown_agent",
                backend="memory"
            )
            
            manager.shutdown()
            
            # Should shutdown short-term memory
            mock_short_term_instance.shutdown.assert_called_once()