"""
Tests for storage system exceptions.

These tests verify that all storage exception classes behave correctly,
have proper messages, and maintain the expected inheritance hierarchy.
"""

import pytest

from praval.storage.exceptions import (
    StorageError,
    StorageNotFoundError,
    StorageConnectionError,
    StoragePermissionError,
    StorageTimeoutError,
    StorageConfigurationError,
)


class TestStorageError:
    """Tests for the base StorageError exception."""

    def test_storage_error_base(self):
        """Base exception with all fields."""
        error = StorageError(
            message="Test error",
            provider="test_provider",
            storage_type="RELATIONAL",
            details={"key": "value"}
        )

        assert str(error) == "Test error"
        assert error.provider == "test_provider"
        assert error.storage_type == "RELATIONAL"
        assert error.details == {"key": "value"}

    def test_storage_error_minimal(self):
        """Base exception with only required message."""
        error = StorageError("Simple error")

        assert str(error) == "Simple error"
        assert error.provider is None
        assert error.storage_type is None
        assert error.details == {}

    def test_storage_error_details_default(self):
        """Details defaults to empty dict when None."""
        error = StorageError("Error", details=None)
        assert error.details == {}


class TestStorageNotFoundError:
    """Tests for StorageNotFoundError exception."""

    def test_storage_not_found_error(self):
        """Resource not found message."""
        error = StorageNotFoundError(resource="my_table")

        assert "my_table" in str(error)
        assert "not found" in str(error)
        assert error.resource == "my_table"

    def test_storage_not_found_error_with_provider(self):
        """Resource not found with provider context."""
        error = StorageNotFoundError(
            resource="my_table",
            provider="postgres_main"
        )

        assert "my_table" in str(error)
        assert "postgres_main" in str(error)
        assert error.provider == "postgres_main"

    def test_storage_not_found_error_with_available(self):
        """Shows available resources in message."""
        error = StorageNotFoundError(
            resource="missing_table",
            available_resources=["users", "orders", "products"]
        )

        assert "missing_table" in str(error)
        assert "Available resources" in str(error)
        assert error.available_resources == ["users", "orders", "products"]

    def test_storage_not_found_error_available_default(self):
        """Available resources defaults to empty list."""
        error = StorageNotFoundError(resource="table")
        assert error.available_resources == []


class TestStorageConnectionError:
    """Tests for StorageConnectionError exception."""

    def test_storage_connection_error(self):
        """Connection failure message."""
        error = StorageConnectionError(provider="redis_cache")

        assert "redis_cache" in str(error)
        assert "connect" in str(error).lower() or "connection" in str(error).lower()
        assert error.provider == "redis_cache"

    def test_storage_connection_error_with_details(self):
        """Connection failure includes details."""
        error = StorageConnectionError(
            provider="postgres_db",
            connection_details="Connection refused on port 5432"
        )

        assert "postgres_db" in str(error)
        assert "5432" in str(error)
        assert error.connection_details == "Connection refused on port 5432"

    def test_storage_connection_error_details_none(self):
        """Connection details can be None."""
        error = StorageConnectionError(provider="redis")
        assert error.connection_details is None


class TestStoragePermissionError:
    """Tests for StoragePermissionError exception."""

    def test_storage_permission_error(self):
        """Permission denied message."""
        error = StoragePermissionError(
            operation="write",
            resource="protected_table"
        )

        assert "write" in str(error)
        assert "protected_table" in str(error)
        assert "permission" in str(error).lower() or "denied" in str(error).lower()
        assert error.operation == "write"
        assert error.resource == "protected_table"

    def test_storage_permission_error_with_provider(self):
        """Permission error with provider context."""
        error = StoragePermissionError(
            operation="delete",
            resource="audit_logs",
            provider="secure_storage"
        )

        assert "delete" in str(error)
        assert "audit_logs" in str(error)
        assert "secure_storage" in str(error)
        assert error.provider == "secure_storage"


class TestStorageTimeoutError:
    """Tests for StorageTimeoutError exception."""

    def test_storage_timeout_error(self):
        """Timeout message."""
        error = StorageTimeoutError(
            operation="query",
            timeout=30.0
        )

        assert "query" in str(error)
        assert "30" in str(error)
        assert "timed out" in str(error).lower()
        assert error.operation == "query"
        assert error.timeout == 30.0

    def test_storage_timeout_error_with_provider(self):
        """Timeout error with provider context."""
        error = StorageTimeoutError(
            operation="bulk_insert",
            timeout=60.0,
            provider="slow_database"
        )

        assert "bulk_insert" in str(error)
        assert "60" in str(error)
        assert "slow_database" in str(error)
        assert error.provider == "slow_database"


class TestStorageConfigurationError:
    """Tests for StorageConfigurationError exception."""

    def test_storage_configuration_error(self):
        """Config issue message."""
        error = StorageConfigurationError(
            provider="s3_bucket",
            config_issue="Missing required 'bucket_name' parameter"
        )

        assert "s3_bucket" in str(error)
        assert "bucket_name" in str(error)
        assert error.provider == "s3_bucket"
        assert error.config_issue == "Missing required 'bucket_name' parameter"


class TestExceptionInheritance:
    """Tests for exception inheritance hierarchy."""

    def test_exception_inheritance(self):
        """All storage exceptions inherit from StorageError."""
        assert issubclass(StorageNotFoundError, StorageError)
        assert issubclass(StorageConnectionError, StorageError)
        assert issubclass(StoragePermissionError, StorageError)
        assert issubclass(StorageTimeoutError, StorageError)
        assert issubclass(StorageConfigurationError, StorageError)

    def test_storage_error_is_exception(self):
        """StorageError inherits from Exception."""
        assert issubclass(StorageError, Exception)

    def test_can_catch_all_with_storage_error(self):
        """All storage exceptions can be caught with StorageError."""
        exceptions = [
            StorageNotFoundError("resource"),
            StorageConnectionError("provider"),
            StoragePermissionError("op", "resource"),
            StorageTimeoutError("op", 10.0),
            StorageConfigurationError("provider", "issue"),
        ]

        for exc in exceptions:
            with pytest.raises(StorageError):
                raise exc
