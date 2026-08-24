# Praval v0.8.3 O3 handoff

## Completed package

Work package O3, agent and runtime instrumentation, is complete.

The runtime now produces one completed `ExecutionObservation` for each agent
invocation and one for each workflow. Facts from nested model calls, tools,
retries, HITL decisions, memory, storage, embeddings, and media operations are
aggregated into the active agent observation. An agent running inside a
workflow also contributes those facts to the workflow observation. Reentrant
instrumentation for the same agent joins the existing observation instead of
creating duplicates.

## Public contracts

- `praval.observability.configure_observation_recorder(recorder)` installs the
  process default `ObservationRecorder` without requiring the OpenTelemetry
  SDK.
- `praval.observability.use_observation_recorder(recorder)` temporarily selects
  a context-local recorder and restores the previous recorder on exit.
- `praval.observability.CompositeObservationRecorder` sends each immutable
  observation to multiple recorders. A recorder failure is isolated from the
  application and from the remaining recorders.
- `AgentConfig.max_tool_rounds` defaults to 8 and is bounded from 1 through
  1000. The typed application and resolved-agent configuration use the same
  bound.
- `ModelRequest.max_tool_rounds` is an optional per-request override with the
  same bound. The request override wins over the agent default.
- Tool-round exhaustion raises the existing application error and emits a
  structured `praval.limit.reached` trace event with limit kind
  `tool_rounds`. The instrumentation does not turn the failure into success.

## Runtime contracts and invariants

- `src/praval/runtime_observation.py` is the provider-neutral runtime spine. It
  depends on the OpenTelemetry API only, not the SDK, exporters, SQLite, or
  evaluation code.
- Observation scope is held in `ContextVar` state and follows async tasks and
  explicit executor context propagation. Concurrent requests cannot share an
  observation accumulator.
- Agent entry points cover sync and async generation, streaming, transcription,
  and speech. Streaming observations remain open until completion, error,
  cancellation, or iterator close, so duration and time to first token describe
  the real stream lifetime.
- Decorated handlers are agent boundaries. If a handler invokes the matching
  `Agent`, the inner call joins the handler observation. Handled exceptions are
  still recorded as errors before the handler returns its compatibility result.
- `AgentSession` is the workflow boundary. It emits one workflow observation,
  while each participating agent still emits one agent observation and adds its
  bounded facts to the workflow aggregate.
- ModelRuntime records request mode, provider, model, response identity, finish
  reason, usage, retries, structured errors, cancellation, and time to first
  token. Native and compatibility streaming paths do not double-count usage.
- Provider calls, continuations, and streams use child spans. Observations and
  their root spans share trace identity, status, error type, and timing facts.
- Tool execution records one fact per logical tool call. An MCP call nested in
  the tool runtime joins that call instead of producing a duplicate fact.
- HITL records requested and terminal decisions (`approved`, `edited`, or
  `rejected`) without reviewer identity. Only the low-cardinality reviewer type
  is retained.
- Memory, storage, embedding, MCP, HITL, and tool operations create child spans
  and contribute facts only when an agent or workflow observation is active.
  Calling those lower-level APIs alone never creates a root observation.
- Metadata-only privacy remains the default. Prompt, response, media, tool,
  memory, storage, and embedding values are represented by bounded SHA-256
  content references and sizes; raw content is not added to observations.
- Recorder, tracer, span metadata, and trace-event failures are isolated.
  Telemetry cannot alter an application return value or replace its exception.
- The O2 `ExecutionObservation` schema was not redefined.

## Test matrix

- Agent: direct success, application error, async cancellation, sync stream,
  async stream, stream cancellation, transcription success and error, and
  speech success and error.
- Decorators and workflows: nested decorated `Agent.chat` deduplication,
  handled-error status, executor context propagation, one observation per
  agent, one observation per workflow, and workflow fact aggregation.
- Model runtime and providers: sync and async usage, response identity, finish
  state, retry aggregation, provider errors, structured-output paths, native
  streaming, compatibility streaming, time to first token, cancellation, and
  tool-round exhaustion.
- Tools and MCP: sync success, returned tool error, raised error, async
  cancellation, MCP success, MCP timeout, and nested-call deduplication.
- HITL: request plus approve, edit, reject, timeout, and privacy-safe reviewer
  metadata.
- Lower-level operations: embedding joins an active observation but produces no
  standalone observation; memory and storage add privacy-safe references and
  preserve return values and failures.
- Robustness: composite recorder isolation, broken tracer isolation, oversized
  metadata isolation, async context isolation, observation/span correlation,
  content hashing, and no-op behavior.
- Legacy compatibility: optional memory methods may be absent without failing
  instrumentation initialization.

## Verification

- Final full repository and coverage suite: 1,850 passed and 128 skipped.
- Total source coverage: 92.83 percent, above the 90 percent release floor.
- Per-file coverage release floors pass. The legacy instrumentation manager is
  now at 80.84 percent and the new runtime observation module is at 96 percent,
  above the plan's 95 percent target for new instrumentation.
- Repository-wide flake8 passes.
- Strict source typing passes for the active Python 3.13 environment and the
  Python 3.10 compatibility target.
- O3 focused runtime observation and fact-source suite: 33 tests pass.
- The full suite reports six dependency or compatibility deprecation warnings;
  no test warning is an O3 runtime failure.

Commands used for the final gate:

```text
source venv/bin/activate && make test
source venv/bin/activate && make lint
source venv/bin/activate && make type-check
source venv/bin/activate && make test-cov
```

## Known limitations and deferred work

- Spore and Reef still use the legacy trace metadata. W3C carrier injection,
  extraction, RabbitMQ propagation, secure-spore authentication, and handoff
  relationship completion belong to O4.
- Metrics, structured logs, live OTLP exporters, bounded signal queues, privacy
  redaction policy configuration, SQLite batch export, retention, and measured
  overhead belong to O5.
- The legacy opt-in monkeypatch instrumentation manager remains for v0.8.2
  compatibility. Direct O3 instrumentation is authoritative. Explicitly
  enabling the legacy manager can add nested compatibility spans, but it does
  not add duplicate observations.
- The package version remains 0.8.2 during staged development. Exact v0.8.3
  versioning, public documentation, migration guidance, and certification
  remain later release work.
- Evaluation implementation remains blocked until O4, O5, and O6 complete the
  observability foundation checkpoint.

## Next package

Proceed with O4, Reef and Spore propagation. Begin from this handoff, the O4
section of the release plan, and the existing `ExecutionObservation` and
runtime-observation contract tests.

O4 may change:

- the versioned Spore carrier and JSON serialization;
- in-memory and RabbitMQ Reef send, broadcast, delivery, request, and response
  paths;
- secure Spore serialization and authentication coverage;
- runtime handoff recording needed to connect producer, delivery, consumer,
  and workflow relationships;
- focused propagation, concurrent-message isolation, and tamper tests.

O4 must not redefine the O2 observation schema or O3 one-observation-per-
agent/workflow semantics. It must not implement metrics, logs, exporters,
SQLite retention, or evaluation.
