"""
Storage system exceptions for Praval framework
"""

from typing import Optional, Dict, Any


class StorageError(Exception):
    """Base exception for storage system errors"""
    
    def __init__(self, message: str, provider: Optional[str] = None, 
                 storage_type: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.provider = provider
        self.storage_type = storage_type
        self.details = details or {}


class StorageNotFoundError(StorageError):
    """Raised when a storage provider or resource is not found"""
    
    def __init__(self, resource: str, provider: Optional[str] = None, 
                 available_resources: Optional[list] = None):
        message = f"Storage resource '{resource}' not found"
        if provider:
            message += f" in provider '{provider}'"
        if available_resources:
            message += f". Available resources: {available_resources}"
        
        super().__init__(message, provider)
        self.resource = resource
        self.available_resources = available_resources or []


class StorageConnectionError(StorageError):
    """Raised when connection to storage backend fails"""
    
    def __init__(self, provider: str, connection_details: Optional[str] = None):
        message = f"Failed to connect to storage provider '{provider}'"
        if connection_details:
            message += f": {connection_details}"
        
        super().__init__(message, provider)
        self.connection_details = connection_details


class StoragePermissionError(StorageError):
    """Raised when storage operation lacks required permissions"""
    
    def __init__(self, operation: str, resource: str, provider: Optional[str] = None):
        message = f"Permission denied for operation '{operation}' on resource '{resource}'"
        if provider:
            message += f" in provider '{provider}'"
        
        super().__init__(message, provider)
        self.operation = operation
        self.resource = resource


class StorageTimeoutError(StorageError):
    """Raised when storage operation times out"""
    
    def __init__(self, operation: str, timeout: float, provider: Optional[str] = None):
        message = f"Storage operation '{operation}' timed out after {timeout} seconds"
        if provider:
            message += f" in provider '{provider}'"
        
        super().__init__(message, provider)
        self.operation = operation
        self.timeout = timeout


class StorageConfigurationError(StorageError):
    """Raised when storage provider configuration is invalid"""
    
    def __init__(self, provider: str, config_issue: str):
        message = f"Configuration error for storage provider '{provider}': {config_issue}"
        super().__init__(message, provider)
        self.config_issue = config_issue