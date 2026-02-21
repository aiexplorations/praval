# Tutorial: HITL Interventions

Learn how to enforce human approvals for risky tool calls using agent-gated HITL.

## Prerequisites
- `pip install -e .[dev]`
- At least one provider API key set (OpenAI, Anthropic, or Cohere)

## 1) Mark a Tool as Approval-Gated

```python
from praval import tool

@tool(
    tool_name="critical_write",
    description="Perform a critical write",
    requires_approval=True,
    risk_level="critical",
    approval_reason="Writes to production resources."
)
def critical_write(resource: str) -> str:
    return f"write-complete:{resource}"
```

## 2) Enable HITL on the Agent

```python
from praval import agent

@agent("ops_agent", tools=["critical_write"], hitl=True)
def ops_agent(spore):
    return {"status": "ready"}
```

`hitl=False` is the default, so enable it only for agents that should pause for human decisions.

## 3) Run, Approve, Resume

```python
from praval import InterventionRequired

try:
    response = ops_agent._praval_agent.chat("Run critical_write on prod")
    print(response)
except InterventionRequired as interruption:
    # Option A: approve original arguments
    ops_agent.approve_intervention(interruption.intervention_id, reviewer="oncall")

    # Option B: edit arguments before approval
    # ops_agent.approve_intervention(
    #     interruption.intervention_id,
    #     reviewer="oncall",
    #     edited_args={"resource": "staging"},
    # )

    resumed = ops_agent.resume_run(interruption.run_id)
    print(resumed)
```

## 4) CLI Workflow

```bash
praval hitl pending
praval hitl show <intervention_id>
praval hitl approve <intervention_id> --reviewer oncall
praval hitl reject <intervention_id> --reason "Unsafe"
praval hitl resume <run_id>
```

## 5) Conflict Semantics

If an agent is declared with `hitl=False` and the invoked tool requires approval,
Praval raises `HITLConfigurationError`. This prevents accidental policy bypass.

## See Also
- [Tool Integration Tutorial](./tool-integration.md)
- [Tool System Guide](../guide/tool-system.md)
- `examples/015_hitl_tool_approval.py`
- `examples/016_hitl_mixed_agents.py`
