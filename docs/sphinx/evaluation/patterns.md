# Recommended agent and evaluator-agent patterns

Reliable evaluation begins in the target design. It cannot be repaired later
by a more elaborate judge.

## Design an agent for evaluation

Use these defaults:

1. Give the agent, workflow, case, prompt, model profile, tool schema, and
   rubric stable versioned identities.
2. Return a structured terminal outcome. Do not make a judge infer success
   from incidental log messages.
3. Bound tool rounds, timeouts, retries, output, context, and concurrency.
4. Inject providers, clocks, retrieval, and tools through deterministic seams
   so tests do not need live services.
5. Produce exactly one immutable `ExecutionObservation` for each evaluated
   agent or workflow. Aggregate model, tool, retry, HITL, and handoff facts into
   it.
6. Keep content out of stored records and telemetry unless a reviewed content
   policy explicitly enables it.

`AgentEvaluationTarget` enforces the single-observation boundary and restores
conversation history between cases. It rejects `persist_state=True`, because
case order must not change the next result.

## Pair target and evaluator

### Single agent

```text
LoadedEvalCase -> target Agent -> one agent observation + ephemeral output
                                -> deterministic metrics
                                -> separate evaluator Agent -> JudgeResult
```

The target and evaluator use different names and preferably different model
profiles. Self-evaluation is rejected unless explicitly enabled. The evaluator
receives a bounded task envelope, not direct access to the target's live state.

### Workflow

```text
LoadedEvalCase -> correlated workflow root
                  -> specialist handoffs and tools
                  -> one workflow observation with aggregated facts
                  -> workflow metrics and evaluator Agent
```

Child agent spans remain visible in telemetry, but the evaluation subject is
the single workflow observation. Do not score each internal span as if it were
an independent user outcome.

## Least-privilege evaluator

An evaluator agent is a normal Praval `Agent`, with a separate system prompt,
model, tools, MCP connections, memory configuration, retrieval source, HITL
policy, limits, and observability. The judge narrows that configured capability
set:

- `allowed_tools` may remove tools but never grant a tool absent from the
  evaluator agent.
- `tool_policy="read_only"` requires read-only metadata.
- `tool_policy="evaluation_safe"` accepts read-only or explicitly
  `evaluation_safe` tools.
- Side-effecting evaluator tools are not supported in v0.8.3.
- `persist_state=True` is rejected. If memory is enabled, give the evaluator a
  dedicated namespace and retention policy that cannot write into target
  operational memory.
- A required HITL decision suspends or fails the evaluation job, never the
  already-completed user request.

## Decision table

| Need | Use | Avoid |
|---|---|---|
| Exact schema/value equality | deterministic metric | model judge |
| Ordered tool selection | `ToolCallMatchMetric` | parsing prose logs |
| Domain formula | custom metric plugin | embedding a rule in a rubric |
| Semantic rubric | `ModelJudge` | target model judging itself |
| Read-only evidence lookup | `AgentJudge` with allowlist | target credentials/tools |
| RAG faithfulness/relevance | supported RAGAS metric | importing RAGAS types into core code |
| Production sampling | `OnlineEvaluationService` + PostgreSQL | judge calls on request path |

## Anti-patterns

- One observation per model or tool call. This fragments the actual outcome
  and creates ambiguous subjects.
- Evaluating trace-backend search results. Retention and sampling then change
  correctness.
- Sharing target conversation history or memory with the evaluator.
- Giving the evaluator all target tools, especially write or payment tools.
- Unversioned rubrics, prompts, schemas, datasets, or baselines.
- Automatically promoting the latest run as a baseline.
- Retrying an invalid judge response without a strict attempt, cost, and time
  bound.
- Persisting raw candidate output or exception text in telemetry.

The credential-free paired example is `examples/evaluation/001_paired_agents.py`.
Its tests cover successful judging, single-observation enforcement, unsafe-tool
rejection, self-evaluation rejection, and bounded invalid judge output.
