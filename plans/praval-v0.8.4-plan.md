# Praval v0.8.4 plan: reliable execution and accurate usage

Status: draft for review, 2026-10-07. Written against `main` at `2cfdd5e` (v0.8.3).

Roadmap: `plans/praval-roadmap.md`. Metering spec: `plans/praval-v0.8.4-usage-metering.md`.

## Objective

A run with tools works on every supported adapter, keeps its full conversation, never repeats a completed side effect, reports typed failures, and reports what it used. Reasoning controls are the last work package and can move to v0.8.5 without affecting the rest.

## Branch and version

- Work on `release/v0.8.4` from `main`. Each work package below is one PR into that branch, in the order given; the branch merges to `main` as the release candidate.
- The uncommitted `local_preset` change (`src/praval/providers/openai.py`, `tests/test_local_provider_options.py`) is the first commit on the branch.
- Patch release by repository convention: `pyproject.toml` version `0.8.4`, `CHANGELOG.md` with Added, Changed and Fixed sections, `docs/releases/RELEASE_NOTES_0.8.4.md`, and updated docs. Release follows `RELEASE.md` exactly: the CI wheel from `main` is the only artifact uploaded.

## Work packages

### WP1. Provider continuation (release blocker)

Problem: `_orchestrate_tool_calls` passes each continuation the original request plus the latest round only (`src/praval/model_runtime.py:1172`). OpenAI Chat Completions (`openai.py:628`) and Anthropic (`anthropic.py:200`) rebuild their messages from that, so earlier rounds are lost. Gemini keeps earlier rounds but rebuilds `functionCall` parts from name and arguments (`gemini.py:467`), dropping thought signatures and any text in the same turn.

Change:

- Each adapter keeps the cumulative provider transcript in the response's continuation state: the messages (or `contents`) it actually sent, plus the assistant turn it received. `continue_with_tool_results` extends that transcript instead of rebuilding from the request. OpenAI Responses keeps `previous_response_id`.
- Gemini appends the candidate's `content` exactly as received (all parts, in order, with `thoughtSignature` and any other fields) rather than reconstructing parts.
- The transcript must survive HITL persistence. `resume_tool_flow` and `resume_tool_flow_async` restore it from the stored continuation state; stored state written by v0.8.3 still resumes (with the v0.8.3 behaviour) rather than failing.
- Cohere's continuation is audited for the same defect and fixed if present.

Tests: deterministic provider fixtures that assert the exact request sent on each round. Three dependent rounds; the same tool called twice; several calls in one round; Gemini signed parts round-tripped byte for byte; HITL pause and resume, including across a process restart, preserves transcript and signatures. Live: a three-round dependent tool run on each adapter, including `gemini-3.5-flash`.

Before the fix ships, the Gemini HTTP 400 is reproduced and shown to be fixed by returning signatures. If it is not, the 400 is tracked separately and the release notes say so.

### WP2. Structured provider errors and per-call retry

Problem: retry wraps the initial call and the whole tool loop (`model_runtime.py:1077`, `:1112`), so a failure in a later round re-runs earlier tools. The tool-round limit raises `ProviderError` inside that block and is retried too. `ProviderError` carries only a message, and the Gemini adapter discards the response body. The OpenAI and Anthropic SDKs also retry internally (default `max_retries=2`; Praval does not set it), invisibly to Praval.

Change:

- `ProviderError` gains `provider`, `model`, `operation`, `status_code`, `error_code`, `request_id`, `retryable` and `retry_after_seconds`, with a sanitised message and the original exception as `__cause__`. Subclasses: `AuthenticationError`, `InvalidRequestError`, `QuotaExceededError`, `RateLimitError`, `ProviderUnavailableError`, `TransportError`. All subclass `ProviderError`, so existing `except ProviderError` code is unaffected. The tool-round limit gets its own `ToolRoundLimitError`, which is never retried.
- Each adapter maps its SDK or HTTP errors to these types and keeps the response body (redacted) for diagnostics.
- One private call-site helper in `ModelRuntime` wraps every provider request: the initial invoke, each continuation, resume, and streaming start. It retries only that request, only when `retryable`, with bounded exponential backoff and jitter, honouring `retry_after_seconds` up to a cap. A retried continuation resends the tool results already computed. The same helper is where WP5 meters each request.
- Praval owns retries: adapters construct SDK clients with `max_retries=0`. An explicit `max_retries` in provider options still wins, and the docs say such retries are not individually metered.

Tests: a failure injected after a side-effecting tool runs leaves the side effect executed exactly once, in sync, async, streaming and resumed flows. Each error type is produced from recorded SDK and HTTP failures per adapter. `Retry-After` is honoured. Non-retryable errors are raised at once. The round limit is not retried.

### WP3. Typed tool boundary

Problem: sync execution returns `str(result)` (`model_runtime.py:375`) and errors are recognised by an `"Error:"` prefix (`model_runtime.py:1606`), so a `ToolResult(is_error=True)` from a sync tool counts as success. Model-supplied arguments reach handlers unvalidated.

Change:

- Sync and async execution return the same `ToolResult`; a handler's returned `ToolResult` is kept as is. Exceptions become `is_error=True` results with the exception type. The string-prefix check remains only for plain-string results, for compatibility.
- Arguments are validated before the handler runs. For Python tools, against the function signature through pydantic (already a dependency). For tools defined only by JSON Schema (MCP, external), see decision 3. A failure returns a structured error result naming the field and expected type, which goes back to the model as the tool result; Praval never rewrites the arguments itself.
- Opt-in local validation of structured responses (`response_schema` with `validate=True`): a response that does not parse or match raises a typed error instead of returning.

Tests: invalid arguments never invoke the handler; identical failures produce identical `ToolResult`s in sync and async paths; returned `ToolResult`s keep `is_error`; response validation rejects non-JSON and schema mismatches.

### WP4. Conversation state and per-call controls

Problem: `_trim_history` can drop the system message (`agent.py:220`); `stream` and `astream` never record the answer (`agent.py:584`); sync `generate` ignores `allowed_tool_names` and `additional_system_message`, which only `agenerate` honours (`agent.py:536`); unknown keyword arguments are silently ignored; `chat()` in `@agent` does not return at its timeout, because leaving the `ThreadPoolExecutor` block joins the worker (`decorators.py:594`).

Change:

- Trimming always keeps system messages and removes whole units (a user turn with its assistant reply, or a tool call with its results), never half of one.
- A successful stream commits the final answer to history and persisted state on its `final` event. A failed or interrupted stream records the user turn only, and this is documented.
- One shared function builds the runtime call from per-call options for `chat`, `generate`, `agenerate`, `stream` and `astream`, so they honour the same controls. Unknown keyword arguments log a warning naming the argument; they become errors in v0.8.5.
- `chat()`/`achat()` raise at their timeout without waiting for the worker; the default timeout becomes the agent's configured timeout instead of a fixed 10 seconds. The abandoned request still runs until it ends (cancellation is v0.8.5), and the docs say so.

Tests: system message survives trimming at every `max_history`; no orphaned tool results after trimming; the five entry points produce equal history for the same exchange; `allowed_tool_names` restricts tools in sync `generate`; a 10 ms `chat()` timeout returns within a small bound while the worker is still running.

### WP5. Usage metering

Implements `plans/praval-v0.8.4-usage-metering.md`, with these changes to the spec, made in the spec before work starts:

- **Meter every request Praval sends,** not every adapter call. The OpenAI empty-response retry (`openai.py:444`) makes two requests in one adapter call; adapters report each request they make to the meter through the WP2 helper's context.
- **Retry ownership** follows WP2: `attempt` counts Praval's retries of one request; SDK retries are off by default.
- **Partial accounting is explicit.** `UsageTotals` and `CostEstimate` gain `complete: bool`, false when any call failed, was interrupted or reported no usage.
- **Stable identities.** `ModelCall` gains `call_id` (UUID), `parent_run_id`, and `correlation_id` taken from a caller-set context value, so applications can persist records without double counting.
- **Request scopes for short-lived agents.** `track()` is the documented way to meter one application request across several agents (PravalClaw creates a fresh `Agent` per planner call), and `subscribe` is the hook for a durable sink.
- **Scope is chat-model usage.** Transcription, speech, image generation and embeddings are not metered in v0.8.4, and the docs say so.

Tests: as listed in the spec, plus two requests metered for one OpenAI empty-response retry, `complete=False` for failed and unreported calls, and unique `call_id`s across retries.

### WP6. Reasoning controls (movable to v0.8.5)

Problem: `chat()` cannot pass reasoning; `@agent` has no `reasoning` argument; Gemini rejects `effort` and maps only `thinkingBudget`, while Gemini 3 uses `thinkingLevel`; any reasoning config forces the OpenAI Responses API (`openai.py:546`), which local Chat Completions servers do not serve; Cohere exposes no reasoning; effort values are unchecked.

Change:

- `reasoning="none" | "low" | "medium" | "high"` (or a full `ReasoningConfig`) on `Agent`, `@agent`, `chat()`/`achat()` and every generate and stream method.
- The mapping is per model family, in the provider registry's model profiles: OpenAI `reasoning.effort` (Responses) and `reasoning_effort` (Chat Completions); Anthropic `output_config.effort` and `thinking`; Gemini 3 `thinkingLevel` and Gemini 2.5 `thinkingBudget`; Cohere thinking; local presets where the server supports it. Each entry is confirmed against a live call or the provider's current documentation, and the source is recorded in the profile.
- A level a model does not support raises an error naming the provider, model and accepted levels. `"none"` is accepted only where the model can actually disable thinking.
- An explicit endpoint choice is respected; reasoning no longer forces the Responses API.

Tests: per-family payload tests for each level; precise errors for unsupported levels; `chat()` passes reasoning through; a local preset sends `reasoning_effort` on Chat Completions. Live: one call per provider at two levels, with reasoning tokens visible in WP5's usage.

## Compatibility

- New error subclasses, `ToolResult` fields, `Usage` fields and keyword arguments are additions.
- Changed: `ModelResponse.usage` in tool runs becomes the run total (metering spec, decision 1); streamed answers now enter history; trimming keeps system messages; SDK-internal retries are off by default; `chat()` timeout now returns on time and defaults to the agent's timeout; sync `generate` now honours `allowed_tool_names`. Each is listed under "Changed" in the changelog.
- HITL continuation state from v0.8.3 still resumes.

## Release gate

Run against the CI-built wheel:

- three dependent tool rounds on every adapter, with exact request fixtures;
- a provider failure after a side effect does not repeat it (sync, async, stream, resume);
- Gemini signatures survive HITL pause, resume and restart;
- invalid tool arguments never reach a handler;
- the five agent entry points leave equal history;
- metered totals equal the sum of recorded requests, and `ExecutionObservation.usage` equals the meter's totals;
- existing suite passes with coverage at or above the current floor; `black`, `isort`, `flake8`, `mypy` clean.

Then, before tagging: live two-tool and three-round runs on OpenAI (Chat Completions and Responses), Anthropic, Gemini and Cohere, and representative PravalClaw container workflows on the candidate wheel. Anthropic and Cohere keys are needed for this.

## Decisions for review

1. **Transcript storage in continuation state.** Recommended: each adapter stores its own native transcript, since only the adapter knows its wire format (Gemini parts, Anthropic content blocks). Alternative: a provider-neutral transcript in the runtime, translated per call; cleaner in principle, but it is where signatures were lost.
2. **SDK retries off by default.** Recommended, so `attempt` and metering are exact. Alternative: leave SDK defaults and document that up to two hidden retries per request are possible.
3. **Validating JSON-Schema-only tools.** Recommended: add `jsonschema` as a core dependency for MCP and external tools. Alternative: validate only Python-signature tools in v0.8.4.
4. **Unknown keyword arguments.** Recommended: warn in v0.8.4, error in v0.8.5. Alternative: error now, which breaks callers passing extra arguments in a patch release.
5. **WP6 in or out.** Recommended: in, if WP1 to WP5 pass the gate without slipping; otherwise first item of v0.8.5.
