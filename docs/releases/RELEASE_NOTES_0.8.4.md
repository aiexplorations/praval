# Praval 0.8.4

Released October 9, 2026. Supports Python 3.10 through 3.14.

This release strengthens model execution, provider continuation, request retries,
conversation state and approval recovery. Usage metering and portable reasoning
controls are included. Jev decision-model support remains planned for v0.8.5.

## Model execution

Provider continuation retains prior tool calls, results and native reasoning
state. OpenAI Responses chains preserve response identity; Anthropic signed
thinking and Gemini thought signatures survive tool rounds. All configured system
messages are preserved across provider serializers.

Full object JSON Schemas registered through `Agent.add_tool_spec`, including
MCP input schemas, now survive the Anthropic, Gemini and Cohere callable-tool
paths. Anthropic and Cohere no longer crash before sending these requests;
Gemini uses `parametersJsonSchema` to preserve actual argument names, nested
types and constraints. Empty object schemas also survive runtime normalization.
Cohere v1 translates argument names, types and required flags into its native
`parameter_definitions`; the complete schema remains in the tool description
and runtime validation. Cohere v2 sends native JSON Schema. Cohere timeouts use
SDK `request_options` on initial calls and every continuation.
The contract matrix inspects each dependent request across public entry points,
and live tool checks require integer and boolean arguments with usage accounting.

Retries apply to individual provider requests, with typed errors, bounded backoff
and SDK retry control. Completed tool results are reused during approval recovery,
including later rounds and a second approval gate. Replay protection starts after
the result commits to SQLite. Applications need idempotency for a crash between an
external effect and that commit.

## Usage and reasoning

`agent.usage` and `praval.metering.UsageMeter.track()` expose actual request counts,
reported token totals and caller-owned cost estimates. Records are content-free and
bounded, while lifetime totals remain exact. Final response usage aggregates tool
rounds and persisted approval history; failed requests and missing usage keep
completeness false. Streaming adds `model_call` events.

Portable reasoning levels map through documented model profiles. Defaults can be
set on an Agent or decorator and overridden per call. Unsupported levels fail
before dispatch. Explicit OpenAI endpoint selection is preserved. Cohere reasoning
uses its v2 API; legacy v1 chat remains available.

GPT-6 Luna, Sol, Astra and 6.1 Sol have model-specific reasoning profiles.
Numbered GPT-5 and later models use the supported Chat Completions token-limit
parameter and omit sampling controls on both OpenAI endpoints. GPT-6 tool requests
select Responses by default. Explicit Luna/Sol Chat Completions tools use reasoning
`none`; unsupported Chat Completions tool combinations fail before dispatch.

## Compatibility and validation

OpenAI requests recover once from explicit unsupported sampling parameters or the
documented token-limit rename, preserving tools and reasoning. Successful repairs
are remembered in a bounded adapter-local cache. Each actual request is metered.
Recovery occurs before a stream opens and can be disabled.

Agent cleanup snapshots an existing Reef without creating it or waiting for its
global initialization lock. This avoids the finalizer/thread-start deadlock
observed in the candidate's Python 3.10 CI run.

Explicit model discovery reads current names and metadata from OpenAI, Anthropic,
Gemini, Ollama and OpenRouter. Ollama profiles read declared tools, vision and
thinking, and separate loaded context from the model maximum. Discovered output
limits are validated before dispatch. `temperature=None` leaves sampling
unspecified. Gemini 404 errors include availability guidance.

Anthropic adds opt-in automatic caching and Sonnet/Haiku 5.5 profiles. Gemini adds
3.6/3.7/3.8 Flash reasoning profiles. OpenRouter adds unified reasoning, intact
model/variant IDs, strict parameter routing, attribution headers and exact
provider-reported USD charges. Catalogue prices and caller-supplied estimates
remain separate from reported charges.

See [migration guidance](../sphinx/guide/v084-migration.md) for history, timeout,
retry, event and schema-validation changes. External schema `patternProperties`
and nested dialect changes are rejected; ordinary external patterns have matching
timeouts and size limits. Trusted response schemas retain existing semantics.

Deterministic provider fixtures and integration matrices cover public entry
points, dependent tools, retries, approval restart, Reef concurrency, observations
and evaluation. Normal CI certifies the exact installed wheel, including offline
and service-backed demos, documentation, reproducibility and supported Python
versions. Generated release evidence records counts and artifact hashes.

Live candidate checks exercised OpenAI GPT-5.4 Mini and GPT-6 Luna, Gemini
Flash-Lite, Cohere v1 and v2, discovered Ollama models, and OpenRouter routes for
OpenAI, Gemini and Anthropic Claude Haiku. These checks covered dependent tools
and usage reconciliation. They do not establish compatibility with every model
or account. Direct Anthropic inference was deferred because the account lacked
credit; Gemini 3.5 continuation was blocked by account quota. Offline adapter
contracts cover those paths, and the limitations remain recorded in validation
evidence.

Install the base package with `pip install praval==0.8.4`. Optional features use
extras, for example `pip install "praval[mcp]==0.8.4"`; all extras share the same
universal wheel. The GitHub release and PyPI use the wheel produced by successful
main CI, as required by [RELEASE.md](../../RELEASE.md).
