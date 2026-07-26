# Praval 0.8.1 feature-diff audit

- Comparison: `v0.7.22..v0.8.1`
- Base commit: `ee056118f9daa444166bd09148a3ca42649ccfd3`
- Release commit: `fa20513e7cc982fd8d94b81c19e55a9427a6f48c`
- Release commits: 47
- Changed files: 320
- Changed public source files: 42
- Inventory entries: 30
- Status: **passed**

## Capability inventory

| Capability | Classification | Changed source files | Evidence files |
|---|---|---:|---:|
| `application-lifecycle` | stable | 1 | 2 |
| `durable-hitl` | optional | 3 | 2 |
| `embedding-runtime` | optional | 1 | 2 |
| `exact-wheel-certification` | stable | 2 | 2 |
| `legacy-chat-api` | compatibility | 1 | 1 |
| `mcp-non-tool-capabilities` | unsupported | 1 | 0 |
| `mcp-tools-client` | optional | 1 | 2 |
| `memory-system` | optional | 1 | 2 |
| `model-runtime` | stable | 2 | 1 |
| `observability` | optional | 2 | 2 |
| `provider-anthropic` | stable | 1 | 2 |
| `provider-cohere` | stable | 1 | 2 |
| `provider-gemini` | stable | 1 | 2 |
| `provider-hosted-descriptors` | experimental | 2 | 1 |
| `provider-openai` | stable | 1 | 2 |
| `provider-openai-compatible` | stable | 2 | 2 |
| `realtime-model-sessions` | unsupported | 1 | 0 |
| `reef-async-completion` | stable | 2 | 2 |
| `reef-coordination` | stable | 2 | 2 |
| `request-voice` | optional | 2 | 2 |
| `runtime-multimodal` | stable | 2 | 2 |
| `runtime-reasoning` | stable | 2 | 2 |
| `runtime-streaming` | stable | 2 | 2 |
| `runtime-structured-output` | stable | 2 | 2 |
| `runtime-sync-async` | stable | 2 | 2 |
| `runtime-tools` | stable | 1 | 2 |
| `runtime-usage-errors` | stable | 2 | 2 |
| `secure-transports` | optional | 0 | 2 |
| `spore-v2` | stable | 1 | 2 |
| `storage-system` | optional | 1 | 2 |

## Unmatched changed implementation files

These files are retained for review because changed implementation support surfaces do not necessarily define distinct paper capabilities.

- `src/praval/__init__.py`
- `src/praval/cli.py`
- `src/praval/core/agent_runner.py`
- `src/praval/core/secure_reef.py`
- `src/praval/hitl/models.py`
- `src/praval/mcp/__init__.py`
- `src/praval/memory/embedded_store.py`
- `src/praval/memory/long_term_memory.py`
- `src/praval/memory/semantic_memory.py`
- `src/praval/memory/short_term_memory.py`
- `src/praval/observability/__init__.py`
- `src/praval/observability/export/console_viewer.py`
- `src/praval/observability/instrumentation/utils.py`
- `src/praval/observability/tracing/tracer.py`
- `src/praval/providers/factory.py`
- `src/praval/storage/base_provider.py`
- `src/praval/storage/providers/postgresql.py`
- `src/praval/storage/providers/qdrant_provider.py`
- `src/praval/storage/providers/redis_provider.py`
- `src/praval/storage/providers/s3_provider.py`

The JSON companion preserves the complete file and commit inventory.
