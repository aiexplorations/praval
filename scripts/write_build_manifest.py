#!/usr/bin/env python3
"""Write checksums and provenance for already-built release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_value(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL
    ).strip()


def write_manifest(dist_dir: Path, evidence_dir: Path) -> Dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    artifacts = sorted(path for path in dist_dir.iterdir() if path.is_file())
    wheels = [path for path in artifacts if path.name.endswith(".whl")]
    if len(artifacts) != 1 or len(wheels) != 1:
        raise ValueError(
            "dist must contain exactly one wheel and no other files before "
            "writing release evidence"
        )
    artifact_data: List[Dict[str, object]] = [
        {"filename": path.name, "sha256": _sha256(path), "size": path.stat().st_size}
        for path in artifacts
    ]
    manifest: Dict[str, object] = {
        "commit": os.environ.get("GITHUB_SHA") or _git_value(root, "rev-parse", "HEAD"),
        "source_date_epoch": os.environ.get("SOURCE_DATE_EPOCH")
        or _git_value(root, "show", "-s", "--format=%ct", "HEAD"),
        "artifacts": artifact_data,
    }
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "build-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    checksum_lines = [
        f"{artifact['sha256']}  {artifact['filename']}" for artifact in artifact_data
    ]
    (evidence_dir / "SHA256SUMS").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist_dir", type=Path)
    parser.add_argument("--evidence-dir", type=Path, default=Path("evidence"))
    args = parser.parse_args()
    write_manifest(args.dist_dir, args.evidence_dir)
    print(f"Wrote checksums and build manifest to {args.evidence_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
