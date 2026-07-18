# Providers

Praval provider adapters translate provider wire formats into
`praval.models.ModelRequest`, `ModelResponse`, and `ModelEvent` contracts.
Adapters should not own policy. Runtime policy belongs in `ModelRuntime`.

## Provider Names

Use explicit provider and model names:

```python
from praval import Agent

agent = Agent("assistant", provider="anthropic", model="claude-sonnet-5")
```

Compact model strings remain supported:

```python
agent = Agent("assistant", model="openai:gpt-5.4-mini")
```

Praval's registry includes release-time profiles for OpenAI `gpt-5.4`,
`gpt-5.4-mini`, `gpt-5.4-nano`, and `gpt-5.5`; Anthropic
`claude-sonnet-5`, `claude-fable-5`, `claude-opus-4-8`, and
`claude-haiku-4-5`; Cohere `command-a-03-2025`; and Gemini
`gemini-3.5-flash`, `gemini-3.1-flash-lite`, and
`gemini-3.1-pro-preview`. The names were checked against the official model
catalogs for the 0.8.0 release. They are package metadata, not a live catalog.
Use each provider's model-list API when availability must be checked at runtime.

## Capability Matrix

Legend:

| Mark | Meaning |
| --- | --- |
| Native | Implemented directly by the provider endpoint. |
| Emulated | Praval can provide a fallback or wrapper. |
| Unsupported | Runtime rejects the request by default. |
| Depends | Server or model dependent. Enable with explicit profiles. |

| Provider | Text | Streaming | Tools | Structured Output | Image | File | Audio/Video Input | Transcription | Speech | Reasoning | Local |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OpenAI | Native | Native | Native | Native | Native | Unsupported by default | Unsupported by default | Native | Native | Native | No |
| Anthropic | Native | Native | Native | Native | Native | Unsupported by default | Unsupported | Unsupported | Unsupported | Native | No |
| Cohere | Native | Unsupported | Native | Unsupported | Unsupported | Unsupported | Unsupported | Unsupported | Unsupported | Unsupported | No |
| Gemini | Native | Native | Native | Native | Native | Native | Native | Unsupported | Unsupported | Native | No |
| Ollama | Native | Native | Unsupported by default | Depends | Depends | Unsupported by default | Depends | Unsupported | Unsupported | Depends | Yes |
| vLLM | Native | Native | Unsupported by default | Depends | Depends | Unsupported by default | Depends | Unsupported | Unsupported | Depends | Yes |
| LM Studio | Native | Native | Unsupported by default | Depends | Depends | Unsupported by default | Depends | Unsupported | Unsupported | Depends | Yes |
| llama.cpp | Native | Native | Unsupported by default | Depends | Depends | Unsupported by default | Depends | Unsupported | Unsupported | Depends | Yes |
| Generic OpenAI-compatible | Native | Native | Depends | Depends | Depends | Depends | Depends | Unsupported by default | Unsupported by default | Depends | Depends |

"Tools" in this table means client/function tools. `ModelRuntime` parses the
provider's tool calls, executes registered Praval tools, emits normalized
`tool_call` and `tool_result` events, submits results, and continues until the
model returns final text. This stable loop is implemented for OpenAI,
Anthropic, Cohere, and Gemini. HITL-gated tools suspend with provider-neutral
continuation state and can resume after approval, editing, or rejection.

## Provider-Hosted Tools and MCP Descriptors

Provider-hosted tools, provider-hosted MCP descriptors, and computer-use
descriptors are not stable cross-provider capabilities in 0.8.0. OpenAI
Responses and Anthropic Messages can receive raw experimental descriptors only
through an explicit per-call opt-in:

```python
response = agent.generate(
    "Use the provider-hosted tool when useful.",
    provider_options={
        "allow_experimental_tools": True,
        "experimental_tools": [{"type": "web_search"}],
    },
)
```

The runtime rejects this option for other providers, rejects it on OpenAI Chat
Completions, and rejects nested credential-bearing fields. Raw descriptors are
provider-specific and may change without Praval compatibility guarantees.

This is distinct from the first-class tools-only client in `praval.mcp`. That
client owns a stdio or Streamable HTTP connection and registers discovered
tools through Praval's normal provider-neutral runtime. See [MCP Tool
Clients](mcp.md). Praval does not convert provider-hosted descriptors into
client connections.

Local OpenAI-compatible profiles are intentionally conservative. Richer support
requires an explicit capability override or registered profile, because local
servers differ substantially by version, model, and command-line flags.

## Registry Inspection

```python
from praval import get_provider_registry

registry = get_provider_registry()
print(registry.list_providers())
print(registry.resolve_profile("ollama", "llama3"))
print(registry.resolve_capabilities("openai", "gpt-5.4-mini"))
```

The registry resolves provider aliases such as `ollama`, `vllm`, `lmstudio`,
`llama-cpp`, and `local` to the OpenAI-compatible provider implementation while
preserving alias-specific profiles.

## Provider Profile Fields

Profiles can include provider, model, endpoint, local preset, context window,
output token limits, default parameters, unsupported combinations, downgrade
policy, and notes. The downgrade policy is `error` by default: a declared but
unsupported feature should fail before execution.

Provider catalogs should be audited against provider documentation before a
release and captured in tests. The 0.8.0 audit used the official
[OpenAI model catalog](https://developers.openai.com/api/docs/models/all),
[Claude model overview](https://platform.claude.com/docs/en/about-claude/models/overview),
[Gemini model catalog](https://ai.google.dev/gemini-api/docs/models), and
[Cohere model catalog](https://docs.cohere.com/docs/models).

When a provider releases a new model, add or update a `ProviderProfile`, record
the endpoint and capability assumptions, and add a registry test. Do not add
placeholder model names to docs or defaults.
