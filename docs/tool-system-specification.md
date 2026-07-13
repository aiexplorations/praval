# Tools

Tools expose Python functions to agents. Legacy decorators and provider imports
remain compatible, but runtime-owned orchestration is the preferred direction.

```python
from praval import Agent

agent = Agent("calculator", provider="openai", model="gpt-5.4-mini")

@agent.tool
def add(x: int, y: int) -> int:
    return x + y

print(agent.chat("Use the tool to add 2 and 3."))
```

Tool declarations are normalized into `ToolSpec` objects with JSON Schema
parameters. HITL metadata such as `requires_approval`, `risk_level`, and
`approval_reason` is preserved when legacy tool dictionaries are converted.

Providers should translate tool declarations and tool-call wire shapes only.
Runtime code owns execution, approval, resume state, retries, tracing, and final
follow-up calls.
