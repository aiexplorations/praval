# Praval Observability - Simple Guide

## What is it?

Observability automatically tracks what your Praval agents are doing:
- How long operations take
- What LLM calls cost
- Where errors happen
- How agents communicate

## Zero Configuration

Just use Praval normally. Observability is automatic:

```python
from praval import agent

@agent("researcher")
def research_agent(spore):
    result = chat("Research topic")
    return result

# Traces automatically saved to ~/.praval/traces.db
```

## View Your Traces

```python
from praval.observability import get_trace_store

store = get_trace_store()

# Get recent traces
recent = store.get_recent_traces(limit=10)

# View a specific trace
spans = store.get_trace(recent[0])
for span in spans:
    print(f"{span['name']}: {span['duration_ms']:.0f}ms")
```

## Configuration (Optional)

Only 3 environment variables:

```bash
# Turn on/off (default: auto-enabled in dev, disabled in prod)
PRAVAL_OBSERVABILITY=on

# Export to Jaeger, Zipkin, etc. (optional)
PRAVAL_OTLP_ENDPOINT=http://localhost:4318/v1/traces

# Sample only 10% of requests (optional, for performance)
PRAVAL_SAMPLE_RATE=0.1
```

## That's It!

- **Phase 1** (now): Core infrastructure ready
- **Phase 2** (next): Automatic instrumentation of all agents
- **Phase 3** (later): Export to external tools

## Try It

```bash
# Simplest example
python examples/observability/000_quickstart.py

# See all configuration options
python examples/observability/002_configuration_demo.py
```

## Questions?

See the full README: `examples/observability/README.md`
