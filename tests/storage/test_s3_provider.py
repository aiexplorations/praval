"""
Integration tests for S3 storage provider.

These tests use moto to mock AWS S3 - no Docker required.
"""

import pytest
import pytest_asyncio
import json

# Skip all tests if boto3/moto are not available
pytest.importorskip("boto3", reason="boto3 required for S3 tests")
pytest.importorskip("moto", reason="moto required for S3 tests")

from moto import mock_aws
import boto3

from praval.storage.providers.s3_provider import S3Provider
from praval.storage.base_provider import StorageType, StorageResult
from praval.storage.exceptions import StorageConnectionError


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_s3():
    """Create mocked S3 service."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="test-bucket")
        yield client


@pytest.fixture
def s3_config():
    """S3 provider configuration."""
    return {
        "bucket_name": "test-bucket",
        "region_name": "us-east-1",
    }


@pytest_asyncio.fixture
async def s3_provider(mock_s3, s3_config):
    """Create S3 provider with mocked backend."""
    provider = S3Provider("test_s3", s3_config)
    await provider.connect()
    yield provider
    await provider.disconnect()


# ============================================================================
# Initialization & Configuration Tests
# ============================================================================


class TestS3ProviderInit:
    """Tests for S3 provider initialization."""

    def test_provider_init_with_config(self, mock_s3, s3_config):
        """Creates provider with required config."""
        provider = S3Provider("test_s3", s3_config)

        assert provider.name == "test_s3"
        assert provider.bucket_name == "test-bucket"

    def test_provider_metadata_storage_type(self, mock_s3, s3_config):
        """Provider has correct storage type."""
        provider = S3Provider("test_s3", s3_config)

        assert provider.metadata.storage_type == StorageType.OBJECT

    def test_provider_default_region(self, mock_s3):
        """Defaults to us-east-1."""
        config = {"bucket_name": "test-bucket"}
        provider = S3Provider("test_s3", config)

        assert provider.config["region_name"] == "us-east-1"


# ============================================================================
# Connection Tests
# ============================================================================


class TestS3Connection:
    """Tests for S3 connection handling."""

    @pytest.mark.asyncio
    async def test_connect_success(self, mock_s3, s3_config):
        """Successfully connects to S3."""
        provider = S3Provider("test_s3", s3_config)

        connected = await provider.connect()

        assert connected is True
        assert provider.is_connected is True
        assert provider.s3_client is not None

        await provider.disconnect()

    @pytest.mark.asyncio
    async def test_connect_bucket_not_found(self, mock_s3):
        """Raises error for non-existent bucket without create_bucket."""
        config = {"bucket_name": "nonexistent-bucket-" + str(id(TestS3Connection))}

        provider = S3Provider("test_s3", config)

        with pytest.raises(StorageConnectionError):
            await provider.connect()

    @pytest.mark.asyncio
    async def test_connect_creates_bucket(self, mock_s3):
        """Creates bucket when create_bucket=True."""
        config = {
            "bucket_name": "new-bucket-" + str(id(TestS3Connection)),
            "create_bucket": True
        }

        provider = S3Provider("test_s3", config)
        await provider.connect()

        assert provider.is_connected is True
        await provider.disconnect()

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_s3, s3_config):
        """Disconnects properly."""
        provider = S3Provider("test_s3", s3_config)
        await provider.connect()

        await provider.disconnect()

        assert provider.is_connected is False
        assert provider.s3_client is None


# ============================================================================
# Store Operations Tests
# ============================================================================


class TestS3Store:
    """Tests for store operations."""

    @pytest.mark.asyncio
    async def test_store_dict(self, s3_provider):
        """Stores dict as JSON."""
        result = await s3_provider.store(
            "test_object.json",
            {"key": "value", "number": 123}
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_store_list(self, s3_provider):
        """Stores list as JSON."""
        result = await s3_provider.store(
            "test_list.json",
            [1, 2, 3, "test"]
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_store_string(self, s3_provider):
        """Stores string as text."""
        result = await s3_provider.store(
            "test_string.txt",
            "Hello, World!"
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_store_bytes(self, s3_provider):
        """Stores binary data."""
        result = await s3_provider.store(
            "test_binary.bin",
            b"binary data here"
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_store_with_metadata(self, s3_provider):
        """Stores with custom metadata."""
        result = await s3_provider.store(
            "test_with_meta.json",
            {"data": "test"},
            metadata={"custom-key": "custom-value"}
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_store_returns_etag(self, s3_provider):
        """Returns ETag in result."""
        result = await s3_provider.store(
            "etag_test.txt",
            "test content"
        )

        assert result.success is True
        # ETag should be in metadata
        assert "etag" in result.metadata or result.data_reference is not None


# ============================================================================
# Retrieve Operations Tests
# ============================================================================


class TestS3Retrieve:
    """Tests for retrieve operations."""

    @pytest.mark.asyncio
    async def test_retrieve_json(self, s3_provider):
        """Retrieves and decodes JSON."""
        await s3_provider.store("retrieve_json.json", {"test": "value"})

        result = await s3_provider.retrieve("retrieve_json.json")

        assert result.success is True
        assert result.data == {"test": "value"}

    @pytest.mark.asyncio
    async def test_retrieve_text(self, s3_provider):
        """Retrieves text content."""
        await s3_provider.store("retrieve_text.txt", "Hello S3")

        result = await s3_provider.retrieve("retrieve_text.txt")

        assert result.success is True
        assert result.data == "Hello S3"

    @pytest.mark.asyncio
    async def test_retrieve_binary(self, s3_provider):
        """Retrieves binary content."""
        await s3_provider.store("retrieve_binary.bin", b"\x00\x01\x02")

        result = await s3_provider.retrieve("retrieve_binary.bin", decode=False)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_retrieve_not_found(self, s3_provider):
        """Returns error for non-existent key."""
        result = await s3_provider.retrieve("nonexistent_key_" + str(id(self)))

        assert result.success is False
        assert "not found" in result.error.lower() or "nosuchkey" in result.error.lower()

    @pytest.mark.asyncio
    async def test_retrieve_includes_metadata(self, s3_provider):
        """Returns object metadata."""
        await s3_provider.store("meta_test.txt", "data")

        result = await s3_provider.retrieve("meta_test.txt")

        assert result.success is True
        assert result.metadata is not None


# ============================================================================
# Query Operations Tests
# ============================================================================


class TestS3Query:
    """Tests for query operations."""

    @pytest.mark.asyncio
    async def test_query_list(self, s3_provider):
        """Lists objects with prefix."""
        await s3_provider.store("list/obj1.txt", "1")
        await s3_provider.store("list/obj2.txt", "2")
        await s3_provider.store("other/obj3.txt", "3")

        result = await s3_provider.query("list/", "list")

        assert result.success is True
        # Should find objects in list/ prefix
        assert isinstance(result.data, (list, dict))

    @pytest.mark.asyncio
    async def test_query_list_empty(self, s3_provider):
        """Returns empty list for prefix with no objects."""
        result = await s3_provider.query("nonexistent_prefix_/", "list")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_query_metadata(self, s3_provider):
        """Gets object metadata (HEAD)."""
        await s3_provider.store("head_test.txt", "content")

        result = await s3_provider.query("head_test.txt", "metadata")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_query_exists_true(self, s3_provider):
        """Checks object existence - true."""
        await s3_provider.store("exists_test.txt", "data")

        result = await s3_provider.query("exists_test.txt", "exists")

        assert result.success is True
        assert result.data.get("exists") is True

    @pytest.mark.asyncio
    async def test_query_exists_false(self, s3_provider):
        """Checks object existence - false."""
        result = await s3_provider.query("not_exists_" + str(id(self)), "exists")

        assert result.success is True
        assert result.data.get("exists") is False


# ============================================================================
# Delete Operations Tests
# ============================================================================


class TestS3Delete:
    """Tests for delete operations."""

    @pytest.mark.asyncio
    async def test_delete_single(self, s3_provider):
        """Deletes single object."""
        await s3_provider.store("delete_me.txt", "data")

        result = await s3_provider.delete("delete_me.txt")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_delete_recursive(self, s3_provider):
        """Deletes all objects with prefix."""
        await s3_provider.store("delete_prefix/obj1.txt", "1")
        await s3_provider.store("delete_prefix/obj2.txt", "2")

        result = await s3_provider.delete("delete_prefix/", recursive=True)

        assert result.success is True


# ============================================================================
# List Resources Tests
# ============================================================================


class TestS3ListResources:
    """Tests for list_resources method."""

    @pytest.mark.asyncio
    async def test_list_resources(self, s3_provider):
        """Lists objects via query."""
        await s3_provider.store("listres/a.txt", "a")
        await s3_provider.store("listres/b.txt", "b")

        result = await s3_provider.query("listres/", "list")

        assert result.success is True
