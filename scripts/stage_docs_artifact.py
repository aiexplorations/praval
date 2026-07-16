#!/usr/bin/env python3
"""Stage a verified exact-wheel documentation artifact into praval-ai."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List

from build_exact_wheel_docs import tree_sha256

FULL_SHA256 = re.compile(r"^[0-9a-f]{64}$")
FULL_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
RELEASE_VERSION = re.compile(r"^\d+\.\d+\.\d+(?:[a-z]+\d+)?$")


def _validate_manifest(manifest: Dict[str, Any], site: Path) -> None:
    """Reject incomplete or non-release documentation provenance."""
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported documentation manifest schema")
    commit = str(manifest.get("commit", ""))
    version = str(manifest.get("version", ""))
    wheel = str(manifest.get("wheel", ""))
    wheel_hash = str(manifest.get("wheel_sha256", ""))
    tree_hash = str(manifest.get("documentation_tree_sha256", ""))
    if FULL_COMMIT_SHA.fullmatch(commit) is None:
        raise ValueError("documentation manifest commit must be a full Git SHA")
    if RELEASE_VERSION.fullmatch(version) is None:
        raise ValueError("documentation manifest has an invalid release version")
    if not wheel.startswith(f"praval-{version}-") or not wheel.endswith(".whl"):
        raise ValueError("documentation manifest wheel does not match its version")
    if FULL_SHA256.fullmatch(wheel_hash) is None:
        raise ValueError("documentation manifest has an invalid wheel SHA-256")
    if FULL_SHA256.fullmatch(tree_hash) is None:
        raise ValueError("documentation manifest has an invalid tree SHA-256")
    file_count = manifest.get("file_count")
    if not isinstance(file_count, int) or file_count <= 0:
        raise ValueError("documentation manifest has an invalid file count")
    actual_count = sum(1 for path in site.rglob("*") if path.is_file())
    if file_count != actual_count:
        raise ValueError("documentation file count does not match its manifest")


def stage_docs(artifact: Path, website: Path) -> Dict[str, Any]:
    """Verify and stage versioned/latest documentation in a website checkout."""
    manifest_path = artifact / "documentation-manifest.json"
    site = artifact / "site"
    if not manifest_path.is_file() or not site.is_dir():
        raise ValueError("documentation artifact must contain a manifest and site")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _validate_manifest(manifest, site)
    actual_hash = tree_sha256(site)
    if actual_hash != manifest.get("documentation_tree_sha256"):
        raise ValueError("documentation tree hash does not match its manifest")

    version = str(manifest["version"])
    docs_root = website / "docs"
    versioned = docs_root / f"v{version}"
    latest = docs_root / "latest"
    for destination in (versioned, latest):
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(site, destination)
        shutil.copy2(manifest_path, destination / "documentation-manifest.json")

    versions_path = docs_root / "versions.json"
    versions = json.loads(versions_path.read_text(encoding="utf-8"))
    retained: List[Dict[str, Any]] = [
        entry
        for entry in versions.get("versions", [])
        if entry.get("version") not in {version, "latest"}
    ]
    versions["current"] = version
    versions["latest"] = version
    versions["versions"] = [
        {
            "version": version,
            "url": f"/docs/v{version}/",
            "title": f"v{version} (latest)",
        },
        {
            "version": "latest",
            "url": "/docs/latest/",
            "title": f"Latest (v{version})",
        },
        *retained,
    ]
    versions_path.write_text(json.dumps(versions, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--website", required=True, type=Path)
    args = parser.parse_args()
    manifest = stage_docs(args.artifact.resolve(), args.website.resolve())
    print(
        f"Staged Praval {manifest['version']} documentation for "
        f"commit {manifest['commit']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
