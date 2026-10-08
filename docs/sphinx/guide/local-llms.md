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

Ollama discovery can replace manual tool overrides. Use
`config={"provider_options": {"discover_model": True}}` or explicitly call
`get_provider_registry().discover_models("ollama", config)`. Profiles read
`/api/show` capabilities and context limits; `/api/ps` supplies
`metadata["loaded_context_window"]`. Supported context and loaded context differ.
Set `required_context_tokens` in provider options to warn when loaded context is
insufficient. Configure a Modelfile with `PARAMETER num_ctx` and reload the model
to increase it; the OpenAI endpoint cannot set context per request. Discovery can
fail when the server is down or the model is missing. Output budgets above a
discovered limit fail before inference.

The OpenAI-compatible provider validates base URLs before creating the SDK
client. It rejects non-HTTP schemes, embedded credentials, and metadata
service/link-local targets. Put secrets in environment variables instead of
`base_url` or `provider_options`.

## Reasoning on vLLM

The vLLM preset supports portable `reasoning="low"`, `"medium"`, and `"high"`
through Chat Completions `reasoning_effort`. The documented
`google/gemma-4-26B-A4B-it` profile also supports `"none"`; the wildcard rejects
`"none"` because some models cannot disable thinking. This requires a server
version and model that support the parameter; consult [vLLM's reasoning
support](https://docs.vllm.ai/en/latest/features/reasoning_outputs/) when
configuring the server. Praval keeps Chat Completions selected for local
reasoning requests. Ollama, LM Studio, llama.cpp, and generic compatible
profiles remain conservative: register a model profile with `reasoning_levels`
and matching capabilities after verifying that server's native controls.
