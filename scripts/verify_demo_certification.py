#!/usr/bin/env python3
"""Verify that live demo evidence certifies the exact release wheel and commit."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _load_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def verify(
    build_manifest_path: Path,
    certification_path: Path,
    expected_commit: str,
    expected_version: Optional[str] = None,
) -> List[str]:
    """Return all exact-artifact certification violations."""
    errors: List[str] = []
    try:
        build = _load_json(build_manifest_path)
    except (OSError, ValueError, TypeError) as exc:
        return [f"unable to load build manifest: {exc}"]
    try:
        certification = _load_json(certification_path)
    except (OSError, ValueError, TypeError) as exc:
        return [f"unable to load certification report: {exc}"]
    wheel = certification.get("wheel")
    summary = certification.get("summary")
    results = certification.get("results")
    if not isinstance(wheel, dict):
        errors.append("certification has no wheel object")
        wheel = {}
    if not isinstance(summary, dict):
        errors.append("certification has no summary object")
        summary = {}
    if not isinstance(results, list) or not results:
        errors.append("certification has no demo results")
        results = []

    if build.get("commit") != expected_commit:
        errors.append("build manifest commit does not match expected commit")
    if certification.get("commit") != expected_commit:
        errors.append("certification commit does not match expected commit")
    if certification.get("mode") != "live":
        errors.append("certification mode must be live")
    if certification.get("status") != "passed":
        errors.append("certification status must be passed")
    if summary.get("failed") != 0 or summary.get("skipped") != 0:
        errors.append("certification must contain zero failures and zero skips")
    if summary.get("passed") != summary.get("total"):
        errors.append("every selected live demo must pass")
    if isinstance(summary.get("total"), int) and summary.get("total") != len(results):
        errors.append("certification summary total does not match demo results")
    for key in ("total", "passed", "failed", "skipped"):
        value = summary.get(key)
        if not isinstance(value, int) or value < 0:
            errors.append(f"certification summary {key} must be a non-negative integer")
    result_ids = []
    for result in results:
        if isinstance(result, dict):
            result_id = result.get("id")
            if not isinstance(result_id, str) or not result_id:
                errors.append("certification demo results must have non-empty ids")
            else:
                result_ids.append(result_id)
    if len(result_ids) != len(set(result_ids)):
        errors.append("certification demo result ids must be unique")
    if any(
        not isinstance(result, dict) or result.get("status") != "passed"
        for result in results
    ):
        errors.append("certification contains a non-passing demo result")

    filename = wheel.get("filename")
    digest = wheel.get("sha256")
    installed_digest = wheel.get("installed_sha256")
    installed_version = wheel.get("installed_version")
    artifacts = build.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append("build manifest has no artifact list")
        artifacts = []
    matching = [
        artifact
        for artifact in artifacts
        if isinstance(artifact, dict) and artifact.get("filename") == filename
    ]
    if len(matching) != 1:
        errors.append("certified wheel is not uniquely present in build manifest")
    elif matching[0].get("sha256") != digest:
        errors.append("certified wheel SHA-256 does not match build manifest")
    if (
        not isinstance(filename, str)
        or not filename.startswith("praval-")
        or not filename.endswith(".whl")
    ):
        errors.append("certification wheel filename is invalid")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        errors.append("certification wheel SHA-256 is invalid")
    if not isinstance(installed_digest, str) or not SHA256_RE.fullmatch(
        installed_digest
    ):
        errors.append("certification installed wheel SHA-256 is invalid or missing")
    elif isinstance(digest, str) and installed_digest != digest:
        errors.append("installed wheel SHA-256 does not match certified wheel")
    if not isinstance(installed_version, str) or not installed_version:
        errors.append("certification installed version is missing")
    elif wheel.get("version") != installed_version:
        errors.append("installed wheel version does not match certified version")
    if wheel.get("source_isolated") is not True:
        errors.append("certification must prove source-tree import isolation")
    if expected_version is not None and wheel.get("version") != expected_version:
        errors.append("certified wheel version does not match expected version")
    return errors


def main() -> int:
    """Validate CLI arguments and print actionable errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_manifest", type=Path)
    parser.add_argument("certification", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--version")
    args = parser.parse_args()
    errors = verify(
        args.build_manifest,
        args.certification,
        args.commit,
        args.version,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Exact-wheel live demo certification verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
