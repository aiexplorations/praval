"""Command-line entry point for the Praval paper-validation harness."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from .audit import audit_paper, audit_summary
from .feature_audit import audit_feature_diff, write_feature_diff_bundle
from .manifest import load_feature_inventory, load_registry
from .provenance import stable_json
from .references import load_references, validate_claim_citations

VALIDATION_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = VALIDATION_ROOT.parents[1]
DEFAULT_PAPER_ROOT = REPOSITORY_ROOT.parent / "praval_paper"


def build_parser() -> argparse.ArgumentParser:
    """Build the documented internal command surface."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="audit paper and evidence metadata")
    audit.add_argument("--paper-root", type=Path, default=DEFAULT_PAPER_ROOT)
    audit.add_argument("--output-dir", type=Path)

    subparsers.add_parser("validate", help="validate manifests and links")

    run = subparsers.add_parser("run", help="run one registered evidence tier")
    run.add_argument(
        "--tier",
        choices=("offline", "services", "live", "comparative"),
        required=True,
    )
    run.add_argument(
        "--wheel",
        type=Path,
        default=REPOSITORY_ROOT / "dist" / "praval-0.8.1-py3-none-any.whl",
    )
    run.add_argument("--output-dir", type=Path)
    run.add_argument("--seed", type=int, default=20260726)
    run.add_argument(
        "--quick",
        action="store_true",
        help="use reduced repetitions for a non-canonical smoke run",
    )

    analyze = subparsers.add_parser("analyze", help="analyze one completed run")
    analyze.add_argument("--run-dir", type=Path, action="append", required=True)
    analyze.add_argument("--output-dir", type=Path)

    export = subparsers.add_parser(
        "export-paper", help="export generated paper tables and claim report"
    )
    export.add_argument("--run-dir", type=Path, action="append", required=True)
    export.add_argument("--output-dir", type=Path)

    paper_validate = subparsers.add_parser(
        "paper-validate",
        help="validate the revised paper, citations, and generated evidence",
    )
    paper_validate.add_argument("--paper-root", type=Path, default=DEFAULT_PAPER_ROOT)

    paper_build = subparsers.add_parser(
        "build-paper",
        help="generate synchronized LaTeX and PDF from Markdown",
    )
    paper_build.add_argument("--paper-root", type=Path, default=DEFAULT_PAPER_ROOT)
    paper_build.add_argument("--output-dir", type=Path, required=True)

    curate = subparsers.add_parser(
        "curate", help="copy sanitized canonical evidence for version control"
    )
    curate.add_argument("--run-dir", type=Path, action="append", required=True)
    curate.add_argument(
        "--output-dir",
        type=Path,
        default=VALIDATION_ROOT / "results" / "canonical",
    )
    return parser


def _validate() -> dict:
    features = load_feature_inventory(
        VALIDATION_ROOT / "features.toml", repository_root=REPOSITORY_ROOT
    )
    registry = load_registry(
        VALIDATION_ROOT / "claims.toml",
        VALIDATION_ROOT / "experiments.toml",
        repository_root=REPOSITORY_ROOT,
    )
    references = load_references(VALIDATION_ROOT / "references.toml")
    validate_claim_citations(registry.claims, references)
    return {
        "schema_version": 1,
        "status": "passed",
        "features": len(features),
        "claims": len(registry.claims),
        "experiments": len(registry.experiments),
        "references": len(references),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Execute the requested validation command."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            print(stable_json(_validate()), end="")
            return 0
        if args.command == "audit":
            result = audit_paper(args.paper_root)
            features = load_feature_inventory(
                VALIDATION_ROOT / "features.toml",
                repository_root=REPOSITORY_ROOT,
            )
            feature_diff = audit_feature_diff(REPOSITORY_ROOT, features)
            result["feature_diff"] = feature_diff
            if args.output_dir is not None:
                args.output_dir.mkdir(parents=True, exist_ok=True)
                (args.output_dir / "paper-audit.json").write_text(
                    stable_json(result), encoding="utf-8"
                )
                (args.output_dir / "paper-audit.md").write_text(
                    audit_summary(result), encoding="utf-8"
                )
                write_feature_diff_bundle(feature_diff, args.output_dir)
            print(stable_json(result), end="")
            return 0
        if args.command == "run":
            from .runner import run_tier

            result = run_tier(
                tier=args.tier,
                wheel=args.wheel,
                output_dir=args.output_dir,
                seed=args.seed,
                quick=args.quick,
            )
            print(stable_json(result), end="")
            return 0 if result["status"] == "passed" else 1
        if args.command == "analyze":
            from .evidence import load_runs
            from .paper_artifacts import write_paper_artifact_bundle
            from .runner import analyze_run

            if len(args.run_dir) == 1 and args.output_dir is None:
                paths = analyze_run(args.run_dir[0])
            else:
                registry = load_registry(
                    VALIDATION_ROOT / "claims.toml",
                    VALIDATION_ROOT / "experiments.toml",
                    repository_root=REPOSITORY_ROOT,
                )
                output_dir = args.output_dir or (
                    VALIDATION_ROOT / "results" / "evidence"
                )
                paths = write_paper_artifact_bundle(
                    load_runs(args.run_dir),
                    registry=registry,
                    output_dir=output_dir,
                )
            print(
                stable_json({name: str(path) for name, path in paths.items()}),
                end="",
            )
            return 0
        if args.command == "export-paper":
            if len(args.run_dir) != 1:
                raise ValueError(
                    "export-paper accepts one run; use analyze to combine runs"
                )
            from .runner import export_paper

            paths = export_paper(args.run_dir[0], output_dir=args.output_dir)
            print(
                stable_json({name: str(path) for name, path in paths.items()}),
                end="",
            )
            return 0
        if args.command in {"paper-validate", "build-paper"}:
            from .paper import (
                build_paper,
                validate_paper,
                validation_to_dict,
            )
            from .references import load_references

            registry = load_registry(
                VALIDATION_ROOT / "claims.toml",
                VALIDATION_ROOT / "experiments.toml",
                repository_root=REPOSITORY_ROOT,
            )
            references = load_references(VALIDATION_ROOT / "references.toml")
            if args.command == "paper-validate":
                validation = validate_paper(
                    args.paper_root,
                    registry=registry,
                    references=references,
                )
                print(stable_json(validation_to_dict(validation)), end="")
                return 0 if validation.status == "passed" else 1
            paths = build_paper(
                args.paper_root,
                output_dir=args.output_dir,
                registry=registry,
                references=references,
            )
            print(
                stable_json({name: str(path) for name, path in paths.items()}),
                end="",
            )
            return 0
        if args.command == "curate":
            from .curation import curate_runs

            paths = curate_runs(args.run_dir, output_dir=args.output_dir)
            print(
                stable_json({name: str(path) for name, path in paths.items()}),
                end="",
            )
            return 0
        raise AssertionError(f"unhandled command: {args.command}")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"paper validation failed: {exc}", file=sys.stderr)
        return 1
