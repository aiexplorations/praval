# Provider robustness in 0.8.4

The user requested that Claude's provider feedback strengthen the pending release.
Provider transport and deterministic contracts belong in Praval; model choice,
coding prompts and semantic tool decisions remain with applications and agents.

| Feedback | Change or evidence |
| --- | --- |
| OpenAI name fragility | Numbered model constraints and one HTTP 400 recovery. Never remove tools, reasoning, schemas or budgets. Cache successful repairs per adapter/model/endpoint and meter every request. |
| Anthropic caching | Opt-in automatic ephemeral caching with 5m/1h TTLs, preserved in continuation and streaming parameters. |
| Anthropic models | Documented Sonnet 5.5 and Haiku 5.5 profiles, correct between_tools/disabled mappings and sampling omission. Explicit model-list discovery. |
| Gemini 3.6 to 3.8 | Documented reasoning profiles; discovery reads input and output limits. |
| Gemini unavailable models | Non-retryable HTTP 404 adds availability guidance. Availability can vary by endpoint and key; do not assert universal retirement. |
| Flash-Lite repeated calls | Existing tests preserve histories, distinct IDs and repeated calls. Live certificates require ordered dependent calls. Intentional repeats remain agent-owned; no argument-based deduplication. |
| Ollama capabilities | Tags/show profiles expose tools, vision, thinking and model context. Discovery registers profiles without manual tool overrides. |
| Ollama context | Loaded context is separate from the model maximum. Warn against application requirements; reject excessive output budgets. OpenAI endpoint context requires num_ctx in a Modelfile. |
| Ollama thinking | Preserve separate reasoning fields in assistant tool transcripts. |
| OpenRouter | Dedicated key/base URL/attribution, unified reasoning, intact vendor/model:variant IDs, strict require_parameters routing and typed HTTP 402 quota errors. |
| OpenRouter metadata | Public catalogue supplies supported parameters, limits and price strings. No runtime prices are hard-coded. |
| OpenRouter charged cost | Per-request reported_cost_usd and exact meter/response aggregates, separate from caller estimates. Missing reports remain explicit. |
| Release checks | Independent provider selection in live_provider_tools.py and GPT-6 Luna endpoint/reasoning checks, both registered for exact-wheel certification. |
| Existing Python 3.10 CI failure | Agent cleanup snapshots the existing Reef without taking its initialization lock. A deterministic finalizer/thread-start regression covers the observed deadlock. |

Discovery is explicit through ProviderRegistry.discover_models(provider, config)
or provider_options={"discover_model": True} at construction. It never runs on
import. Profiles remain snapshots until refreshed. Requested discovery must
succeed rather than quietly enabling capabilities. Limits are validated, not
silently clamped. AgentConfig(temperature=None) leaves sampling unspecified.

Praval Code changes require its repository: provider/base URL/key mapping, setup
and model picker, context/pricing display, output budgets, shorter local prompts
and tool sets, doctor checks and small/local versus hosted evaluations. Praval
exposes the contracts those changes need. Gemini quota and missing inference keys
remain external validation constraints.

Validation combines deterministic SDK/HTTP fixtures, continuation and metering,
CI-equivalent checks, live catalogue discovery and available live tool runs.
Editable-source checks do not replace exact main-CI wheel certification.

Official references checked 2026-10-08:

- https://developers.openai.com/api/docs/models/gpt-6-luna
- https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- https://platform.claude.com/docs/en/models/sonnet-5-5/migration-guide
- https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide
- https://ai.google.dev/api/models
- https://ai.google.dev/gemini-api/docs/latest-model
- https://docs.ollama.com/api/openai-compatibility
- https://openrouter.ai/docs/api-reference/models/get-models
- https://openrouter.ai/docs/guides/routing/provider-selection
- https://openrouter.ai/docs/guides/best-practices/reasoning-tokens
