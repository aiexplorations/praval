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
