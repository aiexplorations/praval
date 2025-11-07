# Agent Lifecycle Management in Praval

> **Added in v0.7.14**: Proper async lifecycle management for distributed agents with RabbitMQ

## Overview

The agent lifecycle describes the stages an agent goes through: registration, initialization, execution, and shutdown. Understanding these stages is important for:

1. **Local agents** (InMemoryBackend) - Simple, synchronous
2. **Distributed agents** (RabbitMQBackend) - Requires async event loop management

## The Problem (v0.7.13 and Earlier)

In previous versions, distributed agents didn't consume messages from RabbitMQ:

```python
# This DIDN'T work - agents never consumed messages
@agent("processor")
def process(spore):
    return {"result": "done"}

# Agent was registered but RabbitMQ had no event loop to:
# 1. Connect to the broker
# 2. Subscribe to queues
# 3. Listen for messages
```

**Why?** The `@agent` decorator subscribes agents at import time (synchronous), but RabbitMQ requires an async event loop to consume messages. Without a running loop, agents were "deaf" to the broker.

## The Solution (v0.7.14)

### Using `run_agents()` (Recommended)

The simplest way to run distributed agents:

```python
from praval import agent
from praval.composition import run_agents

@agent("processor")
def processor_agent(spore):
    return {"processed": True}

@agent("analyzer")
def analyzer_agent(spore):
    return {"analyzed": True}

# Run with proper async lifecycle
run_agents(
    processor_agent,
    analyzer_agent,
    backend_config={
        'url': 'amqp://localhost:5672/',
        'exchange_name': 'praval.agents'
    }
)
```

What `run_agents()` does:
1. Creates an async event loop
2. Initializes RabbitMQ backend (connects to broker)
3. Subscribes agents to their message queues
4. Keeps the loop running until Ctrl+C (SIGTERM/SIGINT)
5. Gracefully shuts down on signals

### Using `AgentRunner` (Advanced)

For more control over initialization:

```python
from praval.core.agent_runner import AgentRunner

runner = AgentRunner(
    agents=[processor_agent, analyzer_agent],
    backend_config={
        'url': 'amqp://localhost:5672/',
        'exchange_name': 'praval.agents'
    }
)

# Option 1: Blocking call
runner.run()

# Option 2: Async context (for async applications)
async with runner.context():
    # Agents are running
    await some_async_operation()
    # Shutdown happens automatically on exit
```

### Using `AgentRunner` in Async Code

If your application is already async:

```python
import asyncio
from praval.core.agent_runner import AgentRunner

async def main():
    runner = AgentRunner(
        agents=[processor_agent, analyzer_agent],
        backend_config={'url': 'amqp://localhost:5672/'}
    )

    # Initialize
    await runner.initialize()

    try:
        # Agents are ready to consume messages
        # Do your work here
        await some_operation()

    finally:
        # Cleanup
        await runner.shutdown()

asyncio.run(main())
```

## Agent Lifecycle Stages

### Stage 1: Decoration (Import Time)

```python
@agent("my_agent")
def my_agent(spore):
    return {}
```

**What happens:**
- Agent function is wrapped
- Metadata attached (`_praval_agent`, `_praval_name`, etc.)
- Agent registered in global registry
- Spore handler set up
- **NOT YET:** Subscribed to RabbitMQ (that's async, can't do synchronously)

### Stage 2: Initialization (start_agents/run_agents)

```python
run_agents(my_agent, backend_config={...})
```

**What happens:**
1. **Backend Initialization** - RabbitMQ connected
   ```
   await reef.initialize_backend(config)
   ```
2. **Agent Subscription** - Agents subscribe to message queues
   ```
   await backend.subscribe(channel, handler)
   ```
3. **Event Loop Started** - Loop ready to consume messages
   ```
   loop.run_until_complete(run_async())
   ```

### Stage 3: Execution

**What agents do:**
- Receive spores from message queues
- Execute their handler functions
- Return results (auto-broadcast or manual)
- May send messages to other agents

**The event loop continuously:**
- Polls message queues
- Delivers spores to agent handlers
- Handles async operations
- Logs errors and activity

### Stage 4: Shutdown

```python
# User presses Ctrl+C or system sends SIGTERM
```

**What happens:**
1. **Shutdown signal** - SIGTERM/SIGINT received
2. **Event loop stops** - Stops accepting new messages
3. **Handlers finish** - Running handlers complete
4. **Backend closes** - RabbitMQ connection closed
5. **Loop closed** - Event loop shut down cleanly

## Local vs Distributed Agents

### Local Agents (InMemoryBackend)

```python
from praval.composition import start_agents

# Synchronous, simple
start_agents(
    agent1,
    agent2,
    initial_data={"task": "analyze"}
)
```

- No event loop needed
- Messages delivered synchronously
- Fast (no network latency)
- Good for: Scripts, testing, single-process apps

### Distributed Agents (RabbitMQBackend)

```python
from praval.composition import run_agents

# Async, with proper lifecycle
run_agents(
    agent1,
    agent2,
    backend_config={'url': 'amqp://...'}
)
```

- Requires event loop
- Messages go through RabbitMQ
- Network latency
- Good for: Microservices, scaling, multi-server deployments

## Comparing Agent Functions

### What Hasn't Changed

Agent functions work the same way:

```python
@agent("processor")
def process(spore):
    """Agent function - works identically in local or distributed mode."""
    data = spore.knowledge.get('data')
    result = process_data(data)
    return {"result": result}
```

### Local Execution
```python
start_agents(process, initial_data={"data": "hello"})
# Message delivered synchronously
# Agent executed immediately
# Result returned and broadcast
```

### Distributed Execution
```python
run_agents(process, backend_config={'url': 'amqp://...'})
# Message sent to RabbitMQ
# Event loop monitors queue
# Agent handler executed when message arrives
# Result published back to RabbitMQ
```

## Troubleshooting

### "Agents not consuming messages"

**Problem:** Agents receive no messages from RabbitMQ

**Solution:** Make sure you're using `run_agents()` or `AgentRunner`:
```python
# ❌ Wrong - no event loop running
from praval import agent
@agent("my_agent")
def my_agent(spore):
    return {}

# ✅ Right - proper lifecycle
from praval.composition import run_agents
run_agents(my_agent, backend_config={...})
```

### "RabbitMQ connection refused"

**Problem:** Can't connect to RabbitMQ

**Solution:** Ensure RabbitMQ is running:
```bash
# Start RabbitMQ in Docker
docker run -d -p 5672:5672 rabbitmq:latest

# Or install locally
brew install rabbitmq
brew services start rabbitmq
```

### "RuntimeError: run_async already running"

**Problem:** Trying to start agent runner twice

**Solution:** Create a new runner instance:
```python
# ❌ Wrong
runner.run()
runner.run()  # Error!

# ✅ Right
runner = AgentRunner(agents=[...])
runner.run()

runner = AgentRunner(agents=[...])  # New instance
runner.run()
```

### "Event loop already running"

**Problem:** Calling `run_agents()` from async code

**Solution:** Use `AgentRunner` directly instead:
```python
# ❌ Wrong
async def main():
    run_agents(...)  # Error - loop already running!

# ✅ Right
async def main():
    runner = AgentRunner(agents=[...], backend_config={...})
    async with runner.context():
        # Agents running
        await asyncio.sleep(10)
```

## Migration Guide (v0.7.13 → v0.7.14)

### If You Were Using Docker Bootstrap

**Old (v0.7.13):**
```python
# bootstrap.py - Didn't actually consume messages
from praval import agent

@agent("my_agent")
def my_agent(spore):
    return {}

# Then in Docker: just wait, agents never consumed messages
```

**New (v0.7.14):**
```python
# bootstrap.py
from praval import agent
from praval.composition import run_agents

@agent("my_agent")
def my_agent(spore):
    return {}

if __name__ == '__main__':
    run_agents(
        my_agent,
        backend_config={
            'url': 'amqp://rabbitmq:5672/',
            'exchange_name': 'praval.agents'
        }
    )
```

### If You Were Manually Creating Agents

**Old (v0.7.13):**
```python
from praval.core.reef import get_reef
from praval.core.reef_backend import RabbitMQBackend

reef = Reef(backend=RabbitMQBackend())
await reef.initialize_backend({'url': 'amqp://...'})
# Agents still didn't consume - missing event loop
```

**New (v0.7.14):**
```python
from praval.composition import run_agents

run_agents(my_agent1, my_agent2, backend_config={'url': 'amqp://...'})
# Proper event loop, agents consume messages
```

### What's Compatible

✅ All existing agent code works unchanged
✅ InMemoryBackend still works as before
✅ `start_agents()` for local agents unchanged
❌ RabbitMQ distributed agents MUST use `run_agents()` or `AgentRunner`

## Best Practices

### 1. Use `run_agents()` for Simplicity

```python
# Simple, recommended
run_agents(agent1, agent2, backend_config={...})
```

### 2. Handle Shutdown Gracefully

```python
# run_agents() handles SIGTERM/SIGINT automatically
# But make sure your agent functions are safe:

@agent("processor")
def process(spore):
    try:
        result = expensive_operation()
        return {"result": result}
    except KeyboardInterrupt:
        # Clean up and return gracefully
        logger.info("Shutting down gracefully")
        return {"status": "shutdown"}
```

### 3. Log Agent Activity

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(message)s'
)

@agent("my_agent")
def my_agent(spore):
    logger.info(f"Processing {spore.knowledge}")
    # ... process ...
    logger.info("Processing complete")
    return {"done": True}
```

### 4. Monitor Agent Health

```python
# Get runner stats
runner = AgentRunner(agents=[...])
runner.run()  # In another thread or process

# Check stats
stats = runner.get_stats()
print(f"Agents running: {stats['agents']}")
print(f"Backend: {stats['backend']}")
print(f"Channels: {stats['channels']}")
```

## Advanced: Custom Event Loops

If you need to use a custom event loop:

```python
import asyncio

# Create custom event loop (e.g., with specific policies)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

runner = AgentRunner(
    agents=[...],
    backend_config={...},
    loop=loop  # Pass your loop
)

runner.run()  # Uses your loop
```

## References

- **Example:** `examples/distributed_agents_bootstrap.py`
- **Tests:** `tests/test_distributed_agent_startup.py`
- **Implementation:** `src/praval/core/agent_runner.py`
- **Main API:** `src/praval/composition.py`

## FAQ

**Q: Do I need to use `run_agents()` for local agents?**
A: No. `start_agents()` still works for local/InMemoryBackend. Use `run_agents()` only for RabbitMQ.

**Q: Can I have mixed local and distributed agents?**
A: No, choose one backend per Reef instance. Create separate runners for different backends.

**Q: What happens if RabbitMQ goes down?**
A: Agents will log errors but won't crash. When RabbitMQ comes back online, they'll reconnect automatically.

**Q: Can I have multiple agent runners?**
A: Yes, but each with separate Reef instances and backends.

**Q: How do I test agents without RabbitMQ?**
A: Use `start_agents()` with InMemoryBackend for unit tests.

---

**Version:** v0.7.14
**Last Updated:** 2025-11-08
