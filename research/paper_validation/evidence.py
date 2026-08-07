"""Aggregate canonical runs into claim and metric evidence ledgers."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Mapping, Sequence, Tuple

from .analysis import bootstrap_mean_ci, describe_samples
from .manifest import Registry
from .provenance import stable_json


def _load_run(path: Path) -> Dict[str, Any]:
    run_path = path.resolve() / "run.json"
    if not run_path.is_file():
        raise ValueError(f"run has no run.json: {path}")
    value = json.loads(run_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"run report is not an object: {run_path}")
    value["_source_dir"] = str(path.resolve())
    return value


def load_runs(paths: Sequence[Path]) -> List[Dict[str, Any]]:
    """Load runs while rejecting ambiguous duplicate experiment evidence."""
    if not paths:
        raise ValueError("at least one run directory is required")
    runs = [_load_run(path) for path in paths]
    owners: Dict[str, str] = {}
    for run in runs:
        for experiment in run.get("experiments", []):
            experiment_id = str(experiment.get("id", ""))
            if not experiment_id:
                continue
            previous = owners.get(experiment_id)
            if previous is not None:
                raise ValueError(
                    f"experiment {experiment_id} appears in both "
                    f"{previous} and {run.get('run_id')}"
                )
            owners[experiment_id] = str(run.get("run_id"))
    return runs


def _experiment_results(
    runs: Sequence[Mapping[str, Any]],
) -> Dict[str, Tuple[Mapping[str, Any], Mapping[str, Any]]]:
    values = {}
    for run in runs:
        for experiment in run.get("experiments", []):
            experiment_id = experiment.get("id")
            if experiment_id:
                values[str(experiment_id)] = (run, experiment)
    return values


def claim_evidence_report(
    runs: Sequence[Mapping[str, Any]], registry: Registry
) -> Dict[str, Any]:
    """Resolve declared claims against all supplied canonical evidence."""
    results = _experiment_results(runs)
    claims: List[Dict[str, Any]] = []
    for claim in registry.claims.values():
        related = {
            experiment_id: results.get(experiment_id)
            for experiment_id in claim.experiments
        }
        evaluated = {
            name: value for name, value in related.items() if value is not None
        }
        failures = [
            name
            for name, (_, result) in evaluated.items()
            if result.get("status") == "failed"
        ]
        required = [
            name
            for name in claim.experiments
            if registry.experiments[name].tier != "live"
        ]
        if not required:
            required = list(claim.experiments)
        required_passed = all(
            name in evaluated
            and evaluated[name][1].get("status") == "passed"
            and bool(evaluated[name][0].get("canonical"))
            for name in required
        )
        every_declared_passed = all(
            name in evaluated
            and evaluated[name][1].get("status") == "passed"
            and bool(evaluated[name][0].get("canonical"))
            for name in claim.experiments
        )
        any_smoke_passed = any(
            result.get("status") == "passed" and not run.get("canonical")
            for run, result in evaluated.values()
        )

        if not claim.experiments:
            observed = claim.status
        elif claim.status in {"unsupported", "contradicted", "future_work"}:
            observed = claim.status
        elif failures:
            observed = "unsupported"
        elif every_declared_passed:
            observed = "validated"
        elif required_passed:
            observed = "validated_with_scope"
        elif any_smoke_passed:
            observed = "provisional_smoke_result"
        else:
            observed = "not_evaluated"

        experiment_evidence: List[Dict[str, Any]] = []
        for name in claim.experiments:
            value = evaluated.get(name)
            if value is None:
                experiment_evidence.append({"id": name, "status": "not_evaluated"})
                continue
            run, result = value
            experiment_evidence.append(
                {
                    "id": name,
                    "status": result.get("status"),
                    "canonical": bool(run.get("canonical")),
                    "run_id": run.get("run_id"),
                    "run_dir": run.get("_source_dir"),
                    "artifacts": result.get("artifacts", {}),
                    "limitations": result.get("limitations", []),
                    "failure": result.get("failure"),
                }
            )
        claims.append(
            {
                "id": claim.id,
                "statement": claim.statement,
                "category": claim.category,
                "scope": claim.scope,
                "paper_sections": list(claim.paper_sections),
                "declared_status": claim.status,
                "observed_status": observed,
                "acceptance_rule": claim.acceptance_rule,
                "implementation_evidence": list(claim.implementation_evidence),
                "citations": list(claim.citations),
                "experiments": experiment_evidence,
                "permitted_wording": claim.permitted_wording,
                "limitations": list(claim.limitations),
            }
        )
    return {
        "schema_version": 1,
        "runs": [
            {
                "run_id": run.get("run_id"),
                "tier": run.get("tier"),
                "status": run.get("status"),
                "canonical": run.get("canonical"),
                "run_dir": run.get("_source_dir"),
            }
            for run in runs
        ],
        "claims": claims,
    }


def _sample_rows(
    runs: Sequence[Mapping[str, Any]],
) -> Iterable[Dict[str, Any]]:
    for run in runs:
        root = Path(str(run["_source_dir"]))
        for experiment in run.get("experiments", []):
            experiment_id = str(experiment.get("id", ""))
            for artifact in experiment.get("artifacts", {}).values():
                relative = artifact.get("path")
                if not isinstance(relative, str) or not relative.endswith(
                    ".samples.jsonl"
                ):
                    continue
                path = root / relative
                if not path.is_file():
                    raise ValueError(f"registered sample artifact is absent: {path}")
                for line_number, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), 1
                ):
                    if not line.strip():
                        continue
                    value = json.loads(line)
                    if (
                        not isinstance(value, dict)
                        or not isinstance(value.get("metric"), str)
                        or not isinstance(value.get("value"), (int, float))
                    ):
                        raise ValueError(f"invalid sample at {path}:{line_number}")
                    yield {
                        "run_id": run.get("run_id"),
                        "tier": run.get("tier"),
                        "canonical": bool(run.get("canonical")),
                        "experiment": experiment_id,
                        **value,
                    }


def metric_evidence_report(
    runs: Sequence[Mapping[str, Any]], *, seed: int = 20260726
) -> Dict[str, Any]:
    """Summarize samples without discarding their grouping dimensions."""
    groups: DefaultDict[Tuple[str, str, str], List[float]] = defaultdict(list)
    dimensions_by_group: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    raw_count = 0
    for row in _sample_rows(runs):
        raw_count += 1
        dimensions = {
            key: value
            for key, value in row.items()
            if key
            not in {
                "run_id",
                "tier",
                "canonical",
                "experiment",
                "metric",
                "value",
                "process_index",
                "repetition",
                "trial",
                "iteration",
                "sample_index",
                "question_id",
                "framework_order",
            }
        }
        serialized = json.dumps(dimensions, sort_keys=True, separators=(",", ":"))
        key = (str(row["experiment"]), str(row["metric"]), serialized)
        groups[key].append(float(row["value"]))
        dimensions_by_group[key] = dimensions
    summaries = []
    for index, key in enumerate(sorted(groups), 1):
        experiment, metric, _ = key
        statistics: Dict[str, Any] = dict(describe_samples(groups[key]))
        if len(groups[key]) > 1:
            statistics["mean_bootstrap_95_ci"] = list(
                bootstrap_mean_ci(groups[key], seed=seed + index)
            )
        summaries.append(
            {
                "experiment": experiment,
                "metric": metric,
                "dimensions": dimensions_by_group[key],
                "statistics": statistics,
            }
        )
    return {
        "schema_version": 1,
        "raw_sample_count": raw_count,
        "groups": summaries,
    }


def _claim_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Claim-to-evidence ledger",
        "",
        "| Claim | Declared | Observed | Permitted wording |",
        "| --- | --- | --- | --- |",
    ]
    for claim in report["claims"]:
        wording = str(claim["permitted_wording"]).replace("|", r"\|")
        lines.append(
            f"| `{claim['id']}` | {claim['declared_status']} | "
            f"{claim['observed_status']} | {wording} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_evidence_bundle(
    runs: Sequence[Mapping[str, Any]],
    *,
    registry: Registry,
    output_dir: Path,
) -> Dict[str, Path]:
    """Write combined claim and metric evidence in reviewable formats."""
    destination = output_dir.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    claim_report = claim_evidence_report(runs, registry)
    metric_report = metric_evidence_report(runs)
    claims_json = destination / "claim-report.json"
    claims_md = destination / "claim-report.md"
    metrics_json = destination / "metric-summary.json"
    metrics_csv = destination / "metric-summary.csv"
    claims_json.write_text(stable_json(claim_report), encoding="utf-8")
    claims_md.write_text(_claim_markdown(claim_report), encoding="utf-8")
    metrics_json.write_text(stable_json(metric_report), encoding="utf-8")
    fields = [
        "experiment",
        "metric",
        "dimensions",
        "count",
        "mean",
        "median",
        "standard_deviation",
        "p50",
        "p95",
        "p99",
        "ci_low",
        "ci_high",
    ]
    with metrics_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for group in metric_report["groups"]:
            statistics = group["statistics"]
            interval = statistics.get("mean_bootstrap_95_ci", ["", ""])
            writer.writerow(
                {
                    "experiment": group["experiment"],
                    "metric": group["metric"],
                    "dimensions": json.dumps(
                        group["dimensions"],
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "count": statistics.get("count", ""),
                    "mean": statistics.get("mean", ""),
                    "median": statistics.get("median", ""),
                    "standard_deviation": statistics.get("standard_deviation", ""),
                    "p50": statistics.get("p50", ""),
                    "p95": statistics.get("p95", ""),
                    "p99": statistics.get("p99", ""),
                    "ci_low": interval[0] if interval else "",
                    "ci_high": interval[1] if interval else "",
                }
            )
    return {
        "claims_json": claims_json,
        "claims_markdown": claims_md,
        "metrics_json": metrics_json,
        "metrics_csv": metrics_csv,
    }
