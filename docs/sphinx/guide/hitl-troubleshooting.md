# HITL Troubleshooting

Common issues for Human-in-the-Loop (HITL) interventions in Praval 0.8.

## `HITLConfigurationError`

**Symptom:**
A tool call fails immediately with `HITLConfigurationError`.

**Cause:**
Tool metadata has `requires_approval=True` but the agent is decorated/configured with `hitl=False`.
The check needs no database: an agent with `hitl=False` never opens the HITL
database (the default path or `PRAVAL_HITL_DB_PATH`) for its tool calls.

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

## Resume reports "is not pending"

**Cause:**
Another thread or process is resuming, or has resumed, the same run. A resume
first moves the suspended run from `pending` to `resuming` in one atomic
update, so only one caller executes the approved tool. The run becomes
`completed` on success and returns to `pending` if the resume raises.

**Fix:**
Check the run's status in the HITL store. A run left in `resuming` after the
resuming process crashed is not resumed automatically, because its tool may
already have run. Inspect the tool's side effects first; to resume it again,
reset it with `HITLStore.update_suspended_run_status(run_id, status="pending")`.
If the suspended state has a `resume_results` entry, the tool finished and its
result was stored, and a reset run reuses that result instead of running the
tool again.

## Resume fails after the approved tool ran

**Symptom:**
`resume_run()` or `aresume_run()` raises (for example a `ProviderError` from
the model call that follows the tool), and the run is `pending` again.

**Behaviour:**
The approved tool, and any other tool calls in the same round, run at most
once per decision. As soon as each one returns, its result is stored with the
suspended run under `resume_results`, keyed by the intervention it belongs to.
Resuming the run again sends the stored results to the model without running
those tools again. Tool calls the model makes in later rounds are new calls
and run normally.

**Fix:**
Resolve the cause of the error (credentials, quota, provider outage) and call
`resume_run(run_id)` again.

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
