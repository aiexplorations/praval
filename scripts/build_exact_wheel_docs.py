#!/usr/bin/env python3
"""Build Sphinx documentation against an installed release wheel."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import venv
from pathlib import Path
from typing import Dict, Iterable


def _venv_python(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_files(root: Path) -> Iterable[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def tree_sha256(root: Path) -> str:
    """Hash relative paths and contents for a deterministic documentation tree."""
    digest = hashlib.sha256()
    for path in _tree_files(root):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def sanitize_site(site_dir: Path) -> None:
    """Remove build-only files that must not be published."""
    for path in sorted(site_dir.rglob("*"), reverse=True):
        if path.is_dir() and path.name in {".doctrees", "__pycache__"}:
            shutil.rmtree(path)
        elif path.is_file() and (
            path.name.endswith((".bak", ".pyc", ".pyo"))
            or path.name in {".buildinfo", ".DS_Store", ".nojekyll"}
        ):
            path.unlink()


def build_docs(
    root: Path,
    dist_dir: Path,
    output_dir: Path,
    *,
    commit: str,
) -> Dict[str, object]:
    """Install the sole wheel, build Sphinx, and return its provenance manifest."""
    wheels = sorted(dist_dir.glob("praval-*.whl"))
    if len(wheels) != 1:
        raise ValueError(f"expected one Praval wheel, found {len(wheels)}")
    wheel = wheels[0].resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    site_dir = output_dir / "site"
    output_dir.mkdir(parents=True)

    with tempfile.TemporaryDirectory(prefix="praval-docs-") as temp:
        environment = Path(temp) / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _venv_python(environment)
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                f"{wheel}[docs,mcp,secure]",
            ],
            check=True,
        )
        probe = subprocess.check_output(
            [
                str(python),
                "-c",
                (
                    "import json, pathlib, praval; "
                    "print(json.dumps({'version': praval.__version__, "
                    "'path': str(pathlib.Path(praval.__file__).resolve())}))"
                ),
            ],
            text=True,
        )
        installed = json.loads(probe)
        installed_path = Path(installed["path"])
        if root in installed_path.parents:
            raise RuntimeError(
                "documentation build imported Praval from the source tree"
            )

        environment_vars = os.environ.copy()
        environment_vars.pop("PYTHONPATH", None)
        environment_vars["PRAVAL_DOCS_EXACT_WHEEL"] = "1"
        subprocess.run(
            [
                str(python),
                "-m",
                "sphinx",
                "-b",
                "html",
                "-W",
                "--keep-going",
                str(root / "docs/sphinx"),
                str(site_dir),
            ],
            cwd=temp,
            env=environment_vars,
            check=True,
        )

    sanitize_site(site_dir)
    manifest: Dict[str, object] = {
        "schema_version": 1,
        "commit": commit,
        "version": installed["version"],
        "wheel": wheel.name,
        "wheel_sha256": _sha256(wheel),
        "documentation_tree_sha256": tree_sha256(site_dir),
        "file_count": sum(1 for _ in _tree_files(site_dir)),
    }
    (output_dir / "documentation-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    manifest = build_docs(
        args.root.resolve(),
        args.dist.resolve(),
        args.output.resolve(),
        commit=args.commit,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
