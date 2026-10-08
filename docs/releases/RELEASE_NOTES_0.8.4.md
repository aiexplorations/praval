# Praval 0.8.4

This release strengthens model execution, provider continuation, request retries,
conversation state and approval recovery. Usage metering and portable reasoning
controls are included. Jev decision-model support remains planned for v0.8.5.

## Model execution

Provider continuation retains prior tool calls, results and native reasoning
state. OpenAI Responses chains preserve response identity; Anthropic signed
thinking and Gemini thought signatures survive tool rounds. All configured system
messages are preserved across provider serializers.

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

## Compatibility and validation

See [migration guidance](../sphinx/guide/v084-migration.md) for history, timeout,
retry, event and schema-validation changes. External schema `patternProperties`
and nested dialect changes are rejected; ordinary external patterns have matching
timeouts and size limits. Trusted response schemas retain existing semantics.

Deterministic provider fixtures and integration matrices cover the supported entry
points, dependent tools, retries, approval restart, Reef concurrency, observations
and evaluation. Test counts, coverage and hashes belong in generated release
evidence. These tests do not establish live-provider compatibility by themselves.

Live Anthropic, Gemini, Cohere and local-provider validation has not been run in
this handoff because credentials or configured endpoints were unavailable. OpenAI
Chat Completions and Responses passed local dependent-tool and usage checks;
portable low reasoning also passed. Exact main-CI wheel certification remains a
release gate.
Publication follows RELEASE.md using only the wheel produced by successful main CI.
