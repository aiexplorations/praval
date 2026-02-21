"""
Tests for storage/memory_integration.py module.

Tests the MemoryStorageAdapter and UnifiedDataInterface classes that
bridge Praval's memory system with the unified storage interface.
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from praval.memory.memory_types import MemoryEntry, MemoryType
from praval.storage.base_provider import DataReference, StorageResult, StorageType
from praval.storage.memory_integration import MemoryStorageAdapter, UnifiedDataInterface


class TestMemoryStorageAdapter:
    """Tests for MemoryStorageAdapter class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_memory_manager = Mock()
        self.mock_memory_manager.short_term_memory = Mock()
        self.mock_memory_manager.long_term_memory = Mock()
        self.agent_id = "test_agent"
        self.adapter = MemoryStorageAdapter(self.mock_memory_manager, self.agent_id)

    def test_adapter_initialization(self):
        """Test adapter initializes with correct attributes."""
        assert self.adapter.memory_manager == self.mock_memory_manager
        assert self.adapter.agent_id == self.agent_id

    @pytest.mark.asyncio
    async def test_store_memory_short_term_success(self):
        """Test successful short-term memory storage."""
        self.mock_memory_manager.short_term_memory.store.return_value = True

        result = await self.adapter.store_memory_as_data(
            memory_type=MemoryType.SHORT_TERM,
            content="Test content",
            metadata={"key": "value"},
            importance=0.8,
        )

        assert result.success is True
        assert result.data["memory_type"] == "short_term"
        assert result.metadata["operation"] == "store_memory"
        assert result.metadata["agent_id"] == self.agent_id
        assert result.data_reference is not None
        assert result.data_reference.provider == "memory"

    @pytest.mark.asyncio
    async def test_store_memory_long_term_success(self):
        """Test successful long-term memory storage."""
        self.mock_memory_manager.store_memory = AsyncMock(return_value=True)

        result = await self.adapter.store_memory_as_data(
            memory_type=MemoryType.SEMANTIC, content="Semantic content", importance=0.9
        )

        assert result.success is True
        assert result.data["memory_type"] == "semantic"
        self.mock_memory_manager.store_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_memory_with_string_type(self):
        """Test storing memory with string type instead of enum."""
        self.mock_memory_manager.store_memory = AsyncMock(return_value=True)

        result = await self.adapter.store_memory_as_data(
            memory_type="episodic", content="Episodic content"
        )

        assert result.success is True
        assert result.data["memory_type"] == "episodic"

    @pytest.mark.asyncio
    async def test_store_memory_failure(self):
        """Test memory storage failure."""
        self.mock_memory_manager.short_term_memory.store.return_value = False

        result = await self.adapter.store_memory_as_data(
            memory_type=MemoryType.SHORT_TERM, content="Test content"
        )

        assert result.success is False
        assert result.error == "Failed to store memory"

    @pytest.mark.asyncio
    async def test_store_memory_exception(self):
        """Test memory storage with exception."""
        self.mock_memory_manager.short_term_memory.store.side_effect = Exception(
            "Storage error"
        )

        result = await self.adapter.store_memory_as_data(
            memory_type=MemoryType.SHORT_TERM, content="Test content"
        )

        assert result.success is False
        assert "Memory storage failed" in result.error

    @pytest.mark.asyncio
    async def test_retrieve_memory_from_short_term(self):
        """Test retrieving memory from short-term storage."""
        mock_entry = MemoryEntry(
            id="mem_123",
            agent_id=self.agent_id,
            memory_type=MemoryType.SHORT_TERM,
            content="Test content",
            metadata={"key": "value"},
            importance=0.7,
            created_at=datetime.now(),
            accessed_at=datetime.now(),
            access_count=1,
        )
        self.mock_memory_manager.short_term_memory.get.return_value = mock_entry

        result = await self.adapter.retrieve_memory_as_data("mem_123")

        assert result.success is True
        assert result.data["id"] == "mem_123"
        assert result.data["content"] == "Test content"
        assert result.data["memory_type"] == "short_term"
        assert result.data["importance"] == 0.7

    @pytest.mark.asyncio
    async def test_retrieve_memory_from_long_term(self):
        """Test retrieving memory from long-term storage when not in short-term."""
        mock_entry = MemoryEntry(
            id="mem_456",
            agent_id=self.agent_id,
            memory_type=MemoryType.SEMANTIC,
            content="Long term content",
            metadata={},
            importance=0.9,
            created_at=datetime.now(),
            accessed_at=datetime.now(),
        )
        self.mock_memory_manager.short_term_memory.get.return_value = None
        self.mock_memory_manager.long_term_memory.get_memory = AsyncMock(
            return_value=mock_entry
        )

        result = await self.adapter.retrieve_memory_as_data("mem_456")

        assert result.success is True
        assert result.data["id"] == "mem_456"
        assert result.data["memory_type"] == "semantic"

    @pytest.mark.asyncio
    async def test_retrieve_memory_with_embedding(self):
        """Test retrieving memory with embedding included."""
        mock_entry = MemoryEntry(
            id="mem_789",
            agent_id=self.agent_id,
            memory_type=MemoryType.SEMANTIC,
            content="Test content",
            metadata={},
            embedding=[0.1, 0.2, 0.3],
            created_at=datetime.now(),
            accessed_at=datetime.now(),
        )
        self.mock_memory_manager.short_term_memory.get.return_value = mock_entry

        result = await self.adapter.retrieve_memory_as_data(
            "mem_789", include_embedding=True
        )

        assert result.success is True
        assert result.data["embedding"] == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_retrieve_memory_not_found(self):
        """Test retrieving non-existent memory."""
        self.mock_memory_manager.short_term_memory.get.return_value = None
        self.mock_memory_manager.long_term_memory.get_memory = AsyncMock(
            return_value=None
        )

        result = await self.adapter.retrieve_memory_as_data("nonexistent")

        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_retrieve_memory_exception(self):
        """Test memory retrieval with exception."""
        self.mock_memory_manager.short_term_memory.get.side_effect = Exception(
            "Retrieval error"
        )

        result = await self.adapter.retrieve_memory_as_data("mem_123")

        assert result.success is False
        assert "Memory retrieval failed" in result.error

    @pytest.mark.asyncio
    @patch("praval.storage.memory_integration.MemoryQuery")
    async def test_search_memory_success(self, mock_query_class):
        """Test successful memory search."""
        # Create mock search result with proper interface
        mock_memory = MemoryEntry(
            id="mem_search_1",
            agent_id=self.agent_id,
            memory_type=MemoryType.SEMANTIC,
            content="Found content",
            metadata={"tag": "test"},
            importance=0.8,
            created_at=datetime.now(),
            accessed_at=datetime.now(),
        )

        # Create mock result object matching expected interface
        mock_result = Mock()
        mock_result.memory = mock_memory
        mock_result.similarity = 0.85

        self.mock_memory_manager.search_memories = AsyncMock(return_value=[mock_result])

        result = await self.adapter.search_memory_as_data(
            query="test query",
            memory_types=[MemoryType.SEMANTIC],
            limit=5,
            min_similarity=0.7,
        )

        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0]["id"] == "mem_search_1"
        assert result.data[0]["content"] == "Found content"
        assert result.data[0]["similarity"] == 0.85
        assert result.metadata["query"] == "test query"
        assert result.metadata["result_count"] == 1

    @pytest.mark.asyncio
    @patch("praval.storage.memory_integration.MemoryQuery")
    async def test_search_memory_no_results(self, mock_query_class):
        """Test memory search with no results."""
        self.mock_memory_manager.search_memories = AsyncMock(return_value=[])

        result = await self.adapter.search_memory_as_data("rare query")

        assert result.success is True
        assert result.data == []
        assert result.metadata["result_count"] == 0

    @pytest.mark.asyncio
    async def test_search_memory_exception(self):
        """Test memory search with exception."""
        self.mock_memory_manager.search_memories = AsyncMock(
            side_effect=Exception("Search error")
        )

        result = await self.adapter.search_memory_as_data("test query")

        assert result.success is False
        assert "Memory search failed" in result.error


class TestUnifiedDataInterface:
    """Tests for UnifiedDataInterface class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_memory_manager = Mock()
        self.mock_memory_manager.short_term_memory = Mock()
        self.mock_memory_manager.long_term_memory = Mock()
        self.mock_data_manager = AsyncMock()
        self.agent_id = "test_agent"

    def test_interface_initialization_full(self):
        """Test interface initialization with all components."""
        interface = UnifiedDataInterface(
            agent_id=self.agent_id,
            memory_manager=self.mock_memory_manager,
            data_manager=self.mock_data_manager,
        )

        assert interface.agent_id == self.agent_id
        assert interface.memory_manager == self.mock_memory_manager
        assert interface.data_manager == self.mock_data_manager
        assert interface.memory_adapter is not None

    def test_interface_initialization_memory_only(self):
        """Test interface initialization with memory only."""
        interface = UnifiedDataInterface(
            agent_id=self.agent_id, memory_manager=self.mock_memory_manager
        )

        assert interface.memory_adapter is not None
        assert interface.data_manager is None

    def test_interface_initialization_storage_only(self):
        """Test interface initialization with storage only."""
        interface = UnifiedDataInterface(
            agent_id=self.agent_id, data_manager=self.mock_data_manager
        )

        assert interface.memory_adapter is None
        assert interface.data_manager == self.mock_data_manager

    @pytest.mark.asyncio
    async def test_store_to_memory(self):
        """Test storing data to memory system."""
        self.mock_memory_manager.short_term_memory.store.return_value = True
        interface = UnifiedDataInterface(
            agent_id=self.agent_id, memory_manager=self.mock_memory_manager
        )

        result = await interface.store("memory:short_term", "Test data")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_store_to_memory_no_memory_system(self):
        """Test storing to memory when memory system not available."""
        interface = UnifiedDataInterface(
            agent_id=self.agent_id, data_manager=self.mock_data_manager
        )

        result = await interface.store("memory:short_term", "Test data")

        assert result.success is False
        assert "Memory system not available" in result.error

    @pytest.mark.asyncio
    async def test_store_to_external_storage(self):
        """Test storing data to external storage provider."""
        self.mock_data_manager.store = AsyncMock(
            return_value=StorageResult(success=True, data={"key": "value"})
        )
        interface = UnifiedDataInterface(
            agent_id=self.agent_id, data_manager=self.mock_data_manager
        )

        result = await interface.store("s3:bucket/file.txt", {"content": "data"})

        assert result.success is True
        self.mock_data_manager.store.assert_called_once_with(
            "s3", "bucket/file.txt", {"content": "data"}
        )

    @pytest.mark.asyncio
    async def test_store_to_external_storage_no_provider_specified(self):
        """Test smart storage when no provider in location."""
        self.mock_data_manager.smart_store = AsyncMock(
            return_value=StorageResult(success=True)
        )
        interface = UnifiedDataInterface(
            agent_id=self.agent_id, data_manager=self.mock_data_manager
        )

        result = await interface.store("config.json", {"setting": "value"})

        assert result.success is True
        self.mock_data_manager.smart_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_to_storage_no_storage_system(self):
        """Test storing when storage system not available."""
        interface = UnifiedDataInterface(
            agent_id=self.agent_id, memory_manager=self.mock_memory_manager
        )

        result = await interface.store("s3:bucket/file.txt", "data")

        assert result.success is False
        assert "Storage system not available" in result.error

    @pytest.mark.asyncio
    async def test_get_from_memory(self):
        """Test retrieving data from memory system."""
        mock_entry = MemoryEntry(
            id="mem_get_1",
            agent_id=self.agent_id,
            memory_type=MemoryType.SHORT_TERM,
            content="Retrieved content",
            metadata={},
            created_at=datetime.now(),
            accessed_at=datetime.now(),
        )
        self.mock_memory_manager.short_term_memory.get.return_value = mock_entry
        interface = UnifiedDataInterface(
            agent_id=self.agent_id, memory_manager=self.mock_memory_manager
        )

        result = await interface.get("memory:mem_get_1")

        assert result.success is True
        assert result.data["content"] == "Retrieved content"

    @pytest.mark.asyncio
    async def test_get_from_memory_no_memory_system(self):
        """Test getting from memory when not available."""
        interface = UnifiedDataInterface(
            agent_id=self.agent_id, data_manager=self.mock_data_manager
        )

        result = await interface.get("memory:some_id")

        assert result.success is False
        assert "Memory system not available" in result.error

    @pytest.mark.asyncio
    async def test_get_from_external_storage(self):
        """Test retrieving from external storage."""
        self.mock_data_manager.get = AsyncMock(
            return_value=StorageResult(success=True, data="file content")
        )
        interface = UnifiedDataInterface(
            agent_id=self.agent_id, data_manager=self.mock_data_manager
        )

        result = await interface.get("s3:bucket/file.txt")

        assert result.success is True
        self.mock_data_manager.get.assert_called_once_with("s3", "bucket/file.txt")

    @pytest.mark.asyncio
    async def test_get_from_storage_no_storage_system(self):
        """Test getting from storage when not available."""
        interface = UnifiedDataInterface(
            agent_id=self.agent_id, memory_manager=self.mock_memory_manager
        )

        result = await interface.get("s3:bucket/file.txt")

        assert result.success is False
        assert "Storage system not available" in result.error

    @pytest.mark.asyncio
    @patch("praval.storage.memory_integration.MemoryQuery")
    async def test_search_across_memory_and_storage(self, mock_query_class):
        """Test searching across both memory and storage."""
        # Set up memory search mock
        mock_memory = MemoryEntry(
            id="mem_1",
            agent_id=self.agent_id,
            memory_type=MemoryType.SEMANTIC,
            content="Memory result",
            metadata={},
            importance=0.8,
            created_at=datetime.now(),
            accessed_at=datetime.now(),
        )
        mock_result = Mock()
        mock_result.memory = mock_memory
        mock_result.similarity = 0.9

        self.mock_memory_manager.search_memories = AsyncMock(return_value=[mock_result])

        # Set up storage search mock
        storage_result = StorageResult(success=True, data=[{"file": "result.txt"}])
        self.mock_data_manager.smart_search = AsyncMock(return_value=[storage_result])

        interface = UnifiedDataInterface(
            agent_id=self.agent_id,
            memory_manager=self.mock_memory_manager,
            data_manager=self.mock_data_manager,
        )

        results = await interface.search("test query")

        assert len(results) >= 1  # Should have results from both
        self.mock_memory_manager.search_memories.assert_called()

    @pytest.mark.asyncio
    @patch("praval.storage.memory_integration.MemoryQuery")
    async def test_search_memory_only(self, mock_query_class):
        """Test searching only memory system."""
        mock_memory = MemoryEntry(
            id="mem_2",
            agent_id=self.agent_id,
            memory_type=MemoryType.SEMANTIC,
            content="Memory only result",
            metadata={},
            importance=0.7,
            created_at=datetime.now(),
            accessed_at=datetime.now(),
        )
        mock_result = Mock()
        mock_result.memory = mock_memory
        mock_result.similarity = 0.85

        self.mock_memory_manager.search_memories = AsyncMock(return_value=[mock_result])

        interface = UnifiedDataInterface(
            agent_id=self.agent_id, memory_manager=self.mock_memory_manager
        )

        results = await interface.search("test", locations=["memory:semantic"])

        assert len(results) == 1
        assert results[0].success is True

    @pytest.mark.asyncio
    async def test_search_storage_only_with_locations(self):
        """Test searching specific storage locations."""
        storage_result = StorageResult(success=True, data=[{"file": "data.json"}])
        self.mock_data_manager.smart_search = AsyncMock(return_value=[storage_result])

        interface = UnifiedDataInterface(
            agent_id=self.agent_id, data_manager=self.mock_data_manager
        )

        results = await interface.search("config", locations=["s3:configs"])

        assert len(results) == 1
        self.mock_data_manager.smart_search.assert_called()

    @pytest.mark.asyncio
    async def test_search_with_memory_error(self):
        """Test search continues when memory search fails."""
        self.mock_memory_manager.search_memories = AsyncMock(
            side_effect=Exception("Memory error")
        )
        storage_result = StorageResult(success=True, data=[])
        self.mock_data_manager.smart_search = AsyncMock(return_value=[storage_result])

        interface = UnifiedDataInterface(
            agent_id=self.agent_id,
            memory_manager=self.mock_memory_manager,
            data_manager=self.mock_data_manager,
        )

        results = await interface.search("test")

        # Should still return storage results despite memory error
        assert len(results) >= 1

    @pytest.mark.asyncio
    @patch("praval.storage.memory_integration.MemoryQuery")
    async def test_search_with_storage_error(self, mock_query_class):
        """Test search continues when storage search fails."""
        mock_memory = MemoryEntry(
            id="mem_err",
            agent_id=self.agent_id,
            memory_type=MemoryType.SEMANTIC,
            content="Result despite error",
            metadata={},
            created_at=datetime.now(),
            accessed_at=datetime.now(),
        )
        mock_result = Mock()
        mock_result.memory = mock_memory
        mock_result.similarity = 0.8

        self.mock_memory_manager.search_memories = AsyncMock(return_value=[mock_result])
        self.mock_data_manager.smart_search = AsyncMock(
            side_effect=Exception("Storage error")
        )

        interface = UnifiedDataInterface(
            agent_id=self.agent_id,
            memory_manager=self.mock_memory_manager,
            data_manager=self.mock_data_manager,
        )

        results = await interface.search("test")

        # Should still return memory results despite storage error
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_resolve_reference_memory_string(self):
        """Test resolving memory reference string."""
        mock_entry = MemoryEntry(
            id="ref_mem",
            agent_id=self.agent_id,
            memory_type=MemoryType.SHORT_TERM,
            content="Reference content",
            metadata={},
            created_at=datetime.now(),
            accessed_at=datetime.now(),
        )
        self.mock_memory_manager.short_term_memory.get.return_value = mock_entry

        interface = UnifiedDataInterface(
            agent_id=self.agent_id, memory_manager=self.mock_memory_manager
        )

        result = await interface.resolve_reference("memory:ref_mem")

        assert result.success is True
        assert result.data["id"] == "ref_mem"

    @pytest.mark.asyncio
    async def test_resolve_reference_external_string(self):
        """Test resolving external storage reference string."""
        self.mock_data_manager.resolve_data_reference = AsyncMock(
            return_value=StorageResult(success=True, data="resolved data")
        )

        interface = UnifiedDataInterface(
            agent_id=self.agent_id, data_manager=self.mock_data_manager
        )

        result = await interface.resolve_reference("s3://bucket/key")

        assert result.success is True
        self.mock_data_manager.resolve_data_reference.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_reference_data_reference_object(self):
        """Test resolving DataReference object."""
        data_ref = DataReference(
            provider="s3",
            storage_type=StorageType.OBJECT,
            resource_id="bucket/file.txt",
        )
        self.mock_data_manager.resolve_data_reference = AsyncMock(
            return_value=StorageResult(success=True, data="file contents")
        )

        interface = UnifiedDataInterface(
            agent_id=self.agent_id, data_manager=self.mock_data_manager
        )

        result = await interface.resolve_reference(data_ref)

        assert result.success is True
        self.mock_data_manager.resolve_data_reference.assert_called_once_with(data_ref)

    @pytest.mark.asyncio
    async def test_resolve_reference_no_storage_for_external(self):
        """Test resolving external reference without storage system."""
        interface = UnifiedDataInterface(
            agent_id=self.agent_id, memory_manager=self.mock_memory_manager
        )

        result = await interface.resolve_reference("s3://bucket/key")

        assert result.success is False
        assert "Storage system not available" in result.error

    @pytest.mark.asyncio
    async def test_resolve_reference_invalid_type(self):
        """Test resolving reference with invalid type."""
        interface = UnifiedDataInterface(
            agent_id=self.agent_id,
            memory_manager=self.mock_memory_manager,
            data_manager=self.mock_data_manager,
        )

        result = await interface.resolve_reference(12345)  # Invalid type

        assert result.success is False
        assert "Invalid reference type" in result.error


class TestMemoryStorageAdapterEdgeCases:
    """Edge case tests for MemoryStorageAdapter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_memory_manager = Mock()
        self.mock_memory_manager.short_term_memory = Mock()
        self.mock_memory_manager.long_term_memory = None  # No long-term memory
        self.adapter = MemoryStorageAdapter(self.mock_memory_manager, "edge_agent")

    @pytest.mark.asyncio
    async def test_retrieve_memory_no_long_term(self):
        """Test retrieval when long-term memory is not configured."""
        self.mock_memory_manager.short_term_memory.get.return_value = None

        result = await self.adapter.retrieve_memory_as_data("nonexistent")

        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_store_memory_default_metadata(self):
        """Test storing memory with default empty metadata."""
        self.mock_memory_manager.short_term_memory.store.return_value = True

        result = await self.adapter.store_memory_as_data(
            memory_type=MemoryType.SHORT_TERM,
            content="No metadata test",
            # metadata not provided - should default to {}
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_retrieve_memory_without_embedding(self):
        """Test retrieval without embedding when embedding exists."""
        mock_entry = MemoryEntry(
            id="embed_test",
            agent_id="edge_agent",
            memory_type=MemoryType.SEMANTIC,
            content="Has embedding",
            metadata={},
            embedding=[0.5, 0.5, 0.5],
            created_at=datetime.now(),
            accessed_at=datetime.now(),
        )
        self.mock_memory_manager.short_term_memory.get.return_value = mock_entry

        result = await self.adapter.retrieve_memory_as_data(
            "embed_test", include_embedding=False
        )

        assert result.success is True
        assert "embedding" not in result.data


class TestUnifiedDataInterfaceEdgeCases:
    """Edge case tests for UnifiedDataInterface."""

    @pytest.mark.asyncio
    @patch("praval.storage.memory_integration.MemoryQuery")
    async def test_search_no_specific_locations(self, mock_query_class):
        """Test search with no specific locations defaults to all."""
        mock_memory_manager = Mock()
        mock_memory_manager.short_term_memory = Mock()
        mock_memory_manager.long_term_memory = Mock()
        mock_memory_manager.search_memories = AsyncMock(return_value=[])

        mock_data_manager = AsyncMock()
        mock_data_manager.smart_search = AsyncMock(return_value=[])

        interface = UnifiedDataInterface(
            agent_id="test",
            memory_manager=mock_memory_manager,
            data_manager=mock_data_manager,
        )

        _ = await interface.search("query")

        # Both should be searched when no locations specified
        mock_memory_manager.search_memories.assert_called()
        mock_data_manager.smart_search.assert_called()

    @pytest.mark.asyncio
    async def test_store_memory_with_all_options(self):
        """Test store to memory with all optional parameters."""
        mock_memory_manager = Mock()
        mock_memory_manager.short_term_memory = Mock()
        mock_memory_manager.short_term_memory.store.return_value = True

        interface = UnifiedDataInterface(
            agent_id="full_test", memory_manager=mock_memory_manager
        )

        result = await interface.store(
            "memory:short_term",
            "Full options content",
            metadata={"custom": "metadata"},
            importance=0.95,
        )

        assert result.success is True
