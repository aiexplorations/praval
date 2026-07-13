# Praval visual notebook course

These notebooks show Praval running, not just the final answer. They render agent
stages, Reef routes, Spore payloads, streaming events, intervention states, and
resource cleanup as the code executes.

## Start here

From the Praval repository:

```bash
source venv/bin/activate
python -m pip install -e ".[notebooks]"
cd examples/notebooks
jupyter lab
```

Open `course/00_architecture.ipynb`, run each cell in order, and continue through the
numbered course. The offline notebooks need no API keys. Service and live notebooks
state their prerequisites in the first cells and fail clearly when a required value
is missing.

## Course

| # | Notebook | Mode | Video |
|---:|---|---|---|
| 00 | [Architecture](course/00_architecture.ipynb) | Offline | [Watch](https://www.youtube.com/watch?v=M30U-6w_WGc) |
| 01 | [Hello world](course/01_hello_world.ipynb) | Offline | [Watch](https://www.youtube.com/watch?v=X25zLFSmXt8) |
| 02 | [Research pipeline](course/02_research_pipeline.ipynb) | Live model | [Watch](https://www.youtube.com/watch?v=u7gib_vrMMQ) |
| 03 | [Feedback loop](course/03_feedback_loop.ipynb) | Offline | [Watch](https://www.youtube.com/watch?v=uNXC_XDeVlc) |
| 04 | [Parallel agents](course/04_parallel_agents.ipynb) | Offline | [Watch](https://www.youtube.com/watch?v=VNZ_lhljPBc) |
| 05 | [Tool use](course/05_tool_use.ipynb) | Offline | [Watch](https://www.youtube.com/watch?v=40-DUQ4Cf2Q) |
| 06 | [Agent memory](course/06_agent_memory.ipynb) | Offline | [Watch](https://www.youtube.com/watch?v=sH3NkfoTZ1c) |
| 07 | [Qdrant vector memory](course/07_qdrant_integration.ipynb) | Live + Qdrant | [Watch](https://www.youtube.com/watch?v=ZhEEFfIpuJg) |
| 08 | [Production features](course/08_production_features.ipynb) | Services | [Watch](https://www.youtube.com/watch?v=wPXbCCjNBHw) |
| 09 | [ModelRuntime](course/09_model_runtime.ipynb) | Offline | New for 0.8 |
| 10 | [Human in the loop](course/10_human_in_the_loop.ipynb) | Live model | New for 0.8 |
| 11 | [MCP tools](course/11_mcp_tools.ipynb) | Local services | New for 0.8 |
| 12 | [Voice and multimodal](course/12_voice_and_multimodal.ipynb) | Live OpenAI | New for 0.8 |

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

The longer historical notebooks are preserved under `case_studies/`. They are
catalogued as reference material while the smaller course notebooks provide the
maintained, release-certified learning path.
