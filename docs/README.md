# Praval documentation sources

`docs/sphinx` is the canonical reference documentation for the current
framework. The Jupyter course under `examples/notebooks` is the detailed
learning experience.

## Maintained surfaces

- `docs/sphinx/guide`: task-oriented guides and architectural contracts.
- `docs/sphinx/tutorials`: concise tested recipes.
- `docs/sphinx/api`: generated reference pages.
- `docs/api-surface.toml`: classification of every top-level public export.
- `docs/feature-claims.toml`: claims that may be repeated in README/site copy,
  with implementation evidence.
- `docs/releases`: human release notes without volatile CI figures.

Long-form generated manuals and superseded documents are historical material.
They are not a source for current API examples unless their content has been
ported into Sphinx.

## Build and validate

```bash
source venv/bin/activate
python scripts/check_api_surface.py
python scripts/check_release_metadata.py
sphinx-build -b html -W --keep-going docs/sphinx docs/_build/html
```

Release documentation is built again against the installed exact wheel:

```bash
python scripts/build_exact_wheel_docs.py \
  --dist dist \
  --output evidence/documentation \
  --commit "$(git rev-parse HEAD)"
```

The release artifact records the wheel hash, installed version, commit, and
HTML tree hash. Generated HTML, doctrees, caches, backups, and PDFs do not
belong in the source repository. The isolated builder installs the
documentation, MCP, and secure-transport extras so autodoc can resolve the
supported public type annotations.

See [DEPLOYMENT.md](DEPLOYMENT.md) for the coordinated `praval-ai` cutover.
