# Documentation Quality

Sphinx source under `docs/sphinx` is the canonical documentation surface.
Generated HTML, generated API pages, and generated PDFs are build artifacts.
Do not hand-edit generated output.

## Release Gates

Run these gates before publishing docs:

```bash
make docs-html
make test
make lint
make type-check
make build
```

For provider and model updates, also run a stale model-name audit against the
official provider documentation:

- [OpenAI model docs](https://platform.openai.com/docs/models)
- [Anthropic model docs](https://docs.anthropic.com/en/docs/about-claude/models)
- [Gemini model docs](https://ai.google.dev/gemini-api/docs/models)

The provider registry is versioned release metadata, not a live catalog.
Before publishing a package, verify every documented default and every
`ProviderProfile` model name against provider docs. Remove placeholder names,
record endpoint assumptions, and add tests for new profiles.

Source material from `~/Github/praval-ai` should be treated as product and
architecture input. Port durable content into Sphinx pages, examples, or ADRs;
do not point users at generated website output as the authoritative docs for a
package release.

## API Coverage

Every public runtime surface should have an API reference entry:

- `praval.models`
- `praval.model_runtime`
- `praval.providers.registry`
- `praval.providers.openai`
- `praval.providers.anthropic`
- `praval.providers.cohere`
- `praval.providers.gemini`
- `praval.providers.openai_compatible`

New public classes or functions should include docstrings and at least one
task-oriented guide page or example.

## Example Policy

Each major feature should have:

- A minimal example that shows the smallest useful call.
- A realistic example that includes options, error handling, or integration.
- An offline fake-provider or local-server alternative when the live example
  would require real provider credentials.

Examples should avoid hardcoded secrets. Use environment variables for provider
keys and skip network-dependent execution in automated tests unless the test
explicitly starts a fake local service.
