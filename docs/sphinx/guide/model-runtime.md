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

The same options are accepted by sync, async, and streaming calls:

| Option | Purpose |
| --- | --- |
| `response_schema` | Provider-neutral structured output schema. |
| `reasoning` | Reasoning effort, display mode, or budget settings. |
| `provider_options` | Provider-specific options after runtime safety checks. |
| `timeout` | Per-call timeout when the adapter supports it. |
| `metadata` | User metadata for tracing and diagnostics. |
| `stream_options` | Streaming options such as usage inclusion. |

Unsafe provider options such as API keys, raw authorization headers, and custom
default headers are rejected before provider execution.

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
