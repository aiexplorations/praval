# Documentation publication

Praval documentation is generated in the framework repository and published
from the separate `praval-ai` website repository.

## Exact-wheel documentation artifact

Normal `main` CI:

1. builds the exact release wheel;
2. installs that wheel in a clean environment with the `docs` extra;
3. clears `PYTHONPATH` and prevents Sphinx from inserting `src/`;
4. builds with warnings as errors;
5. removes doctrees, caches, and backup files; and
6. uploads `praval-docs-<commit>` containing `site/` and
   `documentation-manifest.json`.

The manifest records the commit SHA, installed version, wheel filename and
SHA-256, documentation tree SHA-256, and file count.

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

Prepare and validate the website PR before release. Merge it only after PyPI
serves the exact wheel for the new version.

## Cutover order

1. Merge the framework candidate to `main`.
2. Complete normal exact-wheel CI. Live provider checks are optional.
3. Prepare the `praval-ai` PR from the exact-wheel docs artifact.
4. Upload the named CI wheel to PyPI and verify its hash.
5. Tag the tested commit and let the tag workflow create the GitHub release.
6. Merge the website PR and let Railway deploy `praval-ai/main`.
7. Verify the homepage badge, version index, `docs/latest`, and versioned docs.

Historical documentation directories are immutable. Never rebuild an older
version from a newer source checkout.
