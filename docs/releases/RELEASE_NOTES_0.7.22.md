# Release Notes 0.7.22

## Summary

Praval 0.7.22 introduces agent-gated Human-in-the-Loop (HITL) interventions
for provider tool calls, with durable SQLite-backed pause/resume workflows.

## Highlights

- `@agent(..., hitl=False)` is now the default behavior.
- `@agent(..., hitl=True)` enables approval gates for risky tools.
- Tool metadata supports:
  - `requires_approval`
  - `risk_level`
  - `approval_reason`
- New exceptions:
  - `InterventionRequired`
  - `HITLConfigurationError`
- All supported providers participate in HITL flow:
  - OpenAI
  - Anthropic
  - Cohere
- New CLI commands:
  - `praval hitl pending`
  - `praval hitl show <intervention_id>`
  - `praval hitl approve <intervention_id>`
  - `praval hitl reject <intervention_id>`
  - `praval hitl resume <run_id>`

## Migration Notes (0.7.21 → 0.7.22)

1. If you want HITL behavior, opt in per agent with `hitl=True`.
2. If a tool requires approval and the agent is `hitl=False`, execution now raises
   `HITLConfigurationError`.
3. Callers using `Agent.chat()` should handle `InterventionRequired` for HITL-enabled agents.

## Use-Case Evaluation Matrix

- A: `hitl=False` + non-gated tool => unchanged autonomous behavior.
- B: `hitl=False` + gated tool => `HITLConfigurationError`.
- C: `hitl=True` + gated tool => `InterventionRequired` + pending intervention.
- D: Approve + resume => tool executes and run completes.
- E: Edit + resume => edited args are applied.
- F: Reject + resume => deterministic rejected-tool path is returned to model.
- G: Restart + resume => suspended state restored from SQLite.
- H: Provider parity validated for OpenAI, Anthropic, Cohere.
- I: Mixed HITL/non-HITL agents operate independently by decorator flag.

## Validation Checklist

- [x] `make lint` (passes)
- [x] `make type-check` (`Success: no issues found in 63 source files`)
- [x] `make test` (`1275 passed, 15 skipped, 28 xfailed, 1 xpassed`)
- [x] `make test-cov` (`90.34%`, gate `>=90%` satisfied)
- [ ] `make docs-check` (offline dependency install failure: `setuptools>=61.0`)
- [ ] `make docs-html` (same offline install issue in Make target)
- [x] `sphinx-build -b html docs/sphinx docs/_build/html` (build succeeds with warnings)
- [x] `python tests/test_all_examples.py` (`30 passed, 0 failed`)
- [x] `scripts/test-docker-examples.sh` (passed)
- [x] `python examples/distributed_agents_with_rabbitmq.py` (passes in local smoke mode by default)

## Examples and Use-Case Evidence

- Use cases A-I are covered by HITL unit/provider tests in:
  - `tests/test_hitl_agent.py`
  - `tests/test_hitl_store.py`
  - `tests/test_hitl_provider_parity.py`
- New HITL examples pass:
  - `examples/015_hitl_tool_approval.py`
  - `examples/016_hitl_mixed_agents.py`
- Full example sweep now passes with no failures:
  - `30 passed, 0 failed`

## Documentation Publication

- Documentation artifacts for this release were published to the website repo:
  - `~/Github/praval-ai/docs/v0.7.22`
  - `~/Github/praval-ai/docs/latest`
- `~/Github/praval-ai/docs/versions.json` was updated with `current/latest = 0.7.22`.

## Known Constraints

- CLI resume requires the target agent to be registered in the current process
  (use `--module` to import agent modules first).
- SQLite is the default HITL persistence backend for this release.
