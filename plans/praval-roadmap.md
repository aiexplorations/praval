# Praval roadmap

Status: draft for review, 2026-10-07. Written against `main` at `2cfdd5e` (v0.8.3). Code references are to that commit.

Each release gets a plan in `plans/` before work starts:

- v0.8.4: `plans/praval-v0.8.4-plan.md`
- v0.8.4 usage metering spec: `plans/praval-v0.8.4-usage-metering.md`

Inputs: the v0.8.4 metering spec; Praval Code's harness notes on Gemini, retries, errors, streaming and local models; and a review of Praval, PravalClaw and Praval Code at `2cfdd5e` that ran deterministic probes against the runtime. Every defect listed for v0.8.4 below was confirmed by reading the cited code.

## v0.8.4: reliable execution and accurate usage

A run that uses tools must work on every supported adapter, never repeat a side effect, keep its conversation intact, and report what it used. v0.8.4 fixes the execution path before adding anything new on top of it.

### Fixes

1. **Provider continuation.** Release blocker.
   - OpenAI Chat Completions and Anthropic lose earlier tool rounds. `_orchestrate_tool_calls` passes each continuation the original request and only the latest round's results (`src/praval/model_runtime.py:1172`), and the adapters rebuild their messages from that (`src/praval/providers/openai.py:628`, `src/praval/providers/anthropic.py:200`). By round 3 the model no longer sees round 1. OpenAI Responses is not affected; it chains with `previous_response_id`.
   - Gemini drops thought signatures. The adapter rebuilds each `functionCall` part from name and arguments (`src/praval/providers/gemini.py:467`) instead of returning the model's parts as received, which Gemini 3 function calling requires. Gemini tool runs with `gemini-3.5-flash` fail with HTTP 400 after the first tool result; this is the most likely cause.
2. **Retry and provider errors.**
   - Retry wraps the whole tool loop (`src/praval/model_runtime.py:1077`). A provider error in a later round re-runs every earlier tool call, including tools with side effects.
   - `ProviderError` carries only a message. A used-up quota and a temporary rate limit look the same, `Retry-After` is lost, and the Gemini adapter discards the response body. Applications classify errors from strings or exception chains.
3. **Tool boundary.**
   - Synchronous tool execution returns `str(result)` (`src/praval/model_runtime.py:375`), and errors are detected by an `"Error:"` prefix (`src/praval/model_runtime.py:1606`). A `ToolResult(is_error=True)` from a sync tool is recorded as a success.
   - Model-supplied arguments are not validated against the tool schema before the handler runs.
4. **Conversation state.**
   - `_trim_history` can remove the system message (`src/praval/core/agent.py:220`).
   - `stream` and `astream` never add the assistant's answer to history (`src/praval/core/agent.py:584`).
   - Sync `generate` ignores `allowed_tool_names` and `additional_system_message`; only `agenerate` honours them (`src/praval/core/agent.py:536`).
5. **`chat()` timeout.** `chat()` inside `@agent` (`src/praval/decorators.py:594`) waits for the worker even after its timeout fires, because leaving the `ThreadPoolExecutor` block joins the thread. Its fixed 10 second default is also too short for reasoning models.
6. **`local_preset`** is sent to local servers as an API argument (fix already in the working tree).

### Features

1. **Usage metering.** Every provider request Praval makes is metered with normalised usage; tool runs report true totals; callers compute cost from their own prices. Covers chat-model calls only. Spec: `plans/praval-v0.8.4-usage-metering.md`, with the changes listed in the v0.8.4 plan.
2. **Reasoning controls.** A portable reasoning level accepted by `Agent`, `@agent`, `chat()` and every generate and stream method, mapped per model family to the native setting (for example Gemini 3 `thinkingLevel` versus Gemini 2.5 `thinkingBudget`). An unsupported level fails with a precise error and is never silently weakened. Explicit endpoint selection stops being overridden by reasoning settings, so local Chat Completions servers can receive reasoning effort. Required for v0.8.4, confirmed 2026-10-08.

### Release gate

Behavioural tests against the built wheel: three dependent tool rounds on every supported adapter; a provider failure after a side effect does not repeat it; signatures survive HITL pause, resume and restart; invalid arguments never reach a handler; `chat`, `generate`, `stream` and their async forms leave the same history; metered totals reconcile with every recorded request. Then live two-tool runs on OpenAI, Anthropic, Gemini and Cohere, and representative PravalClaw workflows.

## v0.8.5: operational control

v0.8.4 makes a run correct. v0.8.5 makes it observable while it happens, stoppable, and resumable, and then adds decisions and budgets on top.

- **Native async providers and cancellation.** Async provider methods instead of worker threads, so a caller can stop waiting promptly, close streams and prevent further tools from starting. Cancellation is recorded consistently. A provider may still bill a request after it is cancelled.
- **Live execution events.** Model-round starts, tool starts and results, retries, usage and terminal status emitted as they happen. Today tool streams replay their events after the loop finishes (`src/praval/model_runtime.py:528`), so they cannot serve as progress.
- **Per-round token streaming.** `stream`/`astream` with tools deliver each round's text as it is generated, not only the last round's text at the end.
- **Parallel tool calls within a round,** where tools declare they are safe to run concurrently.
- **Tested local-model profiles.** Published, tested combinations of server, model, tools, structured output, reasoning and streaming.
- **Durable run context and checkpoint hooks.** Extend the HITL continuation machinery so applications can persist progress and resume without repeating completed steps. Complements application ledgers such as PravalClaw's; it does not replace them.
- **Strict keyword arguments.** Unsupported keyword arguments, warned about in v0.8.4, become errors.
- **Decision models: `praval.decide`.** Typed questions (`Noul`, `Choice`, `Score`) answered with probabilities by a decision model, first through TypeSafe's Jev, in a `DecisionRuntime` separate from `ModelRuntime`. Metered and traced like model calls. Released as experimental until its outputs are evaluated on representative PravalClaw tasks; probabilities are not treated as calibrated before then.
- **Calibration in `praval.eval`.** Brier score and expected calibration error for decision outputs against labelled data.
- **Budgets.** Token and cost limits per agent, per tracked scope and per run, built on the meter: warn, stop the tool loop cleanly, or lower the reasoning level.
- **Metering beyond chat.** Embeddings, transcription, speech and image generation.

## v0.9 and beyond

- **Persistence guarantees.** An optional `require_persistence` contract: memory initialisation that cannot reach its backend fails instead of silently falling back to memory, and writes report whether they are durable. Configurable conversation storage with atomic writes, replacing name-based JSON files (`src/praval/core/storage.py`).
- **Application ownership and isolation.** `PravalApp` as a supported boundary for multiple sessions and configurations in one process, with isolated registries, Reef and model settings. PravalClaw currently patches process-wide state to achieve this.
- **Decision-driven routing.** Decision-gated message handling per agent (on top of `responds_to`, still peer-to-peer), decision-based HITL approval that can add approval but never remove a mandatory one, and model or reasoning-level selection per call.
- **Multi-tenant Reef.** Rate limits and channel access control (items S2 and S5 in `plans/rearchitecture_plan_v2.md`), with metering and budgets per tenant.
- **Realtime and binary content.** WebRTC/WebSocket voice sessions and raw binary Spore attachments (deferred from v0.8.1).
