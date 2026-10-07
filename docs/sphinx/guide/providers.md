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
catalogs for the 0.8 release line. They are package metadata, not a live catalog.
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
Anthropic, Cohere, and Gemini. Every continuation resends all earlier tool
calls and results in the provider's native form, including Gemini thought
signatures and Anthropic thinking blocks, so a tool that depends on an earlier
round's result keeps that context. HITL-gated tools suspend with
provider-neutral continuation state and can resume after approval, editing, or
rejection; the resumed run continues with the same full transcript.

## Provider-Hosted Tools and MCP Descriptors

Provider-hosted tools, provider-hosted MCP descriptors, and computer-use
descriptors are not stable cross-provider capabilities in the 0.8 line. OpenAI
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

## Provider Errors and Retries

Every provider failure reaches the caller as a `ProviderError`, importable from
`praval`. Adapters map SDK and HTTP failures to a subclass, so callers can
branch on the kind of failure instead of parsing messages:

| Class | Raised for | Retried |
|---|---|---|
| `ProviderAuthenticationError` | 401, 403: bad key or missing permission | No |
| `ProviderInvalidRequestError` | 400, 404, 422 and other 4xx: the request was rejected | No |
| `ProviderQuotaError` | Exhausted quota or credit (OpenAI `insufficient_quota`, Gemini daily quota, HTTP 402) | No |
| `ProviderRateLimitError` | 429 throttling | Yes |
| `ProviderUnavailableError` | 5xx, Anthropic 529 overloaded, 409 conflict | Yes |
| `ProviderTransportError` | Connection failure or timeout, HTTP 408 | Yes |
| `ToolRoundLimitError` | The tool loop exceeded `max_tool_rounds` | No |

`except ProviderError` still catches all of them. Each error carries the fields
the provider reported: `provider`, `model`, `operation` (`invoke`, `continue`
or `stream`), `status_code`, `error_code` (for example `insufficient_quota`,
`overloaded_error` or Gemini's `RESOURCE_EXHAUSTED`), `request_id`,
`retryable` and `retry_after_seconds`. Gemini error bodies are read, redacted
and kept in the message; the request URL, which carries the API key, is never
copied into an error. An exception the adapter does not recognise becomes a
plain, non-retryable `ProviderError` with the original exception as its
`__cause__`.

```python
from praval import Agent, ProviderQuotaError, ProviderRateLimitError

agent = Agent("assistant", provider="openai", model="gpt-5.4-mini")
try:
    response = agent.generate("Summarise the release notes.")
except ProviderQuotaError as error:
    print(f"Out of quota ({error.error_code}); retrying will not help")
except ProviderRateLimitError as error:
    print(f"Still throttled after retries; wait {error.retry_after_seconds}s")
```

`ModelRuntime` owns retries. Each provider request (the initial call, each
tool-round continuation, the continuation after a HITL resume, and the start of
a native stream) is retried on its own when its error is retryable, up to the
agent's `retries` setting (default 2). Tools that already ran are never run
again: a failed round-2 continuation is resent with the same tool results.
The wait before each retry is the provider's `Retry-After` hint when present
(capped at 60 seconds); otherwise it is exponential backoff with full jitter,
starting at 0.5 seconds and capped at 30 seconds. A stream is retried only
before its first event reaches the caller. Each retry is recorded as a retry
fact on the execution observation with its real backoff.

SDK clients (`openai.OpenAI`, `anthropic.Anthropic`, `cohere.Client`, and the
OpenAI-compatible client) are built with `max_retries=0`, so SDK-internal
retries no longer multiply Praval's. To restore them, set
`provider_options={"max_retries": N}` in the agent configuration; the value is
used for client construction only and is not sent with requests.

## Provider Profile Fields

Profiles can include provider, model, endpoint, local preset, context window,
output token limits, default parameters, unsupported combinations, downgrade
policy, and notes. The downgrade policy is `error` by default: a declared but
unsupported feature should fail before execution.

Provider catalogs should be audited against provider documentation before a
release and captured in tests. The 0.8 audit used the official
[OpenAI model catalog](https://developers.openai.com/api/docs/models/all),
[Claude model overview](https://platform.claude.com/docs/en/about-claude/models/overview),
[Gemini model catalog](https://ai.google.dev/gemini-api/docs/models), and
[Cohere model catalog](https://docs.cohere.com/docs/models).

When a provider releases a new model, add or update a `ProviderProfile`, record
the endpoint and capability assumptions, and add a registry test. Do not add
placeholder model names to docs or defaults.
