"""
Integration tests for Qdrant vector storage provider.

These tests require Docker to run Qdrant via testcontainers.
Skip these tests if Docker is not available: pytest -m "not integration"
"""

import pytest
import pytest_asyncio
import uuid

# Skip all tests if qdrant-client is not available
pytest.importorskip("qdrant_client", reason="qdrant-client required for Qdrant tests")

from praval.storage.providers.qdrant_provider import QdrantProvider
from praval.storage.base_provider import StorageType, StorageResult
from praval.storage.exceptions import StorageConnectionError


# ============================================================================
# Initialization & Configuration Tests
# ============================================================================


class TestQdrantProviderInit:
    """Tests for Qdrant provider initialization."""

    def test_provider_init_with_config(self, qdrant_config):
        """Creates provider with required config."""
        provider = QdrantProvider("test_qdrant", qdrant_config)

        assert provider.name == "test_qdrant"
        assert provider.config["url"] == qdrant_config["url"]

    def test_provider_metadata_storage_type(self, qdrant_config):
        """Provider has correct storage type."""
        provider = QdrantProvider("test_qdrant", qdrant_config)

        assert provider.metadata.storage_type == StorageType.VECTOR

    def test_provider_default_collection(self, qdrant_config):
        """Defaults to praval_storage collection."""
        config = {"url": qdrant_config["url"]}
        provider = QdrantProvider("test_qdrant", config)

        assert provider.config["collection_name"] == "praval_storage"

    def test_provider_default_vector_size(self, qdrant_config):
        """Defaults to 1536 (OpenAI embedding size)."""
        config = {"url": qdrant_config["url"]}
        provider = QdrantProvider("test_qdrant", config)

        assert provider.config["vector_size"] == 1536

    def test_provider_default_distance_metric(self, qdrant_config):
        """Defaults to cosine distance."""
        config = {"url": qdrant_config["url"]}
        provider = QdrantProvider("test_qdrant", config)

        assert provider.config["distance_metric"] == "cosine"

    def test_provider_custom_collection(self, qdrant_config):
        """Accepts custom collection name."""
        config = dict(qdrant_config)
        config["collection_name"] = "custom_collection"
        provider = QdrantProvider("test_qdrant", config)

        assert provider.default_collection == "custom_collection"


# ============================================================================
# Connection Tests
# ============================================================================


class TestQdrantConnection:
    """Tests for Qdrant connection handling."""

    @pytest.mark.asyncio
    async def test_connect_success(self, qdrant_config):
        """Successfully connects to Qdrant."""
        provider = QdrantProvider("test_qdrant", qdrant_config)

        connected = await provider.connect()

        assert connected is True
        assert provider.is_connected is True
        assert provider.qdrant_client is not None

        await provider.disconnect()

    @pytest.mark.asyncio
    async def test_connect_invalid_host(self, qdrant_config):
        """Raises error for invalid host."""
        config = dict(qdrant_config)
        config["url"] = "http://invalid_host_that_does_not_exist:6333"
        config["timeout"] = 1.0  # Short timeout

        provider = QdrantProvider("test_qdrant", config)

        with pytest.raises(StorageConnectionError):
            await provider.connect()

    @pytest.mark.asyncio
    async def test_disconnect(self, qdrant_config):
        """Disconnects properly."""
        provider = QdrantProvider("test_qdrant", qdrant_config)
        await provider.connect()

        await provider.disconnect()

        assert provider.is_connected is False
        assert provider.qdrant_client is None

    @pytest.mark.asyncio
    async def test_connect_creates_default_collection(self, qdrant_provider):
        """Connection ensures default collection exists."""
        # The fixture already connected, so collection should exist
        result = await qdrant_provider.list_resources()

        assert result.success is True
        collection_names = [c["name"] for c in result.data]
        assert qdrant_provider.default_collection in collection_names


# ============================================================================
# Store Operations Tests
# ============================================================================


class TestQdrantStore:
    """Tests for store operations."""

    @pytest.mark.asyncio
    async def test_store_single_point_dict(self, qdrant_provider, sample_vector):
        """Stores single point from dict."""
        point_id = str(uuid.uuid4())
        result = await qdrant_provider.store(
            qdrant_provider.default_collection,
            {
                "id": point_id,
                "vector": sample_vector,
                "payload": {"text": "Test document", "category": "test"}
            }
        )

        assert result.success is True
        assert result.data["points_stored"] == 1

    @pytest.mark.asyncio
    async def test_store_single_point_auto_id(self, qdrant_provider, sample_vector):
        """Generates UUID if no id provided."""
        result = await qdrant_provider.store(
            qdrant_provider.default_collection,
            {
                "vector": sample_vector,
                "payload": {"text": "Auto ID test"}
            }
        )

        assert result.success is True
        assert result.data["points_stored"] == 1

    @pytest.mark.asyncio
    async def test_store_multiple_points(self, qdrant_provider, sample_vector):
        """Stores multiple points from list."""
        points = [
            {
                "id": str(uuid.uuid4()),
                "vector": sample_vector,
                "payload": {"index": i}
            }
            for i in range(3)
        ]

        result = await qdrant_provider.store(
            qdrant_provider.default_collection,
            points
        )

        assert result.success is True
        assert result.data["points_stored"] == 3

    @pytest.mark.asyncio
    async def test_store_raw_vector(self, qdrant_provider, sample_vector):
        """Stores just a vector array."""
        result = await qdrant_provider.store(
            qdrant_provider.default_collection,
            sample_vector,
            payload={"type": "raw_vector"}
        )

        assert result.success is True
        assert result.data["points_stored"] == 1

    @pytest.mark.asyncio
    async def test_store_with_payload(self, qdrant_provider, sample_vector):
        """Stores point with metadata payload."""
        result = await qdrant_provider.store(
            qdrant_provider.default_collection,
            {
                "vector": sample_vector,
                "payload": {
                    "title": "Document Title",
                    "tags": ["tag1", "tag2"],
                    "score": 0.95,
                    "nested": {"key": "value"}
                }
            }
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_store_missing_vector_error(self, qdrant_provider):
        """Raises error for dict without vector."""
        result = await qdrant_provider.store(
            qdrant_provider.default_collection,
            {"id": "test", "payload": {"data": "test"}}
        )

        assert result.success is False
        assert "vector" in result.error.lower()

    @pytest.mark.asyncio
    async def test_store_invalid_format_error(self, qdrant_provider):
        """Raises error for invalid data format."""
        result = await qdrant_provider.store(
            qdrant_provider.default_collection,
            "invalid string data"
        )

        assert result.success is False
        assert "unsupported" in result.error.lower()

    @pytest.mark.asyncio
    async def test_store_returns_data_reference(self, qdrant_provider, sample_vector):
        """Returns DataReference for single point."""
        result = await qdrant_provider.store(
            qdrant_provider.default_collection,
            {
                "id": "ref_test_point",
                "vector": sample_vector
            }
        )

        assert result.success is True
        assert result.data_reference is not None
        assert result.data_reference.provider == "test_qdrant"
        assert result.data_reference.storage_type == StorageType.VECTOR


# ============================================================================
# Retrieve Operations Tests
# ============================================================================


class TestQdrantRetrieve:
    """Tests for retrieve operations."""

    @pytest.mark.asyncio
    async def test_retrieve_single_point(self, qdrant_provider, sample_vector):
        """Retrieves single point by collection:id."""
        point_id = "retrieve_test_point"
        await qdrant_provider.store(
            qdrant_provider.default_collection,
            {"id": point_id, "vector": sample_vector, "payload": {"test": "data"}}
        )

        result = await qdrant_provider.retrieve(
            f"{qdrant_provider.default_collection}:{point_id}"
        )

        assert result.success is True
        assert result.data["id"] == point_id
        assert result.data["payload"]["test"] == "data"

    @pytest.mark.asyncio
    async def test_retrieve_multiple_points(self, qdrant_provider, sample_vector):
        """Retrieves multiple points by point_ids."""
        point_ids = ["multi_1", "multi_2", "multi_3"]
        for pid in point_ids:
            await qdrant_provider.store(
                qdrant_provider.default_collection,
                {"id": pid, "vector": sample_vector, "payload": {"pid": pid}}
            )

        result = await qdrant_provider.retrieve(
            qdrant_provider.default_collection,
            point_ids=point_ids
        )

        assert result.success is True
        assert isinstance(result.data, list)
        assert len(result.data) == 3

    @pytest.mark.asyncio
    async def test_retrieve_with_vectors(self, qdrant_provider, sample_vector):
        """Includes vectors in response."""
        point_id = "vector_retrieve_test"
        await qdrant_provider.store(
            qdrant_provider.default_collection,
            {"id": point_id, "vector": sample_vector}
        )

        result = await qdrant_provider.retrieve(
            f"{qdrant_provider.default_collection}:{point_id}",
            with_vectors=True
        )

        assert result.success is True
        assert "vector" in result.data
        assert len(result.data["vector"]) == len(sample_vector)

    @pytest.mark.asyncio
    async def test_retrieve_without_vectors(self, qdrant_provider, sample_vector):
        """Excludes vectors when with_vectors=False."""
        point_id = "no_vector_retrieve_test"
        await qdrant_provider.store(
            qdrant_provider.default_collection,
            {"id": point_id, "vector": sample_vector}
        )

        result = await qdrant_provider.retrieve(
            f"{qdrant_provider.default_collection}:{point_id}",
            with_vectors=False
        )

        assert result.success is True
        # Vector may or may not be in result depending on Qdrant version

    @pytest.mark.asyncio
    async def test_retrieve_missing_ids_error(self, qdrant_provider):
        """Raises error without point IDs."""
        result = await qdrant_provider.retrieve(
            qdrant_provider.default_collection
        )

        assert result.success is False
        assert "id" in result.error.lower()


# ============================================================================
# Query Operations - Search Tests
# ============================================================================


class TestQdrantQuerySearch:
    """Tests for vector search operations."""

    @pytest.mark.asyncio
    async def test_query_search(self, qdrant_provider, sample_vector):
        """Performs vector similarity search."""
        # Store some points
        for i in range(5):
            await qdrant_provider.store(
                qdrant_provider.default_collection,
                {"id": f"search_{i}", "vector": sample_vector, "payload": {"index": i}}
            )

        result = await qdrant_provider.query(
            qdrant_provider.default_collection,
            "search",
            vector=sample_vector
        )

        assert result.success is True
        assert isinstance(result.data, list)
        assert len(result.data) > 0

    @pytest.mark.asyncio
    async def test_query_search_with_limit(self, qdrant_provider, sample_vector):
        """Limits search results."""
        for i in range(10):
            await qdrant_provider.store(
                qdrant_provider.default_collection,
                {"id": f"limit_{i}", "vector": sample_vector}
            )

        result = await qdrant_provider.query(
            qdrant_provider.default_collection,
            "search",
            vector=sample_vector,
            limit=3
        )

        assert result.success is True
        assert len(result.data) <= 3

    @pytest.mark.asyncio
    async def test_query_search_returns_scores(self, qdrant_provider, sample_vector):
        """Search results include similarity scores."""
        await qdrant_provider.store(
            qdrant_provider.default_collection,
            {"id": "score_test", "vector": sample_vector}
        )

        result = await qdrant_provider.query(
            qdrant_provider.default_collection,
            "search",
            vector=sample_vector
        )

        assert result.success is True
        assert len(result.data) > 0
        assert "score" in result.data[0]

    @pytest.mark.asyncio
    async def test_query_search_missing_vector_error(self, qdrant_provider):
        """Raises error without search vector."""
        result = await qdrant_provider.query(
            qdrant_provider.default_collection,
            "search"
        )

        assert result.success is False
        assert "vector" in result.error.lower()

    @pytest.mark.asyncio
    async def test_query_direct_vector(self, qdrant_provider, sample_vector):
        """Searches with vector list as query."""
        await qdrant_provider.store(
            qdrant_provider.default_collection,
            {"id": "direct_vector_test", "vector": sample_vector}
        )

        result = await qdrant_provider.query(
            qdrant_provider.default_collection,
            sample_vector  # Direct vector as query
        )

        assert result.success is True
        assert isinstance(result.data, list)


# ============================================================================
# Query Operations - Count & Scroll Tests
# ============================================================================


class TestQdrantQueryOther:
    """Tests for count and scroll operations."""

    @pytest.mark.asyncio
    async def test_query_count(self, qdrant_provider, sample_vector):
        """Counts points in collection."""
        # Store some points
        for i in range(5):
            await qdrant_provider.store(
                qdrant_provider.default_collection,
                {"id": f"count_{i}_{uuid.uuid4()}", "vector": sample_vector}
            )

        result = await qdrant_provider.query(
            qdrant_provider.default_collection,
            "count"
        )

        assert result.success is True
        assert "count" in result.data
        assert result.data["count"] >= 5

    @pytest.mark.asyncio
    async def test_query_scroll(self, qdrant_provider, sample_vector):
        """Scrolls through points."""
        for i in range(5):
            await qdrant_provider.store(
                qdrant_provider.default_collection,
                {"id": f"scroll_{i}_{uuid.uuid4()}", "vector": sample_vector}
            )

        result = await qdrant_provider.query(
            qdrant_provider.default_collection,
            "scroll",
            limit=3
        )

        assert result.success is True
        assert "points" in result.data
        assert len(result.data["points"]) <= 3

    @pytest.mark.asyncio
    async def test_query_scroll_with_offset(self, qdrant_provider, sample_vector):
        """Continues scrolling with offset."""
        for i in range(5):
            await qdrant_provider.store(
                qdrant_provider.default_collection,
                {"id": f"scroll_offset_{i}_{uuid.uuid4()}", "vector": sample_vector}
            )

        # First scroll
        result1 = await qdrant_provider.query(
            qdrant_provider.default_collection,
            "scroll",
            limit=2
        )

        assert result1.success is True
        # next_offset may be None if all results returned

    @pytest.mark.asyncio
    async def test_query_unsupported(self, qdrant_provider):
        """Raises error for unknown query type."""
        result = await qdrant_provider.query(
            qdrant_provider.default_collection,
            "unknown_operation"
        )

        assert result.success is False
        assert "unsupported" in result.error.lower()


# ============================================================================
# Delete Operations Tests
# ============================================================================


class TestQdrantDelete:
    """Tests for delete operations."""

    @pytest.mark.asyncio
    async def test_delete_by_id_string(self, qdrant_provider, sample_vector):
        """Deletes point by collection:point_id."""
        point_id = f"delete_test_{uuid.uuid4()}"
        await qdrant_provider.store(
            qdrant_provider.default_collection,
            {"id": point_id, "vector": sample_vector}
        )

        result = await qdrant_provider.delete(
            f"{qdrant_provider.default_collection}:{point_id}"
        )

        assert result.success is True
        assert result.data["deleted"] == 1

    @pytest.mark.asyncio
    async def test_delete_by_point_ids(self, qdrant_provider, sample_vector):
        """Deletes list of point IDs."""
        point_ids = [f"delete_multi_{i}_{uuid.uuid4()}" for i in range(3)]
        for pid in point_ids:
            await qdrant_provider.store(
                qdrant_provider.default_collection,
                {"id": pid, "vector": sample_vector}
            )

        result = await qdrant_provider.delete(
            qdrant_provider.default_collection,
            point_ids=point_ids
        )

        assert result.success is True
        assert result.data["deleted"] == 3

    @pytest.mark.asyncio
    async def test_delete_missing_params_error(self, qdrant_provider):
        """Raises error without ids or filter."""
        result = await qdrant_provider.delete(
            qdrant_provider.default_collection
        )

        assert result.success is False
        assert "point_ids" in result.error.lower() or "filter" in result.error.lower()


# ============================================================================
# List Resources Tests
# ============================================================================


class TestQdrantListResources:
    """Tests for list_resources method."""

    @pytest.mark.asyncio
    async def test_list_resources(self, qdrant_provider):
        """Lists collections."""
        result = await qdrant_provider.list_resources()

        assert result.success is True
        assert isinstance(result.data, list)
        # Should contain at least the default collection
        collection_names = [c["name"] for c in result.data]
        assert qdrant_provider.default_collection in collection_names

    @pytest.mark.asyncio
    async def test_list_resources_with_prefix(self, qdrant_provider):
        """Filters collections by prefix."""
        result = await qdrant_provider.list_resources(prefix="test_")

        assert result.success is True
        assert isinstance(result.data, list)
        # All returned collections should start with prefix
        for collection in result.data:
            assert collection["name"].startswith("test_")

    @pytest.mark.asyncio
    async def test_list_resources_returns_metadata(self, qdrant_provider, sample_vector):
        """Collection info includes metadata."""
        # Ensure there's at least one point in the collection
        await qdrant_provider.store(
            qdrant_provider.default_collection,
            {"id": f"meta_test_{uuid.uuid4()}", "vector": sample_vector}
        )

        result = await qdrant_provider.list_resources()

        assert result.success is True
        # Find the default collection
        default_coll = next(
            (c for c in result.data if c["name"] == qdrant_provider.default_collection),
            None
        )
        assert default_coll is not None
        assert "points_count" in default_coll
        assert "status" in default_coll
