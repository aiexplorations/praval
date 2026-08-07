# Frozen experiment protocol

Protocol version: 2

Freeze date: 2026-07-26

Target: Praval 0.8.1 exact published wheel

Version 2 replaces the pilot slow-consumer condition with a prefetch count of
one and a 20 ms handler delay, requires a positive broker queue-depth
observation, and adds accepted/rejected framework payload-boundary controls.
The first service run under version 1 is retained as an invalid pilot because
its consumer remained within the broker's concurrent prefetch window and did
not demonstrate queue buildup.

Canonical runs use the repetitions, warmups, timeouts, fixtures, services, and
validity checks in `experiments.toml`. Changing those fields after a canonical
run creates a new protocol version and invalidates direct numeric comparison
with the old run.

## Timing and samples

- Use `time.perf_counter_ns()` for elapsed time.
- Keep setup and connection time outside steady-state samples unless the metric
  is explicitly cold start.
- Keep every measured sample in JSONL.
- Keep process, topology, payload, agent count, provider, and model labels with
  each sample.
- Report count, mean, median, sample standard deviation, minimum, maximum,
  p50, p95, and p99 when the sample size supports them.
- Report deterministic percentile-bootstrap 95% intervals for means.
- Do not infer a positive behavioral or performance claim from one execution.

## Run classes

- Pilot and `--quick` runs debug feasibility. They are not paper evidence.
- Canonical offline runs execute all offline experiments without protocol
  changes.
- Canonical service runs use the pinned images in `services.compose.yml`.
- Comparative runs use separate locked environments and the shared controller
  fixture.
- Live runs record provider, requested model, returned model, time, calls,
  tokens, failures, and cost. They establish external validity only.

## Negative results

Failed, unsupported, expired, cancelled, timed-out, and missing-prerequisite
outcomes remain in the run report. Analysis may narrow a claim because of a
negative result, but must not delete the result. Framework defects discovered
here are limitations of 0.8.1 unless separately fixed in a later release.

## Canonical acceptance

A canonical run is valid only if:

1. the exact wheel and installed direct-url hashes match;
2. the import path is outside the source checkout;
3. the local `v0.8.1` tag resolves to the registered commit;
4. dependency and host metadata are present;
5. all declared artifacts exist and have hashes;
6. no required experiment is silently skipped; and
7. the repository protocol and run both state whether the tree was dirty.
