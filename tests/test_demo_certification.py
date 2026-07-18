"""Tests for exact-wheel live certification release verification."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "praval_verify_demo_certification",
    ROOT / "scripts" / "verify_demo_certification.py",
)
assert SPEC is not None and SPEC.loader is not None
verify_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = verify_module
SPEC.loader.exec_module(verify_module)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def valid_evidence(tmp_path):
    wheel_name = "praval-0.8.1-py3-none-any.whl"
    digest = "a" * 64
    build = tmp_path / "build.json"
    certification = tmp_path / "certification.json"
    write_json(
        build,
        {
            "commit": "abc123",
            "artifacts": [{"filename": wheel_name, "sha256": digest}],
        },
    )
    write_json(
        certification,
        {
            "commit": "abc123",
            "mode": "live",
            "status": "passed",
            "wheel": {
                "filename": wheel_name,
                "sha256": digest,
                "version": "0.8.1",
                "installed_sha256": digest,
                "installed_version": "0.8.1",
                "source_isolated": True,
            },
            "summary": {"total": 4, "passed": 4, "failed": 0, "skipped": 0},
            "results": [{"id": str(index), "status": "passed"} for index in range(4)],
        },
    )
    return build, certification


def test_verify_accepts_exact_successful_live_evidence(tmp_path):
    build, certification = valid_evidence(tmp_path)

    errors = verify_module.verify(
        build, certification, "abc123", expected_version="0.8.1"
    )

    assert errors == []


def test_verify_rejects_commit_hash_and_skip_mismatches(tmp_path):
    build, certification = valid_evidence(tmp_path)
    value = json.loads(certification.read_text(encoding="utf-8"))
    value["commit"] = "wrong"
    value["wheel"]["sha256"] = "b" * 64
    value["summary"]["skipped"] = 1
    write_json(certification, value)

    errors = verify_module.verify(
        build, certification, "abc123", expected_version="0.8.1"
    )

    assert any("certification commit" in error for error in errors)
    assert any("zero failures and zero skips" in error for error in errors)
    assert any("SHA-256" in error for error in errors)


def test_verify_rejects_nonpassing_result_and_wrong_version(tmp_path):
    build, certification = valid_evidence(tmp_path)
    value = json.loads(certification.read_text(encoding="utf-8"))
    value["results"][0]["status"] = "failed"
    value["wheel"]["version"] = "0.8.0"
    write_json(certification, value)

    errors = verify_module.verify(
        build, certification, "abc123", expected_version="0.8.1"
    )

    assert any("non-passing" in error for error in errors)
    assert any("version" in error for error in errors)


def test_verify_rejects_unverifiable_installed_wheel(tmp_path):
    build, certification = valid_evidence(tmp_path)
    value = json.loads(certification.read_text(encoding="utf-8"))
    value["wheel"].pop("installed_sha256")
    value["wheel"]["source_isolated"] = False
    write_json(certification, value)

    errors = verify_module.verify(
        build, certification, "abc123", expected_version="0.8.1"
    )

    assert any("installed wheel SHA-256" in error for error in errors)
    assert any("source-tree import isolation" in error for error in errors)


def test_verify_rejects_summary_result_count_mismatch(tmp_path):
    build, certification = valid_evidence(tmp_path)
    value = json.loads(certification.read_text(encoding="utf-8"))
    value["summary"]["total"] = 99
    write_json(certification, value)

    errors = verify_module.verify(build, certification, "abc123")

    assert any("summary total" in error for error in errors)
