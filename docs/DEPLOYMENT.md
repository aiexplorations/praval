# Documentation Deployment Guide

This document explains how Praval's documentation is built, versioned, and deployed to the praval-ai website.

## Overview

Praval documentation uses **Sphinx** with the **ReadTheDocs** theme and is deployed to the praval-ai website with full version tracking and switching capabilities.

### Key Features

- ✅ **Version tracking** - Each Praval release gets its own documentation
- ✅ **Version banner** - Prominent banner showing current version
- ✅ **Version switcher** - Dropdown to switch between doc versions
- ✅ **Latest docs** - Always accessible at `/docs/latest/`
- ✅ **Dark theme** - Optimized for readability with orange accents
- ✅ **Praval logo** - Custom branding throughout

## Quick Commands

### Build Documentation

```bash
# Clean build
make docs-clean

# Build HTML documentation
make docs-html

# Build and open in browser
make docs-serve

# Check for errors
make docs-check
```

### Deploy to Website

```bash
# Build and deploy to praval-ai website
make docs-deploy

# Or manually
./scripts/deploy-docs.sh
```

## Documentation Structure

### In Praval Repository

```
docs/
├── sphinx/                    # Sphinx source files
│   ├── conf.py               # Sphinx configuration
│   ├── index.rst             # Documentation home
│   ├── api/                  # Auto-generated API reference
│   ├── guide/                # User guides
│   ├── tutorials/            # Step-by-step tutorials
│   ├── examples/             # Code examples
│   ├── _static/              # CSS, JS, images
│   │   ├── custom.css        # Dark theme styling
│   │   ├── version-switcher.js
│   │   └── praval-logo.png
│   └── _templates/           # Custom HTML templates
│       └── layout.html       # Version banner template
└── _build/html/              # Generated HTML (not in git)
```

### In praval-ai Website

```
praval-ai/
└── docs/
    ├── index.html            # Documentation landing page
    ├── versions.json         # Version metadata
    ├── latest/               # Latest release docs
    │   └── [full sphinx output]
    └── v0.7.9/              # Version-specific docs
        └── [full sphinx output]
```

## Version Management

### How Versions Work

1. **Version in Code**: Extracted from `src/praval/__init__.py`
   ```python
   __version__ = "0.7.9"
   ```

2. **Sphinx Configuration**: Automatically uses version from package
   ```python
   from praval import __version__
   version = __version__
   release = __version__
   ```

3. **Deployment**: Script creates versioned directories
   ```bash
   docs/v0.7.9/     # Specific version
   docs/latest/     # Symlink or copy of latest
   ```

4. **Version Metadata**: `versions.json` tracks all versions
   ```json
   {
     "current": "0.7.9",
     "latest": "0.7.9",
     "versions": [
       {
         "version": "0.7.9",
         "url": "/docs/v0.7.9/",
         "title": "v0.7.9 (latest)"
       }
     ]
   }
   ```

### Version Banner

Every documentation page displays a sticky banner showing:
- Current version badge
- Message: "You are viewing documentation for Praval v0.7.9"
- Link to latest docs

Implemented in `docs/sphinx/_templates/layout.html`.

### Version Switcher

A dropdown in the sidebar allows switching between:
- Latest (recommended)
- Specific versions (v0.7.9, v0.7.8, etc.)

Implemented in `docs/sphinx/_static/version-switcher.js`.

## Deployment Process

### Automated Deployment

```bash
# From Praval repository root
make docs-deploy
```

This will:
1. Build fresh HTML documentation
2. Copy to `~/Github/praval-ai/docs/v{version}/`
3. Update `~/Github/praval-ai/docs/latest/`
4. Create/update `versions.json`
5. Create docs landing page

### Manual Deployment

```bash
# 1. Build documentation
make docs-html

# 2. Deploy
./scripts/deploy-docs.sh

# 3. Navigate to website repo
cd ~/Github/praval-ai

# 4. Commit changes
git add docs/
git commit -m "docs: Add Praval v0.7.9 documentation"
git push
```

### Deploying Older Versions

To deploy documentation for a specific version:

```bash
# Checkout the version tag
git checkout v0.7.8

# Deploy with explicit version
./scripts/deploy-docs.sh 0.7.8

# Return to main
git checkout main
```

## Website Integration

### Navigation Link

The praval-ai website has been updated with a documentation link:

```html
<li><a href="docs/" class="nav-docs">📚 Docs</a></li>
```

### Version Badge

Updated to match current version:

```html
<span class="badge">v0.7.9</span>
```

## Theme Customization

### Color Scheme

**Dark theme with orange accents:**
- Background: `#1e1e1e` (dark gray)
- Text: `#e0e0e0` (light gray)
- Accent: `#FF6B35` (Praval orange)

### Syntax Highlighting

High-contrast Dracula-inspired colors:
- Keywords: Bright pink (`#ff79c6`)
- Strings: Bright green (`#50fa7b`)
- Functions: Bright cyan (`#8be9fd`)
- Classes: Bright purple (`#bd93f9`)
- Comments: Muted blue (`#6272a4`)

Configured in `docs/sphinx/_static/custom.css`.

### Logo

Praval logo displayed in:
- Sidebar header
- Browser favicon
- Documentation landing page

## Troubleshooting

### Documentation Not Building

**Check virtual environment:**
```bash
# Ensure venv exists
ls venv/

# If not, create it
make setup

# Install docs dependencies
pip install -e ".[docs]"
```

### Deployment Script Fails

**Common issues:**

1. **praval-ai repo not found**
   ```bash
   # Verify path
   ls ~/Github/praval-ai/
   ```

2. **Docs not built**
   ```bash
   # Build first
   make docs-html
   ```

3. **Permission errors**
   ```bash
   # Make script executable
   chmod +x scripts/deploy-docs.sh
   ```

### Version Switcher Not Working

**Check these files exist:**
- `docs/_build/html/_static/version-switcher.js`
- `docs/versions.json` (in website repo)

**Verify versions.json format:**
```bash
cd ~/Github/praval-ai
cat docs/versions.json | python -m json.tool
```

### Logo Not Showing

**Check logo exists:**
```bash
ls docs/sphinx/_static/praval-logo.png
ls docs/_build/html/_static/praval-logo.png
```

## Best Practices

### Before Releasing a New Version

1. **Update version** in `src/praval/__init__.py`
2. **Update CHANGELOG.md** with release notes
3. **Build and test docs** locally
   ```bash
   make docs-html
   make docs-serve
   ```
4. **Deploy to website**
   ```bash
   make docs-deploy
   ```
5. **Commit both repos**
   ```bash
   # Praval repo
   git add .
   git commit -m "docs: Update for v0.7.10"
   git push

   # praval-ai repo
   cd ~/Github/praval-ai
   git add docs/
   git commit -m "docs: Add Praval v0.7.10 documentation"
   git push
   ```

### Documentation Updates Without Version Change

If you're updating docs for the current version:

1. **Make changes** to `docs/sphinx/` files
2. **Rebuild**
   ```bash
   make docs-clean
   make docs-html
   ```
3. **Deploy**
   ```bash
   make docs-deploy
   ```
4. **Commit to website**
   ```bash
   cd ~/Github/praval-ai
   git add docs/
   git commit -m "docs: Update v0.7.9 documentation"
   git push
   ```

### Testing Locally

Before deploying to the website, test the docs locally:

```bash
# Build docs
make docs-html

# Start a local server
cd docs/_build/html
python -m http.server 8000

# Open in browser
open http://localhost:8000
```

## Files Created/Modified

### New Files

**In Praval repo:**
- `docs/sphinx/_static/custom.css` - Dark theme
- `docs/sphinx/_static/version-switcher.js` - Version dropdown
- `docs/sphinx/_static/praval-logo.png` - Logo
- `docs/sphinx/_templates/layout.html` - Version banner
- `scripts/deploy-docs.sh` - Deployment script
- `docs/DEPLOYMENT.md` - This file

**In praval-ai repo:**
- `docs/index.html` - Documentation landing page
- `docs/versions.json` - Version metadata
- `docs/v0.7.9/` - Version-specific docs
- `docs/latest/` - Latest release docs

### Modified Files

**In Praval repo:**
- `docs/sphinx/conf.py` - Added logo, version settings
- `Makefile` - Added `docs-deploy` target
- `pyproject.toml` - Added `[docs]` dependencies

**In praval-ai repo:**
- `index.html` - Added docs navigation link, updated version

## Maintenance

### Adding a New Documentation Section

1. **Create new .md or .rst file** in appropriate directory
2. **Add to index.rst** table of contents
3. **Rebuild and deploy**

### Updating Existing Content

1. **Edit .md/.rst files** or Python docstrings
2. **Rebuild**: `make docs-html`
3. **Deploy**: `make docs-deploy`

### Removing Old Versions

To remove outdated documentation versions:

```bash
cd ~/Github/praval-ai

# Remove version directory
rm -rf docs/v0.7.5/

# Update versions.json manually
# Remove the version entry from the JSON file

# Commit
git add docs/
git commit -m "docs: Remove v0.7.5 documentation"
git push
```

## Support

For issues with documentation:

1. Check this guide
2. Review Sphinx documentation: https://www.sphinx-doc.org/
3. Check ReadTheDocs theme docs: https://sphinx-rtd-theme.readthedocs.io/
4. Open an issue in the Praval repository

## Related Documentation

- [Sphinx Documentation README](sphinx/README.md) - Technical details
- [CHANGELOG.md](../CHANGELOG.md) - Version history
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
