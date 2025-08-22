"""
Base Storage Provider Framework

Defines the core interfaces and base classes for all Praval storage providers.
This provides a standardized way to create, register, and use storage backends
that agents can access uniformly.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Type
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class StorageType(Enum):
    """Types of storage backends"""
    RELATIONAL = "relational"      # PostgreSQL, MySQL, SQLite
    DOCUMENT = "document"          # MongoDB, CouchDB
    KEY_VALUE = "key_value"        # Redis, DynamoDB
    OBJECT = "object"              # S3, MinIO, Azure Blob
    VECTOR = "vector"              # Qdrant, Pinecone, Weaviate
    SEARCH = "search"              # Elasticsearch, Solr
    GRAPH = "graph"                # Neo4j, Amazon Neptune
    FILE_SYSTEM = "file_system"    # Local files, NFS, HDFS
    CACHE = "cache"                # Redis, Memcached
    QUEUE = "queue"                # RabbitMQ, Kafka, SQS


@dataclass
class DataReference:
    """Reference to data stored in a backend"""
    provider: str
    storage_type: StorageType
    resource_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    def to_uri(self) -> str:
        """Convert to URI format for spore communication"""
        return f"{self.provider}://{self.storage_type.value}/{self.resource_id}"
    
    @classmethod
    def from_uri(cls, uri: str) -> 'DataReference':
        """Create DataReference from URI"""
        parsed = urlparse(uri)
        provider = parsed.scheme
        storage_type = StorageType(parsed.path.split('/')[1])
        resource_id = '/'.join(parsed.path.split('/')[2:])
        
        return cls(
            provider=provider,
            storage_type=storage_type,
            resource_id=resource_id
        )
    
    def is_expired(self) -> bool:
        """Check if reference has expired"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


@dataclass
class StorageQuery:
    """Query parameters for storage operations"""
    operation: str  # "get", "set", "query", "search", "delete", etc.
    resource: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    filters: Dict[str, Any] = field(default_factory=dict)
    limit: Optional[int] = None
    offset: Optional[int] = None
    timeout: Optional[float] = None


@dataclass
class StorageResult:
    """Result from storage operation"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    data_reference: Optional[DataReference] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StorageMetadata:
    """Metadata describing a storage provider's capabilities"""
    name: str
    description: str
    storage_type: StorageType
    version: str = "1.0.0"
    supports_async: bool = True
    supports_transactions: bool = False
    supports_schemas: bool = False
    supports_indexing: bool = False
    supports_search: bool = False
    supports_streaming: bool = False
    max_connection_pool: int = 10
    default_timeout: float = 30.0
    required_config: List[str] = field(default_factory=list)
    optional_config: List[str] = field(default_factory=list)
    connection_string_template: Optional[str] = None


class BaseStorageProvider(ABC):
    """
    Abstract base class for all storage providers.
    
    All storage backends must inherit from this class and implement the
    required methods. This ensures a consistent interface across all
    storage types while allowing for provider-specific optimizations.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Initialize the storage provider.
        
        Args:
            name: Unique name for this provider instance
            config: Provider-specific configuration
        """
        self.name = name
        self.config = config
        self.metadata = self._create_metadata()
        self.is_connected = False
        self.connection_pool = None
        self.call_count = 0
        self.last_used = None
        
        # Validate configuration
        self._validate_config()
        
        # Initialize provider-specific setup
        self._initialize()
    
    def _create_metadata(self) -> StorageMetadata:
        """Create metadata for this provider. Override in subclasses."""
        return StorageMetadata(
            name=self.name,
            description=f"{self.__class__.__name__} storage provider",
            storage_type=StorageType.KEY_VALUE  # Default, override in subclasses
        )
    
    def _validate_config(self):
        """Validate provider configuration."""
        required = set(self.metadata.required_config)
        provided = set(self.config.keys())
        missing = required - provided
        
        if missing:
            raise ValueError(f"Missing required configuration: {missing}")
    
    def _initialize(self):
        """Perform provider-specific initialization. Override in subclasses."""
        pass
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the storage backend.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Close connection to the storage backend."""
        pass
    
    @abstractmethod
    async def store(self, resource: str, data: Any, **kwargs) -> StorageResult:
        """
        Store data in the backend.
        
        Args:
            resource: Resource identifier (table, bucket, key, etc.)
            data: Data to store
            **kwargs: Provider-specific parameters
            
        Returns:
            StorageResult with operation outcome
        """
        pass
    
    @abstractmethod
    async def retrieve(self, resource: str, **kwargs) -> StorageResult:
        """
        Retrieve data from the backend.
        
        Args:
            resource: Resource identifier
            **kwargs: Provider-specific parameters
            
        Returns:
            StorageResult with retrieved data
        """
        pass
    
    @abstractmethod
    async def query(self, resource: str, query: Union[str, Dict], **kwargs) -> StorageResult:
        """
        Execute a query against the backend.
        
        Args:
            resource: Resource to query
            query: Query string or structured query
            **kwargs: Provider-specific parameters
            
        Returns:
            StorageResult with query results
        """
        pass
    
    @abstractmethod
    async def delete(self, resource: str, **kwargs) -> StorageResult:
        """
        Delete data from the backend.
        
        Args:
            resource: Resource to delete
            **kwargs: Provider-specific parameters
            
        Returns:
            StorageResult with operation outcome
        """
        pass
    
    async def exists(self, resource: str, **kwargs) -> bool:
        """
        Check if a resource exists.
        
        Args:
            resource: Resource to check
            **kwargs: Provider-specific parameters
            
        Returns:
            True if resource exists, False otherwise
        """
        try:
            result = await self.retrieve(resource, **kwargs)
            return result.success
        except Exception:
            return False
    
    async def list_resources(self, prefix: str = "", **kwargs) -> StorageResult:
        """
        List available resources.
        
        Args:
            prefix: Resource prefix to filter by
            **kwargs: Provider-specific parameters
            
        Returns:
            StorageResult with list of resources
        """
        # Default implementation - override for better performance
        return StorageResult(
            success=False,
            error="list_resources not implemented for this provider"
        )
    
    async def safe_execute(self, operation: str, *args, **kwargs) -> StorageResult:
        """
        Execute operation with error handling and timing.
        
        Args:
            operation: Operation name
            *args, **kwargs: Operation parameters
            
        Returns:
            StorageResult with operation outcome
        """
        start_time = time.time()
        
        try:
            # Ensure connection
            if not self.is_connected:
                await self.connect()
            
            # Get operation method
            method = getattr(self, operation, None)
            if method is None:
                return StorageResult(
                    success=False,
                    error=f"Operation '{operation}' not supported",
                    execution_time=time.time() - start_time
                )
            
            # Execute with timeout
            timeout = kwargs.pop('timeout', self.metadata.default_timeout)
            result = await asyncio.wait_for(
                method(*args, **kwargs),
                timeout=timeout
            )
            
            # Update usage statistics
            self.call_count += 1
            self.last_used = datetime.now()
            
            return result
        
        except asyncio.TimeoutError:
            return StorageResult(
                success=False,
                error=f"Operation '{operation}' timed out after {timeout} seconds",
                execution_time=time.time() - start_time
            )
        except Exception as e:
            logger.error(f"Storage operation failed in {self.name}: {e}")
            return StorageResult(
                success=False,
                error=f"Operation failed: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def get_schema(self) -> Dict[str, Any]:
        """Get provider schema/capabilities."""
        return {
            "name": self.metadata.name,
            "description": self.metadata.description,
            "storage_type": self.metadata.storage_type.value,
            "version": self.metadata.version,
            "capabilities": {
                "async": self.metadata.supports_async,
                "transactions": self.metadata.supports_transactions,
                "schemas": self.metadata.supports_schemas,
                "indexing": self.metadata.supports_indexing,
                "search": self.metadata.supports_search,
                "streaming": self.metadata.supports_streaming
            },
            "configuration": {
                "required": self.metadata.required_config,
                "optional": self.metadata.optional_config,
                "connection_template": self.metadata.connection_string_template
            },
            "limits": {
                "max_connections": self.metadata.max_connection_pool,
                "default_timeout": self.metadata.default_timeout
            }
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the storage backend."""
        start_time = time.time()
        
        try:
            # Try a simple operation
            await self.connect()
            health_status = "healthy"
            error = None
        except Exception as e:
            health_status = "unhealthy"
            error = str(e)
        
        return {
            "provider": self.name,
            "storage_type": self.metadata.storage_type.value,
            "status": health_status,
            "response_time": time.time() - start_time,
            "is_connected": self.is_connected,
            "call_count": self.call_count,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "error": error
        }
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}', type='{self.metadata.storage_type.value}')>"


# Helper function to create simple storage providers
def create_storage_provider(
    provider_class: Type[BaseStorageProvider],
    name: str,
    config: Dict[str, Any]
) -> BaseStorageProvider:
    """
    Create a storage provider instance.
    
    Args:
        provider_class: Provider class to instantiate
        name: Provider instance name
        config: Provider configuration
        
    Returns:
        Configured provider instance
    """
    return provider_class(name, config)