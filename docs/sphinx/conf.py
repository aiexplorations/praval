"""
Sphinx configuration file for Praval documentation.

This configuration sets up:
- Auto-documentation from Python docstrings
- Markdown support via MyST parser
- ReadTheDocs theme with custom styling
- API reference generation
- Code examples with syntax highlighting
"""

import os
import sys
from pathlib import Path

# -- Path setup --------------------------------------------------------------
# Add the project root to sys.path to enable autodoc to find the package
docs_dir = Path(__file__).parent
project_root = docs_dir.parent.parent
src_dir = project_root / "src"

sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(project_root))

# Import version from package
try:
    from praval import __version__
except ImportError:
    __version__ = "0.7.9"

# -- Project information -----------------------------------------------------
project = "Praval"
copyright = "2025, Praval Team"
author = "Praval Team"
version = __version__
release = __version__

# -- General configuration ---------------------------------------------------
extensions = [
    # Core Sphinx extensions
    "sphinx.ext.autodoc",           # Auto-generate docs from docstrings
    "sphinx.ext.autosummary",       # Generate summary tables
    "sphinx.ext.napoleon",          # Support for NumPy and Google style docstrings
    "sphinx.ext.viewcode",          # Add links to highlighted source code
    "sphinx.ext.intersphinx",       # Link to other project documentation
    "sphinx.ext.todo",              # Support for TODO items
    "sphinx.ext.coverage",          # Check documentation coverage
    "sphinx.ext.githubpages",       # Create .nojekyll for GitHub Pages

    # Third-party extensions
    "sphinx_autodoc_typehints",     # Better type hints rendering
    "myst_parser",                  # Markdown support
    "sphinx_copybutton",            # Add copy button to code blocks
    "sphinx_design",                # Cards, tabs, grids, badges
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# The suffix(es) of source filenames.
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# The master toctree document.
master_doc = "index"

# -- Options for HTML output -------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

html_theme_options = {
    "navigation_depth": 4,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "includehidden": True,
    "titles_only": False,
    "logo_only": False,
    "display_version": True,
    "prev_next_buttons_location": "bottom",
    "style_external_links": True,
}

# Custom CSS and JS files
html_css_files = [
    "custom.css",
]

html_js_files = [
    "version-switcher.js",
]

html_title = f"Praval {version}"
html_short_title = "Praval"
html_logo = "_static/praval-logo.png"
html_favicon = "_static/praval-logo.png"

# If true, "Created using Sphinx" is shown in the HTML footer
html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer
html_show_copyright = True

# -- Extension configuration -------------------------------------------------

# -- autodoc configuration
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
    "show-inheritance": True,
}

autodoc_typehints = "description"
autodoc_type_aliases = {
    "SporeType": "praval.core.reef.SporeType",
}

# -- napoleon configuration (for Google/NumPy style docstrings)
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = True
napoleon_type_aliases = None
napoleon_attr_annotations = True

# -- autosummary configuration
autosummary_generate = True
autosummary_imported_members = False

# -- intersphinx configuration
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
    "openai": ("https://platform.openai.com/docs/api-reference", None),
}

# -- myst_parser configuration (Markdown support)
myst_enable_extensions = [
    "colon_fence",      # ::: fences for directives
    "deflist",          # Definition lists
    "substitution",     # Variable substitution
    "tasklist",         # Task lists
]

myst_heading_anchors = 3

# -- copybutton configuration
copybutton_prompt_text = r">>> |\.\.\. |\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: "
copybutton_prompt_is_regexp = True
copybutton_remove_prompts = True

# -- todo extension configuration
todo_include_todos = True

# -- Code highlighting
pygments_style = "sphinx"
highlight_language = "python3"

# -- Options for LaTeX output (if needed for PDF generation)
latex_elements = {
    "papersize": "letterpaper",
    "pointsize": "10pt",
    "preamble": "",
    "figure_align": "htbp",
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto, manual, or own class]).
latex_documents = [
    (master_doc, "Praval.tex", "Praval Documentation", "Praval Team", "manual"),
]

# -- Options for manual page output
man_pages = [
    (master_doc, "praval", "Praval Documentation", [author], 1)
]

# -- Options for Texinfo output
texinfo_documents = [
    (
        master_doc,
        "Praval",
        "Praval Documentation",
        author,
        "Praval",
        "A composable Python framework for LLM-based agents.",
        "Miscellaneous",
    ),
]
