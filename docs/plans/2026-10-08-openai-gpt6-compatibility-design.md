# OpenAI GPT-6 compatibility for 0.8.4

The reported GPT-6 Luna failures come from GPT-5-only request constraints and
missing GPT-6 reasoning profiles. A deterministic probe reproduced `max_tokens`
and `temperature` in outgoing requests and rejection of portable `low`.

Apply numbered GPT generation constraints to GPT-5 and later: Chat Completions
uses `max_completion_tokens`; both endpoints omit sampling controls. Preserve
older and custom-name behavior. Register documented portable levels for Luna/Sol
(none, low, medium, high) and Astra/6.1 Sol (low, medium, high), including dated
snapshots through the existing registry lookup.

Tool routing also needs correction. The official GPT-6 guide requires Responses
for reasoning with tools. Default GPT-6 tool calls use Responses. Explicit Luna
and Sol Chat Completions requests supply `reasoning_effort=none` when omitted;
unsupported combinations fail locally with endpoint guidance. Preserve endpoint
selection and continuation state across sync, async and streaming execution.

A name-only GPT-6 prefix patch would still break tool calls. Expanded feedback
also calls for parameter recovery: retry once on an explicit HTTP 400 sampling
parameter rejection, or the documented max_tokens rename. Preserve tools, reasoning
and budgets; remember successful repairs in a bounded cache per adapter, endpoint
and full model ID. Meter each actual request and recover streams only before they
open. A configuration switch can disable recovery.

Validate with fake SDK requests, dependent tool rounds, reasoning levels and
streaming. Add a dedicated live GPT-6 Luna certificate to the release manifest,
covering automatic and explicit endpoints, low reasoning and per-request usage.
Run release checks before integrating into release/v0.8.4. Publication still uses
the exact wheel produced by main CI under RELEASE.md.

Source: https://developers.openai.com/api/docs/guides/latest-model
and https://developers.openai.com/api/docs/models/gpt-6-luna (checked 2026-10-08).
