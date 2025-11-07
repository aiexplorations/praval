# RabbitMQ Queue Consumption (v0.7.15)

> **Added in v0.7.15**: Support for direct queue consumption with pre-configured RabbitMQ queues

## Problem: Topic-Based vs Queue-Based Routing

Praval's RabbitMQBackend originally assumed a **topic-based exchange model** where:
- Agents publish to topics derived from Praval channels
- All messages use a single configurable exchange
- Routing is managed entirely by Praval

However, real-world RabbitMQ deployments often use **pre-configured queues** where:
- Queues are already defined and bound to exchanges
- Messages arrive from external systems (simulators, other apps)
- Different queues may be bound to different exchanges
- Agents need to consume directly from those pre-configured queues

## The Issue

When external systems publish to a different exchange than Praval's configured exchange:

```
External System              RabbitMQ Broker
     │                           │
     └──→ Publish to            │
         exchange: data.sources  │
         routing key: springs    │ Queue: agent.data_analyzer
     │                           │ Binding: data.sources exchange
     │                           │
     │◄──────────────────────────│
     │    (Messages arrive)      │
     │                           │
Praval Agents                    │
     │                           │
     └──→ Subscribe to           │
         exchange: praval.agents │
         topic: data_received.*  │ (Wrong exchange!)
     │                           │
     │◄──────────────────────────│
     │    (No messages)          │
     │                           │
```

**Result**: Messages published to `data.sources` never reach agents subscribed to `praval.analytics`.

## Solution: Channel-to-Queue Mapping

The fix provides a `channel_queue_map` parameter that tells RabbitMQBackend which pre-configured queues to consume from:

```python
from praval import agent
from praval.composition import run_agents

@agent("data_analyzer", channel="data_received")
def analyze_data(spore):
    # Process data from agent.data_analyzer queue
    return {"analysis": "complete"}

@agent("vision_inspector", channel="qc_inspection_received")
def inspect_quality(spore):
    # Process QC data from agent.vision_inspector queue
    return {"inspection": "complete"}

# Map Praval channels to pre-configured RabbitMQ queues
run_agents(
    analyze_data,
    inspect_quality,
    backend_config={
        'url': 'amqp://rabbitmq:5672/',
        'exchange_name': 'praval.agents'  # Still needed for publishing
    },
    channel_queue_map={
        "data_received": "agent.data_analyzer",           # Consume from this queue
        "qc_inspection_received": "agent.vision_inspector" # Consume from this queue
    }
)
```

## How It Works

When you provide a `channel_queue_map`:

1. **Channels with queue mappings** use **queue-based consumption**:
   - Directly consumes from the specified RabbitMQ queue
   - Ignores the configured exchange for subscription
   - Messages arrive from any exchange bound to that queue

2. **Channels without queue mappings** use **topic-based subscription** (default behavior):
   - Subscribes to topics on the configured exchange
   - Original Praval routing model

```
@agent("data_analyzer", channel="data_received")
            │
            ▼
channel_queue_map has "data_received"?
            │
    ┌───────┴───────┐
    │               │
   YES              NO
    │               │
    ▼               ▼
  Queue-based    Topic-based
  Consumption    Subscription
    │               │
    └───────┬───────┘
            ▼
      Agent receives
      messages from
      RabbitMQ
```

## Configuration Examples

### Example 1: Pre-configured Queues (Queue-based)

Your RabbitMQ setup already has queues defined:
- `agent.data_analyzer` bound to `data.sources` exchange
- `agent.vision_inspector` bound to `qc.events` exchange
- `agent.sink_dispatcher` bound to `data.sinks` exchange

```python
channel_queue_map = {
    "data_received": "agent.data_analyzer",
    "qc_inspection_received": "agent.vision_inspector",
    "quality_assessed": "agent.sink_dispatcher"
}

run_agents(
    data_analyzer_agent,
    vision_inspector_agent,
    sink_dispatcher_agent,
    backend_config={'url': 'amqp://localhost:5672/'},
    channel_queue_map=channel_queue_map
)
```

### Example 2: Praval-Managed Routing (Topic-based, Default)

You want Praval to manage all routing:

```python
# No channel_queue_map needed - uses topic-based subscription
run_agents(
    agent1,
    agent2,
    agent3,
    backend_config={
        'url': 'amqp://localhost:5672/',
        'exchange_name': 'praval.agents'
    }
    # channel_queue_map not specified → topic-based routing
)
```

### Example 3: Hybrid Approach

Some agents consume from queues, others use topic-based routing:

```python
# agent1 and agent2 consume from pre-configured queues
# agent3 uses topic-based subscription
channel_queue_map = {
    "channel1": "existing.queue.1",
    "channel2": "existing.queue.2",
    # channel3 has no mapping → uses topic-based subscription
}

run_agents(
    agent1,
    agent2,
    agent3,
    backend_config={'url': 'amqp://localhost:5672/'},
    channel_queue_map=channel_queue_map
)
```

## Choosing Your Approach

### Use Queue-Based Consumption When:

✅ You have existing RabbitMQ queues with bindings
✅ Messages come from external systems (simulators, APIs)
✅ Queues are on different exchanges than Praval's exchange
✅ You want agents to consume from pre-configured infrastructure
✅ You're integrating with existing RabbitMQ deployments

### Use Topic-Based Subscription When:

✅ All routing is Praval-managed
✅ You want a clean, purpose-built RabbitMQ setup
✅ All agents and services are Praval-based
✅ You prefer Praval to handle exchange and routing key logic
✅ You're building a new system from scratch

## Real-World Example

Imagine a data analytics platform with multiple data sources:

```
Data Sources:
├── Sensor Data (Springs) → exchange: data.sources → queue: agent.data_analyzer
├── QC Events (Vision) → exchange: qc.events → queue: agent.vision_inspector
└── Results Sink → exchange: data.sinks → queue: agent.sink_dispatcher

Praval Agents:
├── @agent("data_analyzer", channel="data_received")
├── @agent("vision_inspector", channel="qc_inspection_received")
└── @agent("sink_dispatcher", channel="quality_assessed")
```

Set up consumption:

```python
from praval import agent
from praval.composition import run_agents

@agent("data_analyzer", channel="data_received")
def analyzer(spore):
    logger.info(f"Analyzing: {spore.knowledge}")
    return {"analyzed": True}

@agent("vision_inspector", channel="qc_inspection_received")
def inspector(spore):
    logger.info(f"Inspecting: {spore.knowledge}")
    return {"inspected": True}

@agent("sink_dispatcher", channel="quality_assessed")
def dispatcher(spore):
    logger.info(f"Dispatching: {spore.knowledge}")
    return {"dispatched": True}

if __name__ == '__main__':
    run_agents(
        analyzer,
        inspector,
        dispatcher,
        backend_config={
            'url': 'amqp://localhost:5672/',
            'exchange_name': 'praval.analytics'
        },
        channel_queue_map={
            "data_received": "agent.data_analyzer",
            "qc_inspection_received": "agent.vision_inspector",
            "quality_assessed": "agent.sink_dispatcher"
        }
    )
```

Now agents will:
1. Consume directly from `agent.data_analyzer`, `agent.vision_inspector`, `agent.sink_dispatcher`
2. Receive messages from those queues (regardless of which exchange they're bound to)
3. Execute their handlers
4. Broadcast results back to RabbitMQ

## Migration from v0.7.14

**v0.7.14** (Topic-based only):
```python
# Could not consume from pre-configured queues
run_agents(agent1, agent2, agent3, backend_config={...})
```

**v0.7.15** (Topic-based + Queue-based):
```python
# Topic-based (old way, still works)
run_agents(agent1, agent2, agent3, backend_config={...})

# Queue-based (new)
run_agents(
    agent1, agent2, agent3,
    backend_config={...},
    channel_queue_map={
        "channel1": "agent.queue.1",
        "channel2": "agent.queue.2"
    }
)
```

No breaking changes - all v0.7.14 code works unchanged.

## Backward Compatibility

✅ **Fully backward compatible**
- Default behavior (topic-based) unchanged
- No `channel_queue_map` → uses topic-based subscription
- Existing deployments work without modification
- Can migrate gradually

## Advanced: Using AgentRunner Directly

If you need more control, use `AgentRunner` directly:

```python
from praval.core.agent_runner import AgentRunner

runner = AgentRunner(
    agents=[agent1, agent2, agent3],
    backend_config={'url': 'amqp://localhost:5672/'},
    channel_queue_map={
        "channel1": "queue.1",
        "channel2": "queue.2"
    }
)

runner.run()  # Blocks until shutdown
```

Or with async context:

```python
async def main():
    runner = AgentRunner(
        agents=[agent1, agent2, agent3],
        backend_config={'url': 'amqp://localhost:5672/'},
        channel_queue_map={
            "channel1": "queue.1",
            "channel2": "queue.2"
        }
    )

    async with runner.context():
        # Agents are running
        await asyncio.sleep(30)  # Let them process

asyncio.run(main())
```

## Troubleshooting

### "Agents still not consuming messages"

1. Verify queue name is correct:
   ```bash
   rabbitmq-admin list_queues | grep agent.data_analyzer
   ```

2. Check queue bindings:
   ```bash
   rabbitmq-admin list_queue_bindings
   ```

3. Enable debug logging:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   run_agents(..., channel_queue_map={...})
   ```

### "Mix of topics and queues not working"

Both modes work together. If `channel_queue_map` only partially specifies channels:

```python
# agent1 uses queue-based (has mapping)
# agent2 and agent3 use topic-based (no mapping)
channel_queue_map = {
    "channel1": "agent.queue.1"
    # "channel2" and "channel3" not listed → topic-based
}
```

### "Switching between modes causes issues"

Each agent handler gets routed correctly based on whether its channel is in `channel_queue_map`:

- ✅ Safe to mix
- ✅ Safe to change mappings
- ✅ Safe to add/remove from map

## References

- **Example**: `examples/distributed_agents_bootstrap.py`
- **API**: `src/praval/core/agent_runner.py` - `AgentRunner.__init__(channel_queue_map=...)`
- **Backend**: `src/praval/core/reef_backend.py` - `RabbitMQBackend`
- **Docs**: `docs/agent-lifecycle.md` - Agent lifecycle management

---

**Version**: v0.7.15
**Type**: Enhancement
**Breaking Changes**: None - Fully backward compatible
