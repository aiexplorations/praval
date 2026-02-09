# Praval Framework Rearchitecture Plan v2

**Branch:** `praval_rearchitecture`
**Date:** 2024-12-10
**Status:** IN PROGRESS (Sprint 1 complete, Sprint 2 pending)
**Last Updated:** 2024-12-30

---

## Changelog from v1

- **Clarified:** ToolRegistry (tool_registry.py:152) already has thread locks; only PravalRegistry needs them
- **Added:** M3 detailed fix for cleanup thread daemon/exception handling
- **Added:** Explicit examples validation step
- **Added:** Benchmark baseline establishment step
- **Added:** Documentation update requirements per change
- **Added (v2.1):** Downstream impact analysis for all identified issues

---

## Executive Summary

This plan outlines a comprehensive rearchitecture of the Praval multi-agent framework to improve:
1. **Performance** - Reduce latency, improve throughput
2. **Memory Safety** - Eliminate leaks, bound resource usage
3. **Security** - Input validation, rate limiting, credential protection
4. **Abstraction Quality** - Cleaner separation of concerns, easier testing

**Key Constraint:** Maintain backward API compatibility for downstream projects.

---

## Current State Analysis

### Codebase Metrics
- **Test Files:** 54 test files
- **Coverage Target:** 80% (configured in pyproject.toml)
- **Python Versions:** 3.9, 3.10, 3.11, 3.12
- **Core Modules:** agent.py, reef.py, decorators.py, composition.py, memory_manager.py

### Identified Issues with Downstream Impact Analysis

#### Performance (P)

| ID | Issue | Location | Severity |
|----|-------|----------|----------|
| P1 | Event loop created per async operation | `reef.py:556-572` | HIGH |
| P2 | ThreadPoolExecutor per channel (4 workers × N) | `reef.py:276-282` | MEDIUM |
| P3 | New event loop per async handler | `reef.py:344-353` | HIGH |
| P4 | Spore size estimation via string conversion | `reef.py:124-139` | LOW |
| P5 | No handler execution batching | `reef.py:307-334` | LOW |

**Downstream Impact:**

| ID | Who is Affected | Impact Description | Mitigation |
|----|-----------------|-------------------|------------|
| P1 | **RabbitMQ users** (`run_agents()`, distributed deployments) | Each message send/receive creates a new event loop. In high-throughput scenarios (>100 msg/sec), this causes 10-100x slower performance than expected. Production systems with multiple distributed agents will experience significant latency. | Fix uses persistent loop; no API change. Existing code will automatically benefit. |
| P2 | **Multi-channel applications** (apps using `create_channel()` extensively) | An app with 10 channels creates 40 threads at startup (4 per channel). This wastes ~320MB of memory (8MB/thread) and causes excessive context switching. Applications with many specialized channels suffer most. | Shared pool is opt-out via `use_shared_pool=False`. Default behavior changes but is backward compatible. |
| P3 | **Async handler users** (handlers using `async def`) | Async handlers lose all benefits of async/await because each runs in an isolated loop. Cannot share connections, cannot coordinate tasks. Async code runs slower than sync equivalent. | Fix allows async handlers to cooperate. No API change needed. |
| P4 | **Large payload users** (sending >1MB knowledge dicts) | Size estimation for auto-referencing converts entire payload to string just to measure size. For 10MB payloads, this wastes ~20MB of temporary memory and CPU cycles. | Internal optimization; no downstream impact. |
| P5 | **High-frequency messaging** (100+ spores/second per channel) | Each spore delivery is individually scheduled. Under high load, scheduling overhead dominates actual handler execution time. | Future optimization; low priority. |

---

#### Memory Safety (M)

| ID | Issue | Location | Severity |
|----|-------|----------|----------|
| M1 | Handlers never unsubscribed in `request_knowledge()` | `agent.py:330-364` | HIGH |
| M2 | No `Agent.close()` method | `agent.py` | HIGH |
| M3 | Cleanup thread uses daemon + silent except | `reef.py:883-893` | MEDIUM |
| M4 | PravalRegistry without thread locks | `registry.py:12-87` | HIGH |
| M5 | Unbounded `conversation_history` | `agent.py:104` | MEDIUM |
| M6 | No shutdown timeout in `ReefChannel.shutdown()` | `reef.py:489-492` | MEDIUM |

**Note:** ToolRegistry (tool_registry.py:152) already has proper thread locks (`self._lock = threading.RLock()`).

**Downstream Impact:**

| ID | Who is Affected | Impact Description | Mitigation |
|----|-----------------|-------------------|------------|
| M1 | **Agents using `request_knowledge()`** (request-response pattern) | Each call to `request_knowledge()` leaks a handler subscription. Long-running agents making frequent requests will accumulate handlers, causing: (1) Memory growth, (2) Slower message delivery as subscriber list grows, (3) Eventually OOM in 24/7 services. | Fix adds automatic cleanup in `finally` block. No API change. Existing code automatically fixed. |
| M2 | **Long-running services** (web servers, daemons using Praval agents) | Agents hold references to reef channels, memory systems, and conversation history forever. In Flask/FastAPI apps creating agents per-request, this causes memory leaks. No way to explicitly release resources. | New `Agent.close()` method and context manager. Existing code continues to work but should adopt `with Agent(...) as agent:` pattern for proper cleanup. |
| M3 | **Production deployments** (any deployment relying on error visibility) | Cleanup thread errors are silently swallowed (`except: pass`). If cleanup fails, expired spores accumulate, spore references become invalid, and operators have no visibility into the failure. | Fix adds logging. No API change. Operators will now see warnings in logs. |
| M4 | **Multi-threaded applications** (concurrent agent creation, web servers) | Concurrent `@agent` decorator calls can corrupt the global registry. Two agents registering simultaneously might overwrite each other or cause KeyError. Race conditions are intermittent and hard to debug. | Fix adds thread lock. No API change. Existing concurrent code becomes safe. |
| M5 | **Chatbot/conversational agents** (agents with long conversations) | `conversation_history` grows without bound. An agent handling 1000 user messages stores all of them. Eventually hits LLM context limits or causes OOM. No way to configure max history. | New `max_history` parameter with default=100. Existing code gets bounded history automatically (breaking change in behavior, but safer default). |
| M6 | **Graceful shutdown scenarios** (SIGTERM handling, container orchestration) | `reef.shutdown()` can hang forever if a handler is stuck. Kubernetes pods get SIGKILL after timeout. Docker containers don't stop cleanly. CI/CD pipelines hang on test cleanup. | New `timeout` parameter with default=30s. Existing code gets timeout automatically. `shutdown()` now returns bool indicating clean vs timeout. |

---

#### Security (S)

| ID | Issue | Location | Severity |
|----|-------|----------|----------|
| S1 | No input validation on spore knowledge | `reef.py:611-672` | HIGH |
| S2 | No rate limiting on broadcast | `reef.py:674-685` | MEDIUM |
| S3 | API keys could appear in logs | `agent.py` | MEDIUM |
| S4 | `print()` instead of `logging` | `agent.py:456,459,463...` | LOW |
| S5 | No authentication on reef channels | `reef.py` | LOW |

**Downstream Impact:**

| ID | Who is Affected | Impact Description | Mitigation |
|----|-----------------|-------------------|------------|
| S1 | **Any application accepting external input** (APIs, user-facing apps) | Malicious input can: (1) **DoS via memory**: Send 1GB spore, crash the process, (2) **Object injection**: If knowledge is later pickled/unpickled, arbitrary code execution possible, (3) **Type confusion**: Non-JSON types cause downstream failures. No size limits, no type validation. | New validation in `send()`. Raises `ValueError` for >10MB, `TypeError` for non-JSON types. **Breaking change** for code sending large payloads—must use knowledge references instead. |
| S2 | **Multi-tenant deployments** (shared Praval infrastructure) | A malicious or buggy agent can flood the reef with broadcasts. No throttling means one agent can DoS all others. Particularly dangerous with RabbitMQ backend where broadcasts go to all subscribers. | Deferred to future sprint. Document as known limitation. |
| S3 | **Production deployments with log aggregation** | API keys from environment variables could appear in error messages or debug logs. Log aggregation services (Datadog, Splunk) would capture and store credentials. | Audit needed. Not addressed in Phase 1. |
| S4 | **All users** (anyone running Praval agents) | `print()` statements in agent.py go to stdout, mixed with application output. Cannot be: (1) Filtered by log level, (2) Redirected to files, (3) Captured by logging frameworks, (4) Disabled in production. Inconsistent with rest of codebase which uses `logging`. | Simple fix: add `import logging; logger = logging.getLogger(__name__)`. No downstream impact—users who weren't seeing prints won't notice; users who were can now control via logging config. |
| S5 | **Multi-tenant deployments** | Any agent can subscribe to any channel and receive all messages. No access control, no isolation between tenants. Agents can impersonate others. | Deferred. Requires significant design work. Document as known limitation for multi-tenant use cases. |

---

#### Abstraction (A)

| ID | Issue | Location | Severity |
|----|-------|----------|----------|
| A1 | `ReefChannel` has 20+ methods | `reef.py:265-493` | MEDIUM |
| A2 | `Reef` mixes low/high-level APIs | `reef.py:495-919` | MEDIUM |
| A3 | `@agent` decorator does 6 things | `decorators.py:119-335` | MEDIUM |
| A4 | `Spore` is mutable but exposed | `reef.py:41-263` | LOW |

**Downstream Impact:**

| ID | Who is Affected | Impact Description | Mitigation |
|----|-----------------|-------------------|------------|
| A1 | **Framework contributors** (anyone extending/modifying reef) | `ReefChannel` is 500+ lines mixing routing, subscription management, thread pools, and stats. Adding new features requires understanding all concerns. Testing requires full channel setup. Hard to customize routing without copying entire class. | Deferred to Phase 3. Propose decomposition into `Router`, `SubscriptionManager`, `ExecutorPool`. No user-facing API change. |
| A2 | **Advanced users** (custom backends, protocol extensions) | `Reef` class handles both low-level message routing AND high-level agent convenience methods. Backend-specific code (`_is_distributed_backend()`) leaks throughout. Hard to add new backend types. | Deferred to Phase 3. Propose split into `ReefCore` + `ReefAPI`. Internal refactor, public API unchanged. |
| A3 | **Users customizing agent behavior** | `@agent` decorator handles: agent creation, message filtering, memory integration, tool registration, error handling, auto-broadcast. Understanding what happens requires reading 150+ lines. Can't customize one aspect without understanding all. | Deferred. Could split into stackable decorators: `@with_memory()`, `@responds_to()`, etc. Would be additive, not breaking. |
| A4 | **Agent handler authors** | `Spore` is a mutable dataclass exposed to handlers. Handlers can accidentally modify spore state, affecting other handlers receiving the same spore (especially broadcasts). No enforcement of read-only access. | Could make `Spore` a frozen dataclass. **Breaking change** for any code modifying spores. Needs careful migration plan. Deferred. |

---

### Breaking vs Non-Breaking Changes Summary

#### Fully Backward Compatible (No User Action Required)
| ID | Change | Why Safe |
|----|--------|----------|
| S4 | print() → logger | Users can now control output via logging config; no behavior change for users not configuring logging |
| M4 | Thread-safe registry | Internal implementation detail; same API, safer behavior |
| M3 | Cleanup thread logging | Adds visibility; no behavior change |
| M1 | Handler cleanup in request_knowledge() | Bug fix; handlers were leaking before, now they don't |
| P1 | Persistent event loop | Internal optimization; same API, faster |
| P2 | Shared thread pool | Default is shared, opt-out available via `use_shared_pool=False` |
| P3 | Async handler cooperation | Internal fix; async handlers now work correctly |

#### Additive Changes (New Features, Existing Code Unaffected)
| ID | Change | New API |
|----|--------|---------|
| M2 | Agent.close() | New method + context manager. Existing code works but should migrate to `with Agent() as agent:` |
| M6 | Shutdown timeout | New `timeout` parameter with sensible default (30s). Return type changes from `None` to `bool` |

#### Potentially Breaking Changes (Require Attention)
| ID | Change | Impact | Migration Path |
|----|--------|--------|----------------|
| S1 | Spore payload validation | Code sending >10MB payloads will get `ValueError` | Use knowledge references for large data |
| M5 | Bounded conversation history | Conversations >100 messages will be trimmed | Set `max_history=None` to restore old behavior (not recommended) |

#### Deferred (Not Implemented in This Plan)
| ID | Change | Reason |
|----|--------|--------|
| S2 | Rate limiting | Requires design discussion |
| S3 | API key protection | Requires security audit |
| S5 | Channel authentication | Major feature, needs RFC |
| A1-A4 | Abstraction refactoring | Internal, no user impact, lower priority |

---

## Pre-Implementation: Establish Baseline

Before any changes, establish baseline metrics:

```bash
# Run full test suite and record baseline
source venv/bin/activate
pytest tests/ -v --tb=short 2>&1 | tee temp_plans/baseline_tests.log

# Run with coverage
pytest tests/ --cov=praval --cov-report=html 2>&1 | tee temp_plans/baseline_coverage.log

# Run examples to verify they work
python examples/simple_multi_agent.py 2>&1 | tee temp_plans/baseline_examples.log

# Create simple benchmark script
cat > temp_plans/benchmark_baseline.py << 'EOF'
"""Baseline performance benchmarks for Praval."""
import time
import threading
from praval import Agent, agent, chat, broadcast, start_agents, get_reef

def benchmark_message_throughput():
    """Measure messages per second."""
    reef = get_reef()
    count = 1000

    start = time.time()
    for i in range(count):
        reef.send("sender", "receiver", {"i": i})
    elapsed = time.time() - start

    print(f"Message throughput: {count/elapsed:.0f} msg/sec")
    return count/elapsed

def benchmark_agent_creation():
    """Measure agent creation time."""
    count = 100

    start = time.time()
    agents = [Agent(f"agent_{i}") for i in range(count)]
    elapsed = time.time() - start

    print(f"Agent creation: {count/elapsed:.0f} agents/sec")
    return count/elapsed

if __name__ == "__main__":
    print("=== Praval Baseline Benchmarks ===")
    benchmark_message_throughput()
    benchmark_agent_creation()
EOF
python temp_plans/benchmark_baseline.py 2>&1 | tee temp_plans/baseline_benchmarks.log
```

---

## Rearchitecture Phases

### Phase 1: Foundation Fixes (Low Risk, High Impact)
**Scope:** Fix critical issues without changing APIs

#### 1.1 Replace print() with logger [S4]
**Files:** `src/praval/core/agent.py`

**Lines to change:** 456, 459, 463, 482, 506, 523, 540, 575, 596

**Current:**
```python
print(f"Memory system initialized for agent {self.name}")
print(f"Memory system not available: {e}")
print(f"Memory not enabled for agent {self.name}")
```

**Target:**
```python
import logging
logger = logging.getLogger(__name__)

# Replace each print with appropriate log level:
logger.info(f"Memory system initialized for agent {self.name}")
logger.warning(f"Memory system not available: {e}")
logger.debug(f"Memory not enabled for agent {self.name}")
```

**Test Strategy:**
```python
# tests/test_agent_logging.py
import logging
import pytest
from unittest.mock import patch, Mock

def test_memory_init_logs_info(caplog):
    """Verify memory initialization logs at INFO level."""
    with caplog.at_level(logging.INFO):
        from praval import Agent
        # Mock memory manager to avoid actual initialization
        with patch('praval.core.agent.MemoryManager'):
            agent = Agent("test_log", memory_enabled=True)

    assert "Memory system initialized" in caplog.text
    assert caplog.records[0].levelno == logging.INFO

def test_memory_unavailable_logs_warning(caplog):
    """Verify missing memory dependencies log at WARNING level."""
    with caplog.at_level(logging.WARNING):
        from praval import Agent
        with patch.dict('sys.modules', {'praval.memory': None}):
            with patch('praval.core.agent.MemoryManager', side_effect=ImportError("test")):
                agent = Agent("test_warn", memory_enabled=True)

    # Should log warning, not crash
    assert agent.memory is None

def test_no_print_statements_in_agent():
    """Verify no print() calls remain in agent.py."""
    import ast
    from pathlib import Path

    agent_path = Path("src/praval/core/agent.py")
    tree = ast.parse(agent_path.read_text())

    print_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == 'print':
                print_calls.append(node.lineno)

    assert len(print_calls) == 0, f"Found print() calls at lines: {print_calls}"
```

---

#### 1.2 Thread-safe PravalRegistry [M4]
**Files:** `src/praval/core/registry.py`

**Note:** ToolRegistry already has locks. Only PravalRegistry needs them.

**Current:**
```python
class PravalRegistry:
    def __init__(self):
        self._agents: Dict[str, Agent] = {}
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register_agent(self, agent: Agent) -> Agent:
        self._agents[agent.name] = agent  # NOT THREAD SAFE
        # ...
```

**Target:**
```python
import threading

class PravalRegistry:
    """Global registry for agents and tools in Praval applications.

    Thread-safe for concurrent agent registration and lookup.
    """

    def __init__(self):
        self._agents: Dict[str, Agent] = {}
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def register_agent(self, agent: Agent) -> Agent:
        """Register an agent in the global registry (thread-safe)."""
        with self._lock:
            self._agents[agent.name] = agent

            # Also register all tools from this agent
            for tool_name, tool_info in agent.tools.items():
                full_tool_name = f"{agent.name}.{tool_name}"
                self._tools[full_tool_name] = {
                    **tool_info,
                    "agent": agent.name
                }

        return agent

    def get_agent(self, name: str) -> Optional[Agent]:
        """Get an agent by name (thread-safe)."""
        with self._lock:
            return self._agents.get(name)

    def get_all_agents(self) -> Dict[str, Agent]:
        """Get all registered agents (thread-safe, returns copy)."""
        with self._lock:
            return self._agents.copy()

    def get_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get a tool by name (thread-safe)."""
        with self._lock:
            return self._tools.get(tool_name)

    def get_tools_by_agent(self, agent_name: str) -> Dict[str, Dict[str, Any]]:
        """Get all tools for a specific agent (thread-safe)."""
        with self._lock:
            return {
                tool_name: tool_info
                for tool_name, tool_info in self._tools.items()
                if tool_info.get("agent") == agent_name
            }

    def list_agents(self) -> List[str]:
        """List names of all registered agents (thread-safe)."""
        with self._lock:
            return list(self._agents.keys())

    def list_tools(self) -> List[str]:
        """List names of all registered tools (thread-safe)."""
        with self._lock:
            return list(self._tools.keys())

    def clear(self):
        """Clear all registered agents and tools (thread-safe)."""
        with self._lock:
            self._agents.clear()
            self._tools.clear()
```

**Test Strategy:**
```python
# tests/test_registry_thread_safety.py
import threading
import time
import pytest
from unittest.mock import Mock, patch

def test_concurrent_agent_registration():
    """Verify registry handles concurrent registrations safely."""
    from praval.core.registry import PravalRegistry, reset_registry
    from praval import Agent

    reset_registry()
    registry = PravalRegistry()
    errors = []
    registered = []

    def register_agent(agent_id):
        try:
            with patch('praval.core.agent.ProviderFactory'):
                agent = Mock()
                agent.name = f"agent_{agent_id}"
                agent.tools = {}
                registry.register_agent(agent)
                registered.append(agent_id)
        except Exception as e:
            errors.append((agent_id, e))

    threads = [threading.Thread(target=register_agent, args=(i,)) for i in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Errors: {errors}"
    assert len(registry.list_agents()) == 100

def test_concurrent_read_write():
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
                errors.append(e)
            time.sleep(0.001)

    def writer():
        for i in range(50):
            try:
                agent = Mock()
                agent.name = f"new_agent_{i}"
                agent.tools = {}
                registry.register_agent(agent)
            except Exception as e:
                errors.append(e)
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
    assert all(r is None or hasattr(r, 'name') for r in reads)

def test_clear_while_reading():
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

    assert len(errors) == 0
```

---

#### 1.3 Add Agent.close() and context manager [M2]
**Files:** `src/praval/core/agent.py`

**Target:**
```python
class Agent:
    def __init__(self, ...):
        # ... existing init
        self._closed = False
        self._subscribed_channels: List[str] = []

    def subscribe_to_channel(self, channel_name: str) -> None:
        """Subscribe this agent to a reef channel."""
        from .reef import get_reef

        reef = get_reef()
        reef.create_channel(channel_name)
        reef.subscribe(self.name, self.on_spore_received, channel_name)

        # Track subscription for cleanup
        if channel_name not in self._subscribed_channels:
            self._subscribed_channels.append(channel_name)

    def close(self) -> None:
        """Release all resources held by the agent.

        This method:
        - Unsubscribes from all reef channels
        - Shuts down the memory system
        - Clears conversation history

        Safe to call multiple times.
        """
        if self._closed:
            return

        self._closed = True

        # Unsubscribe from reef channels
        try:
            from .reef import get_reef
            reef = get_reef()
            for channel_name in self._subscribed_channels:
                try:
                    channel = reef.get_channel(channel_name)
                    if channel:
                        channel.unsubscribe(self.name)
                except Exception as e:
                    logger.warning(f"Error unsubscribing {self.name} from {channel_name}: {e}")
            self._subscribed_channels.clear()
        except Exception as e:
            logger.warning(f"Error during reef cleanup for {self.name}: {e}")

        # Shutdown memory system
        if self.memory:
            try:
                self.memory.shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down memory for {self.name}: {e}")
            self.memory = None

        # Clear conversation history
        self.conversation_history.clear()

        logger.debug(f"Agent {self.name} closed")

    def __enter__(self) -> 'Agent':
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - ensures cleanup."""
        self.close()

    def __del__(self):
        """Destructor - attempt cleanup if not already done."""
        try:
            if not self._closed:
                self.close()
        except Exception:
            pass  # Suppress errors during garbage collection
```

**Test Strategy:**
```python
# tests/test_agent_lifecycle.py
import pytest
from unittest.mock import Mock, patch, MagicMock

def test_agent_close_releases_memory():
    """Verify close() releases memory system."""
    from praval import Agent

    with patch('praval.core.agent.ProviderFactory'):
        with patch('praval.core.agent.MemoryManager') as mock_mm:
            mock_memory = MagicMock()
            mock_mm.return_value = mock_memory

            agent = Agent("test", memory_enabled=True)
            agent.memory = mock_memory

            agent.close()

            mock_memory.shutdown.assert_called_once()
            assert agent.memory is None

def test_agent_context_manager():
    """Verify agent works as context manager."""
    from praval import Agent

    with patch('praval.core.agent.ProviderFactory'):
        with Agent("ctx_agent") as agent:
            assert not agent._closed

        assert agent._closed

def test_agent_double_close_is_safe():
    """Verify calling close() twice is safe."""
    from praval import Agent

    with patch('praval.core.agent.ProviderFactory'):
        agent = Agent("test")
        agent.close()
        agent.close()  # Should not raise

        assert agent._closed

def test_agent_close_clears_subscriptions():
    """Verify close() unsubscribes from reef channels."""
    from praval import Agent
    from praval.core.reef import get_reef, reset_reef

    reset_reef()

    with patch('praval.core.agent.ProviderFactory'):
        agent = Agent("test")
        agent.subscribe_to_channel("test_channel")

        reef = get_reef()
        channel = reef.get_channel("test_channel")
        assert "test" in channel.subscribers

        agent.close()

        assert "test" not in channel.subscribers

def test_agent_close_clears_history():
    """Verify close() clears conversation history."""
    from praval import Agent

    with patch('praval.core.agent.ProviderFactory'):
        agent = Agent("test")
        agent.conversation_history = [{"role": "user", "content": "test"}]

        agent.close()

        assert len(agent.conversation_history) == 0

def test_agent_close_handles_errors_gracefully():
    """Verify close() handles errors during cleanup."""
    from praval import Agent

    with patch('praval.core.agent.ProviderFactory'):
        agent = Agent("test", memory_enabled=True)

        # Set up memory that raises on shutdown
        mock_memory = Mock()
        mock_memory.shutdown.side_effect = RuntimeError("Shutdown failed")
        agent.memory = mock_memory

        # Should not raise
        agent.close()

        assert agent._closed
```

---

#### 1.4 Shutdown timeout and cleanup thread fix [M6, M3]
**Files:** `src/praval/core/reef.py`

**Current (M3 - cleanup thread):**
```python
def _cleanup_loop(self) -> None:
    """Background thread to clean up expired spores."""
    while not self._shutdown:
        try:
            time.sleep(60)
            if not self._shutdown:
                for channel in self.channels.values():
                    channel.cleanup_expired()
        except Exception as e:
            pass  # Silent! Bad!
```

**Target:**
```python
class ReefChannel:
    def shutdown(self, wait: bool = True, timeout: float = 30.0) -> bool:
        """Shutdown the channel's thread pool.

        Args:
            wait: Whether to wait for pending handlers to complete
            timeout: Maximum seconds to wait (only if wait=True)

        Returns:
            True if shutdown completed cleanly, False if timeout occurred
        """
        self._shutdown = True

        if not wait:
            self.executor.shutdown(wait=False)
            return True

        # Cancel pending futures
        with self._futures_lock:
            for future in self._active_futures:
                if not future.done():
                    future.cancel()

        # Shutdown executor with timeout
        # Python 3.9+ has cancel_futures parameter
        import sys
        if sys.version_info >= (3, 9):
            self.executor.shutdown(wait=True, cancel_futures=True)
        else:
            self.executor.shutdown(wait=True)

        # Verify all futures completed
        start = time.time()
        while time.time() - start < timeout:
            with self._futures_lock:
                pending = [f for f in self._active_futures if not f.done()]
            if not pending:
                return True
            time.sleep(0.1)

        logger.warning(f"Channel {self.name} shutdown timed out with {len(pending)} pending handlers")
        return False


class Reef:
    def _cleanup_loop(self) -> None:
        """Background thread to clean up expired spores.

        Runs every 60 seconds. Logs errors instead of silently ignoring them.
        """
        while not self._shutdown:
            try:
                # Use interruptible sleep
                for _ in range(60):
                    if self._shutdown:
                        break
                    time.sleep(1)

                if not self._shutdown:
                    for channel in self.channels.values():
                        try:
                            expired = channel.cleanup_expired()
                            if expired > 0:
                                logger.debug(f"Cleaned up {expired} expired spores from {channel.name}")
                        except Exception as e:
                            logger.warning(f"Error cleaning up channel {channel.name}: {e}")
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                # Don't exit the loop on error, but add backoff
                time.sleep(5)

    def shutdown(self, wait: bool = True, timeout: float = 30.0) -> bool:
        """Shutdown the reef and all its channels.

        Args:
            wait: Whether to wait for pending handlers
            timeout: Maximum total seconds to wait across all channels

        Returns:
            True if all channels shut down cleanly, False if timeout occurred
        """
        self._shutdown = True

        all_clean = True
        remaining_timeout = timeout

        for channel in self.channels.values():
            start = time.time()
            if not channel.shutdown(wait=wait, timeout=remaining_timeout):
                all_clean = False
            elapsed = time.time() - start
            remaining_timeout = max(0, remaining_timeout - elapsed)

        # Wait for cleanup thread
        if wait and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=min(5.0, remaining_timeout))
            if self.cleanup_thread.is_alive():
                logger.warning("Cleanup thread did not stop within timeout")
                all_clean = False

        return all_clean
```

**Test Strategy:**
```python
# tests/test_reef_shutdown.py
import time
import threading
import pytest
from datetime import datetime
from unittest.mock import Mock, patch

def test_shutdown_with_timeout_completes():
    """Verify shutdown completes within timeout."""
    from praval.core.reef import ReefChannel, Spore, SporeType

    channel = ReefChannel("test")

    def fast_handler(spore):
        time.sleep(0.01)

    channel.subscribe("fast_agent", fast_handler)

    start = time.time()
    result = channel.shutdown(wait=True, timeout=5.0)
    elapsed = time.time() - start

    assert result is True
    assert elapsed < 5.0
    assert channel._shutdown is True

def test_shutdown_returns_false_on_timeout():
    """Verify shutdown returns False when timeout exceeded."""
    from praval.core.reef import ReefChannel, Spore, SporeType

    channel = ReefChannel("test")
    hang_event = threading.Event()

    def hanging_handler(spore):
        hang_event.wait(timeout=10)  # Will hang unless signaled

    channel.subscribe("hanging_agent", hanging_handler)

    # Send a spore to trigger handler
    spore = Spore(
        id="test",
        spore_type=SporeType.KNOWLEDGE,
        from_agent="sender",
        to_agent="hanging_agent",
        knowledge={},
        created_at=datetime.now()
    )
    channel.send_spore(spore)

    # Give handler time to start
    time.sleep(0.1)

    # Shutdown should timeout
    start = time.time()
    result = channel.shutdown(wait=True, timeout=0.5)
    elapsed = time.time() - start

    assert result is False
    assert elapsed < 1.0  # Timeout was enforced

    hang_event.set()  # Clean up

def test_cleanup_loop_logs_errors():
    """Verify cleanup loop logs errors instead of silently ignoring."""
    from praval.core.reef import Reef
    import logging

    reef = Reef()

    # Create a channel that raises on cleanup
    mock_channel = Mock()
    mock_channel.cleanup_expired.side_effect = RuntimeError("Test error")
    reef.channels["broken"] = mock_channel

    # Manually run one cleanup iteration
    with patch.object(reef, '_shutdown', False):
        with patch('time.sleep'):  # Speed up test
            # The cleanup should log warning, not crash
            with pytest.raises(StopIteration):
                # Run one iteration then stop
                def stop_after_one(*args):
                    reef._shutdown = True
                    raise StopIteration

                with patch.object(mock_channel, 'cleanup_expired', side_effect=stop_after_one):
                    reef._cleanup_loop()

def test_reef_shutdown_respects_total_timeout():
    """Verify reef shutdown respects total timeout across channels."""
    from praval.core.reef import Reef

    reef = Reef()
    reef.create_channel("ch1")
    reef.create_channel("ch2")
    reef.create_channel("ch3")

    start = time.time()
    result = reef.shutdown(wait=True, timeout=2.0)
    elapsed = time.time() - start

    assert result is True
    assert elapsed < 3.0  # Should complete well within timeout
```

---

#### 1.5 Spore payload size validation [S1]
**Files:** `src/praval/core/reef.py`

**Target:**
```python
# At top of file, after imports
MAX_SPORE_KNOWLEDGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_SPORE_METADATA_SIZE = 64 * 1024  # 64 KB
SAFE_TYPES = (str, int, float, bool, type(None))


def _validate_knowledge_types(obj: Any, path: str = "knowledge") -> None:
    """Recursively validate that knowledge contains only JSON-safe types.

    Args:
        obj: Object to validate
        path: Current path for error messages

    Raises:
        TypeError: If unsafe type is found
    """
    if isinstance(obj, SAFE_TYPES):
        return
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise TypeError(
                    f"Dictionary key at {path} must be string, got {type(k).__name__}"
                )
            _validate_knowledge_types(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj):
            _validate_knowledge_types(item, f"{path}[{i}]")
    else:
        raise TypeError(
            f"Unsafe type at {path}: {type(obj).__name__}. "
            f"Only str, int, float, bool, None, dict, list are allowed."
        )


class Reef:
    def send(self,
             from_agent: str,
             to_agent: Optional[str],
             knowledge: Dict[str, Any],
             ...):
        """Send a spore through the reef.

        Args:
            from_agent: Sending agent name
            to_agent: Target agent name (None for broadcasts)
            knowledge: Data payload (must be JSON-serializable, max 10MB)
            ...

        Raises:
            ValueError: If knowledge exceeds size limit or is not serializable
            TypeError: If knowledge contains unsafe types
        """
        # Validate channel exists
        if channel is None:
            channel = self.default_channel

        reef_channel = self.get_channel(channel)
        if not reef_channel:
            raise ValueError(f"Reef channel '{channel}' not found")

        # Validate knowledge types (security: prevent arbitrary object injection)
        _validate_knowledge_types(knowledge)

        # Validate knowledge size
        try:
            knowledge_json = json.dumps(knowledge)
            knowledge_size = len(knowledge_json.encode('utf-8'))

            if knowledge_size > MAX_SPORE_KNOWLEDGE_SIZE:
                raise ValueError(
                    f"Spore knowledge exceeds maximum size: {knowledge_size:,} bytes "
                    f"(max: {MAX_SPORE_KNOWLEDGE_SIZE:,} bytes). "
                    f"Consider using knowledge references for large payloads."
                )
        except TypeError as e:
            raise ValueError(f"Spore knowledge is not JSON serializable: {e}")

        # ... rest of existing send logic
```

**Test Strategy:**
```python
# tests/test_spore_validation.py
import pytest
from datetime import datetime

def test_send_rejects_oversized_knowledge():
    """Verify send() rejects payloads exceeding size limit."""
    from praval.core.reef import Reef, MAX_SPORE_KNOWLEDGE_SIZE

    reef = Reef()

    # Create knowledge that exceeds limit
    large_data = "x" * (MAX_SPORE_KNOWLEDGE_SIZE + 1000)

    with pytest.raises(ValueError, match="exceeds maximum size"):
        reef.send(
            from_agent="sender",
            to_agent="receiver",
            knowledge={"data": large_data}
        )

def test_send_rejects_non_serializable_objects():
    """Verify send() rejects non-JSON-serializable objects."""
    from praval.core.reef import Reef

    reef = Reef()

    class CustomObject:
        pass

    with pytest.raises(TypeError, match="Unsafe type"):
        reef.send(
            from_agent="sender",
            to_agent="receiver",
            knowledge={"custom": CustomObject()}
        )

def test_send_rejects_callable_in_knowledge():
    """Verify send() rejects functions in knowledge."""
    from praval.core.reef import Reef

    reef = Reef()

    with pytest.raises(TypeError, match="Unsafe type"):
        reef.send(
            from_agent="sender",
            to_agent="receiver",
            knowledge={"func": lambda x: x}
        )

def test_send_rejects_non_string_dict_keys():
    """Verify send() rejects non-string dictionary keys."""
    from praval.core.reef import Reef

    reef = Reef()

    with pytest.raises(TypeError, match="must be string"):
        reef.send(
            from_agent="sender",
            to_agent="receiver",
            knowledge={123: "value"}  # Integer key
        )

def test_send_accepts_nested_safe_types():
    """Verify send() accepts deeply nested safe types."""
    from praval.core.reef import Reef

    reef = Reef()

    nested_knowledge = {
        "string": "hello",
        "number": 42,
        "float": 3.14,
        "bool": True,
        "null": None,
        "list": [1, 2, {"nested": "dict"}],
        "dict": {"a": {"b": {"c": [1, 2, 3]}}}
    }

    spore_id = reef.send(
        from_agent="sender",
        to_agent="receiver",
        knowledge=nested_knowledge
    )

    assert spore_id is not None
    assert len(spore_id) > 0

def test_send_accepts_empty_knowledge():
    """Verify send() accepts empty knowledge dict."""
    from praval.core.reef import Reef

    reef = Reef()

    spore_id = reef.send(
        from_agent="sender",
        to_agent="receiver",
        knowledge={}
    )

    assert spore_id is not None

def test_validate_knowledge_types_recursive():
    """Verify validation handles deeply nested structures."""
    from praval.core.reef import _validate_knowledge_types

    # Valid deep nesting
    deep = {"a": {"b": {"c": {"d": {"e": [1, 2, 3]}}}}}
    _validate_knowledge_types(deep)  # Should not raise

    # Invalid type deep in structure
    bad_deep = {"a": {"b": {"c": {"d": {"e": [1, object()]}}}}}
    with pytest.raises(TypeError, match="Unsafe type"):
        _validate_knowledge_types(bad_deep)
```

---

### Phase 2: Performance & Memory Optimizations

*(Same content as v1 for sections 2.1-2.4)*

---

## Post-Implementation Validation

After implementing all changes, run full validation:

```bash
# 1. Run all existing tests
pytest tests/ -v --tb=short

# 2. Run with coverage to verify >80%
pytest tests/ --cov=praval --cov-report=html --cov-fail-under=80

# 3. Run new tests specifically
pytest tests/test_agent_logging.py tests/test_registry_thread_safety.py \
       tests/test_agent_lifecycle.py tests/test_reef_shutdown.py \
       tests/test_spore_validation.py -v

# 4. Run examples to verify backward compatibility
python examples/simple_multi_agent.py
python examples/001-simple-agent.py
python examples/002-multi-agent-chat.py

# 5. Run benchmarks and compare to baseline
python temp_plans/benchmark_baseline.py

# 6. Format and lint
black src tests
isort src tests
flake8 src tests
mypy src
```

---

## Implementation Order

### Sprint 1 (Phase 1 - Foundation) ✅ COMPLETE
- [x] **Establish baseline** (benchmarks, test results)
- [x] [S4] Replace print() with logger — `1c60550`
- [x] [M4] Thread-safe PravalRegistry — `c6f92a3`
- [x] [M2] Add Agent.close() and context manager — `41c2d42`
- [x] [M6, M3] Shutdown timeout and cleanup thread fix — `083794d`
- [x] [S1] Spore payload size validation — `6e78e0f`
- [x] **Additional:** Handle Python shutdown in Agent.__del__ — `e86ac84`
- [x] **Test fixes:** Resolve test suite issues — `3c6398e`, `882375a`, `013c6cf`, `ab05782`, `9e63103`

### Sprint 2 (Phase 2a - Memory Safety) ⏳ PENDING
- [ ] [M1] Handler cleanup in request_knowledge()
- [ ] [M5] Bounded conversation history
- [ ] **Run validation suite**

### Sprint 3 (Phase 2b - Performance) ⏳ PENDING
- [ ] [P1, P3] Persistent event loop
- [ ] [P2] Shared thread pool
- [ ] **Run benchmarks, compare to baseline**

---

## Success Metrics

| Metric | Baseline | Target | Method |
|--------|----------|--------|--------|
| Test Coverage | ~80% | >85% | pytest-cov |
| All Tests Pass | Yes | Yes | pytest |
| Examples Pass | Yes | Yes | Manual run |
| Message Throughput | TBD | +20% | Benchmark |
| Memory per Agent | TBD | Stable | Memory profiler |
| Shutdown Time | May hang | <5 sec | Integration test |

---

## Open Questions

1. Should we add a rate limiter to `reef.broadcast()`? (S2)
2. Should we make `Spore` immutable (frozen dataclass)? (A4)
3. What's the appropriate default for `max_history`? (Proposed: 100)
4. Should shared pool size be configurable per deployment? (Proposed: Yes, via constructor)

---

## Appendix: File Change Summary

| File | Changes |
|------|---------|
| `src/praval/core/agent.py` | Add logger import, replace prints, add close(), context manager, _subscribed_channels |
| `src/praval/core/reef.py` | Add validation, shutdown timeout, cleanup logging, constants |
| `src/praval/core/registry.py` | Add thread lock to PravalRegistry |
| `tests/test_agent_logging.py` | NEW |
| `tests/test_registry_thread_safety.py` | NEW |
| `tests/test_agent_lifecycle.py` | NEW |
| `tests/test_reef_shutdown.py` | NEW |
| `tests/test_spore_validation.py` | NEW |

---

## Appendix B: Comprehensive Downstream Impact Assessment

This section provides a thorough analysis of how these changes will affect downstream users, with particular emphasis on **negative impacts, risks, and migration challenges**.

### Impact Categories

- 🔴 **BREAKING** - Existing code will fail or behave differently
- 🟠 **BEHAVIORAL** - Code works but produces different results
- 🟡 **MIGRATION NEEDED** - Code works but should be updated
- 🟢 **TRANSPARENT** - No user action required

---

### 1. NEGATIVE IMPACTS (Critical to Understand)

#### 1.1 [S1] Spore Payload Validation - 🔴 BREAKING

**What Changes:**
- `reef.send()` and `reef.broadcast()` now reject payloads >10MB
- Non-JSON-serializable types (custom objects, functions, classes) are rejected
- Non-string dictionary keys are rejected

**Who Will Be Broken:**

| Use Case | Current Behavior | New Behavior | Severity |
|----------|------------------|--------------|----------|
| Sending large files/images as base64 in knowledge | Works (slowly) | `ValueError` raised | HIGH |
| Passing custom objects between agents | Works (may fail on serialization later) | `TypeError` raised immediately | HIGH |
| Using integer keys in knowledge dicts | Works | `TypeError` raised | MEDIUM |
| Sending numpy arrays directly | Works (serialization varies) | `TypeError` raised | MEDIUM |

**Code That Will Break:**
```python
# BEFORE: This worked (or failed silently later)
reef.send("agent1", "agent2", {
    "image": base64.b64encode(large_image).decode(),  # Could be >10MB
    "data": numpy_array,  # Non-JSON type
    123: "integer key",  # Non-string key
})

# AFTER: All three cause immediate exceptions
```

**Migration Path:**
```python
# For large payloads: Use knowledge references
from praval import create_knowledge_reference
ref = create_knowledge_reference(large_data)
reef.send("agent1", "agent2", {"data_ref": ref})

# For numpy arrays: Convert to list
reef.send("agent1", "agent2", {"data": array.tolist()})

# For integer keys: Convert to strings
reef.send("agent1", "agent2", {str(k): v for k, v in data.items()})
```

**Risk Assessment:**
- **Probability of impact:** MEDIUM - Most users send small JSON payloads
- **Severity if hit:** HIGH - Code will crash at runtime
- **Detectability:** HIGH - Clear error messages with guidance
- **Rollback difficulty:** LOW - Can revert to old behavior by removing validation

---

#### 1.2 [M5] Bounded Conversation History - 🟠 BEHAVIORAL

**What Changes:**
- `Agent.conversation_history` is now trimmed to 100 messages by default
- System message (if present) is always preserved
- Oldest non-system messages are removed when limit exceeded

**Who Will Be Affected:**

| Use Case | Current Behavior | New Behavior | Impact |
|----------|------------------|--------------|--------|
| Long-running chatbots | All history preserved | History trimmed at 100 | May lose context |
| Agents analyzing full conversation | Can access all messages | Only recent 100 | Analysis incomplete |
| Agents relying on message count | `len(history)` grows forever | Caps at ~100 | Logic may break |
| Memory-constrained deployments | OOM risk | Memory bounded | POSITIVE |

**Subtle Bugs This May Cause:**
```python
# BEFORE: Agent remembers everything from 2 hours ago
agent.chat("What was the first thing I asked you?")
# Returns correct answer from message #1

# AFTER: If >100 messages exchanged, message #1 is gone
agent.chat("What was the first thing I asked you?")
# Returns "I don't have that in our conversation history"
```

**Code That May Break:**
```python
# This logic assumes unbounded history
def get_all_user_questions(agent):
    return [m for m in agent.conversation_history if m["role"] == "user"]
# AFTER: Only returns up to ~50 user messages (half of 100)

# This assumes history length reflects conversation length
if len(agent.conversation_history) > 500:
    summarize_conversation(agent)
# AFTER: Never triggers because history caps at 100
```

**Migration Path:**
```python
# Option 1: Disable bounding (NOT RECOMMENDED - restores OOM risk)
agent = Agent("chatbot", max_history=None)

# Option 2: Increase limit
agent = Agent("chatbot", max_history=1000)

# Option 3: Implement external history storage
class PersistentAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.full_history = []  # Store externally

    def chat(self, message):
        self.full_history.append({"role": "user", "content": message})
        response = super().chat(message)
        self.full_history.append({"role": "assistant", "content": response})
        return response
```

**Risk Assessment:**
- **Probability of impact:** MEDIUM - Affects long conversations
- **Severity if hit:** MEDIUM - Degrades gracefully (loses old context)
- **Detectability:** LOW - No error, just different behavior
- **Rollback difficulty:** LOW - Set `max_history=None`

---

#### 1.3 [M6] Shutdown Timeout - 🟠 BEHAVIORAL

**What Changes:**
- `reef.shutdown()` now returns `bool` instead of `None`
- Default 30-second timeout enforced
- Stuck handlers are abandoned after timeout

**Negative Consequences:**

| Scenario | Current Behavior | New Behavior | Risk |
|----------|------------------|--------------|------|
| Handler processing large job | Waits forever | Abandoned after 30s | Data loss |
| Cleanup code checking return value | `shutdown()` returns `None` | Returns `True/False` | Logic may break |
| Long-running shutdown procedures | Complete eventually | May be cut short | Incomplete cleanup |

**Code That May Break:**
```python
# BEFORE: This worked (None is falsy)
result = reef.shutdown()
if not result:  # Always true because None is falsy
    print("Shutdown had issues")  # Always printed

# AFTER: Returns True on success
result = reef.shutdown()
if not result:  # Only true on actual timeout
    print("Shutdown had issues")  # Only printed on real problems
```

**Data Loss Scenario:**
```python
@agent("processor")
def data_processor(spore):
    # Processing 10GB file, takes 5 minutes
    result = process_huge_file(spore.knowledge["file_path"])
    save_to_database(result)
    return {"status": "done"}

# If shutdown() called during processing:
# BEFORE: Waits 5 minutes, processing completes, data saved
# AFTER: Waits 30 seconds, handler abandoned, data NOT saved
```

**Migration Path:**
```python
# Option 1: Increase timeout for long operations
reef.shutdown(timeout=300)  # 5 minutes

# Option 2: Check return value and handle appropriately
if not reef.shutdown(timeout=60):
    logger.error("Some handlers did not complete - data may be lost")
    # Implement recovery logic

# Option 3: Use graceful shutdown pattern
class GracefulAgent:
    def __init__(self):
        self._shutting_down = False

    def handle(self, spore):
        if self._shutting_down:
            return {"status": "rejected", "reason": "shutting down"}
        # ... normal processing
```

**Risk Assessment:**
- **Probability of impact:** LOW - Most handlers complete quickly
- **Severity if hit:** HIGH - Potential data loss
- **Detectability:** MEDIUM - Returns False, but may not be checked
- **Rollback difficulty:** LOW - Set `timeout=float('inf')` (not recommended)

---

#### 1.4 [P2] Shared Thread Pool - 🟡 MIGRATION NEEDED

**What Changes:**
- All channels share a single thread pool (16 workers by default)
- Previously each channel had its own pool (4 workers each)

**Negative Consequences:**

| Scenario | Current Behavior | New Behavior | Risk |
|----------|------------------|--------------|------|
| 10 channels, light load | 40 threads available | 16 threads shared | Lower parallelism |
| One slow handler | Blocks 1 of 4 threads in its channel | Blocks 1 of 16 shared | Cross-channel impact |
| Thread-local storage | Each channel isolated | All channels share threads | Data leakage |
| Debugging with thread names | `reef-channelname-0` | `reef-shared-0` | Harder to trace |

**Thread Starvation Scenario:**
```python
# Channel A has slow handlers (1 second each)
# Channel B has fast handlers (1 millisecond each)

# BEFORE:
# - Channel A uses its 4 threads, processes 4/sec
# - Channel B uses its 4 threads, processes 4000/sec (independent)

# AFTER:
# - Shared pool of 16 threads
# - If Channel A saturates pool with slow handlers, Channel B starves
```

**Thread-Local Storage Bug:**
```python
import threading
local = threading.local()

@agent("agent_a", channel="channel_a")
def agent_a(spore):
    local.user_id = spore.knowledge["user_id"]
    # ... processing

@agent("agent_b", channel="channel_b")
def agent_b(spore):
    # BEFORE: Different thread pool, local.user_id not set
    # AFTER: Same thread pool, might see agent_a's user_id!
    print(local.user_id)  # Could print wrong user's ID
```

**Migration Path:**
```python
# Option 1: Opt out of shared pool for specific channels
reef.create_channel("critical_channel", use_shared_pool=False)

# Option 2: Increase shared pool size
reef = Reef(shared_pool_size=64)

# Option 3: Don't use thread-local storage (recommended)
# Pass context through spore.knowledge instead
```

**Risk Assessment:**
- **Probability of impact:** LOW - Most apps don't use thread-local storage
- **Severity if hit:** MEDIUM - Performance degradation or data bugs
- **Detectability:** LOW - Subtle behavioral changes
- **Rollback difficulty:** LOW - `use_shared_pool=False`

---

### 2. OPERATIONAL IMPACTS

#### 2.1 Logging Volume Increase [S4, M3]

**What Changes:**
- `print()` statements converted to `logger.info()` / `logger.warning()`
- Cleanup thread now logs errors instead of silently ignoring

**Negative Impact:**
- **Log volume will increase** - Previously silent operations now logged
- **Log aggregation costs** - More data to Datadog/Splunk/etc.
- **Alert fatigue** - New warnings may trigger existing alert rules

**Example New Log Output:**
```
INFO praval.core.agent - Memory system initialized for agent researcher
INFO praval.core.agent - Memory system initialized for agent writer
WARNING praval.core.reef - Error cleaning up channel main: Connection reset
WARNING praval.core.reef - Cleanup thread encountered error: TimeoutError
DEBUG praval.core.agent - Agent researcher closed
```

**Migration:**
```python
# Suppress if needed
import logging
logging.getLogger("praval.core.agent").setLevel(logging.ERROR)
logging.getLogger("praval.core.reef").setLevel(logging.ERROR)
```

---

#### 2.2 Memory Usage Changes

| Change | Memory Impact | Direction |
|--------|---------------|-----------|
| Bounded history (M5) | -50KB to -5MB per agent | DECREASE |
| Shared thread pool (P2) | -8MB per channel removed | DECREASE |
| Thread lock in registry (M4) | +1KB | INCREASE (negligible) |
| Persistent event loop (P1) | +2MB for loop thread | INCREASE (one-time) |

**Net Impact:** Memory usage should DECREASE for most applications.

**Edge Case:** Applications with few channels but many agents may see slight increase due to persistent event loop overhead.

---

#### 2.3 Timing/Performance Changes

| Change | Latency Impact | Throughput Impact |
|--------|----------------|-------------------|
| Spore validation (S1) | +0.1-1ms per send | -5% for small payloads |
| Persistent event loop (P1) | -10-100ms for distributed | +10-100x for RabbitMQ |
| Shared thread pool (P2) | ±0 for most cases | Variable |
| Thread-safe registry (M4) | +0.01ms per registration | Negligible |

**Net Impact:** Performance should IMPROVE for distributed deployments, be NEUTRAL for local-only use.

**Regression Risk:** Spore validation adds overhead. For applications sending thousands of small spores per second, this could be noticeable.

---

### 3. TESTING & DEPLOYMENT RISKS

#### 3.1 Test Suite Impact

**Tests That May Fail After Upgrade:**

```python
# Test expecting unbounded history
def test_long_conversation():
    agent = Agent("test")
    for i in range(200):
        agent.chat(f"Message {i}")
    assert len(agent.conversation_history) == 400  # FAILS: Now capped

# Test expecting None return from shutdown
def test_shutdown():
    reef = Reef()
    result = reef.shutdown()
    assert result is None  # FAILS: Now returns True

# Test sending custom objects
def test_send_custom_data():
    reef = Reef()
    reef.send("a", "b", {"obj": MyClass()})  # FAILS: TypeError
```

#### 3.2 CI/CD Pipeline Impact

- **Longer test runs:** New thread safety tests add ~5-10 seconds
- **New test dependencies:** None
- **Coverage changes:** May decrease initially if new code paths not tested

#### 3.3 Rollout Recommendations

| Environment | Recommendation |
|-------------|----------------|
| Development | Deploy immediately, fix tests |
| Staging | Deploy, run full integration suite, monitor logs |
| Production | Canary deploy to 5%, monitor for 24h, then gradual rollout |

**Rollback Triggers:**
- Error rate increase >1%
- P95 latency increase >50%
- Memory usage increase >20%
- Any data loss reports

---

### 4. COMPATIBILITY MATRIX

#### 4.1 Python Version Compatibility

| Change | Python 3.9 | Python 3.10 | Python 3.11 | Python 3.12 |
|--------|------------|-------------|-------------|-------------|
| Shutdown timeout | Uses `join(timeout)` | Same | Same | Same |
| Thread locks | `threading.RLock` | Same | Same | Same |
| Event loop | `asyncio.new_event_loop()` | Same | Same | Same |
| Type validation | Works | Works | Works | Works |

All changes are compatible with Python 3.9+.

#### 4.2 Dependency Compatibility

| Dependency | Version | Impact |
|------------|---------|--------|
| pydantic | >=2.0.0 | No change |
| openai | >=1.0.0 | No change |
| chromadb | >=0.4.0 | No change |
| aio-pika | >=9.0.0 | Benefits from P1 fix |

No dependency changes required.

#### 4.3 Integration Compatibility

| Integration | Status | Notes |
|-------------|--------|-------|
| FastAPI | Compatible | Agent.close() useful for dependency cleanup |
| Flask | Compatible | Same |
| Celery | Compatible | May need increased shutdown timeout |
| Kubernetes | Compatible | Shutdown timeout helps with graceful termination |
| Docker | Compatible | Same |

---

### 5. SUMMARY: WHAT USERS MUST DO

#### Immediate Action Required (Before Upgrade)

1. **Audit spore payloads** - Check if any are >10MB or contain non-JSON types
2. **Audit conversation length assumptions** - Check code that assumes unbounded history
3. **Audit shutdown handling** - Check code that examines `shutdown()` return value

#### Recommended Action (After Upgrade)

1. **Adopt context manager pattern** for agents in web apps:
   ```python
   with Agent("assistant") as agent:
       response = agent.chat(user_message)
   ```

2. **Set explicit max_history** if 100 is wrong for your use case:
   ```python
   agent = Agent("chatbot", max_history=500)
   ```

3. **Update logging configuration** if you need to suppress new log messages

#### No Action Required

- Thread safety improvements (M4)
- Cleanup thread logging (M3)
- Performance improvements (P1, P2, P3)
- Handler cleanup fix (M1)

---

### 6. RISK SUMMARY MATRIX

| ID | Change | Break Probability | Severity | Detectability | Overall Risk |
|----|--------|-------------------|----------|---------------|--------------|
| S1 | Payload validation | 15% | HIGH | HIGH | 🟠 MEDIUM |
| M5 | Bounded history | 25% | MEDIUM | LOW | 🟠 MEDIUM |
| M6 | Shutdown timeout | 5% | HIGH | MEDIUM | 🟡 LOW-MEDIUM |
| P2 | Shared pool | 10% | MEDIUM | LOW | 🟡 LOW-MEDIUM |
| S4 | Logging | 5% | LOW | HIGH | 🟢 LOW |
| M4 | Thread safety | 1% | LOW | HIGH | 🟢 LOW |
| M3 | Cleanup logging | 1% | LOW | HIGH | 🟢 LOW |
| M2 | Agent.close() | 0% | N/A | N/A | 🟢 NONE |
| M1 | Handler cleanup | 0% | N/A | N/A | 🟢 NONE |
| P1 | Persistent loop | 2% | LOW | MEDIUM | 🟢 LOW |
| P3 | Async handlers | 1% | LOW | MEDIUM | 🟢 LOW |

**Overall Assessment:** MEDIUM risk. Two changes (S1, M5) have meaningful probability of affecting users. Both have clear migration paths and the benefits outweigh the risks.

---

## Tool System Completion (T) - Full-Fledged Tool Support

### Goals
- Unify tool registration and metadata so agents, registry, and providers use one canonical format.
- Provide consistent tool calling across OpenAI, Anthropic, and Cohere.
- Deliver a straightforward, documented API with working examples.

### Scope
- **T1** Unify tool registration: bridge `Agent.tool` into `ToolRegistry` and keep tool names stable.
- **T2** Provider parity: implement tool calling and follow-up responses for Anthropic/Cohere.
- **T3** Tool discovery: implement module and pattern discovery (not stubbed).
- **T4** `@agent` tool params: add `tools=`, `tool_categories=`, and `auto_discover_tools=`.
- **T5** Docs + examples: replace placeholder tutorial and align spec with code.

### Implementation Steps
1. **Canonical tool schema**
   - Normalize to `{"function", "description", "parameters"}` with stable tool names.
   - When `Agent.tool` is used, auto-register into `ToolRegistry` with metadata.

2. **Decorator integration**
   - Extend `@agent` to accept `tools`, `tool_categories`, `auto_discover_tools`.
   - Resolve tool names or callables via `ToolRegistry` and attach to agent tools.

3. **Provider support**
   - Implement tool schema conversion for Anthropic/Cohere.
   - Add tool call execution path and follow-up response handling, similar to OpenAI.

4. **Discovery**
   - `discover_tools(module=...)`: import module and register decorated tools.
   - `discover_tools(pattern=...)`: glob files, import, and register tools.
   - Fail-safe: log errors, do not crash agent startup.

5. **Docs + tests**
   - Replace `docs/sphinx/tutorials/tool-integration.md` placeholder.
   - Add provider tool-call tests for Anthropic/Cohere.
   - Add integration examples under `examples/`.


### Test Expectations
- **Unit**: validate tool registration (name stability, metadata extraction, type hints required).
- **Decorator**: `@agent` tool params resolve tool names, categories, and auto-discovery correctly.
- **Provider parity**: Anthropic/Cohere tool calls execute tools and return follow-up responses.
- **Discovery**: module and pattern discovery register tools without crashing on import errors.
- **Integration**: end-to-end tool call flows with at least one provider.

### Examples (Authoritative API)

**1) Minimal Tool + Agent**
```python
from praval import agent, tool, start_agents, get_reef

@tool("add_numbers", owned_by="calculator", category="math")
def add(x: int, y: int) -> int:
    return x + y

@agent("calculator", tools=["add_numbers"])
def calc(spore):
    return {"result": add(2, 3)}

start_agents(calc, initial_data={"type": "run"})
get_reef().wait_for_completion()
get_reef().shutdown()
```

**2) Shared Tool Across Agents**
```python
from praval import agent, tool

@tool("logger", shared=True, category="utility")
def log(level: str, message: str) -> str:
    import logging
    logging.getLogger("praval.tools").info(f"[{level}] {message}")
    return "ok"

@agent("writer")
def writer(spore):
    log("info", "writing started")
    return {"status": "done"}
```

**3) Category-Based Tools + Provider Tool Call**
```python
from praval import agent, tool, Agent

@tool("weather", category="external", shared=True)
def get_weather(city: str) -> str:
    return f"Sunny in {city}"

@agent("assistant", tool_categories=["external"])
def assistant(spore):
    return {"answer": "Ask me the weather."}

llm = Agent("assistant")
llm.tools["weather"] = {
    "function": get_weather,
    "description": "Get weather",
    "parameters": {"city": {"type": "str", "required": True}}
}
print(llm.chat("What's the weather in Paris?"))
```
