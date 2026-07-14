# Praval visual notebook course

This is a two-tier learning experience. The numbered course explains Praval from
first principles and keeps optional implementation detail in **Under the hood**
sections. The case studies assume those foundations and concentrate on architecture,
tradeoffs, and complete systems.

Every notebook shows Praval running, not just the final answer. It renders agent
stages, Reef routes, Spore payloads, runtime requests, memory state, tool calls,
interventions, service boundaries, and cleanup as the code executes.

## Start here

From the Praval repository:

```bash
source venv/bin/activate
python -m pip install -e ".[notebooks]"
cd examples/notebooks
jupyter lab
```

Open `course/00_architecture.ipynb`, run each cell in order, and continue through the
numbered course. The first three lessons explain Agent, Reef, Spore, handlers,
identity, delivery, channels, and lifecycle without assuming prior Praval knowledge.
The offline notebooks need no API keys. Service and live notebooks state their
prerequisites in the first cells and fail clearly when a required value is missing.

Each course notebook follows the same rhythm: mental model, message-flow diagram,
small runnable steps, runtime inspection, guided exercise, common correction,
optional internals, recap, and cleanup.

## Learning paths

- **New to Praval:** run `00` through `06` in order, then choose a case study.
- **Building model-backed agents:** run `00`, `01`, `05`, `09`, and `10`.
- **Distributed and external tools:** run `00`, `02`, `04`, `08`, and `11`.
- **Memory and retrieval:** run `00`, `01`, `06`, and `07`, then the conversational
  memory case study.
- **Voice and multimodal:** run `00`, `01`, `09`, and `12`.

## Course

| # | Notebook | Level | Time | Mode | Video |
|---:|---|---|---:|---|---|
| 00 | [Architecture](course/00_architecture.ipynb) | Fundamentals | 20 min | Offline | [Watch](https://www.youtube.com/watch?v=M30U-6w_WGc) |
| 01 | [Hello world](course/01_hello_world.ipynb) | Fundamentals | 25 min | Offline | [Watch](https://www.youtube.com/watch?v=X25zLFSmXt8) |
| 02 | [Research pipeline](course/02_research_pipeline.ipynb) | Fundamentals | 35 min | Live model | [Watch](https://www.youtube.com/watch?v=u7gib_vrMMQ) |
| 03 | [Feedback loop](course/03_feedback_loop.ipynb) | Fundamentals | 30 min | Offline | [Watch](https://www.youtube.com/watch?v=uNXC_XDeVlc) |
| 04 | [Parallel agents](course/04_parallel_agents.ipynb) | Fundamentals | 30 min | Offline | [Watch](https://www.youtube.com/watch?v=VNZ_lhljPBc) |
| 05 | [Tool use](course/05_tool_use.ipynb) | Fundamentals | 30 min | Offline | [Watch](https://www.youtube.com/watch?v=40-DUQ4Cf2Q) |
| 06 | [Agent memory](course/06_agent_memory.ipynb) | Fundamentals | 30 min | Offline | [Watch](https://www.youtube.com/watch?v=sH3NkfoTZ1c) |
| 07 | [Qdrant vector memory](course/07_qdrant_integration.ipynb) | Advanced | 35 min | Live + Qdrant | [Watch](https://www.youtube.com/watch?v=ZhEEFfIpuJg) |
| 08 | [Production features](course/08_production_features.ipynb) | Advanced | 40 min | Services | [Watch](https://www.youtube.com/watch?v=wPXbCCjNBHw) |
| 09 | [ModelRuntime](course/09_model_runtime.ipynb) | Advanced | 35 min | Offline | New for 0.8 |
| 10 | [Human in the loop](course/10_human_in_the_loop.ipynb) | Advanced | 40 min | Live model | New for 0.8 |
| 11 | [MCP tools](course/11_mcp_tools.ipynb) | Advanced | 40 min | Local services | New for 0.8 |
| 12 | [Voice and multimodal](course/12_voice_and_multimodal.ipynb) | Advanced | 45 min | Live OpenAI | New for 0.8 |

Videos `00` through `08` were recorded for the earlier course. Their concepts remain
useful, while the executable notebook code is maintained for Praval 0.8.

## Execution modes

- **Offline** uses real Praval Agent, Reef, Spore, memory, tool, and runtime paths
  without external APIs.
- **Services** uses real local infrastructure, such as RabbitMQ, OTLP, or official MCP
  servers.
- **Live** uses real provider APIs. Live voice performs STT, agent generation, TTS,
  and a second STT pass. A mock does not satisfy these notebooks.

The exact requirements, extras, services, timeouts, and video mappings live in
[`manifest.toml`](manifest.toml). Release automation executes notebooks against the
already-built wheel outside the repository source tree.

## Case studies

The capstones explain architecture and important decisions without narrating routine
Python. All four are maintained and release-certified.

| Case study | Prerequisites | Mode | Time |
|---|---|---|---:|
| [Building an agent team](case_studies/building_agents_tutorial.ipynb) | 01, 02, 04, 05, 06 | Offline | 45 min |
| [Conversational memory assistant](case_studies/conversational_memory_agent.ipynb) | 06 | Offline | 35 min |
| [Student analytics pipeline](case_studies/student_analytics.ipynb) | 02, 04, 05 | Offline | 45 min |
| [AI-powered student analytics](case_studies/student_analytics_ai.ipynb) | 09, 10, deterministic analytics case | Protected live OpenAI | 45 min |

Normal CI executes ten offline notebooks and two service notebooks against the exact
wheel. The five live notebooks execute only through protected manual certification.
