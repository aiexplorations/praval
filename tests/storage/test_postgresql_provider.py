"""
Integration tests for PostgreSQL storage provider.

These tests require Docker to run PostgreSQL via testcontainers.
Skip these tests if Docker is not available: pytest -m "not integration"
"""

import pytest
import pytest_asyncio
import json

# Skip all tests in this file if asyncpg is not available
pytest.importorskip("asyncpg", reason="asyncpg required for PostgreSQL tests")

from praval.storage.providers.postgresql import PostgreSQLProvider
from praval.storage.base_provider import StorageType, StorageResult
from praval.storage.exceptions import StorageConnectionError


# ============================================================================
# Initialization & Configuration Tests
# ============================================================================


class TestPostgreSQLProviderInit:
    """Tests for PostgreSQL provider initialization."""

    def test_provider_init_with_config(self, postgres_config):
        """Creates provider with required config."""
        provider = PostgreSQLProvider("test_postgres", postgres_config)

        assert provider.name == "test_postgres"
        assert provider.config["host"] == postgres_config["host"]
        assert provider.config["database"] == postgres_config["database"]

    def test_provider_metadata_storage_type(self, postgres_config):
        """Provider has correct storage type."""
        provider = PostgreSQLProvider("test_postgres", postgres_config)

        assert provider.metadata.storage_type == StorageType.RELATIONAL

    def test_provider_default_port(self, postgres_config):
        """Defaults to port 5432."""
        config = {k: v for k, v in postgres_config.items() if k != "port"}
        provider = PostgreSQLProvider("test_postgres", config)

        assert provider.config["port"] == 5432

    def test_provider_build_connection_string(self, postgres_config):
        """Builds correct connection string."""
        provider = PostgreSQLProvider("test_postgres", postgres_config)

        conn_str = provider._connection_string
        assert postgres_config["host"] in conn_str
        assert postgres_config["database"] in conn_str
        assert postgres_config["user"] in conn_str


# ============================================================================
# Connection Tests
# ============================================================================


class TestPostgreSQLConnection:
    """Tests for PostgreSQL connection handling."""

    @pytest.mark.asyncio
    async def test_connect_success(self, postgres_config):
        """Successfully connects to PostgreSQL."""
        provider = PostgreSQLProvider("test_postgres", postgres_config)

        connected = await provider.connect()

        assert connected is True
        assert provider.is_connected is True
        assert provider.connection_pool is not None

        await provider.disconnect()

    @pytest.mark.asyncio
    async def test_connect_invalid_host(self, postgres_config):
        """Raises error for invalid host."""
        config = dict(postgres_config)
        config["host"] = "invalid_host_that_does_not_exist"

        provider = PostgreSQLProvider("test_postgres", config)

        with pytest.raises(StorageConnectionError):
            await provider.connect()

    @pytest.mark.asyncio
    async def test_disconnect(self, postgres_config):
        """Disconnects properly."""
        provider = PostgreSQLProvider("test_postgres", postgres_config)
        await provider.connect()

        await provider.disconnect()

        assert provider.is_connected is False
        assert provider.connection_pool is None


# ============================================================================
# Store Operations Tests
# ============================================================================


class TestPostgreSQLStore:
    """Tests for store operations."""

    @pytest.mark.asyncio
    async def test_store_single_dict(self, postgres_provider):
        """Inserts single record from dict."""
        result = await postgres_provider.store(
            "test_table",
            {"name": "Test Record", "data": {"key": "value"}}
        )

        assert result.success is True
        assert result.data.get("inserted") == 1

    @pytest.mark.asyncio
    async def test_store_with_returning(self, postgres_provider):
        """Inserts with RETURNING clause."""
        result = await postgres_provider.store(
            "test_table",
            {"name": "Test Record"},
            returning="id, name"
        )

        assert result.success is True
        assert "id" in result.data
        assert result.data["name"] == "Test Record"

    @pytest.mark.asyncio
    async def test_store_bulk_list(self, postgres_provider):
        """Bulk inserts multiple records."""
        records = [
            {"name": f"Record {i}"} for i in range(5)
        ]

        result = await postgres_provider.store("test_table", records)

        assert result.success is True
        assert result.data.get("inserted") == 5

    @pytest.mark.asyncio
    async def test_store_empty_list(self, postgres_provider):
        """Returns 0 for empty list."""
        result = await postgres_provider.store("test_table", [])

        assert result.success is True
        assert result.data.get("inserted") == 0

    @pytest.mark.asyncio
    async def test_store_invalid_type(self, postgres_provider):
        """Returns error for invalid data type."""
        result = await postgres_provider.store("test_table", "invalid string")

        assert result.success is False
        assert "unsupported" in result.error.lower() or "data type" in result.error.lower()

    @pytest.mark.asyncio
    async def test_store_auto_connect(self, postgres_config):
        """Connects automatically if not connected."""
        provider = PostgreSQLProvider("test_postgres", postgres_config)
        # Don't call connect()

        result = await provider.store("test_table", {"name": "Auto Connect Test"})

        assert result.success is True
        assert provider.is_connected is True

        await provider.disconnect()


# ============================================================================
# Retrieve Operations Tests
# ============================================================================


class TestPostgreSQLRetrieve:
    """Tests for retrieve operations."""

    @pytest.mark.asyncio
    async def test_retrieve_all(self, postgres_provider):
        """Retrieves all records from table."""
        # Insert test data
        await postgres_provider.store("test_table", [
            {"name": "Record 1"},
            {"name": "Record 2"},
            {"name": "Record 3"},
        ])

        result = await postgres_provider.retrieve("test_table")

        assert result.success is True
        assert len(result.data) >= 3

    @pytest.mark.asyncio
    async def test_retrieve_with_where(self, postgres_provider):
        """Retrieves with WHERE clause."""
        await postgres_provider.store("test_table", {"name": "Specific Record"})

        result = await postgres_provider.retrieve(
            "test_table",
            where={"name": "Specific Record"}
        )

        assert result.success is True
        assert len(result.data) >= 1
        assert all(r["name"] == "Specific Record" for r in result.data)

    @pytest.mark.asyncio
    async def test_retrieve_with_order(self, postgres_provider):
        """Retrieves with ORDER BY."""
        await postgres_provider.store("test_table", [
            {"name": "Zebra"},
            {"name": "Apple"},
            {"name": "Mango"},
        ])

        result = await postgres_provider.retrieve(
            "test_table",
            order_by="name ASC"
        )

        assert result.success is True
        # First record should be alphabetically first
        names = [r["name"] for r in result.data]
        assert names == sorted(names)

    @pytest.mark.asyncio
    async def test_retrieve_with_limit_offset(self, postgres_provider):
        """Retrieves with pagination."""
        await postgres_provider.store("test_table", [
            {"name": f"Record {i}"} for i in range(10)
        ])

        result = await postgres_provider.retrieve(
            "test_table",
            limit=3,
            offset=2
        )

        assert result.success is True
        assert len(result.data) <= 3

    @pytest.mark.asyncio
    async def test_retrieve_empty_result(self, postgres_provider):
        """Returns empty list when no matches."""
        result = await postgres_provider.retrieve(
            "test_table",
            where={"name": "NonExistentRecord_" + str(id(self))}
        )

        assert result.success is True
        assert result.data == []


# ============================================================================
# Query Operations Tests
# ============================================================================


class TestPostgreSQLQuery:
    """Tests for query operations."""

    @pytest.mark.asyncio
    async def test_query_raw_select(self, postgres_provider):
        """Executes raw SELECT SQL."""
        await postgres_provider.store("test_table", {"name": "Query Test"})

        result = await postgres_provider.query(
            "test_table",
            "SELECT name FROM test_table WHERE name = $1",
            params=["Query Test"]
        )

        assert result.success is True
        assert len(result.data) >= 1

    @pytest.mark.asyncio
    async def test_query_raw_non_select(self, postgres_provider):
        """Executes raw INSERT/UPDATE/DELETE."""
        result = await postgres_provider.query(
            "test_table",
            "INSERT INTO test_table (name) VALUES ($1)",
            params=["Raw Insert"]
        )

        assert result.success is True
        assert "executed" in str(result.data.get("status", ""))

    @pytest.mark.asyncio
    async def test_query_structured_select(self, postgres_provider):
        """Executes structured dict query."""
        await postgres_provider.store("test_table", {"name": "Structured Query Test"})

        result = await postgres_provider.query(
            "test_table",
            {
                "operation": "select",
                "where": {"name": "Structured Query Test"}
            }
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_query_structured_with_fields(self, postgres_provider):
        """Selects specific columns."""
        await postgres_provider.store("test_table", {"name": "Fields Test"})

        result = await postgres_provider.query(
            "test_table",
            {
                "operation": "select",
                "fields": ["name"],
                "where": {"name": "Fields Test"}
            }
        )

        assert result.success is True
        if result.data:
            # Should only have 'name' column (maybe with 'id' from *)
            assert "name" in result.data[0]


# ============================================================================
# Delete Operations Tests
# ============================================================================


class TestPostgreSQLDelete:
    """Tests for delete operations."""

    @pytest.mark.asyncio
    async def test_delete_with_where(self, postgres_provider):
        """Deletes records matching WHERE."""
        await postgres_provider.store("test_table", {"name": "Delete Me"})

        result = await postgres_provider.delete(
            "test_table",
            where={"name": "Delete Me"}
        )

        assert result.success is True
        assert result.data.get("deleted", 0) >= 1

    @pytest.mark.asyncio
    async def test_delete_no_where_error(self, postgres_provider):
        """Raises error when WHERE clause missing."""
        result = await postgres_provider.delete("test_table")

        assert result.success is False
        assert "where" in result.error.lower()

    @pytest.mark.asyncio
    async def test_delete_returns_count(self, postgres_provider):
        """Returns count of deleted records."""
        # Insert 3 records
        await postgres_provider.store("test_table", [
            {"name": "DeleteBatch"},
            {"name": "DeleteBatch"},
            {"name": "DeleteBatch"},
        ])

        result = await postgres_provider.delete(
            "test_table",
            where={"name": "DeleteBatch"}
        )

        assert result.success is True
        assert result.data.get("deleted") >= 3


# ============================================================================
# WHERE Clause Builder Tests
# ============================================================================


class TestWhereClauseBuilder:
    """Tests for WHERE clause construction."""

    def test_where_equality(self, postgres_config):
        """Builds equality condition."""
        provider = PostgreSQLProvider("test", postgres_config)

        clause, params = provider._build_where_clause({"name": "Test"})

        assert "name = $1" in clause
        assert params == ["Test"]

    def test_where_gt(self, postgres_config):
        """Builds greater than condition."""
        provider = PostgreSQLProvider("test", postgres_config)

        clause, params = provider._build_where_clause({"age": {"$gt": 25}})

        assert "age > $1" in clause
        assert 25 in params

    def test_where_lt(self, postgres_config):
        """Builds less than condition."""
        provider = PostgreSQLProvider("test", postgres_config)

        clause, params = provider._build_where_clause({"age": {"$lt": 30}})

        assert "age < $1" in clause
        assert 30 in params

    def test_where_gte(self, postgres_config):
        """Builds greater than or equal condition."""
        provider = PostgreSQLProvider("test", postgres_config)

        clause, params = provider._build_where_clause({"age": {"$gte": 18}})

        assert "age >= $1" in clause

    def test_where_lte(self, postgres_config):
        """Builds less than or equal condition."""
        provider = PostgreSQLProvider("test", postgres_config)

        clause, params = provider._build_where_clause({"age": {"$lte": 65}})

        assert "age <= $1" in clause

    def test_where_ne(self, postgres_config):
        """Builds not equal condition."""
        provider = PostgreSQLProvider("test", postgres_config)

        clause, params = provider._build_where_clause({"status": {"$ne": "deleted"}})

        assert "status != $1" in clause

    def test_where_in(self, postgres_config):
        """Builds IN condition."""
        provider = PostgreSQLProvider("test", postgres_config)

        clause, params = provider._build_where_clause({"status": {"$in": ["active", "pending"]}})

        assert "status IN" in clause
        assert "active" in params
        assert "pending" in params

    def test_where_multiple(self, postgres_config):
        """Builds multiple conditions with AND."""
        provider = PostgreSQLProvider("test", postgres_config)

        clause, params = provider._build_where_clause({
            "name": "Test",
            "age": {"$gt": 18}
        })

        assert "AND" in clause
        assert "name = $1" in clause


# ============================================================================
# List Resources Tests
# ============================================================================


class TestPostgreSQLListResources:
    """Tests for list_resources method."""

    @pytest.mark.asyncio
    async def test_list_resources(self, postgres_provider):
        """Lists tables in database."""
        result = await postgres_provider.list_resources()

        assert result.success is True
        assert isinstance(result.data, list)
        assert "test_table" in result.data

    @pytest.mark.asyncio
    async def test_list_resources_with_prefix(self, postgres_provider):
        """Filters tables by prefix."""
        result = await postgres_provider.list_resources(prefix="test_")

        assert result.success is True
        assert all(table.startswith("test_") for table in result.data)
