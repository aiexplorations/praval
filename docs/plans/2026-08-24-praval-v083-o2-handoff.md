# Praval v0.8.3 O2 handoff

## Completed package

Work package O2, execution-observation contract and trace core, is complete.

## Public contracts

- `praval.models.ExecutionObservation` is the schema-version-1 contract for one
  completed agent invocation or workflow. It is immutable, rejects unknown
  fields, normalizes aware timestamps to UTC, and serializes through Pydantic's
  JSON contract.
- Observation identity fields are `observation_id`, `run_id`, `kind`,
  `conversation_id`, `response_id`, `agent_id`, `agent_name`, `workflow_id`, and
  `workflow_name`.
- Timing and outcome fields are `started_at`, `ended_at`, `duration_ms`,
  `status`, `error_type`, and `terminal_outcome`. Error observations require a
  structured error type. Cancelled and timed-out observations may also carry a
  structured error type. Successful observations may not.
- Model facts are `provider`, `model`, `request_mode`, and
  `TokenUsageObservation`. Token counts are non-negative and a supplied total
  cannot be smaller than input plus output tokens.
- Bounded nested facts are `ToolCallObservation`, `RetryObservation`,
  `HITLDecisionObservation`, and `ReefHandoffObservation`. An observation can
  contain at most 128 tool calls, 32 retries, 32 HITL decisions, and 128
  handoffs.
- `ContentReference` carries content kind, SHA-256 identity, byte size, optional
  reference, and media type. The schema has no raw prompt, response, context,
  tool-payload, document, media, or judge-evidence field.
- `ObservationPrivacy` defaults to `metadata_only` with content capture
  disabled. Captured content requires an explicit non-metadata mode and a
  positive byte limit.
- `trace_id` and `span_id` are optional as a pair and use the OpenTelemetry
  32-hex and 16-hex forms.
- `ObservationRecorder` is a runtime-checkable structural protocol with one
  synchronous `record(ExecutionObservation) -> None` operation.
  `NoOpObservationRecorder` and `NOOP_OBSERVATION_RECORDER` are the default
  zero-side-effect implementation and singleton.
- The v0.8.2 `praval.observability` and
  `praval.observability.tracing` compatibility names now map to official
  OpenTelemetry API objects: `Span`, `Tracer`, `SpanKind`, `SpanStatus` as
  `StatusCode`, and `NoOpSpan` as `NonRecordingSpan`.
- `get_tracer()` returns the official tracer selected by the O1 lifecycle.
  `get_current_span()` is the official OpenTelemetry function and therefore
  returns an invalid non-recording span when no span is current rather than
  returning `None`.

## Internal contracts and invariants

- `src/praval/models/observation.py` imports neither OpenTelemetry nor
  evaluation code. Observability and eval must consume this provider-neutral
  model rather than parsing one another's internals.
- The trace core has no Praval span class, tracer class, sampling loop,
  exporter call, SQLite write, thread-local current-span store, or second trace
  identifier implementation.
- Span creation, parentage, exception recording, status-on-exception, and
  current context are delegated to the official OpenTelemetry API and SDK.
- Parent-based sampling and service resources remain owned by the O1
  lifecycle. O2 verifies their behavior through official in-memory processors
  and exporters.
- OpenTelemetry context propagation supplies async task isolation. Praval does
  not add another `ContextVar` or thread-local layer.
- `TraceContext` is a frozen compatibility value for the v0.8.2 Spore
  `trace_id`, `span_id`, and `trace_flags` metadata. It validates official
  identifier forms and converts to an official remote-parent `Context`; it does
  not manage the current context itself.
- Existing instrumentation helpers and MCP calls now use official
  `context=` and `Status(StatusCode...)` arguments. Broader runtime
  instrumentation remains O3.
- The legacy SQLite diagnostic store is decoupled from the removed custom span
  through a temporary `StorableSpan` input protocol. It is not attached to the
  official tracer. The official local batch exporter and retention migration
  remain O5.
- The base wheel imports only `opentelemetry-api`. Observation recording and
  no-op tracing work when no OpenTelemetry SDK or exporter package is installed.
- O1 lifecycle ownership remains unchanged. Praval still does not replace,
  flush, or shut down application-owned providers.

## Verification

- Full repository suite: 1,816 passed and 128 skipped.
- O2 observation and official trace-core contract suite: 27 passed.
- Full observability suite plus the observation contract: 102 passed.
- ModelRuntime, MCP, Agent, HITL, and documentation compatibility regression:
  193 passed and 1 skipped.
- Release-script, documentation, instrumentation, and legacy-store regression:
  48 passed.
- New trace/observation coverage: observation model 99 percent, compatibility
  context 100 percent, span mappings 100 percent, tracer facade 100 percent;
  99 percent combined.
- Strict source typing passes on Python 3.13 and the Python 3.10 compatibility
  target.
- Black and isort checks pass across `src`, `tests`, and `scripts`. Targeted
  flake8 passes for all O2 files. A repository-wide flake8 run still reports
  pre-existing E226 findings in the PostgreSQL provider and knowledge-base
  tests; O2 did not modify those files.
- A wheel built from the working tree passes clean-environment smoke tests for
  both the base installation and the `observability` extra. The base
  environment proves `opentelemetry.sdk` is absent while official no-op tracing,
  observation imports, and compatibility mappings work.
- `git diff --check` passes.

## Known limitations and deferred work

- Runtime boundaries do not yet emit `ExecutionObservation` records. O3 will
  integrate the frozen protocol with agents, workflows, model modes, providers,
  tools, MCP, HITL, memory, storage, embeddings, transcription, speech, and
  streaming.
- No concrete observability recorder converts completed observations into
  OpenTelemetry telemetry yet. That belongs with O3 runtime integration; eval
  must still be able to consume the same observations independently later.
- Legacy Spore metadata is not W3C propagation. O4 will add standard
  inject/extract behavior across every Spore wire format and secure
  serialization path.
- Metrics, logs, bounded exporters, local diagnostics, trace viewing migration,
  and retention are O5.
- The package version remains 0.8.2 during staged development. Final 0.8.3
  versioning and release documentation remain in the release package.

## Next package

Proceed with O3, agent and runtime instrumentation. O3 may change stable runtime
boundaries in:

- agent invocation, decorated handlers, conversations, workflows, terminal
  outcomes, and handoffs;
- `ModelRuntime` sync, async, streaming, structured-output, embedding,
  transcription, and speech paths;
- provider calls, retries, usage capture, tools, MCP, HITL, memory, and storage;
- a concrete recorder or internal recorder composition layer that receives the
  frozen `ExecutionObservation` contract;
- focused O3 instrumentation, error, cancellation, usage, privacy, and
  no-op-overhead tests.

O3 must not redefine O2 identity, timing, status, usage, tool, handoff,
content-reference, privacy, or trace-correlation fields. It must not implement
W3C Spore propagation, metrics, logs, OTLP exporters, SQLite export, retention,
or evaluation. Those remain O4, O5, and Workstream B.
