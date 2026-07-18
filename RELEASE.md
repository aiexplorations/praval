# Praval release process

Praval publishes one universal Python wheel. The wheel attached to GitHub must
be the same file that normal `main` CI tested and that PyPI serves. Release
workflows do not rebuild the package.

## Sources of truth

- `pyproject.toml` contains the package version.
- `praval.__version__` comes from installed distribution metadata.
- `CHANGELOG.md` describes user-visible changes.
- `docs/releases/RELEASE_NOTES_<version>.md` describes release scope without
  copied test counts or hashes.
- `dist/` contains exactly one `.whl` file and nothing else.
- `evidence/` contains checksums, manifests, coverage, and demo records.

Run the metadata contracts before the release freeze:

```bash
source venv/bin/activate
python scripts/check_release_metadata.py
python scripts/check_api_surface.py --report evidence/api-coverage.json
```

## Required and optional validation

Normal CI is required. It tests Python 3.9 through 3.13, runs quality and
coverage checks, builds exact-wheel documentation, and certifies offline and
service-backed demos against the installed wheel.

Paid live checks are optional. They are manually dispatched from trusted
`main`, never from a push or pull request. They can exercise real provider
models, model-generated HITL, multimodal input, embeddings, STT, and TTS. A
developer can also run the OpenAI checks locally with their own keys by
following the demo certification guide.

Praval Research is optional downstream integration evidence. Its state does
not block a framework patch release.

## Release sequence

1. Update the version, changelog, release notes, examples, and current docs in
   one reviewable PR.
2. Merge the clean candidate commit to `main`.
3. Let normal `main` CI pass and produce `praval-<commit>` and
   `praval-docs-<commit>` artifacts.
4. Confirm offline and service-backed demo jobs passed for that exact commit.
5. Optionally dispatch `live-demos.yml` from `main` with protected credentials.
6. Prepare the `praval-ai` PR from the exact-wheel docs artifact. Do not merge
   it while PyPI still reports the prior version.
7. Download the successful `praval-<commit>` artifact. Keep its wheel under
   `dist/` and its manifest and checksum under `evidence/`.
8. Verify the downloaded hash and distribution:

   ```bash
   (cd dist && shasum -a 256 -c ../evidence/SHA256SUMS)
   twine check dist/praval-0.8.1-py3-none-any.whl
   python scripts/validate_distribution.py dist
   python scripts/check_release_metadata.py --dist dist
   ```

9. Upload only the named wheel. Do not use a wildcard:

   ```bash
   twine upload dist/praval-0.8.1-py3-none-any.whl
   ```

10. Verify that PyPI serves the exact CI hash:

    ```bash
    python scripts/verify_pypi_wheel.py \
      evidence/build-manifest.json \
      --version 0.8.1
    ```

11. Create `v0.8.1` on the exact tested `main` commit and push the tag.
12. The tag workflow retrieves the prior CI artifacts, verifies the tag,
    documentation provenance, and PyPI wheel hash, then creates the GitHub
    release with the same wheel and evidence.
13. Merge the prepared `praval-ai` PR and verify the production site.

Any source change after the CI build requires a new CI artifact. Do not rebuild
locally and upload a different wheel under the same release plan.

## Local candidate validation

Local builds are useful before merge. They do not replace the exact `main` CI
artifact used for publication.

```bash
source venv/bin/activate
rm -rf build dist
python -m build --wheel
twine check dist/praval-0.8.1-py3-none-any.whl
python scripts/validate_distribution.py dist
python scripts/write_build_manifest.py dist --evidence-dir evidence
python scripts/check_release_metadata.py --dist dist
```

The wheel-only contract prevents the earlier Twine error where
`build-manifest.json` was selected as if it were a Python distribution. Twine
accepts wheels and source distributions, not JSON evidence files. Praval now
publishes only the named wheel and keeps every evidence file outside `dist/`.

## Post-publication verification

Install from PyPI in a clean environment and inspect the installation:

```bash
python -m venv /tmp/praval-release-check
/tmp/praval-release-check/bin/python -m pip install --upgrade praval==0.8.1
/tmp/praval-release-check/bin/praval --version
/tmp/praval-release-check/bin/praval doctor
```

Verify that PyPI, the Git tag, GitHub release, `pravalagents.com` badge,
`docs/versions.json`, `docs/latest`, and the versioned documentation report the
same version. PyPI releases cannot be replaced. If a serious defect appears,
yank the affected release and publish a new patch version.
