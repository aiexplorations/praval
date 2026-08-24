# Evaluation

Praval evaluation runs deterministic metrics and versioned model or agent
judges against immutable execution subjects. A subject contains one completed
`ExecutionObservation` for an agent or workflow, with bounded aggregated facts
for model calls, tools, retries, HITL, and Reef handoffs. Complete records live
in an `EvaluationStore`; OpenTelemetry receives correlated summaries and
trends, not the authoritative dataset.

Evaluation does not query Jaeger, Tempo, or another tracing backend. The target
runtime hands the same provider-neutral observation independently to the
configured observation recorder and to the evaluation runner. This preserves
the dependency boundary: `praval.observability` never imports `praval.eval`.

```{toctree}
:maxdepth: 2

quickstart
configuration
patterns
evaluator-agents
evaluator-flow
direct-model-judges
datasets-suites
agents-workflows
metrics-ragas
gates-ci
online
stores-retention
telemetry
privacy-cost-security
production-recipes
troubleshooting
api-reference
```

## Choose an evaluation mechanism

| Question | Mechanism | Model call |
|---|---|---|
| Did execution terminate successfully? | `TerminalSuccessMetric` | No |
| Does structured output exactly match the reference? | `ExactMatchMetric` | No |
| Were the expected tools selected in order? | `ToolCallMatchMetric` | No |
| Does a custom deterministic rule apply? | `praval.eval.metrics` plugin | Usually no |
| Does semantic quality require a rubric? | `ModelJudge` | Yes |
| Does evaluation require safe tools or retrieval? | `AgentJudge` | Yes |
| Is the task RAG or agentic quality? | Optional RAGAS metric | Often |

Start with deterministic checks. Add model judgment only for qualities that
cannot be asserted reliably, and use an evaluator agent only when the judge
genuinely needs its own tools, retrieval, memory, or HITL policy.

## Record boundary

```text
case -> target agent/workflow -> one immutable ExecutionObservation
                              -> EvaluationSubject
                              -> metrics and judges
                              -> gates and terminal EvaluationResult
                              -> EvaluationStore (authoritative)
                              -> linked OTel summaries (operational)
```

Prompts, responses, reference contexts, and judge evidence remain ephemeral or
content-addressed by default. Metadata-only records carry identities, hashes,
sizes, status, usage, cost, and bounded error types.

## Executed evidence

The examples under `examples/evaluation/` are credential-free and use only
public APIs. Their positive, boundary, failure, and safety behavior is covered
by `tests/eval/`, and the release suite runs them from the exact built wheel.
PostgreSQL, Collector, RAGAS, RabbitMQ, privacy, performance, and shutdown
contracts are separate explicit release gates.

| Tutorial/recipe | Guide or executable | Executed evidence |
|---|---|---|
| Local deterministic suite | [Quickstart](quickstart.md) | `examples/evaluation/000_quickstart.py` |
| Paired target/evaluator agents | [Patterns](patterns.md) | `examples/evaluation/001_paired_agents.py` |
| Workflow handoffs and tools | [Agent and workflow evaluation](agents-workflows.md) | `examples/evaluation/002_workflow_evaluation.py` |
| Deterministic, model, and agent mechanisms | [Decision table](patterns.md#decision-table) | `tests/eval/test_runner.py`, `tests/eval/test_judges.py` |
| JSONL selection and reproducibility | [Datasets](datasets-suites.md) | `tests/eval/test_dataset.py` |
| CI gate and baseline | [Gates and CI](gates-ci.md) | `tests/eval/test_cli.py`, `tests/eval/test_gates.py` |
| PostgreSQL records and jobs | [Stores](stores-retention.md) | `tests/eval/test_postgres_store.py` |
| RAGAS and plugin extension | [Metrics and RAGAS](metrics-ragas.md) | `scripts/smoke_eval_ragas.py`, `tests/eval/test_ragas.py` |
| Sampled online evaluation | [Online evaluation](online.md) | `tests/eval/test_online.py` |
| Privacy, cost, and failures | [Privacy and security](privacy-cost-security.md) | `tests/eval/test_models.py`, `tests/eval/test_judges.py` |
| Trace/result correlation | [Evaluation telemetry](telemetry.md) | `tests/observability/test_signals.py` |

The [production recipes](production-recipes.md) turn this matrix into complete
install, configuration, run, inspection, failure, cleanup, and next-step
procedures.

The exact-wheel smoke executes all three credential-free examples. Real
PostgreSQL and RAGAS tests run separately because tracing and service lifecycle
are part of their contracts.
