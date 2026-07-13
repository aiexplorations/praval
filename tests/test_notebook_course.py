"""Tests for the visual notebook catalog and exact-wheel runner."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "notebooks" / "manifest.toml"
SPEC = importlib.util.spec_from_file_location(
    "praval_run_notebooks", ROOT / "scripts" / "run_notebooks.py"
)
assert SPEC is not None and SPEC.loader is not None
run_notebooks = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run_notebooks
SPEC.loader.exec_module(run_notebooks)

NotebookManifestError = run_notebooks.NotebookManifestError
_clean_environment = run_notebooks._clean_environment
_install_target = run_notebooks._install_target
_redact_notebook = run_notebooks._redact_notebook
load_manifest = run_notebooks.load_manifest
sanitize = run_notebooks.sanitize


def _write_notebook(path: Path, mode: str = "offline") -> None:
    path.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "markdown",
                        "metadata": {},
                        "source": ["# Notebook\n"],
                    },
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": ["await ready()\n"],
                    },
                ],
                "metadata": {"praval": {"execution_mode": mode, "video_url": ""}},
                "nbformat": 4,
                "nbformat_minor": 5,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_manifest(path: Path, notebook_id: str = "notebook") -> None:
    path.write_text(
        f"""
schema_version = 1
[[notebook]]
id = "{notebook_id}"
path = "course.ipynb"
title = "Course"
track = "course"
mode = "offline"
certify = true
extras = []
providers = []
services = []
timeout = 30
video_url = ""
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_repository_catalog_registers_every_notebook() -> None:
    manifest = load_manifest(MANIFEST)
    discovered = {
        path.relative_to(MANIFEST.parent).as_posix()
        for path in MANIFEST.parent.rglob("*.ipynb")
        if ".ipynb_checkpoints" not in path.parts
    }

    assert {item.path.as_posix() for item in manifest.notebooks} == discovered
    assert len(manifest.notebooks) == 17
    assert sum(item.certify for item in manifest.notebooks) == 13


def test_course_has_offline_service_and_manual_live_paths() -> None:
    manifest = load_manifest(MANIFEST)
    certified = [item for item in manifest.notebooks if item.certify]

    assert {item.mode for item in certified} == {"offline", "services", "live"}
    assert sum(item.mode == "offline" for item in certified) == 7
    assert sum(bool(item.video_url) for item in certified) == 9
    assert all(item.timeout > 0 for item in certified)


def test_committed_notebooks_have_no_outputs_or_execution_counts() -> None:
    manifest = load_manifest(MANIFEST)

    for item in manifest.notebooks:
        raw = json.loads((manifest.notebooks_dir / item.path).read_text())
        for cell in raw["cells"]:
            if cell["cell_type"] == "code":
                assert cell.get("execution_count") is None
                assert cell.get("outputs", []) == []


def test_manifest_allows_top_level_await_in_course_code(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "course.ipynb")
    manifest_path = tmp_path / "manifest.toml"
    _write_manifest(manifest_path)

    manifest = load_manifest(manifest_path)

    assert manifest.notebooks[0].id == "notebook"


def test_manifest_rejects_duplicate_notebook_ids(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "course.ipynb")
    _write_notebook(tmp_path / "second.ipynb")
    manifest_path = tmp_path / "manifest.toml"
    _write_manifest(manifest_path, notebook_id="duplicate")
    manifest_path.write_text(
        manifest_path.read_text()
        + """
[[notebook]]
id = "duplicate"
path = "second.ipynb"
title = "Second"
track = "course"
mode = "offline"
certify = true
extras = []
providers = []
services = []
timeout = 30
video_url = ""
""",
        encoding="utf-8",
    )

    with pytest.raises(NotebookManifestError, match="duplicate notebook id"):
        load_manifest(manifest_path)


def test_manifest_rejects_unregistered_notebooks(tmp_path: Path) -> None:
    _write_notebook(tmp_path / "course.ipynb")
    _write_notebook(tmp_path / "unregistered.ipynb")
    manifest_path = tmp_path / "manifest.toml"
    _write_manifest(manifest_path)

    with pytest.raises(NotebookManifestError, match="unregistered"):
        load_manifest(manifest_path)


def test_manifest_rejects_committed_output(tmp_path: Path) -> None:
    notebook = tmp_path / "course.ipynb"
    _write_notebook(notebook)
    raw = json.loads(notebook.read_text())
    raw["cells"][1]["outputs"] = [{"output_type": "stream", "text": "saved"}]
    notebook.write_text(json.dumps(raw), encoding="utf-8")
    manifest_path = tmp_path / "manifest.toml"
    _write_manifest(manifest_path)

    with pytest.raises(NotebookManifestError, match="contains output"):
        load_manifest(manifest_path)


def test_clean_non_live_environment_removes_external_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("PYTHONPATH", "/source-checkout")

    environment = _clean_environment("offline", tmp_path)

    assert "OPENAI_API_KEY" not in environment
    assert "PYTHONPATH" not in environment
    assert environment["PRAVAL_OBSERVABILITY"] == "off"
    assert environment["JUPYTER_RUNTIME_DIR"].startswith(str(tmp_path))


def test_secret_redaction_applies_to_logs_and_notebook_outputs() -> None:
    secret = "do-not-leak"

    assert sanitize(f"error {secret}", [secret]) == "error ***"
    redacted = _redact_notebook(
        {"cells": [{"outputs": [{"text": f"value={secret}"}]}]}, [secret]
    )
    assert secret not in repr(redacted)
    assert "***" in repr(redacted)


def test_install_target_validates_notebook_extras(tmp_path: Path) -> None:
    wheel = tmp_path / "praval-0.8.0-py3-none-any.whl"

    assert _install_target(wheel, ["mcp", "secure", "mcp"]).endswith("[mcp,secure]")
    with pytest.raises(ValueError, match="invalid wheel extra"):
        _install_target(wheel, ["mcp; unsafe"])
