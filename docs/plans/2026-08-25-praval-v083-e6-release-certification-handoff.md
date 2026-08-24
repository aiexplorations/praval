# v0.8.3 E6 documentation and release-certification handoff

E6 completes the local implementation, documentation, example, and combined
observability/evaluation certification scope for v0.8.3. Publication still
requires a clean committed release candidate, the final CI run, documentation
site staging with matching provenance, and the normal tag and package-release
controls.

## Delivered documentation product

- Observability and Evaluation are top-level Sphinx navigation areas.
- The Evaluation manual covers the relationship to observations, installation,
  configuration, target and evaluator-agent patterns, evaluator capability
  policy, direct model judges, datasets, agent and workflow evaluation, metric
  plugins, RAGAS, gates and CI, online workers, stores, telemetry, privacy,
  cost, failures, troubleshooting, and the complete public API.
- The patterns guide recommends a separate least-privilege evaluator agent,
  stable identities, versioned rubrics, bounded execution, deterministic
  dependency seams, and exactly one immutable observation with aggregated
  facts per evaluated agent or workflow. It includes a mechanism decision
  table, paired agent/workflow architectures, safe defaults, and anti-patterns.
- The Observability manual now includes exact signal and instrumentation maps,
  W3C propagation and ownership rules, Collector and Docker Compose recipes,
  TLS and header handling, sampling and queue tradeoffs, local diagnostics,
  privacy boundaries, lifecycle failure behavior, and the full migration map.
- The core guides link to design-for-evaluability guidance without making
  ordinary agent execution depend on `praval.eval`.
- The v0.8.3 migration guide covers Python 3.10 through 3.14, typed
  configuration, explicit observability lifecycle, and evaluation adoption.

## Executable patterns and contracts

- `examples/evaluation/000_quickstart.py` runs a local deterministic suite and
  gate with one agent observation.
- `examples/evaluation/001_paired_agents.py` uses separate target and evaluator
  agents, a fake provider, one read-only evaluator tool, and a strict versioned
  rubric.
- `examples/evaluation/002_workflow_evaluation.py` judges one workflow
  observation containing aggregated tool and handoff facts.
- All three examples are credential-free, use public APIs only, are registered
  in the example manifest, execute from the exact wheel, and are part of the
  clean minimal-install smoke test.
- `docs/documentation-coverage.toml` maps public API, feature, configuration,
  extra, and error claims to documentation pages and executable tests.
- `praval doctor` reports evaluation core, SQLite, PostgreSQL, RAGAS, package,
  and entry-point availability without exposing DSNs or credentials.
- The API inventory contains exact `praval.eval` and `praval.config` exports;
  nonexistent `praval.explainability`, `praval.security`, and `get_metrics()`
  APIs are not claimed.

## Local certification evidence

Results recorded on 2026-08-25:

- Direct repository suite: 2,120 passed and 132 skipped before the final
  coverage-floor additions.
- Final coverage suite: 2,113 passed and 144 expected optional-service skips;
  total package coverage is 92.94 percent and all release floors pass.
- Focused SQLite evaluation store coverage is 95.86 percent. The release-floor
  checker now enforces 95 percent for new evaluation gates, runner, online
  scheduler, SQLite store, W3C context propagation, and runtime observation.
- Real PostgreSQL 15 store, job, lease, retry, recovery, and idempotency suite:
  10 of 10 passed.
- Real OpenTelemetry Collector contract: traces, metrics, and logs passed over
  HTTP/protobuf and gRPC, 2 of 2 tests.
- Real RabbitMQ workflow and W3C parentage suite: 8 of 8 passed. Certification
  also found and fixed an integration-test connection leak; the suite now
  terminates cleanly in about 11 seconds.
- Privacy, lifecycle, shutdown, and online failure/recovery suite: 60 of 60
  passed.
- Measured no-op overhead is 1.41 percent against a 2 percent ceiling;
  enabled batched in-memory telemetry overhead is 1.63 percent against a
  5 percent ceiling. Online scheduling remains below 2 milliseconds p95.
- The exact wheel passes clean minimal smoke tests on Python 3.10, 3.11, 3.12,
  3.13, and 3.14. The `observability` and `eval-ragas` extras also pass clean
  exact-wheel installation and runtime smoke tests.
- Exact-wheel API inventory is 100 percent: 93 exported and 93 documented
  top-level symbols, with exact public submodule exports.
- Exact-wheel Sphinx HTML builds with warnings as errors. Sphinx API coverage
  is 100 percent, documentation link checking passes, and the candidate site
  contains 374 files.
- Black, isort, repository-wide flake8, strict Python 3.13 typing, and Python
  3.10 compatibility typing pass.

## Operational requirements

- Keep observability and online evaluation disabled until explicitly
  configured.
- Send OTLP to a nearby Collector, use parent-based sampling, and call bounded
  shutdown during graceful termination.
- Keep content capture off by default. If content is enabled, apply redaction,
  access control, and retention before storing or exporting it.
- Use PostgreSQL for shared evaluation records and online jobs. SQLite remains
  a local-development and CI store.
- Use separate pinned evaluator configuration where possible, restrict tools
  to evaluation-safe capabilities, keep memory isolated, and promote baselines
  only after review.

## Known limitations

- RAGAS remains an optional and comparatively large dependency set; the tested
  compatibility bounds are documented in the E4 handoff.
- SQLite stores are single-host diagnostics and must not be shared between
  containers.
- Online evaluation is opt-in, requires an application content resolver, and
  intentionally performs no judge work on the request path.
- The current macOS `asyncpg 0.31` coverage-tracer issue requires PostgreSQL
  behavior and its already-certified per-file coverage to run separately.
- v0.8.3 does not include hosted dashboards, leaderboards, automatic baseline
  promotion, synthetic dataset generation, or explainability/security modules.

## Post-v0.8.3 work

- Hosted evaluation reporting and trend exploration.
- Broader metric-adapter and dataset-tooling support.
- Operational dashboards and alert templates for Collector and evaluation
  worker health.
- Further removal of legacy observability compatibility helpers after the
  documented migration window.

## Final publication boundary

Before tagging or publishing, build the wheel from the clean E6 commit, repeat
distribution and exact-wheel smoke checks, generate the documentation artifact
with that same commit in its provenance manifest, stage it into `praval-ai`,
and require the final repository and documentation CI checks to pass. Never
publish a wheel or site built from a dirty or mismatched commit.
