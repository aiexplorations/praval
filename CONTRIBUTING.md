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

1. Ensure version metadata is updated consistently (`pyproject.toml`, package `__init__`, changelog, release notes).
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
```

Rules:
- Do not waive failing gates for a release.
- Re-run the full gate set after any late fix.

### 3. PR topology

Use two PRs when docs are published from a separate site/docs repository:

1. PR-A: framework/package repo (code, tests, docs sources, release metadata).
2. PR-B: docs/site publish repo (generated docs, version index updates, site badges/links).

Order:
1. Merge PR-A.
2. Merge PR-B.
3. Tag and publish release from `main`.

### 4. Build and publish artifacts

1. Clean old build outputs (`dist/`, `build/`, `*.egg-info`).
2. Build artifacts according to release policy (wheel-only or wheel+sdist).
3. Validate artifacts (`twine check`).
4. Upload artifacts (`twine upload`).
5. Smoke test installation from package registry in a clean virtual environment.

### 5. Tag and GitHub release

1. Create and push release tag (for example `vX.Y.Z`) from merged `main`.
2. Create the GitHub release using the release notes file.
3. Attach released artifact(s) to the GitHub release when required by project policy.

### 6. Post-release verification

1. Install released version from registry and verify import/version.
2. Verify CLI entry points and critical commands.
3. Verify docs `latest` and versioned pages resolve correctly.
4. Record final evidence in release notes or release checklist.

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
