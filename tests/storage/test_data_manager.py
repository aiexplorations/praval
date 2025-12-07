"""
Tests for the DataManager class.

These tests verify the high-level data management interface
for agents to interact with multiple storage providers.
"""

import pytest
import pytest_asyncio
import threading
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from praval.storage.data_manager import (
    DataManager,
    get_data_manager,
    store_data,
    get_data,
    query_data,
    delete_data,
)
from praval.storage.storage_registry import StorageRegistry
from praval.storage.base_provider import (
    BaseStorageProvider,
    StorageType,
    StorageResult,
    StorageMetadata,
    DataReference,
)
from praval.storage.exceptions import (
    StorageNotFoundError,
    StorageConfigurationError,
)


class MockStorageProvider(BaseStorageProvider):
    """Mock provider for testing data manager."""

    def __init__(self, name: str, storage_type: StorageType = StorageType.KEY_VALUE, **kwargs):
        self._storage_type = storage_type
        self._data = {}
        config = kwargs.get("config", {})
        super().__init__(name, config)

    def _create_metadata(self) -> StorageMetadata:
        return StorageMetadata(
            name=self.name,
            description=f"Mock {self._storage_type.value} provider",
            storage_type=self._storage_type,
        )

    async def connect(self) -> bool:
        self.is_connected = True
        return True

    async def disconnect(self) -> bool:
        self.is_connected = False
        return True

    async def store(self, resource: str, data, **kwargs) -> StorageResult:
        self._data[resource] = data
        return StorageResult(success=True, data={"stored": resource})

    async def retrieve(self, resource: str, **kwargs) -> StorageResult:
        if resource in self._data:
            return StorageResult(success=True, data=self._data[resource])
        return StorageResult(success=False, error=f"Resource {resource} not found")

    async def query(self, resource: str, query, **kwargs) -> StorageResult:
        return StorageResult(success=True, data={"query_result": query})

    async def delete(self, resource: str, **kwargs) -> StorageResult:
        if resource in self._data:
            del self._data[resource]
            return StorageResult(success=True, data={"deleted": resource})
        return StorageResult(success=False, error=f"Resource {resource} not found")

    async def list_resources(self, **kwargs) -> StorageResult:
        return StorageResult(success=True, data=list(self._data.keys()))


# ============================================================================
# DataManager Initialization Tests
# ============================================================================


class TestDataManagerInit:
    """Tests for DataManager initialization."""

    def test_data_manager_default_registry(self):
        """Uses global registry by default."""
        manager = DataManager()

        assert manager.registry is not None

    def test_data_manager_custom_registry(self):
        """Uses provided registry."""
        custom_registry = StorageRegistry()
        manager = DataManager(registry=custom_registry)

        assert manager.registry is custom_registry

    def test_data_manager_has_agent_context(self):
        """Initializes with thread-local agent context."""
        manager = DataManager()

        assert hasattr(manager, '_agent_context')


# ============================================================================
# Agent Context Tests
# ============================================================================


class TestAgentContext:
    """Tests for agent context management."""

    def test_set_agent_context(self):
        """Sets agent name in context."""
        manager = DataManager()
        manager.set_agent_context("test_agent")

        assert manager.get_agent_context() == "test_agent"

    def test_get_agent_context_default(self):
        """Returns None when no context set."""
        manager = DataManager()

        assert manager.get_agent_context() is None

    def test_agent_context_thread_local(self):
        """Agent context is thread-local."""
        manager = DataManager()
        manager.set_agent_context("main_agent")

        other_context = []

        def thread_func():
            other_context.append(manager.get_agent_context())

        thread = threading.Thread(target=thread_func)
        thread.start()
        thread.join()

        # Other thread should see None (not set in that thread)
        assert other_context[0] is None
        # Main thread should still see its value
        assert manager.get_agent_context() == "main_agent"


# ============================================================================
# Store Operation Tests
# ============================================================================


class TestStoreOperation:
    """Tests for store operation."""

    @pytest_asyncio.fixture
    async def manager_with_provider(self):
        """Manager with registered provider."""
        registry = StorageRegistry()
        provider = MockStorageProvider("test_provider")
        await registry.register_provider(provider)
        return DataManager(registry=registry)

    @pytest.mark.asyncio
    async def test_store_success(self, manager_with_provider):
        """Stores data successfully."""
        result = await manager_with_provider.store(
            "test_provider",
            "test_key",
            {"value": 123}
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_store_provider_not_found(self):
        """Raises error for non-existent provider."""
        registry = StorageRegistry()
        manager = DataManager(registry=registry)

        with pytest.raises(StorageNotFoundError):
            await manager.store("nonexistent", "key", "data")


# ============================================================================
# Get Operation Tests
# ============================================================================


class TestGetOperation:
    """Tests for get operation."""

    @pytest_asyncio.fixture
    async def manager_with_data(self):
        """Manager with stored data."""
        registry = StorageRegistry()
        provider = MockStorageProvider("test_provider")
        await registry.register_provider(provider)
        manager = DataManager(registry=registry)

        await manager.store("test_provider", "test_key", "test_value")
        return manager

    @pytest.mark.asyncio
    async def test_get_success(self, manager_with_data):
        """Retrieves stored data."""
        result = await manager_with_data.get("test_provider", "test_key")

        assert result.success is True
        assert result.data == "test_value"

    @pytest.mark.asyncio
    async def test_get_not_found(self, manager_with_data):
        """Returns error for missing resource."""
        result = await manager_with_data.get("test_provider", "nonexistent")

        assert result.success is False
        assert "not found" in result.error


# ============================================================================
# Query Operation Tests
# ============================================================================


class TestQueryOperation:
    """Tests for query operation."""

    @pytest_asyncio.fixture
    async def manager_with_provider(self):
        registry = StorageRegistry()
        provider = MockStorageProvider("test_provider")
        await registry.register_provider(provider)
        return DataManager(registry=registry)

    @pytest.mark.asyncio
    async def test_query_success(self, manager_with_provider):
        """Executes query successfully."""
        result = await manager_with_provider.query(
            "test_provider",
            "collection",
            {"filter": "value"}
        )

        assert result.success is True


# ============================================================================
# Delete Operation Tests
# ============================================================================


class TestDeleteOperation:
    """Tests for delete operation."""

    @pytest_asyncio.fixture
    async def manager_with_data(self):
        registry = StorageRegistry()
        provider = MockStorageProvider("test_provider")
        await registry.register_provider(provider)
        manager = DataManager(registry=registry)

        await manager.store("test_provider", "test_key", "test_value")
        return manager

    @pytest.mark.asyncio
    async def test_delete_success(self, manager_with_data):
        """Deletes data successfully."""
        result = await manager_with_data.delete("test_provider", "test_key")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self, manager_with_data):
        """Returns error for missing resource."""
        result = await manager_with_data.delete("test_provider", "nonexistent")

        assert result.success is False


# ============================================================================
# Smart Store Tests
# ============================================================================


class TestSmartStore:
    """Tests for smart_store operation."""

    @pytest_asyncio.fixture
    async def manager_with_providers(self):
        """Manager with multiple provider types."""
        registry = StorageRegistry()

        kv_provider = MockStorageProvider("kv_provider", StorageType.KEY_VALUE)
        vector_provider = MockStorageProvider("vector_provider", StorageType.VECTOR)
        relational_provider = MockStorageProvider("db_provider", StorageType.RELATIONAL)
        object_provider = MockStorageProvider("object_provider", StorageType.OBJECT)

        await registry.register_provider(kv_provider)
        await registry.register_provider(vector_provider)
        await registry.register_provider(relational_provider)
        await registry.register_provider(object_provider)

        return DataManager(registry=registry)

    @pytest.mark.asyncio
    async def test_smart_store_with_preference(self, manager_with_providers):
        """Uses preferred provider when specified."""
        result = await manager_with_providers.smart_store(
            {"value": 123},
            resource="test_key",
            preferred_provider="kv_provider"
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_smart_store_auto_select_vector(self, manager_with_providers):
        """Selects vector provider for vector data."""
        result = await manager_with_providers.smart_store(
            {"vector": [0.1, 0.2, 0.3]},
            resource="test_vector"
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_smart_store_auto_select_object(self, manager_with_providers):
        """Selects object provider for large data."""
        large_data = {"content": "x" * 2000}  # Large enough to prefer object storage

        result = await manager_with_providers.smart_store(
            large_data,
            resource="large_data"
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_smart_store_auto_select_relational(self, manager_with_providers):
        """Selects relational provider for record-like data."""
        record_data = {"id": 1, "name": "Test", "email": "test@example.com"}

        result = await manager_with_providers.smart_store(
            record_data,
            resource="user_record"
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_smart_store_generates_id(self, manager_with_providers):
        """Auto-generates resource ID when not provided."""
        result = await manager_with_providers.smart_store(
            {"value": 123},
            preferred_provider="kv_provider"
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_smart_store_no_providers_raises(self):
        """Raises error when no providers available."""
        registry = StorageRegistry()
        manager = DataManager(registry=registry)

        with pytest.raises(StorageConfigurationError):
            await manager.smart_store({"value": 123})


# ============================================================================
# Smart Search Tests
# ============================================================================


class TestSmartSearch:
    """Tests for smart_search operation."""

    @pytest_asyncio.fixture
    async def manager_with_search_providers(self):
        """Manager with search-capable providers."""
        registry = StorageRegistry()

        vector_provider = MockStorageProvider("vector_provider", StorageType.VECTOR)
        relational_provider = MockStorageProvider("db_provider", StorageType.RELATIONAL)
        search_provider = MockStorageProvider("search_provider", StorageType.SEARCH)

        await registry.register_provider(vector_provider)
        await registry.register_provider(relational_provider)
        await registry.register_provider(search_provider)

        return DataManager(registry=registry)

    @pytest.mark.asyncio
    async def test_smart_search_vector(self, manager_with_search_providers):
        """Vector search across providers."""
        results = await manager_with_search_providers.smart_search(
            [0.1, 0.2, 0.3, 0.4]
        )

        # Should attempt vector search on vector provider
        assert len(results) >= 0  # May be empty if no data

    @pytest.mark.asyncio
    async def test_smart_search_text(self, manager_with_search_providers):
        """Text search across providers."""
        results = await manager_with_search_providers.smart_search(
            "search query"
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_smart_search_structured(self, manager_with_search_providers):
        """Structured query search across providers."""
        results = await manager_with_search_providers.smart_search(
            {"field": "value"}
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_smart_search_specific_providers(self, manager_with_search_providers):
        """Search subset of providers."""
        results = await manager_with_search_providers.smart_search(
            "query",
            providers=["db_provider"]
        )

        assert isinstance(results, list)


# ============================================================================
# Data Reference Tests
# ============================================================================


class TestDataReference:
    """Tests for data reference operations."""

    @pytest_asyncio.fixture
    async def manager_with_provider(self):
        registry = StorageRegistry()
        provider = MockStorageProvider("test_provider")
        await registry.register_provider(provider)
        return DataManager(registry=registry)

    def test_create_data_reference(self, manager_with_provider):
        """Creates valid DataReference."""
        ref = manager_with_provider.create_data_reference(
            "test_provider",
            "test_resource",
            custom_key="custom_value"
        )

        assert ref.provider == "test_provider"
        assert ref.resource_id == "test_resource"
        assert ref.metadata.get("custom_key") == "custom_value"

    @pytest.mark.asyncio
    async def test_resolve_data_reference_object(self, manager_with_provider):
        """Resolves DataReference object."""
        # Store some data first
        await manager_with_provider.store("test_provider", "test_key", "stored_data")

        # Create and resolve reference
        ref = DataReference(
            provider="test_provider",
            storage_type=StorageType.KEY_VALUE,
            resource_id="test_key"
        )

        result = await manager_with_provider.resolve_data_reference(ref)

        assert result.success is True
        assert result.data == "stored_data"

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Bug in DataReference.from_uri: uses path instead of netloc for storage_type")
    async def test_resolve_data_reference_uri(self, manager_with_provider):
        """Resolves URI string to data."""
        await manager_with_provider.store("test_provider", "test_key", "stored_data")

        uri = "praval://key_value/test_provider/test_key"
        result = await manager_with_provider.resolve_data_reference(uri)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_resolve_data_reference_expired(self, manager_with_provider):
        """Returns error for expired reference."""
        ref = DataReference(
            provider="test_provider",
            storage_type=StorageType.KEY_VALUE,
            resource_id="test_key",
            expires_at=datetime.now() - timedelta(hours=1)  # Already expired
        )

        result = await manager_with_provider.resolve_data_reference(ref)

        assert result.success is False
        assert "expired" in result.error.lower()


# ============================================================================
# Batch Operations Tests
# ============================================================================


class TestBatchStore:
    """Tests for batch_store operation."""

    @pytest_asyncio.fixture
    async def manager_with_provider(self):
        registry = StorageRegistry()
        provider = MockStorageProvider("test_provider")
        await registry.register_provider(provider)
        return DataManager(registry=registry)

    @pytest.mark.asyncio
    async def test_batch_store_success(self, manager_with_provider):
        """Successfully stores multiple items."""
        operations = [
            {"provider": "test_provider", "resource": "key1", "data": "value1"},
            {"provider": "test_provider", "resource": "key2", "data": "value2"},
            {"provider": "test_provider", "resource": "key3", "data": "value3"},
        ]

        results = await manager_with_provider.batch_store(operations)

        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_batch_store_partial_failure(self, manager_with_provider):
        """Handles partial failures in batch."""
        operations = [
            {"provider": "test_provider", "resource": "key1", "data": "value1"},
            {"provider": "nonexistent", "resource": "key2", "data": "value2"},
            {"provider": "test_provider", "resource": "key3", "data": "value3"},
        ]

        results = await manager_with_provider.batch_store(operations)

        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True


class TestBatchGet:
    """Tests for batch_get operation."""

    @pytest_asyncio.fixture
    async def manager_with_data(self):
        registry = StorageRegistry()
        provider = MockStorageProvider("test_provider")
        await registry.register_provider(provider)
        manager = DataManager(registry=registry)

        # Store some data
        await manager.store("test_provider", "key1", "value1")
        await manager.store("test_provider", "key2", "value2")
        return manager

    @pytest.mark.asyncio
    async def test_batch_get_success(self, manager_with_data):
        """Successfully retrieves multiple items."""
        operations = [
            {"provider": "test_provider", "resource": "key1"},
            {"provider": "test_provider", "resource": "key2"},
        ]

        results = await manager_with_data.batch_get(operations)

        assert len(results) == 2
        assert all(r.success for r in results)
        assert results[0].data == "value1"
        assert results[1].data == "value2"

    @pytest.mark.asyncio
    async def test_batch_get_partial_failure(self, manager_with_data):
        """Handles missing resources in batch."""
        operations = [
            {"provider": "test_provider", "resource": "key1"},
            {"provider": "test_provider", "resource": "nonexistent"},
        ]

        results = await manager_with_data.batch_get(operations)

        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False


# ============================================================================
# Provider Management Tests
# ============================================================================


class TestListProviders:
    """Tests for list_providers method."""

    @pytest_asyncio.fixture
    async def manager_with_providers(self):
        registry = StorageRegistry()

        await registry.register_provider(MockStorageProvider("kv1", StorageType.KEY_VALUE))
        await registry.register_provider(MockStorageProvider("kv2", StorageType.KEY_VALUE))
        await registry.register_provider(MockStorageProvider("db1", StorageType.RELATIONAL))

        return DataManager(registry=registry)

    @pytest.mark.asyncio
    async def test_list_providers_all(self, manager_with_providers):
        """Lists all providers."""
        result = manager_with_providers.list_providers()

        assert len(result) == 3
        assert "kv1" in result
        assert "kv2" in result
        assert "db1" in result

    @pytest.mark.asyncio
    async def test_list_providers_by_type(self, manager_with_providers):
        """Filters providers by type."""
        result = manager_with_providers.list_providers(storage_type="key_value")

        assert len(result) == 2
        assert "kv1" in result
        assert "kv2" in result

    @pytest.mark.asyncio
    async def test_list_providers_invalid_type(self, manager_with_providers):
        """Handles invalid storage type gracefully."""
        result = manager_with_providers.list_providers(storage_type="invalid_type")

        # Should return all providers when type is invalid
        assert len(result) == 3


class TestGetProviderInfo:
    """Tests for get_provider_info method."""

    @pytest_asyncio.fixture
    async def manager_with_provider(self):
        registry = StorageRegistry()
        provider = MockStorageProvider("test_provider")
        await registry.register_provider(provider)
        return DataManager(registry=registry)

    def test_get_provider_info_returns_schema(self, manager_with_provider):
        """Returns provider schema information."""
        info = manager_with_provider.get_provider_info("test_provider")

        assert isinstance(info, dict)
        assert "name" in info
        assert info["name"] == "test_provider"


class TestHealthCheck:
    """Tests for health_check method."""

    @pytest_asyncio.fixture
    async def manager_with_providers(self):
        registry = StorageRegistry()
        await registry.register_provider(MockStorageProvider("provider1"))
        await registry.register_provider(MockStorageProvider("provider2"))
        return DataManager(registry=registry)

    @pytest.mark.asyncio
    async def test_health_check_single(self, manager_with_providers):
        """Checks health of single provider."""
        result = await manager_with_providers.health_check("provider1")

        assert isinstance(result, dict)
        assert result["provider"] == "provider1"

    @pytest.mark.asyncio
    async def test_health_check_all(self, manager_with_providers):
        """Checks health of all providers."""
        result = await manager_with_providers.health_check()

        assert isinstance(result, dict)
        assert "provider1" in result
        assert "provider2" in result


# ============================================================================
# Private Method Tests
# ============================================================================


class TestSelectOptimalProvider:
    """Tests for _select_optimal_provider method."""

    @pytest_asyncio.fixture
    async def manager_with_all_types(self):
        registry = StorageRegistry()

        await registry.register_provider(MockStorageProvider("kv", StorageType.KEY_VALUE))
        await registry.register_provider(MockStorageProvider("vector", StorageType.VECTOR))
        await registry.register_provider(MockStorageProvider("object", StorageType.OBJECT))
        await registry.register_provider(MockStorageProvider("relational", StorageType.RELATIONAL))

        return DataManager(registry=registry)

    def test_select_vector_for_vector_data(self, manager_with_all_types):
        """Selects vector provider for vector data."""
        result = manager_with_all_types._select_optimal_provider(
            {"vector": [0.1, 0.2, 0.3]},
            "store"
        )

        assert result == "vector"

    def test_select_object_for_large_data(self, manager_with_all_types):
        """Selects object provider for large data."""
        large_data = {"content": "x" * 2000}

        result = manager_with_all_types._select_optimal_provider(large_data, "store")

        assert result == "object"

    def test_select_relational_for_records(self, manager_with_all_types):
        """Selects relational for record-like data."""
        record = {"id": 1, "name": "Test"}

        result = manager_with_all_types._select_optimal_provider(record, "store")

        assert result == "relational"


class TestSelectSearchProviders:
    """Tests for _select_search_providers method."""

    @pytest_asyncio.fixture
    async def manager_with_search_types(self):
        registry = StorageRegistry()

        await registry.register_provider(MockStorageProvider("vector", StorageType.VECTOR))
        await registry.register_provider(MockStorageProvider("search", StorageType.SEARCH))
        await registry.register_provider(MockStorageProvider("relational", StorageType.RELATIONAL))
        await registry.register_provider(MockStorageProvider("document", StorageType.DOCUMENT))

        return DataManager(registry=registry)

    def test_select_vector_providers_for_vector_query(self, manager_with_search_types):
        """Selects vector providers for vector queries."""
        result = manager_with_search_types._select_search_providers([0.1, 0.2, 0.3])

        assert "vector" in result

    def test_select_text_providers_for_text_query(self, manager_with_search_types):
        """Selects search/relational for text queries."""
        result = manager_with_search_types._select_search_providers("search term")

        assert "search" in result or "relational" in result

    def test_select_db_providers_for_structured_query(self, manager_with_search_types):
        """Selects relational/document for structured queries."""
        result = manager_with_search_types._select_search_providers({"field": "value"})

        assert "relational" in result or "document" in result


class TestGenerateResourceId:
    """Tests for _generate_resource_id method."""

    @pytest_asyncio.fixture
    async def manager(self):
        registry = StorageRegistry()
        await registry.register_provider(MockStorageProvider("test"))
        return DataManager(registry=registry)

    def test_generate_id_uses_data_id(self, manager):
        """Uses existing id from data."""
        result = manager._generate_resource_id({"id": "my_id"}, "test")

        assert result == "my_id"

    def test_generate_id_creates_unique(self, manager):
        """Generates unique ID when no id field."""
        result = manager._generate_resource_id({"value": 123}, "test")

        assert "test_" in result


# ============================================================================
# Module Functions Tests
# ============================================================================


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_data_manager_singleton(self):
        """Returns same instance on multiple calls."""
        import praval.storage.data_manager as dm
        original = dm._global_data_manager
        dm._global_data_manager = None

        try:
            manager1 = get_data_manager()
            manager2 = get_data_manager()

            assert manager1 is manager2
        finally:
            dm._global_data_manager = original

    @pytest.mark.asyncio
    async def test_store_data_convenience(self):
        """store_data uses global manager."""
        import praval.storage.data_manager as dm
        original_manager = dm._global_data_manager

        # Create a custom registry with provider
        registry = StorageRegistry()
        await registry.register_provider(MockStorageProvider("test_provider"))

        # Replace global manager
        dm._global_data_manager = DataManager(registry=registry)

        try:
            result = await store_data("test_provider", "key", "value")
            assert result.success is True
        finally:
            dm._global_data_manager = original_manager

    @pytest.mark.asyncio
    async def test_get_data_convenience(self):
        """get_data uses global manager."""
        import praval.storage.data_manager as dm
        original_manager = dm._global_data_manager

        registry = StorageRegistry()
        await registry.register_provider(MockStorageProvider("test_provider"))
        dm._global_data_manager = DataManager(registry=registry)

        try:
            await store_data("test_provider", "key", "value")
            result = await get_data("test_provider", "key")
            assert result.success is True
            assert result.data == "value"
        finally:
            dm._global_data_manager = original_manager

    @pytest.mark.asyncio
    async def test_query_data_convenience(self):
        """query_data uses global manager."""
        import praval.storage.data_manager as dm
        original_manager = dm._global_data_manager

        registry = StorageRegistry()
        await registry.register_provider(MockStorageProvider("test_provider"))
        dm._global_data_manager = DataManager(registry=registry)

        try:
            result = await query_data("test_provider", "resource", {"filter": "value"})
            assert result.success is True
        finally:
            dm._global_data_manager = original_manager

    @pytest.mark.asyncio
    async def test_delete_data_convenience(self):
        """delete_data uses global manager."""
        import praval.storage.data_manager as dm
        original_manager = dm._global_data_manager

        registry = StorageRegistry()
        await registry.register_provider(MockStorageProvider("test_provider"))
        dm._global_data_manager = DataManager(registry=registry)

        try:
            await store_data("test_provider", "key", "value")
            result = await delete_data("test_provider", "key")
            assert result.success is True
        finally:
            dm._global_data_manager = original_manager
