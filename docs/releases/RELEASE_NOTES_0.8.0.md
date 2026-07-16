# Praval 0.8.0 (unreleased)

Praval 0.8.0 modernizes model execution while preserving the decorator-first
agent, Reef/Spore, memory, HITL, and observability APIs. Reef remains Praval's
canonical agent-to-agent substrate; this release does not add a second A2A
abstraction.

## Stable 0.8 Surface

- Provider-neutral `ModelRuntime` for OpenAI, Anthropic, Cohere, Gemini, and
  OpenAI-compatible local servers.
- Client/function tool execution with normalized events and HITL resume.
- Tools-only MCP clients for stdio and Streamable HTTP on Python 3.10+.
- OpenAI Responses routing, structured outputs, reasoning, transcription, and
  text-to-speech.
- Gemini function calling and multimodal image/file/audio/video generation
  inputs.
- Request-based voice helpers: `Agent.transcribe()` and `Agent.speak()`.
- Separate provider-neutral embedding configuration for Chroma and Qdrant.
- Spore V2 JSON fields for multimodal content and storage references.
- Conservative local profiles for Ollama, vLLM, LM Studio, and llama.cpp.

## MCP Scope

MCP tools use the existing Praval tool registry and provider-neutral runtime.
They are async-only, namespaced by server, approval-gated by default, traced,
bounded by timeouts and result-size limits, and closed with their client
context. Text and structured results are supported.

MCP resources, prompts, server hosting, OAuth negotiation, legacy SSE,
sampling, elicitation, experimental tasks, binary/image results, automatic
reconnect, and sync event-loop bridging are deferred.

Provider-hosted MCP descriptors remain an experimental provider option. They
are separate from direct connections owned by `praval.mcp.MCPClient`.

## Quality and Build Changes

- Every prior expected-failure cause is fixed; strict xfail handling is on.
- A beginner-first 13-part Jupyter course now explains Agent, Reef, Spore,
  handlers, routing, lifecycle, feedback, fan-out/fan-in, tools, memory,
  ModelRuntime, HITL, MCP, and real voice/multimodal flows. Optional under-the-hood
  sections preserve depth for experienced readers. Four architecture-focused
  capstones are maintained and certified rather than retained as reference-only
  historical material.
- The capstones now cover common agent-heavy domains in depth: Research
  Intelligence, Customer Support Resolution, Software Release Readiness, and an
  AI Marketing Studio. The first three execute deterministically in normal CI;
  Marketing Studio is a protected-live OpenAI workflow with real screenshot
  analysis, structured responses, approval-protected claims, persisted HITL
  interruption/resume, campaign memory, and a bounded learning pass.
- Manifest v2 records prerequisites, estimated time, and learning level for all
  17 notebooks. Exact-wheel certification runs ten offline notebooks in normal
  CI, RabbitMQ/OTLP and official-SDK MCP notebooks in service CI, and five live
  provider, Qdrant, HITL, STT, and TTS notebooks only through the protected
  manual live workflow.
- Complete-package statement coverage must reach 90%, with focused floors for
  Reef, transport, instrumentation, exporters, remote storage, and MCP.
- Mypy, Black, isort, flake8, Sphinx warnings, package metadata, distribution
  contents, and the 3 MiB sdist limit are fatal release gates.
- Linux tests cover Python 3.9 through 3.13. MCP contract tests run against the
  official SDK on Python 3.13. Windows and macOS install the exact wheel in a
  clean environment.
- Builds use a commit-derived `SOURCE_DATE_EPOCH` and must reproduce byte for
  byte.
- OTLP/JSON export now preserves trace and span IDs as the hex strings required
  by the protocol, verified against a real OpenTelemetry collector.
- The tag workflow retrieves the successful artifact for the tagged main
  commit. It does not rebuild, and it pauses at the protected `pypi`
  environment before trusted publishing.

## Explicitly Experimental

Provider-hosted tools, provider-hosted MCP descriptors, and computer-use
descriptors require `allow_experimental_tools=True` plus provider-specific
`experimental_tools`. They are not stable cross-provider capabilities.

## Deferred to 0.9

- Realtime WebRTC/WebSocket model and voice sessions.
- Streaming audio conversations.
- Raw binary Spore transport.
- MCP resources/prompts, MCP server hosting, managed OAuth, richer result
  content, and optional sync bridging.
- Provider SDK dependency extras and internal module decomposition.

## Migration Notes

- `Agent.chat()` remains a string-returning compatibility API. Use
  `generate()`, `agenerate()`, `stream()`, or `astream()` for neutral runtime
  types and events.
- MCP handlers require `agenerate()` or `astream()`. Sync calls fail clearly if
  they encounter an async-only tool.
- Changing embedding provider, model, or dimensions requires re-embedding into
  a new or rebuilt collection.
- Local OpenAI-compatible servers advertise text and streaming only by default;
  opt into richer capabilities only when the selected server/model supports
  them.
- Knowledge-only Spores retain the legacy AMQP body. Use JSON-safe content
  parts or storage references for multimodal data.

## Required Release Evidence

The committed notes intentionally contain no copied test counts, coverage
percentages, durations, artifact sizes, or hashes. Those values are generated
for the exact commit and attached to the release:

- `build-manifest.json` and `SHA256SUMS` identify the wheel and sdist.
- coverage and API-surface reports record complete-package and documentation
  gates.
- offline and service demo reports identify the exact installed wheel.
- the protected live certification records provider/model calls, real
  model-generated HITL, embeddings, multimodal input, and the
  STT-to-agent-to-TTS-to-STT voice round trip.
- the documentation manifest identifies the commit, wheel hash, installed
  version, and generated HTML tree hash.

Publication is blocked until normal `main` CI and protected live certification
both pass for the same commit and wheel. Praval Research remains optional
downstream integration evidence rather than a framework release gate.

The corresponding `praval-ai` update is prepared from the exact-wheel
documentation artifact and merged only after PyPI reports this release.
