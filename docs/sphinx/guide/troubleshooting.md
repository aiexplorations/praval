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

## Provider Errors

Provider failures raise a typed `ProviderError` subclass (see
{doc}`providers`). Check the error before changing configuration:

- `ProviderAuthenticationError`: the key in `api_key_env` is missing, wrong or
  lacks access to the model.
- `ProviderQuotaError`: the account is out of quota or credit. Retrying will
  not help; `error_code` names the provider's reason.
- `ProviderRateLimitError` and `ProviderUnavailableError`: Praval already
  retried the request `retries` times. Raise `retries` for bursty workloads, or
  reduce concurrency. `retry_after_seconds` is the provider's own hint.
- `ProviderTransportError`: the server could not be reached or the request
  timed out. For local servers, confirm the server is running; for slow models,
  raise `timeout`.
- `ToolRoundLimitError`: the model kept requesting tools. Raise
  `max_tool_rounds` only if the task needs more rounds.

`request_id` identifies the failed request in the provider's support channels.
Retries are logged at `INFO` on the `praval.model_runtime` logger and recorded
in the run's observation.

## Streaming Errors

Streaming adapters emit an `error` event with redacted metadata and then raise
a `ProviderError` subclass. A stream that fails before its first event is
retried like any other request, and the discarded attempt's `error` event is
not emitted. Once an event has been emitted, a failure is raised without retry.
Wrap streams in `try`/`except ProviderError` if you need custom cleanup.

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
