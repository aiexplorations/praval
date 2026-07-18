#!/usr/bin/env python3
"""Validate release version metadata and current documentation surfaces."""

from __future__ import annotations

import argparse
import email
import importlib.metadata
import re
import sys
import zipfile
from pathlib import Path
from typing import Iterable, List, Optional

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.9/3.10 compatibility
    import tomli as tomllib


CURRENT_SURFACES = (
    "README.md",
    "RELEASE.md",
    "src/praval",
    "scripts",
    "docs/sphinx",
    ".github/workflows",
)


def project_version(root: Path) -> str:
    """Read the authoritative project version."""
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def wheel_version(dist_dir: Path) -> Optional[str]:
    """Return the version from the sole wheel in ``dist_dir`` when present."""
    wheels = sorted(dist_dir.glob("praval-*.whl"))
    if not wheels:
        return None
    if len(wheels) != 1:
        raise ValueError(f"expected one wheel, found {len(wheels)}")
    with zipfile.ZipFile(wheels[0]) as archive:
        names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(names) != 1:
            raise ValueError("wheel must contain exactly one METADATA file")
        metadata = email.message_from_bytes(archive.read(names[0]))
    return str(metadata["Version"])


def iter_text_files(root: Path, entries: Iterable[str]) -> Iterable[Path]:
    """Yield maintained text files from selected current surfaces."""
    suffixes = {".md", ".rst", ".py", ".sh", ".yml", ".yaml", ".toml"}
    for entry in entries:
        path = root / entry
        if path.is_file():
            yield path
        elif path.is_dir():
            for candidate in sorted(path.rglob("*")):
                if candidate.is_file() and candidate.suffix in suffixes:
                    yield candidate


def validate(
    root: Path,
    *,
    dist_dir: Optional[Path] = None,
    tag: Optional[str] = None,
) -> List[str]:
    """Return release metadata errors."""
    errors: List[str] = []
    expected = project_version(root)
    try:
        installed = importlib.metadata.version("praval")
    except importlib.metadata.PackageNotFoundError:
        installed = None
        if dist_dir is None:
            errors.append("the praval distribution is not installed")
    if installed is not None and installed != expected:
        errors.append(
            "installed praval version "
            f"{installed!r} does not match pyproject {expected!r}"
        )
    if dist_dir is not None:
        packaged = wheel_version(dist_dir)
        if packaged is None:
            errors.append(f"no Praval wheel found in {dist_dir}")
        elif packaged != expected:
            errors.append(
                f"wheel version {packaged!r} does not match pyproject {expected!r}"
            )
    if tag is not None and tag != f"v{expected}":
        errors.append(f"tag {tag!r} does not match v{expected}")

    init_source = (root / "src/praval/__init__.py").read_text(encoding="utf-8")
    if re.search(r"(?m)^__version__\s*=\s*['\"]\d", init_source):
        errors.append(
            "praval.__version__ must come from installed distribution metadata"
        )
    version_literal = re.compile(r"(?<![\w.])\d+\.\d+\.\d+(?![\w.])")
    for relative in (
        "src/praval/observability/__init__.py",
        "src/praval/observability/export/otlp_exporter.py",
        "docs/sphinx/conf.py",
    ):
        text = (root / relative).read_text(encoding="utf-8")
        if version_literal.search(text):
            errors.append(f"{relative} contains a hard-coded package version")

    release_notes = root / "docs/releases" / f"RELEASE_NOTES_{expected}.md"
    if not release_notes.is_file():
        errors.append(f"release notes are missing for {expected}")
    elif not release_notes.read_text(encoding="utf-8").startswith(
        f"# Praval {expected}\n"
    ):
        errors.append(f"release notes title does not match {expected}")

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{expected}]" not in changelog:
        errors.append(f"CHANGELOG.md has no section for {expected}")
    readme = (root / "README.md").read_text(encoding="utf-8")
    expected_notes_link = f"docs/releases/RELEASE_NOTES_{expected}.md"
    if expected_notes_link not in readme:
        errors.append(f"README.md does not link to release notes for {expected}")

    stale_pattern = re.compile(r"(?<![\w.])0\.7\.(?:11|16|18|20|22)(?![\w.])")
    stale: List[str] = []
    for path in iter_text_files(root, CURRENT_SURFACES):
        if path.name == "runtime-migration.md":
            continue
        if stale_pattern.search(path.read_text(encoding="utf-8", errors="replace")):
            stale.append(str(path.relative_to(root)))
    if stale:
        errors.append("stale release literals in current surfaces: " + ", ".join(stale))

    if (root / ".bumpversion.cfg").exists():
        errors.append("obsolete .bumpversion.cfg must be removed")
    if (root / ".github/workflows/auto-version-bump.yml.disabled").exists():
        errors.append("disabled automatic version workflow must be removed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--dist", type=Path)
    parser.add_argument("--tag")
    args = parser.parse_args()
    errors = validate(args.root.resolve(), dist_dir=args.dist, tag=args.tag)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Release metadata agrees on {project_version(args.root.resolve())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
