# Evaluation API reference

The supported evaluation surface is `praval.eval`. It is provider-neutral and
available in the base wheel. PostgreSQL methods require the storage dependency;
`praval.eval.ragas` is optional and intentionally not re-exported.

## Datasets and immutable records

- `EvalCase`, `EvalSuite`, `LoadedEvalCase`, `LoadedEvalSuite`, and
  `load_jsonl_suite()` define bounded datasets.
- `EvaluationRun`, `EvaluationSubject`, `MetricResult`, `JudgeResult`,
  `GateResult`, and `EvaluationResult` are immutable persisted records.
- `EvaluationBaseline`, `EvaluationJob`, and `EvaluationAttempt` cover explicit
  regression and durable online lifecycle.
- Status/operator/aggregation enums make serialized decisions stable.

Validation errors are ordinary Pydantic `ValueError` failures.
`EvalDatasetError` adds file/line context without exposing unrelated data.

## Execution and judges

- `EvalRunner` executes a `LoadedEvalSuite` with bounded concurrency.
- `EvaluationTarget` and `TargetResult` define the async target seam.
- `AgentEvaluationTarget` adapts a non-persistent ordinary `Agent` and enforces
  one observation per case.
- `Judge`, `JudgeContext`, `ModelJudge`, and `AgentJudge` define strict
  evaluator composition.
- `EvaluationExecutionError`, `JudgeConfigurationError`, and
  `JudgeResponseError` report invalid execution or configuration. Judge runtime
  failures normally become error results.

## Metrics, gates, and plugins

- `Metric`, `ExactMatchMetric`, `TerminalSuccessMetric`, and
  `ToolCallMatchMetric` are asynchronous provider-free metrics.
- `builtin_metrics()`, `discover_metric_plugins()`, and `available_metrics()`
  expose deterministic plugin discovery under `METRIC_ENTRY_POINT_GROUP`.
- `MetricPluginError` reports malformed, duplicate, or conflicting plugins.
- `Gate`, `evaluate_gate()`, `compare_evaluation_runs()`, and
  `promote_evaluation_baseline()` implement explicit quality policy.
- `GateEvaluationError`, `MetricComparison`, and `RunComparison` describe
  invalid or completed comparisons.

## Stores

`EvaluationStore` is the async structural contract. Both
`SQLiteEvaluationStore` and `PostgresEvaluationStore` provide migrations,
immutable idempotent writes, queries, baselines, jobs, leases, retries, and
attempts. Call `migrate()` before use and `close()` at shutdown.
`EvaluationStoreError` is the base persistence error;
`EvaluationConflictError` means an identity collision with different data.

## Online evaluation

- `trace_sampled()` makes a deterministic decision from a 128-bit trace ID.
- `OnlineEvaluationProcessor` and `OnlineContextLoader` are async application
  seams.
- `OnlineSubjectEvaluator` composes configured public judges and metrics.
- `OnlineEvaluationService.start()`, `.record()`, `.stats()`, and
  `.shutdown()` own the bounded scheduler/worker lifecycle.
- `OnlineEvaluationStats` contains counters and queue metadata only.
- `evaluation_call_scope()` and `is_evaluation_call()` prevent recursive
  sampled evaluation.

For full signatures, parameter types, defaults, return values, and source
docstrings, see the generated `praval.eval` modules under {doc}`../api/index`.
