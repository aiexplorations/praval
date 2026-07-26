"""Execute registered scenarios inside an exact-wheel environment."""

from __future__ import annotations

import argparse
import os
import traceback
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from .manifest import load_registry
from .provenance import (
    redact_data,
    redact_text,
    secret_values_from_environment,
    sha256_file,
    stable_json,
)
from .scenarios import run_scenario

VALIDATION_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = VALIDATION_ROOT.parents[1]


def _secret_values() -> Sequence[str]:
    return secret_values_from_environment(os.environ)


def _redact_text_artifacts(root: Path, secret_values: Sequence[str]) -> None:
    """Sanitize credential-like values in text artifacts before export."""
    text_suffixes = {
        ".csv",
        ".json",
        ".jsonl",
        ".log",
        ".md",
        ".tex",
        ".txt",
    }
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in text_suffixes:
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        redacted = redact_text(original, secret_values=secret_values)
        if redacted != original:
            path.write_text(redacted, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--experiment", action="append", default=[])
    parser.add_argument("--quick", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    registry = load_registry(
        VALIDATION_ROOT / "claims.toml",
        VALIDATION_ROOT / "experiments.toml",
        repository_root=REPOSITORY_ROOT,
    )
    selected = []
    for experiment_id in args.experiment:
        experiment = registry.experiments.get(experiment_id)
        if experiment is None:
            raise ValueError(f"unknown experiment: {experiment_id}")
        if experiment.tier != args.tier:
            raise ValueError(
                f"{experiment_id} belongs to {experiment.tier}, not {args.tier}"
            )
        selected.append(experiment)
    if not selected:
        raise ValueError("at least one --experiment is required")

    output_dir = args.output_dir.resolve()
    artifact_dir = output_dir / "artifacts"
    experiment_root = output_dir / "experiments"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    experiment_root.mkdir(parents=True, exist_ok=True)
    results = []
    secret_values = _secret_values()
    for experiment in selected:
        scenario_dir = experiment_root / experiment.id
        try:
            result = run_scenario(
                experiment.scenario,
                output_dir=scenario_dir,
                repetitions=experiment.repetitions,
                warmups=experiment.warmups,
                seed=args.seed,
                quick=args.quick,
            )
        except Exception as exc:  # Keep negative evidence in the run.
            result = {
                "status": "failed",
                "checks": {},
                "metrics": {},
                "sample_count": 0,
                "failure": redact_text(
                    f"{type(exc).__name__}: {exc}",
                    secret_values=secret_values,
                ),
                "traceback": redact_text(
                    traceback.format_exc(), secret_values=secret_values
                ),
            }
            scenario_dir.mkdir(parents=True, exist_ok=True)
            (scenario_dir / "result.json").write_text(
                stable_json(result), encoding="utf-8"
            )

        result = redact_data(result, secret_values=secret_values)
        _redact_text_artifacts(scenario_dir, secret_values)
        (scenario_dir / "result.json").write_text(stable_json(result), encoding="utf-8")
        samples_path = scenario_dir / "samples.jsonl"
        exported: Dict[str, Dict[str, Any]] = {}
        summary_target = artifact_dir / f"{experiment.id}.json"
        summary_target.write_text(stable_json(result), encoding="utf-8")
        exported[summary_target.name] = {
            "path": str(summary_target.relative_to(output_dir)),
            "sha256": sha256_file(summary_target),
            "size": summary_target.stat().st_size,
        }
        if samples_path.is_file():
            samples_target = artifact_dir / f"{experiment.id}.samples.jsonl"
            samples_target.write_bytes(samples_path.read_bytes())
            exported[samples_target.name] = {
                "path": str(samples_target.relative_to(output_dir)),
                "sha256": sha256_file(samples_target),
                "size": samples_target.stat().st_size,
            }
        for expected in experiment.expected_artifacts:
            expected_name = Path(expected).name
            if expected_name in exported:
                continue
            source = scenario_dir / expected_name
            if not source.is_file():
                continue
            target = artifact_dir / expected_name
            target.write_bytes(source.read_bytes())
            exported[target.name] = {
                "path": str(target.relative_to(output_dir)),
                "sha256": sha256_file(target),
                "size": target.stat().st_size,
            }
        expected_names = {Path(value).name for value in experiment.expected_artifacts}
        missing_artifacts = sorted(expected_names - set(exported))
        if missing_artifacts:
            result["status"] = "failed"
            result.setdefault("limitations", []).append(
                "Missing declared artifacts: " + ", ".join(missing_artifacts)
            )
            summary_target.write_text(stable_json(result), encoding="utf-8")
            exported[summary_target.name] = {
                "path": str(summary_target.relative_to(output_dir)),
                "sha256": sha256_file(summary_target),
                "size": summary_target.stat().st_size,
            }
        results.append(
            {
                "id": experiment.id,
                "scenario": experiment.scenario,
                "tier": experiment.tier,
                "status": result.get("status", "failed"),
                "checks": result.get("checks", {}),
                "metrics": result.get("metrics", {}),
                "sample_count": result.get("sample_count", 0),
                "details": result.get("details", {}),
                "limitations": result.get("limitations", []),
                "failure": result.get("failure"),
                "artifacts": exported,
            }
        )
    report = {
        "schema_version": 1,
        "tier": args.tier,
        "canonical": not args.quick,
        "seed": args.seed,
        "status": (
            "passed"
            if all(result["status"] == "passed" for result in results)
            else "failed"
        ),
        "experiments": results,
    }
    (output_dir / "worker-report.json").write_text(
        stable_json(report), encoding="utf-8"
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
