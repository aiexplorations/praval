"""
Pytest configuration and fixtures for Praval tests.

This file provides automatic test isolation by resetting global state
(Reef, Registry, ToolRegistry, Observability, Agent context) before each test function.
"""

import pytest


def _reset_agent_context():
    """Reset the thread-local agent context used by decorators."""
    try:
        from praval.decorators import _agent_context
        _agent_context.agent = None
        _agent_context.channel = None
    except (ImportError, AttributeError):
        pass


def _reset_observability():
    """Reset observability global state (config, tracer, trace store)."""
    try:
        from praval.observability.config import reset_config
        reset_config()
    except ImportError:
        pass

    try:
        from praval.observability.tracing.tracer import reset_tracer
        reset_tracer()
    except ImportError:
        pass

    try:
        from praval.observability.storage.sqlite_store import reset_trace_store
        reset_trace_store()
    except ImportError:
        pass


@pytest.fixture(autouse=True)
def reset_global_state():
    """
    Automatically reset all global singletons before each test.

    This ensures test isolation by clearing:
    - The global Reef (communication channels)
    - The global Registry (agent registrations)
    - The global ToolRegistry (tool registrations)
    - The agent context (thread-local from decorators)
    - Observability state (config, tracer, trace store)
    """
    # Reset before test
    from praval.core.reef import reset_reef
    from praval.core.registry import reset_registry
    from praval.core.tool_registry import reset_tool_registry

    reset_reef()
    reset_registry()
    reset_tool_registry()
    _reset_agent_context()
    _reset_observability()

    yield  # Run the test

    # Reset after test for cleanup
    reset_reef()
    reset_registry()
    reset_tool_registry()
    _reset_agent_context()
    _reset_observability()
