"""Unit contracts for deterministic release helper scripts."""

import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.9/3.10 compatibility
    import tomli as tomllib


def _load_script(name):
    path = Path("scripts") / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"praval_release_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validation = _load_script("validate_distribution")
_forbidden_entries = validation._forbidden_entries
_package_version = validation._package_version
_project_version = validation._project_version
validate_distribution = validation.validate
write_manifest = _load_script("write_build_manifest").write_manifest
validate_pypi_payload = _load_script("verify_pypi_wheel").validate_pypi_payload
type_checks = _load_script("check_types")
release_metadata = _load_script("check_release_metadata")
sys.modules["build_exact_wheel_docs"] = _load_script("build_exact_wheel_docs")
stage_docs = _load_script("stage_docs_artifact")


def test_distribution_validation_helpers_read_versions_and_reject_generated_files():
    assert _project_version(Path("pyproject.toml")) == "0.8.1"
    assert _package_version(Path("src/praval/__init__.py")) == "0.8.1"
    assert _forbidden_entries(
        [
            "praval-0.8.1/docs/generated/manual.pdf",
            "praval-0.8.1/docs/logo.png",
            "praval/__pycache__/module.pyc",
            "praval/examples/notebooks/.ipynb_checkpoints/lesson.ipynb",
        ]
    ) == [
        "praval-0.8.1/docs/generated/manual.pdf",
        "praval-0.8.1/docs/logo.png",
        "praval/__pycache__/module.pyc",
        "praval/examples/notebooks/.ipynb_checkpoints/lesson.ipynb",
    ]


def test_write_build_manifest_records_exact_artifacts(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist"
    evidence_dir = tmp_path / "evidence"
    dist_dir.mkdir()
    (dist_dir / "praval.whl").write_bytes(b"wheel")
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    manifest = write_manifest(dist_dir, evidence_dir)

    assert manifest["commit"] == "abc123"
    assert manifest["source_date_epoch"] == "1700000000"
    written = json.loads((evidence_dir / "build-manifest.json").read_text())
    assert written == manifest
    checksums = (evidence_dir / "SHA256SUMS").read_text()
    assert hashlib.sha256(b"wheel").hexdigest() in checksums
    assert sorted(path.name for path in dist_dir.iterdir()) == ["praval.whl"]
    assert [item["filename"] for item in manifest["artifacts"]] == ["praval.whl"]


@pytest.mark.parametrize("extra_name", ["praval.tar.gz", "build-manifest.json"])
def test_wheel_only_release_helpers_reject_extra_files(
    tmp_path, monkeypatch, extra_name
):
    dist_dir = tmp_path / "dist"
    evidence_dir = tmp_path / "evidence"
    dist_dir.mkdir()
    (dist_dir / "praval-0.8.1-py3-none-any.whl").write_bytes(b"wheel")
    (dist_dir / extra_name).write_bytes(b"extra")
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    assert "expected one distribution file, found 2" in validate_distribution(dist_dir)
    with pytest.raises(ValueError, match="exactly one wheel"):
        write_manifest(dist_dir, evidence_dir)


def test_pypi_verifier_accepts_the_exact_single_wheel():
    manifest = {
        "artifacts": [
            {"filename": "praval-0.8.1-py3-none-any.whl", "sha256": "abc", "size": 9}
        ]
    }
    payload = {
        "info": {"version": "0.8.1"},
        "urls": [
            {
                "filename": "praval-0.8.1-py3-none-any.whl",
                "packagetype": "bdist_wheel",
                "digests": {"sha256": "abc"},
                "size": 9,
            }
        ],
    }

    assert validate_pypi_payload(manifest, payload, "0.8.1") == []


def test_pypi_verifier_rejects_extra_files_and_hash_mismatch():
    manifest = {
        "artifacts": [
            {"filename": "praval-0.8.1-py3-none-any.whl", "sha256": "abc", "size": 9}
        ]
    }
    payload = {
        "info": {"version": "0.8.1"},
        "urls": [
            {
                "filename": "praval-0.8.1-py3-none-any.whl",
                "packagetype": "bdist_wheel",
                "digests": {"sha256": "wrong"},
                "size": 9,
            },
            {"filename": "praval-0.8.1.tar.gz", "packagetype": "sdist"},
        ],
    }

    errors = validate_pypi_payload(manifest, payload, "0.8.1")

    assert "PyPI release must contain exactly one file, found 2" in errors
    assert "PyPI wheel SHA-256 does not match the exact CI build manifest" in errors


def test_type_checks_cover_current_and_minimum_python_versions():
    labels = [label for label, _ in type_checks.TYPE_CHECKS]
    commands = [tuple(arguments) for _, arguments in type_checks.TYPE_CHECKS]

    assert labels == [
        "strict Python 3.13 typing",
        "Python 3.9 compatibility typing",
    ]
    assert ("--python-version", "3.13", "src/praval/") in commands
    assert any(
        "--python-version" in command
        and "3.9" in command
        and "--no-site-packages" in command
        for command in commands
    )


def test_python39_s3_extras_constrain_cohere_request_stubs():
    project = tomllib.loads(Path("pyproject.toml").read_text())["project"]
    expected = "types-requests==2.28.11.17; python_version < '3.10'"

    for extra in ("storage", "all", "dev"):
        assert expected in project["optional-dependencies"][extra]


def _write_version_wheel(path: Path, version: str = "0.8.1") -> None:
    metadata = f"Metadata-Version: 2.1\nName: praval\nVersion: {version}\n"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"praval-{version}.dist-info/METADATA", metadata)


def test_release_metadata_accepts_built_wheel_before_install(tmp_path, monkeypatch):
    _write_version_wheel(tmp_path / "praval-0.8.1-py3-none-any.whl")

    def not_installed(_name):
        raise release_metadata.importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(release_metadata.importlib.metadata, "version", not_installed)

    assert release_metadata.validate(Path.cwd(), dist_dir=tmp_path) == []


def _write_docs_artifact(root: Path, *, commit: str) -> None:
    site = root / "site"
    site.mkdir(parents=True)
    (site / "index.html").write_text("<h1>Praval</h1>", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "commit": commit,
        "version": "0.8.1",
        "wheel": "praval-0.8.1-py3-none-any.whl",
        "wheel_sha256": "a" * 64,
        "documentation_tree_sha256": stage_docs.tree_sha256(site),
        "file_count": 1,
    }
    (root / "documentation-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def test_docs_stager_rejects_non_release_commit_provenance(tmp_path):
    artifact = tmp_path / "artifact"
    _write_docs_artifact(artifact, commit="local-docs-build")

    with pytest.raises(ValueError, match="full Git SHA"):
        stage_docs.stage_docs(artifact, tmp_path / "website")


def test_docs_stager_copies_identical_versioned_and_latest_trees(tmp_path):
    artifact = tmp_path / "artifact"
    website = tmp_path / "website"
    (website / "docs").mkdir(parents=True)
    (website / "docs/versions.json").write_text(
        json.dumps(
            {
                "current": "0.7.22",
                "latest": "0.7.22",
                "versions": [
                    {
                        "version": "0.7.22",
                        "url": "/docs/v0.7.22/",
                        "title": "v0.7.22 (latest)",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _write_docs_artifact(artifact, commit="b" * 40)

    manifest = stage_docs.stage_docs(artifact, website)

    assert manifest["version"] == "0.8.1"
    versioned = website / "docs/v0.8.1"
    latest = website / "docs/latest"
    expected_files = [Path("documentation-manifest.json"), Path("index.html")]
    assert (
        sorted(
            path.relative_to(versioned)
            for path in versioned.rglob("*")
            if path.is_file()
        )
        == expected_files
    )
    assert {
        path.relative_to(versioned): path.read_bytes()
        for path in versioned.rglob("*")
        if path.is_file()
    } == {
        path.relative_to(latest): path.read_bytes()
        for path in latest.rglob("*")
        if path.is_file()
    }
    versions = json.loads((website / "docs/versions.json").read_text())
    assert versions["current"] == versions["latest"] == "0.8.1"
