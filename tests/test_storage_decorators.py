"""
Tests for storage decorators in Praval.

Tests the decorator-based integration between agents and storage providers.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import os

from praval.storage.decorators import (
    storage_enabled,
    requires_storage,
    _ensure_storage_providers,
    _ensure_single_provider,
    _auto_register_provider
)
from praval.storage.exceptions import StorageNotFoundError, StorageConfigurationError


class TestStorageEnabledDecorator:
    """Tests for the @storage_enabled decorator."""

    def test_decorator_stores_config_on_function(self):
        """Test that decorator stores storage config on the function."""
        @storage_enabled("postgres")
        def my_func():
            pass

        assert hasattr(my_func, '_storage_config')
        assert my_func._storage_config["providers"] == "postgres"
        assert my_func._storage_config["auto_register"] is True

    def test_decorator_with_list_of_providers(self):
        """Test decorator with multiple providers as list."""
        @storage_enabled(["postgres", "redis", "s3"])
        def my_func():
            pass

        assert my_func._storage_config["providers"] == ["postgres", "redis", "s3"]

    def test_decorator_with_dict_providers(self):
        """Test decorator with provider configurations."""
        config = {
            "postgres": {"host": "localhost", "database": "test"},
            "s3": {"bucket_name": "my-bucket"}
        }

        @storage_enabled(config)
        def my_func():
            pass

        assert my_func._storage_config["providers"] == config

    def test_decorator_with_permissions(self):
        """Test decorator with permissions."""
        @storage_enabled("postgres", permissions=["read", "write"])
        def my_func():
            pass

        assert my_func._storage_config["permissions"] == ["read", "write"]

    def test_decorator_auto_register_false(self):
        """Test decorator with auto_register disabled."""
        @storage_enabled("postgres", auto_register=False)
        def my_func():
            pass

        assert my_func._storage_config["auto_register"] is False

    def test_decorator_with_default_configs(self):
        """Test decorator with default configurations."""
        @storage_enabled("postgres", timeout=30, max_connections=10)
        def my_func():
            pass

        assert my_func._storage_config["default_configs"]["timeout"] == 30
        assert my_func._storage_config["default_configs"]["max_connections"] == 10

    @patch('praval.storage.decorators._ensure_storage_providers')
    @patch('praval.storage.decorators.get_data_manager')
    def test_sync_wrapper_adds_storage_to_kwargs(self, mock_get_dm, mock_ensure):
        """Test that sync wrapper adds storage to kwargs."""
        mock_dm = Mock()
        mock_get_dm.return_value = mock_dm

        @storage_enabled("postgres")
        def my_func(**kwargs):
            return kwargs.get('storage')

        result = my_func()
        assert result == mock_dm

    @patch('praval.storage.decorators._ensure_storage_providers')
    @patch('praval.storage.decorators.get_data_manager')
    def test_sync_wrapper_preserves_existing_storage_kwarg(self, mock_get_dm, mock_ensure):
        """Test that existing storage kwarg is preserved."""
        custom_storage = Mock()

        @storage_enabled("postgres")
        def my_func(**kwargs):
            return kwargs.get('storage')

        result = my_func(storage=custom_storage)
        assert result == custom_storage
        mock_get_dm.assert_not_called()

    @pytest.mark.asyncio
    @patch('praval.storage.decorators._ensure_storage_providers', new_callable=AsyncMock)
    @patch('praval.storage.decorators.get_data_manager')
    async def test_async_wrapper_calls_ensure_providers(self, mock_get_dm, mock_ensure):
        """Test that async wrapper calls _ensure_storage_providers."""
        mock_dm = Mock()
        mock_get_dm.return_value = mock_dm

        @storage_enabled("postgres")
        async def my_async_func(**kwargs):
            return kwargs.get('storage')

        result = await my_async_func()
        mock_ensure.assert_called_once()
        assert result == mock_dm

    @pytest.mark.asyncio
    @patch('praval.storage.decorators._ensure_storage_providers', new_callable=AsyncMock)
    @patch('praval.storage.decorators.get_data_manager')
    async def test_async_wrapper_preserves_return_value(self, mock_get_dm, mock_ensure):
        """Test that async wrapper preserves function return value."""
        mock_get_dm.return_value = Mock()

        @storage_enabled("postgres")
        async def my_async_func(**kwargs):
            return "expected_result"

        result = await my_async_func()
        assert result == "expected_result"


class TestRequiresStorageDecorator:
    """Tests for the @requires_storage decorator."""

    @patch('praval.storage.decorators.get_storage_registry')
    @patch('praval.storage.decorators.get_data_manager')
    def test_sync_wrapper_checks_provider_availability(self, mock_get_dm, mock_get_registry):
        """Test that sync wrapper checks provider availability."""
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry

        @requires_storage("postgres")
        def my_func(**kwargs):
            return "success"

        result = my_func()
        mock_registry.get_provider.assert_called_once_with("postgres", "my_func")
        assert result == "success"

    @patch('praval.storage.decorators.get_storage_registry')
    def test_sync_wrapper_raises_on_missing_provider(self, mock_get_registry):
        """Test that sync wrapper raises error when provider is missing."""
        mock_registry = Mock()
        mock_registry.get_provider.side_effect = StorageNotFoundError("postgres")
        mock_get_registry.return_value = mock_registry

        @requires_storage("postgres")
        def my_func(**kwargs):
            return "success"

        with pytest.raises(StorageConfigurationError) as exc_info:
            my_func()

        assert "postgres" in str(exc_info.value)
        assert "not available" in str(exc_info.value)

    @patch('praval.storage.decorators.get_storage_registry')
    @patch('praval.storage.decorators.get_data_manager')
    def test_sync_wrapper_checks_multiple_providers(self, mock_get_dm, mock_get_registry):
        """Test that sync wrapper checks all required providers."""
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry

        @requires_storage("postgres", "s3", "redis")
        def my_func(**kwargs):
            return "success"

        my_func()

        # Should check all three providers
        assert mock_registry.get_provider.call_count == 3

    @patch('praval.storage.decorators.get_storage_registry')
    @patch('praval.storage.decorators.get_data_manager')
    def test_sync_wrapper_adds_storage_to_kwargs(self, mock_get_dm, mock_get_registry):
        """Test that storage is added to kwargs."""
        mock_dm = Mock()
        mock_get_dm.return_value = mock_dm
        mock_get_registry.return_value = Mock()

        @requires_storage("postgres")
        def my_func(**kwargs):
            return kwargs.get('storage')

        result = my_func()
        assert result == mock_dm

    @pytest.mark.asyncio
    @patch('praval.storage.decorators.get_storage_registry')
    @patch('praval.storage.decorators.get_data_manager')
    async def test_async_wrapper_checks_provider_availability(self, mock_get_dm, mock_get_registry):
        """Test that async wrapper checks provider availability."""
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry

        @requires_storage("postgres")
        async def my_async_func(**kwargs):
            return "success"

        result = await my_async_func()
        mock_registry.get_provider.assert_called_once()
        assert result == "success"

    @pytest.mark.asyncio
    @patch('praval.storage.decorators.get_storage_registry')
    async def test_async_wrapper_raises_on_missing_provider(self, mock_get_registry):
        """Test that async wrapper raises error when provider is missing."""
        mock_registry = Mock()
        mock_registry.get_provider.side_effect = StorageNotFoundError("redis")
        mock_get_registry.return_value = mock_registry

        @requires_storage("redis")
        async def my_async_func(**kwargs):
            return "success"

        with pytest.raises(StorageConfigurationError) as exc_info:
            await my_async_func()

        assert "redis" in str(exc_info.value)


class TestEnsureStorageProviders:
    """Tests for _ensure_storage_providers helper function."""

    @pytest.mark.asyncio
    async def test_empty_providers_config(self):
        """Test with no providers configured."""
        config = {"providers": None}
        # Should not raise
        await _ensure_storage_providers(config, "test_agent")

    @pytest.mark.asyncio
    @patch('praval.storage.decorators._ensure_single_provider', new_callable=AsyncMock)
    async def test_single_string_provider(self, mock_ensure_single):
        """Test with single provider as string."""
        config = {"providers": "postgres"}
        await _ensure_storage_providers(config, "test_agent")

        mock_ensure_single.assert_called_once()
        call_args = mock_ensure_single.call_args
        assert call_args[0][1] == "postgres"

    @pytest.mark.asyncio
    @patch('praval.storage.decorators._ensure_single_provider', new_callable=AsyncMock)
    async def test_list_of_providers(self, mock_ensure_single):
        """Test with list of providers."""
        config = {"providers": ["postgres", "redis", "s3"]}
        await _ensure_storage_providers(config, "test_agent")

        assert mock_ensure_single.call_count == 3

    @pytest.mark.asyncio
    @patch('praval.storage.decorators._ensure_single_provider', new_callable=AsyncMock)
    async def test_dict_of_providers(self, mock_ensure_single):
        """Test with dict of providers and configs."""
        config = {
            "providers": {
                "postgres": {"host": "localhost"},
                "redis": {"port": 6379}
            },
            "default_configs": {"timeout": 30}
        }
        await _ensure_storage_providers(config, "test_agent")

        assert mock_ensure_single.call_count == 2


class TestEnsureSingleProvider:
    """Tests for _ensure_single_provider helper function."""

    @pytest.mark.asyncio
    async def test_provider_already_available(self):
        """Test when provider is already registered."""
        mock_registry = Mock()
        config = {"auto_register": True}

        await _ensure_single_provider(mock_registry, "postgres", config, "test_agent")

        mock_registry.get_provider.assert_called_once_with("postgres", "test_agent")

    @pytest.mark.asyncio
    @patch('praval.storage.decorators._auto_register_provider', new_callable=AsyncMock)
    async def test_auto_register_on_missing(self, mock_auto_register):
        """Test auto-registration when provider is missing."""
        mock_registry = Mock()
        mock_registry.get_provider.side_effect = StorageNotFoundError("postgres")
        config = {"auto_register": True}

        await _ensure_single_provider(mock_registry, "postgres", config, "test_agent")

        mock_auto_register.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_when_auto_register_disabled(self):
        """Test that error is raised when auto_register is False."""
        mock_registry = Mock()
        mock_registry.get_provider.side_effect = StorageNotFoundError("postgres")
        config = {"auto_register": False}

        with pytest.raises(StorageConfigurationError) as exc_info:
            await _ensure_single_provider(mock_registry, "postgres", config, "test_agent")

        assert "auto_register is disabled" in str(exc_info.value)


class TestAutoRegisterProvider:
    """Tests for _auto_register_provider helper function."""

    @pytest.mark.asyncio
    async def test_unknown_provider_type_raises(self):
        """Test that unknown provider type raises error."""
        mock_registry = Mock()
        config = {}

        with pytest.raises(StorageConfigurationError) as exc_info:
            await _auto_register_provider(mock_registry, "unknown_provider", config, "test_agent")

        assert "Unknown storage provider type" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch('praval.storage.providers.FileSystemProvider')
    async def test_filesystem_provider_registration(self, mock_fs_class):
        """Test filesystem provider auto-registration."""
        mock_registry = AsyncMock()
        mock_registry.register_provider = AsyncMock(return_value=True)
        mock_provider = Mock()
        mock_fs_class.return_value = mock_provider

        config = {"default_configs": {}, "permissions": None}

        await _auto_register_provider(mock_registry, "filesystem", config, "test_agent")

        mock_fs_class.assert_called_once()
        mock_registry.register_provider.assert_called_once()

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"POSTGRES_HOST": "testhost", "POSTGRES_DB": "testdb"})
    @patch('praval.storage.providers.PostgreSQLProvider')
    async def test_env_config_loading(self, mock_pg_class):
        """Test that environment variables are loaded into config."""
        mock_registry = AsyncMock()
        mock_registry.register_provider = AsyncMock(return_value=True)
        mock_provider = Mock()
        mock_pg_class.return_value = mock_provider

        config = {"default_configs": {}, "permissions": None}

        await _auto_register_provider(mock_registry, "postgres", config, "test_agent")

        # Check that PostgreSQLProvider was called with env config
        call_args = mock_pg_class.call_args
        provider_config = call_args[0][1]
        assert provider_config.get("host") == "testhost"
        assert provider_config.get("database") == "testdb"

    @pytest.mark.asyncio
    @patch('praval.storage.providers.FileSystemProvider')
    async def test_filesystem_default_path(self, mock_fs_class):
        """Test filesystem provider gets default base_path."""
        mock_registry = AsyncMock()
        mock_registry.register_provider = AsyncMock(return_value=True)
        mock_provider = Mock()
        mock_fs_class.return_value = mock_provider

        config = {"default_configs": {}, "permissions": None}

        await _auto_register_provider(mock_registry, "filesystem", config, "test_agent")

        call_args = mock_fs_class.call_args
        provider_config = call_args[0][1]
        assert "base_path" in provider_config
        assert ".praval/storage" in provider_config["base_path"]

    @pytest.mark.asyncio
    @patch('praval.storage.providers.QdrantProvider')
    async def test_qdrant_default_url(self, mock_qdrant_class):
        """Test qdrant provider gets default URL."""
        mock_registry = AsyncMock()
        mock_registry.register_provider = AsyncMock(return_value=True)
        mock_provider = Mock()
        mock_qdrant_class.return_value = mock_provider

        config = {"default_configs": {}, "permissions": None}

        await _auto_register_provider(mock_registry, "qdrant", config, "test_agent")

        call_args = mock_qdrant_class.call_args
        provider_config = call_args[0][1]
        assert provider_config.get("url") == "http://localhost:6333"

    @pytest.mark.asyncio
    @patch('praval.storage.providers.FileSystemProvider')
    async def test_registration_failure_raises(self, mock_fs_class):
        """Test that registration failure raises StorageConfigurationError."""
        mock_registry = AsyncMock()
        mock_registry.register_provider = AsyncMock(return_value=False)
        mock_provider = Mock()
        mock_fs_class.return_value = mock_provider

        config = {"default_configs": {}, "permissions": None}

        with pytest.raises(StorageConfigurationError) as exc_info:
            await _auto_register_provider(mock_registry, "filesystem", config, "test_agent")

        assert "Failed to register" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch('praval.storage.providers.FileSystemProvider')
    async def test_provider_creation_exception_raises(self, mock_fs_class):
        """Test that provider creation exception is wrapped."""
        mock_registry = AsyncMock()
        mock_fs_class.side_effect = Exception("Connection failed")

        config = {"default_configs": {}, "permissions": None}

        with pytest.raises(StorageConfigurationError) as exc_info:
            await _auto_register_provider(mock_registry, "filesystem", config, "test_agent")

        assert "Failed to create storage provider" in str(exc_info.value)
        assert "Connection failed" in str(exc_info.value)


class TestDecoratorIntegration:
    """Integration tests for storage decorators."""

    @patch('praval.storage.decorators.get_storage_registry')
    @patch('praval.storage.decorators.get_data_manager')
    def test_storage_enabled_with_requires_storage(self, mock_get_dm, mock_get_registry):
        """Test combining storage_enabled with requires_storage."""
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry
        mock_dm = Mock()
        mock_get_dm.return_value = mock_dm

        @requires_storage("postgres")
        @storage_enabled("postgres")
        def process_data(**kwargs):
            return kwargs.get('storage')

        result = process_data()
        assert result == mock_dm

    def test_decorator_preserves_function_metadata(self):
        """Test that decorators preserve function metadata."""
        @storage_enabled("postgres")
        def my_documented_function():
            """This is my documentation."""
            pass

        assert my_documented_function.__name__ == "my_documented_function"
        assert "This is my documentation" in my_documented_function.__doc__

    @patch('praval.storage.decorators.get_storage_registry')
    @patch('praval.storage.decorators.get_data_manager')
    def test_requires_storage_preserves_function_metadata(self, mock_get_dm, mock_get_registry):
        """Test that requires_storage preserves function metadata."""
        mock_get_registry.return_value = Mock()

        @requires_storage("postgres")
        def another_documented_function():
            """Another documentation string."""
            pass

        assert another_documented_function.__name__ == "another_documented_function"
        assert "Another documentation string" in another_documented_function.__doc__
