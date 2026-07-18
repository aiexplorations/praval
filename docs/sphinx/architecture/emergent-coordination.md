# Emergent Coordination Architecture

This page connects the 0.8.0 runtime work with Praval's original
architecture. It synthesizes the current package code and the maintained source
material in `~/Github/praval-ai`, especially the architecture, framework
comparison, scaling, and whitepaper drafts. Generated website output and PDFs
are not the source of truth for this release.

## Architectural Thesis

Praval is not only a wrapper around model providers. It is a framework for
building decentralized agent systems where coordination comes from local,
typed interactions:

- Agents are narrow, autonomous units with explicit input and output contracts.
- Reef is the communication substrate that routes messages between agents.
- Spores are structured knowledge signals, not informal chat transcripts.
- Memory, tools, HITL, storage, and observability support the agent network
  without forcing all behavior through a single orchestrator.

The model runtime added in 0.8.0 makes provider execution more explicit.
It validates capabilities, normalizes streaming events, handles structured
outputs, supports local OpenAI-compatible servers, and owns tool/HITL runtime
policy. It sits inside the agent boundary; it does not replace Reef or Spore
coordination.

Reef is Praval's canonical agent-to-agent substrate. It covers native agent
discovery and Spore delivery, including local and configured remote transports.
Praval does not add a second A2A abstraction in 0.8, and no competing A2A layer
is planned. External protocols should integrate at clear boundaries without
duplicating Reef's role.

## Coordination Model

Praval's default coordination style is emergent and message-driven. Developers
define which message types each agent handles, then agents publish typed
knowledge as work progresses. The system behavior is the result of the message
topology, not a central control loop.

This is strongest when work can be decomposed into specialized, weakly coupled
subtasks. Research, extraction, classification, review, enrichment, and report
assembly can run as separate agents when they exchange structured intermediate
state.

It is weaker when the task is strictly sequential, when every step mutates a
single shared state machine, or when a complete audit trail must follow a fixed
process definition. In those cases, an explicit graph or workflow engine may be
the better outer orchestration layer, with Praval agents used at the edges.

## Framework Positioning

Use this as a practical taxonomy, not a ranking:

| Framework style | Best fit | Main tradeoff |
| --- | --- | --- |
| Praval | Decentralized, typed agent collaboration with low ceremony | Control flow is implicit in message topology. |
| LangGraph-style graphs | Explicit state machines, branches, loops, resumable workflows | More boilerplate and state plumbing. |
| CrewAI-style roles | Human-team metaphors and thorough report generation | Higher latency and prompt overhead. |
| AutoGen-style conversations | Event-driven multi-agent conversations and enterprise integration | More runtime concepts to manage. |
| DSPy-style compilation | Optimizing prompt/program behavior against metrics | Requires evaluation data and compiler mindset. |
| Lightweight single-agent wrappers | Simple model calls with tools | Limited coordination semantics. |

Praval is a good fit when agent specialization, topology, and message contracts
matter more than a globally prescribed workflow. It is not a universal reason
to use many agents; a single model call with retrieval and tools is often the
right architecture.

## Operational Components

The main operational boundaries are:

| Component | Responsibility |
| --- | --- |
| `Agent` | Owns identity, configuration, model runtime, tools, memory hooks, and legacy compatibility. |
| `ModelRuntime` | Owns provider-neutral request validation, capability resolution, streaming events, tool/HITL policy, tracing, and usage accounting. |
| Provider adapters | Translate provider wire formats to `ModelRequest`, `ModelResponse`, and `ModelEvent`. |
| Reef | Routes Spores between agents and records communication history. |
| Spore | Carries structured knowledge and compatibility payloads across the network. |
| Memory | Stores short-term, semantic, episodic, and long-term context where configured. |
| Observability | Captures spans, metrics, redacted errors, provider usage, and agent communication. |

The key ownership rule is simple: providers translate, runtime executes, agents
coordinate, and Reef transports knowledge.

## Design Rules

- Start with decomposition analysis. Use multiple agents only when subtasks are
  specialized enough to reduce work or improve quality.
- Keep agents narrow. If an agent role cannot be stated in one sentence with a
  clear input and output, it is probably too broad.
- Publish structured intermediate knowledge. Downstream agents should consume
  typed fields such as `evidence_found`, `risk_flag`, or `summary_ready`, not
  opaque prose whenever structured data is possible.
- Treat coordination as a budget. Measure latency, token use, retry behavior,
  and failure propagation.
- Prefer explicit capability checks before provider calls. Runtime validation
  should fail early when a provider or local model cannot satisfy a request.

## Benchmarks And Claims

The benchmark material in `~/Github/praval-ai` is useful product and research
context, but release docs should treat those numbers as illustrative unless
the benchmark harness, model versions, hardware, prompts, and provider settings
are captured in this repository and run in CI or a documented benchmark job.

For 0.8.0, the maintained documentation should state architectural
tradeoffs and provide reproducible examples. It should not overstate speed or
quality claims without a versioned benchmark artifact.

## Documentation Policy

Sphinx source under `docs/sphinx` is the canonical documentation surface for
0.8.0. Content from `~/Github/praval-ai` should be ported into Sphinx as
maintained pages, examples, and ADRs. Generated website output, generated API
pages, and PDFs should remain build artifacts or legacy background.
