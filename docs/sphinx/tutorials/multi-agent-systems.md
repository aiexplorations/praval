# Recipe: a bounded multi-agent workflow

Substantial systems need more than chained broadcasts. Define a message
contract, correlation identifier, completion rule, and failure result before
adding model calls.

## Example flow

```text
review_requested
  -> security_result
  -> documentation_result
  -> gate_decision
```

Two specialists can run from the same request. An aggregator waits until both
terminal results have arrived for the same correlation ID.

```python
from collections import defaultdict

from praval import agent, broadcast

results = defaultdict(dict)


def emit(role, spore, status, finding):
    broadcast(
        {
            "type": f"{role}_result",
            "correlation_id": spore.knowledge["correlation_id"],
            "role": role,
            "status": status,
            "finding": finding,
        }
    )


@agent("security", provider="ollama", responds_to=["review_requested"])
def security(spore):
    emit("security", spore, "complete", "no embedded credentials")


@agent("documentation", provider="ollama", responds_to=["review_requested"])
def documentation(spore):
    emit("documentation", spore, "complete", "release notes present")


@agent(
    "gatekeeper",
    provider="ollama",
    responds_to=["security_result", "documentation_result"],
)
def gatekeeper(spore):
    correlation_id = spore.knowledge["correlation_id"]
    results[correlation_id][spore.knowledge["role"]] = spore.knowledge
    if set(results[correlation_id]) == {"security", "documentation"}:
        broadcast(
            {
                "type": "gate_decision",
                "correlation_id": correlation_id,
                "decision": "go",
            }
        )
```

Production workflows should bound duplicate delivery, late results, partial
failure, timeouts, retries, and cleanup according to their own domain policy.
Praval does not add a universal retry or circuit-breaker policy.

The four capstone notebooks apply these ideas to research, customer support,
release readiness, and a protected-live marketing studio.
