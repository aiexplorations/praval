"""Validate and build the evidence-backed Markdown paper."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .audit import LEGACY_TOKENS, audit_paper
from .manifest import Registry
from .provenance import sha256_file, stable_json
from .references import Reference, write_bibtex

INCLUDE_RE = re.compile(
    r"\{\{PRAVAL_INCLUDE:"
    r"(?P<experiment>[a-z0-9][a-z0-9-]*):"
    r"(?P<filename>[A-Za-z0-9][A-Za-z0-9_.-]*):"
    r"(?P<sha256>[0-9a-f]{64})\}\}"
)
RESULT_MARKER_RE = re.compile(
    r"<!--\s*PRAVAL_RESULT:(?P<experiment>[a-z0-9][a-z0-9-]*)\s*-->"
)
VALUE_RE = re.compile(
    r"\{\{PRAVAL_VALUE:" r"(?P<key>[a-z0-9][a-z0-9_]*):" r"(?P<sha256>[0-9a-f]{64})\}\}"
)
IMAGE_RE = re.compile(r"!\[[^\]]*\]\((?P<target>[^)\s]+)(?:\s+[^)]*)?\)")
UNRESOLVED_RE = re.compile(r"\{\{PRAVAL_(?:INCLUDE|VALUE):")
WARNING_RE = re.compile(r"\bwarning\b", re.IGNORECASE)


@dataclass(frozen=True)
class PaperValidation:
    """Structured paper-validation outcome."""

    status: str
    errors: Tuple[str, ...]
    warnings: Tuple[str, ...]
    evidence_experiments: Tuple[str, ...]
    audit: Mapping[str, Any]


def _inside(root: Path, value: Path) -> bool:
    resolved_root = root.resolve()
    resolved = value.resolve()
    return resolved == resolved_root or resolved_root in resolved.parents


def expand_evidence_includes(
    source: str,
    *,
    paper_root: Path,
    registry: Registry,
) -> Tuple[str, Tuple[str, ...]]:
    """Expand only hash-pinned generated Markdown fragments."""
    used: List[str] = []

    def replace(match: re.Match[str]) -> str:
        experiment_id = match.group("experiment")
        if experiment_id not in registry.experiments:
            raise ValueError(f"paper include names unknown experiment: {experiment_id}")
        generated_root = paper_root.resolve() / "generated"
        fragment = generated_root / match.group("filename")
        if not _inside(generated_root, fragment) or not fragment.is_file():
            raise ValueError(f"paper include is absent or unsafe: {fragment}")
        observed = sha256_file(fragment)
        if observed != match.group("sha256"):
            raise ValueError(
                f"paper include hash differs for {fragment.name}: {observed}"
            )
        used.append(experiment_id)
        return fragment.read_text(encoding="utf-8").rstrip()

    expanded = INCLUDE_RE.sub(replace, source)
    values_cache: Dict[str, Any] = {}

    def replace_value(match: re.Match[str]) -> str:
        values_path = paper_root.resolve() / "generated" / "paper-values.json"
        if not values_path.is_file():
            raise ValueError("paper value index is absent")
        observed = sha256_file(values_path)
        if observed != match.group("sha256"):
            raise ValueError(f"paper value index hash differs: {observed}")
        if not values_cache:
            value = json.loads(values_path.read_text(encoding="utf-8"))
            if value.get("schema_version") != 1 or not isinstance(
                value.get("values"), dict
            ):
                raise ValueError("paper value index has an invalid schema")
            values_cache.update(value["values"])
        item = values_cache.get(match.group("key"))
        if not isinstance(item, dict):
            raise ValueError(f"paper value key is absent: {match.group('key')}")
        experiment_id = item.get("experiment")
        rendered = item.get("rendered")
        if experiment_id not in registry.experiments:
            raise ValueError(f"paper value names unknown experiment: {experiment_id}")
        if not isinstance(rendered, str) or not rendered.strip():
            raise ValueError(f"paper value has no rendered text: {match.group('key')}")
        used.append(str(experiment_id))
        return rendered

    expanded = VALUE_RE.sub(replace_value, expanded)
    return expanded, tuple(sorted(set(used)))


def validate_paper(
    paper_root: Path,
    *,
    registry: Registry,
    references: Mapping[str, Reference],
) -> PaperValidation:
    """Reject stale evidence, bibliography, figures, and legacy results."""
    root = paper_root.resolve()
    source_path = root / "report" / "praval_technical_report.md"
    source = source_path.read_text(encoding="utf-8")
    errors: List[str] = []
    warnings: List[str] = []
    used_experiments: List[str] = []
    audit = audit_paper(root)

    citations = audit["citations"]
    if citations["missing"]:
        errors.append(
            "unresolved bibliography keys: " + ", ".join(citations["missing"])
        )
    if citations["duplicate_bibliography_keys"]:
        errors.append(
            "duplicate bibliography keys: "
            + ", ".join(citations["duplicate_bibliography_keys"])
        )
    errors.extend(citations["malformed"])
    registry_keys = set(references)
    paper_keys = set(citations["keys"])
    unresolved_registry = sorted(paper_keys - registry_keys)
    if unresolved_registry:
        errors.append(
            "citations absent from references.toml: " + ", ".join(unresolved_registry)
        )

    for token in LEGACY_TOKENS:
        if token.casefold() in source.casefold():
            errors.append(f"legacy result remains in Markdown: {token}")

    try:
        expanded, included = expand_evidence_includes(
            source, paper_root=root, registry=registry
        )
        used_experiments.extend(included)
    except ValueError as exc:
        errors.append(str(exc))
        expanded = source
    if UNRESOLVED_RE.search(expanded):
        errors.append("paper contains an unresolved evidence directive")

    for marker in RESULT_MARKER_RE.finditer(source):
        experiment_id = marker.group("experiment")
        if experiment_id not in registry.experiments:
            errors.append(
                f"paper result marker names unknown experiment: {experiment_id}"
            )
        else:
            used_experiments.append(experiment_id)

    for match in IMAGE_RE.finditer(expanded):
        target = match.group("target")
        if "://" in target or target.startswith("data:"):
            continue
        candidates = [
            (source_path.parent / target).resolve(),
            (root / target).resolve(),
        ]
        if not any(_inside(root, path) and path.is_file() for path in candidates):
            errors.append(f"paper image is absent or unsafe: {target}")

    if citations["uncited"]:
        warnings.append(f"{len(citations['uncited'])} bibliography records are uncited")
    if not used_experiments:
        warnings.append("paper has no registered experiment evidence markers")
    unsupported_claims = audit["claim_inventory_summary"]["support_missing"]
    if unsupported_claims:
        errors.append(
            f"{unsupported_claims} substantive paper claims lack required support"
        )
    return PaperValidation(
        status="passed" if not errors else "failed",
        errors=tuple(sorted(set(errors))),
        warnings=tuple(sorted(set(warnings))),
        evidence_experiments=tuple(sorted(set(used_experiments))),
        audit=audit,
    )


def validation_to_dict(validation: PaperValidation) -> Dict[str, Any]:
    """Return a stable JSON-compatible paper validation report."""
    audit = validation.audit
    return {
        "schema_version": 1,
        "status": validation.status,
        "errors": list(validation.errors),
        "warnings": list(validation.warnings),
        "evidence_experiments": list(validation.evidence_experiments),
        "audit": {
            "paper_root": audit["paper_root"],
            "hashes": audit["hashes"],
            "citations": audit["citations"],
            "legacy_claim_count": len(audit["legacy_claims"]),
            "strong_claim_count": len(audit["strong_claims"]),
            "claim_inventory_summary": audit["claim_inventory_summary"],
        },
    }


def build_paper(
    paper_root: Path,
    *,
    output_dir: Path,
    registry: Registry,
    references: Mapping[str, Reference],
    pandoc: Optional[str] = None,
) -> Dict[str, Path]:
    """Generate synchronized LaTeX and PDF from the canonical Markdown."""
    root = paper_root.resolve()
    destination = output_dir.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    validation = validate_paper(root, registry=registry, references=references)
    validation_path = destination / "paper-validation.json"
    validation_path.write_text(
        stable_json(validation_to_dict(validation)), encoding="utf-8"
    )
    if validation.status != "passed":
        raise ValueError("paper validation failed: " + "; ".join(validation.errors))

    source = (root / "report" / "praval_technical_report.md").read_text(
        encoding="utf-8"
    )
    expanded, _ = expand_evidence_includes(source, paper_root=root, registry=registry)
    expanded_path = destination / "praval_expanded.md"
    expanded_path.write_text(expanded, encoding="utf-8")
    bibliography_path = write_bibtex(references, destination / "references.bib")
    pandoc_binary = pandoc or shutil.which("pandoc")
    if not pandoc_binary:
        raise RuntimeError("pandoc is required to build the paper")

    latex_path = destination / "praval.tex"
    pdf_path = destination / "praval_technical_report.pdf"
    common = [
        pandoc_binary,
        str(expanded_path),
        "--from",
        "markdown+citations",
        "--standalone",
        "--citeproc",
        "--bibliography",
        str(bibliography_path),
        "--resource-path",
        str(root),
        "--metadata",
        "link-citations=true",
    ]
    logs: List[str] = []
    for command in (
        [*common, "--output", str(latex_path)],
        [
            *common,
            "--pdf-engine=xelatex",
            "-V",
            "geometry:margin=1in",
            "--output",
            str(pdf_path),
        ],
    ):
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        logs.append(completed.stdout + completed.stderr)
        if completed.returncode != 0:
            (destination / "paper-build.log").write_text(
                "\n".join(logs), encoding="utf-8"
            )
            raise RuntimeError(f"paper build failed while producing {command[-1]}")
    build_log = destination / "paper-build.log"
    build_log.write_text("\n".join(logs), encoding="utf-8")
    warning_lines = [
        line for line in "\n".join(logs).splitlines() if WARNING_RE.search(line)
    ]
    if warning_lines:
        raise RuntimeError("paper build emitted warnings; see paper-build.log")
    canonical_bibliography = root / "arxiv" / "references.bib"
    canonical_latex = root / "arxiv" / "praval.tex"
    canonical_pdf = root / "report" / "praval_technical_report_300dpi.pdf"
    canonical_bibliography.parent.mkdir(parents=True, exist_ok=True)
    canonical_pdf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bibliography_path, canonical_bibliography)
    shutil.copy2(latex_path, canonical_latex)
    shutil.copy2(pdf_path, canonical_pdf)
    return {
        "validation": validation_path,
        "markdown": expanded_path,
        "bibliography": bibliography_path,
        "latex": latex_path,
        "pdf": pdf_path,
        "log": build_log,
        "canonical_bibliography": canonical_bibliography,
        "canonical_latex": canonical_latex,
        "canonical_pdf": canonical_pdf,
    }
