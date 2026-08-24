# Praval v0.8.3: production observability and evaluation

## Background

Praval v0.8.2 includes a custom tracing package, but it does not provide a dependable OpenTelemetry implementation for production services. The configured OTLP endpoint is not connected to a live exporter. Trace context does not follow the complete Spore wire contract. Instrumentation misses important runtime paths, and the package has no working metrics or logs pipeline. The local SQLite trace file also does not solve aggregation for multi-container deployments.

Praval evaluation was discussed in an earlier draft under `praval.evaluation`, but it was never implemented or shipped. That draft included useful ideas about agent, workflow, and LLM-as-a-judge evaluation, but it also included leaderboards, marketplaces, reports, and other work that is not needed for this release.

Praval-based agents need both capabilities before they can be operated with confidence in production. Observability explains what an agent system did, where time and tokens were spent, and how failures moved through a workflow. Evaluation measures whether the result was useful, correct, grounded, safe, and better or worse than a baseline. Both features need the same agent, model, tool, workflow, and trace identities.

Version 0.8.3 will therefore be a production readiness release. It will replace the current observability internals and introduce a focused `praval.eval` module. Although the version number is a patch release, the implementation and release checks must be treated as a major platform change.

## Release plan

Version 0.8.3 will deliver two main changes. They will be implemented in order: finish and certify `praval.observability`, freeze its shared observation contracts, and then build `praval.eval` on that foundation.

### 1. `praval.observability`

- Replace the custom tracer and hand-built exporter with the official OpenTelemetry API, SDK, processors, propagators, and OTLP exporters.
- Support traces, metrics, and logs through live, batched OTLP export.
- Instrument agents, workflows, ModelRuntime, providers, tools, Reef, Spores, memory, storage, MCP, HITL, embeddings, transcription, speech, and streaming.
- Propagate W3C trace context through in-memory and RabbitMQ Reef delivery and through secure Spores.
- Add service identity, resource attributes, parent-based sampling, bounded queues, flush and shutdown behavior, privacy controls, and local retention by age and count.
- Keep SQLite as an optional local diagnostic exporter. It will not be the production export queue or an aggregation service.

### 2. `praval.eval`

- Add evaluation runners, judge profiles, durable stores, regression gates, and CLI support.
- Allow a configured Praval agent to evaluate another agent or a complete multi-agent workflow.
- Support direct foundation-model judges and agent judges that can use Praval tools and retrieval.
- Support offline datasets and CI gates, plus asynchronous and explicitly enabled sampled production evaluation.
- Add an optional RAGAS plugin for RAG, agent-goal, topic, and tool-call metrics.
- Persist full evaluation records to SQLite or PostgreSQL and publish correlated OpenTelemetry summaries.

### Shared release foundations

- Add a typed `praval.toml` configuration for applications, model profiles, agents, observability, evaluator models, suites, stores, and gates.
- Raise the minimum supported Python version from 3.9 to 3.10 so Praval can use the current OpenTelemetry Python packages.
- Make metadata-only capture the default. Prompt, response, context, tool, media, and judge content will require explicit opt-in.
- Publish top-level Observability and Evaluation documentation areas on the Praval site with tested tutorials, production recipes, troubleshooting, API references, and migration guidance.
- Validate the exact v0.8.3 wheel, documented imports, real OTLP collector output, multi-container storage, shutdown behavior, and measured runtime overhead before release.

The standards baseline for this work is the official [OpenTelemetry Python API and SDK](https://opentelemetry.io/docs/languages/python/), the [OpenTelemetry GenAI conventions](https://github.com/open-telemetry/semantic-conventions-genai), the standard [`gen_ai.evaluation.result` event](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-events.md), and the documented [RAGAS metric catalog](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/).

## Foundation and dependency order

### Architecture decision

`praval.observability` is the technical foundation for `praval.eval`. Observability establishes execution boundaries, service and agent identities, trace and workflow correlation, model and tool usage, error capture, and the normalized observation of an agent or workflow run. Evaluation uses those facts to decide what happened and how well it performed.

The two features remain separate products. Observability must work without evaluation, and evaluation must work when no OpenTelemetry SDK or exporter is active. The shared contract between them is a provider-neutral `ExecutionObservation`, not an exported trace and not a query against an observability backend.

This decision has the following dependency direction:

```text
Praval runtime, models, and configuration
                  |
                  v
       ExecutionObservation contract
                  |
                  v
         praval.observability
                  |
                  v
        praval.eval offline core
                  |
                  v
       RAGAS and agent judges
                  |
                  v
      sampled online evaluation
```

The package rules are:

- Runtime boundaries produce `ExecutionObservation` records through a small internal recorder interface.
- `praval.observability` converts observations and runtime events into OpenTelemetry spans, metrics, and logs.
- `praval.eval` consumes observations directly for subjects, judges, persistence, and gates.
- `praval.eval` may call the public observability facade to add correlation and evaluation-result events.
- `praval.observability` must never import `praval.eval`.
- Neither module may depend on data being available from an external collector or vendor backend.
- Disabling OTel export must not disable offline evaluation or evaluation persistence.

### Why observability comes first

Building evaluation first would force the evaluation runner to create its own agent, workflow, model, tool, and usage capture. Observability would later need to replace or duplicate that capture. Building both modules independently would also create two definitions of a run and increase the chance of circular imports.

The observability-first path creates each execution fact once. It also lets the team prove async context isolation, distributed Spore propagation, privacy filtering, lifecycle ownership, and bounded export before judge calls and evaluation workers add more concurrency and cost.

### Context management strategy

Development will be serial. Finish the observability workstream and freeze its contracts before starting the evaluation workstream. Do not keep both feature implementations active in one development context.

Each work package below should fit into one focused development task or pull request. At the end of each package, record:

- The public and internal contracts added or changed.
- The architecture invariants that the next package must preserve.
- The tests and commands that prove completion.
- Any known limitations or deferred work.
- The exact next package and the files or APIs it is allowed to change.

The next task should begin from this handoff rather than from the full history of v0.8.3. Cross-workstream changes after the observability freeze require an explicit change to the shared observation contract and its compatibility tests.

For each new development task, load only:

1. The architecture decision and package rules in this section.
2. The current O-series or E-series work package.
3. The immediately preceding package handoff.
4. The public contracts and tests named by that handoff.

Do not carry implementation transcripts from earlier packages unless the handoff identifies an unresolved issue that requires them. O6 to E1 is a mandatory fresh-context boundary.

## Key change 1: `praval.observability`

### Intended outcome

A Praval application must be able to configure observability once and send correct, correlated telemetry to any OTLP-compatible collector. An application that already owns OpenTelemetry providers must be able to give those providers to Praval. Praval must not replace or shut down providers that it does not own.

Importing `praval` or `praval.observability` must have no side effects. Imports must not create files, start worker threads, configure global providers, or monkeypatch framework functions.

### Public API

The supported API will be:

```python
from praval.observability import (
    configure_observability,
    configure_tracing,
    force_flush,
    get_logger,
    get_meter,
    get_tracer,
    shutdown_observability,
)
```

- `configure_observability(...)` configures the selected signals, resources, processors, exporters, and propagators. It returns a handle that records which providers and workers Praval owns.
- `configure_tracing(service_name=..., otlp_endpoint=...)` is a supported trace-only convenience function.
- `get_tracer()`, `get_meter()`, and `get_logger()` return official OpenTelemetry API objects.
- `force_flush()` flushes owned trace, metric, and log pipelines with a bounded timeout.
- `shutdown_observability()` flushes and closes only resources owned by Praval.
- The old documented `get_metrics()` name will not be retained because an OpenTelemetry meter does not provide backend metric query results. Documentation will use `get_meter()` and explain how users query their observability backend.

If a user supplies an OTLP endpoint but Praval cannot attach exporters to the selected providers, configuration must fail with `PravalConfigurationError`. The endpoint must never be accepted and ignored.

### OpenTelemetry pipeline

- Add `opentelemetry-api` as a core dependency so Praval can emit telemetry into an application-owned provider.
- Put the OpenTelemetry SDK and OTLP exporters in the `observability` extra.
- Use `BatchSpanProcessor` for traces, periodic metric export, and batched log processing.
- Support OTLP HTTP/protobuf and gRPC through the official exporters.
- Use bounded queues, batch sizes, export timeouts, and retry limits.
- Send each completed span directly to configured processors. Do not write spans to SQLite and poll them for OTLP export.
- Treat exporter failures as operational events. They must be visible through logs and internal counters, but they must not change an agent result.

The implementation will follow the current OpenTelemetry GenAI conventions where they apply. It will pin the schema version used by v0.8.3 and hide development-stage convention changes behind Praval's instrumentation layer.

### Shared execution-observation spine

Define a versioned `ExecutionObservation` in the provider-neutral model layer. This model must not import the OpenTelemetry SDK or evaluation plugins.

An observation represents an agent invocation or complete workflow and contains bounded, structured facts such as:

- Observation, run, conversation, response, agent, and workflow identities.
- Start, end, duration, status, and structured error type.
- Provider, model, request mode, response identity, and token usage.
- Tool calls, retries, HITL decisions, Reef handoffs, and terminal outcome.
- Content hashes, sizes, and references under the active privacy policy.
- Current trace and span identifiers when a recording span exists.

Runtime boundaries will write observations through an `ObservationRecorder` protocol. The default recorder is a no-op. Observability provides a recorder that enriches and correlates telemetry. Eval can receive observations through the same protocol without parsing spans or importing exporter internals.

The observation schema will be frozen at the observability foundation checkpoint. Later compatible fields may be optional, but v0.8.3 evaluation work must not redefine the identity, timing, status, usage, tool, handoff, or privacy fields.

### Instrumentation coverage

Instrumentation will be placed directly at stable execution boundaries.

- **Agents and workflows:** Instrument agent invocation, decorated handlers, conversations, workflow start and completion, handoffs, and terminal outcomes.
- **Models:** Instrument ModelRuntime sync, async, streaming, structured output, embeddings, transcription, and speech paths.
- **Provider calls:** Record provider, model, attempts, retries, response identity, finish reason, token usage, time to first token, cancellation, timeout, and error type.
- **Tools:** Record tool selection, execution, result status, MCP calls, HITL suspension and resumption, approval decisions, and tool errors.
- **Reef and Spores:** Record send, broadcast, receive, request, response, delivery, and consumer handling.
- **Memory and storage:** Instrument the actual memory operations and storage `store`, `retrieve`, `query`, and `delete` methods.
- **Tool-round limit:** Replace the module constant `MAX_TOOL_ROUNDS` with `AgentConfig.max_tool_rounds`. Allow a request override and emit a structured `tool_round_limit_exceeded` event and error type.

Application exceptions must produce error spans and structured error logs, and then be raised to the caller. Instrumentation must not convert application failures into successful spans.

### Distributed trace context

Add `Spore.trace_context: Dict[str, str]` to the versioned Spore contract. Use the official propagator to inject and extract W3C `traceparent`, `tracestate`, and baggage.

The carrier must survive:

- JSON Spore serialization and deserialization.
- In-memory Reef delivery.
- RabbitMQ headers and body conversion.
- Request and response helpers.
- Secure Spore serialization and authentication.

The existing top-level `trace_id` may remain as a derived convenience field. It must not be used as the parent-context mechanism.

### Traces, metrics, and logs

Praval will emit:

- Invocation counts and duration for agents, workflows, models, and tools.
- Input, output, reasoning, and total token counts.
- Retry, error, timeout, cancellation, tool-limit, and telemetry-drop counts.
- Queue depth and export failure information.
- Evaluation run, case, failure, queue-drop, duration, and score measurements.

Metric dimensions must remain bounded. They may include service, environment, agent or workflow name, provider, model, operation, suite, metric, and status. They must not include prompts, arbitrary user tags, trace IDs, run IDs, or case IDs.

Structured logs will include service resources and trace and span correlation. Praval will emit logs for lifecycle changes, exporter failures, runtime failures, and evaluation results. The evaluation result record will follow the OpenTelemetry `gen_ai.evaluation.result` event shape.

### Local diagnostic storage

The optional SQLite trace store will be implemented as another batch exporter.

- Store resource, instrumentation scope, span, event, status, and link data.
- Enable WAL and a bounded busy timeout.
- Support `cleanup_traces(max_age_days=..., keep_last_n=...)`.
- Document it as a local, single-process diagnostic tool.
- Keep local trace viewing functions available only when the local exporter is enabled.

PostgreSQL or an observability backend will be used for production aggregation. Hosts must not share one SQLite file across containers.

### Privacy and security defaults

The default policy is metadata-only capture.

- Record identities, provider and model names, timings, usage, statuses, hashes, payload sizes, tool names, and schema versions.
- Do not record prompts, responses, tool arguments or results, retrieved documents, media, or judge evidence by default.
- Require explicit configuration before content can be captured.
- Apply allowlisted fields, redaction rules, and byte limits before content enters spans, logs, or local storage.
- Never place secrets or API keys in telemetry.

## Key change 2: `praval.eval`

### Intended outcome

`praval.eval` will provide one way to evaluate individual agents and complete Praval workflows. It will use Praval agents and model profiles as judges, accept metric plugins such as RAGAS, store detailed results, and emit summaries through `praval.observability`.

Praval will own evaluation orchestration. It will not reimplement every quality metric. Praval will define the contracts that runners, judges, stores, gates, and metric plugins share.

Evaluation implementation begins only after the observability foundation checkpoint passes. The runner will consume the frozen `ExecutionObservation` contract. It will not add a second runtime instrumentation system or reach into OpenTelemetry SDK and exporter objects.

### Public API

The initial API will be:

```python
from praval.eval import (
    AgentJudge,
    EvalCase,
    EvalRunner,
    EvalSuite,
    EvaluationResult,
    EvaluationRun,
    EvaluationStore,
    Gate,
    Judge,
    MetricResult,
    ModelJudge,
    run_eval,
)
```

- `EvalCase` describes one input, expected result, optional reference contexts, expected tool calls, metadata, and tags.
- `EvalSuite` selects cases, targets, judges, metric plugins, aggregations, and gates.
- `EvalRunner` runs the target, builds an immutable observation, invokes judges and plugins, applies gates, persists results, and emits telemetry.
- `AgentJudge` invokes an ordinary named Praval agent under a strict evaluation contract.
- `ModelJudge` invokes a configured foundation-model profile without requiring a separately registered agent.
- `EvaluationStore` defines the common async persistence and query contract.

Add these CLI commands:

- `praval eval run <suite>` runs a configured suite.
- `praval eval compare <run> --baseline <baseline>` compares a run with a stored baseline.
- `praval eval baseline set <suite> <run>` explicitly promotes a baseline.

CLI exit code `0` means the gates passed. Exit code `1` means a quality gate failed. Exit code `2` means configuration or evaluation execution failed.

### Agent and model judges

Judge profiles will be configured in `praval.toml`. A profile may reference a named agent or a model profile.

An agent judge is an ordinary Praval agent selected by a judge profile. Praval resolves and starts it through the same registry, `PravalApp`, model-profile, AgentConfig, ModelRuntime, provider, tool, MCP, memory, retrieval, HITL, retry, and observability paths used by project agents.

The evaluator keeps its own configured capabilities. It does not copy or inherit the target agent's tools, memory, credentials, or system prompt. A judge profile may narrow the evaluator's configured capabilities for a suite, but it must not grant a capability that the evaluator agent does not already have.

The runner supplies a versioned evaluation task containing the subject observation, rubric, criteria, references, and requested output schema. The evaluator may follow its normal agent flow and call its approved tools before returning a result.

The runner must require a versioned structured response that contains:

- Metric or criterion name.
- Numeric score when applicable.
- Low-cardinality label such as `pass`, `fail`, `relevant`, or `incorrect`.
- Explanation and bounded evidence.
- Error type when evaluation failed.
- Judge model, prompt hash, rubric version, usage, latency, and attempt count.

Judge prompts must keep the trusted rubric separate from candidate content. Candidate content must be handled as untrusted data. Direct model judges use temperature zero by default, a 60-second timeout, and two attempts.

Judge calls will be marked as evaluation work so online evaluation does not evaluate its own judge calls. Self-evaluation will be disabled unless the suite explicitly enables it.

### Evaluator-agent capability and safety contract

Evaluator-agent execution will follow these rules:

- **Normal runtime:** Use the same sync or async ModelRuntime, provider adapters, structured output, retry, cancellation, usage, and telemetry behavior as other agents.
- **Own tools:** Register the tools and MCP servers declared for the evaluator agent. Never expose the target agent's tools automatically.
- **Judge narrowing:** Allow a judge profile to set an allowlist from the evaluator's tools and to reduce tool rounds, time, tokens, concurrency, and cost.
- **Safe tools by default:** Evaluation jobs may use tools marked read-only or `evaluation_safe`. Tools with external side effects require `allow_side_effects = true` and an explicit HITL policy.
- **Isolated memory:** Give evaluator agents a dedicated memory namespace by default. Projects may attach approved knowledge bases and retrieval sources without mixing judge reasoning into the target agent's operational memory.
- **HITL behavior:** Offline evaluation may wait for intervention when configured. Online evaluation must move the job to `awaiting_intervention` or fail it according to policy. It must never suspend the original user request.
- **Content policy:** Apply the suite's content and redaction policy before the subject reaches the evaluator, its tools, memory, logs, or store.
- **No recursive evaluation:** Propagate an evaluation marker through model, tool, and agent calls and exclude those calls from online sampling.
- **Validated result:** Reject malformed judge output. Persist the attempt, error type, usage, and available evidence, then apply the suite's missing-metric policy.

The evaluator flow is:

```text
Target agent or workflow completes
              |
              v
ExecutionObservation is finalized
              |
              v
EvalRunner selects suite and judge profile
              |
              v
Configured evaluator agent runs through normal Praval flow
              |
              v
Approved tools, MCP, retrieval, memory, and HITL may participate
              |
              v
JudgeResult is validated, stored, gated, and correlated
```

### Agent and workflow evaluation

An agent case evaluates one response or conversation. A workflow case evaluates a correlated multi-agent run.

The workflow observation will contain bounded information about:

- Participating agents and their model profiles.
- Reef messages and handoffs.
- Model and tool calls.
- Retries, failures, HITL decisions, and tool-round limits.
- Final outcome and response identity.
- Usage, timing, and content references.

The runner must build this observation at the execution boundary. It must not depend on querying an arbitrary observability backend after the trace has been exported.

### LLM-as-a-judge and RAGAS

Ship RAGAS as an optional `eval-ragas` extra, pinned to the tested `0.4.x` line.

The adapter will:

- Map Praval cases and observations to the fields required by each RAGAS metric.
- Use configured Praval model and embedding profiles. It must not silently choose its own provider or model.
- Normalize RAGAS results into `MetricResult`.
- Keep RAGAS, LangChain, and datasets types out of the core public API.
- Validate required case fields before starting paid judge calls.

The first adapter will support the applicable RAGAS metrics for faithfulness, response relevancy, context precision and recall, factual correctness, semantic similarity, topic adherence, agent goal accuracy, and tool-call accuracy and F1.

Expose a `praval.eval.metrics` entry-point group so later packages can add DeepEval, human review, deterministic checks, or domain metrics without changing the runner.

### Offline, CI, and online evaluation

Offline suites will use versioned JSONL datasets with stable case IDs. They will support concurrency, deterministic case selection, stored baselines, and repeatable reports.

CI gates will support:

- Minimum and maximum thresholds.
- Pass-rate requirements.
- Mean, minimum, maximum, percentile, and count aggregations.
- Regression limits against an explicit stored baseline.
- Required metrics that fail the run if they are missing or errored.

Baselines must be promoted explicitly. Praval must not replace a baseline because the latest run passed.

Online evaluation will be disabled by default. When enabled, it will:

- Sample deterministically from the originating trace ID.
- Capture the evaluation subject at the agent or workflow boundary.
- Enqueue work without waiting for judge calls.
- Use bounded workers and queues.
- Use durable PostgreSQL jobs when PostgreSQL is configured.
- Retry at most three times with bounded backoff.
- Use idempotent result keys so at-least-once delivery does not create duplicate results.
- Record queue saturation, job loss, store failures, and judge failures.
- Never change or delay the user-facing agent result beyond the bounded enqueue cost.

### Evaluation persistence

Ship two stores behind the same async contract.

- `SQLiteEvaluationStore` supports local development and CI.
- `PostgresEvaluationStore` supports pooled connections, transactions, migrations, concurrent services, and `FOR UPDATE SKIP LOCKED` job leasing.

Persist schema-versioned records for runs, cases, observations, metric results, judge evidence, gates, baselines, jobs, and attempts. Enforce idempotency by run, case, evaluator, and metric identity.

Complete evaluation records are authoritative in `EvaluationStore`. OpenTelemetry carries correlated summaries and trends. Under the default content policy, stores keep hashes and references rather than raw prompts, responses, contexts, or judge evidence.

### Evaluation observability

Each suite run, case, judge call, metric plugin, and gate decision will have trace context.

- Synchronous evaluation spans will be children of the evaluated operation where possible.
- Post-hoc evaluation spans will link to the original agent or workflow span.
- Results will emit `gen_ai.evaluation.result` events with metric name, score, label, response identity, and error type.
- Aggregate counters and histograms will report run status, case status, duration, score, judge failure, and queue drops.
- Full explanations will remain in the evaluation store unless content capture is explicitly enabled for telemetry.

## Installation and dependencies

### Supported installation scopes

| Installation | Intended use | Included capability |
| --- | --- | --- |
| `pip install praval==0.8.3` | Library or application with host-owned OTel SDK | Core framework, `praval.eval`, SQLite evaluation store, and OpenTelemetry API instrumentation |
| `pip install "praval[observability]==0.8.3"` | Praval-managed telemetry pipelines | OpenTelemetry SDK and OTLP trace, metric, and log exporters |
| `pip install "praval[eval-ragas]==0.8.3"` | RAGAS quality metrics | RAGAS adapter and its tested dependency set |
| `pip install "praval[storage]==0.8.3"` | Production evaluation persistence | Existing storage dependencies, including PostgreSQL support |
| `pip install "praval[observability,eval-ragas,storage]==0.8.3"` | Recommended production deployment | Full telemetry, RAGAS evaluation, and PostgreSQL persistence |
| `pip install "praval[all]==0.8.3"` | Development and complete feature testing | All Praval optional features |

`praval.eval` itself remains importable from the base package. RAGAS remains optional because it has a large dependency set. PostgreSQL support remains in the storage extra. SQLite uses the Python standard library.

### Dependency policy

- Require Python 3.10 to 3.14.
- Use a compatible OpenTelemetry package family and pin all API, SDK, semantic-convention, and exporter packages to the same tested minor line.
- Start with OpenTelemetry 1.44.x for v0.8.3 and review later minor updates through contract tests.
- OpenTelemetry Python logs are still marked as a development signal. Keep log integration behind Praval's public facade and protect it with exporter contract tests.
- Pin RAGAS to `>=0.4,<0.5` until its adapter contract is retested.
- Do not add an OpenTelemetry vendor SDK to Praval.
- Do not add a direct dependency on an observability backend. Production applications should send OTLP to an OpenTelemetry Collector.
- Keep provider credentials, OTLP headers, and database credentials in environment variables or a secret manager.

## Configuration

Add a typed `PravalConfig` loaded from `praval.toml`.

```toml
schema_version = 1

[app]
service_name = "vinn-agent-service"
service_version = "0.8.3"
deployment_environment = "production"

[models.default]
provider = "openai"
model = "gpt-5.4-mini"

[models.judge]
provider = "anthropic"
model = "claude-sonnet"
temperature = 0
max_output_tokens = 1200

[agents.researcher]
model = "default"
max_tool_rounds = 8

[agents.quality_critic]
model = "judge"
system_message = "Evaluate agent outputs against the supplied rubric."
tools = ["search_docs", "lookup_policy"]
memory_enabled = true
memory_namespace = "evaluation/quality_critic"
max_tool_rounds = 4

[observability]
enabled = true
capture_content = false
sampling = "parentbased_traceidratio"
sample_ratio = 1.0

[observability.otlp]
endpoint = "http://otel-collector:4318"
protocol = "http/protobuf"
traces = true
metrics = true
logs = true

[observability.local]
enabled = false
path = "~/.praval/telemetry.db"
max_traces = 10000
max_age_days = 7

[eval]
enabled = true
store = "postgres"
offline_concurrency = 4

[eval.online]
enabled = false
sample_ratio = 0.01
queue_capacity = 1000
workers = 2
max_attempts = 3

[eval.stores.postgres]
dsn_env = "PRAVAL_EVAL_DATABASE_URL"

[eval.judges.quality]
agent = "quality_critic"
timeout_seconds = 60
max_attempts = 2
allow_self_evaluation = false
allowed_tools = ["search_docs", "lookup_policy"]
tool_policy = "evaluation_safe"
allow_side_effects = false
hitl_mode = "suspend"
max_input_tokens = 16000
max_cost_usd = 0.25

[eval.suites.research_quality]
dataset = "evals/research_quality.jsonl"
target = "agent:researcher"
judges = ["quality"]
metrics = [
  "ragas.faithfulness",
  "ragas.response_relevancy",
  "ragas.context_precision",
]

[[eval.suites.research_quality.gates]]
metric = "ragas.faithfulness"
aggregation = "mean"
operator = ">="
threshold = 0.85
```

Configuration precedence will be:

- For application settings, explicit API values override environment variables. Environment variables override `praval.toml`, and file values override defaults.
- For an agent, constructor or decorator arguments override `[agents.<name>]`. The agent section overrides its model profile. The model profile overrides `PRAVAL_DEFAULT_*` and provider defaults.
- Standard `OTEL_*` environment variables override matching exporter settings in the file.
- Secret fields use environment-variable references. They must not contain literal secret values in committed configuration.

Configuration loading must validate unknown fields, incompatible settings, missing extras, invalid sample rates, missing service names, store requirements, judge references, judge tool allowlists, memory namespaces, HITL modes, and evaluator time, token, cost, retry, and tool-round budgets before starting workers or paid model calls.

## Implementation plan

Implementation is divided into two serial workstreams. Complete and freeze Workstream A before opening Workstream B. Each package has a narrow scope and an exit gate so development can move to a fresh context after the package is complete.

### Workstream A: build `praval.observability` first

#### O1. Configuration, dependencies, and lifecycle

- Raise the Python floor and update package metadata and the CI matrix.
- Add `PravalConfig`, `praval.toml` discovery, validation, environment overrides, and model-profile resolution.
- Add the observability dependency extra and diagnostics to `praval doctor`.
- Define application-owned and Praval-owned tracer, meter, and logger provider behavior.
- Add the public observability API with no import-time side effects.
- Define bounded flush and shutdown ownership.

Exit gate:

- Exact-wheel core and observability-extra installation tests pass.
- Configuration precedence, invalid configuration, ownership, repeated setup, flush, and shutdown tests pass.
- Importing Praval creates no providers, files, threads, or network activity.

#### O2. Execution-observation contract and trace core

- Add the versioned `ExecutionObservation` model and `ObservationRecorder` protocol.
- Define stable identity, timing, status, usage, tool, handoff, content-reference, and privacy fields.
- Replace custom spans and context management with the official OpenTelemetry API.
- Add service resources, parent-based sampling, exception recording, and async-safe context handling.
- Add compatibility mappings for supported v0.8.2 tracer names without retaining a second tracer implementation.

Exit gate:

- Observation schema and serialization contract tests pass.
- In-memory trace tests prove correct parentage, error status, sampling, and async task isolation.
- The no-op recorder and no-SDK path work without optional observability dependencies.

#### O3. Agent and runtime instrumentation

- Instrument Agent, decorated handlers, workflow boundaries, ModelRuntime, providers, tools, MCP, HITL, memory, storage, embeddings, transcription, speech, and streaming.
- Produce observations and telemetry from the same runtime facts.
- Capture usage, retries, time to first token, finish state, cancellation, errors, and tool results under the privacy policy.
- Replace `MAX_TOOL_ROUNDS` with typed agent and request configuration and a structured limit event.

Exit gate:

- Sync, async, streaming, tool, media, HITL, retry, cancellation, and provider-error contract tests pass.
- Observations and spans agree on identity, status, usage, and timing.
- Instrumentation does not swallow or rewrite application errors.

#### O4. Reef and Spore propagation

- Add the versioned W3C trace carrier to Spore.
- Inject and extract context through JSON, in-memory Reef, RabbitMQ, request and response helpers, and secure Spore paths.
- Record producer, delivery, consumer, handoff, and workflow relationships.
- Preserve sampling decisions and authenticated carrier data across process boundaries.

Exit gate:

- In-memory and RabbitMQ black-box tests prove the same trace and correct parent spans.
- Concurrent messages do not leak context.
- Secure Spore tests prove that the context carrier survives and is covered by authentication.

#### O5. Metrics, logs, exporters, and local diagnostics

- Add bounded OpenTelemetry metric instruments and correlated structured logs.
- Add live batched OTLP HTTP/protobuf and gRPC exporters.
- Convert SQLite trace persistence into an optional batch exporter.
- Add count-based and age-based local retention.
- Add privacy filtering, redaction, truncation, exporter health, queue bounds, and drop counters.

Exit gate:

- A real collector receives valid traces, metrics, and logs.
- Local retention, collector downtime, queue overflow, retry, and shutdown tests pass.
- Default metadata-only capture does not leak content or secrets.
- Observability overhead stays within the release thresholds.

#### O6. Observability certification and contract freeze

- Complete the top-level Observability documentation area and its API reference from the exact public API.
- Add and execute the local development, host-owned SDK, Praval-owned SDK, Collector, multi-container, RabbitMQ, privacy, failure, and shutdown tutorials.
- Update API manifests, optional-extra diagnostics, release notes, and the v0.8.2 migration guide.
- Run the exact-wheel observability certification suite.
- Freeze `ExecutionObservation`, `ObservationRecorder`, identity, correlation, privacy, and lifecycle contracts for the rest of v0.8.3.
- Write the eval handoff with schemas, supported observation fields, test fixtures, helper APIs, limitations, and the commands that prove the checkpoint.

Observability foundation checkpoint:

- Packages O1 to O6 and all their exit gates are complete.
- The real-collector and distributed-context suites pass.
- The exact wheel and documented imports pass.
- No dead endpoint, signal, provider, or storage configuration remains.
- The observation schema has a version and compatibility tests.
- Workstream B can consume observations without importing OpenTelemetry SDK internals.

Do not start `praval.eval` implementation until this checkpoint passes. If eval later exposes a missing execution fact, add it as an optional, backward-compatible observation field with observability contract tests before using it.

### Workstream B: build `praval.eval` after the observability freeze

#### E1. Evaluation contracts and stores

- Add evaluation runs, cases, subjects, metric results, judge results, gates, baselines, jobs, and attempt contracts.
- Map agent and workflow subjects from the frozen `ExecutionObservation` schema.
- Add the async `EvaluationStore` interface.
- Add SQLite and PostgreSQL stores, migrations, transactions, queries, and idempotency.

Exit gate:

- Evaluation records round-trip without an active OTel SDK.
- SQLite and PostgreSQL pass the same store contract suite.
- Migrations, concurrent writes, queries, and duplicate result handling pass.

#### E2. Offline runner and judges

- Add JSONL suite loading, case selection, concurrency, aggregation, and result persistence.
- Add `AgentJudge` and `ModelJudge` using configured Praval agents and model profiles.
- Add strict judge response schemas, rubric and prompt versioning, recursion prevention, retries, timeouts, usage, and cost recording.
- Emit correlation through the public observability facade when it is active.

Exit gate:

- Offline agent and workflow suites run with fake providers and deterministic judges.
- Judge failures, timeouts, invalid schemas, and self-evaluation rules pass.
- Persisted results and emitted evaluation events refer to the same observation and response identities.

#### E3. Workflow evaluation and regression gates

- Build bounded workflow subjects from observations, handoffs, tool calls, retries, failures, and terminal outcomes.
- Add thresholds, pass rates, aggregations, required metrics, baseline comparison, and explicit baseline promotion.
- Add `praval eval run`, `compare`, and `baseline set` with documented exit codes.

Exit gate:

- Single-agent and multi-agent workflow gates pass against fixed fixtures.
- Missing metrics, failed judges, regressions, and explicit baseline promotion behave as documented.
- CI can use the exact wheel and CLI without internal imports.

#### E4. RAGAS and metric plugins

- Add the `praval.eval.metrics` plugin contract and discovery.
- Add the optional RAGAS adapter and Praval ModelRuntime and embedding bridges.
- Validate required case fields before judge calls.
- Normalize supported RAGAS results and failures into `MetricResult`.
- Add a small reference custom metric plugin to prove the public extension contract.

Exit gate:

- The base package imports and runs eval without RAGAS installed.
- The `eval-ragas` exact wheel runs supported metrics with configured models.
- RAGAS, LangChain, and datasets types do not appear in the core public API.

#### E5. Sampled online evaluation

- Add deterministic trace-based sampling and bounded subject capture.
- Add request-path enqueue isolation, durable PostgreSQL jobs, leasing, retries, idempotency, and worker lifecycle.
- Add post-hoc span links, evaluation events, score metrics, queue depth, drops, and failure telemetry.
- Keep online evaluation disabled by default.

Exit gate:

- No judge network call occurs on the user request path.
- Queue saturation, worker restart, PostgreSQL downtime, duplicate delivery, retry exhaustion, and shutdown tests pass.
- Online scheduling and worker resource use remain within release bounds.

#### E6. Eval certification and final v0.8.3 release

- Complete the top-level Evaluation documentation area and its API reference.
- Add and execute tutorials for evaluator-agent flow and tools, local eval, CI, PostgreSQL, workflow judging, RAGAS, sampled-online evaluation, privacy, cost, failures, and observability correlation.
- Update installation scopes, API manifests, `praval doctor`, release notes, and the complete v0.8.3 migration guide.
- Remove claims for nonexistent `praval.explainability`, `praval.security`, and `get_metrics()` APIs.
- Run observability certification again to prove eval did not break the frozen foundation.
- Run the combined exact-wheel, Collector, PostgreSQL, privacy, performance, and shutdown release suites.

Exit gate:

- All observability and evaluation release gates pass together.
- Documentation claims match the wheel's exported symbols and optional extras.
- The final handoff records completed scope, operational requirements, known limitations, and post-v0.8.3 work.

## Testing and validation

### Functional acceptance tests

- Given the exact built wheel, all documented imports and examples must work under their stated installation extras.
- Given a static import-graph check, `praval.observability` must have no dependency on `praval.eval`, and the provider-neutral observation model must have no dependency on the OpenTelemetry SDK or metric plugins.
- Given OTel export disabled and no OpenTelemetry SDK installed, offline evaluation and evaluation persistence must still work through the no-op recorder and provider-neutral observations.
- Given an OTLP endpoint, traces, metrics, and logs must arrive at a real OpenTelemetry Collector without manual polling.
- Given application-owned providers, Praval must use them without replacement or shutdown.
- Given in-memory or RabbitMQ Reef delivery, the consumer span must inherit the correct W3C parent context.
- Given concurrent async agents, spans and evaluation context must not leak between tasks.
- Given retries, provider failures, cancellation, interrupted streams, HITL, or tool-round exhaustion, telemetry must show the correct structured error without swallowing the exception.
- Given local trace retention, age and count pruning must preserve complete newest traces.
- Given an offline evaluation suite, judge, RAGAS metrics, store records, OpenTelemetry events, and gate outcomes must agree.
- Given a judge profile that references a configured agent, the runner must use that agent's model, prompt, provider, tools, MCP, memory, retrieval, HITL, limits, and observability through the normal Praval runtime.
- Given a judge profile allowlist, it may narrow the evaluator's tools but must not grant target-agent tools or any capability absent from the evaluator configuration.
- Given an evaluator tool with side effects, the call must be rejected unless the tool and judge policy explicitly allow it. Required online HITL must suspend only the evaluation job.
- Given evaluator memory enabled, judge writes must use the configured isolated namespace and must not enter the target agent's operational memory.
- Given a workflow suite, the evaluator must receive the complete bounded workflow observation and link results to the original trace.
- Given SQLite and PostgreSQL stores, the same contract suite must pass for migrations, concurrent writes, queries, baselines, jobs, leases, retries, and idempotency.
- Given online queue saturation or a worker restart, the user-facing request must remain isolated and lost or retried work must be visible.
- Given metadata-only capture, prompts, responses, contexts, tool payloads, media, and judge evidence must not appear in telemetry or stored evaluation records.
- Given shutdown, Praval must make one bounded flush attempt for each owned signal and evaluation worker.

### Compatibility tests

- Test `configure_tracing()` and the documented top-level import sequence.
- Map legacy `ObservabilityConfig` field names to the new configuration with deprecation warnings.
- Map `get_tracer` and span-kind imports to official OpenTelemetry objects.
- Keep local viewing and cleanup functions when the local exporter is enabled.
- Deprecate `export_traces_to_otlp()`. It may flush a matching configured pipeline, but it must reject a new endpoint after configuration.

### Performance and reliability gates

- Test Python 3.10 to 3.14.
- Maintain at least 90 percent total coverage and 95 percent per-file coverage for new instrumentation, propagation, runner, store, and gate modules.
- Keep no-op instrumentation below 2 percent overhead in an end-to-end fake-agent benchmark.
- Keep enabled batched telemetry below 5 percent overhead with in-memory exporters, excluding network time.
- Keep online evaluation scheduling below 2 milliseconds at p95 and perform no judge network call on the request path.
- Set hard bounds for queues, batches, payloads, local storage, evaluator concurrency, retries, and flush time.
- Test parent-based sampling, queue overflow, collector downtime, PostgreSQL downtime, process restart, duplicate job delivery, and partial shutdown.
- Verify service identity, sampling, headers, resource attributes, and all three signal payloads from collector output rather than mocked configuration calls.

### Release gates

The release must not proceed unless:

- The exact wheel passes black-box installation and import tests for every documented extra.
- A real collector contract test receives valid traces, metrics, logs, and evaluation events.
- In-memory and RabbitMQ distributed traces have correct parent relationships.
- SQLite and PostgreSQL evaluation store contract tests pass.
- Privacy tests prove that default metadata-only capture does not leak content or credentials.
- Shutdown tests prove bounded flush behavior and no hanging non-daemon workers.
- Documentation API claims match the wheel's exported symbols.
- Both top-level documentation areas build without warnings, and their quickstarts, tutorials, configuration files, imports, and links pass against the exact wheel.
- Instrumentation coverage floors and measured overhead thresholds pass.
- No configured endpoint, store, evaluator, or signal is silently ignored.

## Production deployment recommendations

- Run an OpenTelemetry Collector next to or near Praval services. Send OTLP to the collector instead of configuring each vendor SDK inside Praval.
- Set a stable `service.name` for every deployable service. Also set service version and deployment environment.
- Use parent-based trace sampling. Make the sampling decision at the workflow root so one trace is either complete or consistently unsampled.
- Keep content capture off by default. Enable it only for a defined purpose and after redaction, retention, and access controls are in place.
- Use PostgreSQL for shared evaluation records and online evaluation jobs. Do not share SQLite files between containers.
- Keep online evaluation sampling low at first. Track judge cost, queue depth, result latency, and failure rate before increasing it.
- Use a separate judge model profile from the model under test when possible. Pin the judge prompt and rubric version so comparisons remain meaningful.
- Do not automatically promote baselines. Review a run and promote it explicitly.
- Alert on exporter failures, dropped telemetry, evaluation queue drops, judge failures, and tool-round-limit errors.
- Set timeouts and hard queue bounds. A telemetry or evaluation dependency must not block an agent request indefinitely.
- Call the Praval shutdown API during graceful service termination and allow enough time for bounded flushes.
- Restrict access to evaluation evidence because it may contain model outputs, retrieved material, or user data when content capture is enabled.

## Documentation and migration requirements

Documentation is part of the v0.8.3 product scope and release gate. Extend the existing Sphinx site and add Observability and Evaluation as top-level navigation areas. Do not hide these production features in one long guide or only generate API reference pages.

### Observability documentation area

Publish these pages:

1. **Overview and mental model:** Explain resources, traces, spans, metrics, logs, context propagation, collectors, backends, and Praval's ownership rules.
2. **Installation and five-minute quickstart:** Cover base-package instrumentation, the `observability` extra, host-owned providers, Praval-owned providers, and a local Collector.
3. **Configuration reference:** Document every `praval.toml`, `PRAVAL_*`, and supported `OTEL_*` field with type, default, precedence, validation, and secret handling.
4. **Instrumentation map:** Show which spans, metrics, logs, events, and attributes each Agent, ModelRuntime, provider, tool, Reef, Spore, memory, storage, MCP, HITL, and media operation emits.
5. **Distributed tracing:** Explain W3C context propagation through in-memory Reef, RabbitMQ, request and response helpers, and secure Spores.
6. **Signals:** Provide separate trace, metric, and log guides with naming, bounded dimensions, error behavior, and example backend queries.
7. **Collectors and deployment recipes:** Include Collector configurations for local development, Docker Compose, Kubernetes sidecar or gateway, headers, TLS, and common OTLP backends without adding vendor SDK dependencies.
8. **Sampling and performance:** Explain parent-based sampling, queue and batch tuning, expected overhead, dropped telemetry, and load testing.
9. **Privacy and security:** Document metadata-only defaults, content opt-in, redaction, size limits, secrets, access controls, and retention.
10. **Local diagnostics:** Explain SQLite setup, local viewing, count and age retention, single-process limits, and why it is not production aggregation.
11. **Lifecycle and troubleshooting:** Cover repeated configuration, provider ownership, exporter failures, collector downtime, flush, shutdown, missing spans, broken parentage, and async context problems.
12. **API reference and migration:** Document every public symbol, exception, parameter, return type, and the v0.8.2 replacement path.

### Evaluation documentation area

Publish these pages:

1. **Overview and relationship to observability:** Explain `ExecutionObservation`, evaluation records, telemetry summaries, and why eval does not query an external tracing backend.
2. **Installation and five-minute quickstart:** Cover base `praval.eval`, SQLite, the RAGAS extra, PostgreSQL, one small suite, one judge, and one gate.
3. **Defining evaluator agents:** Show that an evaluator is a normal configured Praval agent. Document model profiles, prompts, AgentConfig, registration, tools, MCP, memory, retrieval, HITL, retries, and observability.
4. **Evaluator flow and capability policy:** Explain the evaluation task envelope, normal agent loop, tool allowlists, `evaluation_safe`, side-effect controls, memory isolation, budgets, recursion prevention, and strict JudgeResult validation.
5. **Direct model judges:** Explain when to use `ModelJudge`, structured output, temperature, retries, timeouts, rubric versioning, and limitations compared with an agent judge.
6. **Cases, datasets, and suites:** Document JSONL schema, stable IDs, reference answers, contexts, expected tools, tags, selection, concurrency, and reproducibility.
7. **Agent and workflow evaluation:** Provide separate guides for a single agent, conversation, and correlated multi-agent workflow with handoffs and tools.
8. **Metrics and RAGAS:** Map supported metrics to required input fields, model and embedding profiles, common failure modes, cost, and plugin extension.
9. **Gates, baselines, and CI:** Document thresholds, aggregations, missing-metric policy, regression comparison, explicit baseline promotion, CLI commands, and exit codes.
10. **Online evaluation:** Explain opt-in sampling, durable jobs, workers, request isolation, retries, idempotency, queue saturation, HITL, and shutdown.
11. **Stores and retention:** Cover SQLite and PostgreSQL configuration, migrations, queries, content references, concurrency, and multi-container operation.
12. **Evaluation telemetry:** Show suite, case, judge, metric, and gate spans, `gen_ai.evaluation.result`, trace links, score metrics, and backend correlation.
13. **Cost, privacy, and security:** Cover evaluator-model cost, content transfer, untrusted candidate output, tool side effects, evidence access, redaction, and retention.
14. **Troubleshooting and API reference:** Cover missing judge agents, invalid output, tool failure, missing RAGAS fields, store errors, failed gates, queue drops, and all public classes and exceptions.

### End-to-end tutorials and production recipes

Ship executable examples for:

- A single agent with local traces, metrics, and logs.
- A multi-agent Reef workflow viewed as one distributed trace.
- Collector-based export from multiple containers with distinct service names.
- An evaluator agent with read-only tools, isolated memory, retrieval, and a strict rubric.
- A workflow evaluator that judges handoffs, tool choices, and final outcome.
- A RAGAS suite with configured Praval judge and embedding models.
- A CI regression gate with an explicit baseline.
- Sampled online evaluation backed by PostgreSQL and correlated with the original trace.
- Privacy-safe metadata-only deployment and an explicit redacted-content deployment.
- Failure exercises for collector downtime, judge timeout, queue saturation, and graceful shutdown.

Each tutorial must show prerequisites, installation command, complete `praval.toml`, code, expected output, telemetry or stored records to inspect, failure behavior, cleanup, and the next relevant guide.

### Documentation quality gates

- Build the Sphinx site with warnings treated as errors.
- Generate or validate the public API inventory from the exact wheel.
- Document every public function and class with types, defaults, return values, exceptions, lifecycle ownership, and optional dependency requirements.
- Execute all quickstarts, tutorials, and included configuration files against the exact wheel in CI.
- Check internal links, external standards links, navigation, code blocks, and referenced files.
- Maintain a documentation coverage manifest that maps each public API, configuration field, installation extra, error type, and feature claim to a page and an executable test.
- Test examples with content capture disabled and scan them for credentials and unsafe placeholder secrets.
- Publish versioned v0.8.3 pages and a clear v0.8.2 migration guide.
- Fail release CI when the site claims an import, option, signal, metric, or module that the wheel does not provide.

## Assumptions and exclusions

- This plan targets v0.8.3 only.
- Python 3.9 support ends with v0.8.2.
- Complete evaluation records are authoritative in `EvaluationStore`. Telemetry contains correlated summaries and trends.
- SQLite is for local development and CI. PostgreSQL is the supported multi-container evaluation store.
- Online evaluation remains disabled until a deployment explicitly configures sampling, a judge, a store, and a content policy.
- Application logs remain application-owned, but Praval emits its own correlated OpenTelemetry logs and can share the application's logger provider.
- Version 0.8.3 will not add leaderboards, a marketplace, certification, a hosted dashboard, synthetic dataset generation, `praval.explainability`, or `praval.security`.
