#!/usr/bin/env python3
"""Validate release coverage floors from coverage.py's JSON report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, Tuple

FILE_FLOORS: Dict[str, float] = {
    "src/praval/core/reef.py": 85.0,
    "src/praval/core/transport.py": 80.0,
    "src/praval/observability/instrumentation/manager.py": 80.0,
    "src/praval/observability/export/console_viewer.py": 70.0,
    "src/praval/observability/export/otlp_exporter.py": 70.0,
    "src/praval/storage/providers/postgresql.py": 60.0,
    "src/praval/storage/providers/qdrant_provider.py": 60.0,
    "src/praval/storage/providers/redis_provider.py": 60.0,
    "src/praval/storage/providers/s3_provider.py": 60.0,
}
PACKAGE_FLOORS: Dict[str, float] = {"src/praval/mcp/": 90.0}
OVERALL_FLOOR = 90.0


def _normalized_files(report: dict) -> Dict[str, dict]:
    return {
        str(path).replace("\\", "/"): data for path, data in report["files"].items()
    }


def _percent(covered: int, statements: int) -> float:
    return 100.0 if statements == 0 else covered * 100.0 / statements


def _summary_counts(summary: dict) -> Tuple[int, int]:
    return int(summary["covered_lines"]), int(summary["num_statements"])


def _package_counts(files: Dict[str, dict], prefix: str) -> Tuple[int, int]:
    covered = 0
    statements = 0
    for path, data in files.items():
        if path.startswith(prefix):
            file_covered, file_statements = _summary_counts(data["summary"])
            covered += file_covered
            statements += file_statements
    return covered, statements


def validate(report: dict) -> Iterable[str]:
    """Yield human-readable failures for unmet release floors."""
    files = _normalized_files(report)
    total_covered, total_statements = _summary_counts(report["totals"])
    total_percent = _percent(total_covered, total_statements)
    if total_percent + 1e-9 < OVERALL_FLOOR:
        yield f"whole package: {total_percent:.2f}% < {OVERALL_FLOOR:.2f}%"

    for path, floor in FILE_FLOORS.items():
        data = files.get(path)
        if data is None:
            yield f"{path}: missing from coverage report"
            continue
        covered, statements = _summary_counts(data["summary"])
        percent = _percent(covered, statements)
        if percent + 1e-9 < floor:
            yield f"{path}: {percent:.2f}% < {floor:.2f}%"

    for prefix, floor in PACKAGE_FLOORS.items():
        covered, statements = _package_counts(files, prefix)
        if statements == 0:
            yield f"{prefix}: missing from coverage report"
            continue
        percent = _percent(covered, statements)
        if percent + 1e-9 < floor:
            yield f"{prefix}: {percent:.2f}% < {floor:.2f}%"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", nargs="?", default="coverage.json")
    args = parser.parse_args()
    report_path = Path(args.report)
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Unable to read coverage report {report_path}: {exc}", file=sys.stderr)
        return 2

    failures = list(validate(report))
    if failures:
        print("Coverage release floors failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Coverage release floors passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
