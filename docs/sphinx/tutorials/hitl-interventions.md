# Tutorial: human approval for a tool call

HITL is enforced at the Agent boundary. A protected tool call can be persisted,
reviewed, and resumed without exposing a private decorated-agent attribute.

## Define an approval-gated tool

```python
from praval import Agent, InterventionRequired, ToolSpec


def critical_write(resource: str) -> str:
    return f"write-complete:{resource}"


spec = ToolSpec(
    name="critical_write",
    description="Perform a critical write",
    parameters={
        "type": "object",
        "properties": {"resource": {"type": "string"}},
        "required": ["resource"],
    },
    requires_approval=True,
    risk_level="critical",
    approval_reason="Writes to a production resource.",
)
```

## Enable HITL and run

```python
agent = Agent(
    "ops-agent",
    provider="openai",
    model="gpt-5.4-mini",
    hitl_enabled=True,
    hitl_db_path="./interventions.sqlite3",
)
agent.add_tool_spec(spec, critical_write)

try:
    try:
        response = agent.generate("Use critical_write for production/orders.")
        print(response.content)
    except InterventionRequired as interruption:
        print(interruption.intervention_id, interruption.run_id)
        agent.approve_intervention(
            interruption.intervention_id,
            reviewer="oncall",
            edited_args={"resource": "staging/orders"},
        )
        print(agent.resume_run(interruption.run_id))
finally:
    agent.close()
```

The model must actually request the tool for an intervention to be created.
`edited_args` is optional; omit it to approve the original arguments. Use
`reject_intervention()` with a reason to reject.

The SQLite store permits the pending intervention and suspended run to be
inspected from another process before resumption.

`critical_write` is a harmless simulated handler. The example's programmatic
approval illustrates the API; a real application must obtain its reviewer's
decision before approving a protected action.

## CLI review

```bash
praval --hitl-db-path ./interventions.sqlite3 hitl pending
praval --hitl-db-path ./interventions.sqlite3 hitl show <intervention_id>
praval --hitl-db-path ./interventions.sqlite3 hitl approve <intervention_id> --reviewer oncall
praval --hitl-db-path ./interventions.sqlite3 hitl reject <intervention_id> --reason "Unsafe"
praval --hitl-db-path ./interventions.sqlite3 hitl resume <run_id> --module your_project.agents
```

The global `--hitl-db-path` option must precede `hitl` and must match the agent's
database. These are alternative review actions for a pending run; the example
above already approves and resumes its own run. For CLI resume, replace
`your_project.agents` with a module that registers the same agent and tools.

If a tool requires approval while HITL is disabled, Praval raises
`HITLConfigurationError`. It does not execute the tool autonomously.

MCP tools use the same approval flow but are async-only in this release. Resume
those runs with the async Agent API.

The optional protected live certification verifies a real provider-generated
call, persistent interruption, argument editing or approval, and resume.
