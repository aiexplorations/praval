# Praval v0.8.4 plan: reliable execution and accurate usage

Status: in implementation, 2026-10-07; detail added after the outline was approved. Branch `release/v0.8.4`, from `main` at `2cfdd5e` (v0.8.3).

Roadmap: `plans/praval-roadmap.md`. Metering spec: `plans/praval-v0.8.4-usage-metering.md`. Conventions: `CLAUDE.md` / `AGENTS.md`.

## Objective

A run with tools works on every supported adapter, keeps its full conversation, never repeats a completed side effect, reports typed failures, and reports what it used. Reasoning controls are the last work package; they can move to v0.8.5 without affecting the rest.

## Decisions taken

1. Each adapter stores its own native transcript in `ModelResponse.metadata` (Gemini already does this with `gemini_contents`).
2. Praval owns retries; SDK clients are built with `max_retries=0` unless the caller sets it.
3. `jsonschema` becomes a core dependency, for tools that only have a JSON Schema (MCP, external) and for local response validation. Python tools are validated against their signatures with pydantic.
4. Unknown keyword arguments to agent entry points log a warning in v0.8.4 and become errors in v0.8.5.
5. Reasoning controls are in, as the last package.

## Baseline facts the work depends on

- `ModelRuntime` (`src/praval/model_runtime.py`) owns the tool loop: `_invoke_with_retries` / `_ainvoke_with_retries` (1077, 1112) call `_invoke_provider` then `_orchestrate_tool_calls[_async]` (1172, 1241), which calls the adapter's `continue_with_tool_results(request, current, round_results)` with the **original** request every round.
- HITL suspension serialises `request`, `response` (including `response.metadata` through `_json_safe`) and the call/result lists (`_runtime_continuation_state`, 1615). Anything an adapter puts in `metadata` as plain JSON survives pause, resume and restart. `resume_tool_flow[_async]` (1333, 1432) restores and continues.
- Streaming with tools (`stream`/`astream`, 528, 599) runs the full non-streaming tool loop and replays events afterwards.
- Tool execution: `execute_legacy_tool_call[_async]` (194, 268) → HITL runtime (`src/praval/hitl/runtime.py`, `_execute_tool` returns `str(result)`) or `_execute_tool_direct[_async]` (375, 390). Sync returns strings; async may return `ToolResult`.
- Adapters: OpenAI (`openai.py`, Chat Completions and Responses, SDK client), Anthropic (`anthropic.py`, SDK), Gemini (`gemini.py`, `urllib` REST, discards HTTP error bodies), Cohere (`cohere.py`, v1 `cohere.Client.chat` with `chat_history` and `tool_results`), local servers (`openai_compatible.py`, OpenAI SDK).
- Unit tests use fake SDK clients and recorded payloads; no network.

## Work packages

### Ownership inside `model_runtime.py`

WP2 and WP3 both edit `model_runtime.py`, so ownership is by function role, not line range:

- **WP2 owns provider-call sites and error raises:** `_invoke_with_retries`, `_ainvoke_with_retries`, `_invoke_provider`, `_invoke_provider_async`, `_continue_with_tool_results_async`, the `continuation(...)` calls and round-limit raises inside `_orchestrate_tool_calls[_async]`, the continuation calls in `resume_tool_flow[_async]`, the provider-call parts of `stream`/`astream`, `_record_retry`, and the new `_call_provider`/`_acall_provider`.
- **WP3 owns tool execution and result construction:** `legacy_tool_to_spec`, `execute_legacy_tool_call[_async]` and their `_impl`s, `_execute_tool_direct[_async]`, `_execute_runtime_tool_call[_async]`, `_tool_result`, the tool-result construction lines inside `resume_tool_flow[_async]`, and the final-response validation hook.
- `resume_tool_flow[_async]` is edited by both and merged by hand by the lead.
- Any other change to `model_runtime.py` is reported, not made.


Each package is one feature branch off `release/v0.8.4`, merged back after its gate passes. Every package: tests in the named files, `black`/`isort`/`flake8` clean, `scripts/check_types.py` clean, full suite passing, docs updated where behaviour is user-visible, new public exports added to `docs/api-surface.toml` and the surface's Sphinx page. Changelog entries are written at integration, not in the package branches.

### WP0. Baseline (done)

`local_preset` fix committed; CLAUDE.md and AGENTS.md synchronised.

### WP1. Provider continuation (release blocker)

Branch `v084/continuation`. Files: `providers/openai.py`, `providers/anthropic.py`, `providers/gemini.py`, `providers/cohere.py`, `providers/openai_compatible.py` (if it overrides continuation). No runtime changes expected.

- **OpenAI Chat Completions.** `_chat_model_response` records the full `messages` list it sent plus the assistant message (with `tool_calls`) in `metadata["openai_chat_messages"]`. `_continue_chat_completions` builds on `response.metadata["openai_chat_messages"]` when present, falling back to `request` messages for state written by v0.8.3. Responses API path unchanged (`previous_response_id`).
- **Anthropic.** Same pattern with `metadata["anthropic_messages"]`; assistant content blocks kept as received (including `thinking` blocks with signatures, which Anthropic requires to be returned unchanged during tool use).
- **Gemini.** `_runtime_tool_call_response` appends the candidate's `content` exactly as received (every part, in order, with `thoughtSignature` and any text) instead of rebuilding `functionCall` parts. Tool call IDs: use `functionCall.id` when the API returns one and echo it in `functionResponse.id`; otherwise generate IDs unique across the run (today `gemini-call-0` repeats every round).
- **Cohere.** Each round's `chat_history` includes the previous rounds: the `CHATBOT` turn with its `tool_calls` and the tool results, kept in `metadata["cohere_chat_history"]`. Confirm the v1 `chat` shape against the installed SDK before changing it.
- **Reproduce the Gemini HTTP 400 first** with a small live script (`gemini-3.5-flash`, one tool, two rounds) before and after the fix; record the result in the PR. If the 400 persists after signatures are returned, file it separately and say so in release notes.

Tests (new `tests/test_provider_continuation.py`, plus additions to `test_<provider>_provider_edges.py`): fake clients capture every request. For each adapter: three dependent rounds where round 3's request contains rounds 1 and 2 in order; the same tool called twice; two calls in one round; Gemini signed parts round-tripped byte for byte with IDs echoed; HITL pause in round 2, serialise state to JSON, restore in a new runtime, resume, and assert round 3's request is complete; v0.8.3-shaped state (no transcript key) still continues.

### WP2. Structured provider errors and per-call retry

Branch `v084/errors-retry`. Files: `core/exceptions.py`, `model_runtime.py` (provider-call sites and error raises, see ownership below), each adapter's `except` blocks and client construction, `__init__.py`, `docs/api-surface.toml`, docs guide `providers.md` / `troubleshooting.md`.

- `ProviderError(message, *, provider=None, model=None, operation=None, status_code=None, error_code=None, request_id=None, retryable=False, retry_after_seconds=None)`; existing positional use keeps working. Subclasses: `ProviderAuthenticationError` (401/403), `ProviderInvalidRequestError` (400/404/422), `ProviderQuotaError` (quota exhausted, not retryable), `ProviderRateLimitError` (429, retryable), `ProviderUnavailableError` (5xx, 529, overloaded; retryable), `ProviderTransportError` (connection, timeout; retryable), `ToolRoundLimitError` (never retried). Names checked against existing exports to avoid clashes.
- Mapping per adapter: OpenAI and Anthropic SDK exception classes and `status_code`/`response.headers` (`retry-after`, `x-request-id`/`request-id`); Gemini `urllib.error.HTTPError` with the body read, parsed and redacted (`error.status`, `error.message`); Cohere SDK errors. Quota versus rate limit: OpenAI `insufficient_quota` code, Gemini `RESOURCE_EXHAUSTED` with quota detail, otherwise 429 is rate limit.
- `ModelRuntime._call_provider(operation, request, fn, *args)` (sync) and `_acall_provider` (async): the single wrapper for every provider request: `invoke`, `continue`, `resume` continuation, and stream start. Retries only that request when `retryable`, up to `config.retries`, with exponential backoff and full jitter (base 0.5 s, cap 30 s), using `retry_after_seconds` when given (capped at 60 s). Records `_record_retry` with real `backoff_ms`. Non-`ProviderError` exceptions from adapters are wrapped as `ProviderError` (not retryable) with the cause kept. WP5 adds metering inside this wrapper.
- `_invoke_with_retries` and `_ainvoke_with_retries` lose their outer retry loop: one initial call through the wrapper, then the tool loop, whose continuations also go through the wrapper. The round-limit raise becomes `ToolRoundLimitError`.
- Streaming: retry is allowed only before the first event is yielded.
- SDK clients (`openai.OpenAI`, `anthropic.Anthropic`, `openai_compatible`) are built with `max_retries=0` unless `provider_options`/config sets `max_retries`.

Tests (new `tests/test_provider_errors.py`, additions to `test_model_runtime_edges.py`): each adapter maps recorded SDK/HTTP failures to the right type and fields; Gemini error body preserved and redacted; a side-effecting tool counter stays at 1 when the round-2 continuation fails once then succeeds, in `invoke`, `ainvoke`, `stream`, `astream` and HITL resume; non-retryable errors raise immediately; `Retry-After` honoured (patched sleep); round limit raises `ToolRoundLimitError` without retry; `except ProviderError` still catches everything.

### WP3. Typed tool boundary

Branch `v084/tool-boundary`. Files: `pyproject.toml` (`jsonschema` dependency), `model_runtime.py` (tool execution and result construction, see ownership below), `hitl/runtime.py` (`_execute_tool`, `_execute_tool_async`), `tools.py` if signature metadata is needed, `models/__init__.py` (`ToolResult` fields if needed), docs `tool-system-specification.md`, `structured-outputs.md`.

- One result type: `_execute_tool_direct` and HITL `_execute_tool` return `ToolResult` (or a string wrapped into one at a single point), never `str(ToolResult)`. Handler-returned `ToolResult` keeps `is_error` and content. Exceptions become `ToolResult(is_error=True, content="Error: <Type>: <message>")`, keeping the `Error:` prefix so existing string checks still work. `ToolCallScope.set_result` gets `is_error` from the `ToolResult`, not by prefix.
- Argument validation before the handler runs, in one function used by sync, async and HITL paths: Python callables through `pydantic.validate_call`-style validation built from the signature (cached per function); JSON-Schema-only tools through `jsonschema` (Draft 2020-12 validator, cached per schema). Failure returns `ToolResult(is_error=True)` with content naming each failing field and expected type, and the handler is not called. Coercion follows pydantic's lax mode (for example `"3"` → `3`), and the coerced values are what the handler receives.
- Local structured-output validation: `StructuredOutputConfig` gains `validate_locally: bool = False` (not `validate`, which shadows a pydantic `BaseModel` attribute). When true, the runtime parses the final content as JSON and checks it against the schema with `jsonschema`; failure raises `ProviderInvalidResponseError` (a `ProviderError` subclass coordinated with WP2; WP3 defines it if WP2 has not merged yet, in `core/exceptions.py`, and the merge keeps one definition).

Tests (new `tests/test_tool_boundary.py`, additions to `test_tool_system.py`, `test_hitl_runtime_edges.py`): invalid arguments never invoke the handler (sync, async, HITL-approved); sync and async produce identical `ToolResult` for the same failure; returned `ToolResult(is_error=True)` stays an error in sync; coercion behaviour; response validation rejects non-JSON and schema mismatches and passes valid output.

### WP4. Conversation state and per-call controls

Branch `v084/conversation-state`. Files: `core/agent.py`, `decorators.py`, docs `model-runtime.md`, `streaming.md`.

- `_trim_history` (220): keeps every system message; drops oldest complete units (a user message and everything up to the next user message), never splitting an assistant tool turn from its results.
- `stream` / `astream` (584, 610): wrap the event iterator so a `final` event appends the assistant answer to history, trims, and saves state when `persist_state`. A failed or abandoned stream keeps only the user turn.
- One private `_runtime_call_options(kwargs, *, entry_point)` used by `chat`, `generate`, `agenerate`, `stream`, `astream`: applies `allowed_tool_names` (tool filtering) and `additional_system_message` identically, passes the known options, and logs one warning per unknown keyword naming it and the entry point. `chat()` gains the same keyword options.
- A call that has timed out never commits to history: `Agent.chat`/`generate` take a per-call token, and the late answer of an abandoned call is discarded instead of being appended (the worker keeps running until the provider returns, so without this it would append during the handler's next call).
- `chat()` / `achat()` in `decorators.py` (594): `timeout: Optional[float] = None`, defaulting to the agent's configured timeout; when neither is set there is no client-side limit beyond the provider's own (the fixed 10 s default is removed). The executor is shut down with `wait=False` so `TimeoutError` is raised on time; per-call keyword options (including `reasoning`) are forwarded.

Tests (new `tests/test_agent_conversation_state.py`, additions to `test_decorator_edges.py`): system message survives trimming for every `max_history` from 1 to 10; no orphan tool messages; `chat`, `generate`, `agenerate`, `stream`, `astream` leave equal history for the same exchange; sync `generate(allowed_tool_names=[...])` restricts the tools sent; unknown kwarg warns once; `chat(timeout=0.01)` raises within 0.2 s while the worker is still running; the abandoned call's answer never appears in history, including when a second `chat()` runs before the first worker finishes.

### WP5. Usage metering

Branch `v084/metering`, started after WP2 merges. Spec: `plans/praval-v0.8.4-usage-metering.md`, updated with these changes before work starts (done at integration of WP2):

- Meter every request Praval sends. Metering sits inside WP2's `_call_provider`; adapters that make more than one request per call (OpenAI empty-response retry, `openai.py:444`) report each through a context-local reporter that the wrapper installs.
- `attempt` counts WP2 retries of that request.
- `UsageTotals.complete` and `CostEstimate.complete` are false when any call failed, was interrupted or reported no usage.
- `ModelCall` gains `call_id` (UUID4), `parent_run_id` and `correlation_id` (from a `praval.metering.correlation(...)` context manager).
- `track()` is the documented way to meter one application request across several agents; `subscribe` is the hook for a durable sink.
- Scope is chat-model usage only; embeddings, transcription, speech and image generation are not metered and the docs say so.
- Cohere: v1 `chat` responses carry `meta.billed_units` and `meta.tokens`; the mapping is confirmed against the installed SDK.

Files: new `src/praval/metering.py`; `models/__init__.py` (`Usage` fields); `model_runtime.py` (wrapper, response usage totals, `model_call` events, observation calls); adapters' usage extraction; `runtime_observation.py` (`model_calls`, cache fields, metrics); `core/agent.py` (`agent.usage`); `__init__.py`, `docs/api-surface.toml`, `docs/observation-contract.toml` if the observation schema changes; new guide `docs/sphinx/guide/usage-metering.md`.

Tests as listed in the spec, in new `tests/test_metering.py` and `tests/test_provider_usage.py`, plus: two requests metered for one OpenAI empty-response retry; `complete=False` cases; unique `call_id`s across retries; `ExecutionObservation.usage` equals meter totals with no double counting; existing observation contract tests still pass.

### WP6. Reasoning controls

Branch `v084/reasoning`, started after WP4 merges (shares `agent.py`/`decorators.py` keyword handling). Files: `models/__init__.py` (`ReasoningConfig.level`), `model_runtime.py` (`normalize_reasoning_config`, validation 906-925), `providers/registry.py` (per-family reasoning profile data), `providers/openai.py` (546-560, 775-785), `providers/anthropic.py` (436-460), `providers/gemini.py` (243-250), `providers/cohere.py`, `providers/openai_compatible.py`, `core/agent.py`, `decorators.py`, docs `providers.md`, `local-llms.md`.

- `reasoning` accepts `"none" | "low" | "medium" | "high"`, a dict, or `ReasoningConfig`; a string becomes `ReasoningConfig(level=...)`. Explicit `effort`/`budget_tokens` still pass through unchanged.
- Registry model profiles gain `reasoning_levels: Dict[str, Dict[str, Any]]`, the native parameters per level, with a `source` note (documentation URL or live check date). Families: OpenAI reasoning models (`reasoning.effort` on Responses, `reasoning_effort` on Chat Completions); Anthropic (`output_config.effort`, and `thinking` where required); Gemini 3 (`thinkingConfig.thinkingLevel`) and Gemini 2.5 (`thinkingConfig.thinkingBudget`); Cohere reasoning models (thinking setting from the installed SDK); local presets that accept `reasoning_effort`. Each mapping is checked against current provider documentation, and live where keys exist.
- Validation error for an unsupported level names provider, model and accepted levels. `"none"` only where the model can disable thinking.
- `_use_responses_api` (openai 546) no longer switches to Responses because reasoning is set when the endpoint is explicitly `chat.completions`; Chat Completions sends `reasoning_effort`.
- `@agent(reasoning=...)`, `Agent(..., reasoning=...)` via config, and per call through WP4's options helper.

Tests (new `tests/test_reasoning_controls.py`): per-family payloads for each level; precise errors; `chat()` forwards reasoning; local preset sends `reasoning_effort` on Chat Completions; explicit `ReasoningConfig(effort=...)` unchanged.

### WP7. Hardening: security, concurrency and memory

Added after wave 1 merged (release tip `2a3d3b9`, 2484 passed). Wave 1 changed the execution path in ways the unit tests for each package do not probe together. WP7 looks for defects in three areas, writes a failing test for each one it confirms, and fixes it when the fix is local. A defect that needs a design decision is reported with its failing test marked `xfail(strict=True)` and a reason, not patched.

**Security** (branch `v084/hardening-security`, tests in `tests/test_security_hardening.py`):

- Secrets never appear in exception messages, `repr`, logs, span attributes, `ExecutionObservation`, HITL rows or `ModelResponse.metadata`: API keys (including the Gemini key in the request URL), `Authorization` headers, and provider error bodies that echo them. Covers WP2's new error mapping on every adapter.
- WP1 transcripts in `metadata` and HITL state: confirm they are not exported to traces or logs beyond what the privacy filters allow, and that content capture settings apply to them.
- Tool arguments from the model are untrusted: oversized and deeply nested arguments (recursion limits in `_json_safe`, `HITLRuntime._parse_args`, validation), non-object JSON, duplicate keys, arguments naming parameters that are not tools' declared ones.
- JSON Schemas from MCP servers are untrusted: `$ref` to remote or file URLs must not be fetched; pathological `pattern` values (ReDoS) and deeply nested schemas must not hang or crash a run.
- `Retry-After` and error bodies are untrusted: negative, huge, malformed and HTTP-date values; very large bodies are truncated before parsing or logging.
- Unsafe provider options still blocked after WP2 added `max_retries` to the reserved keys; nested credential keys in every option path.

**Concurrency** (branch `v084/hardening-concurrency`, tests in `tests/test_concurrency_hardening.py`):

- One `Agent` used from several threads at once (Reef delivers spores on a thread pool): history consistency, `_history_lock` coverage of every read and write, `persist_state` file writes, unknown-kwarg warnings.
- HITL: two concurrent resumes or decisions for the same intervention must not execute the approved tool twice; `decide_intervention` and suspended-run status changes must be atomic.
- Decorator `chat()`/`achat()` timeouts under load: thread and executor leaks after many timeouts, the `_CallToken` race between commit and cancel, ContextVar propagation into worker threads.
- Retry: sync backoff never blocks an event loop (sync paths called from async code), async retries do not leak coroutines, cancellation during backoff stops promptly.
- Shared caches: signature-validator `WeakKeyDictionary` and schema `lru_cache` under concurrent first use and garbage collection.
- Streams: abandoning a stream from another thread or task, and closing generators, leave no half-committed history.

**Memory** (branch `v084/hardening-memory`, tests in `tests/test_memory_hardening.py`):

- WP1 transcripts: each tool-call response holds a full transcript copy, so a long run can hold O(rounds²) data and HITL rows grow per round. Measure for 50 rounds with large tool outputs; bound or share what is held.
- `conversation_history` growth with `max_history=None`, large tool outputs and multimodal content; persisted state size.
- Abandoned `chat()` workers: what an abandoned call keeps alive (agent, request, response) and for how long.
- Caches: validator caches must not keep handlers, agents or closures alive (weak references actually released after `gc.collect()`); schema cache bounded.
- Reef and agent lifecycle: creating and discarding many agents (PravalClaw creates one per planner call) must not leak registrations, threads, executors or memory, checked with `tracemalloc` and `gc` over repeated cycles.
- Observation and span buffers stay bounded under long runs.

Each WP7 agent works like a wave-1 agent (own worktree and venv, tests real, gates green), may edit any file its fixes need but keeps fixes minimal, and reports: each finding with its test, severity (high: wrong result, data loss, secret exposure or unbounded growth reachable in normal use; medium: reachable under load or misuse; low: hardening), whether it was fixed, and any design-level item left as `xfail`. The lead merges security, then concurrency, then memory, with the full gate after each, and brings the `xfail` items to the user before wave 2.

## Execution: agents, branches and merging

Implementation is split across subagents, each in its own git worktree (`isolation: "worktree"`), branching from the current tip of `release/v0.8.4`. The lead session (this one) owns `release/v0.8.4`, all merges, `CHANGELOG.md`, release notes, the metering spec update, and the integration gate.

**Wave 1, in parallel.** Overlaps: `model_runtime.py` (WP2 and WP3, split by the ownership rules above; `resume_tool_flow[_async]` merged by hand) and the adapters (WP1 continuation and response builders, WP2 `except` blocks and client construction):

| Agent | Package | Branch |
|---|---|---|
| continuation | WP1 | `v084/continuation` |
| errors-retry | WP2 | `v084/errors-retry` |
| tool-boundary | WP3 | `v084/tool-boundary` |
| conversation-state | WP4 | `v084/conversation-state` |

**Wave 2, in parallel, after wave 1 is merged:**

| Agent | Package | Branch |
|---|---|---|
| metering | WP5 | `v084/metering` |
| reasoning | WP6 | `v084/reasoning` |

Each agent works in its own worktree with its **own venv** (`python3 -m venv venv && venv/bin/pip install -e ".[dev,mcp,secure]"`), because the main `venv/` has praval installed editable from the main checkout; before any test it confirms `python -c "import praval; print(praval.__file__)"` points inside the worktree, and reports that line. Its brief: its section of this plan; read `CLAUDE.md` first; stay within the listed files (anything else is reported, not changed); use the venv; write tests before or with the change; run the package's new tests, the full suite with CI flags, `black --check`, `isort --check-only --profile black`, `flake8`, `scripts/check_types.py`, and `scripts/check_api_surface.py`; commit on its branch with `fix:`/`feat:`/`test:`/`docs:` prefixes and the co-author trailer; do not push or merge; report what changed, test evidence, deviations from the plan, and changelog lines.

**Merging.** Order WP1 → WP2 → WP3 → WP4, then WP5 → WP6. For each: review the diff against the plan and conventions, merge with `--no-ff` into `release/v0.8.4`, resolve conflicts by hand, then run the full local gate (below) before the next merge. A failing gate is fixed on the release branch before continuing. Wave 2 branches are created from the release branch after wave 1's gate passes.

**Integration gate (local, after each merge and at the end):**

```bash
source venv/bin/activate
pytest tests/ --ignore=tests/test_arxiv_downloader.py --ignore=tests/test_message_filtering.py \
  --ignore=tests/test_venturelens_demo.py --timeout=60 --timeout-method=thread -q
pytest tests/ ... --cov=src/praval --cov-report=json:coverage.json --cov-fail-under=90   # final only
python scripts/check_coverage_floors.py coverage.json                                  # final only
black --check src/ tests/ scripts/ examples/certification/ examples/notebooks/*.py
isort --check-only src/ tests/ scripts/ examples/certification/ examples/notebooks/*.py --profile black
flake8 src/ tests/ scripts/ examples/certification/ examples/notebooks/*.py --max-line-length=88 --extend-ignore=E203,W503
python scripts/check_types.py
python scripts/check_api_surface.py
PRAVAL_DOCS_OFFLINE=1 sphinx-build -b html -W --keep-going docs/sphinx docs/_build/html   # final only
```

**Cross-package behavioural tests** (written by the lead after wave 2, `tests/test_v084_release_gate.py`): one scenario per adapter with a fake client that runs three dependent tool rounds, fails the round-2 continuation once with a retryable error, includes an invalid tool argument in round 1 and a HITL pause in round 2 with restart; asserts complete transcripts, side effect executed once, handler not called for the invalid call, equal history across entry points, and metered totals equal the sum of recorded requests.

## Release

1. Version `0.8.4` in `pyproject.toml`; `CHANGELOG.md` `[0.8.4]` with Added / Changed / Fixed; `docs/releases/RELEASE_NOTES_0.8.4.md` including the behaviour changes and migration notes; `python scripts/check_release_metadata.py`.
2. Live checks before merging to `main`: extend `examples/certification/live_provider_matrix.py` with a two-tool, three-round dependent run and usage reconciliation; run on OpenAI (Chat Completions and Responses), Gemini, and Anthropic and Cohere when keys are available. Record results in the PR; any adapter not run live is stated in the release notes.
3. PravalClaw and Praval Code: install the candidate wheel in each and run their integration suites; remove Praval Code's `retries=0` workaround in a follow-up there.
4. PR `release/v0.8.4` → `main`, then follow `RELEASE.md` exactly (CI wheel, Twine upload of that wheel, PyPI verification, tag, docs PR).

## Compatibility

- Additions: error subclasses and fields, `ToolResult` handling, `StructuredOutputConfig.validate_locally`, `Usage` fields, `praval.metering`, `agent.usage`, reasoning levels, `chat()` keyword options.
- Changed (listed under "Changed" in the changelog): `ModelResponse.usage` in tool runs is the run total; streamed answers enter history; trimming keeps system messages and whole units; SDK-internal retries off by default; retry no longer repeats tool rounds; round-limit errors are `ToolRoundLimitError`; `chat()` timeout returns on time and defaults to the agent's timeout; sync `generate` honours `allowed_tool_names` and `additional_system_message`; unknown keyword arguments warn; tool exceptions' content includes the exception type.
- HITL state written by v0.8.3 still resumes.
