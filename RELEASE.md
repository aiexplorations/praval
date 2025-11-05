# Manual Release Process for Praval

This document describes how to manually create and publish new versions of Praval to PyPI.

## Prerequisites

- Clean working directory (no uncommitted changes)
- All tests passing
- CHANGELOG.md updated with release notes
- PyPI credentials configured (`~/.pypirc` or API token)

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):
- **Patch** (0.7.11 → 0.7.12): Bug fixes, documentation, minor changes
- **Minor** (0.7.11 → 0.8.0): New features, backwards compatible
- **Major** (0.7.11 → 1.0.0): Breaking changes, API redesign

## Release Steps

### 1. Update Version Numbers

Use bump2version to update all version references automatically:

```bash
# Activate virtual environment
source venv/bin/activate

# Install bump2version if not already installed
pip install bump2version

# Bump version (choose one)
bump2version patch   # 0.7.11 → 0.7.12
bump2version minor   # 0.7.11 → 0.8.0
bump2version major   # 0.7.11 → 1.0.0
```

This automatically updates:
- `pyproject.toml`
- `src/praval/__init__.py`
- `.bumpversion.cfg`
- Creates a git commit and tag

### 2. Update CHANGELOG.md

Edit `CHANGELOG.md` to document the changes:

```markdown
## [0.7.7] - 2025-10-23

### Added
- New feature description

### Fixed
- Bug fix description

### Changed
- Breaking change description (for major versions)
```

Commit the changelog:
```bash
git add CHANGELOG.md
git commit -m "docs: Update CHANGELOG for v0.7.7"
```

### 3. Build the Package

```bash
# Clean previous builds
rm -rf dist/ build/ src/praval.egg-info/

# Build both wheel and source distribution
python -m build
```

Verify the build:
```bash
ls -lh dist/
# Should show:
# praval-0.7.7-py3-none-any.whl
# praval-0.7.7.tar.gz
```

### 4. Test the Package (Optional but Recommended)

Test in a clean virtual environment:

```bash
# Create test environment
python -m venv test_env
source test_env/bin/activate

# Install from local build
pip install dist/praval-0.7.7-py3-none-any.whl

# Test import
python -c "import praval; print(praval.__version__)"

# Test basic functionality
python -c "from praval import agent, chat; print('Success!')"

# Deactivate and remove
deactivate
rm -rf test_env
```

### 5. Upload to TestPyPI (Optional)

Test the upload process first:

```bash
# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ praval
```

### 6. Upload to Production PyPI

```bash
# Check package validity
twine check dist/*

# Upload to PyPI (will prompt for credentials or use .pypirc)
twine upload dist/*

# Or use API token directly
twine upload -u __token__ -p pypi-YOUR-API-TOKEN-HERE dist/*
```

### 7. Push to GitHub

```bash
# Push the version bump commit and tag
git push origin main
git push origin --tags

# Or use --follow-tags to push both at once
git push --follow-tags
```

### 8. Create GitHub Release

1. Go to https://github.com/aiexplorations/praval/releases/new
2. Select the tag you just created (e.g., `v0.7.7`)
3. Title: `Praval v0.7.7`
4. Description: Copy from CHANGELOG.md
5. Attach the distribution files from `dist/`
6. Click "Publish release"

Or use GitHub CLI:

```bash
gh release create v0.7.7 \
  --title "Praval v0.7.7" \
  --notes-file CHANGELOG.md \
  dist/praval-0.7.7-py3-none-any.whl \
  dist/praval-0.7.7.tar.gz
```

## Quick Reference Commands

```bash
# Complete release process
source venv/bin/activate
bump2version patch
# Edit CHANGELOG.md
git add CHANGELOG.md
git commit -m "docs: Update CHANGELOG for v$(python -c 'import praval; print(praval.__version__)')"
rm -rf dist/ build/
python -m build
twine check dist/*
twine upload dist/*
git push --follow-tags
```

## Verifying the Release

After publishing:

```bash
# Wait a few minutes for PyPI to index

# Install from PyPI
pip install --upgrade praval

# Verify version
python -c "import praval; print(praval.__version__)"

# Test with UV
uv pip install praval
```

## Rolling Back a Release

If you need to unpublish a version:

1. **PyPI doesn't allow deletion** of releases (only yanking)
2. To yank a release: https://pypi.org/manage/project/praval/releases/
3. Click the version → "Options" → "Yank release"
4. This prevents new installs but doesn't delete it

For local rollback:
```bash
# Delete tag
git tag -d v1.0.0
git push origin :refs/tags/v1.0.0

# Revert version bump commit
git revert <commit-hash>
git push origin main
```

## Troubleshooting

### "File already exists" error from PyPI
- You cannot re-upload the same version
- Bump to a new version (e.g., 0.7.7 → 0.7.8)

### Tests failing after version bump
- Run: `pytest tests/ -v`
- Fix issues before publishing
- May need to update tests that check version numbers

### Import errors after installation
- Check dependencies in `pyproject.toml`
- Verify all required files are in MANIFEST.in
- Test in clean environment

## Notes

- **Never bump to 1.0.0 without team discussion** - this signals API stability
- Patch versions can be released frequently for bug fixes
- Minor versions should have feature announcements
- Major versions need migration guides

---

**Current Version**: 0.7.11
**Last Updated**: 2025-11-05
