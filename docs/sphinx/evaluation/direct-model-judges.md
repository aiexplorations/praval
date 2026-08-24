# Direct model judges

`ModelJudge` sends the same strict evaluation envelope directly through a
provider-neutral `ModelRuntime`. It is the simpler paid judge when no tools,
retrieval, memory, MCP, or HITL are required.

```toml
[models.quality_judge]
provider = "anthropic"
model = "claude-sonnet-5"
temperature = 0.0
max_output_tokens = 800

[eval.judges.quality]
model = "quality_judge"
timeout_seconds = 30
max_attempts = 2
allow_self_evaluation = false
max_input_tokens = 12000
max_cost_usd = 0.10
rubric = "Score factual correctness against the supplied reference."
rubric_version = "facts-v2"
judge_version = "1"
```

`ModelJudge.from_config()` resolves the model profile, forces temperature to
zero and provider retries to zero, and uses the judge's own bounded retry loop.
It requests strict structured output, records usage/cost when the provider
reports them, and hashes the exact versioned prompt.

Use a different provider/model from the target when practical. A same-model
subject is rejected by default. `allow_self_evaluation=true` is an explicit
exception, not a recommended production setting.

Timeouts, malformed structured output, provider errors, token-budget breach,
and cost-budget breach produce error results. They do not crash other cases,
and their exception messages are not persisted. A model judge cannot call
tools; choose {doc}`evaluator-agents` if bounded external evidence is necessary.
