"""
Storage Registry System

Provides centralized registration, discovery, and management of storage
providers available to Praval agents. This follows the same pattern as
the tool registry for consistent framework design.
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set, Type, Any, Union
import threading
from datetime import datetime, timedelta
import asyncio

from .base_provider import BaseStorageProvider, StorageType, StorageQuery, StorageResult
from .exceptions import (
    StorageNotFoundError, StorageConfigurationError, 
    StoragePermissionError, StorageConnectionError
)

logger = logging.getLogger(__name__)


class StorageRegistry:
    """
    Central registry for managing storage providers available to agents.
    
    Features:
    - Provider registration and discovery
    - Type-based organization (relational, object, vector, etc.)
    - Access control and permissions
    - Connection pooling and lifecycle management
    - Usage statistics and health monitoring
    - Multi-provider query routing
    """
    
    def __init__(self):
        self._providers: Dict[str, BaseStorageProvider] = {}
        self._types: Dict[StorageType, Set[str]] = defaultdict(set)
        self._permissions: Dict[str, Set[str]] = defaultdict(set)  # provider_name -> agent_names
        self._usage_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._health_status: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        
        # Security and management settings
        self.security_enabled = True
        self.require_explicit_permissions = False
        self.blocked_providers: Set[str] = set()
        self.auto_connect = True
        self.health_check_interval = 300  # 5 minutes
        
        # Background tasks
        self._health_check_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.info("Storage registry initialized")
    
    async def register_provider(
        self, 
        provider: BaseStorageProvider, 
        replace_existing: bool = False,
        permissions: Optional[List[str]] = None,
        auto_connect: bool = None
    ) -> bool:
        """
        Register a storage provider in the registry.
        
        Args:
            provider: Provider instance to register
            replace_existing: Whether to replace existing provider with same name
            permissions: List of agent names allowed to use this provider
            auto_connect: Whether to auto-connect the provider
            
        Returns:
            True if registration successful, False otherwise
        """
        with self._lock:
            if provider.name in self._providers and not replace_existing:
                logger.warning(f"Provider '{provider.name}' already registered. Use replace_existing=True to override.")
                return False
            
            try:
                # Validate provider
                await self._validate_provider(provider)
                
                # Auto-connect if enabled
                should_connect = auto_connect if auto_connect is not None else self.auto_connect
                if should_connect:
                    connected = await provider.connect()
                    if not connected:
                        logger.warning(f"Failed to connect provider '{provider.name}' during registration")
                
                # Register the provider
                self._providers[provider.name] = provider
                self._types[provider.metadata.storage_type].add(provider.name)
                
                # Set permissions
                if permissions:
                    self._permissions[provider.name] = set(permissions)
                
                # Initialize usage statistics
                self._usage_stats[provider.name] = {
                    "registered_at": datetime.now(),
                    "total_operations": 0,
                    "successful_operations": 0,
                    "failed_operations": 0,
                    "total_execution_time": 0.0,
                    "avg_execution_time": 0.0,
                    "last_used": None,
                    "connections_made": 0,
                    "health_checks": 0
                }
                
                # Initialize health status
                self._health_status[provider.name] = await provider.health_check()
                
                logger.info(f"Provider '{provider.name}' registered successfully (type: {provider.metadata.storage_type.value})")
                return True
                
            except Exception as e:
                logger.error(f"Failed to register provider '{provider.name}': {e}")
                return False
    
    async def _validate_provider(self, provider: BaseStorageProvider):
        """Validate provider before registration."""
        if not isinstance(provider, BaseStorageProvider):
            raise StorageConfigurationError(
                provider.name,
                "Provider must inherit from BaseStorageProvider"
            )
        
        if not provider.name or not isinstance(provider.name, str):
            raise StorageConfigurationError(
                getattr(provider, 'name', 'unknown'),
                "Provider must have a valid string name"
            )
        
        # Test basic functionality
        try:
            schema = provider.get_schema()
            if not schema or not isinstance(schema, dict):
                raise StorageConfigurationError(
                    provider.name,
                    "Provider must return valid schema"
                )
        except Exception as e:
            raise StorageConfigurationError(
                provider.name,
                f"Provider schema validation failed: {e}"
            )
    
    async def unregister_provider(self, provider_name: str) -> bool:
        """
        Unregister a provider from the registry.
        
        Args:
            provider_name: Name of provider to unregister
            
        Returns:
            True if unregistration successful, False if provider not found
        """
        with self._lock:
            if provider_name not in self._providers:
                logger.warning(f"Provider '{provider_name}' not found for unregistration")
                return False
            
            provider = self._providers[provider_name]
            
            try:
                # Disconnect provider
                await provider.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting provider '{provider_name}': {e}")
            
            # Remove from main registry
            del self._providers[provider_name]
            
            # Remove from type mapping
            self._types[provider.metadata.storage_type].discard(provider_name)
            if not self._types[provider.metadata.storage_type]:
                del self._types[provider.metadata.storage_type]
            
            # Clean up metadata
            self._permissions.pop(provider_name, None)
            self._usage_stats.pop(provider_name, None)
            self._health_status.pop(provider_name, None)
            
            logger.info(f"Provider '{provider_name}' unregistered successfully")
            return True
    
    def get_provider(self, provider_name: str, agent_name: str = None) -> BaseStorageProvider:
        """
        Get a provider by name with permission checking.
        
        Args:
            provider_name: Name of the provider to retrieve
            agent_name: Name of the agent requesting the provider
            
        Returns:
            BaseStorageProvider instance
            
        Raises:
            StorageNotFoundError: If provider not found
            StoragePermissionError: If agent lacks permission
        """
        with self._lock:
            if provider_name not in self._providers:
                raise StorageNotFoundError(
                    provider_name, 
                    available_resources=list(self._providers.keys())
                )
            
            # Check if provider is blocked
            if provider_name in self.blocked_providers:
                raise StoragePermissionError(
                    "access", provider_name, 
                    f"Provider '{provider_name}' is currently blocked"
                )
            
            # Check permissions if security is enabled
            if self.security_enabled and agent_name:
                if not self._check_permission(provider_name, agent_name):
                    raise StoragePermissionError(
                        "access", provider_name,
                        f"Agent '{agent_name}' lacks permission to use provider '{provider_name}'"
                    )
            
            return self._providers[provider_name]
    
    def _check_permission(self, provider_name: str, agent_name: str) -> bool:
        """Check if agent has permission to use provider."""
        # If no explicit permissions set and not requiring explicit permissions, allow
        if not self.require_explicit_permissions and provider_name not in self._permissions:
            return True
        
        # Check explicit permissions
        allowed_agents = self._permissions.get(provider_name, set())
        return agent_name in allowed_agents or "*" in allowed_agents
    
    def list_providers(
        self, 
        storage_type: Optional[StorageType] = None,
        agent_name: Optional[str] = None,
        connected_only: bool = False
    ) -> List[str]:
        """
        List available providers with optional filtering.
        
        Args:
            storage_type: Filter by storage type
            agent_name: Filter by agent permissions
            connected_only: Only return connected providers
            
        Returns:
            List of provider names
        """
        with self._lock:
            providers = set(self._providers.keys())
            
            # Filter by storage type
            if storage_type:
                providers &= self._types.get(storage_type, set())
            
            # Filter by permissions
            if agent_name and self.security_enabled:
                permitted_providers = set()
                for provider_name in providers:
                    if self._check_permission(provider_name, agent_name):
                        permitted_providers.add(provider_name)
                providers = permitted_providers
            
            # Filter by connection status
            if connected_only:
                connected_providers = set()
                for provider_name in providers:
                    if self._providers[provider_name].is_connected:
                        connected_providers.add(provider_name)
                providers = connected_providers
            
            # Remove blocked providers
            providers -= self.blocked_providers
            
            return sorted(list(providers))
    
    def get_providers_by_type(self, storage_type: StorageType) -> List[str]:
        """Get all providers of a specific storage type."""
        with self._lock:
            return sorted(list(self._types.get(storage_type, set())))
    
    def get_storage_types(self) -> List[StorageType]:
        """Get list of all available storage types."""
        with self._lock:
            return sorted(list(self._types.keys()), key=lambda x: x.value)
    
    async def execute_query(
        self, 
        provider_name: str, 
        query: StorageQuery,
        agent_name: Optional[str] = None
    ) -> StorageResult:
        """
        Execute a query on a specific provider.
        
        Args:
            provider_name: Name of provider to query
            query: Query to execute
            agent_name: Name of requesting agent
            
        Returns:
            StorageResult with query outcome
        """
        provider = self.get_provider(provider_name, agent_name)
        
        # Update usage statistics
        start_time = datetime.now()
        
        try:
            # Execute the query
            if query.operation == "store":
                result = await provider.store(query.resource, query.parameters.get("data"), **query.parameters)
            elif query.operation == "retrieve":
                result = await provider.retrieve(query.resource, **query.parameters)
            elif query.operation == "query":
                result = await provider.query(query.resource, query.parameters.get("query"), **query.parameters)
            elif query.operation == "delete":
                result = await provider.delete(query.resource, **query.parameters)
            else:
                result = await provider.safe_execute(query.operation, query.resource, **query.parameters)
            
            # Update statistics
            await self._update_usage_stats(provider_name, start_time, True)
            
            return result
            
        except Exception as e:
            logger.error(f"Query execution failed on provider '{provider_name}': {e}")
            await self._update_usage_stats(provider_name, start_time, False)
            
            return StorageResult(
                success=False,
                error=f"Query execution failed: {str(e)}",
                execution_time=(datetime.now() - start_time).total_seconds()
            )
    
    async def _update_usage_stats(self, provider_name: str, start_time: datetime, success: bool):
        """Update usage statistics for a provider."""
        if provider_name not in self._usage_stats:
            return
        
        execution_time = (datetime.now() - start_time).total_seconds()
        stats = self._usage_stats[provider_name]
        
        stats["total_operations"] += 1
        stats["total_execution_time"] += execution_time
        stats["last_used"] = datetime.now()
        
        if success:
            stats["successful_operations"] += 1
        else:
            stats["failed_operations"] += 1
        
        # Update average execution time
        stats["avg_execution_time"] = stats["total_execution_time"] / stats["total_operations"]
    
    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Perform health checks on all registered providers."""
        health_results = {}
        
        for provider_name, provider in self._providers.items():
            try:
                health_results[provider_name] = await provider.health_check()
                self._health_status[provider_name] = health_results[provider_name]
                
                # Update stats
                if provider_name in self._usage_stats:
                    self._usage_stats[provider_name]["health_checks"] += 1
                    
            except Exception as e:
                health_results[provider_name] = {
                    "provider": provider_name,
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                logger.error(f"Health check failed for provider '{provider_name}': {e}")
        
        return health_results
    
    def get_usage_stats(self, provider_name: Optional[str] = None) -> Union[Dict[str, Any], Dict[str, Dict[str, Any]]]:
        """Get usage statistics for providers."""
        with self._lock:
            if provider_name:
                if provider_name not in self._usage_stats:
                    raise StorageNotFoundError(provider_name)
                return dict(self._usage_stats[provider_name])
            else:
                return {name: dict(stats) for name, stats in self._usage_stats.items()}
    
    def get_registry_info(self) -> Dict[str, Any]:
        """Get comprehensive information about the registry."""
        with self._lock:
            return {
                "total_providers": len(self._providers),
                "storage_types": {st.value: list(providers) for st, providers in self._types.items()},
                "blocked_providers": list(self.blocked_providers),
                "security_enabled": self.security_enabled,
                "require_explicit_permissions": self.require_explicit_permissions,
                "providers_with_permissions": len(self._permissions),
                "connected_providers": sum(1 for p in self._providers.values() if p.is_connected),
                "registry_statistics": {
                    "total_operations": sum(stats["total_operations"] for stats in self._usage_stats.values()),
                    "successful_operations": sum(stats["successful_operations"] for stats in self._usage_stats.values()),
                    "failed_operations": sum(stats["failed_operations"] for stats in self._usage_stats.values()),
                    "total_execution_time": sum(stats["total_execution_time"] for stats in self._usage_stats.values())
                }
            }
    
    # Permission management methods
    def set_permissions(self, provider_name: str, agent_names: List[str]):
        """Set permissions for a provider."""
        with self._lock:
            if provider_name not in self._providers:
                raise StorageNotFoundError(provider_name)
            
            self._permissions[provider_name] = set(agent_names)
            logger.info(f"Updated permissions for provider '{provider_name}': {agent_names}")
    
    def add_permission(self, provider_name: str, agent_name: str):
        """Add permission for an agent to use a provider."""
        with self._lock:
            if provider_name not in self._providers:
                raise StorageNotFoundError(provider_name)
            
            self._permissions[provider_name].add(agent_name)
            logger.info(f"Added permission for agent '{agent_name}' to use provider '{provider_name}'")
    
    def remove_permission(self, provider_name: str, agent_name: str):
        """Remove permission for an agent to use a provider."""
        with self._lock:
            if provider_name not in self._providers:
                raise StorageNotFoundError(provider_name)
            
            self._permissions[provider_name].discard(agent_name)
            logger.info(f"Removed permission for agent '{agent_name}' to use provider '{provider_name}'")
    
    def block_provider(self, provider_name: str):
        """Block a provider from being used."""
        with self._lock:
            self.blocked_providers.add(provider_name)
            logger.warning(f"Provider '{provider_name}' has been blocked")
    
    def unblock_provider(self, provider_name: str):
        """Unblock a previously blocked provider."""
        with self._lock:
            self.blocked_providers.discard(provider_name)
            logger.info(f"Provider '{provider_name}' has been unblocked")
    
    async def cleanup_registry(self):
        """Clean up disconnected providers and expired data."""
        with self._lock:
            disconnected_providers = []
            for name, provider in self._providers.items():
                if not provider.is_connected:
                    try:
                        # Try to reconnect
                        await provider.connect()
                    except Exception:
                        disconnected_providers.append(name)
            
            for name in disconnected_providers:
                logger.warning(f"Provider '{name}' remains disconnected after cleanup attempt")


# Global registry instance
_global_storage_registry: Optional[StorageRegistry] = None
_storage_registry_lock = threading.Lock()


def get_storage_registry() -> StorageRegistry:
    """Get the global storage registry instance."""
    global _global_storage_registry
    
    if _global_storage_registry is None:
        with _storage_registry_lock:
            if _global_storage_registry is None:
                _global_storage_registry = StorageRegistry()
    
    return _global_storage_registry


async def register_storage_provider(provider: BaseStorageProvider, **kwargs) -> bool:
    """Register a storage provider in the global registry."""
    return await get_storage_registry().register_provider(provider, **kwargs)


def get_storage_provider(provider_name: str, agent_name: str = None) -> BaseStorageProvider:
    """Get a storage provider from the global registry."""
    return get_storage_registry().get_provider(provider_name, agent_name)


def list_storage_providers(**kwargs) -> List[str]:
    """List available storage providers from the global registry."""
    return get_storage_registry().list_providers(**kwargs)