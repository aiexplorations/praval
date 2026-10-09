# Migrating to v0.8.4

Usage metering and portable reasoning controls ship in v0.8.4. Jev is planned for
v0.8.5. See {doc}`usage-metering` and {doc}`providers` for configuration.

## Provider and application setup

OpenRouter is available with `provider="openrouter"` and
`OPENROUTER_API_KEY`. Keep its full model ID, for example
`anthropic/claude-haiku-4.5`. Capability profiles and account availability are
separate; see {doc}`providers` for discovery and portable reasoning controls.

For Ollama tools, enable `config={"provider_options": {"discover_model": True}}`
or explicitly configure verified capabilities. Discovery reports the loaded
context separately from the model maximum. Per-request native Ollama context
configuration remains planned for 0.8.5; see {doc}`local-llms`.

Put client defaults such as timeout, retries and endpoint selection in an
agent's `config` dictionary. Per-call options have a narrower contract; see
{doc}`model-runtime`. Registered full object JSON Schema tools, including MCP
tools, now preserve their argument names and types across supported adapters.

## Observable behavior changes

- `ModelResponse.usage` is the sum of reported requests in the logical invocation,
  including tool continuations and approval history. It can remain partial; inspect
  `metadata["usage_complete"]`. Legacy approval state without request records stays
  incomplete. Streaming consumers should accept the new `model_call` event.
- SDK retries default to zero. Runtime retries use typed provider errors and retry
  the failed request; exhausted tool rounds raise `ToolRoundLimitError`.
- Streaming final answers are saved to history before `final` reaches the caller.
  History keeps system messages and whole user exchanges, and concurrent answers
  remain paired with their user turn.
- Decorated `chat` and `achat` honor the configured timeout and common request
  options. A timed-out synchronous provider worker may finish later, but its answer
  is discarded. Unknown keywords warn now and are planned to error in v0.8.5.
- Tool exceptions include their exception type. Tool validation and error outcomes
  are consistent across entry points; local structured output validation also
  applies to streaming final answers.

## External tool schemas

The base dependency set adds `regex` for bounded external `pattern` matching.
External `patternProperties` and nested `$schema` dialect switches fail closed,
including when referenced locally. Convert such schemas to explicit `properties`
with ordinary bounded `pattern` checks before registration. Trusted application
response schemas retain their existing validator behavior.

## Approval recovery

Existing v0.8.3 approval state remains readable. Newly saved state retains committed
results and request history across restart and failed resumes. Application-level
idempotency is still required for a crash after an external side effect and before
its result is durably saved. Resuming state does not replay historical metering
records into lifetime counters or subscribers.
