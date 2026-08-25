# Evaluation configuration reference

Evaluation uses typed `praval.toml` configuration. Defaults apply first, then
the discovered/explicit file, supported environment variables, and explicit
API construction. Unknown fields, bad references, and out-of-bound values fail
before execution.

The `EvalConfig` fields are `enabled`, `store`, `offline_concurrency`, `online`,
`stores`, `ragas`, `judges`, and `suites`, serialized beneath `eval`.

## Core and stores

| Field | Type | Default | Validation |
|---|---|---|---|
| `eval.enabled` | bool | `false` | no runtime work when false |
| `eval.store` | `sqlite` or `postgres` | `sqlite` | PostgreSQL block required when selected |
| `eval.offline_concurrency` | int | `4` | greater than zero |
| `eval.stores.sqlite.path` | string | `.praval/evaluations.db` | local/CI path |
| `eval.stores.postgres.dsn_env` | string | none | uppercase environment-variable name |

The named DSN environment value is read at runtime and never included in
diagnostics. Online evaluation requires `store="postgres"`.

## Judge profiles

Each `[eval.judges.<name>]` sets exactly one of `agent` or `model`.

| Field | Default | Validation |
|---|---|---|
| `timeout_seconds` | `60` | positive |
| `max_attempts` | `2` | positive |
| `allow_self_evaluation` | `false` | explicit opt-in |
| `allowed_tools` | `[]` | subset of configured evaluator tools |
| `tool_policy` | `evaluation_safe` | or `read_only` |
| `allow_side_effects` | `false` | `true` rejected in v0.8.3 |
| `hitl_mode` | `suspend` | or `fail` |
| `max_input_tokens` | `16000` | positive |
| `max_cost_usd` | `0.25` | positive finite |
| `rubric` | default outcome rubric | 1 to 16,384 characters |
| `rubric_version` | `1` | 1 to 128 characters |
| `judge_version` | `1` | 1 to 128 characters |

Agent references must exist under `[agents]`; model references must exist
under `[models]`. Agent profile `max_tool_rounds` defaults to 8, and memory
requires a stable `memory_namespace`.

## Suites and gates

Each `[eval.suites.<name>]` requires `dataset` and `target`; `judges`, `metrics`,
and `gates` default empty. Referenced judges and gate result names must exist.
Each gate has optional `gate_id`, required metric, aggregation, operator, and
finite threshold. `required` defaults true. `percentile` is required only for
percentile aggregation and must be in `(0, 100]`.
`baseline_max_regression`, when supplied, is finite and non-negative.

## RAGAS

`eval.ragas` is optional. `model` and `embedding` reference named Praval
profiles, `timeout_seconds` defaults to 60 and is positive, and
`strict_tool_order` defaults true. Selected metrics may require only the model,
only embeddings, or both; see {doc}`metrics-ragas`.

## Online workers

| Field | Default | Hard bound |
|---|---:|---:|
| `enabled` | false | boolean |
| `sample_ratio` | 0.01 | 0 through 1 |
| `queue_capacity` | 1000 | 1 through 100,000 |
| `workers` | 2 | 1 through 64 |
| `max_attempts` | 3 | 1 through 3 |
| `max_enqueue_attempts` | 3 | 1 through 3 |
| `lease_seconds` | 180 | positive, at most 3,600 |
| `job_timeout_seconds` | 120 | positive, at most 1,800 |
| `poll_interval_seconds` | 0.1 | positive, at most 60 |
| `retry_backoff_seconds` | 0.25 | 0 through 300 |
| `shutdown_timeout_seconds` | 5 | positive, at most 300 |
| `max_subject_bytes` | 262,144 | 1 through 1,048,576 |

The lease must be longer than the processor timeout. Configuration never starts
a worker; application lifecycle must explicitly construct and start the
service.
