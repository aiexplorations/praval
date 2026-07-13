"""Unit contracts for deterministic release helper scripts."""

import hashlib
import importlib.util
import io
import json
import sys
import tarfile
from pathlib import Path


def _load_script(name):
    path = Path("scripts") / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"praval_release_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


normalize_sdist = _load_script("normalize_sdist").normalize_sdist
validation = _load_script("validate_distribution")
_forbidden_entries = validation._forbidden_entries
_package_version = validation._package_version
_project_version = validation._project_version
write_manifest = _load_script("write_build_manifest").write_manifest


def _write_sdist(path, *, mtime, uid):
    with tarfile.open(path, "w:gz") as archive:
        root = tarfile.TarInfo("praval-0.8.0")
        root.type = tarfile.DIRTYPE
        root.mode = 0o755
        root.mtime = mtime
        root.uid = uid
        archive.addfile(root)

        content = b"release-content\n"
        member = tarfile.TarInfo("praval-0.8.0/README.md")
        member.size = len(content)
        member.mode = 0o644
        member.mtime = mtime
        member.uid = uid
        archive.addfile(member, io.BytesIO(content))


def test_normalize_sdist_produces_identical_canonical_archives(tmp_path):
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    _write_sdist(first, mtime=100, uid=501)
    _write_sdist(second, mtime=200, uid=1000)

    normalize_sdist(first, epoch=1_700_000_000)
    normalize_sdist(second, epoch=1_700_000_000)

    assert first.read_bytes() == second.read_bytes()
    with tarfile.open(first, "r:gz") as archive:
        for member in archive.getmembers():
            assert member.mtime == 1_700_000_000
            assert member.uid == 0
            assert member.gid == 0
            assert member.uname == ""
            assert member.gname == ""


def test_distribution_validation_helpers_read_versions_and_reject_generated_files():
    assert _project_version(Path("pyproject.toml")) == "0.8.0"
    assert _package_version(Path("src/praval/__init__.py")) == "0.8.0"
    assert _forbidden_entries(
        [
            "praval-0.8.0/docs/generated/manual.pdf",
            "praval-0.8.0/docs/logo.png",
            "praval/__pycache__/module.pyc",
        ]
    ) == [
        "praval-0.8.0/docs/generated/manual.pdf",
        "praval-0.8.0/docs/logo.png",
        "praval/__pycache__/module.pyc",
    ]


def test_write_build_manifest_records_exact_artifacts(tmp_path, monkeypatch):
    (tmp_path / "praval.whl").write_bytes(b"wheel")
    (tmp_path / "praval.tar.gz").write_bytes(b"sdist")
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")

    manifest = write_manifest(tmp_path)

    assert manifest["commit"] == "abc123"
    assert manifest["source_date_epoch"] == "1700000000"
    written = json.loads((tmp_path / "build-manifest.json").read_text())
    assert written == manifest
    checksums = (tmp_path / "SHA256SUMS").read_text()
    assert hashlib.sha256(b"wheel").hexdigest() in checksums
    assert hashlib.sha256(b"sdist").hexdigest() in checksums
