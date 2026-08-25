# Sampled online evaluation

Online evaluation is opt-in and disabled by default. The request path performs
only target matching, deterministic trace sampling, bounded observation
serialization, and a non-blocking bounded queue insertion. Storage and all
metric, judge, model, embedding, retrieval, tool, and network work occurs in
explicitly started workers.

Production online evaluation requires PostgreSQL:

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

`lease_seconds` must exceed `job_timeout_seconds`. Queue, worker, retry,
payload, lease, polling, timeout, and shutdown values have hard validation
bounds.

Construct an `OnlineEvaluationService` with a suite, PostgreSQL store, and
worker processor (normally `OnlineSubjectEvaluator`). Call `await start()`,
register the service as an observation recorder, and call `await shutdown()`
during graceful termination. `OnlineSubjectEvaluator` resolves candidate
content through the application `OnlineContextLoader` only after leasing a
durable job.

Jobs have stable natural identities. PostgreSQL workers lease with
`FOR UPDATE SKIP LOCKED`, recover expired leases, persist bounded attempts, use
exponential retry delay, and dead-letter after at most three attempts.
Duplicate observation delivery cannot revert a completed job.

Queue saturation, oversized subjects, invalid trace IDs, persistence failure,
retries, dead letters, queue depth, duration, and completion are observable.
Worker spans link to the original completed execution span. They are not
children that distort request latency.

Start with a low sample ratio. Alert on queue drops, store failures, judge
failure, latency, and cost before increasing it. A PostgreSQL outage may lose
items still only in the bounded process queue; the drop counter makes this
explicit. Shutdown makes one bounded drain attempt and releases interrupted
leases for a later process.
