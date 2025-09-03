"""
Test collection separation feature in EmbeddedVectorStore

This tests the new architecture where knowledge base and conversational
memories are stored in separate ChromaDB collections for better separation
of concerns.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from praval.memory.embedded_store import EmbeddedVectorStore
from praval.memory.memory_types import MemoryEntry, MemoryType, MemoryQuery
from praval.memory.memory_manager import MemoryManager

pytestmark = pytest.mark.unit


class TestCollectionSeparation:
    """Test collection separation functionality"""
    
    def test_separated_collections_initialization(self):
        """Test that separated collections are created correctly"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EmbeddedVectorStore(
                storage_path=temp_dir,
                collection_name="test_memories",
                enable_collection_separation=True
            )
            
            # Check that both collections are created
            assert hasattr(store, 'knowledge_collection')
            assert hasattr(store, 'memory_collection')
            assert store.knowledge_collection.name == "test_memories_knowledge"
            assert store.memory_collection.name == "test_memories_memory"
            
            # Check that collection separation is enabled
            assert store.enable_collection_separation is True
    
    def test_legacy_single_collection_mode(self):
        """Test that legacy single collection mode still works"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EmbeddedVectorStore(
                storage_path=temp_dir,
                collection_name="test_memories",
                enable_collection_separation=False
            )
            
            # Check that only single collection is used
            assert hasattr(store, 'collection')
            assert store.collection.name == "test_memories"
            assert store.enable_collection_separation is False
    
    def test_semantic_memory_storage_in_knowledge_collection(self):
        """Test that semantic memories are stored in knowledge collection"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EmbeddedVectorStore(
                storage_path=temp_dir,
                collection_name="test_memories",
                enable_collection_separation=True
            )
            
            # Create semantic memory
            semantic_memory = MemoryEntry(
                id=None,
                agent_id="test_agent",
                memory_type=MemoryType.SEMANTIC,
                content="This is semantic knowledge about AI",
                metadata={"domain": "ai", "confidence": 0.9}
            )
            
            memory_id = store.store(semantic_memory)
            
            # Verify it's stored in knowledge collection
            knowledge_results = store.knowledge_collection.get(
                ids=[memory_id],
                include=["metadatas", "documents"]
            )
            assert len(knowledge_results["ids"]) == 1
            assert knowledge_results["documents"][0] == "This is semantic knowledge about AI"
            
            # Verify it's NOT in memory collection
            memory_results = store.memory_collection.get(
                ids=[memory_id],
                include=["metadatas", "documents"]  
            )
            assert len(memory_results["ids"]) == 0
    
    def test_episodic_memory_storage_in_memory_collection(self):
        """Test that episodic memories are stored in memory collection"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EmbeddedVectorStore(
                storage_path=temp_dir,
                collection_name="test_memories",
                enable_collection_separation=True
            )
            
            # Create episodic memory
            episodic_memory = MemoryEntry(
                id=None,
                agent_id="test_agent", 
                memory_type=MemoryType.EPISODIC,
                content="User asked about machine learning",
                metadata={"conversation_turn": 1}
            )
            
            memory_id = store.store(episodic_memory)
            
            # Verify it's stored in memory collection
            memory_results = store.memory_collection.get(
                ids=[memory_id],
                include=["metadatas", "documents"]
            )
            assert len(memory_results["ids"]) == 1
            assert memory_results["documents"][0] == "User asked about machine learning"
            
            # Verify it's NOT in knowledge collection
            knowledge_results = store.knowledge_collection.get(
                ids=[memory_id],
                include=["metadatas", "documents"]
            )
            assert len(knowledge_results["ids"]) == 0
    
    def test_short_term_memory_storage_in_memory_collection(self):
        """Test that short-term memories are stored in memory collection"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EmbeddedVectorStore(
                storage_path=temp_dir,
                collection_name="test_memories", 
                enable_collection_separation=True
            )
            
            # Create short-term memory
            short_term_memory = MemoryEntry(
                id=None,
                agent_id="test_agent",
                memory_type=MemoryType.SHORT_TERM,
                content="Current task: analyze user query",
                metadata={"task_id": "t123"}
            )
            
            memory_id = store.store(short_term_memory)
            
            # Verify it's stored in memory collection
            memory_results = store.memory_collection.get(
                ids=[memory_id],
                include=["metadatas", "documents"]
            )
            assert len(memory_results["ids"]) == 1
            assert memory_results["documents"][0] == "Current task: analyze user query"
    
    def test_knowledge_file_indexing_in_knowledge_collection(self):
        """Test that knowledge files are indexed in knowledge collection"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test knowledge file
            kb_dir = Path(temp_dir) / "knowledge"
            kb_dir.mkdir()
            test_file = kb_dir / "test.txt"
            test_file.write_text("This is test knowledge content")
            
            store = EmbeddedVectorStore(
                storage_path=temp_dir,
                collection_name="test_memories",
                enable_collection_separation=True
            )
            
            # Index the knowledge file
            indexed_count = store.index_knowledge_files(kb_dir, "test_agent")
            assert indexed_count == 1
            
            # Verify it's in knowledge collection
            all_knowledge = store.knowledge_collection.get(include=["metadatas", "documents"])
            assert len(all_knowledge["ids"]) == 1
            assert "This is test knowledge content" in all_knowledge["documents"][0]
            assert all_knowledge["metadatas"][0]["memory_type"] == "semantic"
            
            # Verify it's NOT in memory collection
            all_memory = store.memory_collection.get(include=["metadatas", "documents"])
            assert len(all_memory["ids"]) == 0
    
    def test_search_across_collections(self):
        """Test that search works across both collections"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EmbeddedVectorStore(
                storage_path=temp_dir,
                collection_name="test_memories",
                enable_collection_separation=True
            )
            
            # Store different types of memories
            semantic_memory = MemoryEntry(
                id=None,
                agent_id="test_agent",
                memory_type=MemoryType.SEMANTIC,
                content="Machine learning is a subset of AI",
                metadata={"domain": "ai"}
            )
            
            episodic_memory = MemoryEntry(
                id=None,
                agent_id="test_agent",
                memory_type=MemoryType.EPISODIC, 
                content="User asked about machine learning applications",
                metadata={"conversation_turn": 1}
            )
            
            store.store(semantic_memory)
            store.store(episodic_memory)
            
            # Search for "machine learning" - should find both
            query = MemoryQuery(
                query_text="machine learning",
                agent_id="test_agent",
                limit=10,
                similarity_threshold=0.1
            )
            
            results = store.search(query)
            assert len(results.entries) == 2
            
            # Verify we got both types
            memory_types = {entry.memory_type for entry in results.entries}
            assert MemoryType.SEMANTIC in memory_types
            assert MemoryType.EPISODIC in memory_types
    
    def test_search_specific_memory_types(self):
        """Test searching for specific memory types"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EmbeddedVectorStore(
                storage_path=temp_dir,
                collection_name="test_memories",
                enable_collection_separation=True
            )
            
            # Store different types of memories with similar content
            semantic_memory = MemoryEntry(
                id=None,
                agent_id="test_agent",
                memory_type=MemoryType.SEMANTIC,
                content="Python is a programming language",
                metadata={"domain": "programming"}
            )
            
            episodic_memory = MemoryEntry(
                id=None,
                agent_id="test_agent",
                memory_type=MemoryType.EPISODIC,
                content="User asked about Python programming",
                metadata={"conversation_turn": 1}
            )
            
            store.store(semantic_memory)
            store.store(episodic_memory)
            
            # Search only semantic memories
            semantic_query = MemoryQuery(
                query_text="Python",
                agent_id="test_agent",
                memory_types=[MemoryType.SEMANTIC],
                limit=10,
                similarity_threshold=0.1
            )
            
            semantic_results = store.search(semantic_query)
            assert len(semantic_results.entries) == 1
            assert semantic_results.entries[0].memory_type == MemoryType.SEMANTIC
            
            # Search only episodic memories
            episodic_query = MemoryQuery(
                query_text="Python",
                agent_id="test_agent", 
                memory_types=[MemoryType.EPISODIC],
                limit=10,
                similarity_threshold=0.1
            )
            
            episodic_results = store.search(episodic_query)
            assert len(episodic_results.entries) == 1
            assert episodic_results.entries[0].memory_type == MemoryType.EPISODIC
    
    def test_retrieval_across_collections(self):
        """Test that memory retrieval works across both collections"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EmbeddedVectorStore(
                storage_path=temp_dir,
                collection_name="test_memories",
                enable_collection_separation=True
            )
            
            # Store semantic memory
            semantic_memory = MemoryEntry(
                id=None,
                agent_id="test_agent",
                memory_type=MemoryType.SEMANTIC,
                content="Neural networks learn from data",
                metadata={"domain": "ai"}
            )
            
            semantic_id = store.store(semantic_memory)
            
            # Store episodic memory
            episodic_memory = MemoryEntry(
                id=None,
                agent_id="test_agent",
                memory_type=MemoryType.EPISODIC,
                content="User asked about neural networks",
                metadata={"conversation_turn": 1}
            )
            
            episodic_id = store.store(episodic_memory)
            
            # Test retrieval of both
            retrieved_semantic = store.retrieve(semantic_id)
            assert retrieved_semantic is not None
            assert retrieved_semantic.content == "Neural networks learn from data"
            assert retrieved_semantic.memory_type == MemoryType.SEMANTIC
            
            retrieved_episodic = store.retrieve(episodic_id)
            assert retrieved_episodic is not None
            assert retrieved_episodic.content == "User asked about neural networks"
            assert retrieved_episodic.memory_type == MemoryType.EPISODIC
    
    def test_deletion_policy_immutable_knowledge_base(self):
        """Test that knowledge base is immutable but memory collection allows deletion"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EmbeddedVectorStore(
                storage_path=temp_dir,
                collection_name="test_memories",
                enable_collection_separation=True
            )
            
            # Store memories in both collections
            semantic_memory = MemoryEntry(
                id=None,
                agent_id="test_agent",
                memory_type=MemoryType.SEMANTIC,
                content="Deep learning uses neural networks",
                metadata={"domain": "ai"}
            )
            
            episodic_memory = MemoryEntry(
                id=None,
                agent_id="test_agent",
                memory_type=MemoryType.EPISODIC,
                content="User asked about deep learning",
                metadata={"conversation_turn": 1}
            )
            
            semantic_id = store.store(semantic_memory)
            episodic_id = store.store(episodic_memory)
            
            # Semantic memory (knowledge base) should NOT be deletable
            assert store.delete(semantic_id) is False  # Deletion should fail
            assert store.retrieve(semantic_id) is not None  # Should still exist
            
            # Episodic memory (conversational) should be deletable
            assert store.delete(episodic_id) is True  # Deletion should succeed
            assert store.retrieve(episodic_id) is None  # Should be gone
    
    def test_clear_agent_memories_preserves_knowledge_base(self):
        """Test that clearing agent memories preserves knowledge base but clears conversations"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EmbeddedVectorStore(
                storage_path=temp_dir,
                collection_name="test_memories",
                enable_collection_separation=True
            )
            
            # Store memories for two different agents
            agent1_semantic = MemoryEntry(
                id=None,
                agent_id="agent1",
                memory_type=MemoryType.SEMANTIC,
                content="Agent 1 knowledge",
                metadata={"domain": "ai"}
            )
            
            agent1_episodic = MemoryEntry(
                id=None,
                agent_id="agent1", 
                memory_type=MemoryType.EPISODIC,
                content="Agent 1 conversation",
                metadata={"conversation_turn": 1}
            )
            
            agent2_episodic = MemoryEntry(
                id=None,
                agent_id="agent2",
                memory_type=MemoryType.EPISODIC,
                content="Agent 2 conversation",
                metadata={"conversation_turn": 1}
            )
            
            store.store(agent1_semantic)
            store.store(agent1_episodic)
            store.store(agent2_episodic)
            
            # Clear agent1 memories
            store.clear_agent_memories("agent1")
            
            # Verify agent1 knowledge base is preserved but conversation is cleared
            query_agent1_knowledge = MemoryQuery(
                query_text="Agent 1 knowledge",
                agent_id="agent1",
                memory_types=[MemoryType.SEMANTIC],
                limit=10,
                similarity_threshold=0.1
            )
            agent1_knowledge_results = store.search(query_agent1_knowledge)
            assert len(agent1_knowledge_results.entries) == 1  # Knowledge preserved
            
            query_agent1_conversation = MemoryQuery(
                query_text="Agent 1 conversation",
                agent_id="agent1",
                memory_types=[MemoryType.EPISODIC],
                limit=10,
                similarity_threshold=0.1
            )
            agent1_conversation_results = store.search(query_agent1_conversation)
            assert len(agent1_conversation_results.entries) == 0  # Conversation cleared
            
            # Verify agent2 conversation still exists
            query_agent2 = MemoryQuery(
                query_text="Agent 2",
                agent_id="agent2",
                limit=10,
                similarity_threshold=0.1
            )
            agent2_results = store.search(query_agent2)
            assert len(agent2_results.entries) == 1
    
    def test_get_stats_with_separated_collections(self):
        """Test statistics with separated collections"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EmbeddedVectorStore(
                storage_path=temp_dir,
                collection_name="test_memories",
                enable_collection_separation=True
            )
            
            # Store memories in both collections
            semantic_memory = MemoryEntry(
                id=None,
                agent_id="test_agent",
                memory_type=MemoryType.SEMANTIC,
                content="Knowledge about AI",
                metadata={"domain": "ai"}
            )
            
            episodic_memory = MemoryEntry(
                id=None,
                agent_id="test_agent",
                memory_type=MemoryType.EPISODIC,
                content="Conversation about AI",
                metadata={"conversation_turn": 1}
            )
            
            store.store(semantic_memory)
            store.store(episodic_memory)
            
            # Get stats
            stats = store.get_stats()
            
            # Verify separated collection stats
            assert stats["collection_separation"] is True
            assert stats["knowledge_collection"] == "test_memories_knowledge"
            assert stats["memory_collection"] == "test_memories_memory"
            assert stats["total_memories"] == 2
            assert stats["knowledge_memories"] == 1
            assert stats["conversational_memories"] == 1
    
    def test_health_check_with_separated_collections(self):
        """Test health check with separated collections"""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = EmbeddedVectorStore(
                storage_path=temp_dir,
                collection_name="test_memories",
                enable_collection_separation=True
            )
            
            # Health check should pass for both collections
            assert store.health_check() is True


class TestLegacyCollectionMigration:
    """Test migration from legacy single collection to separated collections"""
    
    def test_legacy_collection_migration(self):
        """Test that legacy collections are migrated to separated collections"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # First, create a legacy single collection with mixed data
            legacy_store = EmbeddedVectorStore(
                storage_path=temp_dir,
                collection_name="test_memories",
                enable_collection_separation=False
            )
            
            # Store mixed memory types in legacy collection
            semantic_memory = MemoryEntry(
                id=None,
                agent_id="test_agent",
                memory_type=MemoryType.SEMANTIC,
                content="Legacy semantic knowledge",
                metadata={"domain": "ai"}
            )
            
            episodic_memory = MemoryEntry(
                id=None,
                agent_id="test_agent",
                memory_type=MemoryType.EPISODIC,
                content="Legacy conversation",
                metadata={"conversation_turn": 1}
            )
            
            semantic_id = legacy_store.store(semantic_memory)
            episodic_id = legacy_store.store(episodic_memory)
            
            # Verify both are in the single collection
            legacy_stats = legacy_store.get_stats()
            assert legacy_stats["total_memories"] == 2
            assert "knowledge_memories" not in legacy_stats
            
            # Now reinitialize with separated collections enabled
            # This should trigger migration
            separated_store = EmbeddedVectorStore(
                storage_path=temp_dir,
                collection_name="test_memories",
                enable_collection_separation=True
            )
            
            # Verify migration occurred
            stats = separated_store.get_stats()
            assert stats["collection_separation"] is True
            assert stats["total_memories"] == 2
            assert stats["knowledge_memories"] == 1  # semantic memory
            assert stats["conversational_memories"] == 1  # episodic memory
            
            # Verify memories can still be retrieved
            retrieved_semantic = separated_store.retrieve(semantic_id)
            assert retrieved_semantic is not None
            assert retrieved_semantic.content == "Legacy semantic knowledge"
            
            retrieved_episodic = separated_store.retrieve(episodic_id)
            assert retrieved_episodic is not None
            assert retrieved_episodic.content == "Legacy conversation"
    
    def test_no_migration_when_no_legacy_collection(self):
        """Test that migration doesn't fail when no legacy collection exists"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Initialize with separated collections from the start
            store = EmbeddedVectorStore(
                storage_path=temp_dir,
                collection_name="test_memories",
                enable_collection_separation=True
            )
            
            # Should initialize without errors
            assert store.health_check() is True
            
            # Should have empty collections
            stats = store.get_stats()
            assert stats["total_memories"] == 0
            assert stats["knowledge_memories"] == 0
            assert stats["conversational_memories"] == 0


class TestMemoryManagerWithSeparatedCollections:
    """Test that MemoryManager works correctly with separated collections"""
    
    def test_memory_manager_with_separated_collections(self):
        """Test that MemoryManager uses separated collections by default"""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = MemoryManager(
                agent_id="test_agent",
                backend="chromadb",
                storage_path=temp_dir,
                collection_name="test_memories"
            )
            
            # Verify separated collections are enabled
            assert manager.embedded_store.enable_collection_separation is True
            
            # Store different types of memories
            semantic_id = manager.store_knowledge(
                agent_id="test_agent",
                knowledge="Python is a programming language",
                domain="programming"
            )
            
            conversation_id = manager.store_conversation_turn(
                agent_id="test_agent",
                user_message="What is Python?",
                agent_response="Python is a programming language"
            )
            
            # Verify stats show separated collections
            stats = manager.get_memory_stats()
            persistent_stats = stats["persistent_memory"]
            assert persistent_stats["collection_separation"] is True
            assert persistent_stats["knowledge_memories"] >= 1
            assert persistent_stats["conversational_memories"] >= 1
    
    def test_knowledge_base_indexing_with_separated_collections(self):
        """Test that knowledge base indexing works with separated collections"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create knowledge base files
            kb_dir = Path(temp_dir) / "knowledge"
            kb_dir.mkdir()
            (kb_dir / "python.txt").write_text("Python is a high-level programming language")
            (kb_dir / "ai.txt").write_text("Artificial Intelligence is machine intelligence")
            
            # Initialize manager with knowledge base
            manager = MemoryManager(
                agent_id="test_agent",
                backend="chromadb",
                storage_path=temp_dir,
                collection_name="test_memories",
                knowledge_base_path=str(kb_dir)
            )
            
            # Verify knowledge files were indexed
            stats = manager.get_memory_stats()
            persistent_stats = stats["persistent_memory"]
            assert persistent_stats["knowledge_memories"] >= 2
            
            # Verify they're in the knowledge collection (not memory collection)
            assert persistent_stats["conversational_memories"] == 0
            
            # Test search for knowledge
            results = manager.search_memories(MemoryQuery(
                query_text="Python programming",
                agent_id="test_agent",
                memory_types=[MemoryType.SEMANTIC],
                limit=5
            ))
            
            assert len(results.entries) >= 1
            found_python = any("Python" in entry.content for entry in results.entries)
            assert found_python