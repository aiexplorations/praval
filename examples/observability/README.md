# Praval Observability Examples

These examples demonstrate the Praval observability framework features.

## Phase 1: Core Infrastructure (Available Now)

### Example 001: Basic Tracing Demo
**File**: `001_basic_tracing_demo.py`

Demonstrates:
- Creating spans manually
- Parent-child span relationships
- Recording attributes and events
- Storing traces to SQLite
- Querying and viewing traces

```bash
python examples/observability/001_basic_tracing_demo.py
```

**What you'll see**:
- Simulated agent operation with spans
- LLM call tracking (provider, model, tokens, cost)
- Memory operation tracking
- Complete trace visualization
- Storage statistics

---

### Example 002: Configuration Demo
**File**: `002_configuration_demo.py`

Demonstrates:
- All 3 configuration environment variables
- Auto-detection of dev/prod environments
- Sampling configuration
- OTLP endpoint configuration
- Custom storage paths

```bash
python examples/observability/002_configuration_demo.py
```

**What you'll see**:
- Default configuration behavior
- Explicitly enabling/disabling observability
- Production auto-detection
- Sampling rates and their effects
- Combined configuration scenarios

---

### Example 003: Context Propagation Demo
**File**: `003_context_propagation_demo.py`

Demonstrates:
- Trace context extraction from Spores
- Trace context injection into Spores
- Parent-child relationships across agent boundaries
- Multi-agent workflow tracing
- Parallel agent execution

```bash
python examples/observability/003_context_propagation_demo.py
```

**What you'll see**:
- 3-agent workflow (Researcher → Analyzer → Reporter)
- Trace ID continuity across agents
- Complete trace hierarchy visualization
- Parallel agent execution patterns

---

## Configuration Quick Reference

### Environment Variables

```bash
# Enable/disable observability
PRAVAL_OBSERVABILITY=auto  # auto (default) | on | off

# OTLP export endpoint (optional)
PRAVAL_OTLP_ENDPOINT=http://localhost:4318/v1/traces

# Sample rate (optional)
PRAVAL_SAMPLE_RATE=1.0  # 0.0-1.0 (default: 1.0 = 100%)

# Custom storage path (optional)
PRAVAL_TRACES_PATH=~/.praval/traces.db  # default
```

### Common Scenarios

**Development (default)**:
```bash
# No configuration needed
# Observability auto-enabled
python your_script.py
```

**Production (sampled)**:
```bash
PRAVAL_OBSERVABILITY=on \
PRAVAL_SAMPLE_RATE=0.1 \
PRAVAL_OTLP_ENDPOINT=http://collector:4318/v1/traces \
python your_script.py
```

**Performance testing (disabled)**:
```bash
PRAVAL_OBSERVABILITY=off python your_script.py
```

---

## What's Working Now (Phase 1)

✅ **Core Infrastructure**:
- OpenTelemetry-compatible spans
- Trace context propagation
- SQLite local storage
- Configuration system
- Manual span creation

✅ **Test Coverage**: 76 tests, 100% passing, >95% coverage

---

## Coming Next (Phase 2)

⏳ **Automatic Instrumentation**:
- `@agent` decorator auto-instrumentation
- Automatic LLM call tracking
- Automatic memory operation tracking
- Automatic communication tracking
- Zero code changes required

⏳ **Phase 3: Export & Viewing**:
- OTLP export implementation
- Console trace viewer
- Integration with Jaeger, Zipkin

⏳ **Phase 4: Testing & Documentation**:
- End-to-end integration tests
- Comprehensive documentation
- More examples

---

## Viewing Traces

### SQLite Storage

Traces are stored in `~/.praval/traces.db` by default.

**View with SQLite CLI**:
```bash
sqlite3 ~/.praval/traces.db

# List recent traces
SELECT DISTINCT trace_id FROM spans
ORDER BY start_time DESC LIMIT 10;

# View spans for a specific trace
SELECT name, duration_ms, status
FROM spans
WHERE trace_id = 'your-trace-id'
ORDER BY start_time;
```

**Query via Python**:
```python
from praval.observability import get_trace_store

store = get_trace_store()

# Get recent trace IDs
recent = store.get_recent_traces(limit=10)

# Get all spans for a trace
spans = store.get_trace(trace_id)

# Find spans by criteria
errors = store.find_spans(status="ERROR")
slow = store.find_spans(min_duration_ms=100)
agent_spans = store.find_spans(agent_name="researcher")
```

---

## Troubleshooting

### Observability not working?

1. **Check configuration**:
```python
from praval.observability import get_config
config = get_config()
print(f"Enabled: {config.is_enabled()}")
```

2. **Check environment**:
```bash
echo $PRAVAL_OBSERVABILITY
echo $ENVIRONMENT
```

3. **Verify storage**:
```bash
ls -lh ~/.praval/traces.db
```

### Seeing NoOpSpan instead of Span?

This means observability is disabled or sampling rejected the span:
- Check `PRAVAL_OBSERVABILITY` is not set to "off"
- Check `ENVIRONMENT` is not set to "production" (when using "auto" mode)
- Check `PRAVAL_SAMPLE_RATE` is not too low

---

## Learn More

- **Plan**: See `temp_plans/praval_observability_plan.md` for complete specification
- **Tests**: See `tests/observability/` for comprehensive examples
- **Code**: See `src/praval/observability/` for implementation

---

## Feedback

Found a bug or have a suggestion? Please open an issue on GitHub!
