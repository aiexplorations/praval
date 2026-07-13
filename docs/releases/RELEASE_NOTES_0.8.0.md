# Praval 0.8.0 Release Candidate

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
- A 13-part visual Jupyter course now shows agent stages, Reef routing, Spore
  payloads, feedback loops, fan-out/fan-in, tools, memory, ModelRuntime, HITL,
  MCP, and real voice/multimodal flows. Four longer historical notebooks are
  retained as catalogued case studies.
- Exact-wheel notebook certification runs seven keyless notebooks in normal
  CI, RabbitMQ/OTLP and official-SDK MCP notebooks in service CI, and live
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

## Candidate Validation Evidence

- Current full local suite: `1682 passed, 91 skipped`, with zero failures, XFAIL,
  or XPASS.
- Complete-package statement coverage: `92.90%`; every focused floor passed.
- Mypy passed across 72 source modules after replacing the broad provider
  exemption with explicit legacy-module exemptions.
- The wheel and normalized sdist reproduced byte for byte across consecutive
  isolated builds. Clean minimal and MCP-extra wheel installations passed.
- The local candidate wheel is about 220 KB and the sdist is about 2.2 MB,
  below the 3 MiB release cap. Exact release hashes remain commit-derived CI
  evidence and are intentionally not recorded before that artifact exists.

The final wheel hash, sdist hash, Praval Research regression result, DMG hash,
and checksum-manifest verification will be recorded here only after the exact
CI artifact completes downstream release validation. Until then this document
describes a release candidate, not a published final release.
