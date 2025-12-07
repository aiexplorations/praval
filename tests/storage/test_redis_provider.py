"""
Integration tests for Redis storage provider.

These tests require Docker to run Redis via testcontainers.
Skip these tests if Docker is not available: pytest -m "not integration"
"""

import pytest
import pytest_asyncio

# Skip all tests if redis is not available
pytest.importorskip("redis", reason="redis required for Redis tests")

from praval.storage.providers.redis_provider import RedisProvider
from praval.storage.base_provider import StorageType, StorageResult
from praval.storage.exceptions import StorageConnectionError


# ============================================================================
# Initialization & Configuration Tests
# ============================================================================


class TestRedisProviderInit:
    """Tests for Redis provider initialization."""

    def test_provider_init_with_config(self, redis_config):
        """Creates provider with required config."""
        provider = RedisProvider("test_redis", redis_config)

        assert provider.name == "test_redis"
        assert provider.config["host"] == redis_config["host"]

    def test_provider_metadata_storage_type(self, redis_config):
        """Provider has correct storage type."""
        provider = RedisProvider("test_redis", redis_config)

        assert provider.metadata.storage_type == StorageType.KEY_VALUE

    def test_provider_default_port(self, redis_config):
        """Defaults to port 6379."""
        config = {"host": redis_config["host"]}
        provider = RedisProvider("test_redis", config)

        assert provider.config["port"] == 6379

    def test_provider_default_database(self, redis_config):
        """Defaults to database 0."""
        config = {"host": redis_config["host"]}
        provider = RedisProvider("test_redis", config)

        assert provider.config["database"] == 0

    def test_provider_build_connection_kwargs(self, redis_config):
        """Builds correct connection parameters."""
        provider = RedisProvider("test_redis", redis_config)

        kwargs = provider._connection_kwargs
        assert kwargs["host"] == redis_config["host"]
        assert kwargs["db"] == redis_config.get("database", 0)


# ============================================================================
# Connection Tests
# ============================================================================


class TestRedisConnection:
    """Tests for Redis connection handling."""

    @pytest.mark.asyncio
    async def test_connect_success(self, redis_config):
        """Successfully connects to Redis."""
        provider = RedisProvider("test_redis", redis_config)

        connected = await provider.connect()

        assert connected is True
        assert provider.is_connected is True
        assert provider.redis_client is not None

        await provider.disconnect()

    @pytest.mark.asyncio
    async def test_connect_invalid_host(self, redis_config):
        """Raises error for invalid host."""
        config = dict(redis_config)
        config["host"] = "invalid_host_that_does_not_exist"

        provider = RedisProvider("test_redis", config)

        with pytest.raises(StorageConnectionError):
            await provider.connect()

    @pytest.mark.asyncio
    async def test_disconnect(self, redis_config):
        """Disconnects properly."""
        provider = RedisProvider("test_redis", redis_config)
        await provider.connect()

        await provider.disconnect()

        assert provider.is_connected is False
        assert provider.redis_client is None


# ============================================================================
# Store Operations Tests
# ============================================================================


class TestRedisStore:
    """Tests for store operations."""

    @pytest.mark.asyncio
    async def test_store_dict(self, redis_provider):
        """Stores dict with JSON serialization."""
        result = await redis_provider.store(
            "test_key",
            {"name": "Test", "value": 123}
        )

        assert result.success is True
        assert result.data.get("stored") is True

    @pytest.mark.asyncio
    async def test_store_list(self, redis_provider):
        """Stores list with JSON serialization."""
        result = await redis_provider.store(
            "test_list_key",
            [1, 2, 3, "test"]
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_store_string(self, redis_provider):
        """Stores string value."""
        result = await redis_provider.store("string_key", "simple string")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_store_with_expiry_seconds(self, redis_provider):
        """Stores with expiration in seconds."""
        result = await redis_provider.store(
            "expiring_key",
            "expiring data",
            ex=3600
        )

        assert result.success is True
        assert result.metadata.get("ttl") is not None

    @pytest.mark.asyncio
    async def test_store_nx_success(self, redis_provider):
        """Stores only if key doesn't exist (NX flag)."""
        # First store should succeed
        result = await redis_provider.store("nx_key", "first", nx=True)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_store_nx_failure(self, redis_provider):
        """Fails to store when key exists with NX flag."""
        await redis_provider.store("existing_nx_key", "first")

        result = await redis_provider.store("existing_nx_key", "second", nx=True)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_store_xx_success(self, redis_provider):
        """Stores only if key exists (XX flag)."""
        await redis_provider.store("xx_key", "first")

        result = await redis_provider.store("xx_key", "updated", xx=True)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_store_returns_data_reference(self, redis_provider):
        """Returns DataReference with TTL info."""
        result = await redis_provider.store("ref_key", "data", ex=60)

        assert result.data_reference is not None
        assert result.data_reference.provider == "test_redis"


# ============================================================================
# Retrieve Operations Tests
# ============================================================================


class TestRedisRetrieve:
    """Tests for retrieve operations."""

    @pytest.mark.asyncio
    async def test_retrieve_json(self, redis_provider):
        """Retrieves and decodes JSON."""
        await redis_provider.store("json_key", {"key": "value"})

        result = await redis_provider.retrieve("json_key")

        assert result.success is True
        assert result.data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_retrieve_string(self, redis_provider):
        """Retrieves string value."""
        await redis_provider.store("plain_string", "hello")

        result = await redis_provider.retrieve("plain_string", decode_json=False)

        assert result.success is True
        assert result.data == "hello"

    @pytest.mark.asyncio
    async def test_retrieve_not_found(self, redis_provider):
        """Returns error for missing key."""
        result = await redis_provider.retrieve("nonexistent_key_" + str(id(self)))

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_retrieve_no_decode(self, redis_provider):
        """Returns raw string with decode_json=False."""
        await redis_provider.store("raw_json", {"a": 1})

        result = await redis_provider.retrieve("raw_json", decode_json=False)

        assert result.success is True
        assert isinstance(result.data, str)

    @pytest.mark.asyncio
    async def test_retrieve_includes_ttl(self, redis_provider):
        """Metadata includes TTL information."""
        await redis_provider.store("ttl_key", "data", ex=300)

        result = await redis_provider.retrieve("ttl_key")

        assert result.success is True
        assert "ttl" in result.metadata


# ============================================================================
# Query Operations - Keys Tests
# ============================================================================


class TestRedisQueryKeys:
    """Tests for key-related query operations."""

    @pytest.mark.asyncio
    async def test_query_keys_pattern(self, redis_provider):
        """Finds keys matching pattern."""
        await redis_provider.store("prefix_a", "1")
        await redis_provider.store("prefix_b", "2")
        await redis_provider.store("other_c", "3")

        result = await redis_provider.query("prefix_*", "keys")

        assert result.success is True
        assert any("prefix_" in k for k in result.data)

    @pytest.mark.asyncio
    async def test_query_scan(self, redis_provider):
        """Cursor-based scanning."""
        await redis_provider.store("scan_1", "1")
        await redis_provider.store("scan_2", "2")

        result = await redis_provider.query("scan_*", "scan", count=10)

        assert result.success is True
        assert "cursor" in result.data
        assert "keys" in result.data

    @pytest.mark.asyncio
    async def test_query_exists_single(self, redis_provider):
        """Checks if key exists."""
        await redis_provider.store("exists_key", "value")

        result = await redis_provider.query("exists_key", "exists")

        assert result.success is True
        assert result.data["exists_count"] >= 1

    @pytest.mark.asyncio
    async def test_query_exists_multiple(self, redis_provider):
        """Checks existence of multiple keys."""
        await redis_provider.store("exists_multi_1", "1")
        await redis_provider.store("exists_multi_2", "2")

        result = await redis_provider.query(
            "",
            "exists",
            keys=["exists_multi_1", "exists_multi_2"]
        )

        assert result.success is True
        assert result.data["exists_count"] >= 2


# ============================================================================
# Query Operations - Hashes Tests
# ============================================================================


class TestRedisQueryHashes:
    """Tests for hash query operations."""

    @pytest.mark.asyncio
    async def test_query_hgetall(self, redis_provider):
        """Gets all hash fields."""
        # Set up hash directly
        await redis_provider.redis_client.hset("test_hash", mapping={"f1": "v1", "f2": "v2"})

        result = await redis_provider.query("test_hash", "hgetall")

        assert result.success is True
        assert "f1" in result.data
        assert result.data["f1"] == "v1"

    @pytest.mark.asyncio
    async def test_query_hget(self, redis_provider):
        """Gets single hash field."""
        await redis_provider.redis_client.hset("test_hash_2", "myfield", "myvalue")

        result = await redis_provider.query("test_hash_2", "hget", field="myfield")

        assert result.success is True
        assert result.data.get("myfield") == "myvalue"

    @pytest.mark.asyncio
    async def test_query_hget_missing_field_error(self, redis_provider):
        """Raises error without field parameter."""
        await redis_provider.redis_client.hset("test_hash_3", "f", "v")

        result = await redis_provider.query("test_hash_3", "hget")

        assert result.success is False
        assert "field" in result.error.lower()

    @pytest.mark.asyncio
    async def test_query_hkeys(self, redis_provider):
        """Lists hash field names."""
        await redis_provider.redis_client.hset("hkeys_hash", mapping={"a": "1", "b": "2"})

        result = await redis_provider.query("hkeys_hash", "hkeys")

        assert result.success is True
        assert "a" in result.data
        assert "b" in result.data

    @pytest.mark.asyncio
    async def test_query_hvals(self, redis_provider):
        """Lists hash values."""
        await redis_provider.redis_client.hset("hvals_hash", mapping={"x": "10", "y": "20"})

        result = await redis_provider.query("hvals_hash", "hvals")

        assert result.success is True
        assert "10" in result.data
        assert "20" in result.data


# ============================================================================
# Query Operations - Lists Tests
# ============================================================================


class TestRedisQueryLists:
    """Tests for list query operations."""

    @pytest.mark.asyncio
    async def test_query_lrange(self, redis_provider):
        """Gets list range."""
        await redis_provider.redis_client.rpush("test_list", "a", "b", "c", "d")

        result = await redis_provider.query("test_list", "lrange", start=0, end=-1)

        assert result.success is True
        assert result.data == ["a", "b", "c", "d"]

    @pytest.mark.asyncio
    async def test_query_llen(self, redis_provider):
        """Gets list length."""
        await redis_provider.redis_client.rpush("len_list", "1", "2", "3")

        result = await redis_provider.query("len_list", "llen")

        assert result.success is True
        assert result.data["length"] == 3

    @pytest.mark.asyncio
    async def test_query_lindex(self, redis_provider):
        """Gets element by index."""
        await redis_provider.redis_client.rpush("index_list", "first", "second", "third")

        result = await redis_provider.query("index_list", "lindex", index=1)

        assert result.success is True
        assert result.data["value"] == "second"


# ============================================================================
# Query Operations - Sets Tests
# ============================================================================


class TestRedisQuerySets:
    """Tests for set query operations."""

    @pytest.mark.asyncio
    async def test_query_smembers(self, redis_provider):
        """Gets all set members."""
        await redis_provider.redis_client.sadd("test_set", "m1", "m2", "m3")

        result = await redis_provider.query("test_set", "smembers")

        assert result.success is True
        assert set(result.data) == {"m1", "m2", "m3"}

    @pytest.mark.asyncio
    async def test_query_scard(self, redis_provider):
        """Gets set cardinality."""
        await redis_provider.redis_client.sadd("card_set", "a", "b", "c", "d")

        result = await redis_provider.query("card_set", "scard")

        assert result.success is True
        assert result.data["count"] == 4

    @pytest.mark.asyncio
    async def test_query_sismember(self, redis_provider):
        """Checks set membership."""
        await redis_provider.redis_client.sadd("member_set", "hello", "world")

        result = await redis_provider.query("member_set", "sismember", member="hello")

        assert result.success is True


# ============================================================================
# Query Operations - Structured Tests
# ============================================================================


class TestRedisQueryStructured:
    """Tests for structured query operations."""

    @pytest.mark.asyncio
    async def test_query_mget(self, redis_provider):
        """Multi-get multiple keys."""
        await redis_provider.store("mget_1", "value1")
        await redis_provider.store("mget_2", "value2")

        result = await redis_provider.query(
            "",
            {"operation": "mget", "keys": ["mget_1", "mget_2"]}
        )

        assert result.success is True
        assert result.data.get("mget_1") == "value1"
        assert result.data.get("mget_2") == "value2"

    @pytest.mark.asyncio
    async def test_query_unsupported(self, redis_provider):
        """Raises error for unknown query."""
        result = await redis_provider.query("key", "unknown_operation")

        assert result.success is False
        assert "unsupported" in result.error.lower()


# ============================================================================
# Delete Operations Tests
# ============================================================================


class TestRedisDelete:
    """Tests for delete operations."""

    @pytest.mark.asyncio
    async def test_delete_single(self, redis_provider):
        """Deletes single key."""
        await redis_provider.store("delete_me", "data")

        result = await redis_provider.delete("delete_me")

        assert result.success is True
        assert result.data.get("deleted") >= 1

    @pytest.mark.asyncio
    async def test_delete_pattern(self, redis_provider):
        """Deletes keys matching pattern."""
        await redis_provider.store("delete_pattern_1", "1")
        await redis_provider.store("delete_pattern_2", "2")
        await redis_provider.store("keep_this", "3")

        result = await redis_provider.delete("delete_pattern_*", pattern_delete=True)

        assert result.success is True
        assert result.data.get("deleted") >= 2

    @pytest.mark.asyncio
    async def test_delete_pattern_no_matches(self, redis_provider):
        """Returns 0 for pattern with no matches."""
        result = await redis_provider.delete(
            "nonexistent_pattern_*",
            pattern_delete=True
        )

        assert result.success is True
        assert result.data.get("deleted") == 0


# ============================================================================
# List Resources Tests
# ============================================================================


class TestRedisListResources:
    """Tests for list_resources method."""

    @pytest.mark.asyncio
    async def test_list_resources(self, redis_provider):
        """Lists keys with prefix pattern."""
        await redis_provider.store("list_res_1", "1")
        await redis_provider.store("list_res_2", "2")

        result = await redis_provider.query("list_res_*", "keys")

        assert result.success is True
        assert len(result.data) >= 2
