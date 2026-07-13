# Praval Model Runtime and API Rearchitecture Plan

## Summary

- Keep Praval's public identity: decorator-first agents, Reef/Spore peer
  messaging, first-class tools, memory, HITL, and observability.
- Move model execution into a provider-neutral `ModelRuntime`.
- Treat providers as wire adapters, not owners of tools, HITL, retries,
  streaming, response parsing, or observability.
- Support modern OpenAI Responses, current Claude Messages features, Gemini,
  and local OpenAI-compatible runtimes through capability-aware adapters.

## Re-Research Findings

- `AgentConfig` has only provider, temperature, max tokens, and system message;
  model choice, base URL, structured output, reasoning, streaming, and local
  LLM config are missing from the core API.
- Provider selection is API-key driven and exact-match only. Existing providers
  hard-code stale defaults and duplicate tool/HITL logic.
- `HITLRuntime` and `ToolRegistry` are useful foundations and should be reused.
- `@agent` should remain the primary simple interface, but its internal context
  and lifecycle wiring should be modernized.
- `threading.local()` and per-call executors are weak primitives for async agent
  isolation.
- Reef already has a facade/core split and backends; the major gap is explicit
  app ownership and a richer envelope.
- Observability exists, but runtime-level spans should replace provider-specific
  monkey-patching for new model execution.
- Tests are broad but provider-internal, with weak async assertions and current
  observability xfails.

## Public API and Types

- Add `praval.models` with Pydantic v2 models and `typing.Protocol`
  interfaces:
  - `ModelRequest`, `ModelResponse`, `ModelEvent`, `ModelMessage`,
    `ContentPart`
  - `ToolSpec`, `ToolCall`, `ToolResult`
  - `Usage`, `ReasoningConfig`, `StructuredOutputConfig`,
    `ProviderCapabilities`, `ProviderProfile`
  - `ProviderAdapter`
- Expand `AgentConfig` with model/provider/base URL/API key env/timeout/retries,
  structured output, reasoning, streaming, store/cache, strict tools, and
  provider options.
- Preserve `Agent.chat(message) -> str` and module-level `chat()` as
  compatibility wrappers.
- Add richer agent APIs: `generate`, `stream`, `agenerate`, and `astream`.
- Resolve model settings in this order: explicit config, decorator arguments,
  environment defaults, then legacy API-key detection.
- Accept both split provider/model fields and compact `provider:model` strings.

## Architecture Changes

- Create `ModelRuntime` as the single owner of model invocation, streaming event
  normalization, retries/timeouts, tool dispatch, HITL interruption/resume,
  structured output validation, usage accounting, and observability spans.
- Convert existing providers into adapters that translate neutral requests to
  provider wire formats and translate provider responses back to neutral
  responses/events.
- Add `ProviderRegistry` with built-ins for OpenAI, Anthropic, Cohere, Gemini,
  OpenAI-compatible endpoints, and local presets for Ollama, vLLM, LM Studio,
  and llama.cpp.
- Make local LLM support first-class through an OpenAI-compatible adapter with
  configurable base URL, dummy local API key support, endpoint mode, and explicit
  capability configuration.
- Reuse `ToolRegistry`; add a `ToolSpec` adapter for JSON Schema generation from
  type hints, Pydantic models, and existing metadata.
- Move HITL continuation state to a provider-independent runtime state with
  idempotent resume and async tool support.
- Introduce `PravalApp` as explicit owner for Reef, registry, model runtime,
  memory, and observability while keeping global compatibility shims.
- Replace decorator thread-local context with `contextvars`.
- Add `SporeV2` compatibility fields while preserving `Spore.knowledge`.
- Separate chat model config from embedding model config in memory/RAG paths.

## Provider Feature Updates

- OpenAI: prefer Responses API for new requests, keep Chat Completions for
  legacy/local compatibility, and expose model profiles plus reasoning, tools,
  structured outputs, multimodal inputs, MCP/built-in tools, and state options.
- Anthropic: update defaults and support tools, strict tools, server tools, MCP,
  prompt caching, files/PDF/vision, thinking controls, and structured outputs.
- Gemini: add native Gemini adapter for models, thinking, structured output,
  function calling, Live capability metadata, and embeddings.
- Local runtimes: support Ollama, vLLM, LM Studio, and llama.cpp through
  OpenAI-compatible HTTP endpoints.
- Provider-hosted tools such as web search, file search, code execution, MCP,
  and computer-use style tools must be opt-in per agent or request.

## Implementation Sequence

1. Add model contracts, provider registry, expanded config, and compatibility
   wrappers without changing legacy behavior.
2. Build `ModelRuntime` and move tool execution, HITL, usage, retries, and
   runtime spans into it.
3. Rewrite OpenAI and Anthropic adapters on the new contract; keep old provider
   classes as wrappers.
4. Add OpenAI-compatible local provider support and native Gemini support.
5. Add streaming, structured outputs, multimodal content parts, and provider
   feature checks.
6. Introduce `PravalApp`, contextvars, and `SporeV2` migration shims.
7. Update README, docs, examples, generated docs, changelog, and migration
   guide.

## Expanded Test Envelope

- Add provider contract tests and fake OpenAI-compatible HTTP server tests.
- Add backward compatibility tests for `Agent.chat()`, `chat()`, `@agent`,
  `@tool`, `start_agents()`, `get_reef()`, and legacy provider imports.
- Add tests for streaming, structured output, tool/HITL, local providers,
  multimodal content, Reef/Spore, context isolation, observability, and security.
- Remove weak placeholder assertions and current observability xfails where
  runtime instrumentation replaces monkey-patching.
- New modules must pass mypy without broad `ignore_errors`.
- Keep `make test`, `make lint`, `make type-check`, and `make build` green.

## Assumptions

- Compatibility remains the default; breaking removals wait for a later major
  release.
- `@agent` remains the simple primary API.
- Local LLM support means HTTP-compatible servers, not launching inference
  engines.
- Model profiles should be data-driven and easy to update.
- Provider-specific power features should flow through neutral capabilities
  first, with `provider_options` as the escape hatch.
