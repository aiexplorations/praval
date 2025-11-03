# Praval Observability Design Refinement
**Multi-Level Control & Standard Metrics**

**Date**: November 2024
**Status**: Design Proposal

---

## Problem Statement

The initial design has observability as **always-on at framework level** with only a global environment variable for control. This lacks:

1. **Agent-level control**: Can't choose which agents to observe
2. **Metric-level control**: Can't choose which metrics to collect
3. **Script-level control**: Can't configure per-script
4. **Standard metrics definition**: No clear definition of what metrics are "standard"

---

## Improved Design: Three Levels of Control

### Level 1: Framework Default (Global)

**Default behavior if nothing specified**:

```python
# In praval config or environment
PRAVAL_OBSERVABILITY_MODE=auto  # auto | enabled | disabled

# auto = enabled for dev, disabled for production (detect via env)
# enabled = always on
# disabled = always off
```

**Config file** (`~/.praval/config.yaml`):
```yaml
observability:
  mode: auto  # auto | enabled | disabled
  default_metrics:
    - latency
    - errors
    - llm_tokens
    - llm_cost
  storage:
    backend: sqlite
    path: ~/.praval/traces.db
  exporters:
    - console
```

---

### Level 2: Script-Level Configuration

**Configure at the top of your script**:

```python
from praval import agent, configure_observability

# Configure for THIS script
configure_observability(
    enabled=True,
    metrics=[
        "latency",           # Execution time
        "errors",            # Error tracking
        "llm_tokens",        # Token usage
        "llm_cost",          # Cost tracking
        "memory_operations", # Memory queries
        "message_flow"       # Inter-agent messages
    ],
    export_to=["console", "sqlite"],
    sample_rate=1.0  # 100% sampling
)

# Now define agents - they inherit this config
@agent("researcher")
def research_agent(spore):
    return result
```

**Advantages**:
- ✅ Per-script control
- ✅ Choose which metrics to collect
- ✅ Configure export destinations
- ✅ Set sampling rate
- ✅ Override framework defaults

---

### Level 3: Agent-Level Configuration

**Configure per-agent**:

```python
from praval import agent

# Agent with custom observability
@agent(
    "researcher",
    observability={
        "enabled": True,
        "metrics": ["latency", "llm_cost"],
        "sample_rate": 0.1,  # Only sample 10% of calls
        "custom_attributes": {
            "team": "research",
            "criticality": "high"
        }
    }
)
def research_agent(spore):
    return result

# Agent with observability disabled
@agent(
    "background_worker",
    observability=False  # Shorthand to disable
)
def background_agent(spore):
    return result

# Agent with default observability (inherits script/framework config)
@agent("analyzer")
def analyzer_agent(spore):
    return result  # Uses defaults
```

**Advantages**:
- ✅ Per-agent control
- ✅ Different sampling rates per agent
- ✅ Custom attributes per agent
- ✅ Can disable for non-critical agents
- ✅ Fine-grained performance tuning

---

## Standard Metrics Definition

### Core Standard Metrics (Always Collected When Enabled)

These are **built-in** and require zero configuration:

```python
STANDARD_METRICS = {
    # Timing Metrics
    "latency": {
        "description": "Agent execution time",
        "unit": "milliseconds",
        "type": "histogram",
        "always_on": True
    },

    # Error Metrics
    "errors": {
        "description": "Error count and types",
        "type": "counter",
        "always_on": True
    },

    # LLM Metrics
    "llm_calls": {
        "description": "Number of LLM API calls",
        "type": "counter",
        "always_on": False  # Opt-in
    },
    "llm_tokens": {
        "description": "Token usage (input/output)",
        "type": "histogram",
        "always_on": False
    },
    "llm_cost": {
        "description": "Estimated API cost",
        "unit": "USD",
        "type": "histogram",
        "always_on": False
    },

    # Memory Metrics
    "memory_operations": {
        "description": "Memory store/recall operations",
        "type": "counter",
        "always_on": False
    },
    "memory_latency": {
        "description": "Memory operation latency",
        "unit": "milliseconds",
        "type": "histogram",
        "always_on": False
    },

    # Communication Metrics
    "messages_sent": {
        "description": "Spores broadcast/sent",
        "type": "counter",
        "always_on": False
    },
    "messages_received": {
        "description": "Spores received",
        "type": "counter",
        "always_on": False
    },
    "message_flow": {
        "description": "Inter-agent message tracing",
        "type": "trace",
        "always_on": False
    }
}
```

### Metric Categories

**Minimal** (Default for production):
- `latency` (always on)
- `errors` (always on)

**Standard** (Default for development):
- `latency`
- `errors`
- `llm_calls`
- `llm_tokens`
- `llm_cost`

**Full** (Debugging/analysis):
- All metrics enabled

**Custom**: Choose specific metrics

---

## Configuration Hierarchy (Priority Order)

```
1. Agent-level config (highest priority)
   ↓
2. Script-level config
   ↓
3. Config file (~/.praval/config.yaml)
   ↓
4. Environment variables
   ↓
5. Framework defaults (lowest priority)
```

### Example: How Priority Works

```python
# Environment: PRAVAL_OBSERVABILITY_MODE=disabled
# Config file: mode: auto, metrics: [latency, errors]

# Script level
configure_observability(
    enabled=True,  # Overrides env var
    metrics=["latency", "llm_cost"]  # Overrides config file
)

@agent("researcher")  # Uses: enabled=True, metrics=[latency, llm_cost]
def researcher_agent(spore):
    pass

@agent(
    "expensive",
    observability={
        "sample_rate": 0.1  # Adds to script config
    }
)  # Uses: enabled=True, metrics=[latency, llm_cost], sample_rate=0.1
def expensive_agent(spore):
    pass

@agent(
    "disabled",
    observability=False  # Overrides everything
)  # Observability completely disabled
def disabled_agent(spore):
    pass
```

---

## Revised API Design

### 1. Framework-Level Configuration

**File**: `src/praval/observability/config.py`

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

class ObservabilityMode(Enum):
    AUTO = "auto"      # Smart default (dev=on, prod=off)
    ENABLED = "enabled"
    DISABLED = "disabled"

class MetricLevel(Enum):
    MINIMAL = "minimal"    # latency, errors only
    STANDARD = "standard"  # + LLM metrics
    FULL = "full"         # All metrics
    CUSTOM = "custom"     # User-specified list

@dataclass
class ObservabilityConfig:
    """Global observability configuration."""

    mode: ObservabilityMode = ObservabilityMode.AUTO
    metric_level: MetricLevel = MetricLevel.STANDARD
    custom_metrics: List[str] = field(default_factory=list)

    # Storage
    storage_backend: str = "sqlite"
    storage_path: str = "~/.praval/traces.db"

    # Export
    exporters: List[str] = field(default_factory=lambda: ["console"])
    otlp_endpoint: Optional[str] = None

    # Performance
    sample_rate: float = 1.0
    async_recording: bool = True
    batch_size: int = 10

    # Feature flags
    collect_traces: bool = True
    collect_metrics: bool = True
    collect_logs: bool = True

    def is_enabled(self) -> bool:
        """Check if observability is enabled."""
        if self.mode == ObservabilityMode.DISABLED:
            return False
        elif self.mode == ObservabilityMode.ENABLED:
            return True
        else:  # AUTO
            # Enable for dev environments
            return not self._is_production_env()

    def _is_production_env(self) -> bool:
        """Detect if running in production."""
        env = os.getenv("ENVIRONMENT", "").lower()
        return env in ["production", "prod"]

    def get_enabled_metrics(self) -> List[str]:
        """Get list of enabled metrics."""
        if self.metric_level == MetricLevel.MINIMAL:
            return ["latency", "errors"]
        elif self.metric_level == MetricLevel.STANDARD:
            return ["latency", "errors", "llm_calls", "llm_tokens", "llm_cost"]
        elif self.metric_level == MetricLevel.FULL:
            return list(STANDARD_METRICS.keys())
        else:  # CUSTOM
            return self.custom_metrics

# Global config instance
_global_config = ObservabilityConfig()

def get_observability_config() -> ObservabilityConfig:
    """Get global observability config."""
    return _global_config
```

### 2. Script-Level Configuration

**File**: `src/praval/observability/__init__.py`

```python
def configure_observability(
    enabled: Optional[bool] = None,
    metrics: Optional[Union[str, List[str]]] = None,
    export_to: Optional[List[str]] = None,
    sample_rate: Optional[float] = None,
    storage: Optional[str] = None,
    **kwargs
) -> None:
    """
    Configure observability for the current script.

    Args:
        enabled: Enable/disable observability (overrides mode)
        metrics: Metrics to collect ("minimal"|"standard"|"full"|list)
        export_to: Export destinations (["console", "sqlite", "otlp"])
        sample_rate: Sampling rate (0.0-1.0)
        storage: Storage backend ("sqlite"|"memory")
        **kwargs: Additional configuration

    Example:
        configure_observability(
            enabled=True,
            metrics=["latency", "llm_cost"],
            export_to=["console", "sqlite"],
            sample_rate=1.0
        )
    """
    config = get_observability_config()

    if enabled is not None:
        config.mode = ObservabilityMode.ENABLED if enabled else ObservabilityMode.DISABLED

    if metrics is not None:
        if isinstance(metrics, str):
            config.metric_level = MetricLevel[metrics.upper()]
        else:
            config.metric_level = MetricLevel.CUSTOM
            config.custom_metrics = metrics

    if export_to is not None:
        config.exporters = export_to

    if sample_rate is not None:
        config.sample_rate = sample_rate

    if storage is not None:
        config.storage_backend = storage

    # Apply any additional kwargs
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    # Re-initialize instrumentation with new config
    _reinitialize_instrumentation()


def get_metrics_config() -> Dict[str, Any]:
    """Get current metrics configuration."""
    config = get_observability_config()
    return {
        "enabled": config.is_enabled(),
        "metrics": config.get_enabled_metrics(),
        "sample_rate": config.sample_rate,
        "exporters": config.exporters
    }
```

### 3. Agent-Level Configuration

**File**: `src/praval/decorators.py` (modifications)

```python
@dataclass
class AgentObservabilityConfig:
    """Per-agent observability configuration."""

    enabled: bool = True
    metrics: Optional[List[str]] = None  # None = inherit from global
    sample_rate: Optional[float] = None  # None = inherit from global
    custom_attributes: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict_or_bool(cls, config: Union[bool, Dict, None]) -> 'AgentObservabilityConfig':
        """Create from decorator parameter."""
        if config is None:
            return cls()  # Defaults
        elif isinstance(config, bool):
            return cls(enabled=config)
        else:
            return cls(**config)


def agent(
    name: str,
    *,
    responds_to: Optional[List[str]] = None,
    memory: bool = False,
    knowledge_base: Optional[str] = None,
    observability: Union[bool, Dict, None] = None,  # NEW PARAMETER
    **kwargs
) -> Callable:
    """
    Agent decorator with observability configuration.

    Args:
        name: Agent identifier
        responds_to: Message types to respond to
        memory: Enable memory system
        knowledge_base: Path to knowledge base
        observability: Observability config (bool to enable/disable, dict for detailed config)

    Example:
        # Use defaults
        @agent("researcher")
        def research_agent(spore): pass

        # Disable observability
        @agent("background", observability=False)
        def background_agent(spore): pass

        # Custom configuration
        @agent("expensive", observability={
            "enabled": True,
            "metrics": ["latency", "llm_cost"],
            "sample_rate": 0.1,
            "custom_attributes": {"team": "research"}
        })
        def expensive_agent(spore): pass
    """

    def decorator(func: Callable) -> Callable:
        # Parse observability config
        obs_config = AgentObservabilityConfig.from_dict_or_bool(observability)

        # Store config on function
        func._observability_config = obs_config

        # Rest of agent decorator logic...
        # The instrumentation layer will read func._observability_config

        return wrapped_func

    return decorator
```

### 4. Instrumentation Layer (Reads Configuration)

**File**: `src/praval/observability/instrumentation/agent.py`

```python
class AgentInstrumentor(BaseInstrumentor):
    """Instrument agent execution with configuration awareness."""

    def _should_instrument_agent(self, agent_func) -> bool:
        """Check if agent should be instrumented."""
        global_config = get_observability_config()

        # Check global enabled state
        if not global_config.is_enabled():
            return False

        # Check agent-level config
        if hasattr(agent_func, '_observability_config'):
            agent_config = agent_func._observability_config
            return agent_config.enabled

        return True  # Default to enabled

    def _should_sample_execution(self, agent_func) -> bool:
        """Check if this execution should be sampled."""
        global_config = get_observability_config()

        # Get agent-specific sample rate if available
        sample_rate = global_config.sample_rate
        if hasattr(agent_func, '_observability_config'):
            agent_config = agent_func._observability_config
            if agent_config.sample_rate is not None:
                sample_rate = agent_config.sample_rate

        return random.random() < sample_rate

    def _get_enabled_metrics(self, agent_func) -> List[str]:
        """Get enabled metrics for this agent."""
        global_config = get_observability_config()

        # Check for agent-specific metrics
        if hasattr(agent_func, '_observability_config'):
            agent_config = agent_func._observability_config
            if agent_config.metrics is not None:
                return agent_config.metrics

        # Fall back to global config
        return global_config.get_enabled_metrics()

    def _get_custom_attributes(self, agent_func) -> Dict[str, Any]:
        """Get custom attributes for this agent."""
        if hasattr(agent_func, '_observability_config'):
            agent_config = agent_func._observability_config
            return agent_config.custom_attributes
        return {}

    def _create_traced_handler(self, handler, agent_name):
        """Create instrumented handler with config awareness."""

        @functools.wraps(handler)
        def traced_handler(spore):
            # Check if should instrument
            if not self._should_instrument_agent(handler):
                return handler(spore)

            # Check sampling
            if not self._should_sample_execution(handler):
                return handler(spore)

            # Get enabled metrics
            enabled_metrics = self._get_enabled_metrics(handler)

            # Get custom attributes
            custom_attrs = self._get_custom_attributes(handler)

            # Create span
            parent_ctx = TraceContext.from_spore(spore)
            with self.tracer.start_span(
                f"agent.{agent_name}.execute",
                parent=parent_ctx
            ) as span:
                # Set standard attributes
                span.set_attribute("agent.name", agent_name)
                span.set_attribute("spore.id", spore.id)

                # Set custom attributes
                for key, value in custom_attrs.items():
                    span.set_attribute(f"agent.{key}", value)

                # Set metric collection flags
                span.set_attribute("metrics.enabled", enabled_metrics)

                try:
                    result = handler(spore)

                    # Collect only enabled metrics
                    if "llm_calls" in enabled_metrics:
                        # Record LLM call count
                        pass

                    if "memory_operations" in enabled_metrics:
                        # Record memory operations
                        pass

                    span.set_status("ok")
                    return result
                except Exception as e:
                    if "errors" in enabled_metrics:
                        span.record_exception(e)
                    span.set_status("error", str(e))
                    raise

        return traced_handler
```

---

## Usage Examples

### Example 1: Minimal Configuration (Production)

```python
from praval import agent, configure_observability

# Minimal metrics for production
configure_observability(
    enabled=True,
    metrics="minimal",  # Only latency and errors
    export_to=["sqlite"],
    sample_rate=0.1  # Sample 10% of calls
)

@agent("researcher")
def research_agent(spore):
    return result  # Only latency and errors tracked, 10% sampling
```

### Example 2: Development with Full Metrics

```python
from praval import agent, configure_observability

# Full metrics for development
configure_observability(
    enabled=True,
    metrics="full",  # All metrics
    export_to=["console", "sqlite"],
    sample_rate=1.0  # 100% sampling
)

@agent("researcher")
def research_agent(spore):
    return result  # All metrics tracked
```

### Example 3: Mixed Agent Configuration

```python
from praval import agent, configure_observability

# Script-level: Standard metrics
configure_observability(
    enabled=True,
    metrics="standard",
    export_to=["console"]
)

# Critical agent: Full observability
@agent(
    "critical_processor",
    observability={
        "enabled": True,
        "metrics": ["latency", "errors", "llm_cost"],
        "sample_rate": 1.0,
        "custom_attributes": {
            "criticality": "high",
            "team": "core"
        }
    }
)
def critical_agent(spore):
    return result  # Full tracking, 100% sampling

# Background agent: Minimal observability
@agent(
    "background_worker",
    observability={
        "enabled": True,
        "metrics": ["errors"],  # Only errors
        "sample_rate": 0.01  # 1% sampling
    }
)
def background_agent(spore):
    return result  # Minimal tracking, 1% sampling

# Disabled agent
@agent("internal_helper", observability=False)
def helper_agent(spore):
    return result  # No tracking
```

### Example 4: Cost-Aware Configuration

```python
from praval import agent, configure_observability

# Focus on cost tracking
configure_observability(
    enabled=True,
    metrics=["latency", "errors", "llm_cost"],  # Custom list
    export_to=["sqlite"]
)

@agent("expensive_researcher")
def research_agent(spore):
    result = chat("Do expensive research")  # Cost tracked
    return result

# View cost report
from praval.observability import get_cost_report

report = get_cost_report(hours=24)
print(f"Total cost (24h): ${report['total_cost']:.2f}")
print(f"By agent: {report['by_agent']}")
```

### Example 5: Environment-Aware (Auto Mode)

```python
from praval import agent
# No explicit configuration - uses AUTO mode

@agent("researcher")
def research_agent(spore):
    return result

# Behavior:
# - Development (ENVIRONMENT=dev): Full observability
# - Production (ENVIRONMENT=production): Disabled by default
# - Unknown environment: Standard observability
```

---

## Configuration File Support

**File**: `~/.praval/config.yaml`

```yaml
observability:
  mode: auto  # auto | enabled | disabled

  metrics:
    level: standard  # minimal | standard | full | custom
    custom:  # If level=custom
      - latency
      - errors
      - llm_cost

  sampling:
    default: 1.0  # 100%
    by_agent:
      expensive_agent: 0.1  # Override for specific agents
      background_*: 0.01    # Pattern matching

  storage:
    backend: sqlite
    path: ~/.praval/traces.db
    max_size_mb: 500
    retention_days: 30

  export:
    console:
      enabled: true
      format: tree  # tree | table | json
    sqlite:
      enabled: true
    otlp:
      enabled: false
      endpoint: http://localhost:4318/v1/traces

  performance:
    async_recording: true
    batch_size: 10
    max_queue_size: 1000
```

---

## Standard Metrics Implementation

**File**: `src/praval/observability/metrics/standard.py`

```python
class StandardMetrics:
    """Standard metrics collected by Praval observability."""

    @staticmethod
    def collect_latency(span: Span, start_time: float, end_time: float):
        """Collect latency metric."""
        duration_ms = (end_time - start_time) * 1000
        span.set_attribute("metric.latency_ms", duration_ms)
        return {"latency_ms": duration_ms}

    @staticmethod
    def collect_errors(span: Span, error: Optional[Exception]):
        """Collect error metric."""
        if error:
            span.set_attribute("metric.error", True)
            span.set_attribute("metric.error_type", type(error).__name__)
            return {"error": True, "error_type": type(error).__name__}
        return {"error": False}

    @staticmethod
    def collect_llm_tokens(span: Span, usage):
        """Collect LLM token usage."""
        if usage:
            span.set_attribute("metric.llm.tokens.input", usage.prompt_tokens)
            span.set_attribute("metric.llm.tokens.output", usage.completion_tokens)
            span.set_attribute("metric.llm.tokens.total", usage.total_tokens)
            return {
                "llm_tokens_input": usage.prompt_tokens,
                "llm_tokens_output": usage.completion_tokens,
                "llm_tokens_total": usage.total_tokens
            }
        return {}

    @staticmethod
    def collect_llm_cost(span: Span, provider: str, model: str, usage):
        """Collect LLM cost."""
        cost = calculate_cost(provider, model, usage)
        span.set_attribute("metric.llm.cost", cost)
        return {"llm_cost_usd": cost}

    @staticmethod
    def collect_memory_operations(span: Span, operation_type: str, count: int):
        """Collect memory operation metrics."""
        span.set_attribute("metric.memory.operation", operation_type)
        span.set_attribute("metric.memory.count", count)
        return {"memory_operation": operation_type, "memory_count": count}
```

---

## Summary: Three-Level Control

| Level | Scope | Priority | Configuration Method |
|-------|-------|----------|---------------------|
| **Framework** | All agents globally | Lowest | Environment vars, config file |
| **Script** | All agents in script | Medium | `configure_observability()` |
| **Agent** | Single agent | Highest | `@agent(observability=...)` |

**Key Improvements**:
1. ✅ **Agent-level control**: Choose which agents to observe
2. ✅ **Metric-level control**: Choose which metrics to collect
3. ✅ **Script-level control**: Configure per-script
4. ✅ **Standard metrics**: Clear definition of standard metrics
5. ✅ **Flexible**: Can mix and match configurations
6. ✅ **Performance**: Sampling and selective metric collection
7. ✅ **Simple defaults**: Works with zero config
8. ✅ **Production-ready**: Minimal overhead with sampling

---

## Migration Path

**Phase 1 Implementation** (Week 1):
- Core tracing infrastructure (no config yet)
- Always-on by default

**Phase 2 Enhancement** (Week 2):
- Add configuration system
- Script-level and agent-level control
- Standard metrics definition

**Phase 3 Polish** (Week 3):
- Config file support
- Advanced features (sampling, patterns)

This way we can start simple and add sophistication progressively.

---

**Does this design address your concerns about built-in metrics and configuration control?**
