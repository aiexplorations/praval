"""Curate sanitized canonical evidence for version control."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from .provenance import sha256_file, stable_json

ALLOWED_ARTIFACT_SUFFIXES = {
    ".csv",
    ".json",
    ".jsonl",
    ".md",
    ".png",
    ".svg",
    ".tex",
    ".txt",
}


def _load_canonical_run(run_dir: Path) -> Mapping[str, Any]:
    run_path = run_dir.resolve() / "run.json"
    if not run_path.is_file():
        raise ValueError(f"run has no run.json: {run_dir}")
    raw_run = json.loads(run_path.read_text(encoding="utf-8"))
    if not isinstance(raw_run, dict):
        raise ValueError(f"run report is not an object: {run_path}")
    run: Dict[str, Any] = raw_run
    if run.get("canonical") is not True:
        raise ValueError(f"quick run cannot be curated: {run_dir}")
    if run.get("status") not in {"passed", "failed", "not_run"}:
        raise ValueError(f"run is not terminal: {run_dir}")
    if run.get("tier") == "live" and run.get("status") != "not_run":
        raise ValueError("live evidence requires manual review before curation")
    return run


def curate_runs(run_dirs: Sequence[Path], *, output_dir: Path) -> Dict[str, Path]:
    """Copy only registered, hash-verified, sanitized canonical artifacts."""
    if not run_dirs:
        raise ValueError("at least one canonical run is required")
    destination = output_dir.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    outputs: Dict[str, Path] = {}
    manifest_runs = []
    for run_dir in run_dirs:
        root = run_dir.resolve()
        run = _load_canonical_run(root)
        run_id = str(run.get("run_id", ""))
        if not run_id or Path(run_id).name != run_id:
            raise ValueError(f"run has unsafe run_id: {run_id!r}")
        target = destination / run_id
        if target.exists():
            raise ValueError(f"curation target already exists: {target}")
        artifact_target = target / "artifacts"
        artifact_target.mkdir(parents=True)
        curated_artifacts = []
        for experiment in run.get("experiments", []):
            for name, artifact in experiment.get("artifacts", {}).items():
                relative = artifact.get("path")
                expected_hash = artifact.get("sha256")
                if not isinstance(relative, str) or not isinstance(expected_hash, str):
                    raise ValueError(
                        f"{run_id}: artifact metadata is incomplete: {name}"
                    )
                source = (root / relative).resolve()
                if (
                    root not in source.parents
                    or not source.is_file()
                    or source.suffix.lower() not in ALLOWED_ARTIFACT_SUFFIXES
                ):
                    raise ValueError(
                        f"{run_id}: artifact is absent, unsafe, or private: "
                        f"{relative}"
                    )
                observed_hash = sha256_file(source)
                if observed_hash != expected_hash:
                    raise ValueError(f"{run_id}: artifact hash changed: {relative}")
                output = artifact_target / source.name
                if output.exists():
                    raise ValueError(
                        f"{run_id}: duplicate curated artifact: {source.name}"
                    )
                shutil.copy2(source, output)
                curated_artifacts.append(
                    {
                        "experiment": experiment.get("id"),
                        "path": str(output.relative_to(destination)),
                        "sha256": observed_hash,
                        "size": output.stat().st_size,
                    }
                )
        run_target = target / "run.json"
        shutil.copy2(root / "run.json", run_target)
        curation_target = target / "curation.json"
        curation_target.write_text(
            stable_json(
                {
                    "schema_version": 1,
                    "run_id": run_id,
                    "source_run_sha256": sha256_file(root / "run.json"),
                    "artifact_count": len(curated_artifacts),
                    "artifacts": sorted(
                        curated_artifacts,
                        key=lambda value: str(value["path"]),
                    ),
                    "excluded": [
                        "install and worker logs",
                        "service databases and container volumes",
                        "unregistered files",
                        "private or large media",
                    ],
                }
            ),
            encoding="utf-8",
        )
        outputs[run_id] = target
        manifest_runs.append(
            {
                "run_id": run_id,
                "tier": run.get("tier"),
                "status": run.get("status"),
                "path": str(target.relative_to(destination)),
                "run_sha256": sha256_file(run_target),
                "curation_sha256": sha256_file(curation_target),
            }
        )
    manifest_path = destination / "canonical-runs.json"
    manifest_path.write_text(
        stable_json(
            {
                "schema_version": 1,
                "runs": sorted(manifest_runs, key=lambda value: str(value["run_id"])),
            }
        ),
        encoding="utf-8",
    )
    outputs["manifest"] = manifest_path
    return outputs
