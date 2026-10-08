# Native Ollama context control for v0.8.5

Status: planned, reviewed on 2026-10-08 against `release/v0.8.4` at `dae03df`.
This document records requirements. The setting and native adapter described
below are not implemented in v0.8.4. The release remains on hold for owner tests.
See the [roadmap](praval-roadmap.md).

## Evidence and ownership

Praval currently routes `provider="ollama"` through `OpenAICompatibleProvider`
at `/v1`. Its discovery code reads `/api/show` for model capabilities and the
model's supported context, then `/api/ps` for the observed loaded context.
`required_context_tokens` can warn about a mismatch. It does not change the
inference request's context size.

Claude reported this sequence on the user's `qwen3.5:9b` installation:

| Request | Observed context | Reported loaded size |
| --- | --- | --- |
| Native preload with `num_ctx=32768` | 32,768 tokens | 6.7 GB |
| Ordinary OpenAI-compatible inference after the preload | 4,096 tokens | 5.5 GB |
| Native `/api/chat` with `options.num_ctx=32768` | 32,768 tokens | 6.7 GB |

This probe has not been repeated by Praval. It demonstrates why applications
should not treat a preload as a persistent context setting for later requests.
The 1.2 GB difference applies to that model and setup. Memory requirements vary
with the model, quantization, cache format, concurrency and device. Ollama's
documented defaults also vary with available memory. See its
[context guide](https://docs.ollama.com/context-length).

Praval owns parameter validation, transport, provider translation and runtime
contracts. Praval Code owns the selected context size, memory policy, prompt
budget, configuration and user interface. Praval will not impose a 32k default.

## Proposed Praval contract

An application can request a context allocation with
`provider_options={"context_tokens": 32768}`. This name is proposed for v0.8.5;
applications must not pass it to the v0.8.4 adapter.

1. Accept a positive integer at agent configuration and per-call override
   boundaries. Reject booleans, zero, negative values and conflicting native
   settings before dispatch. Keep `context_tokens` distinct from
   `max_output_tokens`, the model maximum and `required_context_tokens`.
2. Use a native Ollama transport when this option is supplied. Send
   `options.num_ctx` on every `/api/chat` request, including the initial call,
   each tool continuation, each retry, sync and async streams, and HITL resume
   after a process restart. Persist the resolved value in continuation state.
3. Keep existing `/v1` behavior when the option is omitted during the initial
   rollout. An explicit incompatible endpoint or unsupported provider must
   produce a clear error. Do not silently fall back to `/v1` or remove `num_ctx`
   during parameter recovery.
4. Preserve complete conversation and tool transcripts. Translate `ToolSpec`
   JSON Schemas, images, structured output and discovered thinking controls
   using the native API. Keep the runtime responsible for argument validation,
   tool execution and approvals. Preserve native thinking state required for
   continuation without adding private thinking to normal observations.
5. Map the output limit separately to `options.num_predict`. Reject a context
   allocation above a known model maximum. A stale loaded-context snapshot
   must not cap a newly requested allocation or be treated as the model's
   supported output maximum. Record the context used for budget validation.
6. Meter every actual native request. Normalize reported prompt, output and
   cache counts, and preserve complete usage reconciliation across tool rounds
   and retries. Keep missing usage explicit. Report allocation and transport
   failures as typed errors with actionable context; do not reduce the requested
   allocation silently after a memory failure.
7. Expose the model maximum, requested context and latest observed loaded
   context as separate facts. Refresh `/api/ps` explicitly for certification
   and diagnostics. Include the observation time and server/model identity;
   another application's request may change the loaded state between snapshots.
   Missing observations remain unknown.

The native route builds on Ollama's [chat API](https://docs.ollama.com/api/chat),
[tool continuation contract](https://docs.ollama.com/capabilities/tool-calling)
and [running-model metadata](https://docs.ollama.com/api/ps). Detailed adapter
design and an endpoint migration guide are required before implementation.

## Praval Code dependency

Praval Code's context-budget work should include the following policy:

- Propose 32,768 tokens as the default for local coding sessions. Bound it by
  the model maximum and a measured or configured memory ceiling with headroom.
  The advertised model maximum alone does not prove that an allocation fits.
- Allow a per-model override and pass the resolved value to Praval on every
  request. Store it with the session so resume uses the same budget.
- Budget system messages, tool declarations, conversation and retrieved code
  against that allocation. Reserve space for generation and thinking according
  to the model's accounting. Apply prompt pruning and compaction to the selected
  session budget. Report estimates as estimates.
- Show the model maximum, session allocation and observed loaded context in
  `/provider` and `/model`. Have `doctor` warn when observed context is below
  the session requirement, or say that loaded context is unknown.
- Handle memory failures visibly. Let the user choose a smaller allocation or
  model, then recompute the session budget. Do not silently continue with a
  smaller context than the displayed budget.

This is Praval Code work recorded as a dependency. Its repository and runtime
configuration are unchanged by this plan.

## Interim setup for v0.8.4

Use a named model variant so its configured default applies to ordinary Praval
requests. A proposed example is:

```text
FROM qwen3.5:9b
PARAMETER num_ctx 32768
```

Save the two lines in a Modelfile, then run
`ollama create qwen3.5-9b-32k -f /path/to/Modelfile` and select that model name
in the application. Verify the loaded context after an ordinary request with
`ollama ps` or `/api/ps`. The application may offer this action when context
is too small, with the user's approval. See the
[Modelfile reference](https://docs.ollama.com/modelfile).

Alternatively, set `OLLAMA_CONTEXT_LENGTH` on the Ollama server. This changes
the server default for models that do not override it and requires a restart.
For the macOS app, Ollama documents `launchctl setenv` followed by restarting
the app. A shell export alone does not change an already running app. The
application should explain the scope and request approval for the server change.
See [environment configuration](https://docs.ollama.com/faq#setting-environment-variables-on-mac).
No model variants or server settings are changed by this roadmap update.

## Work order and acceptance

1. Specify the native adapter, endpoint selection, request option precedence,
   reasoning support, usage mapping and compatibility behavior.
2. Implement deterministic contracts at the HTTP boundary. Check `num_ctx` on
   every request across all public entry points, dependent tool rounds, retries
   and persisted approval resume. Cover invalid values, conflicting settings,
   unknown/stale discovery, cancellation, malformed responses and typed errors.
3. Certify context control live on a bounded local model. Start with a smaller
   loaded context, request 32,768 where the model and hardware support it, then
   verify the allocation after each Praval request. Control server concurrency
   and record other clients so `/api/ps` observations can be attributed.
4. Include a regression probe that performs an intervening `/v1` call with
   default options, then proves the next native Praval request restores the
   selected context. Run dependent integer/boolean tools, thinking where
   supported, image input on a vision model, structured output and streaming.
   Reconcile usage for each actual request and record model/server versions,
   allocation, memory observations and durations.
5. Integrate the Praval Code policy and configuration. Compare a small local
   coding model with a hosted model on its existing application evaluations.
   Certify the built wheel and Praval Code session behavior before declaring
   support complete. Keep native context control in v0.8.5.
