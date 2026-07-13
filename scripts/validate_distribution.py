#!/usr/bin/env python3
"""Validate Praval wheel and source-distribution release invariants."""

from __future__ import annotations

import argparse
import email
import re
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

MAX_SDIST_BYTES = 3 * 1024 * 1024
FORBIDDEN_PARTS = {
    "__pycache__",
    ".pytest_cache",
    "_build",
    "archive",
    "generated",
    "dist",
}
FORBIDDEN_EXACT_SUFFIXES = {
    "docs/logo.png",
    "docs/sphinx/_static/praval-logo.png",
}


def _project_version(pyproject: Path) -> str:
    contents = pyproject.read_text(encoding="utf-8")
    project_match = re.search(r"(?ms)^\[project\]\s+(.*?)(?=^\[|\Z)", contents)
    if project_match is None:
        raise ValueError("pyproject.toml has no [project] table")
    version_match = re.search(
        r'^version\s*=\s*["\']([^"\']+)["\']\s*$',
        project_match.group(1),
        re.MULTILINE,
    )
    if version_match is None:
        raise ValueError("pyproject.toml has no static project version")
    return version_match.group(1)


def _package_version(init_file: Path) -> str:
    contents = init_file.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', contents, re.MULTILINE)
    if match is None:
        raise ValueError("praval.__version__ is not defined")
    return match.group(1)


def _metadata_from_wheel(wheel: Path) -> Dict[str, Any]:
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        wheel_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/WHEEL")
        ]
        if len(metadata_names) != 1 or len(wheel_names) != 1:
            raise ValueError("wheel must contain exactly one METADATA and WHEEL file")
        metadata = email.message_from_bytes(archive.read(metadata_names[0]))
        wheel_metadata = email.message_from_bytes(archive.read(wheel_names[0]))
    return {
        "name": str(metadata["Name"]),
        "version": str(metadata["Version"]),
        "requires_python": str(metadata["Requires-Python"]),
        "root_is_purelib": str(wheel_metadata["Root-Is-Purelib"]),
        "tag": str(wheel_metadata["Tag"]),
        "requires_dist": [
            str(value) for value in metadata.get_all("Requires-Dist", [])
        ],
    }


def _sdist_names(sdist: Path) -> List[str]:
    with tarfile.open(sdist, "r:gz") as archive:
        return archive.getnames()


def _wheel_names(wheel: Path) -> List[str]:
    with zipfile.ZipFile(wheel) as archive:
        return archive.namelist()


def _forbidden_entries(names: Iterable[str]) -> List[str]:
    forbidden: List[str] = []
    for name in names:
        normalized = name.replace("\\", "/").strip("/")
        parts = normalized.split("/")
        without_root = "/".join(parts[1:]) if len(parts) > 1 else normalized
        if FORBIDDEN_PARTS.intersection(parts):
            forbidden.append(name)
        elif any(without_root.endswith(suffix) for suffix in FORBIDDEN_EXACT_SUFFIXES):
            forbidden.append(name)
        elif normalized.endswith((".pyc", ".pyo", ".DS_Store")):
            forbidden.append(name)
    return forbidden


def validate(dist_dir: Path, expected_tag: Optional[str] = None) -> List[str]:
    errors: List[str] = []
    wheels = sorted(dist_dir.glob("praval-*.whl"))
    sdists = sorted(dist_dir.glob("praval-*.tar.gz"))
    if len(wheels) != 1:
        errors.append(f"expected one wheel, found {len(wheels)}")
    if len(sdists) != 1:
        errors.append(f"expected one sdist, found {len(sdists)}")
    if errors:
        return errors

    wheel = wheels[0]
    sdist = sdists[0]
    root = Path(__file__).resolve().parents[1]
    project_version = _project_version(root / "pyproject.toml")
    package_version = _package_version(root / "src/praval/__init__.py")
    wheel_metadata = _metadata_from_wheel(wheel)

    versions = {
        "pyproject.toml": project_version,
        "praval.__version__": package_version,
        "wheel metadata": wheel_metadata["version"],
    }
    if len(set(versions.values())) != 1:
        errors.append(f"version mismatch: {versions}")
    if expected_tag is not None and expected_tag != f"v{project_version}":
        errors.append(
            f"tag {expected_tag!r} does not match package version v{project_version}"
        )
    if wheel_metadata["name"].lower() != "praval":
        errors.append(f"unexpected wheel project name: {wheel_metadata['name']!r}")
    if wheel_metadata["requires_python"] != ">=3.9":
        errors.append("wheel Requires-Python must retain core support for Python >=3.9")
    if wheel_metadata["root_is_purelib"].lower() != "true":
        errors.append("wheel must declare Root-Is-Purelib: true")
    if wheel_metadata["tag"] != "py3-none-any":
        errors.append(f"wheel must use py3-none-any, got {wheel_metadata['tag']!r}")
    if not wheel.name.endswith("-py3-none-any.whl"):
        errors.append(f"wheel filename is not universal pure Python: {wheel.name}")
    requirements = wheel_metadata["requires_dist"]
    mcp_requirements = [
        requirement
        for requirement in requirements
        if requirement.lower().startswith("mcp") and 'extra == "mcp"' in requirement
    ]
    if len(mcp_requirements) != 1:
        errors.append("wheel must declare exactly one mcp-extra SDK requirement")
    elif not all(
        fragment in mcp_requirements[0]
        for fragment in (">=1.27", "<2", 'python_version >= "3.10"')
    ):
        errors.append(f"invalid MCP SDK requirement: {mcp_requirements[0]!r}")
    if any(requirement.lower().startswith("pypdf2") for requirement in requirements):
        errors.append("wheel must not depend on deprecated PyPDF2")
    if not any(
        requirement.lower().startswith("pypdf") and 'extra == "pdf"' in requirement
        for requirement in requirements
    ):
        errors.append("wheel must declare the pypdf extra")
    if sdist.stat().st_size >= MAX_SDIST_BYTES:
        errors.append(
            f"sdist is {sdist.stat().st_size} bytes; limit is {MAX_SDIST_BYTES}"
        )

    sdist_names = _sdist_names(sdist)
    wheel_names = _wheel_names(wheel)
    forbidden = _forbidden_entries(sdist_names + wheel_names)
    if forbidden:
        errors.append("forbidden package entries: " + ", ".join(forbidden[:20]))
    if not any("/tests/" in name and name.endswith(".py") for name in sdist_names):
        errors.append("sdist must contain the test suite")
    if not any("/examples/" in name and name.endswith(".py") for name in sdist_names):
        errors.append("sdist must contain Python examples")
    if not any(name.endswith("/examples/manifest.toml") for name in sdist_names):
        errors.append("sdist must contain the demo certification manifest")
    required_fixture_suffixes = (
        "/examples/certification/assets/image_input.png.base64",
        "/examples/certification/assets/knowledge_input.pdf.base64",
        "/examples/certification/assets/voice_phrase.txt",
        "/examples/certification/assets/voice_input.wav.gz.base64",
        "/examples/certification/assets/video_input.mp4.base64",
        "/examples/certification/assets/PROVENANCE.md",
    )
    if not all(
        any(name.endswith(suffix) for name in sdist_names)
        for suffix in required_fixture_suffixes
    ):
        errors.append("sdist must contain certification fixture provenance")
    if not any("/docs/sphinx/" in name for name in sdist_names):
        errors.append("sdist must contain Sphinx documentation sources")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist_dir", type=Path)
    parser.add_argument("--tag", help="optional release tag, such as v0.8.0")
    args = parser.parse_args()
    errors = validate(args.dist_dir, args.tag)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Distribution validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
