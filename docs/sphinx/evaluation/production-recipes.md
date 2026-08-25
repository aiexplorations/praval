# Evaluation production recipes

These recipes turn the reference pages into repeatable operating procedures.
Run them from a clean environment with the candidate wheel installed. Keep
provider keys, database DSNs, and OTLP headers in environment variables; none
of the checked-in examples requires a credential.

Every recipe states what to install, what configuration is complete for that
path, what to run, what to inspect, how failure appears, how to clean up, and
where to continue. The [executed evidence matrix](index.md#executed-evidence)
identifies the deterministic test for every external-service or failure path.

## 1. Local deterministic evaluation

Prerequisites
: Python 3.10 or newer and the exact `praval` wheel.

Install
: `python -m pip install ./praval-0.8.3-py3-none-any.whl`

Complete `praval.toml`
: No configuration is required. The example constructs a local SQLite store,
  deterministic target, metric, and gate through public APIs.

Run
: `python examples/evaluation/000_quickstart.py`

Expected output
: One completed run, one passing case, one passing gate, and one agent subject.

Inspect
: Open the temporary SQLite path printed or supplied by your wrapper and query
  the run, subject, metric result, gate result, and terminal result through
  `SQLiteEvaluationStore`.

Failure and cleanup
: A failed gate is a quality result, while invalid input or execution is an
  error. The example uses a temporary database; delete a persistent local file
  only after retaining any evidence you need.

Next
: [Five-minute quickstart](quickstart.md) and
  [datasets and suites](datasets-suites.md).

## 2. Paired target and evaluator agents

Prerequisites
: The base wheel. The checked-in example uses a fake provider and one
  read-only tool, so it needs no model credential.

Install
: `python -m pip install ./praval-0.8.3-py3-none-any.whl`

Complete `praval.toml`
: The example registers its deterministic provider and agents in code. For a
  deployed model-backed pair, use the complete target/evaluator configuration
  in [defining evaluator agents](evaluator-agents.md#configuration), including
  separate model profiles, memory namespaces, limits, and `allowed_tools`.

Run
: `python examples/evaluation/001_paired_agents.py`

Expected output
: One completed run and passing strict judge result. The target identity is
  `answerer`; the evaluator allowlist contains only `policy_lookup`.

Inspect
: Verify the `EvaluationSubject` contains one agent observation, the
  `JudgeResult` carries pinned judge/rubric versions, and no target tool or
  memory capability was inherited by the evaluator.

Failure and cleanup
: Invalid structured output, a missing evaluator, unsafe tools, self-evaluation,
  timeout, and budget exhaustion become bounded evaluation errors. Close the
  store and any application-owned agent resources.

Next
: [Recommended patterns](patterns.md) and
  [evaluator capability policy](evaluator-flow.md).

## 3. Workflow judging

Prerequisites
: The base wheel. A production workflow must propagate W3C context and expose
  one terminal workflow observation.

Install
: `python -m pip install ./praval-0.8.3-py3-none-any.whl`

Complete `praval.toml`
: No configuration is required for the deterministic example. Add normal
  application model/agent profiles when replacing its fixture target.

Run
: `python examples/evaluation/002_workflow_evaluation.py`

Expected output
: One workflow subject, one aggregated tool fact, one aggregated handoff fact,
  and passing terminal/tool metrics.

Inspect
: Compare the workflow observation ID with stored metric results. When
  observability is enabled, use its trace ID to inspect the child agent,
  provider, Reef delivery, and tool spans.

Failure and cleanup
: More than one workflow subject, a missing terminal outcome, escaped target
  failure, or mismatched expected tools remains visible and cannot silently
  pass. Shut down Reef and every backend the application owns.

Next
: [Agent and workflow evaluation](agents-workflows.md) and
  [distributed tracing](../observability/distributed-tracing.md).

## 4. CI regression gate and explicit baseline

Prerequisites
: A committed JSONL dataset, importable target module, writable evaluation
  store, and immutable candidate wheel.

Install
: `python -m pip install ./praval-0.8.3-py3-none-any.whl`

Complete `praval.toml`

```toml
[eval]
enabled = true
store = "sqlite"
offline_concurrency = 4

[eval.stores.sqlite]
path = ".artifacts/evaluation.db"

[eval.suites.answers]
dataset = "evaluation/answers.jsonl"
target = "answerer"
metrics = ["terminal_success", "exact_match"]

[[eval.suites.answers.gates]]
gate_id = "exact-match-pass-rate"
metric = "exact_match"
aggregation = "pass_rate"
operator = ">="
threshold = 0.95
required = true
```

Run

```bash
praval eval run answers --module myapp.agents --run-id "$CI_COMMIT_SHA" --json
praval eval compare "$CI_COMMIT_SHA" --suite answers \
  --max-regression 0.02 --direction higher_is_better --json
```

Expected output and inspect
: Save the JSON summary, evaluation database, dataset hash, wheel hash, and
  configuration as CI artifacts. Exit 0 passes, exit 1 is a quality decision,
  and exit 2 is an execution/configuration error.

Failure and cleanup
: Missing required metrics fail. Promote only a reviewed completed run with
  `praval eval baseline set answers APPROVED_RUN --json`; never promote from
  the candidate job automatically. Apply normal artifact retention afterward.

Next
: [Gates, baselines, and CI](gates-ci.md).

## 5. PostgreSQL shared store

Prerequisites
: Reachable PostgreSQL, a dedicated database role, TLS according to deployment
  policy, and the DSN stored in `PRAVAL_EVAL_DATABASE_URL`.

Install
: `python -m pip install "praval[storage]"`

Complete `praval.toml`

```toml
[eval]
enabled = true
store = "postgres"

[eval.stores.postgres]
dsn_env = "PRAVAL_EVAL_DATABASE_URL"
```

Run

```python
import asyncio
import os
from praval.eval import PostgresEvaluationStore

async def main() -> None:
    store = PostgresEvaluationStore(os.environ["PRAVAL_EVAL_DATABASE_URL"])
    try:
        await store.migrate()
        # Run EvalRunner or online workers with this store.
    finally:
        await store.close()

asyncio.run(main())
```

Expected output and inspect
: Concurrent migration succeeds, immutable replay is idempotent, and runs,
  results, baselines, jobs, leases, and attempts are queryable through the
  public store contract.

Failure and cleanup
: Connection failure raises a store error and never becomes a passing result.
  Stop workers before revoking the role; keep baseline referential integrity
  when applying record retention.

Next
: [Stores and retention](stores-retention.md).

## 6. RAGAS through Praval runtimes

Prerequisites
: The selected metrics' required case fields and explicitly configured judge
  and embedding profiles. The shipped smoke uses deterministic seams and no
  credential.

Install
: `python -m pip install "praval[eval-ragas]"`

Complete `praval.toml`

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

Run
: `python scripts/smoke_eval_ragas.py`

Expected output and inspect
: The reference plugin is discovered and faithfulness, semantic similarity,
  and tool-call accuracy return normalized passing `MetricResult` records.

Failure and cleanup
: Required fields are validated before paid calls. Timeout, provider failure,
  invalid structured response, or non-finite score becomes a bounded metric
  error. Close application-owned model and embedding resources.

Next
: [Metrics, plugins, and RAGAS](metrics-ragas.md).

## 7. Sampled online evaluation

Prerequisites
: PostgreSQL, an existing suite and evaluator policy, a content resolver, and
  graceful application lifecycle hooks.

Install
: `python -m pip install "praval[storage,observability]"`

Complete `praval.toml`

```toml
[eval]
enabled = true
store = "postgres"

[eval.stores.postgres]
dsn_env = "PRAVAL_EVAL_DATABASE_URL"

[eval.online]
enabled = true
sample_ratio = 0.01
queue_capacity = 1000
workers = 2
max_attempts = 3
max_enqueue_attempts = 3
lease_seconds = 180
job_timeout_seconds = 120
poll_interval_seconds = 0.1
retry_backoff_seconds = 0.25
shutdown_timeout_seconds = 5
max_subject_bytes = 262144
```

Run
: Construct `OnlineSubjectEvaluator`, then `OnlineEvaluationService`, call
  `await service.start()`, register `service.record` with the observation
  lifecycle, and call `await service.shutdown()` during graceful termination.

Expected output and inspect
: Selected traces enqueue without judge work on the request path. Inspect jobs,
  attempts, queue depth, drops, completion latency, and the post-hoc trace link.

Failure and cleanup
: Queue or store saturation is counted, expired leases recover, and exhausted
  work dead-letters. Shutdown makes one bounded drain attempt and releases
  interrupted leases. Stop workers before database maintenance.

Next
: [Sampled online evaluation](online.md) and
  [evaluation telemetry](telemetry.md).

## 8. Metadata-only and redacted-content deployment

Prerequisites
: An approved data classification, evidence access policy, and retention
  owner. Sampling does not replace these controls.

Install
: `python -m pip install "praval[observability]"`

Complete metadata-only `praval.toml`

```toml
[observability]
enabled = true
capture_content = false
content_allowlist = []

[eval]
enabled = true
store = "sqlite"

[eval.stores.sqlite]
path = ".praval/evaluation.db"
```

Run and inspect
: Execute the local example, then inspect stored JSON and exported telemetry.
  Only identities, hashes, sizes, status, usage, cost, and bounded error types
  should appear. Prompts, responses, contexts, evidence, payloads, exception
  messages, DSNs, headers, and credentials must be absent.

Redacted-content variant
: Redact in application code before constructing `JudgeContext`, write content
  to an application-owned protected store, and persist only a
  `ContentReference`. Do not put even redacted content in telemetry attributes.

Failure and cleanup
: Treat any discovered content or credential as a release-blocking privacy
  failure. Revoke exposed credentials, remove affected artifacts under the
  incident policy, and retain the metadata-only audit record when allowed.

Next
: [Cost, privacy, and security](privacy-cost-security.md) and
  [observability privacy](../observability/privacy-security.md).

## 9. Failure and graceful-shutdown exercise

Prerequisites
: A non-production environment with bounded test queues and temporary
  Collector/PostgreSQL services.

Install
: `python -m pip install "praval[storage,observability]"`

Complete `praval.toml`
: Use the online configuration above and the Collector configuration in
  [Collector deployment recipes](../observability/collectors.md). Keep all
  queue, retry, lease, timeout, and flush bounds explicit.

Run
: In order, stop the Collector, return an evaluator timeout, fill the online
  queue, interrupt a worker after lease, restart it, and finally terminate the
  application through its graceful-shutdown hook.

Expected output and inspect
: Export failures and drops are visible; user requests remain isolated; timed
  out work retries then dead-letters; an expired lease is reclaimed exactly
  once; owned providers and workers make bounded flush/drain attempts; host
  providers remain application-owned.

Failure and cleanup
: A hung process, swallowed target exception, unbounded retry, silent drop, or
  duplicate terminal record fails the exercise. Restart temporary services,
  drain or delete only the test queues, and retain the generated evidence.

Next
: [Troubleshooting](troubleshooting.md) and
  [observability lifecycle](../observability/lifecycle-troubleshooting.md).

## 10. Correlate an evaluation result with its trace

Prerequisites
: Observability enabled with an OTLP Collector and an evaluation run whose
  observation has trace and span identities.

Install
: `python -m pip install "praval[observability]"`

Complete `praval.toml`

```toml
[app]
service_name = "answer-service"
service_version = "0.8.3"
deployment_environment = "staging"

[observability]
enabled = true
sampling = "parentbased_traceidratio"
sample_ratio = 1.0
capture_content = false

[observability.otlp]
endpoint = "http://localhost:4318"
protocol = "http/protobuf"
traces = true
metrics = true
logs = true
```

Run and inspect
: Run an offline or online evaluation. Start with suite/run/subject IDs in the
  `EvaluationStore`, find the `gen_ai.evaluation.result` event or score metric,
  then follow the observation trace ID. Online worker spans use a link to the
  already-completed request span rather than becoming its child.

Failure and cleanup
: Missing telemetry does not erase authoritative store results. Diagnose
  Collector reachability and observability health without rerunning paid
  evaluation solely to recreate telemetry. Stop the temporary Collector and
  call bounded observability shutdown.

Next
: [Evaluation telemetry](telemetry.md) and
  [Observability signals](../observability/signals.md).
