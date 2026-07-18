# ADR: Model Runtime Hardening

## Status

Accepted for the model runtime rearchitecture branch.

## Context

Provider APIs have diverged across chat completions, responses APIs, reasoning,
structured output, multimodal input, native streaming, local OpenAI-compatible
servers, and tool-calling protocols. A provider-level boolean is no longer
enough to tell users what will work.

## Decision

Praval uses a provider-neutral `ModelRuntime` and public contracts in
`praval.models`.

Runtime responsibilities:

- Resolve capabilities from provider, model, endpoint, local preset, and
  explicit overrides.
- Validate requests before provider execution.
- Normalize streaming events.
- Own tool execution policy, HITL pause/resume state, retries, usage accounting,
  and observability spans.
- Preserve legacy string-returning APIs.

Provider responsibilities:

- Translate neutral requests into provider wire payloads.
- Translate provider responses and stream chunks into neutral runtime objects.
- Redact secrets in provider errors.

## Capability Resolution

Profiles include provider, model, endpoint, local preset, default parameters,
context window, output token limits, unsupported combinations, and downgrade
policy. The default downgrade policy is `error`.

## Streaming Semantics

The runtime emits `start`, then adapter events, then `final`. Providers with
`native_streaming=True` must implement a native stream path or validation fails.
Fake streaming is reserved for explicit emulated profiles.

## Multimodal Normalization

`ContentPart` values are validated before provider execution. Providers only
serialize supported text, image, file, and audio shapes into their wire format.
Unsupported content types fail deterministically.

## Local Provider Policy

OpenAI-compatible local servers are conservative by default. Text and native
streaming are enabled. Tools, structured output, reasoning, and multimodal input
require explicit opt-in profiles or per-call capability overrides.

## Async Execution

Adapters may implement native `ainvoke()` and `astream()`. The runtime falls
back to a thread executor for legacy sync providers.

## Agent Communication and Realtime Scope

Reef remains Praval's native agent-to-agent communication system. The model
runtime operates inside an agent and does not replace Reef or introduce a
second A2A abstraction.

In Praval, a realtime model session would be a persistent provider connection
with a continuous stream of input and output events, potentially including
bidirectional audio over WebRTC or WebSocket. That lifecycle differs from a
normal request, a streamed text response, or a Reef message. Realtime model
sessions are not part of 0.8.

Request-based `Agent.transcribe()` and `Agent.speak()` remain supported. They
perform bounded transcription and speech-generation requests and do not keep a
persistent audio session open.

## Consequences

Users get predictable failures instead of silent downgrades. Provider adapters
stay smaller, and tests can run the same contract suite across real SDKs, fake
SDKs, and local-compatible HTTP servers.
