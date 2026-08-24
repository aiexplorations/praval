# Gates, baselines, and CI

A `Gate` aggregates one named metric or judge result and compares the observed
value with a finite threshold. Supported aggregations are mean, minimum,
maximum, percentile, count, and pass rate. Operators are `>=`, `>`, `<=`, `<`,
and `==`.

Missing data never passes silently. A required gate without usable results is
failed; an optional one is skipped. Error results remain visible and do not
turn into zero scores. Persisted `GateResult` values contain the observed
value, threshold, sample size, and decision.

```bash
praval eval run answers --module myapp.agents --run-id ci-${GITHUB_SHA} --json
praval eval baseline set answers ci-approved-run --json
praval eval compare ci-${GITHUB_SHA} --suite answers \
  --max-regression 0.02 --direction higher_is_better --json
```

Baseline promotion is always explicit. It verifies that the source run exists,
belongs to the suite, completed successfully, and has a terminal result. The
store atomically deactivates the previous baseline and preserves history.

`praval eval compare` compares matched metric name/version pairs. It fails when
the current run regresses beyond the configured bound or lacks required
comparable data. Use direction `higher_is_better` or `lower_is_better`; do not
mix versions as if their scales were identical.

In CI, pin the wheel, dataset hash, suite configuration, provider/model
profiles, metric and judge versions, selection seed, and baseline run ID. Save
the JSON result and database/evidence manifest as artifacts. Exit code 1 is a
quality decision; exit code 2 is an execution/configuration failure and should
be diagnosed separately.
