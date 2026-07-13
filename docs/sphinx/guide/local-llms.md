# Local LLMs

Praval supports local LLM servers through OpenAI-compatible HTTP APIs. It does
not launch inference engines. Start the server yourself, then point Praval at
the server.

## Presets

| Preset | Default Base URL |
| --- | --- |
| `ollama` | `http://localhost:11434/v1` |
| `vllm` | `http://localhost:8000/v1` |
| `lmstudio` | `http://localhost:1234/v1` |
| `llama-cpp` | `http://localhost:8080/v1` |

```python
from praval import Agent

agent = Agent("local", provider="ollama", model="llama3")
print(agent.chat("Say hello."))
```

For generic servers:

```python
agent = Agent(
    "local",
    provider="openai-compatible",
    model="my-model",
    config={"base_url": "http://127.0.0.1:8000/v1"},
)
```

## Conservative Defaults

Local profiles enable text and native streaming by default. Tools, JSON schema
mode, multimodal input, and reasoning are rejected unless you opt into a richer
profile:

```python
response = agent.generate(
    "Return JSON.",
    response_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    provider_options={
        "capabilities": {
            "structured_outputs": True,
            "json_schema_mode": "json_schema",
        }
    },
)
```

Only override capabilities you have verified on the specific server, model, and
endpoint.

## Base URL Safety

The OpenAI-compatible provider validates base URLs before creating the SDK
client. It rejects non-HTTP schemes, embedded credentials, and metadata
service/link-local targets. Put secrets in environment variables instead of
`base_url` or `provider_options`.
