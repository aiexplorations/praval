"""
Tests for PravalRegistry thread safety.

Verifies that PravalRegistry handles concurrent access correctly.
Part of rearchitecture issue M4.
"""

import threading
import time
from unittest.mock import Mock, patch

import pytest


class TestRegistryThreadSafety:
    """Tests for concurrent registry access."""

    def test_concurrent_agent_registration(self):
        """Verify registry handles concurrent registrations safely."""
        from praval.core.registry import PravalRegistry

        registry = PravalRegistry()
        errors = []
        registered = []

        def register_agent(agent_id):
            try:
                agent = Mock()
                agent.name = f"agent_{agent_id}"
                agent.tools = {}
                registry.register_agent(agent)
                registered.append(agent_id)
            except Exception as e:
                errors.append((agent_id, e))

        # Launch 100 concurrent registrations
        threads = [
            threading.Thread(target=register_agent, args=(i,)) for i in range(100)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent registration: {errors}"
        assert len(registry.list_agents()) == 100
        assert len(registered) == 100

    def test_concurrent_read_write(self):
        """Verify registry handles concurrent reads and writes."""
        from praval.core.registry import PravalRegistry

        registry = PravalRegistry()

        # Pre-register one agent
        initial_agent = Mock()
        initial_agent.name = "initial"
        initial_agent.tools = {}
        registry.register_agent(initial_agent)

        reads = []
        errors = []

        def reader():
            for _ in range(50):
                try:
                    result = registry.get_agent("initial")
                    reads.append(result)
                except Exception as e:
                    errors.append(("read", e))
                time.sleep(0.001)

        def writer():
            for i in range(50):
                try:
                    agent = Mock()
                    agent.name = f"new_agent_{i}"
                    agent.tools = {}
                    registry.register_agent(agent)
                except Exception as e:
                    errors.append(("write", e))
                time.sleep(0.001)

        read_threads = [threading.Thread(target=reader) for _ in range(5)]
        write_thread = threading.Thread(target=writer)

        for t in read_threads:
            t.start()
        write_thread.start()

        write_thread.join()
        for t in read_threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent access: {errors}"
        # All reads should return valid Mock or None (no corruption)
        assert all(r is None or hasattr(r, "name") for r in reads)
        # Should have initial + 50 new agents
        assert len(registry.list_agents()) == 51

    def test_clear_while_reading(self):
        """Verify clear() doesn't corrupt state during reads."""
        from praval.core.registry import PravalRegistry

        registry = PravalRegistry()

        # Pre-populate
        for i in range(10):
            agent = Mock()
            agent.name = f"agent_{i}"
            agent.tools = {}
            registry.register_agent(agent)

        errors = []

        def reader():
            for _ in range(100):
                try:
                    agents = registry.list_agents()
                    # Should be list, not corrupted
                    assert isinstance(agents, list)
                except Exception as e:
                    errors.append(e)

        def clearer():
            time.sleep(0.01)
            registry.clear()

        read_threads = [threading.Thread(target=reader) for _ in range(5)]
        clear_thread = threading.Thread(target=clearer)

        for t in read_threads:
            t.start()
        clear_thread.start()

        clear_thread.join()
        for t in read_threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent clear: {errors}"

    def test_concurrent_tool_registration(self):
        """Verify tools are registered correctly during concurrent access."""
        from praval.core.registry import PravalRegistry

        registry = PravalRegistry()
        errors = []

        def register_agent_with_tools(agent_id):
            try:
                agent = Mock()
                agent.name = f"agent_{agent_id}"
                agent.tools = {
                    "tool1": {"function": Mock(), "description": "Tool 1"},
                    "tool2": {"function": Mock(), "description": "Tool 2"},
                }
                registry.register_agent(agent)
            except Exception as e:
                errors.append((agent_id, e))

        threads = [
            threading.Thread(target=register_agent_with_tools, args=(i,))
            for i in range(50)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(registry.list_agents()) == 50
        # Each agent has 2 tools
        assert len(registry.list_tools()) == 100

    def test_get_tools_by_agent_thread_safe(self):
        """Verify get_tools_by_agent is thread-safe."""
        from praval.core.registry import PravalRegistry

        registry = PravalRegistry()

        # Register agents with tools
        for i in range(10):
            agent = Mock()
            agent.name = f"agent_{i}"
            agent.tools = {f"tool_{j}": {"function": Mock()} for j in range(3)}
            registry.register_agent(agent)

        errors = []
        results = []

        def get_tools():
            for i in range(10):
                try:
                    tools = registry.get_tools_by_agent(f"agent_{i}")
                    results.append(len(tools))
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=get_tools) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        # All results should be 3 (each agent has 3 tools)
        assert all(r == 3 for r in results)

    def test_registry_has_lock(self):
        """Verify PravalRegistry has a lock attribute."""
        from praval.core.registry import PravalRegistry

        registry = PravalRegistry()
        assert hasattr(registry, "_lock")
        assert isinstance(registry._lock, type(threading.RLock()))

    def test_reentrant_locking(self):
        """Verify RLock allows same thread to acquire multiple times."""
        from praval.core.registry import PravalRegistry

        registry = PravalRegistry()

        # This should not deadlock - RLock allows reentrant acquisition
        def nested_operations():
            agent = Mock()
            agent.name = "nested_test"
            agent.tools = {"tool1": {"function": Mock()}}

            # This calls register_agent which acquires lock
            registry.register_agent(agent)

            # These also acquire lock - should work with RLock
            registry.get_agent("nested_test")
            registry.list_agents()
            registry.get_tools_by_agent("nested_test")

        # Should complete without deadlock
        thread = threading.Thread(target=nested_operations)
        thread.start()
        thread.join(timeout=5)

        assert not thread.is_alive(), "Thread deadlocked - RLock not working correctly"


class TestGlobalRegistryThreadSafety:
    """Tests for global registry functions thread safety."""

    def test_global_registry_concurrent_access(self):
        """Verify global registry functions are thread-safe."""
        from praval.core.registry import (
            register_agent,
            get_registry,
            reset_registry,
        )

        reset_registry()
        errors = []

        def register_and_check(agent_id):
            try:
                agent = Mock()
                agent.name = f"global_agent_{agent_id}"
                agent.tools = {}
                register_agent(agent)

                # Verify registration worked
                registry = get_registry()
                found = registry.get_agent(f"global_agent_{agent_id}")
                assert found is not None
            except Exception as e:
                errors.append((agent_id, e))

        threads = [
            threading.Thread(target=register_and_check, args=(i,)) for i in range(50)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(get_registry().list_agents()) == 50

        # Cleanup
        reset_registry()
