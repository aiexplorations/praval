# Recipe: agent communication

This recipe builds a two-stage message flow without a model call. It isolates
Reef and Spore behavior so you can inspect it before adding provider output.

## Message contract

```text
work_requested -> work_completed
```

Both messages carry a `correlation_id`. The second agent copies it instead of
inventing a new identifier.

## Implement the handlers

```python
from praval import agent, broadcast, get_reef, start_agents

trail = []


@agent("worker", provider="ollama", responds_to=["work_requested"])
def worker(spore):
    trail.append(spore)
    broadcast(
        {
            "type": "work_completed",
            "correlation_id": spore.knowledge["correlation_id"],
            "result": spore.knowledge["value"].upper(),
        }
    )


@agent("reviewer", provider="ollama", responds_to=["work_completed"])
def reviewer(spore):
    trail.append(spore)
    print(spore.knowledge["result"])


start_agents(
    worker,
    reviewer,
    initial_data={
        "type": "work_requested",
        "correlation_id": "demo-1",
        "value": "reef delivery",
    },
)
reef = get_reef()
reef.wait_for_completion(timeout=30)

assert [item.knowledge["type"] for item in trail] == [
    "work_requested",
    "work_completed",
]
assert {item.knowledge["correlation_id"] for item in trail} == {"demo-1"}
reef.shutdown()
```

The Ollama preset makes the underlying handler agents credential-free. No
model call occurs, so a local server is not required for this recipe.

## What to inspect

Each trail entry is a `Spore`. Inspect its `id`, `from_agent`, `to_agent`,
`spore_type`, `knowledge`, and metadata. In a real workflow, also require every
fan-out branch to emit a terminal success or failure result.

For channels, request/reply, async handlers, and fan-out/fan-in, continue with
the visual course notebooks `02`, `03`, and `04`.
