#!/usr/bin/env python3
"""Verify that PyPI serves the exact wheel produced by Praval CI."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List


def validate_pypi_payload(
    build_manifest: Dict[str, Any], payload: Dict[str, Any], version: str
) -> List[str]:
    """Compare a PyPI release response with the exact CI build manifest."""
    errors: List[str] = []
    artifacts = build_manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 1:
        return ["build manifest must describe exactly one release artifact"]

    expected = artifacts[0]
    filename = expected.get("filename")
    if not isinstance(filename, str) or not filename.endswith(".whl"):
        return ["build manifest release artifact must be a wheel"]

    info = payload.get("info")
    actual_version = info.get("version") if isinstance(info, dict) else None
    if actual_version != version:
        errors.append(
            f"PyPI version mismatch: expected {version!r}, got {actual_version!r}"
        )

    files = payload.get("urls")
    if not isinstance(files, list):
        return errors + ["PyPI response has no release file list"]
    if len(files) != 1:
        errors.append(f"PyPI release must contain exactly one file, found {len(files)}")

    matches = [item for item in files if item.get("filename") == filename]
    if len(matches) != 1:
        return errors + [f"PyPI does not contain the expected wheel {filename!r}"]

    uploaded = matches[0]
    if uploaded.get("packagetype") != "bdist_wheel":
        errors.append("PyPI release file is not classified as a wheel")
    digests = uploaded.get("digests")
    actual_sha = digests.get("sha256") if isinstance(digests, dict) else None
    if actual_sha != expected.get("sha256"):
        errors.append("PyPI wheel SHA-256 does not match the exact CI build manifest")
    if uploaded.get("size") != expected.get("size"):
        errors.append("PyPI wheel size does not match the exact CI build manifest")
    return errors


def verify_pypi_wheel(
    manifest_path: Path, version: str, project: str = "praval"
) -> List[str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    url = f"https://pypi.org/pypi/{project}/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:  # nosec B310
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return [f"could not read PyPI release metadata: {type(exc).__name__}"]
    return validate_pypi_payload(manifest, payload, version)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("build_manifest", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--project", default="praval")
    args = parser.parse_args()
    errors = verify_pypi_wheel(args.build_manifest, args.version, args.project)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"PyPI serves the exact praval {args.version} CI wheel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
