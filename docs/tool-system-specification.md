# Tools

Tools expose Python functions to agents. Legacy decorators and provider imports
remain compatible, but runtime-owned orchestration is the preferred direction.

```python
from praval import Agent

agent = Agent("calculator", provider="openai", model="gpt-5.4-mini")

@agent.tool
def add(x: int, y: int) -> int:
    return x + y

try:
    print(agent.chat("Use the tool to add 2 and 3."))
finally:
    agent.close()
```

Tool declarations are normalized into `ToolSpec` objects with JSON Schema
parameters. HITL metadata such as `requires_approval`, `risk_level`, and
`approval_reason` is preserved when legacy tool dictionaries are converted.

Providers translate declarations and provider-specific tool-call wire shapes.
Runtime code owns execution, approval and resume state, tracing, and final
follow-up calls. Retry behavior is provider and error specific; Praval does not
promise universal retries or a circuit breaker.
