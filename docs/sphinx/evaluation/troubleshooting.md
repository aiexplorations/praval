# Troubleshooting

## Target agent is not registered

`praval eval run` imports only modules passed with `--module`. Pass the module
that constructs/registers `agent:<name>`, and ensure the suite target matches
the registered identity exactly.

## Unknown judge or metric

Judge names must exist under `[eval.judges]`. Plugin metrics must be installed
under the `praval.eval.metrics` entry-point group; RAGAS metrics require
`praval[eval-ragas]` plus configured Praval model/embedding profiles. Run
`praval doctor --json` to inspect installed evaluation dependencies without
printing credentials.

## Invalid judge output

The judge must return the strict structured result. Passed/failed responses
need finite score and non-empty label. Invalid JSON/schema, timeout, token/cost
limit, and provider failure become bounded error results. Inspect `error_type`,
attempt count, usage, cost, and the linked judge span; raw exception content is
intentionally absent.

## RAGAS metric reports missing input

Check {doc}`metrics-ragas` for required fields. Praval validates them before a
paid call. `reference_contexts`, expected output, and expected tools must be in
the loaded JSONL case, not reconstructed from tracing attributes.

## Gate failed

Distinguish a valid low score from missing/error results. Check metric/judge
version, selected case count, aggregation, threshold, and baseline direction.
Promotion is explicit; a new run is never made baseline automatically.

## Store conflict or outage

An `EvaluationConflictError` means a stable identity was reused with different
immutable data. Fix versioning or choose a new run ID. For PostgreSQL, verify
the named DSN environment variable, migration access, and pool connectivity.
Online queue drops during an outage are explicit and cannot be reconstructed
unless the application supplies a stronger upstream durable buffer.

## Online jobs retry or dead-letter

Inspect job status, bounded `error_type`, attempt records, lease expiry, queue
depth, drop/failure counters, and post-hoc span. Common errors are
`ProcessorTimeout`, `SubjectMissing`, provider error types, and lease recovery
after process shutdown. Increase bounds only after diagnosing cost and
capacity; never move judge work onto the request path.

## Shutdown hangs

Call `OnlineEvaluationService.shutdown()` and observability shutdown from the
application's graceful termination path. Both make bounded attempts. Close
application-owned evaluator agents, MCP clients, stores, and providers after
workers stop.
