# Evaluator flow and capability policy

For each subject, Praval builds a bounded `JudgeContext` containing the loaded
case, immutable subject observation, and ephemeral target output. The evaluator
receives a versioned system rubric plus a canonical candidate envelope. It must
return the strict `JudgeResult` payload: status, score and label for pass/fail,
optional bounded explanation, and bounded evidence references.

```text
lease job -> load immutable subject -> resolve ephemeral context
          -> enter evaluation_call_scope
          -> normal Agent tool/model loop with narrowed allowlist
          -> validate structured response
          -> persist idempotent JudgeResult
          -> emit metadata-only linked telemetry
```

The evaluation-call marker prevents sampled online evaluation from recursively
evaluating its own judge calls. It does not hide judge spans; observability can
still distinguish and cost them.

## Tools and side effects

An allowed tool must already exist on the evaluator agent and satisfy its
selected metadata policy. For `read_only`, use `metadata={"read_only": true}`
or a supported read-only hint. For `evaluation_safe`, either read-only or
`metadata={"evaluation_safe": true}` is accepted. v0.8.3 rejects evaluator
side effects even when a configuration attempts to enable them.

If a tool requires approval, configure evaluator HITL independently. In
offline evaluation, the runner may surface the suspended evaluation. In online
evaluation, only the durable evaluation job may wait or fail; the completed
user request is never reopened.

## Isolation and budgets

- Use a distinct evaluator memory namespace. Never point it at target
  operational memory.
- Treat candidate output as untrusted data, not instructions. The rubric and
  system message must say this explicitly.
- Cap tool rounds, attempts, wall time, input tokens, output tokens, and cost.
- Keep temperature at zero for direct judges and pin provider/model profiles.
- Store evidence as `ContentReference` values unless an approved content
  policy requires a protected content store.

Cancellation is re-raised so process shutdown remains correct. Other failures
are reduced to a bounded error type; raw provider or tool exception text is not
placed in the result.
