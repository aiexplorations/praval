"""
Storage decorators for Praval agents

Provides decorator-based integration between agents and storage providers,
following the same patterns as the agent and tool decorators.
"""

import asyncio
import logging
from functools import wraps
from typing import Dict, Any, List, Optional, Union, Callable
import inspect

from .storage_registry import get_storage_registry
from .data_manager import get_data_manager
from .exceptions import StorageNotFoundError, StorageConfigurationError

logger = logging.getLogger(__name__)


def storage_enabled(
    providers: Optional[Union[str, List[str], Dict[str, Dict[str, Any]]]] = None,
    auto_register: bool = True,
    permissions: Optional[List[str]] = None,
    **default_configs
):
    """
    Decorator to enable storage access for agent functions.
    
    Args:
        providers: Storage providers to enable. Can be:
            - String: Single provider name
            - List: Multiple provider names  
            - Dict: Provider name -> configuration mapping
        auto_register: Whether to auto-register providers from environment
        permissions: Default permissions for storage access
        **default_configs: Default configurations for providers
    
    Examples:
        @storage_enabled("postgres")
        @agent("data_analyst")
        def analyze_data(spore):
            data = storage.query("postgres", "SELECT * FROM customers")
            
        @storage_enabled(["postgres", "s3", "redis"])
        @agent("business_intelligence")
        def generate_report(spore):
            # Access multiple storage backends
            pass
            
        @storage_enabled({
            "postgres": {"host": "localhost", "database": "business"},
            "s3": {"bucket_name": "reports"}
        })
        @agent("report_generator")
        def create_analysis(spore):
            pass
    """
    def decorator(func: Callable) -> Callable:
        # Store storage configuration on the function
        func._storage_config = {
            "providers": providers,
            "auto_register": auto_register,
            "permissions": permissions,
            "default_configs": default_configs
        }
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Ensure storage providers are available
            await _ensure_storage_providers(func._storage_config, func.__name__)
            
            # Add storage interface to kwargs if not present
            if 'storage' not in kwargs:
                kwargs['storage'] = get_data_manager()
            
            # Call the original function
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, run storage setup in event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, create a task
                    loop.create_task(_ensure_storage_providers(func._storage_config, func.__name__))
                else:
                    # Run in new event loop
                    loop.run_until_complete(_ensure_storage_providers(func._storage_config, func.__name__))
            except Exception as e:
                logger.warning(f"Failed to setup storage providers: {e}")
            
            # Add storage interface to kwargs if not present
            if 'storage' not in kwargs:
                kwargs['storage'] = get_data_manager()
            
            return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def requires_storage(*provider_names: str, permissions: Optional[List[str]] = None):
    """
    Decorator to require specific storage providers for a function.
    
    Args:
        *provider_names: Names of required storage providers
        permissions: Required permissions for storage access
    
    Example:
        @requires_storage("postgres", "s3")
        @agent("data_processor")
        def process_customer_data(spore):
            # Function requires both postgres and s3 to be available
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            registry = get_storage_registry()
            agent_name = getattr(func, '__name__', 'unknown')
            
            # Check that all required providers are available
            for provider_name in provider_names:
                try:
                    registry.get_provider(provider_name, agent_name)
                except StorageNotFoundError:
                    raise StorageConfigurationError(
                        provider_name,
                        f"Required storage provider '{provider_name}' not available for function '{func.__name__}'"
                    )
            
            # Add storage interface to kwargs if not present
            if 'storage' not in kwargs:
                kwargs['storage'] = get_data_manager()
            
            # Call the original function
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            registry = get_storage_registry()
            agent_name = getattr(func, '__name__', 'unknown')
            
            # Check that all required providers are available
            for provider_name in provider_names:
                try:
                    registry.get_provider(provider_name, agent_name)
                except StorageNotFoundError:
                    raise StorageConfigurationError(
                        provider_name,
                        f"Required storage provider '{provider_name}' not available for function '{func.__name__}'"
                    )
            
            # Add storage interface to kwargs if not present
            if 'storage' not in kwargs:
                kwargs['storage'] = get_data_manager()
            
            return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


async def _ensure_storage_providers(config: Dict[str, Any], agent_name: str):
    """Ensure storage providers are registered and available."""
    registry = get_storage_registry()
    providers = config.get("providers")
    
    if not providers:
        return
    
    if isinstance(providers, str):
        # Single provider
        await _ensure_single_provider(registry, providers, config, agent_name)
    
    elif isinstance(providers, list):
        # Multiple providers
        for provider_name in providers:
            await _ensure_single_provider(registry, provider_name, config, agent_name)
    
    elif isinstance(providers, dict):
        # Providers with configurations
        for provider_name, provider_config in providers.items():
            merged_config = {**config.get("default_configs", {}), **provider_config}
            await _ensure_single_provider(registry, provider_name, {"default_configs": merged_config}, agent_name)


async def _ensure_single_provider(registry, provider_name: str, config: Dict[str, Any], agent_name: str):
    """Ensure a single provider is available."""
    try:
        # Check if provider is already registered
        registry.get_provider(provider_name, agent_name)
        logger.debug(f"Storage provider '{provider_name}' already available")
        
    except StorageNotFoundError:
        # Try to auto-register if enabled
        if config.get("auto_register", True):
            await _auto_register_provider(registry, provider_name, config, agent_name)
        else:
            raise StorageConfigurationError(
                provider_name,
                f"Storage provider '{provider_name}' not found and auto_register is disabled"
            )


async def _auto_register_provider(registry, provider_name: str, config: Dict[str, Any], agent_name: str):
    """Auto-register a storage provider from environment or defaults."""
    import os
    from .providers import (
        PostgreSQLProvider, RedisProvider, S3Provider, 
        FileSystemProvider, QdrantProvider
    )
    
    # Provider class mapping
    provider_classes = {
        "postgres": PostgreSQLProvider,
        "postgresql": PostgreSQLProvider,
        "redis": RedisProvider,
        "s3": S3Provider,
        "filesystem": FileSystemProvider,
        "qdrant": QdrantProvider
    }
    
    if provider_name.lower() not in provider_classes:
        raise StorageConfigurationError(
            provider_name,
            f"Unknown storage provider type: {provider_name}"
        )
    
    provider_class = provider_classes[provider_name.lower()]
    
    # Build configuration from environment and defaults
    provider_config = config.get("default_configs", {}).copy()
    
    # Add environment-based configuration
    env_mappings = {
        "postgres": {
            "host": "POSTGRES_HOST",
            "port": "POSTGRES_PORT", 
            "database": "POSTGRES_DB",
            "user": "POSTGRES_USER",
            "password": "POSTGRES_PASSWORD"
        },
        "redis": {
            "host": "REDIS_HOST",
            "port": "REDIS_PORT",
            "password": "REDIS_PASSWORD",
            "database": "REDIS_DB"
        },
        "s3": {
            "bucket_name": "S3_BUCKET_NAME",
            "aws_access_key_id": "AWS_ACCESS_KEY_ID",
            "aws_secret_access_key": "AWS_SECRET_ACCESS_KEY",
            "region_name": "AWS_DEFAULT_REGION",
            "endpoint_url": "S3_ENDPOINT_URL"
        },
        "filesystem": {
            "base_path": "FILESYSTEM_BASE_PATH"
        },
        "qdrant": {
            "url": "QDRANT_URL",
            "api_key": "QDRANT_API_KEY",
            "collection_name": "QDRANT_COLLECTION_NAME"
        }
    }
    
    env_mapping = env_mappings.get(provider_name.lower(), {})
    for config_key, env_var in env_mapping.items():
        if env_var in os.environ:
            provider_config[config_key] = os.environ[env_var]
    
    # Set sensible defaults
    if provider_name.lower() == "filesystem":
        provider_config.setdefault("base_path", os.path.expanduser("~/.praval/storage"))
    elif provider_name.lower() == "qdrant":
        provider_config.setdefault("url", "http://localhost:6333")
    
    # Validate required configuration
    try:
        provider_instance = provider_class(provider_name, provider_config)
        
        # Register the provider
        permissions = config.get("permissions", [agent_name]) if agent_name != "unknown" else None
        success = await registry.register_provider(
            provider_instance,
            permissions=permissions,
            auto_connect=True
        )
        
        if success:
            logger.info(f"Auto-registered storage provider: {provider_name}")
        else:
            raise StorageConfigurationError(
                provider_name,
                f"Failed to register storage provider: {provider_name}"
            )
            
    except Exception as e:
        raise StorageConfigurationError(
            provider_name,
            f"Failed to create storage provider '{provider_name}': {e}"
        )