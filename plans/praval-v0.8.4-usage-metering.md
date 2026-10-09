# Praval v0.8.4: usage metering

Status: approved, revised 2026-10-07 for the v0.8.4 plan (`plans/praval-v0.8.4-plan.md`, WP5). Written against `main` at `2cfdd5e` (v0.8.3); metering builds on WP2's per-request provider wrapper.

## Background

Praval does not report what a run cost. In a run that uses tools, `ModelRuntime` makes one provider call to start and one more after each tool round, but only the last call's usage survives:

- The tool loops (`_orchestrate_tool_calls`, `_orchestrate_tool_calls_async`, `resume_tool_flow`, `resume_tool_flow_async`) receive a `ModelResponse` with usage from every `continue_with_tool_results` call and discard it. `_complete_response` keeps nothing.
- `_record_response_facts` runs once, on the final response, so `ExecutionObservation.usage` and the OpenTelemetry span attributes carry the last call's usage too.
- Nothing reports how many model calls a run made.

Measured on 2026-10-07 with `gpt-5.4-mini` and one tool called twice: three provider calls used 74, 104 and 132 tokens (310 in total); the stream's `usage` event and the final response both said 132.

Provider adapters also leave usage out:

| Adapter | Reports today | Missing |
|---|---|---|
| OpenAI | input, output, total, reasoning | cached input (`prompt_tokens_details.cached_tokens`, `input_tokens_details.cached_tokens`) |
| Anthropic | input, output | cache reads and writes (`cache_read_input_tokens`, `cache_creation_input_tokens`), which Anthropic counts outside `input_tokens` |
| Gemini | nothing (`usage` is always `None`) | everything; the raw reply has `usageMetadata` with `promptTokenCount`, `candidatesTokenCount`, `thoughtsTokenCount`, `cachedContentTokenCount`, `totalTokenCount` |
| Cohere | nothing found in the adapter | to be read from the response of the client version in use |

Gemini's thinking tokens matter: one measured call produced 14 tokens of text and 479 thinking tokens, all billed.

Applications built on Praval need exact usage to show spend, enforce budgets and size context. Praval Code's `/tokenspend` is the first consumer.

## Outcome

Every provider call Praval makes for an agent or a `ModelRuntime` is metered: one record per call, with normalised usage. Callers can read per-call records and totals, receive each record as it happens, and compute cost from their own prices. Observability aggregates the same records, so traces and `ExecutionObservation` report the true totals.

Praval meters what providers report. It never estimates tokens. A call whose provider reports no usage is counted as a call with unreported usage.

## Scope

In scope: chat model calls through `ModelRuntime`, whether started by `Agent.chat`, `generate`, `agenerate`, `stream`, `astream`, `resume_run`, `aresume_run`, or used directly; the four providers above; cost calculation from caller-supplied prices.

This release meters chat-model usage only. Out of scope: embeddings, transcription, speech and image generation metering (applications such as PravalClaw that call these directly are not covered); built-in price lists; budget enforcement (applications build it on the meter); token estimation.

## Normalised usage

`praval.models.Usage` gains two fields, both defaulting to 0 so existing code is unaffected:

```python
class Usage(BaseModel):
    input_tokens: int = 0        # every prompt token processed, including cache reads and writes
    output_tokens: int = 0       # every generated token, including reasoning tokens
    total_tokens: int = 0
    reasoning_tokens: int = 0    # subset of output_tokens
    cache_read_tokens: int = 0   # subset of input_tokens
    cache_write_tokens: int = 0  # subset of input_tokens
```

The rule is that `input_tokens` and `output_tokens` are complete, and the other fields are subsets of them, so a price per input and output token is never double counted. Mapping per provider:

| Field | OpenAI | Anthropic | Gemini |
|---|---|---|---|
| `input_tokens` | `prompt_tokens` / `input_tokens` | `input_tokens + cache_read_input_tokens + cache_creation_input_tokens` | `promptTokenCount` |
| `output_tokens` | `completion_tokens` / `output_tokens` | `output_tokens` | `candidatesTokenCount + thoughtsTokenCount` |
| `reasoning_tokens` | `*_tokens_details.reasoning_tokens` | 0 (thinking is inside `output_tokens`) | `thoughtsTokenCount` |
| `cache_read_tokens` | `*_tokens_details.cached_tokens` | `cache_read_input_tokens` | `cachedContentTokenCount` |
| `cache_write_tokens` | 0 | `cache_creation_input_tokens` | 0 |

Each mapping is confirmed against a live response before it ships, and the fixtures used by unit tests are recorded from those responses.

## Public API: `praval.metering`

```python
from praval.metering import ModelCall, UsageMeter, UsageTotals, Price, PriceTable, CostEstimate

@dataclass(frozen=True)
class ModelCall:
    provider: str
    model: str
    operation: Literal["invoke", "stream", "continue", "resume"]
    round_index: int | None      # tool round that led to this call; None for the first call
    attempt: int                 # 1 for the first attempt, higher for Praval retries
    status: Literal["ok", "error"]
    usage: Usage | None          # None when the provider reported none, or the call failed
    duration_ms: float
    started_at: datetime
    agent_name: str | None
    call_id: str                 # UUID4, unique per provider request, stable for export
    run_id: str | None           # the ExecutionObservation run, when one is active
    parent_run_id: str | None    # the enclosing run when this run was started inside another
    correlation_id: str | None   # caller-set, from praval.metering.correlation(...)
    response_id: str | None

@dataclass(frozen=True)
class UsageTotals:
    calls: int
    failed_calls: int
    unreported_calls: int        # successful calls with no usage from the provider
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    total_tokens: int
    complete: bool               # False if any call failed, was interrupted or reported no usage

class UsageMeter:
    def record(self, call: ModelCall) -> None: ...
    @property
    def totals(self) -> UsageTotals: ...
    def totals_by_model(self) -> dict[tuple[str, str], UsageTotals]: ...
    @property
    def calls(self) -> tuple[ModelCall, ...]: ...   # most recent records, bounded
    def subscribe(self, callback: Callable[[ModelCall], None]) -> Callable[[], None]: ...
    def cost(self, prices: PriceTable) -> CostEstimate: ...
    def reset(self) -> None: ...
    @contextmanager
    def track(self) -> Iterator["UsageMeter"]: ...  # meter every call in this context
```

Two ways to attach a meter:

1. **Per agent.** Every `Agent` has `agent.usage`, a `UsageMeter` that records every call the agent makes for its lifetime. It needs no configuration. An application that keeps one agent per session gets session totals from it directly.
2. **Per scope.** `with meter.track():` meters every call made in the current context, by any agent or runtime, through a context variable. Praval already copies the context into executor threads (`copy_context().run`), so synchronous provider calls made from async code are metered too. Scopes nest: a call is recorded by every active meter and by its agent's meter.

`subscribe` delivers each `ModelCall` as soon as the provider call returns, before the tool loop continues. This is how a terminal UI updates a usage line during a long run, even though `astream` with tools still delivers its events at the end. A callback that raises is logged and removed; it never breaks the run.

Storage is bounded: `calls` keeps the most recent 10,000 records (configurable), while totals stay exact after older records are dropped. Records hold no prompt or response content.

Thread safety: `record`, `totals` and `subscribe` are safe to call from any thread; each meter holds one lock.

### Cost

```python
@dataclass(frozen=True)
class Price:
    input_per_million: float
    output_per_million: float
    cache_read_per_million: float | None = None   # None: billed at the input price
    cache_write_per_million: float | None = None  # None: billed at the input price
    currency: str = "USD"

class PriceTable:
    def __init__(self, prices: Mapping[tuple[str, str], Price]) -> None: ...  # (provider, model)

@dataclass(frozen=True)
class CostEstimate:
    amount: float
    currency: str
    priced_calls: int
    unpriced_calls: int      # calls whose model has no price, or with unreported usage
    complete: bool           # False when unpriced_calls > 0 or the totals are incomplete
```

Cost per call is `(input - cache_read - cache_write) * input + cache_read * cache_read_price + cache_write * cache_write_price + output * output_price`, each per million. Reasoning tokens are inside `output_tokens` and are not priced again. Praval ships no prices: they change often and differ by account, so the caller supplies them. A table with more than one currency raises `ValueError`.

## Runtime changes

Metering covers every request Praval sends, not every adapter call. It happens inside WP2's `ModelRuntime._call_provider` / `_acall_provider`, the single wrapper every provider request passes through. An adapter that sends more than one request in one call (the OpenAI empty-response retry, `openai.py:444`) reports each request through a context-local reporter the wrapper installs, so both requests are recorded. Call sites:

- `_invoke_provider` and `_invoke_provider_async` (first call, `operation="invoke"`).
- The native streaming path (`operation="stream"`), recording from the final event's response or the last `usage` event.
- Each `continue_with_tool_results` call in the four tool loops (`operation="continue"`, with `round_index`).
- `resume_tool_flow` and `resume_tool_flow_async` after a HITL decision (`operation="resume"`).
- Each retry attempt of one request made by the wrapper, with its `attempt` number. Praval owns retries: SDK clients are built with `max_retries=0`. A caller who sets `max_retries` explicitly gets SDK retries that the meter cannot see, and the docs say so.

A failed provider call is recorded with `status="error"` and `usage=None`, then the error propagates unchanged. An interrupted call (a stream abandoned before its final event) is recorded with `status="error"` and whatever usage the stream reported, and marks totals incomplete.

### Scopes and identities

- `with meter.track():` is the documented way to meter one application request across several agents. Applications that create a fresh `Agent` per step (PravalClaw's planner does) cannot rely on `agent.usage` alone.
- `with praval.metering.correlation("<id>"):` sets `correlation_id` on every record made inside it, so an application can join records to its own request or session.
- `subscribe` is the hook for a durable sink: records carry `call_id`, so a sink that stores them can deduplicate.

### What responses and events report

- `ModelResponse.usage` for a run with tools becomes the sum over every call in the run, not the last call. This is a behaviour change (see Decisions).
- `ModelResponse.metadata["model_calls"]` lists the run's calls as dictionaries, in order.
- `stream` and `astream` emit one `ModelEvent(type="model_call", usage=..., metadata={...})` per call, in call order, before `final`. On the tool path they arrive at the end of the run, like `tool_call` events. The existing `usage` event carries the run total.

### Observability

- `record_model_facts` is called once per provider call with that call's usage, and no longer with the final response's usage, so `ExecutionObservation.usage` is the true sum without double counting. Its existing `cache_read_tokens` and `cache_write_tokens` fields are filled from the new `Usage` fields.
- A new `ExecutionObservation.model_calls: int` counts calls.
- When the metrics pipeline is configured, each call records the OpenTelemetry GenAI client token usage histogram with input and output token types, and a `praval.model.calls` counter, both labelled with provider, model and operation. Span attributes on the run span report the totals.

## Provider adapter changes

- OpenAI: read cached tokens from both Chat Completions and Responses usage shapes.
- Anthropic: read cache read and write counts and add them into `input_tokens` as tabled above.
- Gemini: build `Usage` from `usageMetadata` in `invoke`, `continue_with_tool_results` and `stream`.
- Cohere: the v1 `chat` response carries `meta.billed_units` (input and output tokens) and `meta.tokens`; confirm against the installed SDK and map billed units. If the client does not report usage, record calls as unreported and say so in the docs.
- Local OpenAI-compatible servers often omit usage; their calls are counted as unreported, never estimated.

## Compatibility

- New `Usage` fields default to 0; the new module and `agent.usage` are additions.
- `ModelResponse.usage` in tool runs changes from last call to run total. Code that relied on the old value was reading an undercount; the CHANGELOG states the change under "Changed".
- `ModelEvent(type="model_call")` is a new event type; consumers that ignore unknown event types are unaffected.

## Tests

- Unit, with a deterministic test provider (no network) that returns recorded responses: a tool run of N rounds produces N+1 records with the right operations and round indexes; totals equal the sum of the records; `ModelResponse.usage` equals the totals; failed calls and retries are recorded with status and attempt; unreported usage is counted; nested `track()` scopes and the agent meter each record once; executor-thread calls are metered; a raising subscriber is removed without breaking the run; storage bound keeps exact totals; cost arithmetic including cache prices, missing prices and mixed currencies.
- Provider mapping, from responses recorded live: OpenAI Chat Completions and Responses (with and without cached tokens and reasoning), Anthropic (with prompt caching), Gemini (with thinking), Cohere.
- Observability: `ExecutionObservation.usage` equals the meter's totals for the same run; no double counting when both the final response and per-call facts exist.
- Live, in `examples/certification/live_provider_matrix.py` (not pytest), gated by keys: a two-tool run on each provider, asserting three calls, totals equal to the sum of per-call usage, and totals greater than the last call's usage.

## Decisions for review

1. **`ModelResponse.usage` semantics.** Recommended: run total, as above. Alternative: keep the last call there and add `ModelResponse.run_usage`; safer for existing callers, but leaves the undercount in place for everyone who does not read the docs.
2. **Agent meter always on.** Recommended: yes; it is a counter and a bounded deque, with no measurable cost. Alternative: opt in with `Agent(meter=...)`.
3. **Live `model_call` events on the tool path.** This spec delivers live updates through `subscribe`, and events at the end of the run. Streaming events between tool rounds belongs with the separate per-round streaming work.

## Related v0.8.4 work

Continuation, retry and error handling are WP1 and WP2 of `plans/praval-v0.8.4-plan.md`; metering depends on WP2's wrapper and on WP1 for live Gemini tool runs.
