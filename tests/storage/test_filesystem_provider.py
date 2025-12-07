"""
Tests for FileSystem storage provider.

These tests use a temporary directory and don't require any external services.
"""

import asyncio
import json
import os
import pytest
import tempfile
from io import BytesIO, StringIO
from pathlib import Path

from praval.storage.providers.filesystem import FileSystemProvider
from praval.storage.base_provider import StorageType, StorageResult
from praval.storage.exceptions import StorageConnectionError, StorageConfigurationError


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def provider(temp_dir):
    """Create a FileSystem provider for testing."""
    return FileSystemProvider("test_fs", {"base_path": temp_dir})


class TestFileSystemProviderInit:
    """Tests for FileSystemProvider initialization."""

    def test_filesystem_provider_init(self, temp_dir):
        """Creates with base_path."""
        provider = FileSystemProvider("test_fs", {"base_path": temp_dir})

        assert provider.name == "test_fs"
        assert provider.base_path == Path(temp_dir).resolve()
        assert provider.is_connected is False

    def test_filesystem_provider_metadata(self, temp_dir):
        """Correct StorageType.FILE_SYSTEM."""
        provider = FileSystemProvider("test_fs", {"base_path": temp_dir})

        assert provider.metadata.storage_type == StorageType.FILE_SYSTEM
        assert provider.metadata.supports_async is True
        assert provider.metadata.supports_search is True

    def test_filesystem_provider_creates_base_dir(self, temp_dir):
        """Creates base_path if missing with create_directories=True."""
        new_dir = os.path.join(temp_dir, "new_subdir")
        assert not os.path.exists(new_dir)

        provider = FileSystemProvider("test_fs", {
            "base_path": new_dir,
            "create_directories": True
        })

        assert os.path.exists(new_dir)
        assert os.path.isdir(new_dir)

    def test_filesystem_provider_missing_base_dir_error(self, temp_dir):
        """Raises error with create_directories=False."""
        non_existent = os.path.join(temp_dir, "nonexistent")

        with pytest.raises(StorageConfigurationError) as exc_info:
            FileSystemProvider("test_fs", {
                "base_path": non_existent,
                "create_directories": False
            })

        assert "does not exist" in str(exc_info.value)

    def test_filesystem_provider_base_not_dir_error(self, temp_dir):
        """Raises if base_path is a file."""
        file_path = os.path.join(temp_dir, "somefile.txt")
        Path(file_path).write_text("content")

        with pytest.raises(StorageConfigurationError) as exc_info:
            FileSystemProvider("test_fs", {"base_path": file_path})

        assert "not a directory" in str(exc_info.value)


class TestFileSystemConnection:
    """Tests for connection handling."""

    @pytest.mark.asyncio
    async def test_filesystem_connect_success(self, provider):
        """Verifies write access."""
        result = await provider.connect()

        assert result is True
        assert provider.is_connected is True

    @pytest.mark.asyncio
    async def test_filesystem_connect_no_write_access(self, temp_dir):
        """Raises StorageConnectionError if no write access."""
        # Create read-only directory
        readonly_dir = os.path.join(temp_dir, "readonly")
        os.makedirs(readonly_dir)
        os.chmod(readonly_dir, 0o444)

        provider = FileSystemProvider("test_fs", {"base_path": readonly_dir})

        try:
            with pytest.raises(StorageConnectionError):
                await provider.connect()
        finally:
            # Restore permissions for cleanup
            os.chmod(readonly_dir, 0o755)

    @pytest.mark.asyncio
    async def test_filesystem_disconnect(self, provider):
        """Sets is_connected=False."""
        await provider.connect()
        assert provider.is_connected is True

        await provider.disconnect()

        assert provider.is_connected is False


class TestPathResolution:
    """Tests for path resolution and security."""

    def test_filesystem_resolve_path_relative(self, provider):
        """Resolves relative path."""
        resolved = provider._resolve_path("data/file.txt")

        assert resolved == provider.base_path / "data" / "file.txt"

    def test_filesystem_resolve_path_leading_slash(self, provider):
        """Handles leading slash."""
        resolved = provider._resolve_path("/data/file.txt")

        assert resolved == provider.base_path / "data" / "file.txt"

    def test_filesystem_resolve_path_backslash(self, provider):
        """Normalizes backslashes."""
        resolved = provider._resolve_path("data\\subfolder\\file.txt")

        assert resolved == provider.base_path / "data" / "subfolder" / "file.txt"

    def test_filesystem_resolve_path_traversal_attack(self, provider):
        """Blocks ../.. paths."""
        with pytest.raises(ValueError) as exc_info:
            provider._resolve_path("../../etc/passwd")

        assert "outside base directory" in str(exc_info.value)


class TestFileSystemStore:
    """Tests for store operations."""

    @pytest.mark.asyncio
    async def test_filesystem_store_dict_as_json(self, provider):
        """Stores dict as JSON file."""
        await provider.connect()
        data = {"name": "test", "value": 123}

        result = await provider.store("data.json", data)

        assert result.success is True
        stored_content = (provider.base_path / "data.json").read_text()
        assert json.loads(stored_content) == data

    @pytest.mark.asyncio
    async def test_filesystem_store_list_as_json(self, provider):
        """Stores list as JSON file."""
        await provider.connect()
        data = [1, 2, 3, "four", {"five": 5}]

        result = await provider.store("list.json", data)

        assert result.success is True
        stored_content = (provider.base_path / "list.json").read_text()
        assert json.loads(stored_content) == data

    @pytest.mark.asyncio
    async def test_filesystem_store_string(self, provider):
        """Stores text file."""
        await provider.connect()
        content = "Hello, World!"

        result = await provider.store("hello.txt", content)

        assert result.success is True
        stored_content = (provider.base_path / "hello.txt").read_text()
        assert stored_content == content

    @pytest.mark.asyncio
    async def test_filesystem_store_bytes(self, provider):
        """Stores binary file."""
        await provider.connect()
        binary_data = b"\x00\x01\x02\x03\xff"

        result = await provider.store("binary.bin", binary_data)

        assert result.success is True
        stored_content = (provider.base_path / "binary.bin").read_bytes()
        assert stored_content == binary_data

    @pytest.mark.asyncio
    async def test_filesystem_store_file_object(self, provider):
        """Stores from file-like object."""
        await provider.connect()
        content = "File content from stream"
        file_obj = StringIO(content)

        result = await provider.store("stream.txt", file_obj)

        assert result.success is True
        stored_content = (provider.base_path / "stream.txt").read_text()
        assert stored_content == content

    @pytest.mark.asyncio
    async def test_filesystem_store_creates_parent_dirs(self, provider):
        """Creates nested directories."""
        await provider.connect()

        result = await provider.store("nested/deep/folder/file.txt", "content")

        assert result.success is True
        assert (provider.base_path / "nested" / "deep" / "folder" / "file.txt").exists()

    @pytest.mark.asyncio
    async def test_filesystem_store_custom_encoding(self, provider):
        """Uses specified encoding."""
        await provider.connect()
        content = "Héllo Wörld"

        result = await provider.store("encoded.txt", content, encoding="utf-8")

        assert result.success is True
        stored = (provider.base_path / "encoded.txt").read_text(encoding="utf-8")
        assert stored == content

    @pytest.mark.asyncio
    async def test_filesystem_store_custom_permissions(self, temp_dir):
        """Sets file permissions."""
        provider = FileSystemProvider("test_fs", {"base_path": temp_dir})
        await provider.connect()

        result = await provider.store("secure.txt", "secret", permissions=0o600)

        assert result.success is True
        file_path = provider.base_path / "secure.txt"
        mode = file_path.stat().st_mode & 0o777
        assert mode == 0o600

    @pytest.mark.asyncio
    async def test_filesystem_store_returns_metadata(self, provider):
        """Returns size, path, modified time."""
        await provider.connect()

        result = await provider.store("meta.txt", "test content")

        assert result.success is True
        assert result.metadata["operation"] == "write_file"
        assert result.metadata["size"] > 0
        assert "modified" in result.metadata
        assert result.data_reference is not None


class TestFileSystemRetrieve:
    """Tests for retrieve operations."""

    @pytest.mark.asyncio
    async def test_filesystem_retrieve_json_file(self, provider):
        """Reads and parses JSON."""
        await provider.connect()
        data = {"key": "value"}
        await provider.store("data.json", data)

        result = await provider.retrieve("data.json")

        assert result.success is True
        assert result.data == data

    @pytest.mark.asyncio
    async def test_filesystem_retrieve_text_file(self, provider):
        """Reads text file."""
        await provider.connect()
        content = "Plain text content"
        await provider.store("text.txt", content)

        result = await provider.retrieve("text.txt")

        assert result.success is True
        assert result.data == content

    @pytest.mark.asyncio
    async def test_filesystem_retrieve_binary_file(self, provider):
        """Reads binary file."""
        await provider.connect()
        binary_data = b"\x00\x01\x02\x03\xff"
        await provider.store("binary.bin", binary_data)

        result = await provider.retrieve("binary.bin", binary=True)

        assert result.success is True
        assert result.data == binary_data

    @pytest.mark.asyncio
    async def test_filesystem_retrieve_not_found(self, provider):
        """Returns error for missing file."""
        await provider.connect()

        result = await provider.retrieve("nonexistent.txt")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_filesystem_retrieve_is_directory(self, provider):
        """Returns error for directory."""
        await provider.connect()
        (provider.base_path / "some_dir").mkdir()

        result = await provider.retrieve("some_dir")

        assert result.success is False
        assert "not a file" in result.error.lower()

    @pytest.mark.asyncio
    async def test_filesystem_retrieve_no_json_decode(self, provider):
        """decode_json=False returns string."""
        await provider.connect()
        data = {"key": "value"}
        await provider.store("data.json", data)

        result = await provider.retrieve("data.json", decode_json=False)

        assert result.success is True
        assert isinstance(result.data, str)
        assert json.loads(result.data) == data

    @pytest.mark.asyncio
    async def test_filesystem_retrieve_custom_encoding(self, provider):
        """Uses specified encoding."""
        await provider.connect()
        content = "Héllo Wörld"
        (provider.base_path / "encoded.txt").write_text(content, encoding="utf-8")

        result = await provider.retrieve("encoded.txt", encoding="utf-8")

        assert result.success is True
        assert result.data == content

    @pytest.mark.asyncio
    async def test_filesystem_retrieve_detects_content_type(self, provider):
        """Infers content type from extension."""
        await provider.connect()
        await provider.store("data.json", {"test": True})

        result = await provider.retrieve("data.json")

        assert result.metadata["content_type"] == "application/json"


class TestFileSystemQuery:
    """Tests for query operations."""

    @pytest.mark.asyncio
    async def test_filesystem_query_list_directory(self, provider):
        """Lists directory contents."""
        await provider.connect()
        await provider.store("file1.txt", "content1")
        await provider.store("file2.txt", "content2")
        (provider.base_path / "subdir").mkdir()

        result = await provider.query("", "list")

        assert result.success is True
        names = [item["name"] for item in result.data]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "subdir" in names

    @pytest.mark.asyncio
    async def test_filesystem_query_list_not_found(self, provider):
        """Returns error for missing directory."""
        await provider.connect()

        result = await provider.query("nonexistent", "list")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_filesystem_query_list_not_dir(self, provider):
        """Returns error if path is file."""
        await provider.connect()
        await provider.store("somefile.txt", "content")

        result = await provider.query("somefile.txt", "list")

        assert result.success is False
        assert "not a directory" in result.error.lower()

    @pytest.mark.asyncio
    async def test_filesystem_query_find_pattern(self, provider):
        """Finds files matching glob pattern."""
        await provider.connect()
        await provider.store("file1.txt", "content")
        await provider.store("file2.txt", "content")
        await provider.store("other.json", "{}")

        result = await provider.query("", "find", pattern="*.txt")

        assert result.success is True
        names = [item["name"] for item in result.data]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "other.json" not in names

    @pytest.mark.asyncio
    async def test_filesystem_query_find_recursive(self, provider):
        """Recursive glob search."""
        await provider.connect()
        await provider.store("root.txt", "content")
        await provider.store("nested/deep/file.txt", "nested content")

        result = await provider.query("", "find", pattern="**/*.txt", recursive=True)

        assert result.success is True
        paths = [item["path"] for item in result.data]
        assert any("deep/file.txt" in p for p in paths)

    @pytest.mark.asyncio
    async def test_filesystem_query_metadata(self, provider):
        """Returns file/directory metadata."""
        await provider.connect()
        await provider.store("meta.txt", "content")

        result = await provider.query("meta.txt", "metadata")

        assert result.success is True
        assert result.data["type"] == "file"
        assert "size" in result.data
        assert "modified" in result.data
        assert "created" in result.data

    @pytest.mark.asyncio
    async def test_filesystem_query_exists_true(self, provider):
        """Returns exists=True."""
        await provider.connect()
        await provider.store("exists.txt", "content")

        result = await provider.query("exists.txt", "exists")

        assert result.success is True
        assert result.data["exists"] is True

    @pytest.mark.asyncio
    async def test_filesystem_query_exists_false(self, provider):
        """Returns exists=False."""
        await provider.connect()

        result = await provider.query("nonexistent.txt", "exists")

        assert result.success is True
        assert result.data["exists"] is False

    @pytest.mark.asyncio
    async def test_filesystem_query_unsupported(self, provider):
        """Raises for unknown query type."""
        await provider.connect()

        result = await provider.query("resource", "unsupported_query")

        assert result.success is False
        assert "unsupported" in result.error.lower()


class TestFileSystemDelete:
    """Tests for delete operations."""

    @pytest.mark.asyncio
    async def test_filesystem_delete_file(self, provider):
        """Deletes single file."""
        await provider.connect()
        await provider.store("to_delete.txt", "content")
        assert (provider.base_path / "to_delete.txt").exists()

        result = await provider.delete("to_delete.txt")

        assert result.success is True
        assert not (provider.base_path / "to_delete.txt").exists()

    @pytest.mark.asyncio
    async def test_filesystem_delete_file_not_found(self, provider):
        """Returns error for missing file."""
        await provider.connect()

        result = await provider.delete("nonexistent.txt")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_filesystem_delete_empty_directory(self, provider):
        """Deletes empty directory."""
        await provider.connect()
        (provider.base_path / "empty_dir").mkdir()

        result = await provider.delete("empty_dir")

        assert result.success is True
        assert not (provider.base_path / "empty_dir").exists()

    @pytest.mark.asyncio
    async def test_filesystem_delete_directory_not_empty(self, provider):
        """Returns error for non-empty directory without recursive."""
        await provider.connect()
        await provider.store("non_empty/file.txt", "content")

        result = await provider.delete("non_empty")

        assert result.success is False
        assert "not empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_filesystem_delete_directory_recursive(self, provider):
        """Deletes directory with contents recursively."""
        await provider.connect()
        await provider.store("to_delete/file1.txt", "content1")
        await provider.store("to_delete/nested/file2.txt", "content2")

        result = await provider.delete("to_delete", recursive=True)

        assert result.success is True
        assert not (provider.base_path / "to_delete").exists()


class TestFileSystemListResources:
    """Tests for list_resources."""

    @pytest.mark.asyncio
    async def test_filesystem_list_resources(self, provider):
        """Lists via query('list')."""
        await provider.connect()
        await provider.store("file1.txt", "content")
        await provider.store("file2.txt", "content")

        result = await provider.list_resources()

        assert result.success is True
        names = [item["name"] for item in result.data]
        assert "file1.txt" in names
        assert "file2.txt" in names
