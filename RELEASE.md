# Praval release process

Praval publishes the exact wheel and source distribution produced by a
successful `main` CI run. Tag and publication workflows never rebuild the
package.

## Sources of truth

- `pyproject.toml` contains the authoritative package version.
- `praval.__version__` comes from installed distribution metadata.
- `CHANGELOG.md` describes user-visible changes.
- `docs/releases/RELEASE_NOTES_<version>.md` describes the release without
  copying volatile test counts or hashes.
- `dist/` contains only `.whl` and `.tar.gz` files.
- `evidence/` contains checksums, manifests, coverage, and certification data.

Run the metadata contract before freezing:

```bash
source venv/bin/activate
python scripts/check_release_metadata.py
python scripts/check_api_surface.py --report evidence/api-coverage.json
```

## Release sequence

1. Update `pyproject.toml`, changelog, release notes, examples, and current
   documentation in a reviewable PR.
2. Make the candidate commit clean and merge it to `main`.
3. Let `main` CI test Python 3.9 through 3.13 and produce the exact package and
   documentation artifacts for that commit.
4. Verify offline and service-backed demos against that wheel.
5. Manually dispatch the protected `live-demo` workflow from `main`. It must
   reuse the successful CI artifact and validate real providers, HITL,
   multimodal input, embeddings, STT, and TTS.
6. Prepare the corresponding `praval-ai` PR from the exact-wheel documentation
   artifact, but do not merge it yet.
7. Create `v<version>` on the exact certified `main` commit.
8. The tag workflow verifies commit, version, wheel hash, live certificate, and
   release notes, then pauses at the protected `pypi` environment.
9. Approve trusted publishing. The workflow publishes only `verified/dist/`
   and attaches the evidence to the GitHub release.
10. After PyPI reports the release, merge the `praval-ai` PR and verify the
    production site.

Any source change after live certification invalidates the certification and
requires a new `main` artifact and manual live run.

## Local package validation

```bash
source venv/bin/activate
python -m build
python scripts/normalize_sdist.py dist/praval-*.tar.gz
twine check dist/*.whl dist/*.tar.gz
python scripts/validate_distribution.py dist
python scripts/write_build_manifest.py dist --evidence-dir evidence
python scripts/check_release_metadata.py --dist dist
```

Do not run `twine upload dist/*` if non-distribution files have been placed in
`dist/`. The repository contract prevents that state; `twine` accepts Python
distributions, not JSON manifests or checksum files.

## Post-publication verification

In a clean environment, install from PyPI and verify package and CLI metadata:

```bash
python -m venv /tmp/praval-release-check
/tmp/praval-release-check/bin/python -m pip install --upgrade praval
/tmp/praval-release-check/bin/python -c \
  "import importlib.metadata, praval; print(praval.__version__); print(importlib.metadata.version('praval'))"
/tmp/praval-release-check/bin/praval --help
```

Verify that PyPI, the Git tag, GitHub release, `pravalagents.com` badge,
`docs/versions.json`, `docs/latest`, and the versioned documentation all report
the same version. PyPI releases cannot be replaced; use PyPI's yank mechanism
and publish a corrected version if a serious defect is found.
