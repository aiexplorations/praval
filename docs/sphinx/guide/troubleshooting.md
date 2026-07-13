# Troubleshooting

## Capability Errors

If a call fails with a capability error, inspect the resolved profile:

```python
from praval import get_provider_registry

registry = get_provider_registry()
print(registry.resolve_capabilities("ollama", "llama3"))
```

Use explicit capability overrides only after verifying the specific provider,
model, endpoint, and server version.

## Local Provider Connection Errors

Praval connects to already-running HTTP servers. Start Ollama, vLLM, LM Studio,
llama.cpp, or your compatible server first, then configure `provider` and
`base_url`.

## Streaming Errors

Streaming adapters emit an `error` event with redacted metadata and then raise
`ProviderError`. Wrap streams in `try`/`except ProviderError` if you need custom
cleanup.

## Documentation Quality Gates

Before release, run:

```bash
make docs-html
make test
make lint
make type-check
make build
```

Documentation changes should also include:

- Sphinx build checks.
- Link checks for provider documentation links.
- Executable snippets for critical examples where practical.
- A stale model-name audit against provider docs.
- API reference coverage for new public modules.
