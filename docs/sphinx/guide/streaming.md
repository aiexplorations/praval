# Streaming

Streaming uses normalized `ModelEvent` objects. The runtime emits a `start`
event, then delegates native streaming to adapters when available.

```python
from praval import Agent

agent = Agent("assistant", provider="openai", model="gpt-5.4-mini")

for event in agent.stream("Write one sentence.", stream_options={"include_usage": True}):
    if event.type == "delta":
        print(event.delta, end="")
    elif event.type == "usage":
        print(f"\nusage={event.usage.total_tokens}")
    elif event.type == "final":
        print("\ncomplete")
```

Async streaming:

```python
async for event in agent.astream("Write one sentence."):
    ...
```

## Streaming and conversation history

A streamed exchange enters the agent's history the same way as `chat()` or
`generate()`. The user turn is added when `stream()` is called, or when
iteration of `astream()` begins. When the
`final` event is produced, the answer from `final.response.content` is added,
the history is trimmed, and with `persist_state=True` the state is saved, all
before the event reaches your loop. Breaking out of the loop after `final`
therefore keeps the answer.

A stream that raises, or that is closed or abandoned before `final`, leaves
only the user turn in history.

`stream()` and `astream()` accept the per-call options listed in
{doc}`model-runtime`, including `allowed_tool_names` and
`additional_system_message`.

## Native and fallback streaming

OpenAI, Anthropic, Gemini, and OpenAI-compatible providers use native streaming
paths. If a profile advertises `native_streaming=True` but the adapter does not
implement streaming, the runtime raises a provider error before execution.

Fallback streaming is allowed only for providers that explicitly describe
streaming as non-native or emulated.
