"""Write machine-readable and paper-ready analysis artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping


def _latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(character, character) for character in value)


def _primary_metric(experiment: Mapping[str, Any]) -> str:
    metrics = experiment.get("metrics")
    if not isinstance(metrics, dict) or not metrics:
        return "n/a"
    first_name = sorted(metrics)[0]
    value = metrics[first_name]
    if isinstance(value, dict):
        for field in ("median", "mean", "value"):
            if field in value:
                return f"{first_name}: {value[field]}"
    return f"{first_name}: {value}"


def _markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Praval paper validation analysis",
        "",
        f"- Run: `{report.get('run_id', 'unknown')}`",
        f"- Tier: `{report.get('tier', 'unknown')}`",
        f"- Status: `{report.get('status', 'unknown')}`",
        "",
        "| Experiment | Status | Primary metric |",
        "| --- | --- | --- |",
    ]
    for experiment in report.get("experiments", []):
        lines.append(
            "| {id} | {status} | {metric} |".format(
                id=experiment.get("id", "unknown"),
                status=experiment.get("status", "unknown"),
                metric=_primary_metric(experiment),
            )
        )
    lines.append("")
    return "\n".join(lines)


def _latex_report(report: Mapping[str, Any]) -> str:
    lines = [
        r"\begin{tabular}{lll}",
        r"\hline",
        r"Experiment & Status & Primary metric \\",
        r"\hline",
    ]
    for experiment in report.get("experiments", []):
        lines.append(
            "{} & {} & {} \\\\".format(
                _latex_escape(str(experiment.get("id", "unknown"))),
                _latex_escape(str(experiment.get("status", "unknown"))),
                _latex_escape(_primary_metric(experiment)),
            )
        )
    lines.extend([r"\hline", r"\end{tabular}", ""])
    return "\n".join(lines)


def write_analysis_bundle(
    report: Mapping[str, Any], output_dir: Path
) -> Dict[str, Path]:
    """Write stable JSON, Markdown, and LaTeX forms of one analysis."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "analysis.json"
    markdown_path = output_dir / "analysis.md"
    latex_path = output_dir / "analysis.tex"
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(_markdown_report(report), encoding="utf-8")
    latex_path.write_text(_latex_report(report), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path, "latex": latex_path}
