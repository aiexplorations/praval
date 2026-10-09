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
`gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-5.5`, `gpt-6-luna`, `gpt-6-sol`,
`gpt-6-astra`, and `gpt-6.1-sol`; Anthropic
`claude-sonnet-5`, `claude-fable-5`, `claude-opus-4-8`, and
`claude-haiku-4-5`, plus `claude-sonnet-5-5` and `claude-haiku-5-5`;
Cohere `command-a-03-2025`; and Gemini
`gemini-3.5-flash`, `gemini-3.1-flash-lite`, and
`gemini-3.1-pro-preview`, plus `gemini-3.6-flash`, `gemini-3.7-flash` and
`gemini-3.8-flash`. The names were checked against the official model
catalogs for the 0.8 release line. They are package metadata, not a live catalog.
Use each provider's model-list API when availability must be checked at runtime.

## Live Model Discovery

Discovery is explicit and does not run during imports:

```python
from praval.core.agent import AgentConfig
from praval.providers.registry import get_provider_registry

registry = get_provider_registry()
profiles = registry.discover_models("ollama", AgentConfig(provider="ollama"))
for profile in profiles:
    print(profile.model, profile.capabilities.tools, profile.context_window)
```

OpenAI, Anthropic, Gemini, Ollama and OpenRouter expose catalogue discovery.
The method registers returned profiles and preserves known reasoning mappings.
Profiles expose `context_window`, `max_output_tokens`, `supported_parameters`,
`pricing` and `metadata`. Refresh them when availability changes. Gemini limits
come from its model API; OpenRouter parameters, limits and price strings come
from its public catalogue. Budgets above discovered limits fail before inference.

Use `config={"provider_options": {"discover_model": True}}` to discover at
construction. Ollama reads `/api/show` capabilities instead of requiring manual
tool overrides. Its `metadata["loaded_context_window"]` differs from the model's
theoretical context. Set `required_context_tokens` in provider options to warn
when a loaded model falls below the application's requirement. The OpenAI endpoint
requires a Modelfile with `PARAMETER num_ctx` to increase that size. See
[Ollama context configuration](https://docs.ollama.com/api/openai-compatibility).
Separate local reasoning fields are preserved in assistant tool transcripts.

## OpenRouter

Set `OPENROUTER_API_KEY` and use `Agent("router", provider="openrouter",
model="vendor/model:variant")`. The default base URL is
`https://openrouter.ai/api/v1`. Full vendor/model IDs and variant suffixes remain
intact. Provider options accept `http_referer`, `app_title`, and a `routing` dict
such as `{"only": ["your-upstream"], "allow_fallbacks": False}`.

The adapter sends unified `reasoning` and always sets
`provider.require_parameters=true`, so upstreams must support requested controls.
HTTP 402 maps to `ProviderQuotaError`. Discover model-specific capabilities and
current prices. Attribution headers are client configuration. Pin upstream routing
when comparing evaluations. See
[OpenRouter routing](https://openrouter.ai/docs/guides/routing/provider-selection).

## Anthropic Prompt Caching

Set `provider_options={"prompt_caching": True}` for automatic ephemeral caching,
or pass `{"type": "ephemeral", "ttl": "1h"}` as the option value. The default TTL
is five minutes; caching remains opt-in. Parameters survive tool continuations and
streaming. Provider-reported cache reads and writes are included in usage. Cache
minimums and prices depend on the model; see
[Anthropic caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching).

## Cohere Request Timeouts

Cohere accepts Praval's configured and per-call `timeout` on both chat endpoints.
The adapter sends it through SDK `request_options`, including each tool
continuation. No provider-specific timeout option is needed.

Cohere v1 tools use native `parameter_definitions` with Python types such as
`int` and `bool`. Praval includes the full JSON Schema in the tool description
because v1 cannot represent its nested constraints natively, and validates
arguments against that original schema before running a handler. The v2
endpoint accepts native JSON Schema via `provider_options={"endpoint": "chat.v2"}`.

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
| Cohere | Native | Depends (emulated) | Native | Unsupported | Unsupported | Unsupported | Unsupported | Unsupported | Unsupported | Depends (v2) | No |
| Gemini | Native | Native | Native | Native | Native | Native | Native | Unsupported | Unsupported | Native | No |
| OpenRouter | Native | Native | Depends | Depends | Depends | Unsupported by default | Unsupported by default | Unsupported | Unsupported | Depends | No |
| Ollama | Native | Native | Unsupported by default | Depends | Depends | Unsupported by default | Depends | Unsupported | Unsupported | Depends | Yes |
| vLLM | Native | Native | Unsupported by default | Depends | Depends | Unsupported by default | Depends | Unsupported | Unsupported | Depends | Yes |
| LM Studio | Native | Native | Unsupported by default | Depends | Depends | Unsupported by default | Depends | Unsupported | Unsupported | Depends | Yes |
| llama.cpp | Native | Native | Unsupported by default | Depends | Depends | Unsupported by default | Depends | Unsupported | Unsupported | Depends | Yes |
| Generic OpenAI-compatible | Native | Native | Depends | Depends | Depends | Depends | Depends | Unsupported by default | Unsupported by default | Depends | Depends |

Cohere's default `command-a-03-2025` profile rejects streaming and reasoning.
The `command-a-reasoning-08-2025` profile supports portable reasoning on v2
and emulated streaming: the full response arrives before text events are emitted.
Selecting `chat.v2` alone does not enable unsupported model capabilities.

"Tools" in this table means client/function tools. `ModelRuntime` parses the
provider's tool calls, executes registered Praval tools, emits normalized
`tool_call` and `tool_result` events, submits results, and continues until the
model returns final text. This stable loop is implemented for OpenAI,
Anthropic, Cohere, Gemini, OpenRouter and compatible local servers with tools
enabled by discovery or explicit capabilities. Each continuation retains earlier
tool context in the provider's native form, including Gemini thought
signatures and Anthropic thinking blocks, so a tool that depends on an earlier
round's result keeps that context. HITL-gated tools suspend with
provider-neutral continuation state and can resume after approval, editing, or
rejection; the resumed run continues with the same full transcript. OpenAI
Responses may retain prior context by chaining response IDs instead of resending
the whole transcript. Turns that offer client tools buffer streaming output
until orchestration completes; see {doc}`streaming`.

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
| `ProviderInvalidResponseError` | The final response failed local structured-output validation (`validate_locally=True`): not JSON, or not matching the schema | No |

`except ProviderError` still catches all of them. Each error carries the fields
the provider reported: `provider`, `model`, `operation` (`invoke`, `continue`
or `stream`), `status_code`, `error_code` (for example `insufficient_quota`,
`overloaded_error` or Gemini's `RESOURCE_EXHAUSTED`), `request_id`,
`retryable` and `retry_after_seconds`. Gemini error bodies are read, redacted
and kept in the message. An exception the adapter does not recognise becomes a
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

The same policy covers provider requests made outside the runtime's tool loop:
OpenAI `transcribe` and `speak` (an audio file is rewound and resent whole; a
stream that cannot seek is not retried), and the follow-up request that each
adapter's legacy `generate()` tool flow sends after running tools, which is
also the request a HITL resume of a v0.8.3 suspended run ends with. Only that
follow-up is retried, never the tools; if it still fails, the adapter returns
the tool output as before.

SDK clients (`openai.OpenAI`, `anthropic.Anthropic`, `cohere.Client`, and the
OpenAI-compatible client) are built with `max_retries=0`, so SDK-internal
retries no longer multiply Praval's. To restore them, set
`provider_options={"max_retries": N}` in the agent configuration; the value is
used for client construction only and is not sent with requests.

## Gemini Authentication

The Gemini adapter and Gemini embeddings send the API key in the
`x-goog-api-key` request header. Earlier releases appended it to the URL as
`?key=...`, where any exception, log line or proxy that quoted the URL could
expose it. Surrounding whitespace, such as a trailing newline from an env
file, is stripped from the key. A custom `base_url` keeps working as long as
the proxy or gateway forwards the `x-goog-api-key` header to Google; one that
only forwarded query parameters needs that header added to its configuration.

The chat adapter reads the key from the variable named by `api_key_env`
(default `GEMINI_API_KEY`) or `GOOGLE_API_KEY`. With a custom `base_url` the
key is optional: when none is set (a gateway that injects its own
credentials), no header is sent. Embeddings read `provider_options["api_key"]`,
`GEMINI_API_KEY` or `GOOGLE_API_KEY` and require one of them.

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

## Portable Reasoning Levels

Set `reasoning="low"`, `"medium"`, `"high"`, or `"none"` on an agent or an
individual call. The decorator accepts the same default:

```python
from praval import Agent, agent, chat

assistant = Agent("assistant", model="openai:gpt-5.4", reasoning="medium")
answer = assistant.chat("Check this calculation", reasoning="high")

@agent("reviewer", model="anthropic:claude-sonnet-5", reasoning="low")
def reviewer(spore):
    return {"review": chat("Review the proposal", reasoning="high")}
```

Defaults may also be supplied in `config={"reasoning": "medium"}`. Per-call
values override that default on `chat`, `generate`, `agenerate`, `stream`, and
`astream`, including calls through decorator `chat` and `achat`. A string
normalizes to `ReasoningConfig(level=...)`. Dicts and existing
`ReasoningConfig(effort=..., budget_tokens=...)` controls remain supported;
explicit effort or budget overrides the mapped value.

Levels express intent, not equivalent compute or answer quality across models.
The model profile's `reasoning_levels` stores native mappings and
`reasoning_source` records their documentation. Unsupported levels fail before
a provider request with the provider, model, and accepted levels in the error.
Unknown models require a registered profile to use portable levels.

GPT-6 tool requests select the Responses API by default, including when no
reasoning level is configured. Explicit endpoint selection is preserved.
Luna and Sol support Chat Completions tools only with reasoning `none`;
Praval supplies `reasoning_effort="none"` for those tool requests when omitted.
Other GPT-6 Chat Completions tool combinations fail before dispatch and require
`provider_options={"endpoint": "responses"}`.
See the [OpenAI GPT-6 guide](https://developers.openai.com/api/docs/guides/latest-model).

GPT-5 and later numbered GPT families use `max_completion_tokens` on Chat
Completions and omit sampling parameters. Responses retains `max_output_tokens`
and also omits sampling parameters for these models, even without an explicit
reasoning setting. GPT-4 and custom names retain their existing parameter behavior.
Future model names do not automatically gain portable reasoning profiles.

OpenAI-compatible requests can recover once from an explicit HTTP 400 unsupported
sampling parameter or the `max_tokens` to `max_completion_tokens` rename. Successful
repairs are remembered per full model ID and endpoint in a bounded adapter-local
cache. Tools, reasoning, schemas and budgets remain intact. Recovery counts each
request and applies to streaming only before it opens. Set
`provider_options={"parameter_recovery": False}` to disable it. OpenRouter keeps
strict routing and does not negotiate away parameters. Applications may use
`config={"temperature": None}` to leave sampling unspecified.
Gemini HTTP 404 errors guide callers to select an available model from discovery.

| Model family | Mapping | Supported portable levels |
| --- | --- | --- |
| OpenAI GPT-5.1/5.2/5.4/5.5 | Responses `reasoning.effort`; Chat Completions `reasoning_effort` | none, low, medium, high |
| OpenAI GPT-6 Luna/Sol | Same effort parameters; reasoning with tools requires Responses | none, low, medium, high |
| OpenAI GPT-6 Astra/6.1 Sol | Same effort parameters; tools require Responses | low, medium, high |
| OpenAI GPT-5 and o1/o3/o4-mini | Same effort parameters | low, medium, high |
| Claude Sonnet 5, Opus 4.6/4.7/4.8, Sonnet 4.6 | `thinking.type=adaptive`, `output_config.effort`; none disables thinking | none, low, medium, high |
| Claude Fable 5 | Adaptive thinking and output effort | low, medium, high |
| Claude Sonnet 5.5 | Adaptive thinking and effort; none selects `between_tools` | none, low, medium, high |
| Claude Haiku 5.5 | Adaptive thinking and effort; none disables thinking | none, low, medium, high |
| Claude Haiku 4.5 and Sonnet 4.5 | Enabled thinking with budgets 1024/4096/8192; none disables thinking | none, low, medium, high |
| Gemini 3.5 Flash, 3.1 Flash-Lite and 3.1 Pro | `thinkingConfig.thinkingLevel` | low, medium, high |
| Gemini 3.6/3.7/3.8 Flash | `thinkingConfig.thinkingLevel` | low, medium, high |
| Gemini 2.5 Flash and Flash-Lite | `thinkingBudget`: 0/1024/4096/8192 | none, low, medium, high |
| Gemini 2.5 Pro | `thinkingBudget`: 1024/4096/8192 | low, medium, high |
| Cohere Command A Reasoning | v2 `thinking` with disabled or enabled and budgets 512/2048/8192 | none, low, medium, high |
| vLLM preset | Chat Completions `reasoning_effort` | low, medium, high; none for documented Gemma 4 profile |
| OpenRouter | Unified `reasoning.effort`; none sets `enabled=false` | none, low, medium, high when the model supports reasoning |

Budgets in this table are Praval's choices within the providers' documented
ranges. Give reasoning sufficient output space, for example
`config={"max_output_tokens": 16384}`. Claude manual thinking requires its output
limit to exceed the thinking budget; Praval checks this for portable budgets.
Gemini's output limit includes thinking tokens. Gemini 3's `minimal` setting
still permits thinking, so Praval rejects `none` for that family. Gemini 2.5
Pro and Claude Fable 5 also cannot disable thinking.

An explicit `provider_options={"endpoint": "chat.completions"}` stays on
OpenAI Chat Completions when reasoning is enabled. Portable OpenAI and Claude
requests omit sampling parameters that conflict with thinking and use provider
default sampling. Existing explicit provider controls keep their original
parameter behavior.

Cohere `command-a-reasoning-08-2025` uses the installed SDK's `ClientV2` because
v1 `Client.chat` has no `thinking` parameter. The normal Command A profile
retains v1. V2 reasoning preserves native thinking and tool-call blocks through
continuation and HITL state; returned content contains the text answer.
`stream` and `astream` on that profile replay the completed response rather
than use native streaming.

Mappings were checked on 2026-10-08 against [OpenAI reasoning](https://developers.openai.com/api/docs/guides/reasoning),
[Claude thinking](https://platform.claude.com/docs/en/build-with-claude/thinking-troubleshooting),
[Gemini generateContent thinking](https://ai.google.dev/gemini-api/docs/generate-content/thinking),
[Cohere reasoning](https://docs.cohere.com/docs/reasoning), and
[vLLM reasoning](https://docs.vllm.ai/en/latest/features/reasoning_outputs/).
Deterministic tests verify payloads; live model behavior requires separate
provider certification.
