# HITL Troubleshooting

Common issues for Human-in-the-Loop (HITL) interventions in Praval 0.8.0.

## `HITLConfigurationError`

**Symptom:**
A tool call fails immediately with `HITLConfigurationError`.

**Cause:**
Tool metadata has `requires_approval=True` but the agent is decorated/configured with `hitl=False`.

**Fix:**
Enable HITL for that agent:

```python
@agent("ops_agent", hitl=True, tools=["critical_tool"])
def ops_agent(spore):
    ...
```

## `InterventionRequired` during `Agent.chat()`

**Symptom:**
`chat()` raises `InterventionRequired`.

**Cause:**
Expected behavior for approval-gated tools on `hitl=True` agents.

**Fix:**
Approve/reject/edit intervention, then resume the run:

```python
agent.approve_intervention(intervention_id, reviewer="oncall")
agent.resume_run(run_id)
```

## Pending queue never clears

**Checklist:**
1. Inspect queue: `praval hitl pending`.
2. Confirm intervention decision exists (`APPROVED`/`REJECTED`).
3. Resume run via API or CLI.
4. Verify DB path consistency (`PRAVAL_HITL_DB_PATH` vs explicit `--hitl-db-path`).

## `praval hitl resume` cannot find agent

**Symptom:**
CLI reports agent not registered in current process.

**Cause:**
CLI process has not imported/initialized the module that defines the agent.

**Fix:**
Use `--module` to import agent modules before resume:

```bash
praval hitl resume <run_id> --module your_project.agents
```

## Resume fails after restart

**Checklist:**
1. Use the same HITL SQLite database path across restarts.
2. Ensure tool names and signatures are unchanged.
3. Ensure code imports register the same agent name used by the suspended run.
