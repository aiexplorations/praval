# Usage metering

Every `Agent` exposes `agent.usage`, a thread-safe `UsageMeter`. It records each
actual chat-model request, including retries, tool continuations, streams and
approval resumes. It excludes embeddings, transcription, speech and image generation.

```python
from praval import Agent
from praval.metering import Price, PriceTable, UsageMeter, correlation

meter = UsageMeter(max_records=1000)
agent = Agent("writer", provider="openai", model="gpt-5.4-mini")
with meter.track(), correlation("application-request-42"):
    response = agent.generate("Explain coral reefs briefly.")

print(meter.totals)
prices = PriceTable({("openai", "gpt-5.4-mini"): Price(1.0, 2.0)})
print(meter.cost(prices))  # Illustrative caller-supplied prices per million tokens.
```

`track()` includes calls from multiple agents in the current context and its
Praval worker threads. Nested tracking of the same meter records each request
once. `agent.usage` covers the agent lifetime. `reset()` clears its totals and
history while retaining subscribers. `subscribe(callback)` provides each new
`ModelCall` and returns an unsubscribe function. A failing subscriber is removed;
its failure does not interrupt model execution.

## Records and totals

`ModelCall` contains request identities, operation, attempt, tool round, status,
duration and provider-reported usage. It contains no prompts, responses or tool
arguments. `calls` retains at most `max_records` recent records. Lifetime totals
and totals by provider/model remain exact after records are evicted.

`ModelResponse.usage` sums reported usage across the complete logical invocation.
`metadata["model_calls"]` holds its request records and
`metadata["usage_complete"]` reports whether every request succeeded and supplied
usage. Missing usage stays unknown; zero usage is a reported value.
`UsageTotals.failed_calls` counts errors, while `unreported_calls` counts successful
requests without usage. `complete` is false for either condition.

Streaming adds a `model_call` event for each completed request before `final`.
Provider usage snapshots are not added repeatedly. A subscriber receives records
when requests finish, including an interrupted stream with no final response.
`ExecutionObservation.model_calls` and its usage reflect actual requests without
counting the final aggregate again.

Approval state retains request records across restart and failed resumes. Restored
records contribute to the resumed response, but are not emitted again to lifetime
meters or subscribers. Tool replay protection applies after the result is committed
to SQLite; applications still need idempotency for a crash between an external
effect and that commit.

## Token normalization and cost

Input includes cached tokens. Output includes reasoning tokens. Cache read/write
and reasoning fields are subsets, so pricing does not charge them twice. Anthropic
cache counts are added to its ordinary input count; Gemini thought tokens are added
to candidate output. Cohere uses billed units when available. Local providers that
omit usage produce incomplete totals.

Prices belong to the caller and are never fetched automatically. Cache prices
default to the input price. Missing model prices or usage produce an incomplete
`CostEstimate` with explicit priced/unpriced request counts. Tables cannot mix
currencies. Estimates describe reported token charges, excluding other fees.

Provider field references: [OpenAI](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create),
[Anthropic](https://platform.claude.com/docs/en/build-with-claude/prompt-caching),
[Gemini](https://ai.google.dev/api/generate-content),
[Cohere](https://docs.cohere.com/v1/reference/chat).

## API

```{automodule} praval.metering
:members:
```
