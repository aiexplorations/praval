# Documentation publication

Praval documentation is generated in the framework repository and published
from the separate `praval-ai` website repository.

## Release artifact

Normal `main` CI:

1. builds the exact wheel and sdist;
2. installs that wheel in a clean environment with the `docs` extra;
3. clears `PYTHONPATH` and prevents Sphinx from inserting `src/`;
4. builds with warnings as errors;
5. removes doctrees, caches, and backup files; and
6. uploads `praval-docs-<commit>` containing `site/` and
   `documentation-manifest.json`.

The manifest records commit SHA, installed version, wheel filename and SHA-256,
documentation tree SHA-256, and file count.

## Stage the website change

Use a clean `praval-ai` checkout or worktree so unrelated site edits are not
included:

```bash
./scripts/deploy-docs.sh \
  /path/to/praval-docs-artifact \
  /path/to/clean/praval-ai-worktree
```

The staging command verifies the tree hash, writes `docs/v<version>` and an
identical `docs/latest`, stores the documentation manifest in both trees, and
updates `docs/versions.json` while preserving historical versions.

Prepare and validate the website PR before release, but do not merge it while
PyPI still reports the previous version.

## Cutover order

1. Merge the framework candidate to `main`.
2. Complete normal and protected live certification for the exact wheel.
3. Prepare the `praval-ai` PR from the exact-wheel docs artifact.
4. Tag and publish the certified wheel through trusted publishing.
5. Confirm the version on PyPI.
6. Merge the website PR and let Railway deploy `praval-ai/main`.
7. Verify the homepage badge, version index, `docs/latest`, and versioned docs.

Historical documentation directories are immutable. Never rebuild an older
version from a newer source checkout.
