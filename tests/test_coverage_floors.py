"""Tests for the release coverage-floor checker."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "check_coverage_floors.py"
SPEC = importlib.util.spec_from_file_location("check_coverage_floors", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def _summary(covered, statements):
    return {"covered_lines": covered, "num_statements": statements}


def _passing_report():
    files = {path: {"summary": _summary(9, 10)} for path in checker.FILE_FLOORS}
    files["src/praval/mcp/client.py"] = {"summary": _summary(9, 10)}
    return {"files": files, "totals": _summary(90, 100)}


def test_validate_accepts_all_release_floors():
    assert list(checker.validate(_passing_report())) == []


def test_validate_reports_overall_file_package_and_missing_failures():
    report = _passing_report()
    report["totals"] = _summary(89, 100)
    report["files"]["src/praval/core/reef.py"] = {"summary": _summary(8, 10)}
    del report["files"]["src/praval/core/transport.py"]
    report["files"]["src/praval/mcp/client.py"] = {"summary": _summary(8, 10)}

    failures = list(checker.validate(report))

    assert any("whole package" in failure for failure in failures)
    assert any("reef.py" in failure for failure in failures)
    assert any("transport.py: missing" in failure for failure in failures)
    assert any("src/praval/mcp/" in failure for failure in failures)
