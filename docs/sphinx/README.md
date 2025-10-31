# Praval Sphinx Documentation

This directory contains the source files for Praval's comprehensive Sphinx-based HTML documentation.

## Quick Start

### Build Documentation

```bash
# From project root
make docs-html
```

This will:
1. Install documentation dependencies
2. Build HTML documentation
3. Output to `docs/_build/html/`

### View Documentation

```bash
# Build and open in browser
make docs-serve
```

Or manually:
```bash
open docs/_build/html/index.html
```

### Clean Build Artifacts

```bash
make docs-clean
```

### Check for Errors

```bash
make docs-check
```

This runs Sphinx with warnings treated as errors.

## Documentation Structure

```
docs/sphinx/
├── conf.py                 # Sphinx configuration
├── index.rst              # Documentation home page
│
├── api/                   # API Reference (auto-generated)
│   ├── index.rst         # API documentation home
│   └── generated/        # Auto-generated module docs
│
├── guide/                 # User Guides
│   ├── getting-started.md       # Quick start guide
│   ├── core-concepts.md         # Architecture and design
│   ├── memory-system.md         # Memory system (symlink)
│   ├── reef-protocol.md         # Communication protocol (symlink)
│   ├── tool-system.md          # Tool integration (symlink)
│   └── storage.md              # Storage system
│
├── tutorials/             # Step-by-step Tutorials
│   ├── first-agent.md           # Creating your first agent
│   ├── agent-communication.md   # Agent messaging patterns
│   ├── memory-enabled-agents.md # Using memory
│   ├── tool-integration.md      # Integrating tools
│   └── multi-agent-systems.md   # Complex systems
│
├── examples/              # Code Examples
│   └── index.rst         # Examples showcase
│
├── _static/               # Static Assets
│   └── custom.css        # Custom styling
│
├── _templates/            # HTML Templates
│
├── changelog.rst          # Version history
├── contributing.rst       # Contribution guide
└── license.rst           # License information
```

## Features

### Auto-Generated API Reference

The `api/` directory contains auto-generated documentation from Python docstrings using Sphinx's autodoc extension. It automatically documents:

- All public classes and functions
- Function signatures with type hints
- Parameter descriptions
- Return types
- Examples from docstrings

### Markdown Support

Thanks to MyST parser, you can write documentation in Markdown (.md) or reStructuredText (.rst):

```markdown
# My Section

This is **Markdown** with `code`.

```python
from praval import agent

@agent("example")
def my_agent(spore):
    return {"status": "done"}
```
```

### Code Highlighting

Automatic syntax highlighting for code blocks with copy buttons:

```python
@agent("researcher")
def research_agent(spore):
    result = chat("Research this topic")
    return {"findings": result}
```

### Custom Styling

The documentation uses:
- **ReadTheDocs theme** - Professional, mobile-responsive design
- **Coral color scheme** - Custom CSS matching Praval's branding
- **Copy buttons** - One-click code copying
- **Sphinx Design** - Cards, tabs, badges, and grids

### Cross-References

Link to other documentation sections:

```markdown
See [Getting Started](guide/getting-started.md)
See the API: {py:class}`praval.core.agent.Agent`
```

## Updating Documentation

### Add a New Guide

1. Create markdown file in `guide/`:
   ```bash
   touch docs/sphinx/guide/my-guide.md
   ```

2. Add to `index.rst` table of contents:
   ```rst
   .. toctree::
      :caption: User Guide

      guide/my-guide
   ```

### Add a New Tutorial

1. Create tutorial file:
   ```bash
   touch docs/sphinx/tutorials/my-tutorial.md
   ```

2. Add to index.rst:
   ```rst
   .. toctree::
      :caption: Tutorials

      tutorials/my-tutorial
   ```

### Update API Documentation

API docs are auto-generated from source code. Just:

1. Update docstrings in Python code
2. Rebuild documentation

Example good docstring:

```python
def my_function(param1: str, param2: int) -> dict:
    """
    Brief description of what the function does.

    Extended description with more details about behavior,
    edge cases, and usage patterns.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Dictionary containing:
        - key1: Description
        - key2: Description

    Raises:
        ValueError: When param1 is empty
        TypeError: When param2 is not an integer

    Example:
        >>> result = my_function("test", 42)
        >>> print(result)
        {'key1': 'value1', 'key2': 'value2'}
    """
    ...
```

## Configuration

### Sphinx Settings

Edit `conf.py` to customize:

- **Project metadata** - Name, author, version
- **Extensions** - Enable/disable Sphinx extensions
- **Theme options** - Colors, navigation, layout
- **Autodoc settings** - What to document automatically

### Theme Customization

Edit `_static/custom.css` to change:
- Colors (coral/ocean palette)
- Fonts
- Spacing
- Mobile responsiveness

## Build Options

### Full Rebuild

```bash
make docs-clean
make docs-html
```

### Fast Incremental Build

```bash
cd docs/sphinx
../../venv/bin/sphinx-build -b html . ../_build/html
```

### Check for Broken Links

```bash
cd docs/sphinx
../../venv/bin/sphinx-build -b linkcheck . ../_build/linkcheck
```

### Build PDF (requires LaTeX)

```bash
cd docs/sphinx
../../venv/bin/sphinx-build -b latex . ../_build/latex
cd ../_build/latex
make
```

## Troubleshooting

### Build Fails with Import Errors

Install documentation dependencies:
```bash
pip install -e ".[docs]"
```

### Warnings About Missing Cross-References

This is expected for:
- Stub tutorial files
- External links
- Symlinked documentation

You can safely ignore these warnings or fix them by:
1. Completing the stub files
2. Updating cross-reference paths
3. Adding `:no-index:` to suppress duplicates

### API Documentation Not Updating

Sphinx caches builds. Clean and rebuild:
```bash
make docs-clean
make docs-html
```

### Custom CSS Not Applied

Check:
1. CSS file is in `_static/custom.css`
2. Referenced in `conf.py` under `html_css_files`
3. Browser cache cleared

## Writing Tips

### Use Admonitions

```markdown
:::{note}
This is a note admonition.
:::

:::{warning}
This is a warning.
:::

:::{tip}
Pro tip: Use type hints for better docs!
:::
```

### Include Code Examples

```markdown
Here's an example:

\```python
from praval import agent, chat

@agent("example")
def my_agent(spore):
    return chat("Hello")
\```
```

### Link to API

```markdown
See the {py:func}`praval.decorators.agent` decorator.
See {py:class}`praval.core.agent.Agent` for details.
```

### Create Tables

```markdown
| Feature | Status |
|---------|--------|
| Agents  | ✅     |
| Memory  | ✅     |
| Tools   | ✅     |
```

## Deployment

### GitHub Pages

1. Build documentation:
   ```bash
   make docs-html
   ```

2. Copy `docs/_build/html/` to your GitHub Pages branch

3. Add `.nojekyll` file:
   ```bash
   touch docs/_build/html/.nojekyll
   ```

### ReadTheDocs

1. Add `.readthedocs.yml` to project root:
   ```yaml
   version: 2
   sphinx:
     configuration: docs/sphinx/conf.py
   python:
     install:
       - requirements: requirements.txt
       - method: pip
         path: .
         extra_requirements:
           - docs
   ```

2. Import project on readthedocs.org

## Further Reading

- [Sphinx Documentation](https://www.sphinx-doc.org/)
- [MyST Parser Guide](https://myst-parser.readthedocs.io/)
- [ReadTheDocs Theme](https://sphinx-rtd-theme.readthedocs.io/)
- [Sphinx Design](https://sphinx-design.readthedocs.io/)

## Contributing

When contributing documentation:

1. Follow the existing structure
2. Write in Markdown when possible
3. Include code examples
4. Test your changes with `make docs-html`
5. Check for warnings with `make docs-check`

For more details, see [Contributing Guide](contributing.rst).
