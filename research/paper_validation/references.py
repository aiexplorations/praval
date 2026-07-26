"""Versioned citation registry and BibTeX export for the paper."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple
from urllib.parse import urlparse

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.9 compatibility
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]

from .manifest import SCHEMA_VERSION, Claim, ManifestError

REFERENCE_TYPES = {
    "article",
    "book",
    "inproceedings",
    "report",
    "software",
    "specification",
    "web",
}
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{7,40}$")


@dataclass(frozen=True)
class Reference:
    """One primary, official, or explicitly contextual paper source."""

    id: str
    type: str
    title: str
    authors: Tuple[str, ...]
    year: int
    url: str
    accessed: str
    primary: bool
    doi: str
    version: str
    commit: str
    venue: str
    notes: str


def _required_string(item: Mapping[str, Any], field: str, owner: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{owner}: {field} must be a non-empty string")
    return value.strip()


def _optional_string(item: Mapping[str, Any], field: str, owner: str) -> str:
    value = item.get(field, "")
    if not isinstance(value, str):
        raise ManifestError(f"{owner}: {field} must be a string")
    return value.strip()


def load_references(path: Path) -> Dict[str, Reference]:
    """Load and validate the versioned citation registry."""
    if not path.is_file():
        raise ManifestError(f"reference registry does not exist: {path}")
    with path.open("rb") as handle:
        raw = tomllib.load(handle)
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError(f"{path}: schema_version must be {SCHEMA_VERSION}")
    items = raw.get("reference")
    if not isinstance(items, list) or not items:
        raise ManifestError(f"{path}: at least one [[reference]] is required")

    references: Dict[str, Reference] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ManifestError(f"{path}: every reference must be a table")
        reference_id = _required_string(item, "id", str(path))
        if reference_id in references:
            raise ManifestError(f"duplicate reference id: {reference_id}")
        reference_type = _required_string(item, "type", reference_id)
        if reference_type not in REFERENCE_TYPES:
            raise ManifestError(
                f"{reference_id}: type must use {sorted(REFERENCE_TYPES)}"
            )
        authors_value = item.get("authors")
        if (
            not isinstance(authors_value, list)
            or not authors_value
            or not all(
                isinstance(author, str) and author.strip() for author in authors_value
            )
        ):
            raise ManifestError(f"{reference_id}: authors must be non-empty strings")
        authors = tuple(author.strip() for author in authors_value)
        if len(authors) != len(set(authors)):
            raise ManifestError(f"{reference_id}: authors must be unique")
        year = item.get("year")
        if not isinstance(year, int) or year < 1900 or year > date.today().year:
            raise ManifestError(f"{reference_id}: year is invalid")
        url = _required_string(item, "url", reference_id)
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ManifestError(f"{reference_id}: url must be an absolute HTTPS URL")
        accessed = _required_string(item, "accessed", reference_id)
        try:
            accessed_date = date.fromisoformat(accessed)
        except ValueError as exc:
            raise ManifestError(
                f"{reference_id}: accessed must use YYYY-MM-DD"
            ) from exc
        if accessed_date > date.today():
            raise ManifestError(
                f"{reference_id}: accessed date cannot be in the future"
            )
        doi = _optional_string(item, "doi", reference_id)
        if doi and not DOI_PATTERN.fullmatch(doi):
            raise ManifestError(f"{reference_id}: malformed DOI: {doi}")
        version = _optional_string(item, "version", reference_id)
        commit = _optional_string(item, "commit", reference_id)
        if commit and not COMMIT_PATTERN.fullmatch(commit):
            raise ManifestError(f"{reference_id}: malformed commit: {commit}")
        if reference_type == "software" and not (version or commit):
            raise ManifestError(
                f"{reference_id}: software requires a version or commit"
            )
        primary = item.get("primary")
        if not isinstance(primary, bool):
            raise ManifestError(f"{reference_id}: primary must be a boolean")
        references[reference_id] = Reference(
            id=reference_id,
            type=reference_type,
            title=_required_string(item, "title", reference_id),
            authors=authors,
            year=year,
            url=url,
            accessed=accessed,
            primary=primary,
            doi=doi,
            version=version,
            commit=commit,
            venue=_optional_string(item, "venue", reference_id),
            notes=_optional_string(item, "notes", reference_id),
        )
    return references


def validate_claim_citations(
    claims: Mapping[str, Claim], references: Mapping[str, Reference]
) -> None:
    """Reject claim citation keys that are absent from the registry."""
    for claim in claims.values():
        for citation in claim.citations:
            if citation not in references:
                raise ManifestError(f"{claim.id}: unknown citation: {citation}")


def _bibtex_escape(value: str) -> str:
    return (
        value.replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("_", r"\_")
    )


def references_to_bibtex(references: Mapping[str, Reference]) -> str:
    """Render the registry as deterministic BibTeX."""
    entry_type = {
        "article": "article",
        "book": "book",
        "inproceedings": "inproceedings",
        "report": "techreport",
        "software": "software",
        "specification": "misc",
        "web": "misc",
    }
    blocks = []
    for reference in references.values():
        fields = [
            ("author", " and ".join(reference.authors)),
            ("title", reference.title),
            ("year", str(reference.year)),
        ]
        if reference.venue:
            venue_field = (
                "journal"
                if reference.type == "article"
                else (
                    "booktitle" if reference.type == "inproceedings" else "howpublished"
                )
            )
            fields.append((venue_field, reference.venue))
        if reference.doi:
            fields.append(("doi", reference.doi))
        fields.append(("url", reference.url))
        fields.append(("urldate", reference.accessed))
        if reference.version:
            fields.append(("version", reference.version))
        note_parts = []
        if reference.commit:
            note_parts.append(f"commit {reference.commit}")
        if reference.notes:
            note_parts.append(reference.notes)
        if note_parts:
            fields.append(("note", "; ".join(note_parts)))
        width = max(len(name) for name, _ in fields)
        body = ",\n".join(
            f"  {name.ljust(width)} = {{{_bibtex_escape(value)}}}"
            for name, value in fields
        )
        blocks.append(f"@{entry_type[reference.type]}{{{reference.id},\n{body}\n}}")
    return "\n\n".join(blocks) + "\n"


def write_bibtex(references: Mapping[str, Reference], output_path: Path) -> Path:
    """Write canonical, deterministic BibTeX for paper generation."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(references_to_bibtex(references), encoding="utf-8")
    return output_path
