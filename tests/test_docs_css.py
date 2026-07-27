"""Regression tests for documentation theme overrides."""

import re
from pathlib import Path


CSS_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "sphinx" / "_static" / "custom.css"
)


def _declarations_for(selector: str) -> str:
    css = CSS_PATH.read_text(encoding="utf-8")
    match = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>[^}}]+)\}}", css)
    assert match is not None, f"Missing CSS rule for {selector}"
    return match.group("body")


def test_doc_table_cells_override_read_the_docs_zebra_stripes():
    """Table colors must target cells because the base theme stripes cells."""
    table_selector = (
        ".rst-content table.docutils" ":not(.field-list):not(.footnote):not(.citation)"
    )

    odd_row = _declarations_for(f"{table_selector}\n    tbody tr:nth-child(odd) td")
    even_row = _declarations_for(f"{table_selector}\n    tbody tr:nth-child(even) td")

    assert "background-color: var(--praval-bg-dark)" in odd_row
    assert "background-color: var(--praval-table-stripe)" in even_row
    assert "color: var(--praval-text)" in odd_row
    assert "color: var(--praval-text)" in even_row


def test_doc_table_header_colors_are_applied_to_header_cells():
    """Header cells must not depend on a transparent inherited background."""
    header = _declarations_for(
        ".rst-content table.docutils:not(.field-list):not(.footnote):"
        "not(.citation) thead th"
    )

    assert "background-color: var(--praval-orange)" in header
    assert "color: var(--praval-bg-darker)" in header
