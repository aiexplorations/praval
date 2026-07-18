# Praval 0.8.1

Praval 0.8.1 is the first supported release in the 0.8 line. It introduces the
provider-neutral runtime and learning resources prepared for 0.8, while
preserving the established Agent, decorated-agent, Reef, Spore, memory, HITL,
and observability APIs.

## Why there is no supported 0.8.0

Version 0.8.0 was briefly uploaded during release preparation, then withdrawn
before Praval created a matching Git tag and GitHub release. PyPI does not let
projects reuse a deleted release filename. Praval moved to 0.8.1 so the package,
tag, GitHub release, checksums, and documentation can all identify the same
tested artifact.

There is no user migration from 0.8.0 to 0.8.1. The 0.8.1 patch changes release
quality, diagnostics, and documentation. It does not intentionally change the
runtime behavior of the withdrawn 0.8.0 candidate.

## Highlights

- One provider-neutral `ModelRuntime` for OpenAI, Anthropic, Cohere, Gemini,
  and OpenAI-compatible servers.
- Direct `Agent` APIs for complete responses, sync and async streaming,
  structured output, tools, media, usage, and normalized errors.
- Reef and Spores remain Praval's sole native agent-to-agent system.
- Durable HITL approval, edit, reject, interruption, and resume for protected
  tool calls.
- Optional tools-only MCP clients for stdio and Streamable HTTP on Python 3.10
  and newer.
- Request-based OpenAI transcription and speech generation through
  `Agent.transcribe()` and `Agent.speak()`.
- Provider-neutral embeddings and explicit model and dimension compatibility.
- A 13-lesson visual notebook course and four substantial agent-team
  capstones.

## 0.8.1 quality changes

- `praval --version` shows the installed package version.
- `praval doctor` gives a readable installation report.
- `praval doctor --json` gives a stable machine-readable report.
- Diagnostics show the package path, install source, Python runtime, optional
  dependency availability, and provider environment presence without printing
  credential values.
- Builds and releases contain exactly one universal `py3-none-any` wheel.
- `dist/` rejects source distributions, JSON evidence, checksums, and any other
  extra files.
- Build evidence remains in `evidence/`, separate from the uploadable wheel.
- The tag workflow does not rebuild or upload. It checks that PyPI serves the
  exact wheel hash from successful `main` CI, then attaches that same wheel to
  the GitHub release.
- Paid live demos remain manual and optional. They never run on pushes or pull
  requests. Developers can run real HITL and STT to agent to TTS to STT checks
  with their own OpenAI key and configured model names.
- Reef and ReefChannel shutdown are idempotent. Explicit cleanup no longer
  causes a second backend close during interpreter finalization.
- Examples 002 and 003 use bounded correlated workflows and print collected
  results only after Reef completes, which keeps stages in order.

## Model execution and providers

`Agent.chat()` remains the plain-string compatibility API. Use
`generate()` or `agenerate()` for a `ModelResponse` with content, finish state,
provider metadata, usage, and tool information. Use `stream()` or `astream()`
for normalized events.

The runtime supports provider-constrained structured output. The JSON text is
returned through `ModelResponse.content`. Applications should parse and
validate it locally when they require their own schema guarantee.

OpenAI Responses routing, Gemini function calling, multimodal inputs, and
provider tool loops use the same neutral request path. Local presets exist for
Ollama, vLLM, LM Studio, llama.cpp, and generic OpenAI-compatible servers.
Their default capabilities are conservative. Applications should enable tools,
structured output, media, or embeddings only when the selected endpoint and
model support them.

## Collaboration, tools, and HITL

Reef provides in-process delivery and a distributed RabbitMQ backend. Redis is
a storage provider, not a Reef transport. Optional secure transport includes
AMQP, MQTT, and STOMP adapters.

Spores carry structured knowledge, identity, correlation, and JSON-safe media
or storage references. Async handlers are supported, and completion waits
replace timing sleeps in maintained workflows.

`Agent.add_tool_spec()` registers external JSON Schema tools in the same
registry used by decorated tools. HITL can persist an approval-protected call
to SQLite, accept approval, argument edits, or rejection, and resume a stored
continuation across a process boundary.

## MCP scope

`praval.mcp.MCPClient` consumes tools from local stdio and remote Streamable
HTTP servers. Discovered tools are namespaced, async-only, approval-gated by
default, traced, bounded by timeout and result size, and closed with the client
context. Text and structured results are supported.

The 0.8 line does not include MCP resources, prompts, server hosting, managed
OAuth, legacy SSE, sampling, elicitation, experimental tasks, binary or image
results, automatic reconnect, or sync event-loop bridging. Provider-hosted MCP
descriptors are a separate experimental provider capability.

## Memory, storage, and observability

Praval supports short-term, episodic, semantic, and long-term memory paths.
Embedding configuration is separate from chat model configuration. Changing an
embedding provider, model, or dimension requires a new or rebuilt collection.

Storage APIs are asynchronous and cover filesystem, PostgreSQL, Redis,
S3-compatible services, and Qdrant. The PDF extra uses `pypdf`.

Observability finalizes each span before storing it once. Console inspection,
SQLite storage, and OTLP HTTP export cover local and service-backed use. The
instrumentation manager initializes and resets idempotently.

## Learning resources

The README gives a route for direct agents, agent teams, tools, HITL, MCP,
memory, local models, voice, and complete systems. The notebook course teaches
the framework from Agent, Reef, Spore, and lifecycle basics through runtime,
MCP, HITL, and real voice.

The four capstones show larger systems:

- Research Intelligence Desk
- Customer Support Resolution Center
- Software Release Readiness Team
- AI Marketing Studio

The first three are deterministic and run in normal CI. The Marketing Studio
uses a real OpenAI model only when a developer or maintainer starts the optional
live workflow. Existing course video links remain available through the Praval
AI YouTube channel.

## Compatibility and migration

- Core Praval supports Python 3.9 through 3.13. The optional official MCP SDK
  requires Python 3.10 or newer.
- Existing `Agent.chat()`, decorated agents, Reef delivery, and top-level
  compatibility imports remain available.
- MCP handlers require `agenerate()` or `astream()`.
- `PravalApp` owns Agent and Reef cleanup. It is not a dependency-injection
  container and does not isolate the process-wide provider registry.
- Knowledge-only Spores preserve the legacy AMQP body. Use JSON-safe content
  parts or storage references for multimodal data.
- Applications that use `PyPDF2` alongside Praval's PDF extra should migrate
  to `pypdf`.

## Important boundaries

- Request-based STT and TTS are not persistent realtime model sessions.
- Provider capabilities depend on both the adapter and the selected model.
- Retries are explicit and provider-specific. Praval does not promise a hidden
  universal circuit breaker, storage fallback, or MCP reconnect layer.
- Provider-hosted tools, provider-hosted MCP descriptors, and computer-use
  descriptors remain experimental pass-through features.

Realtime WebRTC or WebSocket model sessions, streaming audio conversations,
raw binary Spore attachments, richer MCP content, MCP server hosting, managed
OAuth, optional sync MCP bridging, and internal module decomposition remain
future work.

## Release evidence

These notes do not copy volatile test counts, coverage percentages, durations,
artifact sizes, or hashes. The exact commit produces:

- `build-manifest.json` and `SHA256SUMS` for the sole wheel;
- coverage and public API surface reports;
- offline and service demo reports tied to the installed wheel; and
- a documentation manifest tied to the commit, wheel hash, installed version,
  and generated HTML tree.

Optional live runs add sanitized provider, model, HITL, multimodal, embedding,
STT, TTS, usage, and generated artifact evidence. This evidence is useful, but
it is not required to publish the framework patch.

The corresponding `praval-ai` update is built from the exact-wheel
documentation artifact and merged after PyPI reports 0.8.1.
