# Sampling and performance

`parentbased_traceidratio` is the production default sampler. Make the decision
at the workflow root so descendants follow the same decision. Use `always_on`
for small deterministic diagnostics and `always_off` when an explicitly
configured pipeline should emit no spans.

Tune `max_queue_size`, `max_export_batch_size`, `schedule_delay_millis`,
`export_timeout_millis`, and `metric_export_interval_millis` to the process
budget. Smaller queues bound memory more tightly but increase drops during
collector outages. Smaller batches reduce latency and usually increase export
overhead.

Release certification measures an end-to-end deterministic fake-agent path.
No-op instrumentation must remain below 2 percent overhead and enabled,
in-memory batched telemetry below 5 percent, excluding network time:

```bash
PRAVAL_RUN_PERFORMANCE_TESTS=1 \
  pytest tests/performance/test_observability_overhead.py -v
```

Do not infer network exporter performance from that test. Load-test the chosen
Collector topology and alert on queue depth, dropped items, export failures,
and lifecycle failures.

## Choosing a ratio

Start with the smallest ratio that still yields enough complete traces for the
target's request volume and error budget. Sampling is all-or-nothing at the
root: do not independently sample child agents or Reef consumers. Metrics and
structured completion logs remain useful for aggregate monitoring when most
traces are unsampled.

`always_on` is appropriate for deterministic tests and short local diagnosis;
it is rarely an acceptable high-volume production default. `always_off` keeps
an explicitly configured pipeline available while suppressing spans, but it
does not disable metrics/logs. Disable unneeded signals in `observability.otlp`
when the desired outcome is no exporter at all.

## Queue and batch tradeoffs

- Queue capacity is the hard in-process memory/loss boundary during exporter
  slowdown.
- Batch size cannot exceed queue size. Larger batches improve throughput but
  can increase delivery latency.
- Schedule delay bounds how long a partially filled trace/log batch waits.
- Export timeout bounds each exporter attempt; it must fit the service's total
  shutdown budget.
- Metric export interval controls aggregation freshness and backend traffic.

Measure with representative concurrency, tool facts, Reef handoffs, and
attribute counts. Benchmark p50/p95/p99 request latency, CPU, resident memory,
queue high-water mark, exporter failures, and drops. Never add request IDs,
user IDs, raw URLs, prompts, or exception messages as metric dimensions to
solve a sampling problem; that creates a cardinality and privacy problem.
