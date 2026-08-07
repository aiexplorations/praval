| Claim | Status | Experiment evidence | Permitted wording |
| --- | --- | --- | --- |
| durable-hitl-resume | validated_with_scope | hitl-process-recovery (passed), live-capability-matrix (not_run) | Praval can persist and resume approval-protected tool continuations across a process boundary. |
| mcp-tools-bounded-scope | validated_with_scope | mcp-safety (passed), live-capability-matrix (not_run) | Praval 0.8.1 provides an async tools-only MCP client for stdio and Streamable HTTP. |
| reef-completion-lifecycle | validated | lifecycle-failure (passed) | Praval provides completion waits and idempotent cleanup for bounded Reef workflows. |
| embedding-compatibility | validated_with_scope | data-observability-contracts (passed), service-integrations (passed), live-capability-matrix (not_run) | Praval separates embedding configuration and rejects known model or dimension mismatches. |
| observability-once | validated | data-observability-contracts (passed), service-integrations (passed), abstraction-overhead (passed) | Praval stores finalized spans once and supports console, SQLite, and OTLP inspection paths. |
| storage-service-roundtrips | validated | data-observability-contracts (passed), service-integrations (passed) | Praval 0.8.1 completed round trips against the pinned storage services in the recorded environment. |
| secure-spore-bounded-claim | validated | secure-spore-behavior (passed), abstraction-overhead (passed) | Secure Spores use authenticated public-key encryption and signatures for configured peers. |
| abstraction-costs-measured | validated | abstraction-overhead (passed) | The paper separates measured framework abstraction costs from external model latency. |
