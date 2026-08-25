# Agent and workflow evaluation

## Single agent

Wrap a non-persistent ordinary agent with `AgentEvaluationTarget`. Each case is
serialized canonically, executed through `Agent.agenerate()`, and must yield
exactly one agent observation plus a `ModelResponse`. Conversation history is
restored after the case.

```python
from praval import Agent
from praval.eval import AgentEvaluationTarget

target_agent = Agent(
    "answerer",
    provider="openai",
    model="gpt-5.4-mini",
    persist_state=False,
)
target = AgentEvaluationTarget(target_agent)
```

For a multi-turn conversation, model the whole conversation as one case and
execute it behind one custom `EvaluationTarget`. The returned output should be
the structured terminal outcome, and the observation should aggregate the
turn/model/tool facts. Do not reuse conversation state between cases.

## Correlated workflow

A workflow adapter implements the public async `EvaluationTarget` protocol and
returns `TargetResult` with `ObservationKind.WORKFLOW`. Keep one stable workflow
run ID, propagate W3C context through every Spore, aggregate handoff and tool
facts at the workflow root, and finish only when the terminal outcome is known.

Workflow metrics can check terminal status and expected tools. An evaluator
agent can judge handoff quality and the final outcome from the bounded workflow
observation and ephemeral output. Internal agent spans remain children of the
workflow trace for diagnosis; they are not separate evaluation cases.

Failures to produce exactly one subject, invalid target output, or an escaped
target exception become errored cases. They remain distinct from a valid
subject that a metric or judge marks as failed.
