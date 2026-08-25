# Cases, datasets, and suites

Evaluation datasets are UTF-8 JSON Lines. Each non-empty line is one bounded
JSON object.

```json
{"id":"case-001","name":"Known answer","input":{"question":"2+2"},"expected_output":{"answer":4},"reference_contexts":["Arithmetic over integers"],"expected_tool_calls":["calculator"],"tags":["smoke","math"],"metadata":{"owner":"quality"}}
```

| Field | Required | Contract |
|---|---|---|
| `id` | yes | non-empty and unique in the file |
| `input` | yes | finite JSON, bounded by loader limits |
| `name` | no | defaults to `id` |
| `expected_output` | no | finite JSON; required by some metrics |
| `reference_contexts` | no | JSON array; required by some RAGAS metrics |
| `expected_tool_calls` | no | ordered array of tool names |
| `tags` | no | array used for deterministic selection |
| `metadata` | no | bounded scalar values only |

`load_jsonl_suite()` rejects duplicate IDs, non-finite numbers, oversized
lines/content, unknown requested IDs, and empty selections. Selection is
stable: explicit case IDs are sorted; tag filters are deterministic; a seeded
limit hashes case IDs before selecting and then restores stable order.

Persisted `EvalCase` values hold `ContentReference` objects with SHA-256, size,
media type, and a dataset URI. The loaded input, expected output, and reference
contexts remain ephemeral. Dataset storage and access control remain an
application responsibility.

A suite pins target, case IDs, judge names, metric names, gates, and tags.
Version the suite ID when its semantic contract changes. `EvalRunner`
parallelizes cases up to `concurrency`, but each `AgentEvaluationTarget` also
protects its ordinary agent's mutable history. Use separate agent instances
when true target parallelism is required.
