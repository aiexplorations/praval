| Version | Status | Date | Main change |
| --- | --- | --- | --- |
| 0.1.0 | development | 2025-08-03 | Established the package, direct Agent abstraction, provider integrations, state, prompts, tools, memory interfaces, and the first multi-agent components. |
| 0.2.0 | development | 2025-08-08 | Introduced the decorator-based agent API and made Reef and Spore message exchange the main multi-agent coordination path. |
| 0.5.0 | tagged release | 2025-08-09 | Added the layered memory system, knowledge-base integration, progressive examples, and reorganized package and test infrastructure. |
| 0.5.1 | tagged release | 2025-08-18 | Corrected multi-agent communication behavior and updated examples. |
| 0.6.0 | tagged release | 2025-08-19 | Added Secure Spore behavior and AMQP, MQTT, and STOMP transport adapters. |
| 0.6.1 | documented release | 2025-08-20 | Documented the async storage provider layer, storage registry, DataReference, and memory-to-storage integration. |
| 0.6.2 | tagged release | 2025-08-22 | Added containerized examples for memory and storage services and corrected their service setup. |
| 0.7.0 | tagged release | 2025-09-01 | Added PDF ingestion support to the knowledge-base path. |
| 0.7.1 | tagged release | 2025-09-01 | Corrected a ChromaDB query path used by the knowledge base. |
| 0.7.2 | development | 2025-09-02 | Introduced the registered tool system and its Python decorator. |
| 0.7.3 | tagged release | 2025-09-02 | Released the registered tool system and synchronized package version metadata. |
| 0.7.4 | tagged release | 2025-09-03 | Improved knowledge-base behavior and added focused tests. |
| 0.7.5 | tagged release | 2025-09-03 | Corrected ChromaDB collection initialization and knowledge-base integration. |
| 0.7.6 | tagged release | 2025-09-03 | Separated knowledge-base collections from conversational-memory collections. |
| 1.0.0 | excluded transient state | 2025-10-23 | Package metadata was changed to 1.0.0 and immediately reverted. |
| 0.7.7 | tagged release | 2025-10-23 | Restored the 0.7 release line and revised the release workflow. |
| 0.7.8 | tagged release | 2025-10-23 | Prepared a wheel-only release workflow and cleaned package artifacts. |
| 0.7.9 | tagged release | 2025-10-24 | Added minimal, memory, and all optional installation groups. |
| 0.7.10 | documented release | 2025-10-29 | Synchronized package metadata after fixes for notebook execution and dependency organization. |
| 0.7.11 | tagged release | 2025-11-05 | Added built-in tracing, console inspection, SQLite trace storage, and OTLP export. |
| 0.7.12 | tagged release | 2025-11-07 | Corrected Reef broadcast delivery to registered agent handlers. |
| 0.7.13 | tagged release | 2025-11-07 | Added native Spore AMQP serialization and pluggable Reef backends. |
| 0.7.14 | tagged release | 2025-11-08 | Corrected RabbitMQ-backed distributed agent consumption. |
| 0.7.15 | tagged release | 2025-11-08 | Added RabbitMQ queue consumption with channel-to-queue mapping. |
| 0.7.16 | tagged release | 2025-11-08 | Corrected default-channel resolution for chained broadcasts. |
| 0.7.17 | tagged release | 2025-12-07 | Expanded storage tests and improved test isolation. |
| 0.7.18 | tagged release | 2025-12-08 | Added explicit completion waiting and corrected broadcast channel resolution. |
| 0.7.19 | tagged release | 2025-12-09 | Routed distributed messages through the configured backend and improved error and lifecycle handling. |
| 0.7.20 | tagged release | 2025-12-09 | Corrected the RabbitMQ backend send argument order. |
| 0.7.21 | tagged release | 2026-02-09 | Stabilized Reef, Spore, tools, lifecycle cleanup, payload validation, authorization, rate limits, and observability behavior. |
| 0.7.22 | tagged release | 2026-02-21 | Added agent-gated human intervention for protected tools, with SQLite-backed approval, editing, rejection, suspension, restart, and resume. |
| 0.8.0 | withdrawn | 2026-07-18 | Prepared the provider-neutral runtime release candidate, then withdrew the uploaded package before creating a matching tag and release. |
| 0.8.1 | supported | 2026-07-18 | Retained the Agent, Reef, and Spore coordination model and added ModelRuntime, EmbeddingRuntime, provider profiles, normalized contracts, Spore V2, MCP tools, and PravalApp lifecycle ownership. |
