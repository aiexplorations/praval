# Model Runtime

`ModelRuntime` is the execution boundary between agents and provider adapters.
It owns provider-neutral request validation, capability resolution, retry
policy, tracing spans, legacy tool execution hooks, HITL resume metadata, and
the normalized response/event types in `praval.models`.

Prefer this path for new code:

```python
from praval import Agent

agent = Agent("planner", provider="openai", model="gpt-5.4-mini")
response = agent.generate(
    "Return a JSON task list.",
    response_schema={
        "type": "object",
        "properties": {"tasks": {"type": "array", "items": {"type": "string"}}},
        "required": ["tasks"],
    },
    metadata={"workflow": "planning"},
)

print(response.content)
```

`Agent.chat()` remains compatible and returns only a string. `Agent.generate()`,
`Agent.agenerate()`, `Agent.stream()`, and `Agent.astream()` return or emit
structured runtime types.

## Request Options

`Agent.chat()`, `generate()`, `agenerate()`, `stream()`, and `astream()` accept
the same keyword options and apply them the same way:

| Option | Purpose |
| --- | --- |
| `response_schema` | Provider-neutral structured output schema. |
| `reasoning` | Reasoning effort, display mode, or budget settings. |
| `provider_options` | Provider-specific options after runtime safety checks. |
| `timeout` | Per-call timeout when the adapter supports it. |
| `metadata` | User metadata for tracing and diagnostics. |
| `stream_options` | Streaming options such as usage inclusion. |
| `max_tool_rounds` | Tool-round limit for this call. |
| `allowed_tool_names` | Send only these registered tools; an unknown name raises `ValueError` before anything is sent. |
| `additional_system_message` | A system message placed first in this request only; it is not stored in history. |

`chat()` and `generate()` also accept `stream`.

An unknown keyword argument is ignored and logged as a warning that names the
keyword and the method, for example
`Agent.generate() ignored unknown keyword argument 'temprature'`. In v0.8.5
unknown keyword arguments become errors.

Unsafe provider options such as API keys, raw authorization headers, and custom
default headers are rejected before provider execution. Keys are matched
case-insensitively at any depth, so `{"extra_headers": {"Authorization": ...}}`
is rejected as well.

## Conversation History

Every entry point leaves the same history for the same exchange: the user turn
followed by the assistant's final answer. The user turn is added when the call
starts; the answer is added only when the call succeeds, then the history is
trimmed and, with `persist_state=True`, saved. A call that fails keeps only the
user turn. `stream()` and `astream()` add the answer when the `final` event is
produced, before it reaches your loop, so breaking out after `final` keeps it.

Calls on one agent may overlap, for example when the Reef delivers spores on
several threads. Each answer is inserted directly after its own user turn, so
the history reads user A, answer A, user B, answer B regardless of which call
finishes first. If later calls have trimmed a user turn away before its answer
arrives, that answer is returned to its caller but not stored, since there is
no question left to pair it with.

`max_history` limits the number of non-system messages kept. Trimming removes
the oldest whole units, where a unit is a user message and everything up to the
next user message, so an assistant tool turn is never separated from its tool
results. System messages are always kept and do not count towards the limit.
The newest unit is always kept, even when it alone exceeds the limit; with
`max_history=0` the agent keeps its system messages and the current exchange
only.

With `persist_state=True`, an agent that has a `system_message` replaces the
system messages in the loaded history with its own, placed first, so a changed
`system_message` takes effect on restart and restarts never add copies. An agent
without a `system_message` keeps the persisted ones.

## Timeouts in Decorated Agents

Inside an `@agent` handler, `chat(message, timeout=None, **options)` and
`achat(...)` accept the same keyword options as `Agent.chat()`. `timeout` is a
client-side limit in seconds. When it is not given, the agent's configured
`timeout` applies; when neither is set there is no limit beyond the provider's
own. On expiry `TimeoutError` is raised on time. The abandoned call keeps
running until its provider returns, but its answer is discarded and never
enters the conversation history, even if the handler has made further calls by
then.

`achat()` runs calls on a Praval-owned pool of daemon threads rather than the
event loop's default executor, so hung calls cannot starve other
`run_in_executor` users, and a hung call does not keep the process alive at
exit. The pool is shared by every event loop in the process and has 32 threads;
set `PRAVAL_ACHAT_MAX_WORKERS` to change that. A timed-out call holds its thread
until the provider returns, so once every thread is held by such calls, later
`achat()` calls wait for a free thread and may time out themselves.

```python
from praval import agent, chat


@agent("summarizer", responds_to=["summary_request"])
def summarizer(spore):
    summary = chat(
        spore.knowledge["text"],
        timeout=30,
        additional_system_message="Answer in three sentences.",
    )
    return {"summary": summary}
```

## Public Inspection

Use the registry and runtime to inspect behavior before executing a call:

```python
from praval import Agent, ModelMessage, ModelRequest

agent = Agent("local", provider="ollama", model="llama3")
request = ModelRequest(
    provider="ollama",
    model="llama3",
    messages=[ModelMessage(role="user", content="hello")],
)

capabilities = agent.runtime.resolve_capabilities(request)
agent.runtime.validate_request(request)
```

For production code that needs preflight checks, construct
`praval.models.ModelRequest` directly and pass it to `resolve_capabilities()` or
`validate_request()`.

## Runtime Events

Streaming emits normalized `ModelEvent` values:

| Event | Meaning |
| --- | --- |
| `start` | Runtime accepted the request and resolved stream capability. |
| `delta` | Text delta. |
| `tool_call_delta` | Partial tool-call arguments or provider tool-call delta. |
| `tool_call` | Complete tool call request. |
| `tool_result` | Tool result emitted by runtime-owned orchestration. |
| `usage` | Token usage update. |
| `model_call` | Completed actual request, including attempt and reported usage. |
| `error` | Provider or stream error, with redacted metadata. |
| `final` | Final `ModelResponse`. |

Adapters may expose more provider metadata, but user code should branch on the
normalized event type first.

## Client Tool Orchestration

Client/function tools are runtime-owned in 0.8. A provider adapter only
translates declarations, tool calls, and tool results. For each response,
`ModelRuntime` executes all requested client tools, records ordered
`ToolCall`/`ToolResult` values, asks the provider to continue, and repeats up to
the configured tool-round limit. Sync tools, async tools, sync streaming, and
async streaming share this orchestration path.

Tools marked `requires_approval=True` are evaluated by the HITL runtime before
execution. An intervention stores JSON-safe provider-neutral continuation
state. After the operator approves, edits, or rejects the call,
`Agent.resume_run(run_id)` reconstructs the request and response, completes the
remaining tool calls, and continues the model loop. Legacy provider-specific
continuation schemas remain readable for compatibility.

Provider-hosted tools are a separate experimental pass-through. See
{doc}`providers` for the explicit opt-in and security restrictions.

See {doc}`usage-metering` for aggregate response usage and per-request accounting.
