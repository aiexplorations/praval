# Contributing

This guide explains how to contribute changes and ship a release safely.

## Development Workflow

1. Create a branch from `main` using the `codex/` prefix.
2. Keep commits focused by concern (core code, providers, tests, examples, docs).
3. Run local quality gates before opening a PR.
4. Open a PR with:
   - change summary,
   - risk notes,
   - test evidence,
   - migration notes when API behavior changes.

## Release Workflow

Use this flow for any tagged release.

### 1. Stabilize release branch

1. Update the authoritative version in `pyproject.toml`; runtime
   `praval.__version__` is derived from installed distribution metadata.
2. Confirm release notes include:
   - feature summary,
   - breaking/behavioral changes,
   - migration guidance,
   - validation evidence.
3. Verify no unresolved TODOs or temporary debug code remain.

### 2. Run strict gates on final release candidate commit

Run all required checks and keep outputs for PR evidence:

```bash
make lint
make type-check
make test
make test-cov
python tests/test_all_examples.py
bash scripts/test-docker-examples.sh
make docs-check
make docs-html
python scripts/check_release_metadata.py
python scripts/check_api_surface.py
```

Rules:
- Do not waive failing gates for a release.
- Re-run the full gate set after any late fix.

### 3. PR topology

Use two PRs when docs are published from a separate site/docs repository:

1. PR-A: framework/package repo (code, tests, docs sources, release metadata).
2. PR-B: docs/site publish repo (generated docs, version index updates, site badges/links).

Order:
1. Merge PR-A and let `main` CI build the exact package/docs artifacts.
2. Optionally run protected live certification for that commit.
3. Prepare and validate PR-B without merging it.
4. Upload the exact CI wheel to PyPI, verify it, and tag that `main` commit.
5. Merge PR-B only after the new version appears on PyPI.

### 4. Build and publish artifacts

1. Keep exactly one wheel in `dist/`; write manifests and checksums to
   `evidence/`.
2. Validate the exact CI wheel with `twine check`, distribution validation,
   reproducibility, and clean-wheel smoke tests.
3. Upload the named CI wheel with Twine. Do not use `dist/*`.
4. Create the tag only after PyPI serves that exact wheel. The tag workflow
   verifies its hash and creates the GitHub release.
5. Do not rebuild or upload a different local artifact.
6. Smoke test installation from PyPI in a clean virtual environment.

### 5. Tag and GitHub release

1. Create and push release tag (for example `vX.Y.Z`) from merged `main`.
2. Create the GitHub release using the release notes file.
3. Attach released artifact(s) to the GitHub release when required by project policy.

### 6. Post-release verification

1. Install released version from registry and verify import/version.
2. Verify CLI entry points and critical commands.
3. Verify docs `latest` and versioned pages resolve correctly.
4. Verify the generated release evidence; do not copy volatile counts or hashes
   back into the committed release notes.

## Commit Convention

Use commit prefixes to signal intent:

- `feat:` new functionality
- `fix:` bug fix
- `docs:` documentation-only changes
- `test:` tests only
- `refactor:` non-behavioral code restructuring
- `BREAKING CHANGE:` incompatible API/behavior change

## Pull Request Checklist

- [ ] Scope is focused and documented.
- [ ] Tests added/updated for behavior changes.
- [ ] Examples updated when user-facing behavior changed.
- [ ] Docs updated (developer guide/API/tutorials/migration notes as needed).
- [ ] Strict gates pass.
- [ ] Release notes/changelog updated for release branches.
