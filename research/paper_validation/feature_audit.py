"""Version-diff audit for the Praval 0.8.1 capability inventory."""

from __future__ import annotations

import hashlib
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from .manifest import Feature
from .provenance import stable_json

BASE_TAG = "v0.7.22"
RELEASE_TAG = "v0.8.1"
EXPECTED_RELEASE_COMMIT = "fa20513e7cc982fd8d94b81c19e55a9427a6f48c"


def _git(repository_root: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_name_status(text: str) -> list[Dict[str, str]]:
    changes: list[Dict[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        status = fields[0]
        if status.startswith(("R", "C")) and len(fields) == 3:
            changes.append(
                {
                    "status": status,
                    "old_path": fields[1],
                    "path": fields[2],
                }
            )
        elif len(fields) == 2:
            changes.append({"status": status, "path": fields[1]})
        else:
            raise RuntimeError(f"unexpected git name-status line: {line}")
    return changes


def audit_feature_diff(
    repository_root: Path,
    features: Mapping[str, Feature],
    *,
    base_tag: str = BASE_TAG,
    release_tag: str = RELEASE_TAG,
) -> Dict[str, Any]:
    """Map the release diff to the versioned capability inventory."""
    release_commit = _git(
        repository_root, "rev-parse", f"{release_tag}^{{commit}}"
    ).strip()
    base_commit = _git(repository_root, "rev-parse", f"{base_tag}^{{commit}}").strip()
    name_status = _git(
        repository_root,
        "diff",
        "--name-status",
        f"{base_tag}..{release_tag}",
    )
    numstat = _git(
        repository_root,
        "diff",
        "--numstat",
        f"{base_tag}..{release_tag}",
    )
    commit_lines = [
        line
        for line in _git(
            repository_root,
            "log",
            "--format=%H%x09%s",
            f"{base_tag}..{release_tag}",
        ).splitlines()
        if line
    ]
    changes = _parse_name_status(name_status)
    source_to_features: Dict[str, list[str]] = {}
    for feature in features.values():
        for source in feature.source:
            source_to_features.setdefault(source, []).append(feature.id)

    changed_paths = {change["path"] for change in changes}
    changed_source_paths = sorted(
        change["path"] for change in changes if change["path"].startswith("src/praval/")
    )
    mapped_sources = {
        path: sorted(source_to_features[path])
        for path in changed_source_paths
        if path in source_to_features
    }
    unmatched_sources = [
        path for path in changed_source_paths if path not in source_to_features
    ]
    feature_rows = []
    for feature in sorted(features.values(), key=lambda item: item.id):
        changed = sorted(path for path in feature.source if path in changed_paths)
        feature_rows.append(
            {
                "id": feature.id,
                "classification": feature.classification,
                "changed_sources": changed,
                "source": list(feature.source),
                "evidence": list(feature.evidence),
                "documentation": list(feature.documentation),
            }
        )

    status_counts = Counter(change["status"][0] for change in changes)
    classification_counts = Counter(
        feature.classification for feature in features.values()
    )
    result: Dict[str, Any] = {
        "schema_version": 1,
        "comparison": f"{base_tag}..{release_tag}",
        "base_tag": base_tag,
        "base_commit": base_commit,
        "release_tag": release_tag,
        "release_commit": release_commit,
        "expected_release_commit": EXPECTED_RELEASE_COMMIT,
        "release_commit_matches_expected": release_commit == EXPECTED_RELEASE_COMMIT,
        "commit_count": len(commit_lines),
        "commits": [
            {
                "commit": line.split("\t", 1)[0],
                "subject": line.split("\t", 1)[1],
            }
            for line in commit_lines
        ],
        "changed_file_count": len(changes),
        "change_status_counts": dict(sorted(status_counts.items())),
        "changed_files": changes,
        "diff_numstat_sha256": _sha256_text(numstat),
        "feature_count": len(features),
        "classification_counts": dict(sorted(classification_counts.items())),
        "features": feature_rows,
        "changed_public_source_count": len(changed_source_paths),
        "mapped_public_source_count": len(mapped_sources),
        "mapped_public_sources": mapped_sources,
        "unmatched_public_sources": unmatched_sources,
        "interpretation": (
            "Unmatched source files are implementation support surfaces, not "
            "automatically missing user-facing capabilities. Every inventory "
            "entry independently records source, executable evidence, and "
            "documentation."
        ),
    }
    result["status"] = (
        "passed" if result["release_commit_matches_expected"] else "failed"
    )
    return result


def feature_diff_summary(result: Mapping[str, Any]) -> str:
    """Render a concise reviewable feature-diff summary."""
    lines = [
        "# Praval 0.8.1 feature-diff audit",
        "",
        f"- Comparison: `{result['comparison']}`",
        f"- Base commit: `{result['base_commit']}`",
        f"- Release commit: `{result['release_commit']}`",
        f"- Release commits: {result['commit_count']}",
        f"- Changed files: {result['changed_file_count']}",
        f"- Changed public source files: {result['changed_public_source_count']}",
        f"- Inventory entries: {result['feature_count']}",
        f"- Status: **{result['status']}**",
        "",
        "## Capability inventory",
        "",
        "| Capability | Classification | Changed source files | Evidence files |",
        "|---|---|---:|---:|",
    ]
    for feature in result["features"]:
        lines.append(
            "| `{id}` | {classification} | {changed} | {evidence} |".format(
                id=feature["id"],
                classification=feature["classification"],
                changed=len(feature["changed_sources"]),
                evidence=len(feature["evidence"]),
            )
        )
    lines.extend(
        [
            "",
            "## Unmatched changed implementation files",
            "",
            (
                "These files are retained for review because changed implementation "
                "support surfaces do not necessarily define distinct paper "
                "capabilities."
            ),
            "",
        ]
    )
    lines.extend(f"- `{path}`" for path in result["unmatched_public_sources"])
    lines.extend(
        [
            "",
            "The JSON companion preserves the complete file and commit inventory.",
            "",
        ]
    )
    return "\n".join(lines)


def write_feature_diff_bundle(
    result: Mapping[str, Any], output_dir: Path
) -> Sequence[Path]:
    """Write the machine-readable and reviewable diff audit."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "feature-diff-audit.json"
    markdown_path = output_dir / "feature-diff-audit.md"
    json_path.write_text(stable_json(result), encoding="utf-8")
    markdown_path.write_text(feature_diff_summary(result), encoding="utf-8")
    return (json_path, markdown_path)
