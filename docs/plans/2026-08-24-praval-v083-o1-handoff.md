# Praval v0.8.3 O1 handoff

## Completed package

Work package O1, configuration, dependencies, and lifecycle, is complete.

## Public contracts

- `praval.PravalConfig`, `praval.load_config()`, and
  `praval.discover_config_path()` define schema-versioned `praval.toml`
  configuration with defaults, file values, environment values, and explicit
  overrides in increasing precedence.
- `praval.PravalConfigurationError` is the public failure type for invalid
  application and observability configuration.
- `praval.observability.configure_observability()` returns an
  `ObservabilityHandle` that records the active providers and the signals whose
  lifecycle Praval owns.
- `configure_tracing()`, `get_tracer()`, `get_meter()`, `get_logger()`,
  `force_flush()`, and `shutdown_observability()` use official OpenTelemetry API
  objects.
- The v0.8.2 `ObservabilityConfig` flat fields remain accepted with deprecation
  warnings through `praval.observability.config`.

## Internal contracts and invariants

- Importing `praval` or `praval.observability` does not configure providers,
  instrument runtime functions, create files, or start threads. The global Reef
  is now created lazily behind a reentrant guard to satisfy the same import
  contract without deadlocking agent finalizers during garbage collection.
- Praval never replaces global OpenTelemetry providers. Its facade uses the
  providers supplied to `configure_observability()` or providers created and
  owned by the returned handle.
- Application-owned providers are never flushed or shut down by Praval.
  Processors attached by Praval remain Praval-owned.
- A configured endpoint is either attached to every selected signal or rejected
  with `PravalConfigurationError`. Existing meter providers cannot accept new
  readers and are rejected when Praval is asked to add OTLP metric export.
- Repeated identical configuration returns the active handle. Different
  configuration is rejected until the active handle is shut down.
- Flush and shutdown share a hard wall-clock bound and isolate exporter errors
  from application behavior.
- The base wheel contains OpenTelemetry API 1.44.x. The `observability` extra
  contains the SDK plus HTTP/protobuf and gRPC OTLP exporters on the same minor
  line.
- Python support is 3.10 through 3.14.
- Configuration is immutable, rejects unknown fields, validates model, agent,
  judge, suite, tool, memory, HITL, store, and budget references before runtime
  work, and keeps secret values behind environment-variable names.

## Verification

- Full test suite after the O1 edge tests: 1,836 passed, 128 skipped. The two
  initial failures were API inventory counts updated for the four new
  configuration exports; the focused documentation contract suite passes after
  that update.
- Fresh-process Agent, Reef, request/reply, and observability lifecycle teardown
  regression: 146 passed, including the reentrant lazy-Reef guard.
- Focused observability and Reef regression suite: 168 passed.
- New-file coverage: `praval.config` 100 percent and
  `praval.observability.lifecycle` 96 percent.
- Strict typing: current Python 3.13 and minimum Python 3.10 passes.
- Black, isort, and flake8 checks pass for the changed implementation and tests.
- A built wheel passes Twine and distribution metadata validation.
- Clean-environment smoke tests pass for both the base wheel and the
  `observability` extra. The base environment has no OpenTelemetry SDK; the
  extra installs OpenTelemetry 1.44.0 and exercises the public lifecycle API.

## Known limitations and deferred work

- The package version remains 0.8.2 during staged development. The final 0.8.3
  version, release notes, and complete documentation migration belong to the
  release package after both workstreams pass.
- The v0.8.2 custom tracer remains available internally until O2 replaces it and
  maps supported compatibility names to official OpenTelemetry objects.
- Runtime instrumentation still uses the custom tracer until O2 and O3.
- The local SQLite diagnostic exporter is deliberately rejected by the new
  lifecycle until O5 converts it into an official batch exporter. It is never
  silently ignored.
- OpenTelemetry global providers are application-owned. Praval does not mutate
  them because Python global providers cannot be safely replaced during repeat
  setup or test isolation.

## Next package

Proceed with O2, execution-observation contract and trace core. O2 may change:

- `src/praval/models/` or a provider-neutral sibling module for
  `ExecutionObservation` and `ObservationRecorder`;
- `src/praval/observability/tracing/` to replace the custom implementation;
- `src/praval/observability/lifecycle.py` only for compatibility mappings or
  trace-core integration that preserves O1 ownership and shutdown behavior;
- focused observation, official in-memory trace, sampling, parentage, exception,
  no-SDK, async-context, and compatibility tests.

O2 must not start runtime-wide agent, provider, tool, Reef, storage, metrics,
logs, OTLP collector, or SQLite exporter instrumentation. Those remain O3 to O5.
