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

OpenAI, Anthropic, Gemini, and OpenAI-compatible providers use native streaming
paths. If a profile advertises `native_streaming=True` but the adapter does not
implement streaming, the runtime raises a provider error before execution.

Fallback streaming is allowed only for providers that explicitly describe
streaming as non-native or emulated.
