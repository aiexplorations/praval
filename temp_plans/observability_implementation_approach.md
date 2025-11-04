# Praval Observability Implementation Approach
**Infrastructure-Agnostic Design for Multi-Backend Support**

**Status**: Awaiting Approval
**Date**: November 2024
**Branch**: `praval-observability`

---

## Executive Summary

### What We're Building

**Observability system** that works across ALL Praval infrastructure variants:
- **4 Communication backends**: Reef, SecureReef (AMQP/MQTT/STOMP)
- **3 Memory backends**: ChromaDB, Qdrant, memory-only
- **5 Storage providers**: PostgreSQL, Redis, S3, Qdrant, Filesystem
- **3 LLM providers**: OpenAI, Anthropic, Cohere

### Key Design Decisions

1. **Three-Layer Architecture**:
   - Layer 1: Core tracing (OpenTelemetry, no Praval knowledge)
   - Layer 2: Praval instrumentation (detects backends at runtime)
   - Layer 3: Backend-specific collectors (optional)

2. **Three-Level Configuration Control**:
   - **Framework-level**: Global defaults via config file/env vars
   - **Script-level**: `configure_observability()` at top of script
   - **Agent-level**: `@agent(observability={...})` per agent

3. **Standard Metrics Built-In**:
   - `latency`, `errors` (always on)
   - `llm_calls`, `llm_tokens`, `llm_cost` (opt-in)
   - `memory_operations`, `message_flow` (opt-in)

4. **Infrastructure-Agnostic**:
   - Instrumentation at abstraction boundaries (base classes)
   - Runtime backend detection
   - Works with ANY combination of backends

---

## Design Principles

### 1. Instrumentation at Abstraction Boundaries

✅ **DO**: Instrument base classes
- `Reef.send()` - works for Reef and SecureReef
- `MemoryManager.store_memory()` - works for all memory backends
- `BaseStorageProvider.safe_execute()` - works for all storage

❌ **DON'T**: Instrument concrete implementations
- Avoids coupling to specific backends

### 2. Runtime Backend Discovery

System auto-detects active backends:
```python
# Detect communication backend
if isinstance(get_reef(), SecureReef):
    backend = "SecureReef"
    protocol = reef.protocol.value  # AMQP/MQTT/STOMP
else:
    backend = "Reef"
    protocol = "in-memory"
```

### 3. Backend Context as Span Attributes

All metrics tagged with backend info:
```python
span.set_attribute("comm.backend", "SecureReef")
span.set_attribute("comm.protocol", "AMQP")
span.set_attribute("memory.backend", "qdrant")
span.set_attribute("storage.provider", "PostgreSQL")
span.set_attribute("llm.provider", "openai")
```

---

## Configuration System

### Level 1: Framework Default (Global)

**Environment Variables**:
```bash
PRAVAL_OBSERVABILITY_MODE=auto  # auto|enabled|disabled
PRAVAL_METRICS_LEVEL=standard   # minimal|standard|full
```

**Config File** (`~/.praval/config.yaml`):
```yaml
observability:
  mode: auto
  metrics:
    level: standard  # minimal|standard|full|custom
  storage:
    backend: sqlite
    path: ~/.praval/traces.db
  export:
    - console
    - sqlite
```

### Level 2: Script-Level Configuration

**At top of script**:
```python
from praval import agent, configure_observability

# Configure for this script
configure_observability(
    enabled=True,
    metrics=["latency", "errors", "llm_cost"],
    export_to=["console", "sqlite"],
    sample_rate=1.0
)

@agent("researcher")
def research_agent(spore):
    return result  # Uses script config
```

### Level 3: Agent-Level Configuration

**Per-agent control**:
```python
# Full observability
@agent(
    "critical",
    observability={
        "metrics": ["latency", "llm_cost"],
        "sample_rate": 1.0
    }
)
def critical_agent(spore):
    return result

# Minimal observability
@agent(
    "background",
    observability={
        "metrics": ["errors"],
        "sample_rate": 0.01  # 1% sampling
    }
)
def background_agent(spore):
    return result

# Disabled
@agent("helper", observability=False)
def helper_agent(spore):
    return result
```

### Configuration Priority

```
Agent-level    (highest)
    ↓
Script-level
    ↓
Config file
    ↓
Environment
    ↓
Defaults       (lowest)
```

---

## Standard Metrics

### Built-In Metrics

**Always Collected** (when enabled):
- `latency` - Agent execution time
- `errors` - Error count and types

**Opt-In Standard Metrics**:
- `llm_calls` - Number of LLM API calls
- `llm_tokens` - Token usage (input/output)
- `llm_cost` - Estimated API cost
- `memory_operations` - Memory store/recall
- `memory_latency` - Memory operation time
- `messages_sent` - Spores broadcast
- `messages_received` - Spores received
- `message_flow` - Inter-agent tracing

### Metric Levels

**Minimal** (production default):
- `latency`, `errors`

**Standard** (development default):
- `latency`, `errors`, `llm_calls`, `llm_tokens`, `llm_cost`

**Full** (debugging):
- All metrics enabled

**Custom**:
- User-specified list

---

## Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1)

**Goal**: OpenTelemetry-compatible tracing

**Deliverables**:
```
src/praval/observability/
├── tracing/
│   ├── tracer.py    # OpenTelemetry Tracer
│   ├── span.py      # OpenTelemetry Span
│   └── context.py   # Trace context propagation
├── storage/
│   └── sqlite.py    # SQLite trace storage
└── exporters/
    ├── console.py   # Console viewer
    ├── json.py      # JSON export
    └── otlp.py      # OTLP export (Jaeger)
```

**Tasks**:
- [ ] Implement Tracer and Span (OpenTelemetry semantics)
- [ ] Context propagation via Spore metadata
- [ ] SQLite storage with OTel schema
- [ ] Console trace viewer
- [ ] Unit tests (>90% coverage)

**Success Criteria**:
- ✅ Can create and store spans
- ✅ Context propagates parent-child
- ✅ Console viewer displays trace trees
- ✅ Zero Praval dependencies

---

### Phase 2: Instrumentation Layer (Week 2)

**Goal**: Praval framework instrumented at abstraction boundaries

**Deliverables**:
```
src/praval/observability/
├── instrumentation/
│   ├── manager.py         # Orchestrates all
│   ├── base.py            # BaseInstrumentor
│   ├── communication.py   # Reef/SecureReef
│   ├── memory.py          # MemoryManager
│   ├── storage.py         # StorageRegistry
│   ├── provider.py        # LLM providers
│   └── agent.py           # Agent lifecycle
├── discovery/
│   └── backend_detector.py  # Runtime detection
└── config.py              # Configuration system
```

**Key Classes**:

**InstrumentationManager**:
```python
class InstrumentationManager:
    def auto_instrument(self):
        # Detect backends
        # Create instrumentors
        # Apply instrumentation
```

**CommunicationInstrumentor**:
```python
class CommunicationInstrumentor:
    def instrument(self):
        # Wrap Reef.send()
        # Wrap SecureReef.send_secure_spore()
        # Inject trace context into spores
```

**MemoryInstrumentor**:
```python
class MemoryInstrumentor:
    def instrument(self):
        # Wrap MemoryManager.store_memory()
        # Wrap MemoryManager.search_memories()
```

**Configuration System**:
```python
def configure_observability(
    enabled=None,
    metrics=None,
    export_to=None,
    sample_rate=None
):
    # Script-level configuration
```

**Agent Decorator Enhancement**:
```python
@agent(
    name,
    observability={
        "metrics": [...],
        "sample_rate": 1.0
    }
)
```

**Tasks**:
- [ ] Implement InstrumentationManager
- [ ] Implement 6 instrumentors (Comm, Memory, Storage, Provider, Agent, Registry)
- [ ] Backend detection logic
- [ ] Configuration system (3 levels)
- [ ] Modify `__init__.py` for auto-initialization
- [ ] Integration tests per backend type

**Success Criteria**:
- ✅ Auto-detects all backends
- ✅ Works with all communication backends
- ✅ Works with all memory backends
- ✅ Works with all storage providers
- ✅ Configuration system functional
- ✅ Overhead <5%

---

### Phase 3: Testing & Documentation (Week 3)

**Goal**: Comprehensive testing and documentation

**Test Matrix**:

| Communication | Memory | Storage | LLM | Status |
|---------------|--------|---------|-----|--------|
| Reef | Memory | None | OpenAI | ✓ |
| Reef | ChromaDB | Filesystem | Anthropic | ✓ |
| Reef | Qdrant | PostgreSQL | Cohere | ✓ |
| SecureReef (AMQP) | Qdrant | S3 | OpenAI | ✓ |
| SecureReef (MQTT) | ChromaDB | Redis | Anthropic | ✓ |

**Test Categories**:
1. Unit tests (per instrumentor)
2. Integration tests (end-to-end)
3. Performance tests (overhead measurement)
4. Compatibility tests (backend combinations)

**Documentation**:
```
examples/observability_examples/
├── 001_basic_tracing.py
├── 002_script_config.py
├── 003_agent_config.py
├── 004_export_jaeger.py
└── 005_cost_tracking.py

docs/
├── observability.md
├── observability-configuration.md
└── observability-backends.md
```

**Tasks**:
- [ ] Write comprehensive tests
- [ ] Test all backend combinations
- [ ] Performance benchmarking
- [ ] Create 5 examples
- [ ] Write documentation

**Success Criteria**:
- ✅ >90% code coverage
- ✅ All combinations tested
- ✅ Overhead <5% confirmed
- ✅ No functionality regressions
- ✅ Clear documentation

---

## Architecture Details

### Three-Layer Design

```
┌─────────────────────────────────────────┐
│  Layer 1: Core Tracing                  │
│  (OpenTelemetry, agnostic)              │
│  - Tracer, Span, Context                │
│  - Storage, Exporters                   │
└─────────────────────────────────────────┘
              ▲
              │
┌─────────────────────────────────────────┐
│  Layer 2: Praval Instrumentation        │
│  (Detects backends, applies wrappers)   │
│  - InstrumentationManager               │
│  - 6 Instrumentors                      │
│  - Configuration System                 │
└─────────────────────────────────────────┘
              ▲
              │
┌─────────────────────────────────────────┐
│  Layer 3: Backend-Specific (Optional)   │
│  - AMQPMetrics, QdrantMetrics, etc.     │
└─────────────────────────────────────────┘
```

### Integration Point

**Modify `src/praval/__init__.py`**:
```python
from praval.observability import initialize_observability

# Auto-initialize on import
initialize_observability()
```

**New `src/praval/observability/__init__.py`**:
```python
def initialize_observability(config=None):
    # Check if disabled
    if os.getenv("PRAVAL_DISABLE_OBSERVABILITY") == "1":
        return

    # Create tracer
    tracer = get_tracer()

    # Create instrumentation manager
    manager = InstrumentationManager(tracer, config)

    # Auto-instrument detected backends
    manager.auto_instrument()
```

---

## Performance Optimization

### Target: <5% Overhead

**Strategies**:
1. **Async span recording** - Background thread
2. **Batched writes** - 10 spans at a time
3. **Sampling** - Configurable per agent
4. **Lazy serialization** - Only when needed
5. **NoOp mode** - Zero overhead when disabled

**Expected Overhead**:
- Reef + Memory: ~3%
- SecureReef + Qdrant: ~4%
- All features: <5%

---

## User Experience

### Zero Configuration (Default)

```python
# Just works - no changes needed
from praval import agent

@agent("researcher")
def research_agent(spore):
    result = chat("Research topic")
    return result

# Traces automatically collected ✓
```

### Viewing Traces

```python
from praval.observability import show_trace

show_trace(trace_id)

# Output:
# Trace: abc-123
# Duration: 1234ms
#
# ├─ agent.researcher.execute (1200ms) ✓
# │  ├─ llm.chat (1150ms) ✓
# │  │  ├─ Provider: openai
# │  │  ├─ Tokens: 350
# │  │  └─ Cost: $0.0025
# │  └─ memory.store (40ms) ✓
```

### Export to Jaeger

```python
from praval.observability import export_to_jaeger

export_to_jaeger("http://localhost:4318/v1/traces")
# View at http://localhost:16686
```

---

## Approval Checklist

**Architecture**:
- [ ] Three-layer design (Core → Instrumentation → Backend-specific)
- [ ] Instrumentation at abstraction boundaries
- [ ] Runtime backend detection

**Configuration**:
- [ ] Three-level control (Framework → Script → Agent)
- [ ] Standard metrics defined
- [ ] Flexible and simple defaults

**Implementation**:
- [ ] 3-week timeline (Core → Instrumentation → Testing)
- [ ] Backend-agnostic approach
- [ ] OpenTelemetry compatibility

**Performance**:
- [ ] <5% overhead target
- [ ] Sampling support
- [ ] Opt-out available

**Testing**:
- [ ] Comprehensive test matrix
- [ ] All backend combinations
- [ ] Performance benchmarks

**User Experience**:
- [ ] Zero configuration required
- [ ] Works across all backends
- [ ] Clear documentation

---

## Next Steps After Approval

1. **Create branch**: `git checkout -b praval-observability`
2. **Phase 1**: Implement core tracing (Week 1)
3. **Phase 2**: Implement instrumentation (Week 2)
4. **Phase 3**: Testing and docs (Week 3)
5. **Demo**: End of each phase
6. **Merge**: After successful testing

---

## Questions & Feedback

Please review:
- Is the three-level configuration approach right?
- Is the standard metrics definition sufficient?
- Any concerns about the instrumentation approach?
- Timeline feasible?
- Any specific requirements?

**Ready to implement upon your approval!** 🚀

---

## Additional Documents

See also:
- `temp_plans/praval_observability_plan.md` - Full technical specification
- `temp_plans/observability_design_refinement.md` - Configuration system details

These provide more implementation details and code examples.
