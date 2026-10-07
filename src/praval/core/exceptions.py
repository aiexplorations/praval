"""
Custom exceptions for the Praval framework.

These exceptions provide clear error handling and debugging information
for common issues in LLM agent operations.
"""

from typing import Any, Optional, Tuple


class PravalError(Exception):
    """Base exception for all Praval-related errors."""

    pass


class ProviderError(PravalError):
    """Raised when there are issues with LLM provider operations.

    The message stays the exception's string form, so ``ProviderError("...")``
    keeps working. Keyword fields describe a failed provider request when the
    runtime or an adapter knows them. ``retryable`` defaults to the class
    policy: rate limits, unavailability and transport failures are retryable,
    everything else is not.
    """

    default_retryable = False

    def __init__(
        self,
        message: str = "",
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        operation: Optional[str] = None,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        request_id: Optional[str] = None,
        retryable: Optional[bool] = None,
        retry_after_seconds: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.model = model
        self.operation = operation
        self.status_code = status_code
        self.error_code = error_code
        self.request_id = request_id
        self.retryable = self.default_retryable if retryable is None else retryable
        self.retry_after_seconds = retry_after_seconds

    def __reduce__(self) -> Tuple[Any, ...]:
        # Keyword fields are not part of ``args``; keep them across pickling.
        return (type(self), (self.message,), dict(self.__dict__))


class ProviderAuthenticationError(ProviderError):
    """The provider rejected the credentials or permissions (401/403)."""


class ProviderInvalidRequestError(ProviderError):
    """The provider rejected the request itself (400/404/422)."""


class ProviderQuotaError(ProviderError):
    """The account's quota or credit is exhausted; retrying will not help."""


class ProviderRateLimitError(ProviderError):
    """The provider throttled the request (429); retry after a delay."""

    default_retryable = True


class ProviderUnavailableError(ProviderError):
    """The provider failed or is overloaded (5xx, 529)."""

    default_retryable = True


class ProviderTransportError(ProviderError):
    """The request did not complete: connection failure or timeout."""

    default_retryable = True


class ToolRoundLimitError(ProviderError):
    """A tool loop exceeded its configured round limit; never retried."""

    def __init__(
        self,
        message: str = "",
        *,
        limit: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        super().__init__(message, provider=provider, model=model, retryable=False)
        self.limit = limit


class ConfigurationError(PravalError):
    """Raised when there are configuration validation issues."""

    pass


class PravalConfigurationError(ConfigurationError):
    """Raised when typed application or lifecycle configuration is invalid."""

    pass


class EmbeddingConfigurationError(ConfigurationError):
    """Raised when persistent vectors do not match embedding configuration."""

    pass


class ToolError(PravalError):
    """Raised when there are issues with tool registration or execution."""

    pass


class StateError(PravalError):
    """Raised when there are issues with state persistence operations."""

    pass


class InterventionRequired(PravalError):
    """Raised when a tool call is paused waiting for human intervention."""

    def __init__(
        self,
        intervention_id: str,
        run_id: str,
        agent_name: str,
        tool_name: str,
        reason: str = "",
    ):
        self.intervention_id = intervention_id
        self.run_id = run_id
        self.agent_name = agent_name
        self.tool_name = tool_name
        self.reason = reason
        message = (
            f"Intervention required for agent '{agent_name}' tool '{tool_name}' "
            f"(run_id={run_id}, intervention_id={intervention_id})"
        )
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message)


class HITLConfigurationError(PravalError):
    """Raised when HITL policy requires approval for a HITL-disabled agent."""

    pass
