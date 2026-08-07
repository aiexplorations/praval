"""Generate paper-ready tables and figures from aggregated raw samples."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from .evidence import (
    claim_evidence_report,
    metric_evidence_report,
    write_evidence_bundle,
)
from .manifest import HistoryEntry, Registry, load_history
from .provenance import sha256_file, stable_json

ERA_DESCRIPTIONS = {
    "Initial agent foundation": (
        "0.1.0",
        "Established the package, direct Agent abstraction, provider integrations, state, prompts, tools, memory interfaces, and the first multi-agent components.",
        "Create a Python package in which model-backed agents and their supporting facilities could be composed.",
    ),
    "Initial coordination model": (
        "0.2.0",
        "Introduced the decorator-based agent API and made Reef and Spore message exchange the main multi-agent coordination path.",
        "Reduce the application code needed to define specialist agents and connect their message handlers.",
    ),
    "Memory and application foundation": (
        "0.5.0 to 0.5.1",
        "Added layered memory, knowledge-base integration, a fuller application structure, and corrections to early multi-agent communication.",
        "Give coordinated agents maintained working, episodic, semantic, and long-term information paths.",
    ),
    "Data, transport, and security expansion": (
        "0.6.0 to 0.6.2",
        "Added Secure Spore behavior, external transports, async storage, DataReference, memory-to-storage integration, and service-backed examples.",
        "Separate large or durable data from messages and integrate configured storage, protection, and transport systems.",
    ),
    "Coordination and operations maturity": (
        "0.7.0 to 0.7.22",
        "Added document ingestion, registered tools, observability, RabbitMQ Reef delivery, completion tracking, lifecycle controls, and durable human intervention.",
        "Make the coordination model easier to operate, inspect, govern, and extend while preserving Agent, Reef, and Spore.",
    ),
    "Provider-neutral execution transition": (
        "0.8.1",
        "Added ModelRuntime, EmbeddingRuntime, provider profiles, normalized contracts, Spore V2, MCP tools, and PravalApp lifecycle ownership.",
        "Separate provider capability handling and model execution from inter-agent message coordination.",
    ),
}

COMPARISON_METRIC_RE = re.compile(
    r"^comparison_delayed_(?P<framework>praval|langgraph|crewai)_"
    r"measured_(?P<metric>.+)$"
)
COMPARISON_STARTUP_RE = re.compile(
    r"^comparison_delayed_(?P<framework>praval|langgraph|crewai)_"
    r"(?P<metric>setup_seconds|process_ready_seconds)$"
)


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


def _write_table(
    stem: str,
    *,
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    output_dir: Path,
) -> Dict[str, Path]:
    markdown = output_dir / f"{stem}.md"
    latex = output_dir / f"{stem}.tex"
    markdown_lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    markdown_lines.extend(
        "| " + " | ".join(value.replace("|", r"\|") for value in row) + " |"
        for row in rows
    )
    markdown.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")
    latex_lines = [
        r"\begin{tabular}{" + "l" * len(headers) + "}",
        r"\hline",
        " & ".join(_latex_escape(value) for value in headers) + r" \\",
        r"\hline",
    ]
    latex_lines.extend(
        " & ".join(_latex_escape(value) for value in row) + r" \\" for row in rows
    )
    latex_lines.extend([r"\hline", r"\end{tabular}", ""])
    latex.write_text("\n".join(latex_lines), encoding="utf-8")
    return {f"{stem}_markdown": markdown, f"{stem}_latex": latex}


def _seconds(value: float) -> str:
    if value < 0.001:
        return f"{value * 1_000_000:.2f} µs"
    if value < 1.0:
        return f"{value * 1_000:.2f} ms"
    return f"{value:.3f} s"


def _groups_for(
    report: Mapping[str, Any], experiment: str
) -> Iterable[Mapping[str, Any]]:
    return (group for group in report["groups"] if group["experiment"] == experiment)


def _claim_tables(report: Mapping[str, Any], output_dir: Path) -> Dict[str, Path]:
    paths: Dict[str, Path] = {}
    for rq in ("RQ1", "RQ2", "RQ3", "RQ4", "RQ5"):
        rows = []
        for claim in report["claims"]:
            if not any(rq in section for section in claim["paper_sections"]):
                continue
            experiments = ", ".join(
                f"{value['id']} ({value['status']})" for value in claim["experiments"]
            )
            rows.append(
                [
                    str(claim["id"]),
                    str(claim["observed_status"]),
                    experiments,
                    str(claim["permitted_wording"]),
                ]
            )
        if rows:
            paths.update(
                _write_table(
                    f"{rq.casefold()}-claim-evidence",
                    headers=(
                        "Claim",
                        "Status",
                        "Experiment evidence",
                        "Permitted wording",
                    ),
                    rows=rows,
                    output_dir=output_dir,
                )
            )
    return paths


def _history_tables(
    history: Mapping[str, HistoryEntry], output_dir: Path
) -> Dict[str, Path]:
    paths = _write_table(
        "praval-version-history",
        headers=("Version", "Status", "Date", "Main change"),
        rows=[
            (
                entry.version,
                entry.status.replace("_", " "),
                entry.date.isoformat(),
                entry.summary,
            )
            for entry in history.values()
        ],
        output_dir=output_dir,
    )
    grouped: Dict[str, List[HistoryEntry]] = {}
    for entry in history.values():
        if entry.status == "excluded_transient_state":
            continue
        grouped.setdefault(entry.era, []).append(entry)
    era_rows = []
    for era in grouped:
        if era not in ERA_DESCRIPTIONS:
            raise ValueError(f"history era has no paper description: {era}")
        period, capability, motivation = ERA_DESCRIPTIONS[era]
        era_rows.append(
            (
                era,
                period,
                capability,
                motivation,
            )
        )
    paths.update(
        _write_table(
            "praval-evolution-eras",
            headers=("Era", "Versions", "Resulting capability", "Reason for change"),
            rows=era_rows,
            output_dir=output_dir,
        )
    )
    return paths


def _choreography_table(
    report: Mapping[str, Any], output_dir: Path
) -> Tuple[Dict[str, Path], List[Dict[str, float]]]:
    cells: Dict[Tuple[int, float], Dict[str, float]] = {}
    for group in _groups_for(report, "choreography-critical-path"):
        metric = str(group["metric"])
        if metric not in {"sequential_seconds", "fanout_seconds"}:
            continue
        dimensions = group["dimensions"]
        key = (int(dimensions["branches"]), float(dimensions["work_seconds"]))
        cells.setdefault(key, {})[metric] = float(group["statistics"]["median"])
    values = []
    rows = []
    for (branches, work_seconds), metrics in sorted(cells.items()):
        if set(metrics) != {"sequential_seconds", "fanout_seconds"}:
            continue
        speedup = metrics["sequential_seconds"] / metrics["fanout_seconds"]
        value = {
            "branches": float(branches),
            "work_seconds": work_seconds,
            "sequential_seconds": metrics["sequential_seconds"],
            "fanout_seconds": metrics["fanout_seconds"],
            "speedup": speedup,
        }
        values.append(value)
        rows.append(
            [
                str(branches),
                _seconds(work_seconds),
                _seconds(metrics["sequential_seconds"]),
                _seconds(metrics["fanout_seconds"]),
                f"{speedup:.2f}×",
            ]
        )
    if not rows:
        return {}, values
    return (
        _write_table(
            "rq3-choreography-critical-path",
            headers=(
                "Branches",
                "Work per branch",
                "Sequential median",
                "Fan-out median",
                "Speedup",
            ),
            rows=rows,
            output_dir=output_dir,
        ),
        values,
    )


def _overhead_table(
    report: Mapping[str, Any], output_dir: Path
) -> Tuple[Dict[str, Path], List[Tuple[str, float]]]:
    values = []
    rows = []
    for group in sorted(
        _groups_for(report, "abstraction-overhead"),
        key=lambda item: str(item["metric"]),
    ):
        median = float(group["statistics"]["median"])
        metric = str(group["metric"])
        values.append((metric, median))
        rows.append(
            [
                metric.removesuffix("_seconds").replace("_", " "),
                _seconds(median),
                str(int(group["statistics"]["count"])),
            ]
        )
    if not rows:
        return {}, values
    return (
        _write_table(
            "rq2-rq4-abstraction-overhead",
            headers=("Path", "Median", "Samples"),
            rows=rows,
            output_dir=output_dir,
        ),
        values,
    )


def _comparison_table(
    report: Mapping[str, Any], output_dir: Path
) -> Tuple[Dict[str, Path], Dict[str, Dict[str, float]]]:
    values: Dict[str, Dict[str, float]] = {}
    for group in _groups_for(report, "controlled-framework-comparison"):
        metric_name = str(group["metric"])
        match = COMPARISON_METRIC_RE.match(metric_name)
        if match:
            values.setdefault(match.group("framework"), {})[match.group("metric")] = (
                float(group["statistics"]["median"])
            )
            values[match.group("framework")][f"{match.group('metric')}_p95"] = float(
                group["statistics"]["p95"]
            )
            continue
        startup_match = COMPARISON_STARTUP_RE.match(metric_name)
        if startup_match:
            values.setdefault(startup_match.group("framework"), {})[
                startup_match.group("metric")
            ] = float(group["statistics"]["median"])
    rows = []
    for framework in ("praval", "langgraph", "crewai"):
        metrics = values.get(framework, {})
        if "elapsed_seconds" not in metrics:
            continue
        rows.append(
            [
                framework,
                _seconds(metrics.get("process_ready_seconds", 0.0)),
                _seconds(metrics["elapsed_seconds"]),
                _seconds(metrics["elapsed_seconds_p95"]),
                f"{metrics.get('correct', 0.0):.3f}",
                f"{metrics.get('model_calls', 0.0):.1f}",
            ]
        )
    if not rows:
        return {}, values
    return (
        _write_table(
            "rq5-controlled-comparison",
            headers=(
                "Framework",
                "Process ready (one run)",
                "Steady median",
                "Steady p95",
                "Correct fraction",
                "Model calls",
            ),
            rows=rows,
            output_dir=output_dir,
        ),
        values,
    )


def _scaling_table(
    report: Mapping[str, Any], output_dir: Path
) -> Tuple[Dict[str, Path], List[Dict[str, Any]]]:
    specifications = (
        (
            "in-memory",
            "reef-scaling-inmemory",
            "throughput_deliveries_per_second",
            "delivery_latency_seconds",
        ),
        (
            "RabbitMQ",
            "reef-scaling-rabbitmq",
            "rabbitmq_throughput_deliveries_per_second",
            "rabbitmq_delivery_latency_seconds",
        ),
    )
    cells: List[Dict[str, Any]] = []
    for backend, experiment, throughput_metric, latency_metric in specifications:
        values: Dict[Tuple[int, int], Dict[str, Mapping[str, Any]]] = {}
        for group in _groups_for(report, experiment):
            dimensions = group["dimensions"]
            if "agents" not in dimensions or "payload_bytes" not in dimensions:
                continue
            key = (
                int(dimensions["agents"]),
                int(dimensions["payload_bytes"]),
            )
            if group["metric"] == throughput_metric:
                values.setdefault(key, {})["throughput"] = group["statistics"]
            elif group["metric"] == latency_metric:
                values.setdefault(key, {})["latency"] = group["statistics"]
        for (agents, payload_bytes), metrics in sorted(values.items()):
            if set(metrics) != {"throughput", "latency"}:
                continue
            cells.append(
                {
                    "backend": backend,
                    "agents": agents,
                    "payload_bytes": payload_bytes,
                    "throughput": float(metrics["throughput"]["median"]),
                    "latency_p50": float(metrics["latency"]["p50"]),
                    "latency_p95": float(metrics["latency"]["p95"]),
                    "latency_p99": float(metrics["latency"]["p99"]),
                }
            )
    rows = [
        [
            str(cell["backend"]),
            str(cell["agents"]),
            (
                f"{cell['payload_bytes']} B"
                if cell["payload_bytes"] < 1024
                else f"{cell['payload_bytes'] // 1024} KiB"
            ),
            f"{cell['throughput']:.1f}",
            _seconds(cell["latency_p50"]),
            _seconds(cell["latency_p95"]),
            _seconds(cell["latency_p99"]),
        ]
        for cell in cells
    ]
    if not rows:
        return {}, cells
    paths = _write_table(
        "rq3-reef-scaling",
        headers=(
            "Backend",
            "Agents",
            "Payload",
            "Median deliveries/s",
            "p50 latency",
            "p95 latency",
            "p99 latency",
        ),
        rows=rows,
        output_dir=output_dir,
    )
    for backend, stem in (
        ("in-memory", "rq3-reef-scaling-inmemory"),
        ("RabbitMQ", "rq3-reef-scaling-rabbitmq"),
    ):
        backend_rows = [row[1:] for row in rows if row[0] == backend]
        paths.update(
            _write_table(
                stem,
                headers=(
                    "Agents",
                    "Payload",
                    "Median deliveries/s",
                    "p50",
                    "p95",
                    "p99",
                ),
                rows=backend_rows,
                output_dir=output_dir,
            )
        )
    return paths, cells


def _configure_plotting(output_dir: Path) -> Any:
    cache = output_dir / ".matplotlib-cache"
    cache.mkdir(exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(cache)
    os.environ["XDG_CACHE_HOME"] = str(cache)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as pyplot

    return pyplot


def _save_figure(figure: Any, stem: Path) -> Dict[str, Path]:
    svg = stem.with_suffix(".svg")
    png = stem.with_suffix(".png")
    figure.savefig(
        svg,
        bbox_inches="tight",
        metadata={"Date": None, "Creator": "Praval paper validation"},
    )
    svg.write_text(
        "\n".join(
            line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()
        )
        + "\n",
        encoding="utf-8",
    )
    figure.savefig(
        png,
        dpi=300,
        bbox_inches="tight",
        metadata={"Software": "Praval paper validation"},
    )
    return {f"{stem.name}_svg": svg, f"{stem.name}_png": png}


def _figures(
    *,
    choreography: Sequence[Mapping[str, float]],
    overhead: Sequence[Tuple[str, float]],
    comparison: Mapping[str, Mapping[str, float]],
    scaling: Sequence[Mapping[str, Any]],
    output_dir: Path,
) -> Dict[str, Path]:
    if not choreography and not overhead and not comparison:
        return {}
    pyplot = _configure_plotting(output_dir)
    paths: Dict[str, Path] = {}
    if choreography:
        figure, axis = pyplot.subplots(figsize=(6.4, 3.5))
        work_values = sorted({value["work_seconds"] for value in choreography})
        for work in work_values:
            rows = [value for value in choreography if value["work_seconds"] == work]
            axis.plot(
                [value["branches"] for value in rows],
                [value["speedup"] for value in rows],
                marker="o",
                label=f"{work * 1_000:.0f} ms work",
            )
        axis.axhline(1.0, color="#666666", linewidth=0.8)
        axis.set_xlabel("Independent branches")
        axis.set_ylabel("Sequential / fan-out median")
        axis.legend(frameon=False)
        axis.grid(axis="y", alpha=0.2)
        paths.update(_save_figure(figure, output_dir / "rq3-choreography-speedup"))
        pyplot.close(figure)
    if overhead:
        figure, axis = pyplot.subplots(figsize=(7.2, 4.2))
        labels = [
            name.removesuffix("_seconds").replace("_", " ") for name, _ in overhead
        ]
        values = [value * 1_000_000 for _, value in overhead]
        axis.barh(labels, values, color="#386cb0")
        axis.set_xlabel("Median duration (µs, log scale)")
        axis.set_xscale("log")
        axis.grid(axis="x", alpha=0.2)
        paths.update(_save_figure(figure, output_dir / "rq2-rq4-abstraction-overhead"))
        pyplot.close(figure)
    comparison_rows = [
        (name, values["elapsed_seconds"])
        for name, values in comparison.items()
        if "elapsed_seconds" in values
    ]
    if comparison_rows:
        figure, axis = pyplot.subplots(figsize=(5.8, 3.4))
        axis.bar(
            [name for name, _ in comparison_rows],
            [value * 1_000 for _, value in comparison_rows],
            color=["#1b9e77", "#7570b3", "#d95f02"],
        )
        axis.set_ylabel("Median elapsed time (ms)")
        axis.grid(axis="y", alpha=0.2)
        paths.update(_save_figure(figure, output_dir / "rq5-controlled-comparison"))
        pyplot.close(figure)
    if scaling:
        figure, axes = pyplot.subplots(1, 2, figsize=(9.0, 3.5))
        for axis, backend in zip(axes, ("in-memory", "RabbitMQ")):
            backend_rows = [value for value in scaling if value["backend"] == backend]
            payloads = sorted({int(value["payload_bytes"]) for value in backend_rows})
            for payload in payloads:
                rows = sorted(
                    (
                        value
                        for value in backend_rows
                        if int(value["payload_bytes"]) == payload
                    ),
                    key=lambda value: int(value["agents"]),
                )
                label = f"{payload} B" if payload < 1024 else f"{payload // 1024} KiB"
                axis.plot(
                    [value["agents"] for value in rows],
                    [value["throughput"] for value in rows],
                    marker="o",
                    label=label,
                )
            axis.set_title(backend)
            axis.set_xlabel("Agents")
            axis.grid(axis="y", alpha=0.2)
            axis.legend(frameon=False)
        axes[0].set_ylabel("Median deliveries/s")
        paths.update(_save_figure(figure, output_dir / "rq3-reef-scaling"))
        pyplot.close(figure)
    return paths


def _paper_values(
    *,
    choreography: Sequence[Mapping[str, float]],
    overhead: Sequence[Tuple[str, float]],
    comparison: Mapping[str, Mapping[str, float]],
    scaling: Sequence[Mapping[str, Any]],
    output_dir: Path,
) -> Path:
    values: Dict[str, Dict[str, Any]] = {}
    if choreography:
        speedups = [float(value["speedup"]) for value in choreography]
        values["choreography_speedup_range"] = {
            "experiment": "choreography-critical-path",
            "value": [min(speedups), max(speedups)],
            "rendered": f"{min(speedups):.2f}× to {max(speedups):.2f}×",
        }
    for metric, median in overhead:
        values[f"overhead_{metric.removesuffix('_seconds')}"] = {
            "experiment": "abstraction-overhead",
            "value": median,
            "rendered": _seconds(median),
        }
    for framework, metrics in comparison.items():
        if "elapsed_seconds" not in metrics:
            continue
        values[f"comparison_{framework}_median_elapsed"] = {
            "experiment": "controlled-framework-comparison",
            "value": metrics["elapsed_seconds"],
            "rendered": _seconds(metrics["elapsed_seconds"]),
        }
    for backend in ("in-memory", "RabbitMQ"):
        rows = [value for value in scaling if value["backend"] == backend]
        if not rows:
            continue
        throughputs = [float(value["throughput"]) for value in rows]
        key = backend.casefold().replace("-", "_")
        values[f"{key}_throughput_range"] = {
            "experiment": (
                "reef-scaling-inmemory"
                if backend == "in-memory"
                else "reef-scaling-rabbitmq"
            ),
            "value": [min(throughputs), max(throughputs)],
            "rendered": (
                f"{min(throughputs):.1f} to " f"{max(throughputs):.1f} deliveries/s"
            ),
        }
    path = output_dir / "paper-values.json"
    path.write_text(
        stable_json({"schema_version": 1, "values": values}),
        encoding="utf-8",
    )
    return path


def write_paper_artifact_bundle(
    runs: Sequence[Mapping[str, Any]],
    *,
    registry: Registry,
    output_dir: Path,
) -> Dict[str, Path]:
    """Write ledgers, generated tables, figures, and a digest manifest."""
    destination = output_dir.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    paths = write_evidence_bundle(runs, registry=registry, output_dir=destination)
    history = load_history(
        Path(__file__).with_name("history.toml"),
        repository_root=Path(__file__).resolve().parents[2],
    )
    paths.update(_history_tables(history, destination))
    claim_report = claim_evidence_report(runs, registry)
    metric_report = metric_evidence_report(runs)
    paths.update(_claim_tables(claim_report, destination))
    choreography_paths, choreography = _choreography_table(metric_report, destination)
    paths.update(choreography_paths)
    overhead_paths, overhead = _overhead_table(metric_report, destination)
    paths.update(overhead_paths)
    comparison_paths, comparison = _comparison_table(metric_report, destination)
    paths.update(comparison_paths)
    scaling_paths, scaling = _scaling_table(metric_report, destination)
    paths.update(scaling_paths)
    paths.update(
        _figures(
            choreography=choreography,
            overhead=overhead,
            comparison=comparison,
            scaling=scaling,
            output_dir=destination,
        )
    )
    paths["paper_values"] = _paper_values(
        choreography=choreography,
        overhead=overhead,
        comparison=comparison,
        scaling=scaling,
        output_dir=destination,
    )
    cache = destination / ".matplotlib-cache"
    if cache.exists():
        import shutil

        shutil.rmtree(cache)
    manifest_path = destination / "paper-artifacts.json"
    manifest = {
        "schema_version": 1,
        "artifacts": {
            name: {
                "path": str(path.relative_to(destination)),
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
            for name, path in sorted(paths.items())
        },
    }
    manifest_path.write_text(stable_json(manifest), encoding="utf-8")
    paths["manifest"] = manifest_path
    return paths
