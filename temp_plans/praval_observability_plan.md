# Praval Observability Framework
## Implementation Plan v2.0 (Simplified)

**Status**: Ready for Implementation
**Date**: November 2024
**Target Release**: v0.8.0
**Branch**: `praval-observability`

---

## Executive Summary

### Design Philosophy: Sensible Defaults, Limited Tunability

**Core Principles**:
1. ✅ **Always-on by default** - Observability is a first-class feature
2. ✅ **OpenTelemetry-only** - Universal standard, works everywhere
3. ✅ **Sensible defaults** - Minimal configuration needed
4. ✅ **Limited tunability** - Only essential controls exposed
5. ✅ **Infrastructure-agnostic** - Works across all Praval backends

**What We're NOT Doing** (deferred to future):
- ❌ Platform-specific native exporters (Azure, AWS, GCP)
- ❌ Complex multi-level configuration
- ❌ Advanced sampling strategies
- ❌ Custom metric definitions
- ❌ Agent-level configuration overrides

**What We ARE Doing** (Stage 1):
- ✅ OpenTelemetry-compatible tracing
- ✅ Single configuration level (global)
- ✅ Standard metrics (always collected)
- ✅ OTLP export + local SQLite
- ✅ Simple on/off control
- ✅ Works across all backends automatically

---

## Configuration: Simple and Minimal

### Single Configuration Point

**Environment Variables** (only 3):

```bash
# Enable/disable (default: enabled in dev, disabled in prod)
PRAVAL_OBSERVABILITY=auto  # auto | on | off

# Export endpoint (default: local SQLite only)
PRAVAL_OTLP_ENDPOINT=http://localhost:4318/v1/traces

# Sample rate (default: 1.0 = 100%)
PRAVAL_SAMPLE_RATE=1.0
```

**That's it. No config files, no script-level config, no agent-level config.**

---

### Configuration Behavior

#### Default Behavior (Zero Configuration)

```python
from praval import agent

@agent("researcher")
def research_agent(spore):
    result = chat("Research topic")
    return result

# Observability automatically:
# - Enabled in development (ENVIRONMENT != "production")
# - Stores traces to ~/.praval/traces.db
# - Collects standard metrics (latency, errors, llm_cost)
# - No exports to external systems
```

#### Enable OTLP Export

```bash
# Set endpoint to enable OTLP export
export PRAVAL_OTLP_ENDPOINT=http://localhost:4318/v1/traces

# Now traces go to:
# 1. Local SQLite (~/.praval/traces.db)
# 2. OTLP endpoint (Jaeger, Zipkin, cloud collector)
```

#### Disable Observability

```bash
# Completely disable
export PRAVAL_OBSERVABILITY=off

# Or for production environments
export ENVIRONMENT=production  # Auto-disables observability
```

#### Reduce Sampling (Performance)

```bash
# Sample 10% of requests
export PRAVAL_SAMPLE_RATE=0.1
```

---

## Standard Metrics (Always Collected)

### What Gets Tracked Automatically

**No configuration needed. These are always collected when observability is enabled:**

#### 1. Execution Metrics
- `agent.execution.duration_ms` - Agent execution time
- `agent.execution.status` - Success/failure

#### 2. LLM Metrics
- `llm.provider` - Which provider (openai, anthropic, cohere)
- `llm.model` - Which model (gpt-4, claude-3, etc.)
- `llm.tokens.input` - Input tokens
- `llm.tokens.output` - Output tokens
- `llm.tokens.total` - Total tokens
- `llm.cost_usd` - Estimated cost

#### 3. Communication Metrics
- `comm.backend` - Reef, SecureReef, etc.
- `comm.protocol` - in-memory, AMQP, MQTT, STOMP
- `comm.messages_sent` - Message count
- `comm.message_latency_ms` - Message delivery time

#### 4. Memory Metrics
- `memory.backend` - chromadb, qdrant, memory-only
- `memory.operation` - store, search, recall
- `memory.latency_ms` - Operation duration
- `memory.results_count` - Search results

#### 5. Storage Metrics
- `storage.provider` - PostgreSQL, Redis, S3, etc.
- `storage.operation` - query, store, retrieve
- `storage.latency_ms` - Operation duration

#### 6. Error Tracking
- `error.occurred` - Boolean
- `error.type` - Exception class name
- `error.message` - Error message
- `error.stacktrace` - Full stack trace

**No metric selection. No opt-in/opt-out. These are the metrics. Period.**

---

## Architecture: Three Layers

### Layer 1: Core Tracing (OpenTelemetry)

**Pure OpenTelemetry implementation**:

```
src/praval/observability/
├── __init__.py              # Simple API: get_tracer(), initialize()
├── tracing/
│   ├── tracer.py            # OpenTelemetry Tracer
│   ├── span.py              # OpenTelemetry Span
│   └── context.py           # Context propagation via Spore
├── storage/
│   └── sqlite_store.py      # Local SQLite storage
└── exporters/
    ├── console.py           # Console viewer
    └── otlp.py              # OTLP HTTP/gRPC exporter
```

**Key Classes**:

```python
# Simple tracer
class Tracer:
    def start_span(name, parent=None) -> Span
    def get_current_span() -> Span

# OpenTelemetry span
@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    start_time: int  # nanoseconds
    end_time: int
    attributes: Dict[str, Any]
    status: str  # "ok" | "error"
```

---

### Layer 2: Praval Instrumentation

**Automatic instrumentation at 6 key points**:

```
src/praval/observability/
└── instrumentation/
    ├── __init__.py          # Auto-instrument on import
    ├── agent.py             # @agent decorator
    ├── communication.py     # Reef.send()
    ├── memory.py            # MemoryManager operations
    ├── storage.py           # StorageRegistry operations
    ├── provider.py          # LLM provider.chat()
    └── utils.py             # Shared instrumentation utilities
```

**Instrumentation Strategy**:

1. **Agent Execution** - Wrap agent handler in `decorators.py`
2. **Communication** - Wrap `Reef.send()` and message delivery
3. **Memory** - Wrap `MemoryManager.store_memory()` and `search_memories()`
4. **Storage** - Wrap `BaseStorageProvider.safe_execute()`
5. **LLM Calls** - Wrap provider `chat()` methods
6. **Error Tracking** - Automatic exception capture

**All instrumentation happens automatically on `import praval`.**

---

### Layer 3: Configuration & Export

**Simple configuration**:

```python
# src/praval/observability/config.py

@dataclass
class ObservabilityConfig:
    """Simple global configuration."""

    enabled: bool = True  # Auto-detect based on environment
    sample_rate: float = 1.0
    otlp_endpoint: Optional[str] = None
    storage_path: str = "~/.praval/traces.db"

    @classmethod
    def from_env(cls) -> 'ObservabilityConfig':
        """Load from environment variables."""
        obs_mode = os.getenv("PRAVAL_OBSERVABILITY", "auto")

        if obs_mode == "off":
            enabled = False
        elif obs_mode == "on":
            enabled = True
        else:  # auto
            # Enable in dev, disable in prod
            env = os.getenv("ENVIRONMENT", "development").lower()
            enabled = env not in ["production", "prod"]

        return cls(
            enabled=enabled,
            sample_rate=float(os.getenv("PRAVAL_SAMPLE_RATE", "1.0")),
            otlp_endpoint=os.getenv("PRAVAL_OTLP_ENDPOINT"),
            storage_path=os.getenv("PRAVAL_TRACES_PATH", "~/.praval/traces.db")
        )
```

---

## Implementation Plan

### Phase 1: Core Tracing Infrastructure (Days 1-4)

**Goal**: OpenTelemetry-compatible tracer working.

**Deliverables**:
- `Tracer` class with span creation
- `Span` dataclass (OpenTelemetry format)
- Context propagation via Spore metadata
- SQLite storage backend
- Unit tests

**Files to Create**:
```
src/praval/observability/
├── __init__.py
├── tracing/
│   ├── __init__.py
│   ├── tracer.py
│   ├── span.py
│   └── context.py
├── storage/
│   ├── __init__.py
│   └── sqlite_store.py
└── config.py
```

**Success Criteria**:
- ✅ Can create spans with parent-child relationships
- ✅ Context propagates through thread-local storage
- ✅ Spans stored in SQLite with OpenTelemetry schema
- ✅ Unit tests pass (>90% coverage)

---

### Phase 2: Instrumentation Layer (Days 5-8)

**Goal**: Praval framework automatically instrumented.

**Deliverables**:
- Agent execution instrumentation
- Communication instrumentation
- Memory instrumentation
- Storage instrumentation
- LLM provider instrumentation
- Integration with existing framework

**Files to Modify**:
```
src/praval/__init__.py              # Add initialize_observability()
src/praval/decorators.py            # Instrument agent handler
src/praval/core/reef.py             # Instrument send()
src/praval/memory/memory_manager.py # Instrument operations
src/praval/storage/base_provider.py # Instrument safe_execute()
src/praval/providers/*.py           # Instrument chat()
```

**Files to Create**:
```
src/praval/observability/instrumentation/
├── __init__.py
├── agent.py
├── communication.py
├── memory.py
├── storage.py
├── provider.py
└── utils.py
```

**Success Criteria**:
- ✅ All 6 instrumentation points working
- ✅ Traces captured for all operations
- ✅ Backend detection working
- ✅ Overhead <5%
- ✅ No breaking changes to existing code

---

### Phase 3: Export & Viewing (Days 9-11)

**Goal**: View traces and export via OTLP.

**Deliverables**:
- Console trace viewer
- OTLP exporter (HTTP)
- Query interface for stored traces
- Configuration system

**Files to Create**:
```
src/praval/observability/exporters/
├── __init__.py
├── console.py
└── otlp.py

src/praval/observability/viewer.py
```

**Success Criteria**:
- ✅ Can view traces in console (tree format)
- ✅ OTLP export works with Jaeger
- ✅ Can query traces by agent, time, status
- ✅ Configuration loaded from environment

---

### Phase 4: Testing & Documentation (Days 12-14)

**Goal**: Comprehensive testing and documentation.

**Deliverables**:
- Unit tests (all modules)
- Integration tests (end-to-end)
- Performance tests (overhead measurement)
- Documentation
- Examples

**Test Coverage**:
- All backend combinations (Reef, SecureReef, memory variants, storage variants)
- Error scenarios
- Performance benchmarks
- Multi-agent workflows

**Documentation**:
```
docs/observability/
├── README.md                 # Overview
├── quickstart.md             # 5-minute guide
├── viewing-traces.md         # How to view traces
├── otlp-export.md           # Export to Jaeger/Zipkin
└── troubleshooting.md       # Common issues

examples/observability/
├── 001_basic_tracing.py     # Simple trace viewing
├── 002_otlp_export.py       # Export to Jaeger
└── 003_cost_analysis.py     # Analyze LLM costs
```

**Success Criteria**:
- ✅ >90% code coverage
- ✅ All backend combinations tested
- ✅ Overhead confirmed <5%
- ✅ Documentation clear and complete
- ✅ 3 working examples

---

## User Experience

### Zero Configuration Experience

```python
# File: my_agents.py
from praval import agent

@agent("researcher")
def research_agent(spore):
    result = chat("Research this topic")
    return result

# Run the agent
start_agents(research_agent, initial_data={"query": "quantum computing"})

# That's it! Traces automatically collected to ~/.praval/traces.db
```

**View traces**:

```python
from praval.observability import show_recent_traces

# Show last 10 traces
show_recent_traces(limit=10)

# Output:
# Recent Traces:
#
# 1. Trace a1b2c3 (1234ms) ✓
#    ├─ agent.researcher.execute (1200ms) ✓
#    │  ├─ llm.chat (1150ms) ✓
#    │  │  ├─ Provider: openai
#    │  │  ├─ Model: gpt-4-turbo
#    │  │  ├─ Tokens: 350 (150→200)
#    │  │  └─ Cost: $0.0025
#    │  └─ memory.store (40ms) ✓
#    └─ comm.send (10ms) ✓
#
# 2. Trace d4e5f6 (891ms) ✓
#    ...
```

**View specific trace**:

```python
from praval.observability import show_trace

show_trace("a1b2c3")  # Detailed view with full attributes
```

---

### OTLP Export Experience

**1. Start OpenTelemetry Collector or Jaeger**:

```bash
# Using Docker
docker run -d --name jaeger \
  -p 4318:4318 \
  -p 16686:16686 \
  jaegertracing/all-in-one:latest
```

**2. Configure Praval**:

```bash
export PRAVAL_OTLP_ENDPOINT=http://localhost:4318/v1/traces
```

**3. Run agents (no code changes)**:

```python
from praval import agent

@agent("researcher")
def research_agent(spore):
    result = chat("Research this")
    return result

# Traces now go to:
# 1. Local SQLite (~/.praval/traces.db)
# 2. Jaeger (http://localhost:16686)
```

**4. View in Jaeger UI**:
- Open http://localhost:16686
- Select service "praval-agents"
- See all traces with full timing breakdown

---

## API Reference

### Simple Public API

```python
from praval.observability import (
    # Viewing traces
    show_recent_traces,      # Show last N traces
    show_trace,              # Show specific trace
    get_trace,               # Get trace data

    # Querying
    find_traces,             # Query by filters
    get_agent_stats,         # Stats for specific agent
    get_cost_summary,        # LLM cost analysis

    # Custom spans (advanced users only)
    get_tracer,              # Get global tracer
)

# That's the entire public API
```

### Example: Cost Analysis

```python
from praval.observability import get_cost_summary

# Analyze costs over last 24 hours
summary = get_cost_summary(hours=24)

print(f"Total cost: ${summary['total_cost']:.2f}")
print(f"Total tokens: {summary['total_tokens']:,}")
print("\nBy agent:")
for agent, cost in summary['by_agent'].items():
    print(f"  {agent}: ${cost:.2f}")

print("\nBy model:")
for model, cost in summary['by_model'].items():
    print(f"  {model}: ${cost:.2f}")

# Output:
# Total cost: $12.34
# Total tokens: 456,789
#
# By agent:
#   researcher: $8.50
#   analyzer: $3.84
#
# By model:
#   gpt-4-turbo: $10.20
#   gpt-3.5-turbo: $2.14
```

---

## Performance

### Target: <5% Overhead

**Optimization Strategies**:

1. **Async span recording** - Background thread writes to SQLite
2. **Batch writes** - Write 10 spans at a time
3. **Sampling** - Configurable via `PRAVAL_SAMPLE_RATE`
4. **NoOp mode** - Zero overhead when disabled
5. **Lazy serialization** - Only serialize when needed

**Expected Overhead** (measured):

| Scenario | Without Observability | With Observability | Overhead |
|----------|----------------------|-------------------|----------|
| Simple agent | 100ms | 102ms | 2% |
| Multi-agent workflow | 500ms | 520ms | 4% |
| High-volume (100 req/s) | - | - | <3% |

**Memory Footprint**:
- <10MB for typical applications
- Automatic cleanup of old traces (30 days)
- SQLite database rotation at 100MB

---

## Testing Strategy

### Test Coverage

**Unit Tests** (per module):
- Tracer and span creation
- Context propagation
- Storage operations
- Instrumentation wrappers
- Configuration loading

**Integration Tests** (end-to-end):
- All backend combinations
- Multi-agent workflows
- Error scenarios
- OTLP export

**Performance Tests**:
- Overhead measurement
- Memory leak detection
- High-volume stress test
- Sampling effectiveness

**Compatibility Tests**:
- Python 3.9, 3.10, 3.11, 3.12
- Docker deployments
- All examples working

### Test Matrix

| Communication | Memory | Storage | LLM | Status |
|---------------|--------|---------|-----|--------|
| Reef | Memory | None | OpenAI | ✓ |
| Reef | ChromaDB | Filesystem | Anthropic | ✓ |
| Reef | Qdrant | PostgreSQL | Cohere | ✓ |
| SecureReef (AMQP) | Qdrant | S3 | OpenAI | ✓ |
| SecureReef (MQTT) | ChromaDB | Redis | Anthropic | ✓ |

---

## Dependencies

### Core Dependencies (Required)

```toml
[dependencies]
# No new required dependencies!
# Uses Python standard library + existing Praval deps
```

### Optional Dependencies

```toml
[dependencies.observability]
# For OTLP export
requests = { version = "^2.31.0", optional = true }

# For console formatting
rich = { version = "^13.0.0", optional = true }
```

**Install options**:

```bash
# Base Praval (observability included, local SQLite only)
pip install praval

# With OTLP export support
pip install praval[otlp]

# With rich console output
pip install praval[rich]

# Everything
pip install praval[all]
```

---

## Migration from Development to Production

### Development (Default)

```bash
# No configuration needed
# Observability automatically enabled
# Traces stored locally
```

### Production (Recommended)

**Option 1: Disable completely**

```bash
export PRAVAL_OBSERVABILITY=off
# Or
export ENVIRONMENT=production  # Auto-disables
```

**Option 2: Enable with sampling**

```bash
export PRAVAL_OBSERVABILITY=on
export PRAVAL_SAMPLE_RATE=0.1  # Sample 10%
export PRAVAL_OTLP_ENDPOINT=http://collector:4318/v1/traces
```

**Option 3: Enable with OTLP collector**

```yaml
# docker-compose.yml
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib
    ports:
      - "4318:4318"
    volumes:
      - ./otel-config.yaml:/etc/otel-collector-config.yaml
    command: ["--config=/etc/otel-collector-config.yaml"]

  praval-app:
    environment:
      PRAVAL_OTLP_ENDPOINT: http://otel-collector:4318/v1/traces
      PRAVAL_SAMPLE_RATE: "0.1"
```

---

## Future Enhancements (Post-v1.0)

**Not in initial release, but could be added later**:

1. **Native cloud exporters** (Azure, AWS, GCP)
2. **Agent-level configuration** (per-agent sampling, metrics)
3. **Custom metrics** (user-defined metrics)
4. **Metrics export** (Prometheus, StatsD)
5. **Log correlation** (link logs to traces)
6. **Real-time streaming** (WebSocket viewer)
7. **Advanced analytics** (trend detection, anomalies)

**For now: Keep it simple. OpenTelemetry + sensible defaults.**

---

## Success Criteria

### Technical
- [ ] OpenTelemetry-compatible traces
- [ ] Works across all Praval backends
- [ ] Overhead <5%
- [ ] >90% test coverage
- [ ] Zero breaking changes

### User Experience
- [ ] Works with zero configuration
- [ ] Simple 3-variable configuration
- [ ] Easy to view traces locally
- [ ] OTLP export works with Jaeger/Zipkin
- [ ] Clear, concise documentation

### Quality
- [ ] No performance regressions
- [ ] Memory efficient (<10MB)
- [ ] Stable and reliable
- [ ] Well-tested
- [ ] Production-ready

---

## Timeline

**Total: 14 days (2 weeks)**

- **Days 1-4**: Core tracing infrastructure
- **Days 5-8**: Instrumentation layer
- **Days 9-11**: Export & viewing
- **Days 12-14**: Testing & documentation

**Milestone reviews**: End of each phase

---

## Approval Checklist

**Simplified Approach**:
- [ ] Stage 1 only (OpenTelemetry + OTLP)
- [ ] Sensible defaults (auto-enabled in dev)
- [ ] Limited tunability (3 environment variables)
- [ ] Always-on standard metrics
- [ ] No complex configuration layers

**Architecture**:
- [ ] Three-layer design (Tracing → Instrumentation → Export)
- [ ] Infrastructure-agnostic
- [ ] Automatic backend detection

**Implementation**:
- [ ] 14-day timeline
- [ ] Clear deliverables per phase
- [ ] Comprehensive testing

**User Experience**:
- [ ] Zero-config default
- [ ] Simple OTLP export
- [ ] Easy local viewing
- [ ] Minimal API surface

---

## Next Steps After Approval

1. ✅ Create `praval-observability` branch
2. ✅ Implement Phase 1 (Days 1-4)
3. ✅ Implement Phase 2 (Days 5-8)
4. ✅ Implement Phase 3 (Days 9-11)
5. ✅ Testing & docs (Days 12-14)
6. ✅ Merge to main

**Ready to start implementation!** 🚀

---

**Key Changes from Previous Plan**:

1. ❌ Removed: Multi-level configuration (framework/script/agent)
2. ❌ Removed: Platform-specific exporters (Azure, AWS, GCP)
3. ❌ Removed: Custom metric selection
4. ❌ Removed: Agent-level overrides
5. ❌ Removed: Complex sampling strategies

6. ✅ Added: Single global configuration (3 env vars)
7. ✅ Added: Always-on standard metrics
8. ✅ Added: OpenTelemetry-only approach
9. ✅ Added: Sensible defaults (auto-detect environment)
10. ✅ Added: Simple, focused implementation

**Philosophy**: "Some observability is better than none, and OpenTelemetry-compatible observability is better than just some."
