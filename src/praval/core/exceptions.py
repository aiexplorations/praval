"""
Custom exceptions for the Praval framework.

These exceptions provide clear error handling and debugging information
for common issues in LLM agent operations.
"""


class PravalError(Exception):
    """Base exception for all Praval-related errors."""
    pass


class ProviderError(PravalError):
    """Raised when there are issues with LLM provider operations."""
    pass


class ConfigurationError(PravalError):
    """Raised when there are configuration validation issues."""
    pass


class ToolError(PravalError):
    """Raised when there are issues with tool registration or execution."""
    pass


class StateError(PravalError):
    """Raised when there are issues with state persistence operations."""
    pass