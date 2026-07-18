# Getting started

Praval has two entry paths. Start with direct `Agent` calls when one agent is
enough. Add Reef and Spores when independent specialists need to collaborate.

## Install

```bash
python -m pip install praval
```

Praval supports Python 3.9 through 3.13. Optional capabilities are installed
separately:

```bash
python -m pip install "praval[memory]"
python -m pip install "praval[storage]"
python -m pip install "praval[mcp]"  # Python 3.10+
```

For a hosted provider, set the corresponding environment variable before
running an example:

```bash
export OPENAI_API_KEY="..."
# or ANTHROPIC_API_KEY, COHERE_API_KEY, or GEMINI_API_KEY
```

Passing `provider` and `model` explicitly makes an example reproducible. If
they are omitted, Praval resolves its configured defaults and available
credentials.

## First path: call a model through Agent

```python
from praval import Agent

assistant = Agent(
    "assistant",
    provider="openai",
    model="gpt-5.4-mini",
    system_message="Be concise.",
)
try:
    response = assistant.generate("Explain what a Praval Spore carries.")
    print(response.content)
    print(response.provider, response.model, response.usage)
finally:
    assistant.close()
```

`Agent.generate()` returns `ModelResponse`. Its content, provider, model,
usage, tool calls, and raw provider data are available without changing the
application contract for each provider.

The compatibility method returns only a string:

```python
text = assistant.chat("Explain Reef in one sentence.")
```

Prefer `generate()` for new code. Use `agenerate()`, `stream()`, and
`astream()` for asynchronous work and normalized streaming events.

## Structured output

```python
import json

response = assistant.generate(
    "Return one fact about Reef as JSON.",
    response_schema={
        "type": "object",
        "properties": {"fact": {"type": "string"}},
        "required": ["fact"],
    },
)
fact = json.loads(response.content)["fact"]
```

The runtime checks that the selected provider profile supports structured
output and then sends the schema as a provider constraint. It does not run a
second local JSON Schema validation pass.

## Second path: collaborate through Reef

A Spore contains routing fields and a structured `knowledge` dictionary. The
conventional `knowledge["type"]` value lets decorated agents decide which
messages to handle.

```python
from praval import agent, broadcast, get_reef, start_agents


@agent("researcher", provider="ollama", responds_to=["research_request"])
def researcher(spore):
    topic = spore.knowledge["topic"]
    broadcast(
        {
            "type": "research_complete",
            "topic": topic,
            "finding": f"Evidence collected for {topic}",
        }
    )


@agent("editor", provider="ollama", responds_to=["research_complete"])
def editor(spore):
    print(spore.knowledge["finding"])


start_agents(
    researcher,
    editor,
    initial_data={"type": "research_request", "topic": "agent systems"},
)
reef = get_reef()
reef.wait_for_completion(timeout=30)
reef.shutdown()
```

This example uses the Ollama preset only to construct credential-free message
handlers; it does not call the local model server. A decorated handler may call
`chat()` or `achat()` when it actually needs model output.

`wait_for_completion()` waits for submitted Reef work. Always shut down Reef
and other resources explicitly in scripts and tests.

## When to use each layer

| Need | Start with |
| --- | --- |
| One conversational or tool-using agent | `Agent` |
| Provider-neutral metadata and usage | `Agent.generate()` |
| Streaming deltas and final events | `Agent.stream()` / `Agent.astream()` |
| Multiple reactive specialists | `@agent`, Reef, and Spores |
| Deterministic application cleanup | `PravalApp` |
| External MCP tools | `praval.mcp.MCPClient` with async `Agent` calls |

`PravalApp` owns agents and a Reef for cleanup. In this release it does not
isolate provider registries or redirect agent Reef helpers; see
{doc}`application-lifecycle`.

## Local models

Praval connects to an already-running OpenAI-compatible server:

```python
from praval import Agent

local = Agent("local", provider="ollama", model="llama3")
try:
    print(local.chat("Say hello."))
finally:
    local.close()
```

The presets are `ollama`, `vllm`, `lmstudio`, and `llama-cpp`. Text and
streaming are enabled by default. Tools, structured output, reasoning, and
multimodal input require explicit capability configuration for the server you
are using.

## Learn by inspecting execution

The Jupyter course explains Agent, Reef, Spore, tools, memory, HITL, MCP, and
voice flows with visible runtime state. Start with
`examples/notebooks/course/00_architecture.ipynb`.

For a credential-free runtime check:

```bash
python examples/model_runtime_fake_provider.py
```

Next, read {doc}`core-concepts`, {doc}`model-runtime`, and the generated
{doc}`../api/index`.
