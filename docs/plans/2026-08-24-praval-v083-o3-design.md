# Praval v0.8.3 O3 runtime instrumentation design

## Decision

O3 emits one `ExecutionObservation` for each real agent invocation or complete
workflow. Model, provider, streaming, tool, MCP, HITL, memory, storage,
embedding, transcription, and speech operations add bounded facts to the
active observation. Standalone lower-level operations emit spans but do not
invent agent or workflow identities and therefore do not emit synthetic
observations.

Recorder and telemetry failures never change application results. Application
exceptions retain their original type and value, produce error telemetry and a
structured observation outcome, and are re-raised.

## Runtime structure

- A provider-neutral observation scope owns one mutable, context-local builder
  during execution and freezes it into the O2 schema exactly once at exit.
- The scope uses OpenTelemetry API spans without importing the SDK. It records
  stable bounded attributes and hashes, never raw content under the default
  metadata-only policy.
- Nested runtime boundaries use child spans and append facts to the active
  builder. Async tasks inherit OpenTelemetry and observation context through
  `ContextVar`; sibling tasks do not share mutable builders.
- Recorder composition fans a completed observation to configured consumers.
  Consumer failures are isolated independently so one recorder cannot prevent
  other consumers or the application result.
- Agent and workflow boundaries provide identity. ModelRuntime provides model,
  provider, response, usage, retry, finish, time-to-first-token, cancellation,
  and error facts. Tool and subsystem boundaries contribute their own bounded
  child facts.
- Tool-round limits use typed agent/request configuration. Limit exhaustion
  produces `tool_round_limit_exceeded`, marks the active observation as an
  error, and preserves the existing public exception behavior.

## Feature and test matrix

| Feature item | Required tests |
| --- | --- |
| Observation scope and recorder fan-out | success serialization, exactly-once delivery, nested scope isolation, recorder failure isolation, no-recorder no-op |
| Privacy capture | prompt/response hashes and sizes, no raw content, capture policy bounds, secret-shaped content absence |
| Agent invocation | sync success, provider error re-raised, identity and timing agreement with root span, conversation/response correlation |
| Decorated handler | success, ignored message produces no invocation, handler error policy and error observation, async isolation where supported |
| Workflow boundary | success, terminal outcome, child agent correlation without duplicate synthetic identities, workflow failure |
| Model sync and async | response identity, provider/model, usage, finish state, timeout, cancellation, provider error, structured output |
| Streaming | time to first token, final usage and finish state, interrupted consumer, provider failure before and after first token, sync and async cleanup |
| Retries and tool-round limit | each retry fact, attempts, configured agent limit, request override, structured limit event and error type |
| Tools and MCP | selected tool name/id, duration, success, returned error, raised error, timeout, cancellation, HITL suspension |
| HITL | requested, approved, rejected, edited, timeout, cancellation, suspension/resumption correlation |
| Embeddings and media | embedding dimensions/count, transcription and speech status, provider/model, sizes and hashes, provider errors |
| Memory and storage | operation/name/status/duration child spans, errors re-raised, no payload capture |
| Standalone lower-level calls | spans exist with an SDK, no synthetic observation, no-SDK behavior remains functional |
| Compatibility and overhead | existing runtime tests, disabled/no-op benchmark below the release threshold, no optional SDK import |

## Package boundaries

O3 does not change the frozen O2 observation fields. It does not add W3C Spore
propagation, metrics, logs, exporters, SQLite trace export, retention, or eval.
Those remain O4, O5, and Workstream B.
