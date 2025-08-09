"""
Comprehensive tests for Praval ShortTermMemory.

This module ensures the short-term memory system is bulletproof and handles
all edge cases correctly. Tests are strict and verify both functionality
and error conditions, including thread safety.
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from collections import deque

from praval.memory.short_term_memory import ShortTermMemory
from praval.memory.memory_types import MemoryEntry, MemoryType, MemoryQuery, MemorySearchResult


class TestShortTermMemoryInitialization:
    """Test ShortTermMemory initialization with comprehensive coverage."""
    
    def test_short_term_memory_default_initialization(self):
        """Test short-term memory with default parameters."""
        memory = ShortTermMemory()
        
        assert memory.max_entries == 1000
        assert memory.retention_hours == 24
        assert memory.cleanup_interval == 3600
        assert isinstance(memory._memories, dict)
        assert isinstance(memory._agent_memories, dict)
        assert isinstance(memory._recent_memories, deque)
        assert memory._recent_memories.maxlen == 1000
        assert memory._shutdown is False
        assert memory._cleanup_thread is not None
    
    def test_short_term_memory_custom_initialization(self):
        """Test short-term memory with custom parameters."""
        memory = ShortTermMemory(
            max_entries=500,
            retention_hours=12,
            cleanup_interval=1800
        )
        
        assert memory.max_entries == 500
        assert memory.retention_hours == 12
        assert memory.cleanup_interval == 1800
        assert memory._recent_memories.maxlen == 500
        
        # Cleanup to prevent background thread issues
        memory.shutdown()
    
    def test_short_term_memory_agent_memory_capacity(self):
        """Test that agent-specific memory has correct capacity."""
        memory = ShortTermMemory(max_entries=100)
        
        # Agent memory should be max_entries // 10
        expected_agent_capacity = 10
        
        # Create an entry to trigger agent memory creation
        entry = MemoryEntry(
            id="capacity_test",
            agent_id="test_agent",
            memory_type=MemoryType.SHORT_TERM,
            content="Capacity test",
            metadata={}
        )
        
        memory.store(entry)
        
        assert memory._agent_memories["test_agent"].maxlen == expected_agent_capacity
        
        memory.shutdown()
    
    def test_short_term_memory_cleanup_thread_starts(self):
        """Test that cleanup thread starts correctly."""
        memory = ShortTermMemory()
        
        assert memory._cleanup_thread is not None
        assert memory._cleanup_thread.daemon is True
        assert memory._cleanup_thread.is_alive()
        
        memory.shutdown()


class TestShortTermMemoryStorage:
    """Test memory storage functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.memory = ShortTermMemory(max_entries=10, retention_hours=1)
    
    def teardown_method(self):
        """Clean up test environment."""
        self.memory.shutdown()
    
    def test_store_memory_basic(self):
        """Test basic memory storage."""
        entry = MemoryEntry(
            id="store_test",
            agent_id="test_agent",
            memory_type=MemoryType.SHORT_TERM,
            content="Test storage content",
            metadata={"test": True}
        )
        
        result_id = self.memory.store(entry)
        
        assert result_id == "store_test"
        assert "store_test" in self.memory._memories
        assert self.memory._memories["store_test"] == entry
        assert "store_test" in self.memory._agent_memories["test_agent"]
        assert "store_test" in self.memory._recent_memories
    
    def test_store_memory_sets_default_type(self):
        """Test that store sets default memory type when None."""
        entry = MemoryEntry(
            id="default_type_test",
            agent_id="test_agent",
            memory_type=None,
            content="Default type test",
            metadata={}
        )
        
        self.memory.store(entry)
        
        stored_entry = self.memory._memories["default_type_test"]
        assert stored_entry.memory_type == MemoryType.SHORT_TERM
    
    def test_store_memory_multiple_agents(self):
        """Test storing memories for multiple agents."""
        entries = []
        for i in range(3):
            entry = MemoryEntry(
                id=f"multi_agent_{i}",
                agent_id=f"agent_{i}",
                memory_type=MemoryType.SHORT_TERM,
                content=f"Content for agent {i}",
                metadata={"agent_index": i}
            )
            entries.append(entry)
            self.memory.store(entry)
        
        # Verify all entries stored
        assert len(self.memory._memories) == 3
        
        # Verify agent-specific storage
        for i in range(3):
            agent_id = f"agent_{i}"
            assert f"multi_agent_{i}" in self.memory._agent_memories[agent_id]
        
        # Verify recency order
        recent_ids = list(self.memory._recent_memories)
        expected_order = ["multi_agent_0", "multi_agent_1", "multi_agent_2"]
        assert recent_ids == expected_order
    
    def test_store_memory_capacity_cleanup(self):
        """Test automatic cleanup when capacity exceeded."""
        # Fill to capacity
        for i in range(10):
            entry = MemoryEntry(
                id=f"capacity_{i}",
                agent_id="capacity_agent",
                memory_type=MemoryType.SHORT_TERM,
                content=f"Capacity test {i}",
                metadata={}
            )
            self.memory.store(entry)
        
        assert len(self.memory._memories) == 10
        
        # Store one more to trigger cleanup
        overflow_entry = MemoryEntry(
            id="overflow",
            agent_id="capacity_agent",
            memory_type=MemoryType.SHORT_TERM,
            content="Overflow entry",
            metadata={}
        )
        
        with patch.object(self.memory, '_cleanup_old_memories') as mock_cleanup:
            self.memory.store(overflow_entry)
            mock_cleanup.assert_called_once()
    
    def test_store_memory_thread_safety(self):
        """Test that store operation is thread-safe."""
        results = []
        errors = []
        
        def store_worker(worker_id):
            try:
                for i in range(5):
                    entry = MemoryEntry(
                        id=f"thread_{worker_id}_{i}",
                        agent_id=f"worker_{worker_id}",
                        memory_type=MemoryType.SHORT_TERM,
                        content=f"Thread {worker_id} entry {i}",
                        metadata={"worker": worker_id, "index": i}
                    )
                    result = self.memory.store(entry)
                    results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = []
        for worker_id in range(3):
            thread = threading.Thread(target=store_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify no errors and correct storage
        assert not errors
        assert len(results) == 15  # 3 workers × 5 entries each
        assert len(self.memory._memories) == 10  # Limited by max_entries


class TestShortTermMemoryRetrieval:
    """Test memory retrieval functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.memory = ShortTermMemory()
        
        # Create test memories
        self.test_entries = []
        for i in range(5):
            entry = MemoryEntry(
                id=f"retrieve_test_{i}",
                agent_id=f"agent_{i % 2}",  # Alternate between two agents
                memory_type=MemoryType.SHORT_TERM,
                content=f"Retrieval test content {i}",
                metadata={"index": i}
            )
            self.test_entries.append(entry)
            self.memory.store(entry)
    
    def teardown_method(self):
        """Clean up test environment."""
        self.memory.shutdown()
    
    def test_retrieve_memory_existing(self):
        """Test retrieving existing memory."""
        result = self.memory.retrieve("retrieve_test_2")
        
        assert result is not None
        assert result.id == "retrieve_test_2"
        assert result.content == "Retrieval test content 2"
        assert result.access_count == 1  # Should be marked as accessed
    
    def test_retrieve_memory_nonexistent(self):
        """Test retrieving non-existent memory."""
        result = self.memory.retrieve("nonexistent_id")
        
        assert result is None
    
    def test_retrieve_memory_marks_accessed(self):
        """Test that retrieve marks memory as accessed."""
        original_entry = self.memory._memories["retrieve_test_1"]
        original_access_count = original_entry.access_count
        original_accessed_at = original_entry.accessed_at
        
        # Small delay to ensure timestamp difference
        time.sleep(0.01)
        
        retrieved = self.memory.retrieve("retrieve_test_1")
        
        assert retrieved.access_count == original_access_count + 1
        assert retrieved.accessed_at > original_accessed_at
    
    def test_retrieve_memory_thread_safety(self):
        """Test that retrieve operation is thread-safe."""
        results = []
        errors = []
        
        def retrieve_worker():
            try:
                for i in range(5):
                    result = self.memory.retrieve(f"retrieve_test_{i}")
                    results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=retrieve_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify no errors
        assert not errors
        assert len(results) == 15  # 3 threads × 5 retrievals each
        
        # All retrievals should have succeeded
        assert all(result is not None for result in results)


class TestShortTermMemorySearch:
    """Test memory search functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.memory = ShortTermMemory()
        
        # Create diverse test memories
        test_data = [
            ("search_1", "agent_1", "The quick brown fox jumps", MemoryType.SHORT_TERM, 0.5),
            ("search_2", "agent_1", "Programming in Python is fun", MemoryType.SEMANTIC, 0.7),
            ("search_3", "agent_2", "Machine learning algorithms work", MemoryType.PROCEDURAL, 0.8),
            ("search_4", "agent_2", "The fox and the hound story", MemoryType.EPISODIC, 0.6),
            ("search_5", "agent_1", "Python programming tutorial", MemoryType.SEMANTIC, 0.9),
        ]
        
        for entry_id, agent_id, content, memory_type, importance in test_data:
            entry = MemoryEntry(
                id=entry_id,
                agent_id=agent_id,
                memory_type=memory_type,
                content=content,
                metadata={"importance": importance},
                importance=importance
            )
            self.memory.store(entry)
    
    def teardown_method(self):
        """Clean up test environment."""
        self.memory.shutdown()
    
    def test_search_basic_query(self):
        """Test basic search query."""
        query = MemoryQuery(query_text="Python programming")
        result = self.memory.search(query)
        
        assert isinstance(result, MemorySearchResult)
        assert result.query == query
        assert len(result.entries) >= 1
        assert len(result.scores) == len(result.entries)
        
        # Should find Python-related entries
        python_entries = [e for e in result.entries if "Python" in e.content]
        assert len(python_entries) >= 1
    
    def test_search_agent_specific(self):
        """Test search with agent ID filter."""
        query = MemoryQuery(
            query_text="fox",
            agent_id="agent_2"
        )
        result = self.memory.search(query)
        
        # Should only return entries from agent_2
        assert all(entry.agent_id == "agent_2" for entry in result.entries)
        
        # Should find the fox-related entry from agent_2
        assert len(result.entries) >= 1
        assert any("fox" in entry.content for entry in result.entries)
    
    def test_search_memory_type_filter(self):
        """Test search with memory type filter."""
        query = MemoryQuery(
            query_text="Python",
            memory_types=[MemoryType.SEMANTIC]
        )
        result = self.memory.search(query)
        
        # Should only return semantic memories
        assert all(entry.memory_type == MemoryType.SEMANTIC for entry in result.entries)
        assert len(result.entries) >= 1
    
    def test_search_similarity_threshold(self):
        """Test search with custom similarity threshold."""
        high_threshold_query = MemoryQuery(
            query_text="fox",
            similarity_threshold=0.9  # Very high threshold
        )
        low_threshold_query = MemoryQuery(
            query_text="fox",
            similarity_threshold=0.1  # Very low threshold
        )
        
        high_result = self.memory.search(high_threshold_query)
        low_result = self.memory.search(low_threshold_query)
        
        # High threshold should return fewer results
        assert len(high_result.entries) <= len(low_result.entries)
    
    def test_search_with_temporal_filter(self):
        """Test search with temporal constraints."""
        # Create entries with specific timestamps
        past_time = datetime.now() - timedelta(hours=2)
        recent_time = datetime.now() - timedelta(minutes=30)
        
        past_entry = MemoryEntry(
            id="past_entry",
            agent_id="temporal_agent",
            memory_type=MemoryType.SHORT_TERM,
            content="Past temporal entry",
            metadata={},
            created_at=past_time
        )
        
        recent_entry = MemoryEntry(
            id="recent_entry",
            agent_id="temporal_agent",
            memory_type=MemoryType.SHORT_TERM,
            content="Recent temporal entry",
            metadata={},
            created_at=recent_time
        )
        
        self.memory.store(past_entry)
        self.memory.store(recent_entry)
        
        # Query for recent entries only
        query = MemoryQuery(
            query_text="temporal",
            temporal_filter={"after": datetime.now() - timedelta(hours=1)}
        )
        result = self.memory.search(query)
        
        # Should only return recent entry
        assert len(result.entries) == 1
        assert result.entries[0].id == "recent_entry"
    
    def test_search_limit(self):
        """Test search result limit."""
        query = MemoryQuery(
            query_text="the",  # Common word likely to match multiple entries
            limit=2
        )
        result = self.memory.search(query)
        
        # Should respect limit
        assert len(result.entries) <= 2
        assert len(result.scores) <= 2
    
    def test_search_marks_entries_accessed(self):
        """Test that search marks found entries as accessed."""
        # Get original access counts
        original_counts = {
            entry_id: entry.access_count 
            for entry_id, entry in self.memory._memories.items()
        }
        
        query = MemoryQuery(query_text="Python")
        result = self.memory.search(query)
        
        # Found entries should have increased access count
        for entry in result.entries:
            assert entry.access_count > original_counts[entry.id]
    
    def test_search_score_ordering(self):
        """Test that search results are ordered by score."""
        query = MemoryQuery(query_text="programming Python")
        result = self.memory.search(query)
        
        if len(result.scores) > 1:
            # Scores should be in descending order
            for i in range(len(result.scores) - 1):
                assert result.scores[i] >= result.scores[i + 1]
    
    def test_search_no_matches(self):
        """Test search with no matching results."""
        query = MemoryQuery(
            query_text="nonexistent_unique_term_xyz123",
            similarity_threshold=0.8
        )
        result = self.memory.search(query)
        
        assert len(result.entries) == 0
        assert len(result.scores) == 0
        assert result.total_found == 0


class TestShortTermMemoryRecentAccess:
    """Test recent memory access functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.memory = ShortTermMemory()
        
        # Create test memories in sequence
        for i in range(5):
            entry = MemoryEntry(
                id=f"recent_{i}",
                agent_id=f"agent_{i % 2}",
                memory_type=MemoryType.SHORT_TERM,
                content=f"Recent test content {i}",
                metadata={"sequence": i}
            )
            self.memory.store(entry)
            time.sleep(0.01)  # Small delay to ensure ordering
    
    def teardown_method(self):
        """Clean up test environment."""
        self.memory.shutdown()
    
    def test_get_recent_all_agents(self):
        """Test getting recent memories across all agents."""
        recent = self.memory.get_recent(limit=3)
        
        assert len(recent) == 3
        
        # Should be in reverse chronological order (most recent first)
        expected_order = ["recent_4", "recent_3", "recent_2"]
        actual_order = [entry.id for entry in recent]
        assert actual_order == expected_order
    
    def test_get_recent_specific_agent(self):
        """Test getting recent memories for specific agent."""
        recent = self.memory.get_recent(agent_id="agent_0", limit=3)
        
        # Should only contain memories from agent_0 (indices 0, 2, 4)
        assert all(entry.agent_id == "agent_0" for entry in recent)
        assert len(recent) <= 3
        
        # Should be in reverse order of creation
        expected_ids = ["recent_4", "recent_2", "recent_0"]
        actual_ids = [entry.id for entry in recent]
        assert actual_ids == expected_ids
    
    def test_get_recent_limit(self):
        """Test recent memory limit enforcement."""
        recent = self.memory.get_recent(limit=10)  # More than available
        
        # Should return all available (5 entries)
        assert len(recent) == 5
    
    def test_get_recent_empty_agent(self):
        """Test getting recent memories for non-existent agent."""
        recent = self.memory.get_recent(agent_id="nonexistent_agent")
        
        assert len(recent) == 0
        assert recent == []


class TestShortTermMemoryContext:
    """Test contextual memory access."""
    
    def setup_method(self):
        """Set up test environment."""
        self.memory = ShortTermMemory()
    
    def teardown_method(self):
        """Clean up test environment."""
        self.memory.shutdown()
    
    def test_get_context_basic(self):
        """Test basic context retrieval."""
        # Store context memories
        for i in range(3):
            entry = MemoryEntry(
                id=f"context_{i}",
                agent_id="context_agent",
                memory_type=MemoryType.SHORT_TERM,
                content=f"Context entry {i}",
                metadata={}
            )
            self.memory.store(entry)
        
        context = self.memory.get_context("context_agent", context_size=2)
        
        assert len(context) == 2
        # Should get most recent entries
        assert context[0].id == "context_2"
        assert context[1].id == "context_1"
    
    def test_get_context_delegates_to_get_recent(self):
        """Test that get_context delegates to get_recent correctly."""
        with patch.object(self.memory, 'get_recent') as mock_get_recent:
            mock_get_recent.return_value = []
            
            self.memory.get_context("test_agent", context_size=7)
            
            mock_get_recent.assert_called_once_with(agent_id="test_agent", limit=7)


class TestShortTermMemoryCleanup:
    """Test memory cleanup functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        # Use short retention for testing
        self.memory = ShortTermMemory(retention_hours=1, max_entries=10)
    
    def teardown_method(self):
        """Clean up test environment."""
        self.memory.shutdown()
    
    def test_clear_agent_memories(self):
        """Test clearing memories for specific agent."""
        # Store memories for multiple agents
        for agent_id in ["agent_1", "agent_2"]:
            for i in range(2):
                entry = MemoryEntry(
                    id=f"{agent_id}_memory_{i}",
                    agent_id=agent_id,
                    memory_type=MemoryType.SHORT_TERM,
                    content=f"Memory {i} for {agent_id}",
                    metadata={}
                )
                self.memory.store(entry)
        
        assert len(self.memory._memories) == 4
        assert "agent_1" in self.memory._agent_memories
        assert "agent_2" in self.memory._agent_memories
        
        # Clear agent_1 memories
        self.memory.clear_agent_memories("agent_1")
        
        # Should only have agent_2 memories left
        assert len(self.memory._memories) == 2
        assert "agent_1" not in self.memory._agent_memories
        assert "agent_2" in self.memory._agent_memories
        
        # Verify correct memories remain
        remaining_ids = set(self.memory._memories.keys())
        expected_ids = {"agent_2_memory_0", "agent_2_memory_1"}
        assert remaining_ids == expected_ids
    
    def test_clear_nonexistent_agent(self):
        """Test clearing memories for non-existent agent."""
        # Should not raise error
        self.memory.clear_agent_memories("nonexistent_agent")
        assert len(self.memory._memories) == 0
    
    def test_cleanup_old_memories_by_age(self):
        """Test cleanup of old memories by age."""
        # Create old memory
        old_time = datetime.now() - timedelta(hours=2)
        old_entry = MemoryEntry(
            id="old_entry",
            agent_id="test_agent",
            memory_type=MemoryType.SHORT_TERM,
            content="Old memory",
            metadata={},
            created_at=old_time,
            importance=0.5  # Low importance
        )
        
        # Create recent memory
        recent_entry = MemoryEntry(
            id="recent_entry",
            agent_id="test_agent",
            memory_type=MemoryType.SHORT_TERM,
            content="Recent memory",
            metadata={},
            importance=0.5
        )
        
        self.memory.store(old_entry)
        self.memory.store(recent_entry)
        
        # Manually trigger cleanup
        self.memory._cleanup_old_memories()
        
        # Old entry should be removed, recent should remain
        assert "old_entry" not in self.memory._memories
        assert "recent_entry" in self.memory._memories
    
    def test_cleanup_preserves_important_memories(self):
        """Test that cleanup preserves important old memories."""
        # Create old but important memory
        old_time = datetime.now() - timedelta(hours=2)
        important_entry = MemoryEntry(
            id="important_old",
            agent_id="test_agent",
            memory_type=MemoryType.SHORT_TERM,
            content="Important old memory",
            metadata={},
            created_at=old_time,
            importance=0.9  # High importance
        )
        
        self.memory.store(important_entry)
        
        # Manually trigger cleanup
        self.memory._cleanup_old_memories()
        
        # Important entry should be preserved despite age
        assert "important_old" in self.memory._memories


class TestShortTermMemoryStatistics:
    """Test memory statistics functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.memory = ShortTermMemory(max_entries=100, retention_hours=6)
    
    def teardown_method(self):
        """Clean up test environment."""
        self.memory.shutdown()
    
    def test_get_stats_empty(self):
        """Test statistics for empty memory."""
        stats = self.memory.get_stats()
        
        expected = {
            'total_memories': 0,
            'agents_with_memories': 0,
            'max_capacity': 100,
            'retention_hours': 6,
            'memory_types': {
                'short_term': 0,
                'episodic': 0,
                'semantic': 0,
                'procedural': 0,
                'emotional': 0
            }
        }
        
        assert stats == expected
    
    def test_get_stats_with_memories(self):
        """Test statistics with stored memories."""
        # Store diverse memories
        test_data = [
            ("mem_1", "agent_1", MemoryType.SHORT_TERM),
            ("mem_2", "agent_1", MemoryType.SEMANTIC),
            ("mem_3", "agent_2", MemoryType.SHORT_TERM),
            ("mem_4", "agent_2", MemoryType.EPISODIC),
            ("mem_5", "agent_3", MemoryType.PROCEDURAL),
        ]
        
        for mem_id, agent_id, memory_type in test_data:
            entry = MemoryEntry(
                id=mem_id,
                agent_id=agent_id,
                memory_type=memory_type,
                content=f"Content for {mem_id}",
                metadata={}
            )
            self.memory.store(entry)
        
        stats = self.memory.get_stats()
        
        assert stats['total_memories'] == 5
        assert stats['agents_with_memories'] == 3
        assert stats['max_capacity'] == 100
        assert stats['retention_hours'] == 6
        assert stats['memory_types'] == {
            'short_term': 2,
            'episodic': 1,
            'semantic': 1,
            'procedural': 1,
            'emotional': 0
        }


class TestShortTermMemoryThreadSafety:
    """Test thread safety of ShortTermMemory operations."""
    
    def setup_method(self):
        """Set up test environment."""
        self.memory = ShortTermMemory(max_entries=100)
    
    def teardown_method(self):
        """Clean up test environment."""
        self.memory.shutdown()
    
    def test_concurrent_store_and_retrieve(self):
        """Test concurrent store and retrieve operations."""
        results = {"stored": [], "retrieved": [], "errors": []}
        
        def store_worker(worker_id):
            try:
                for i in range(10):
                    entry = MemoryEntry(
                        id=f"concurrent_{worker_id}_{i}",
                        agent_id=f"worker_{worker_id}",
                        memory_type=MemoryType.SHORT_TERM,
                        content=f"Concurrent content {worker_id}_{i}",
                        metadata={"worker": worker_id, "index": i}
                    )
                    result = self.memory.store(entry)
                    results["stored"].append(result)
            except Exception as e:
                results["errors"].append(e)
        
        def retrieve_worker():
            try:
                time.sleep(0.1)  # Let some stores happen first
                for worker_id in range(3):
                    for i in range(5):  # Try to retrieve some entries
                        entry_id = f"concurrent_{worker_id}_{i}"
                        result = self.memory.retrieve(entry_id)
                        if result:
                            results["retrieved"].append(result.id)
            except Exception as e:
                results["errors"].append(e)
        
        # Start threads
        threads = []
        
        # Store threads
        for worker_id in range(3):
            thread = threading.Thread(target=store_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        # Retrieve threads
        for _ in range(2):
            thread = threading.Thread(target=retrieve_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        assert not results["errors"], f"Thread safety errors: {results['errors']}"
        
        # Verify operations succeeded
        assert len(results["stored"]) == 30  # 3 workers × 10 entries
        assert len(results["retrieved"]) > 0  # Some retrievals succeeded
    
    def test_concurrent_search_operations(self):
        """Test concurrent search operations."""
        # Pre-populate with searchable content
        for i in range(20):
            entry = MemoryEntry(
                id=f"search_prep_{i}",
                agent_id=f"agent_{i % 5}",
                memory_type=MemoryType.SHORT_TERM,
                content=f"Searchable content {i} with keywords python programming",
                metadata={"index": i}
            )
            self.memory.store(entry)
        
        results = {"searches": [], "errors": []}
        
        def search_worker(query_word):
            try:
                for _ in range(5):
                    query = MemoryQuery(query_text=query_word, limit=5)
                    result = self.memory.search(query)
                    results["searches"].append(len(result.entries))
                    time.sleep(0.01)
            except Exception as e:
                results["errors"].append(e)
        
        # Start search threads with different queries
        threads = []
        for query_word in ["python", "programming", "content", "keywords"]:
            thread = threading.Thread(target=search_worker, args=(query_word,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        assert not results["errors"], f"Search thread errors: {results['errors']}"
        
        # Verify searches returned results
        assert len(results["searches"]) == 20  # 4 threads × 5 searches
        assert all(count >= 0 for count in results["searches"])


class TestShortTermMemoryIntegration:
    """Test integration scenarios for ShortTermMemory."""
    
    def setup_method(self):
        """Set up test environment."""
        self.memory = ShortTermMemory(max_entries=50, retention_hours=2)
    
    def teardown_method(self):
        """Clean up test environment."""
        self.memory.shutdown()
    
    def test_full_memory_lifecycle(self):
        """Test complete memory lifecycle from store to cleanup."""
        # Store initial memories
        entries = []
        for i in range(5):
            entry = MemoryEntry(
                id=f"lifecycle_{i}",
                agent_id="lifecycle_agent",
                memory_type=MemoryType.SHORT_TERM,
                content=f"Lifecycle test content {i}",
                metadata={"phase": "initial"},
                importance=0.5
            )
            entries.append(entry)
            self.memory.store(entry)
        
        # Verify storage
        assert len(self.memory._memories) == 5
        
        # Search and retrieve
        query = MemoryQuery(query_text="lifecycle test")
        search_results = self.memory.search(query)
        assert len(search_results.entries) == 5
        
        # Access some memories
        for i in range(3):
            retrieved = self.memory.retrieve(f"lifecycle_{i}")
            assert retrieved is not None
            assert retrieved.access_count == 1
        
        # Get recent memories
        recent = self.memory.get_recent(agent_id="lifecycle_agent", limit=3)
        assert len(recent) == 3
        
        # Clear specific agent memories
        self.memory.clear_agent_memories("lifecycle_agent")
        assert len(self.memory._memories) == 0
    
    def test_memory_similarity_calculation(self):
        """Test internal similarity calculation accuracy."""
        # Test the internal similarity method
        test_cases = [
            ("hello world", "hello world", 1.0),  # Identical
            ("hello world", "world hello", 1.0),  # Same words, different order
            ("hello world", "hello", 0.5),  # Partial match
            ("hello world", "goodbye universe", 0.0),  # No match
            ("", "hello world", 0.0),  # Empty query
            ("hello world", "", 0.0),  # Empty content
        ]
        
        for query, content, expected_score in test_cases:
            actual_score = self.memory._calculate_similarity(query, content)
            assert actual_score == expected_score, f"Query: '{query}', Content: '{content}'"
    
    def test_temporal_filter_accuracy(self):
        """Test temporal filtering accuracy."""
        base_time = datetime.now()
        
        # Create memories with specific timestamps
        time_entries = [
            (base_time - timedelta(hours=3), "old_entry"),
            (base_time - timedelta(hours=1), "medium_entry"),
            (base_time - timedelta(minutes=30), "recent_entry"),
        ]
        
        memories = []
        for timestamp, entry_id in time_entries:
            entry = MemoryEntry(
                id=entry_id,
                agent_id="temporal_test",
                memory_type=MemoryType.SHORT_TERM,
                content=f"Content for {entry_id}",
                metadata={},
                created_at=timestamp
            )
            memories.append(entry)
        
        # Test after filter
        after_filter = {"after": base_time - timedelta(hours=2)}
        filtered = self.memory._apply_temporal_filter(memories, after_filter)
        assert len(filtered) == 2  # medium and recent
        
        # Test before filter
        before_filter = {"before": base_time - timedelta(hours=2)}
        filtered = self.memory._apply_temporal_filter(memories, before_filter)
        assert len(filtered) == 1  # only old
        
        # Test combined filter
        combined_filter = {
            "after": base_time - timedelta(hours=2),
            "before": base_time - timedelta(minutes=45)
        }
        filtered = self.memory._apply_temporal_filter(memories, combined_filter)
        assert len(filtered) == 1  # only medium