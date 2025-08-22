"""
Praval Storage System

Unified data storage and retrieval capabilities for agents, providing seamless
access to various storage backends through a consistent interface.

Key Components:
- Storage provider abstractions and implementations
- Storage registry for discovery and management
- Agent integration through decorators
- Data reference system for spore communication
- Memory-storage integration
"""

from .base_provider import (
    BaseStorageProvider, StorageMetadata, StorageQuery, 
    StorageResult, DataReference, StorageType
)
from .storage_registry import StorageRegistry, get_storage_registry
from .providers import (
    PostgreSQLProvider, S3Provider, RedisProvider, 
    FileSystemProvider, QdrantProvider
)
from .decorators import storage_enabled, requires_storage
from .data_manager import DataManager, get_data_manager
from .exceptions import (
    StorageError, StorageNotFoundError, StorageConnectionError,
    StoragePermissionError, StorageTimeoutError
)

# Availability flag for optional dependencies
STORAGE_AVAILABLE = True

__all__ = [
    # Core framework
    "BaseStorageProvider", "StorageMetadata", "StorageQuery", 
    "StorageResult", "DataReference", "StorageType",
    
    # Registry and management
    "StorageRegistry", "get_storage_registry",
    "DataManager", "get_data_manager",
    
    # Built-in providers
    "PostgreSQLProvider", "S3Provider", "RedisProvider",
    "FileSystemProvider", "QdrantProvider",
    
    # Decorators
    "storage_enabled", "requires_storage",
    
    # Exceptions
    "StorageError", "StorageNotFoundError", "StorageConnectionError",
    "StoragePermissionError", "StorageTimeoutError",
    
    # Availability flag
    "STORAGE_AVAILABLE"
]