"""
Comprehensive tests for Praval memory types and data structures.

This module ensures all memory data structures are bulletproof and handle
all edge cases correctly. Tests are strict and verify both functionality
and error conditions.
"""

import pytest
from datetime import datetime, timedelta
from typing import List, Dict, Any
import uuid

from praval.memory.memory_types import (
    MemoryType, MemoryEntry, MemoryQuery, MemorySearchResult
)


class TestMemoryType:
    """Test the MemoryType enum with comprehensive coverage."""
    
    def test_memory_type_values(self):
        """Test that all memory types have correct string values."""
        assert MemoryType.SHORT_TERM.value == "short_term"
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.SEMANTIC.value == "semantic"
        assert MemoryType.PROCEDURAL.value == "procedural"
        assert MemoryType.EMOTIONAL.value == "emotional"
    
    def test_memory_type_enumeration(self):
        """Test enumeration of all memory types."""
        all_types = list(MemoryType)
        expected = [
            MemoryType.SHORT_TERM,
            MemoryType.EPISODIC,
            MemoryType.SEMANTIC,
            MemoryType.PROCEDURAL,
            MemoryType.EMOTIONAL
        ]
        assert all_types == expected
    
    def test_memory_type_from_string(self):
        """Test creating memory types from string values."""
        assert MemoryType("short_term") == MemoryType.SHORT_TERM
        assert MemoryType("episodic") == MemoryType.EPISODIC
        assert MemoryType("semantic") == MemoryType.SEMANTIC
        assert MemoryType("procedural") == MemoryType.PROCEDURAL
        assert MemoryType("emotional") == MemoryType.EMOTIONAL
    
    def test_memory_type_invalid_string(self):
        """Test that invalid string raises ValueError."""
        with pytest.raises(ValueError, match="'invalid_type' is not a valid MemoryType"):
            MemoryType("invalid_type")


class TestMemoryEntry:
    """Test the MemoryEntry dataclass with comprehensive coverage."""
    
    def test_memory_entry_basic_creation(self):
        """Test basic memory entry creation with required fields."""
        entry = MemoryEntry(
            id="test_id",
            agent_id="test_agent",
            memory_type=MemoryType.SEMANTIC,
            content="Test memory content",
            metadata={"source": "test"}
        )
        
        assert entry.id == "test_id"
        assert entry.agent_id == "test_agent"
        assert entry.memory_type == MemoryType.SEMANTIC
        assert entry.content == "Test memory content"
        assert entry.metadata == {"source": "test"}
        assert entry.embedding is None
        assert entry.access_count == 0
        assert entry.importance == 0.5
    
    def test_memory_entry_auto_id_generation(self):
        """Test automatic ID generation when None provided."""
        entry = MemoryEntry(
            id=None,
            agent_id="test_agent",
            memory_type=MemoryType.SHORT_TERM,
            content="Auto ID test",
            metadata={}
        )
        
        # Should generate a valid UUID
        assert entry.id is not None
        assert isinstance(entry.id, str)
        # Should be valid UUID format
        uuid.UUID(entry.id)  # Will raise ValueError if invalid
    
    def test_memory_entry_auto_timestamps(self):
        """Test automatic timestamp generation."""
        before_creation = datetime.now()
        
        entry = MemoryEntry(
            id="timestamp_test",
            agent_id="test_agent",
            memory_type=MemoryType.EPISODIC,
            content="Timestamp test",
            metadata={},
            created_at=None,
            accessed_at=None
        )
        
        after_creation = datetime.now()
        
        # Timestamps should be auto-generated
        assert entry.created_at is not None
        assert entry.accessed_at is not None
        
        # Should be recent
        assert before_creation <= entry.created_at <= after_creation
        assert entry.accessed_at == entry.created_at  # Initially same
    
    def test_memory_entry_explicit_timestamps(self):
        """Test memory entry with explicit timestamps."""
        created_time = datetime(2023, 1, 1, 12, 0, 0)
        accessed_time = datetime(2023, 1, 2, 12, 0, 0)
        
        entry = MemoryEntry(
            id="explicit_time",
            agent_id="test_agent",
            memory_type=MemoryType.PROCEDURAL,
            content="Explicit timestamps",
            metadata={},
            created_at=created_time,
            accessed_at=accessed_time
        )
        
        assert entry.created_at == created_time
        assert entry.accessed_at == accessed_time
    
    def test_memory_entry_with_embedding(self):
        """Test memory entry with embedding vector."""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        entry = MemoryEntry(
            id="embedding_test",
            agent_id="test_agent",
            memory_type=MemoryType.SEMANTIC,
            content="Content with embedding",
            metadata={},
            embedding=embedding
        )
        
        assert entry.embedding == embedding
        assert len(entry.embedding) == 5
    
    def test_memory_entry_custom_importance(self):
        """Test memory entry with custom importance level."""
        entry = MemoryEntry(
            id="importance_test",
            agent_id="test_agent",
            memory_type=MemoryType.EMOTIONAL,
            content="Important memory",
            metadata={},
            importance=0.9
        )
        
        assert entry.importance == 0.9
    
    def test_memory_entry_custom_access_count(self):
        """Test memory entry with custom access count."""
        entry = MemoryEntry(
            id="access_test",
            agent_id="test_agent",
            memory_type=MemoryType.SHORT_TERM,
            content="Accessed memory",
            metadata={},
            access_count=5
        )
        
        assert entry.access_count == 5
    
    def test_memory_entry_mark_accessed(self):
        """Test marking memory entry as accessed."""
        entry = MemoryEntry(
            id="access_mark_test",
            agent_id="test_agent",
            memory_type=MemoryType.EPISODIC,
            content="Mark accessed test",
            metadata={},
            access_count=2
        )
        
        original_accessed_at = entry.accessed_at
        
        # Small delay to ensure timestamp difference
        import time
        time.sleep(0.01)
        
        # Mark as accessed
        entry.mark_accessed()
        
        assert entry.access_count == 3
        assert entry.accessed_at > original_accessed_at
    
    def test_memory_entry_mark_accessed_multiple_times(self):
        """Test marking memory entry as accessed multiple times."""
        entry = MemoryEntry(
            id="multi_access_test",
            agent_id="test_agent",
            memory_type=MemoryType.SEMANTIC,
            content="Multiple access test",
            metadata={},
            access_count=0
        )
        
        # Mark accessed 3 times
        for i in range(3):
            entry.mark_accessed()
        
        assert entry.access_count == 3
    
    def test_memory_entry_to_dict(self):
        """Test converting memory entry to dictionary."""
        created_time = datetime(2023, 6, 15, 14, 30, 0)
        accessed_time = datetime(2023, 6, 16, 10, 15, 0)
        embedding = [0.1, 0.2, 0.3]
        
        entry = MemoryEntry(
            id="dict_test",
            agent_id="dict_agent",
            memory_type=MemoryType.PROCEDURAL,
            content="Dictionary test content",
            metadata={"key": "value", "number": 42},
            embedding=embedding,
            created_at=created_time,
            accessed_at=accessed_time,
            access_count=7,
            importance=0.8
        )
        
        result_dict = entry.to_dict()
        
        expected = {
            'id': "dict_test",
            'agent_id': "dict_agent",
            'memory_type': "procedural",
            'content': "Dictionary test content",
            'metadata': {"key": "value", "number": 42},
            'embedding': [0.1, 0.2, 0.3],
            'created_at': "2023-06-15T14:30:00",
            'accessed_at': "2023-06-16T10:15:00",
            'access_count': 7,
            'importance': 0.8
        }
        
        assert result_dict == expected
    
    def test_memory_entry_to_dict_none_embedding(self):
        """Test converting memory entry with None embedding to dictionary."""
        entry = MemoryEntry(
            id="none_embedding_test",
            agent_id="test_agent",
            memory_type=MemoryType.SHORT_TERM,
            content="No embedding",
            metadata={},
            embedding=None
        )
        
        result_dict = entry.to_dict()
        assert result_dict['embedding'] is None
    
    def test_memory_entry_from_dict_complete(self):
        """Test creating memory entry from complete dictionary."""
        data = {
            'id': "from_dict_test",
            'agent_id': "from_dict_agent",
            'memory_type': "emotional",
            'content': "From dictionary content",
            'metadata': {"emotion": "happy", "intensity": 0.7},
            'embedding': [0.4, 0.5, 0.6],
            'created_at': "2023-07-20T09:00:00",
            'accessed_at': "2023-07-21T15:30:00",
            'access_count': 3,
            'importance': 0.75
        }
        
        entry = MemoryEntry.from_dict(data)
        
        assert entry.id == "from_dict_test"
        assert entry.agent_id == "from_dict_agent"
        assert entry.memory_type == MemoryType.EMOTIONAL
        assert entry.content == "From dictionary content"
        assert entry.metadata == {"emotion": "happy", "intensity": 0.7}
        assert entry.embedding == [0.4, 0.5, 0.6]
        assert entry.created_at == datetime(2023, 7, 20, 9, 0, 0)
        assert entry.accessed_at == datetime(2023, 7, 21, 15, 30, 0)
        assert entry.access_count == 3
        assert entry.importance == 0.75
    
    def test_memory_entry_from_dict_minimal(self):
        """Test creating memory entry from minimal dictionary."""
        data = {
            'id': "minimal_test",
            'agent_id': "minimal_agent",
            'memory_type': "semantic",
            'content': "Minimal content",
            'metadata': {},
            'created_at': "2023-08-01T12:00:00",
            'accessed_at': "2023-08-01T12:00:00"
        }
        
        entry = MemoryEntry.from_dict(data)
        
        assert entry.id == "minimal_test"
        assert entry.agent_id == "minimal_agent"
        assert entry.memory_type == MemoryType.SEMANTIC
        assert entry.content == "Minimal content"
        assert entry.metadata == {}
        assert entry.embedding is None
        assert entry.access_count == 0  # Default value
        assert entry.importance == 0.5  # Default value
    
    def test_memory_entry_roundtrip_conversion(self):
        """Test that to_dict -> from_dict preserves all data."""
        original = MemoryEntry(
            id="roundtrip_test",
            agent_id="roundtrip_agent",
            memory_type=MemoryType.EPISODIC,
            content="Roundtrip test content",
            metadata={"test": True, "value": 123},
            embedding=[0.7, 0.8, 0.9],
            created_at=datetime(2023, 9, 1, 8, 0, 0),
            accessed_at=datetime(2023, 9, 2, 16, 30, 0),
            access_count=5,
            importance=0.95
        )
        
        # Convert to dict and back
        dict_data = original.to_dict()
        reconstructed = MemoryEntry.from_dict(dict_data)
        
        # Should be identical
        assert reconstructed.id == original.id
        assert reconstructed.agent_id == original.agent_id
        assert reconstructed.memory_type == original.memory_type
        assert reconstructed.content == original.content
        assert reconstructed.metadata == original.metadata
        assert reconstructed.embedding == original.embedding
        assert reconstructed.created_at == original.created_at
        assert reconstructed.accessed_at == original.accessed_at
        assert reconstructed.access_count == original.access_count
        assert reconstructed.importance == original.importance


class TestMemoryQuery:
    """Test the MemoryQuery dataclass with comprehensive coverage."""
    
    def test_memory_query_basic_creation(self):
        """Test basic memory query creation."""
        query = MemoryQuery(
            query_text="test query"
        )
        
        assert query.query_text == "test query"
        assert query.memory_types == list(MemoryType)  # All types by default
        assert query.agent_id is None
        assert query.limit == 10
        assert query.similarity_threshold == 0.7
        assert query.include_metadata is True
        assert query.temporal_filter is None
    
    def test_memory_query_with_specific_types(self):
        """Test memory query with specific memory types."""
        query = MemoryQuery(
            query_text="semantic search",
            memory_types=[MemoryType.SEMANTIC, MemoryType.PROCEDURAL]
        )
        
        assert query.memory_types == [MemoryType.SEMANTIC, MemoryType.PROCEDURAL]
    
    def test_memory_query_with_agent_filter(self):
        """Test memory query with agent ID filter."""
        query = MemoryQuery(
            query_text="agent specific query",
            agent_id="specific_agent"
        )
        
        assert query.agent_id == "specific_agent"
    
    def test_memory_query_with_custom_parameters(self):
        """Test memory query with custom parameters."""
        query = MemoryQuery(
            query_text="custom query",
            memory_types=[MemoryType.EPISODIC],
            agent_id="custom_agent",
            limit=5,
            similarity_threshold=0.8,
            include_metadata=False
        )
        
        assert query.query_text == "custom query"
        assert query.memory_types == [MemoryType.EPISODIC]
        assert query.agent_id == "custom_agent"
        assert query.limit == 5
        assert query.similarity_threshold == 0.8
        assert query.include_metadata is False
    
    def test_memory_query_with_temporal_filter(self):
        """Test memory query with temporal filter."""
        after_date = datetime(2023, 1, 1)
        before_date = datetime(2023, 12, 31)
        
        query = MemoryQuery(
            query_text="temporal query",
            temporal_filter={"after": after_date, "before": before_date}
        )
        
        assert query.temporal_filter == {"after": after_date, "before": before_date}
    
    def test_memory_query_empty_memory_types_becomes_all(self):
        """Test that empty memory_types list becomes all types."""
        query = MemoryQuery(
            query_text="all types query",
            memory_types=None
        )
        
        # Should be all memory types
        assert query.memory_types == list(MemoryType)
        assert len(query.memory_types) == 5
    
    def test_memory_query_single_memory_type(self):
        """Test memory query with single memory type."""
        query = MemoryQuery(
            query_text="single type query",
            memory_types=[MemoryType.SHORT_TERM]
        )
        
        assert query.memory_types == [MemoryType.SHORT_TERM]
        assert len(query.memory_types) == 1


class TestMemorySearchResult:
    """Test the MemorySearchResult dataclass with comprehensive coverage."""
    
    def create_sample_entries(self) -> List[MemoryEntry]:
        """Create sample memory entries for testing."""
        return [
            MemoryEntry(
                id=f"entry_{i}",
                agent_id="test_agent",
                memory_type=MemoryType.SEMANTIC,
                content=f"Test content {i}",
                metadata={"index": i},
                importance=0.5 + (i * 0.1)
            )
            for i in range(5)
        ]
    
    def test_memory_search_result_basic_creation(self):
        """Test basic memory search result creation."""
        entries = self.create_sample_entries()[:3]
        scores = [0.9, 0.8, 0.7]
        query = MemoryQuery(query_text="test query")
        
        result = MemorySearchResult(
            entries=entries,
            scores=scores,
            query=query,
            total_found=10
        )
        
        assert result.entries == entries
        assert result.scores == scores
        assert result.query == query
        assert result.total_found == 10
        assert len(result.entries) == 3
        assert len(result.scores) == 3
    
    def test_memory_search_result_empty(self):
        """Test memory search result with no results."""
        query = MemoryQuery(query_text="no results query")
        
        result = MemorySearchResult(
            entries=[],
            scores=[],
            query=query,
            total_found=0
        )
        
        assert result.entries == []
        assert result.scores == []
        assert result.total_found == 0
    
    def test_memory_search_result_get_best_match_with_results(self):
        """Test getting best match when results exist."""
        entries = self.create_sample_entries()[:3]
        scores = [0.95, 0.85, 0.75]
        query = MemoryQuery(query_text="best match query")
        
        result = MemorySearchResult(
            entries=entries,
            scores=scores,
            query=query,
            total_found=3
        )
        
        best_match = result.get_best_match()
        assert best_match == entries[0]  # First entry should be best
        assert best_match.id == "entry_0"
    
    def test_memory_search_result_get_best_match_no_results(self):
        """Test getting best match when no results exist."""
        query = MemoryQuery(query_text="no results query")
        
        result = MemorySearchResult(
            entries=[],
            scores=[],
            query=query,
            total_found=0
        )
        
        best_match = result.get_best_match()
        assert best_match is None
    
    def test_memory_search_result_get_above_threshold_default(self):
        """Test getting entries above default threshold (0.8)."""
        entries = self.create_sample_entries()
        scores = [0.95, 0.85, 0.75, 0.65, 0.55]
        query = MemoryQuery(query_text="threshold query")
        
        result = MemorySearchResult(
            entries=entries,
            scores=scores,
            query=query,
            total_found=5
        )
        
        above_threshold = result.get_above_threshold()
        
        # Should return entries with scores >= 0.8 (first 2)
        assert len(above_threshold) == 2
        assert above_threshold[0] == entries[0]  # Score 0.95
        assert above_threshold[1] == entries[1]  # Score 0.85
    
    def test_memory_search_result_get_above_threshold_custom(self):
        """Test getting entries above custom threshold."""
        entries = self.create_sample_entries()
        scores = [0.95, 0.85, 0.75, 0.65, 0.55]
        query = MemoryQuery(query_text="custom threshold query")
        
        result = MemorySearchResult(
            entries=entries,
            scores=scores,
            query=query,
            total_found=5
        )
        
        above_threshold = result.get_above_threshold(threshold=0.7)
        
        # Should return entries with scores >= 0.7 (first 3)
        assert len(above_threshold) == 3
        assert above_threshold[0] == entries[0]  # Score 0.95
        assert above_threshold[1] == entries[1]  # Score 0.85
        assert above_threshold[2] == entries[2]  # Score 0.75
    
    def test_memory_search_result_get_above_threshold_high_threshold(self):
        """Test getting entries above very high threshold."""
        entries = self.create_sample_entries()
        scores = [0.95, 0.85, 0.75, 0.65, 0.55]
        query = MemoryQuery(query_text="high threshold query")
        
        result = MemorySearchResult(
            entries=entries,
            scores=scores,
            query=query,
            total_found=5
        )
        
        above_threshold = result.get_above_threshold(threshold=0.99)
        
        # No entries should match
        assert len(above_threshold) == 0
        assert above_threshold == []
    
    def test_memory_search_result_get_above_threshold_exact_match(self):
        """Test getting entries with exact threshold match."""
        entries = self.create_sample_entries()[:2]
        scores = [0.8, 0.8]  # Both exactly at threshold
        query = MemoryQuery(query_text="exact threshold query")
        
        result = MemorySearchResult(
            entries=entries,
            scores=scores,
            query=query,
            total_found=2
        )
        
        above_threshold = result.get_above_threshold(threshold=0.8)
        
        # Both entries should match (>= threshold)
        assert len(above_threshold) == 2
        assert above_threshold == entries
    
    def test_memory_search_result_entries_scores_mismatch_length(self):
        """Test behavior when entries and scores have different lengths."""
        entries = self.create_sample_entries()[:3]
        scores = [0.9, 0.8]  # Only 2 scores for 3 entries
        query = MemoryQuery(query_text="mismatch query")
        
        result = MemorySearchResult(
            entries=entries,
            scores=scores,
            query=query,
            total_found=3
        )
        
        # get_above_threshold should handle mismatch gracefully
        # zip() will stop at shorter length
        above_threshold = result.get_above_threshold(threshold=0.7)
        
        # Should only process first 2 entries (matching scores length)
        assert len(above_threshold) == 2
        assert above_threshold[0] == entries[0]
        assert above_threshold[1] == entries[1]


class TestIntegrationScenarios:
    """Test integration scenarios between memory data structures."""
    
    def test_memory_entry_in_search_result_workflow(self):
        """Test complete workflow from entry creation to search result."""
        # Create entries
        entries = [
            MemoryEntry(
                id=f"workflow_{i}",
                agent_id="workflow_agent",
                memory_type=MemoryType.SEMANTIC,
                content=f"Workflow content {i}",
                metadata={"workflow_step": i},
                importance=0.6 + (i * 0.1)
            )
            for i in range(3)
        ]
        
        # Mark some as accessed
        entries[0].mark_accessed()
        entries[1].mark_accessed()
        entries[1].mark_accessed()  # Access twice
        
        # Create query
        query = MemoryQuery(
            query_text="workflow search",
            memory_types=[MemoryType.SEMANTIC],
            agent_id="workflow_agent",
            limit=5
        )
        
        # Create search result
        scores = [0.9, 0.85, 0.8]
        result = MemorySearchResult(
            entries=entries,
            scores=scores,
            query=query,
            total_found=3
        )
        
        # Verify workflow
        best_match = result.get_best_match()
        assert best_match.id == "workflow_0"
        assert best_match.access_count == 1
        
        high_quality = result.get_above_threshold(0.8)
        assert len(high_quality) == 3  # All entries
        
        # Verify access counts are preserved
        assert entries[0].access_count == 1
        assert entries[1].access_count == 2
        assert entries[2].access_count == 0
    
    def test_memory_entry_serialization_in_search_context(self):
        """Test serialization of memory entries within search context."""
        # Create entry with complex metadata
        entry = MemoryEntry(
            id="serial_test",
            agent_id="serial_agent",
            memory_type=MemoryType.EPISODIC,
            content="Serialization test content",
            metadata={
                "conversation_id": "conv_123",
                "participants": ["user", "agent"],
                "context_length": 1500,
                "emotions": {"confidence": 0.8, "helpfulness": 0.9}
            },
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
            importance=0.85
        )
        
        # Convert to dict and back
        entry_dict = entry.to_dict()
        reconstructed = MemoryEntry.from_dict(entry_dict)
        
        # Create search result with both
        query = MemoryQuery(query_text="serialization test")
        result = MemorySearchResult(
            entries=[entry, reconstructed],
            scores=[0.95, 0.95],
            query=query,
            total_found=2
        )
        
        # Both entries should be identical
        original_dict = result.entries[0].to_dict()
        reconstructed_dict = result.entries[1].to_dict()
        assert original_dict == reconstructed_dict
    
    def test_memory_query_with_all_memory_types(self):
        """Test memory query behavior with all memory types."""
        # Create entries of different types
        entries = [
            MemoryEntry(
                id=f"type_test_{memory_type.value}",
                agent_id="type_agent",
                memory_type=memory_type,
                content=f"Content for {memory_type.value}",
                metadata={"type": memory_type.value}
            )
            for memory_type in MemoryType
        ]
        
        # Query for all types
        query = MemoryQuery(
            query_text="all types test",
            memory_types=list(MemoryType)
        )
        
        # Create result with all entries
        scores = [0.9, 0.8, 0.7, 0.6, 0.5]
        result = MemorySearchResult(
            entries=entries,
            scores=scores,
            query=query,
            total_found=len(entries)
        )
        
        # Should find all types
        assert len(result.entries) == 5
        memory_types_found = {entry.memory_type for entry in result.entries}
        assert memory_types_found == set(MemoryType)
    
    def test_temporal_query_integration(self):
        """Test memory query with temporal filtering integration."""
        base_time = datetime(2023, 6, 1, 12, 0, 0)
        
        # Create entries with different timestamps
        entries = []
        for i in range(3):
            entry_time = base_time + timedelta(days=i)
            entries.append(
                MemoryEntry(
                    id=f"temporal_{i}",
                    agent_id="temporal_agent",
                    memory_type=MemoryType.EPISODIC,
                    content=f"Temporal content {i}",
                    metadata={"day": i},
                    created_at=entry_time,
                    accessed_at=entry_time
                )
            )
        
        # Create temporal query
        filter_after = base_time + timedelta(hours=12)  # After first entry
        filter_before = base_time + timedelta(days=2, hours=12)  # Before last entry
        
        query = MemoryQuery(
            query_text="temporal filter test",
            temporal_filter={"after": filter_after, "before": filter_before}
        )
        
        # Create result (simulating filtered results)
        # In real implementation, only middle entry would match
        matching_entries = [entries[1]]  # Only second entry in time range
        result = MemorySearchResult(
            entries=matching_entries,
            scores=[0.85],
            query=query,
            total_found=1
        )
        
        # Verify temporal filtering context
        assert len(result.entries) == 1
        assert result.entries[0].id == "temporal_1"
        assert result.query.temporal_filter["after"] == filter_after
        assert result.query.temporal_filter["before"] == filter_before