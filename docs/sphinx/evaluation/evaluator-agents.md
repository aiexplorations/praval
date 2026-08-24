# Defining evaluator agents

Use `ModelJudge` when a model and rubric are sufficient. Use `AgentJudge` only
when evaluation needs an ordinary agent capability such as a read-only tool,
MCP server, retrieval source, isolated memory, or HITL.

## Configuration

```toml
[models.judge_model]
provider = "openai"
model = "gpt-5.4-mini"
temperature = 0.0
max_output_tokens = 800

[agents.quality_evaluator]
model = "judge_model"
system_message = "Judge only from the supplied evidence and rubric."
tools = ["policy_lookup"]
memory_enabled = true
memory_namespace = "evaluation/quality-v3"
max_tool_rounds = 2

[eval.judges.quality]
agent = "quality_evaluator"
timeout_seconds = 30
max_attempts = 2
allowed_tools = ["policy_lookup"]
tool_policy = "read_only"
allow_self_evaluation = false
allow_side_effects = false
hitl_mode = "suspend"
max_input_tokens = 12000
max_cost_usd = 0.10
rubric = "Pass only when every required policy statement is supported."
rubric_version = "3"
judge_version = "2"
```

The application still constructs and registers `quality_evaluator`, including
its provider, tool implementations, MCP lifecycle, memory backend, and
retrieval source. `AgentJudge.from_config()` resolves that registered agent and
applies the narrower evaluation policy.

```python
from praval import Agent
from praval.eval import AgentJudge

evaluator = Agent(
    "quality_evaluator",
    provider="openai",
    model="gpt-5.4-mini",
    persist_state=False,
    system_message="Judge only from supplied evidence.",
)

# Register policy_lookup as a ToolSpec with read_only metadata, then register
# the agent in the normal Praval registry used by the application.
judge = AgentJudge.from_config(
    "quality",
    config,
    rubric=config.eval.judges["quality"].rubric,
    rubric_version=config.eval.judges["quality"].rubric_version,
    judge_version=config.eval.judges["quality"].judge_version,
)
```

## Capability ownership

The evaluator's `Agent` owns its model runtime, registered tools, MCP clients,
memory/retrieval configuration, HITL service, and telemetry. `AgentJudge` owns
only the evaluation envelope, rubric, strict result schema, temporary history
isolation, tool allowlist, timeout, retries, token bound, and cost bound.

MCP tools are async-only and must carry read-only or `evaluation_safe`
metadata before they can enter the allowlist. Praval does not infer safety from
a tool name. Evaluator conversation history is restored after every case, and
`persist_state=True` is rejected. Close the evaluator and any MCP clients when
the runner is finished.

## Errors

Configuration failures raise `JudgeConfigurationError` before a judge call:
unknown profiles, missing registered agent, an unknown/unsafe tool, persistent
conversation state, or an invalid policy. Provider, timeout, invalid structured
output, token, cost, and self-evaluation failures become bounded
`JudgeResult(status="error")` records so a suite can finish and gates can make
an explicit decision.
