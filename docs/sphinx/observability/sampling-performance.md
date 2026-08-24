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

