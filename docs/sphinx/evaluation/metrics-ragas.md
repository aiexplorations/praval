# Metrics, plugins, and RAGAS

## Built-in deterministic metrics

| Metric | Required data | Meaning |
|---|---|---|
| `terminal_success` | subject observation | target ended successfully |
| `exact_match` | expected output and target output | canonical JSON equality |
| `tool_call_match` | expected tool calls and observed tool facts | exact ordered names |
| `reference.word_overlap` | expected output and target output | reference plugin example |

All metrics implement the public async `Metric.evaluate(JudgeContext)`
contract and return an immutable `MetricResult`. Discover installed plugins
through the `praval.eval.metrics` entry-point group. Names and versions must be
bounded and unique; plugins cannot shadow built-ins.

## RAGAS

Install the optional adapter:

```bash
python -m pip install "praval[eval-ragas]"
```

```toml
[models.ragas_judge]
provider = "openai"
model = "gpt-5.4-mini"
temperature = 0.0

[embeddings.ragas_embedding]
provider = "openai"
model = "text-embedding-3-small"

[eval.ragas]
model = "ragas_judge"
embedding = "ragas_embedding"
timeout_seconds = 60
strict_tool_order = true
```

Supported names are `ragas.faithfulness`, `ragas.response_relevancy`,
`ragas.context_precision`, `ragas.context_recall`,
`ragas.factual_correctness`, `ragas.semantic_similarity`,
`ragas.topic_adherence`, `ragas.agent_goal_accuracy`,
`ragas.tool_call_accuracy`, and `ragas.tool_call_f1`.

Faithfulness and context precision/recall need reference contexts. Response
relevancy and semantic similarity need configured embeddings. Tool metrics
need expected and observed tool calls. Agent-goal accuracy needs the task input
and terminal outcome; its reference variant also needs expected output. Praval
validates required fields before a paid call.

RAGAS model and embedding traffic uses configured Praval `ModelRuntime` and
`EmbeddingRuntime` seams inside the evaluation-call scope. It never chooses a
provider, model, credential, or embedding implicitly. Missing fields, timeout,
invalid scores, structured-response errors, and provider failures become
bounded `MetricResult` errors. RAGAS, LangChain, and datasets types do not
appear in the core `praval.eval` public API.
