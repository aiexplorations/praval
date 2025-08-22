"""
File system storage provider for Praval framework

Provides local file system storage capabilities with path management,
directory operations, and file metadata support.
"""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from ..base_provider import BaseStorageProvider, StorageMetadata, StorageResult, StorageType, DataReference
from ..exceptions import StorageConnectionError, StorageConfigurationError

logger = logging.getLogger(__name__)


class FileSystemProvider(BaseStorageProvider):
    """
    Local file system storage provider.
    
    Features:
    - File and directory operations
    - Path management and validation
    - File metadata and permissions
    - Recursive operations
    - Pattern-based file listing
    - Atomic file operations
    """
    
    def _create_metadata(self) -> StorageMetadata:
        return StorageMetadata(
            name=self.name,
            description="Local file system storage provider",
            storage_type=StorageType.FILE_SYSTEM,
            supports_async=True,
            supports_transactions=False,
            supports_schemas=False,
            supports_indexing=False,
            supports_search=True,  # Basic pattern matching
            supports_streaming=True,
            default_timeout=30.0,
            required_config=["base_path"],
            optional_config=["create_directories", "permissions", "max_file_size"],
            connection_string_template="file://{base_path}"
        )
    
    def _initialize(self):
        """Initialize file system-specific settings."""
        self.base_path = Path(self.config["base_path"]).resolve()
        self.config.setdefault("create_directories", True)
        self.config.setdefault("permissions", 0o644)
        self.config.setdefault("max_file_size", 100 * 1024 * 1024)  # 100MB default
        
        # Validate base path
        if not self.base_path.exists():
            if self.config["create_directories"]:
                self.base_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created base directory: {self.base_path}")
            else:
                raise StorageConfigurationError(
                    self.name,
                    f"Base path does not exist: {self.base_path}"
                )
        
        if not self.base_path.is_dir():
            raise StorageConfigurationError(
                self.name,
                f"Base path is not a directory: {self.base_path}"
            )
    
    async def connect(self) -> bool:
        """Verify file system access."""
        try:
            # Test write access
            test_file = self.base_path / ".praval_test"
            test_file.write_text("test")
            test_file.unlink()
            
            self.is_connected = True
            logger.info(f"Connected to file system: {self.base_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to access file system: {e}")
            raise StorageConnectionError(self.name, str(e))
    
    async def disconnect(self):
        """No explicit disconnection needed for file system."""
        self.is_connected = False
        logger.info(f"Disconnected from file system: {self.name}")
    
    def _resolve_path(self, resource: str) -> Path:
        """Resolve resource path relative to base path."""
        # Normalize path separators
        resource = resource.replace('\\', '/')
        
        # Remove leading slash
        if resource.startswith('/'):
            resource = resource[1:]
        
        resolved = (self.base_path / resource).resolve()
        
        # Security check: ensure path is within base directory
        try:
            resolved.relative_to(self.base_path)
        except ValueError:
            raise ValueError(f"Path '{resource}' is outside base directory")
        
        return resolved
    
    async def store(self, resource: str, data: Any, **kwargs) -> StorageResult:
        """
        Store data to file system.
        
        Args:
            resource: File path relative to base_path
            data: Data to store (string, bytes, dict/list for JSON, or file-like object)
            **kwargs: File parameters (encoding, mode, etc.)
            
        Returns:
            StorageResult with operation outcome
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            file_path = self._resolve_path(resource)
            
            # Create parent directories if needed
            if self.config["create_directories"]:
                file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Determine how to write the data
            if isinstance(data, (dict, list)):
                # JSON data
                content = json.dumps(data, indent=2)
                encoding = kwargs.get("encoding", "utf-8")
                file_path.write_text(content, encoding=encoding)
                content_type = "application/json"
                
            elif isinstance(data, str):
                # Text data
                encoding = kwargs.get("encoding", "utf-8")
                file_path.write_text(data, encoding=encoding)
                content_type = "text/plain"
                
            elif isinstance(data, bytes):
                # Binary data
                file_path.write_bytes(data)
                content_type = "application/octet-stream"
                
            elif hasattr(data, 'read'):
                # File-like object
                content_type = kwargs.get("content_type", "application/octet-stream")
                
                if hasattr(data, 'mode') and 'b' in data.mode:
                    # Binary file
                    with open(file_path, 'wb') as f:
                        shutil.copyfileobj(data, f)
                else:
                    # Text file
                    encoding = kwargs.get("encoding", "utf-8")
                    with open(file_path, 'w', encoding=encoding) as f:
                        shutil.copyfileobj(data, f)
            
            else:
                # Convert to string
                content = str(data)
                encoding = kwargs.get("encoding", "utf-8")
                file_path.write_text(content, encoding=encoding)
                content_type = "text/plain"
            
            # Set file permissions if specified
            if "permissions" in kwargs:
                file_path.chmod(kwargs["permissions"])
            
            # Get file stats
            stat = file_path.stat()
            
            return StorageResult(
                success=True,
                data={
                    "path": str(file_path.relative_to(self.base_path)),
                    "size": stat.st_size,
                    "created": True
                },
                metadata={
                    "operation": "write_file",
                    "content_type": content_type,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "permissions": oct(stat.st_mode)[-3:]
                },
                data_reference=DataReference(
                    provider=self.name,
                    storage_type=StorageType.FILE_SYSTEM,
                    resource_id=resource,
                    metadata={
                        "size": stat.st_size,
                        "content_type": content_type,
                        "full_path": str(file_path)
                    }
                )
            )
        
        except Exception as e:
            logger.error(f"Store operation failed: {e}")
            return StorageResult(
                success=False,
                error=f"Store operation failed: {str(e)}"
            )
    
    async def retrieve(self, resource: str, **kwargs) -> StorageResult:
        """
        Retrieve data from file system.
        
        Args:
            resource: File path relative to base_path
            **kwargs: Read parameters (encoding, decode_json, etc.)
            
        Returns:
            StorageResult with retrieved data
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            file_path = self._resolve_path(resource)
            
            if not file_path.exists():
                return StorageResult(
                    success=False,
                    error=f"File not found: {resource}"
                )
            
            if not file_path.is_file():
                return StorageResult(
                    success=False,
                    error=f"Path is not a file: {resource}"
                )
            
            # Determine content type from extension
            suffix = file_path.suffix.lower()
            if suffix in ['.json']:
                content_type = "application/json"
            elif suffix in ['.txt', '.md', '.csv']:
                content_type = "text/plain"
            elif suffix in ['.jpg', '.jpeg', '.png', '.gif']:
                content_type = f"image/{suffix[1:]}"
            else:
                content_type = "application/octet-stream"
            
            # Read data based on content type and parameters
            decode_json = kwargs.get("decode_json", content_type == "application/json")
            binary_mode = kwargs.get("binary", content_type.startswith("image/") or content_type == "application/octet-stream")
            
            if binary_mode:
                data = file_path.read_bytes()
            else:
                encoding = kwargs.get("encoding", "utf-8")
                data = file_path.read_text(encoding=encoding)
                
                if decode_json and (suffix == '.json' or content_type == "application/json"):
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        pass  # Keep as string if JSON parsing fails
            
            # Get file stats
            stat = file_path.stat()
            
            return StorageResult(
                success=True,
                data=data,
                metadata={
                    "operation": "read_file",
                    "path": resource,
                    "content_type": content_type,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "permissions": oct(stat.st_mode)[-3:]
                }
            )
        
        except Exception as e:
            logger.error(f"Retrieve operation failed: {e}")
            return StorageResult(
                success=False,
                error=f"Retrieve operation failed: {str(e)}"
            )
    
    async def query(self, resource: str, query: Union[str, Dict], **kwargs) -> StorageResult:
        """
        Execute file system operations.
        
        Args:
            resource: Path or pattern
            query: Query type ("list", "find", "metadata", etc.)
            **kwargs: Query parameters
            
        Returns:
            StorageResult with query results
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            if isinstance(query, str):
                if query == "list":
                    # List directory contents
                    dir_path = self._resolve_path(resource)
                    
                    if not dir_path.exists():
                        return StorageResult(
                            success=False,
                            error=f"Directory not found: {resource}"
                        )
                    
                    if not dir_path.is_dir():
                        return StorageResult(
                            success=False,
                            error=f"Path is not a directory: {resource}"
                        )
                    
                    items = []
                    for item in dir_path.iterdir():
                        stat = item.stat()
                        items.append({
                            "name": item.name,
                            "path": str(item.relative_to(self.base_path)),
                            "type": "directory" if item.is_dir() else "file",
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "permissions": oct(stat.st_mode)[-3:]
                        })
                    
                    return StorageResult(
                        success=True,
                        data=items,
                        metadata={"operation": "list_directory", "count": len(items)}
                    )
                
                elif query == "find":
                    # Find files matching pattern
                    pattern = kwargs.get("pattern", "*")
                    recursive = kwargs.get("recursive", False)
                    
                    base_dir = self._resolve_path(resource) if resource else self.base_path
                    
                    if recursive:
                        matches = list(base_dir.rglob(pattern))
                    else:
                        matches = list(base_dir.glob(pattern))
                    
                    items = []
                    for match in matches:
                        if match.is_file():
                            stat = match.stat()
                            items.append({
                                "name": match.name,
                                "path": str(match.relative_to(self.base_path)),
                                "size": stat.st_size,
                                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                "permissions": oct(stat.st_mode)[-3:]
                            })
                    
                    return StorageResult(
                        success=True,
                        data=items,
                        metadata={"operation": "find_files", "pattern": pattern, "count": len(items)}
                    )
                
                elif query == "metadata":
                    # Get file/directory metadata
                    path = self._resolve_path(resource)
                    
                    if not path.exists():
                        return StorageResult(
                            success=False,
                            error=f"Path not found: {resource}"
                        )
                    
                    stat = path.stat()
                    
                    return StorageResult(
                        success=True,
                        data={
                            "path": resource,
                            "type": "directory" if path.is_dir() else "file",
                            "size": stat.st_size,
                            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
                            "permissions": oct(stat.st_mode)[-3:],
                            "owner": stat.st_uid,
                            "group": stat.st_gid
                        },
                        metadata={"operation": "file_metadata"}
                    )
                
                elif query == "exists":
                    # Check if path exists
                    path = self._resolve_path(resource)
                    
                    return StorageResult(
                        success=True,
                        data={"exists": path.exists()},
                        metadata={"operation": "path_exists"}
                    )
                
                else:
                    raise ValueError(f"Unsupported query type: {query}")
            
            else:
                raise ValueError(f"Unsupported query format: {type(query)}")
        
        except Exception as e:
            logger.error(f"Query operation failed: {e}")
            return StorageResult(
                success=False,
                error=f"Query operation failed: {str(e)}"
            )
    
    async def delete(self, resource: str, **kwargs) -> StorageResult:
        """
        Delete file or directory from file system.
        
        Args:
            resource: Path to delete
            **kwargs: Delete parameters (recursive, etc.)
            
        Returns:
            StorageResult with operation outcome
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            path = self._resolve_path(resource)
            
            if not path.exists():
                return StorageResult(
                    success=False,
                    error=f"Path not found: {resource}"
                )
            
            if path.is_file():
                path.unlink()
                deleted_count = 1
                operation = "delete_file"
            
            elif path.is_dir():
                recursive = kwargs.get("recursive", False)
                
                if recursive:
                    shutil.rmtree(path)
                    deleted_count = 1  # Count as one directory
                    operation = "delete_directory_recursive"
                else:
                    # Only delete if empty
                    try:
                        path.rmdir()
                        deleted_count = 1
                        operation = "delete_directory"
                    except OSError as e:
                        return StorageResult(
                            success=False,
                            error=f"Directory not empty (use recursive=True): {e}"
                        )
            
            else:
                return StorageResult(
                    success=False,
                    error=f"Unknown path type: {resource}"
                )
            
            return StorageResult(
                success=True,
                data={"deleted": deleted_count},
                metadata={"operation": operation, "path": resource}
            )
        
        except Exception as e:
            logger.error(f"Delete operation failed: {e}")
            return StorageResult(
                success=False,
                error=f"Delete operation failed: {str(e)}"
            )
    
    async def list_resources(self, prefix: str = "", **kwargs) -> StorageResult:
        """List files and directories."""
        return await self.query(prefix or "", "list", **kwargs)