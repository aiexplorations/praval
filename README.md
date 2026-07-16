<div align="center">
  <img src="docs/assets/logo.png" alt="Praval Logo" width="180"/>

  # Praval

  **A Python framework for agent systems and provider-neutral model execution**

  [![PyPI](https://img.shields.io/pypi/v/praval.svg)](https://pypi.org/project/praval/)
  [![Python](https://img.shields.io/pypi/pyversions/praval.svg)](https://pypi.org/project/praval/)
  [![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
</div>

Praval supports two complementary ways to build:

- Use `Agent` when one agent needs model calls, tools, streaming, structured
  output, multimodal input, embeddings, transcription, or speech generation.
- Use decorated agents with Reef and Spores when several specialists need to
  exchange structured knowledge and react to one another.

`ModelRuntime` is the provider-neutral execution boundary inside `Agent`.
Reef is Praval's agent-to-agent delivery substrate, and Spores are the messages
it carries. These layers work together; neither replaces the other.

## Install

```bash
pip install praval

# Install only the optional capabilities you use
pip install "praval[memory]"
pip install "praval[storage]"
pip install "praval[mcp]"       # Python 3.10+
pip install "praval[notebooks]"
```

The core package supports Python 3.9 through 3.13. The official MCP Python SDK
requires Python 3.10 or newer.

## Path 1: Direct model execution

```python
import json

from praval import Agent

assistant = Agent("assistant", provider="openai", model="gpt-5.4-mini")
try:
    response = assistant.generate(
        "Return a short JSON summary of Praval.",
        response_schema={
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    )
    payload = json.loads(response.content)
    print(payload["summary"])
    print(response.usage)
finally:
    assistant.close()
```

`response_schema` asks a capable provider to constrain its response. Praval
returns the provider's JSON text in `ModelResponse.content`; parse and validate
it in your application when local validation is required.

`Agent.chat()` remains available for compatibility when a plain string is all
you need. New code should prefer `generate()`, `agenerate()`, `stream()`, or
`astream()` when metadata, usage, structured output, or normalized events
matter.

## Path 2: Agents collaborating through Reef

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

The in-process Reef is built in. RabbitMQ is the supported distributed Reef
backend. Redis is a storage provider, not a Reef backend. AMQP, MQTT, and STOMP
adapters belong to the optional secure transport layer.

## Lifecycle ownership

`PravalApp` owns agents and a Reef so an application can clean them up
deterministically:

```python
from praval import PravalApp

with PravalApp() as app:
    assistant = app.create_agent("assistant", provider="openai")
    print(assistant.chat("Say hello in one sentence."))
```

In this release, `PravalApp` is a lifecycle owner. It is not an isolated
dependency-injection container and does not replace the process-wide provider
registry used by `Agent`.

## Optional capabilities

- Tools and HITL: JSON-schema tools can require persisted human approval before
  execution and resume.
- MCP: `praval.mcp` consumes tools from stdio and Streamable HTTP servers. It is
  separate from provider-hosted MCP descriptors.
- Memory and embeddings: local or provider-backed retrieval paths are explicit.
- Storage: the unified API is asynchronous and supports filesystem,
  PostgreSQL, Redis, S3-compatible storage, and Qdrant.
- Observability: local spans, SQLite trace storage, console viewing, and OTLP
  HTTP export are available.
- Voice: `Agent.transcribe()` and `Agent.speak()` are request-based STT and TTS
  operations. Persistent realtime audio/model sessions are not part of this
  release.

Local OpenAI-compatible presets are available for Ollama, vLLM, LM Studio, and
llama.cpp. Their advanced capabilities are disabled unless the configured
server profile explicitly enables them.

## Documentation and examples

- [Published documentation](https://pravalagents.com/docs/latest/)
- [Getting started](docs/sphinx/guide/getting-started.md)
- [Architecture and API layers](docs/sphinx/guide/core-concepts.md)
- [Model runtime](docs/sphinx/guide/model-runtime.md)
- [Providers and capabilities](docs/sphinx/guide/providers.md)
- [MCP client](docs/sphinx/guide/mcp.md)
- [Storage](docs/sphinx/guide/storage.md)
- [API reference](docs/sphinx/api/index.rst)
- [Jupyter course and capstones](examples/notebooks/README.md)

Run the offline provider-neutral example without credentials:

```bash
python examples/model_runtime_fake_provider.py
```

Build the reference documentation locally:

```bash
make docs-html
```

Provider model catalogs change independently of Praval. The packaged registry
is a tested capability snapshot; production applications should still choose
and verify explicit model names.

## Development

```bash
make setup
source venv/bin/activate
make test
make lint
make type-check
make build
```

Release artifacts keep uploadable distributions in `dist/` and checksums,
manifests, coverage, and certification records in `evidence/`.
