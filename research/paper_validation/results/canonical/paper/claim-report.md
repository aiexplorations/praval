# Claim-to-evidence ledger

| Claim | Declared | Observed | Permitted wording |
| --- | --- | --- | --- |
| `two-plane-architecture` | proposed | validated | Praval 0.8.1 separates its coordination plane from its model execution plane. |
| `initial-agent-coordination-foundation` | validated_with_scope | validated_with_scope | Praval began with a direct Agent abstraction, then made decorated agents, Reef, and Spores its main coordination model in the 0.2.0 source state. |
| `intellectual-origins` | descriptive_only | descriptive_only | Praval's message-driven coordination model drew on the author's work with dynamical systems and population-based optimization, practical agent-framework experience, and ideas from swarm intelligence, stigmergy, and coral reef systems. |
| `first-party-development-accounts` | descriptive_only | descriptive_only | Contemporaneous first-party posts document how Praval's design, distributed coordination, applications, comparisons, and 0.8.1 transition were described during development. |
| `memory-data-transport-expansion` | validated_with_scope | validated_with_scope | The 0.5 and 0.6 series added memory, data, transport, and bounded security facilities around Praval's coordination model. |
| `coordination-operations-maturity` | validated_with_scope | validated_with_scope | The 0.7 series made the coordination model more operational through tools, observability, distributed Reef support, completion tracking, lifecycle work, and durable human intervention. |
| `pre-0-8-coordination-foundation` | validated_with_scope | validated_with_scope | By version 0.7.22, Praval already provided the Agent, Reef, and Spore coordination model plus documented tools, data, transport, observability, and completion facilities. |
| `praval-0-7-22-hitl-boundary` | validated_with_scope | validated_with_scope | Version 0.7.22 added agent-gated HITL with SQLite-backed intervention and suspended-run state. |
| `praval-0-8-1-execution-transition` | validated_with_scope | validated_with_scope | Praval 0.8.1 extended the established coordination foundation with a provider-neutral execution plane centered on ModelRuntime. |
| `runtime-provider-neutral-contract` | proposed | validated_with_scope | Praval normalizes model execution for capabilities declared by the selected provider profile. |
| `runtime-capability-fail-fast` | proposed | validated | The runtime rejects unsupported declared capabilities before provider execution. |
| `reef-choreography-scope` | proposed | validated | Praval does not require an application-level workflow orchestrator for registered Reef topologies. |
| `spore-v2-compatibility` | proposed | validated | Spore V2 preserves the legacy knowledge-only transport body while adding JSON-safe references and content parts. |
| `durable-hitl-resume` | proposed | validated_with_scope | Praval can persist and resume approval-protected tool continuations across a process boundary. |
| `mcp-tools-bounded-scope` | proposed | validated_with_scope | Praval 0.8.1 provides an async tools-only MCP client for stdio and Streamable HTTP. |
| `reef-completion-lifecycle` | proposed | validated | Praval provides completion waits and idempotent cleanup for bounded Reef workflows. |
| `embedding-compatibility` | proposed | validated_with_scope | Praval separates embedding configuration and rejects known model or dimension mismatches. |
| `observability-once` | proposed | validated | Praval stores finalized spans once and supports console, SQLite, and OTLP inspection paths. |
| `storage-service-roundtrips` | proposed | validated | Praval 0.8.1 completed round trips against the pinned storage services in the recorded environment. |
| `secure-spore-bounded-claim` | proposed | validated | Secure Spores use authenticated public-key encryption and signatures for configured peers. |
| `exact-wheel-provenance` | proposed | validated | All canonical experiments use the published Praval 0.8.1 wheel identified by its SHA-256 digest. |
| `choreography-critical-path` | proposed | validated | For independent branches in the tested workloads, Reef fan-out reduced the critical path relative to a sequential baseline. |
| `reef-scaling-bounded` | proposed | validated | The paper reports measured Reef scaling only for the registered hardware, payloads, agent counts, and backends. |
| `abstraction-costs-measured` | proposed | validated | The paper separates measured framework abstraction costs from external model latency. |
| `historical-comparison-not-evidence` | unsupported | unsupported | The paper excludes comparison values that do not satisfy its controlled protocol. |
| `controlled-comparison-bounded` | proposed | validated | For the registered controlled workload, the paper reports each framework's latency distribution, correctness, failures, model calls, token use, and cost without attributing differences to architecture alone. |
| `request-voice-bounded` | proposed | not_evaluated | Praval supports request-based OpenAI transcription and speech generation. |
