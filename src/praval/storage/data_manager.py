"""
Data Manager - Unified interface for storage operations

Provides a high-level interface for agents to interact with multiple
storage providers through a single, consistent API.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
import threading

from .storage_registry import get_storage_registry, StorageRegistry
from .base_provider import BaseStorageProvider, StorageQuery, StorageResult, DataReference
from .exceptions import StorageNotFoundError, StorageConfigurationError

logger = logging.getLogger(__name__)


class DataManager:
    """
    Unified data management interface for agents.
    
    Provides high-level methods for storing, retrieving, and querying data
    across multiple storage backends through a single interface.
    
    Features:
    - Automatic provider selection based on data type
    - Cross-provider queries and operations
    - Data reference management for spore communication
    - Storage optimization and caching
    - Transaction-like operations across providers
    """
    
    def __init__(self, registry: Optional[StorageRegistry] = None):
        """
        Initialize data manager.
        
        Args:
            registry: Storage registry to use (defaults to global registry)
        """
        self.registry = registry or get_storage_registry()
        self._agent_context = threading.local()
    
    def set_agent_context(self, agent_name: str):
        """Set the current agent context for permission checking."""
        self._agent_context.agent_name = agent_name
    
    def get_agent_context(self) -> Optional[str]:
        """Get the current agent context."""
        return getattr(self._agent_context, 'agent_name', None)
    
    # High-level storage operations
    
    async def store(self, 
                   provider: str, 
                   resource: str, 
                   data: Any, 
                   **kwargs) -> StorageResult:
        """
        Store data in a specific provider.
        
        Args:
            provider: Storage provider name
            resource: Resource identifier (table, key, path, etc.)
            data: Data to store
            **kwargs: Provider-specific parameters
            
        Returns:
            StorageResult with operation outcome
        """
        storage_provider = self._get_provider(provider)
        return await storage_provider.store(resource, data, **kwargs)
    
    async def get(self, 
                  provider: str, 
                  resource: str, 
                  **kwargs) -> StorageResult:
        """
        Retrieve data from a specific provider.
        
        Args:
            provider: Storage provider name
            resource: Resource identifier
            **kwargs: Provider-specific parameters
            
        Returns:
            StorageResult with retrieved data
        """
        storage_provider = self._get_provider(provider)
        return await storage_provider.retrieve(resource, **kwargs)
    
    async def query(self, 
                    provider: str, 
                    resource: str, 
                    query: Union[str, Dict], 
                    **kwargs) -> StorageResult:
        """
        Execute a query on a specific provider.
        
        Args:
            provider: Storage provider name
            resource: Resource to query
            query: Query string or structured query
            **kwargs: Query parameters
            
        Returns:
            StorageResult with query results
        """
        storage_provider = self._get_provider(provider)
        return await storage_provider.query(resource, query, **kwargs)
    
    async def delete(self, 
                     provider: str, 
                     resource: str, 
                     **kwargs) -> StorageResult:
        """
        Delete data from a specific provider.
        
        Args:
            provider: Storage provider name
            resource: Resource to delete
            **kwargs: Delete parameters
            
        Returns:
            StorageResult with operation outcome
        """
        storage_provider = self._get_provider(provider)
        return await storage_provider.delete(resource, **kwargs)
    
    # Smart storage operations
    
    async def smart_store(self, 
                          data: Any, 
                          resource: Optional[str] = None,
                          preferred_provider: Optional[str] = None,
                          **kwargs) -> StorageResult:
        """
        Intelligently store data by selecting the best provider.
        
        Args:
            data: Data to store
            resource: Optional resource identifier
            preferred_provider: Preferred storage provider
            **kwargs: Storage parameters
            
        Returns:
            StorageResult with operation outcome
        """
        if preferred_provider:
            provider_name = preferred_provider
        else:
            provider_name = self._select_optimal_provider(data, "store")
        
        if not resource:
            resource = self._generate_resource_id(data, provider_name)
        
        return await self.store(provider_name, resource, data, **kwargs)
    
    async def smart_search(self, 
                           query: Union[str, List[float], Dict], 
                           providers: Optional[List[str]] = None,
                           **kwargs) -> List[StorageResult]:
        """
        Search across multiple providers intelligently.
        
        Args:
            query: Search query (text, vector, or structured)
            providers: Providers to search (defaults to all suitable)
            **kwargs: Search parameters
            
        Returns:
            List of StorageResult from different providers
        """
        if providers is None:
            providers = self._select_search_providers(query)
        
        results = []
        for provider_name in providers:
            try:
                result = await self._execute_search(provider_name, query, **kwargs)
                if result.success:
                    results.append(result)
            except Exception as e:
                logger.warning(f"Search failed on provider {provider_name}: {e}")
        
        return results
    
    # Data reference operations
    
    def create_data_reference(self, 
                             provider: str, 
                             resource: str, 
                             **metadata) -> DataReference:
        """
        Create a data reference for spore communication.
        
        Args:
            provider: Storage provider name
            resource: Resource identifier
            **metadata: Additional metadata
            
        Returns:
            DataReference object
        """
        storage_provider = self._get_provider(provider)
        
        return DataReference(
            provider=provider,
            storage_type=storage_provider.metadata.storage_type,
            resource_id=resource,
            metadata=metadata
        )
    
    async def resolve_data_reference(self, 
                                    data_ref: Union[DataReference, str],
                                    **kwargs) -> StorageResult:
        """
        Resolve a data reference to actual data.
        
        Args:
            data_ref: DataReference object or URI string
            **kwargs: Retrieval parameters
            
        Returns:
            StorageResult with resolved data
        """
        if isinstance(data_ref, str):
            data_ref = DataReference.from_uri(data_ref)
        
        # Check if reference has expired
        if data_ref.is_expired():
            return StorageResult(
                success=False,
                error="Data reference has expired"
            )
        
        return await self.get(data_ref.provider, data_ref.resource_id, **kwargs)
    
    # Batch operations
    
    async def batch_store(self, 
                          operations: List[Dict[str, Any]]) -> List[StorageResult]:
        """
        Execute multiple store operations in batch.
        
        Args:
            operations: List of operation dictionaries with keys:
                - provider: Storage provider name
                - resource: Resource identifier
                - data: Data to store
                - kwargs: Additional parameters
                
        Returns:
            List of StorageResult objects
        """
        results = []
        
        for op in operations:
            try:
                result = await self.store(
                    op["provider"],
                    op["resource"], 
                    op["data"],
                    **op.get("kwargs", {})
                )
                results.append(result)
            except Exception as e:
                results.append(StorageResult(
                    success=False,
                    error=f"Batch operation failed: {str(e)}"
                ))
        
        return results
    
    async def batch_get(self, 
                        operations: List[Dict[str, Any]]) -> List[StorageResult]:
        """
        Execute multiple get operations in batch.
        
        Args:
            operations: List of operation dictionaries with keys:
                - provider: Storage provider name
                - resource: Resource identifier  
                - kwargs: Additional parameters
                
        Returns:
            List of StorageResult objects
        """
        results = []
        
        for op in operations:
            try:
                result = await self.get(
                    op["provider"],
                    op["resource"],
                    **op.get("kwargs", {})
                )
                results.append(result)
            except Exception as e:
                results.append(StorageResult(
                    success=False,
                    error=f"Batch operation failed: {str(e)}"
                ))
        
        return results
    
    # Provider management
    
    def list_providers(self, storage_type: Optional[str] = None) -> List[str]:
        """
        List available storage providers.
        
        Args:
            storage_type: Filter by storage type
            
        Returns:
            List of provider names
        """
        from .base_provider import StorageType
        
        storage_type_enum = None
        if storage_type:
            try:
                storage_type_enum = StorageType(storage_type)
            except ValueError:
                logger.warning(f"Unknown storage type: {storage_type}")
        
        return self.registry.list_providers(
            storage_type=storage_type_enum,
            agent_name=self.get_agent_context()
        )
    
    def get_provider_info(self, provider: str) -> Dict[str, Any]:
        """
        Get information about a storage provider.
        
        Args:
            provider: Storage provider name
            
        Returns:
            Provider information dictionary
        """
        storage_provider = self._get_provider(provider)
        return storage_provider.get_schema()
    
    async def health_check(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform health check on providers.
        
        Args:
            provider: Specific provider to check (None for all)
            
        Returns:
            Health check results
        """
        if provider:
            storage_provider = self._get_provider(provider)
            return await storage_provider.health_check()
        else:
            return await self.registry.health_check_all()
    
    # Private helper methods
    
    def _get_provider(self, provider_name: str) -> BaseStorageProvider:
        """Get storage provider with permission checking."""
        return self.registry.get_provider(provider_name, self.get_agent_context())
    
    def _select_optimal_provider(self, data: Any, operation: str) -> str:
        """Select the best storage provider for given data and operation."""
        from .base_provider import StorageType
        
        # Simple heuristics for provider selection
        if isinstance(data, dict) and "vector" in data:
            # Vector data - prefer vector databases
            vector_providers = self.registry.get_providers_by_type(StorageType.VECTOR)
            if vector_providers:
                return vector_providers[0]
        
        if isinstance(data, (dict, list)) and len(str(data)) > 1024:
            # Large structured data - prefer object storage
            object_providers = self.registry.get_providers_by_type(StorageType.OBJECT)
            if object_providers:
                return object_providers[0]
        
        if isinstance(data, dict) and any(key in data for key in ["id", "name", "email"]):
            # Structured record - prefer relational database
            relational_providers = self.registry.get_providers_by_type(StorageType.RELATIONAL)
            if relational_providers:
                return relational_providers[0]
        
        if operation in ["get", "set"] and isinstance(data, (str, int, float)):
            # Simple key-value - prefer cache/key-value store
            kv_providers = self.registry.get_providers_by_type(StorageType.KEY_VALUE)
            if kv_providers:
                return kv_providers[0]
        
        # Default to first available provider
        available_providers = self.list_providers()
        if available_providers:
            return available_providers[0]
        
        raise StorageConfigurationError("", "No storage providers available")
    
    def _select_search_providers(self, query: Union[str, List[float], Dict]) -> List[str]:
        """Select providers suitable for search based on query type."""
        from .base_provider import StorageType
        
        suitable_providers = []
        
        if isinstance(query, list) and all(isinstance(x, (int, float)) for x in query):
            # Vector query - use vector databases
            suitable_providers.extend(self.registry.get_providers_by_type(StorageType.VECTOR))
        
        if isinstance(query, str):
            # Text query - use search engines, full-text capable databases
            suitable_providers.extend(self.registry.get_providers_by_type(StorageType.SEARCH))
            suitable_providers.extend(self.registry.get_providers_by_type(StorageType.RELATIONAL))
        
        if isinstance(query, dict):
            # Structured query - use databases
            suitable_providers.extend(self.registry.get_providers_by_type(StorageType.RELATIONAL))
            suitable_providers.extend(self.registry.get_providers_by_type(StorageType.DOCUMENT))
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(suitable_providers))
    
    def _generate_resource_id(self, data: Any, provider_name: str) -> str:
        """Generate appropriate resource ID based on data and provider."""
        import hashlib
        import time
        
        # Simple resource ID generation
        if hasattr(data, 'get') and 'id' in data:
            return str(data['id'])
        
        # Generate based on content hash and timestamp
        content_str = str(data)[:1000]  # Limit to avoid huge strings
        hash_obj = hashlib.md5(content_str.encode())
        timestamp = int(time.time())
        
        return f"{provider_name}_{timestamp}_{hash_obj.hexdigest()[:8]}"
    
    async def _execute_search(self, provider_name: str, query: Any, **kwargs) -> StorageResult:
        """Execute search on a specific provider."""
        storage_provider = self._get_provider(provider_name)
        
        if isinstance(query, list) and all(isinstance(x, (int, float)) for x in query):
            # Vector search
            return await storage_provider.query("", "search", vector=query, **kwargs)
        
        elif isinstance(query, str):
            # Text search
            return await storage_provider.query("", query, **kwargs)
        
        else:
            # Structured query
            return await storage_provider.query("", query, **kwargs)


# Global data manager instance
_global_data_manager: Optional[DataManager] = None
_data_manager_lock = threading.Lock()


def get_data_manager() -> DataManager:
    """Get the global data manager instance."""
    global _global_data_manager
    
    if _global_data_manager is None:
        with _data_manager_lock:
            if _global_data_manager is None:
                _global_data_manager = DataManager()
    
    return _global_data_manager


# Convenience functions for common operations
async def store_data(provider: str, resource: str, data: Any, **kwargs) -> StorageResult:
    """Store data using the global data manager."""
    return await get_data_manager().store(provider, resource, data, **kwargs)


async def get_data(provider: str, resource: str, **kwargs) -> StorageResult:
    """Retrieve data using the global data manager."""
    return await get_data_manager().get(provider, resource, **kwargs)


async def query_data(provider: str, resource: str, query: Union[str, Dict], **kwargs) -> StorageResult:
    """Query data using the global data manager."""
    return await get_data_manager().query(provider, resource, query, **kwargs)


async def delete_data(provider: str, resource: str, **kwargs) -> StorageResult:
    """Delete data using the global data manager."""
    return await get_data_manager().delete(provider, resource, **kwargs)