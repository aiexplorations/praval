<div align="center">
  <img src="https://raw.githubusercontent.com/aiexplorations/praval/main/docs/assets/logo.png" alt="Praval Logo" width="180"/>

  # Praval

  **Build model-backed agents and message-driven agent teams in Python**

  [![PyPI](https://img.shields.io/pypi/v/praval.svg)](https://pypi.org/project/praval/)
  [![Python](https://img.shields.io/pypi/pyversions/praval.svg)](https://pypi.org/project/praval/)
  [![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/aiexplorations/praval/blob/main/LICENSE)
</div>

Praval is a focused Python framework for agent systems. One agent can use a
provider-neutral model runtime, tools, streaming, structured output, memory,
multimodal input, and request-based voice. Teams of agents can collaborate
through a native layer called Reef.

You can start small with one `Agent`, then add Reef and Spores when work needs
to move between specialists. These are two parts of the same framework, not
competing APIs.

## Choose where to start

| I want to... | Start with | First resource |
|---|---|---|
| Call a model and keep normalized metadata | `Agent` and `ModelRuntime` | [Direct model quick start](#quick-start-call-a-model) |
| Build a team of collaborating specialists | `@agent`, Reef, and Spores | [Agent team quick start](#quick-start-connect-agents-through-reef) |
| Give an agent local or shared tools | `ToolSpec` and the agent tool registry | [Tool integration tutorial](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/tutorials/tool-integration.md) |
| Pause a sensitive tool for human approval | HITL policies and persisted interventions | [HITL guide](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/tutorials/hitl-interventions.md) |
| Consume tools from an MCP server | `praval.mcp.MCPClient` | [MCP guide](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/mcp.md) |
| Add memory and retrieval | Memory, embeddings, and storage | [Memory tutorial](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/tutorials/memory-enabled-agents.md) |
| Use a local model server | An OpenAI-compatible profile | [Local model guide](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/local-llms.md) |
| Transcribe or generate speech | `Agent.transcribe()` and `Agent.speak()` | [Voice and multimodal notebook](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/course/12_voice_and_multimodal.ipynb) |
| Learn by running complete systems | The visual notebook course and capstones | [Notebook learning center](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/README.md) |

## How the pieces fit

```text
Your application
      |
      +--> Agent --> ModelRuntime --> OpenAI, Anthropic, Cohere, Gemini,
      |       |                       or OpenAI-compatible servers
      |       +--> tools, HITL, MCP, memory, media, and streaming
      |
      +--> decorated agents <--> Reef <--> Spores
                                  |
                                  +--> in-process or RabbitMQ delivery

PravalApp closes the agents and Reef that an application owns.
```

| Term | Meaning |
|---|---|
| `Agent` | The main object for model requests, tools, streaming, media, and memory. |
| `ModelRuntime` | The provider-neutral execution boundary used by `Agent`. |
| Reef | Praval's native agent-to-agent delivery system. |
| Spore | A structured message carried through Reef, with identity, correlation, and payload data. |
| Handler | A function that reacts to a Spore or performs a registered tool action. |
| `PravalApp` | A lifecycle owner that closes its agents and Reef. |

See [Core concepts](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/core-concepts.md) for a deeper explanation
of the runtime and collaboration layers.

## Install

Install the core package:

```bash
python -m pip install praval
```

Praval supports Python 3.9 through 3.13. Install only the optional capabilities
your application needs:

| Extra | Install command | Adds |
|---|---|---|
| Memory | `python -m pip install "praval[memory]"` | ChromaDB, sentence transformers, and local retrieval support |
| Storage | `python -m pip install "praval[storage]"` | PostgreSQL, Redis, S3-compatible storage, and Qdrant clients |
| Secure transport | `python -m pip install "praval[secure]"` | Secure Spores and AMQP, MQTT, and STOMP adapters |
| PDF | `python -m pip install "praval[pdf]"` | PDF ingestion through `pypdf` |
| MCP | `python -m pip install "praval[mcp]"` | Official MCP client SDK on Python 3.10 or newer |
| Observability | `python -m pip install "praval[observability]"` | OTLP HTTP export support |
| Notebooks | `python -m pip install "praval[notebooks]"` | JupyterLab and the tested notebook runtime |
| Documentation | `python -m pip install "praval[docs]"` | Sphinx and the documentation theme |
| Runtime features | `python -m pip install "praval[all]"` | All optional runtime features, excluding notebooks and documentation tools |

### Why the 0.8 line starts at 0.8.1

Version 0.8.0 was briefly uploaded during release preparation, then withdrawn
before Praval created a matching Git tag and GitHub release. PyPI does not
allow a deleted release filename to be reused. Praval therefore moved to
0.8.1 so every supported package has clear, matching provenance. There is no
user migration between 0.8.0 and 0.8.1. Version 0.8.1 is the first supported
release in the 0.8 line.

Provider credentials are read from the standard environment variables:

| Provider | Environment variable |
|---|---|
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Cohere | `COHERE_API_KEY` |
| Gemini | `GEMINI_API_KEY` |

OpenAI-compatible endpoints use an explicit base URL, API key, and model
profile. See [Providers and capabilities](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/providers.md) for
configuration and the tested capability matrix.

## Check your installation

Praval includes diagnostics that do not print secret values:

```bash
praval --version
praval doctor
praval doctor --json
```

`praval doctor` reports the installed version and path, Python runtime,
available optional dependencies, and whether provider environment variables
are present. Missing provider keys are informational because a Praval install
does not require every provider.

## Quick start: call a model

Set `OPENAI_API_KEY`, then create an agent and keep the normalized response:

```python
from praval import Agent

with Agent(
    "assistant",
    provider="openai",
    model="gpt-5.4-mini",
    system_message="Be concise and concrete.",
) as assistant:
    response = assistant.generate(
        "Explain what a Praval Spore carries in two sentences."
    )
    print(response.content)
    print(response.usage)
```

`ModelResponse` keeps content, finish state, provider metadata, and usage
in one provider-neutral shape. Use the API that matches the work:

| API | Use it for |
|---|---|
| `chat()` | A compatibility path that returns a plain string |
| `generate()` and `agenerate()` | Complete sync or async responses with metadata |
| `stream()` and `astream()` | Normalized sync or async response events |
| `transcribe()` | Request-based speech-to-text |
| `speak()` | Request-based text-to-speech |

Structured output asks a capable provider to constrain its response. The JSON
text is returned through `ModelResponse.content`. Parse and validate it in your
application when you need local schema validation. Start with the
[ModelRuntime guide](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/model-runtime.md),
[streaming guide](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/streaming.md), and
[structured output guide](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/structured-outputs.md).

You can try the normalized runtime without credentials:

```bash
python examples/model_runtime_fake_provider.py
```

## Quick start: connect agents through Reef

Decorated agents react to Spores delivered by Reef. This example uses custom
handlers, so it can show the collaboration flow without making a paid model
call:

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

The in-process Reef is built in. RabbitMQ is the distributed Reef backend.
Redis is a storage provider, not a Reef backend. Start with the
[first agent tutorial](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/tutorials/first-agent.md), then continue to
[agent communication](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/tutorials/agent-communication.md) and
[multi-agent systems](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/tutorials/multi-agent-systems.md).

## Own the lifecycle with PravalApp

`PravalApp` closes registered agents and its Reef when the application exits:

```python
from praval import PravalApp

with PravalApp() as app:
    assistant = app.create_agent("assistant", provider="openai")
    print(assistant.chat("Say hello in one sentence."))
```

It is a lifecycle owner in this release. It is not a dependency-injection
container, and it does not replace the process-wide provider registry used by
`Agent`. See [Application lifecycle](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/application-lifecycle.md)
for cleanup rules and async use.

## Capability map

| Area | What Praval provides | Start here |
|---|---|---|
| Model execution | Provider-neutral requests, responses, events, capabilities, usage, and errors | [ModelRuntime](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/model-runtime.md) |
| Provider adapters | OpenAI, Anthropic, Cohere, Gemini, and OpenAI-compatible servers | [Providers](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/providers.md) |
| Agent collaboration | Direct delivery, broadcast, channels, request and reply, completion tracking, and RabbitMQ delivery | [Agent communication](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/tutorials/agent-communication.md) |
| Tools | JSON Schema definitions, sync and async handlers, shared tools, validation, and tool errors | [Tool integration](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/tutorials/tool-integration.md) |
| Human approval | Approve, edit, reject, persist, and resume approval-protected tool calls | [HITL interventions](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/tutorials/hitl-interventions.md) |
| MCP | Async tool discovery and execution over stdio and Streamable HTTP | [MCP client](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/mcp.md) |
| Memory | Short-term, episodic, semantic, and long-term memory paths | [Memory-enabled agents](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/tutorials/memory-enabled-agents.md) |
| Embeddings | Local and provider embeddings with explicit compatibility checks | [Embeddings](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/embeddings.md) |
| Storage | Async filesystem, PostgreSQL, Redis, S3-compatible, and Qdrant providers | [Storage](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/storage.md) |
| Observability | Finalized spans, console inspection, SQLite storage, and OTLP HTTP export | [Observability](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/observability.md) |
| Multimodal and voice | Images, files, audio and video where supported, plus request-based STT and TTS | [Multimodal](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/multimodal.md) |
| Secure messages | Signed and encrypted Spores with optional transport adapters | [Production notebook](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/course/08_production_features.ipynb) |

Provider model catalogs change independently of Praval. The packaged model
registry is a tested capability snapshot. Production applications should
select and verify an explicit model name instead of relying on a moving
provider default.

Local presets are available for Ollama, vLLM, LM Studio, llama.cpp, and generic
OpenAI-compatible servers. Their default profiles are conservative. Enable
tools, media, structured output, or embeddings only when your endpoint supports
them. The [local model guide](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/local-llms.md) shows how.

## Learning center

The repository includes 13 course notebooks, four substantial capstones,
runnable Python examples, reference documentation, and companion videos. The
course explains every core term before using it. The capstones assume those
basics and focus on complete systems and design choices.

Start JupyterLab from a source checkout:

```bash
make setup
source venv/bin/activate
python -m pip install -e ".[notebooks]"
cd examples/notebooks
jupyter lab
```

Open `course/00_architecture.ipynb` and run the cells in order. Offline lessons
need no API keys. Service and live lessons list their prerequisites at the top.

### Suggested learning paths

| Goal | Run these lessons |
|---|---|
| Learn Praval from the beginning | Course 00 through 06, in order |
| Build model-backed agents | 00, 01, 05, 09, and 10 |
| Build distributed agent systems | 00, 02, 04, 08, and 11 |
| Add memory and retrieval | 00, 02, 05, 06, and 07 |
| Build voice and multimodal agents | 00, 01, 09, and 12 |
| Study a complete production-style system | Complete the relevant fundamentals, then choose a capstone |

### Visual course

| # | Lesson | You will learn | Mode |
|---:|---|---|---|
| 00 | [Architecture](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/course/00_architecture.ipynb) | Agent, ModelRuntime, Reef, Spore, handler, and lifecycle | Offline |
| 01 | [Hello world](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/course/01_hello_world.ipynb) | Agent identity, construction, inputs, outputs, and cleanup | Offline |
| 02 | [Research pipeline](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/course/02_research_pipeline.ipynb) | Spore fields, delivery, channels, request and reply, and pipelines | Live model |
| 03 | [Feedback loop](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/course/03_feedback_loop.ipynb) | Correlation, feedback, termination, and choreography | Offline |
| 04 | [Parallel agents](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/course/04_parallel_agents.ipynb) | Fan-out, fan-in, aggregation, completion, and partial failure | Offline |
| 05 | [Tool use](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/course/05_tool_use.ipynb) | Schemas, registration, execution, sharing, and errors | Offline |
| 06 | [Agent memory](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/course/06_agent_memory.ipynb) | Short-term, episodic, semantic, and long-term memory | Offline |
| 07 | [Qdrant vector memory](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/course/07_qdrant_integration.ipynb) | Embeddings, collections, retrieval, and cleanup | Live with Qdrant |
| 08 | [Production features](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/course/08_production_features.ipynb) | RabbitMQ, secure Spores, tracing, export, and shutdown | Local services |
| 09 | [ModelRuntime](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/course/09_model_runtime.ipynb) | Capabilities, sync and async calls, streaming, usage, and schemas | Offline |
| 10 | [Human in the loop](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/course/10_human_in_the_loop.ipynb) | Approval, editing, rejection, persistence, and resume | Live model |
| 11 | [MCP tools](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/course/11_mcp_tools.ipynb) | Discovery, namespacing, approval, invocation, timeout, and cleanup | Local services |
| 12 | [Voice and multimodal](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/course/12_voice_and_multimodal.ipynb) | Real STT, agent response, TTS, and multimodal requests | Live OpenAI |

Lessons 00 through 08 also have companion videos. Use the links in the
[notebook catalog](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/README.md), or browse the
[Praval AI YouTube channel](https://www.youtube.com/@praval-ai).

### Capstones

| Case study | What the agent team does | Mode |
|---|---|---|
| [Research Intelligence Desk](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/case_studies/research_intelligence_desk.ipynb) | Audits contradictory evidence, forces a revision, and publishes a cited decision brief | Offline |
| [Customer Support Resolution Center](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/case_studies/customer_support_resolution_center.ipynb) | Combines customer context, service state, knowledge, policy, review, and escalation | Offline |
| [Software Release Readiness Team](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/case_studies/software_release_readiness.ipynb) | Finds real test and security failures, applies a bounded repair, verifies it, and makes a release decision | Offline with local traces |
| [AI Marketing Studio](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/case_studies/marketing_studio.ipynb) | Uses multimodal evidence, structured assets, approval-protected claims, HITL resume, and campaign learning | Protected live OpenAI |

### Runnable examples

| Example | What it demonstrates | External requirement |
|---|---|---|
| [Provider-neutral fake runtime](https://github.com/aiexplorations/praval/blob/main/examples/model_runtime_fake_provider.py) | Normalized requests, responses, and usage | None |
| [Simple multi-agent system](https://github.com/aiexplorations/praval/blob/main/examples/simple_multi_agent.py) | Decorated agents and Reef delivery | None |
| [Streaming events](https://github.com/aiexplorations/praval/blob/main/examples/streaming_events.py) | Normalized streaming events | Provider key |
| [Structured output](https://github.com/aiexplorations/praval/blob/main/examples/structured_output_runtime.py) | Provider-constrained JSON output | Provider key |
| [HITL tool approval](https://github.com/aiexplorations/praval/blob/main/examples/015_hitl_tool_approval.py) | Deterministic approval-protected tool execution | None |
| [Configurable embeddings](https://github.com/aiexplorations/praval/blob/main/examples/configurable_embeddings.py) | Local and provider embedding profiles | Depends on profile |
| [Local OpenAI-compatible server](https://github.com/aiexplorations/praval/blob/main/examples/local_llm_openai_compatible.py) | Local model configuration | Local server |
| [Request-based voice agent](https://github.com/aiexplorations/praval/blob/main/examples/request_based_voice_agent.py) | STT, agent generation, and TTS | OpenAI key |
| [Distributed agents](https://github.com/aiexplorations/praval/blob/main/examples/distributed_agents_with_rabbitmq.py) | RabbitMQ-backed Reef delivery | RabbitMQ |
| [Observability quick start](https://github.com/aiexplorations/praval/blob/main/examples/observability/000_quickstart.py) | Local spans and trace inspection | Observability extra |

The [complete example manifest](https://github.com/aiexplorations/praval/blob/main/examples/manifest.toml) records execution modes,
extras, services, timeouts, and expected artifacts for release certification.

## Documentation map

| Need | Resource |
|---|---|
| Published reference | [pravalagents.com/docs/latest](https://pravalagents.com/docs/latest/) |
| Installation and first use | [Getting started](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/getting-started.md) |
| Architecture | [Core concepts](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/core-concepts.md) |
| Runtime migration | [ModelRuntime migration](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/runtime-migration.md) |
| API details | [API reference](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/api/index.rst) |
| Common failures | [Troubleshooting](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/troubleshooting.md) |
| Detailed learning course | [Notebook catalog](https://github.com/aiexplorations/praval/blob/main/examples/notebooks/README.md) |
| Release changes | [Changelog](https://github.com/aiexplorations/praval/blob/main/CHANGELOG.md) |
| Release scope | [Release notes](https://github.com/aiexplorations/praval/blob/main/docs/releases/RELEASE_NOTES_0.8.1.md) |

Build the reference documentation locally with warnings treated as errors:

```bash
make docs-html
```

## Important boundaries

- Reef is Praval's canonical agent-to-agent system. There is no second A2A
  abstraction in this release.
- `praval.mcp` is a direct MCP tools client. Provider-hosted MCP descriptors are
  a separate experimental provider capability.
- MCP support covers stdio and Streamable HTTP tool discovery and execution. It
  does not yet cover resources, prompts, server hosting, OAuth, or rich binary
  results.
- Voice APIs are request-based STT and TTS. Persistent connections with
  continuous audio and event exchange are realtime sessions and are deferred.
- Structured output is constrained by a capable provider. Praval does not claim
  universal local JSON Schema validation of provider text.
- Retries are explicit and provider-specific. Praval does not promise a hidden
  universal circuit breaker, storage fallback, or automatic reconnect layer.
- `PravalApp` owns cleanup. It is not an isolated service container.

See the [release notes](https://github.com/aiexplorations/praval/blob/main/docs/releases/RELEASE_NOTES_0.8.1.md)
for the stable scope, compatibility details, limitations, and deferred work.

## Development and release validation

```bash
make setup
source venv/bin/activate
make test
make test-cov
make lint
make type-check
make docs-html
make build
```

Praval validates examples and notebooks against the exact built wheel outside
the source tree. Normal CI runs deterministic and service-backed paths. Paid
provider calls are optional checks that developers run with their own
credentials. They never run on a push or pull request.

For a real OpenAI HITL and voice check, set models available to your account
and choose an output directory:

```bash
export OPENAI_API_KEY="your-key"
export PRAVAL_OPENAI_MODEL="your-model"
export PRAVAL_OPENAI_TRANSCRIPTION_MODEL="your-transcription-model"
export PRAVAL_OPENAI_TTS_MODEL="your-tts-model"
export PRAVAL_OPENAI_TTS_VOICE="your-voice"
export PRAVAL_DEMO_REPORT_DIR="$PWD/evidence/live-openai"

python examples/certification/live_hitl.py
python examples/certification/live_voice_roundtrip.py
```

The HITL check requires a real model-generated protected tool call and verifies
approve, edit, reject, persistence, and cross-process resume. The voice check
runs a real STT to agent to TTS to STT round trip and writes sanitized evidence
under `PRAVAL_DEMO_REPORT_DIR`. API use can incur provider charges. The
[demo certification guide](https://github.com/aiexplorations/praval/blob/main/docs/sphinx/guide/demo-certification.md)
also explains the optional all-provider workflow.

The sole uploadable distribution lives in `dist/` as one universal wheel.
Checksums, coverage, demo reports, voice evidence, and certification manifests
live in `evidence/`. Upload the named wheel, never a wildcard.

Read [Contributing](https://github.com/aiexplorations/praval/blob/main/CONTRIBUTING.md) before opening a change. Bug reports and
feature requests belong in [GitHub Issues](https://github.com/aiexplorations/praval/issues).
The project is licensed under the [MIT License](https://github.com/aiexplorations/praval/blob/main/LICENSE).
