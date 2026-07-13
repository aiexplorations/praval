#!/usr/bin/env python3
"""Validate or execute Praval notebooks against an exact wheel artifact."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import venv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    import tomllib
except ImportError:  # pragma: no cover - exercised by Python 3.9 CI
    import tomli as tomllib  # type: ignore[no-redef]


SCHEMA_VERSION = 1
MODES = {"offline", "services", "live", "reference"}
EXECUTION_DEPENDENCIES = (
    "nbclient==0.10.2",
    "nbformat==5.10.4",
    "ipykernel==7.1.0",
)
SECRET_FRAGMENTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTHORIZATION")
LIVE_SECRET_NAMES = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "COHERE_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENAI_COMPATIBLE_API_KEY",
    "OPENAI_COMPATIBLE_BASE_URL",
)
TRANSIENT_PATTERNS = (
    "429",
    "502",
    "503",
    "504",
    "connection reset",
    "rate limit",
    "temporarily unavailable",
    "timed out",
    "timeout",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class NotebookManifestError(ValueError):
    """Raised when the notebook catalog violates its execution contract."""


@dataclass(frozen=True)
class Notebook:
    """One manifest-backed notebook."""

    id: str
    path: Path
    title: str
    track: str
    mode: str
    certify: bool
    extras: Tuple[str, ...]
    providers: Tuple[str, ...]
    services: Tuple[str, ...]
    timeout: int
    video_url: str


@dataclass(frozen=True)
class NotebookManifest:
    """Validated notebook manifest."""

    path: Path
    notebooks: Tuple[Notebook, ...]

    @property
    def notebooks_dir(self) -> Path:
        return self.path.parent

    @property
    def examples_dir(self) -> Path:
        return self.notebooks_dir.parent

    @property
    def repository_root(self) -> Path:
        return self.examples_dir.parent


def _string_tuple(value: Any, name: str, notebook_id: str) -> Tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise NotebookManifestError(
            f"{notebook_id}: {name} must be an array of strings"
        )
    return tuple(value)


def _relative_notebook_path(value: Any, notebook_id: str) -> Path:
    if not isinstance(value, str) or not value.endswith(".ipynb"):
        raise NotebookManifestError(f"{notebook_id}: path must name an .ipynb file")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise NotebookManifestError(
            f"{notebook_id}: path must stay inside examples/notebooks"
        )
    return path


def load_manifest(path: Path) -> NotebookManifest:
    """Load the notebook catalog, inventory, and static notebook contract."""
    resolved = path.resolve()
    with resolved.open("rb") as handle:
        raw = tomllib.load(handle)
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise NotebookManifestError(f"schema_version must be {SCHEMA_VERSION}")
    entries = raw.get("notebook")
    if not isinstance(entries, list) or not entries:
        raise NotebookManifestError("manifest must define [[notebook]] entries")

    notebooks: List[Notebook] = []
    ids = set()
    paths = set()
    for item in entries:
        if not isinstance(item, dict):
            raise NotebookManifestError("each [[notebook]] entry must be a table")
        notebook_id = item.get("id")
        if not isinstance(notebook_id, str) or not notebook_id.strip():
            raise NotebookManifestError("every notebook must have a non-empty id")
        if notebook_id in ids:
            raise NotebookManifestError(f"duplicate notebook id: {notebook_id}")
        relative = _relative_notebook_path(item.get("path"), notebook_id)
        if relative.as_posix() in paths:
            raise NotebookManifestError(f"duplicate notebook path: {relative}")

        title = item.get("title")
        track = item.get("track")
        mode = item.get("mode")
        certify = item.get("certify")
        timeout = item.get("timeout")
        video_url = item.get("video_url")
        if not isinstance(title, str) or not title.strip():
            raise NotebookManifestError(f"{notebook_id}: title is required")
        if track not in {"course", "case-study"}:
            raise NotebookManifestError(f"{notebook_id}: invalid track")
        if mode not in MODES:
            raise NotebookManifestError(f"{notebook_id}: invalid mode")
        if not isinstance(certify, bool):
            raise NotebookManifestError(f"{notebook_id}: certify must be boolean")
        if not isinstance(timeout, int) or timeout < 0:
            raise NotebookManifestError(f"{notebook_id}: timeout must be non-negative")
        if certify and (mode == "reference" or timeout == 0):
            raise NotebookManifestError(
                f"{notebook_id}: certified notebooks need an executable mode "
                "and timeout"
            )
        if mode == "reference" and certify:
            raise NotebookManifestError(
                f"{notebook_id}: reference notebooks cannot be certified"
            )
        if not isinstance(video_url, str):
            raise NotebookManifestError(f"{notebook_id}: video_url must be a string")

        notebook = Notebook(
            id=notebook_id,
            path=relative,
            title=title,
            track=track,
            mode=mode,
            certify=certify,
            extras=_string_tuple(item.get("extras"), "extras", notebook_id),
            providers=_string_tuple(item.get("providers"), "providers", notebook_id),
            services=_string_tuple(item.get("services"), "services", notebook_id),
            timeout=timeout,
            video_url=video_url,
        )
        notebooks.append(notebook)
        ids.add(notebook_id)
        paths.add(relative.as_posix())

    manifest = NotebookManifest(path=resolved, notebooks=tuple(notebooks))
    validate_inventory(manifest)
    for notebook in manifest.notebooks:
        validate_notebook(manifest.notebooks_dir / notebook.path, notebook)
    return manifest


def validate_inventory(manifest: NotebookManifest) -> None:
    """Require every maintained notebook to be catalogued exactly once."""
    discovered = {
        path.relative_to(manifest.notebooks_dir).as_posix()
        for path in manifest.notebooks_dir.rglob("*.ipynb")
        if ".ipynb_checkpoints" not in path.parts
    }
    registered = {notebook.path.as_posix() for notebook in manifest.notebooks}
    missing = sorted(discovered - registered)
    stale = sorted(registered - discovered)
    if missing or stale:
        details = []
        if missing:
            details.append("unregistered: " + ", ".join(missing))
        if stale:
            details.append("missing files: " + ", ".join(stale))
        raise NotebookManifestError("; ".join(details))


def validate_notebook(path: Path, entry: Notebook) -> None:
    """Check JSON structure, clean outputs, code syntax, and course metadata."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise NotebookManifestError(
            f"{entry.id}: invalid notebook JSON: {exc}"
        ) from exc
    if raw.get("nbformat") != 4 or not isinstance(raw.get("cells"), list):
        raise NotebookManifestError(f"{entry.id}: notebook must use nbformat 4")
    cells = raw["cells"]
    if not cells or cells[0].get("cell_type") != "markdown":
        raise NotebookManifestError(f"{entry.id}: first cell must be markdown")
    if entry.track == "course":
        metadata = raw.get("metadata", {}).get("praval", {})
        if metadata.get("execution_mode") != entry.mode:
            raise NotebookManifestError(
                f"{entry.id}: notebook execution_mode does not match manifest"
            )
        if entry.video_url and metadata.get("video_url") != entry.video_url:
            raise NotebookManifestError(
                f"{entry.id}: notebook video URL does not match manifest"
            )
    for index, cell in enumerate(cells):
        if cell.get("cell_type") != "code":
            continue
        if cell.get("execution_count") is not None or cell.get("outputs"):
            raise NotebookManifestError(
                f"{entry.id}: committed code cell {index} contains output"
            )
        if entry.track != "course":
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        if not isinstance(source, str):
            raise NotebookManifestError(f"{entry.id}: cell {index} source is invalid")
        try:
            compile(
                source,
                f"{entry.path.as_posix()}#cell-{index}",
                "exec",
                flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
            )
        except SyntaxError as exc:
            raise NotebookManifestError(
                f"{entry.id}: code cell {index} does not compile: {exc}"
            ) from exc


def sha256_file(path: Path) -> str:
    """Return a file's SHA-256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _python_in_venv(directory: Path) -> Path:
    if os.name == "nt":
        return directory / "Scripts" / "python.exe"
    return directory / "bin" / "python"


def _find_wheel(value: Path) -> Path:
    value = value.resolve()
    if value.is_file() and value.name.startswith("praval-") and value.suffix == ".whl":
        return value
    if value.is_dir():
        wheels = sorted(value.glob("praval-*.whl"))
        if len(wheels) == 1:
            return wheels[0]
        raise ValueError(f"expected one Praval wheel in {value}, found {len(wheels)}")
    raise ValueError(f"not a Praval wheel path: {value}")


def _install_target(wheel: Path, extras: Iterable[str]) -> str:
    normalized = sorted(set(extras))
    for extra in normalized:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", extra) is None:
            raise ValueError(f"invalid wheel extra: {extra!r}")
    suffix = f"[{','.join(normalized)}]" if normalized else ""
    return f"{wheel}{suffix}"


def _secret_values(environment: Mapping[str, str]) -> Tuple[str, ...]:
    values = []
    for name, value in environment.items():
        if value and (
            name == "OPENAI_COMPATIBLE_BASE_URL"
            or any(fragment in name.upper() for fragment in SECRET_FRAGMENTS)
        ):
            values.append(value)
    return tuple(sorted(set(values), key=len, reverse=True))


def sanitize(value: str, secrets: Iterable[str]) -> str:
    """Redact configured credential values from captured output."""
    for secret in secrets:
        if secret:
            value = value.replace(secret, "***")
    return value[-65536:]


def _clean_environment(mode: str, workspace: Path) -> Dict[str, str]:
    environment = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT"):
        environment.pop(name, None)
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PRAVAL_NOTEBOOK_MODE": mode,
            "PRAVAL_OBSERVABILITY": "off" if mode != "live" else "on",
            "IPYTHONDIR": str(workspace / "ipython"),
            "JUPYTER_CONFIG_DIR": str(workspace / "jupyter-config"),
            "JUPYTER_DATA_DIR": str(workspace / "jupyter-data"),
            "JUPYTER_RUNTIME_DIR": str(workspace / "jupyter-runtime"),
        }
    )
    if mode != "live":
        for name in LIVE_SECRET_NAMES:
            environment.pop(name, None)
    return environment


def _installed_info(python: Path, cwd: Path, wheel_hash: str) -> Dict[str, str]:
    code = (
        "import importlib.metadata,json,pathlib,praval;"
        "d=importlib.metadata.distribution('praval');"
        "u=d.read_text('direct_url.json');"
        "print(json.dumps({'version':praval.__version__,"
        "'metadata_version':d.version,"
        "'path':str(pathlib.Path(praval.__file__).resolve()),"
        "'direct_url':u}))"
    )
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [str(python), "-I", "-c", code],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    info = json.loads(completed.stdout)
    if info["version"] != info["metadata_version"]:
        raise RuntimeError("installed version and wheel metadata differ")
    direct = json.loads(info["direct_url"] or "{}")
    archive = direct.get("archive_info", {})
    installed_hash = archive.get("hashes", {}).get("sha256", "")
    if not installed_hash and str(archive.get("hash", "")).startswith("sha256="):
        installed_hash = archive["hash"].split("=", 1)[1]
    if not SHA256_RE.fullmatch(installed_hash) or installed_hash != wheel_hash:
        raise RuntimeError("installed Praval wheel hash does not match supplied wheel")
    return {
        "version": str(info["version"]),
        "path": str(info["path"]),
        "wheel_sha256": installed_hash,
    }


def _copy_execution_inputs(manifest: NotebookManifest, destination: Path) -> Path:
    examples = destination / "examples"
    shutil.copytree(manifest.notebooks_dir, examples / "notebooks")
    certification = manifest.examples_dir / "certification"
    shutil.copytree(
        certification,
        examples / "certification",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return examples


def _is_transient(returncode: int, stdout: str, stderr: str) -> bool:
    if returncode == 75:
        return True
    combined = f"{stdout}\n{stderr}".lower()
    return returncode not in {0, 2, 3} and any(
        pattern in combined for pattern in TRANSIENT_PATTERNS
    )


def _run_one(
    entry: Notebook,
    python: Path,
    script: Path,
    copied_examples: Path,
    report_dir: Path,
    environment: Dict[str, str],
    mode: str,
) -> Dict[str, Any]:
    source = copied_examples / "notebooks" / entry.path
    output = report_dir / "executed" / entry.path
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(python),
        str(script),
        "--execute-one",
        str(source),
        "--output",
        str(output),
        "--execution-cwd",
        str(copied_examples),
        "--cell-timeout",
        str(entry.timeout),
    ]
    secrets = _secret_values(environment)
    attempts = 0
    started = time.monotonic()
    completed: Optional[subprocess.CompletedProcess[str]] = None
    while attempts < (3 if mode == "live" else 1):
        attempts += 1
        try:
            completed = subprocess.run(
                command,
                cwd=copied_examples,
                env=environment,
                capture_output=True,
                text=True,
                timeout=entry.timeout + 45,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            completed = subprocess.CompletedProcess(
                command,
                75,
                str(exc.stdout or ""),
                str(exc.stderr or "") + "\nNotebook timed out",
            )
        if completed.returncode == 0:
            break
        if mode != "live" or not _is_transient(
            completed.returncode, completed.stdout, completed.stderr
        ):
            break
        time.sleep(min(2**attempts, 4))
    assert completed is not None
    result: Dict[str, Any] = {
        "id": entry.id,
        "path": entry.path.as_posix(),
        "mode": mode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "attempts": attempts,
        "duration_seconds": round(time.monotonic() - started, 3),
        "stdout": sanitize(completed.stdout, secrets),
        "stderr": sanitize(completed.stderr, secrets),
        "providers": list(entry.providers),
        "services": list(entry.services),
    }
    if output.is_file():
        result["executed_notebook"] = {
            "path": output.relative_to(report_dir).as_posix(),
            "sha256": sha256_file(output),
            "size": output.stat().st_size,
        }
    return result


def run_certification(
    manifest: NotebookManifest,
    wheel: Path,
    mode: str,
    report_dir: Path,
    commit_sha: str,
    notebook_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute one manifest mode in a source-isolated environment."""
    selected = [
        item
        for item in manifest.notebooks
        if item.certify
        and item.mode == mode
        and (notebook_id is None or item.id == notebook_id)
    ]
    if not selected:
        raise RuntimeError(f"no certified notebooks selected for mode {mode}")
    report_dir = report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    wheel_hash = sha256_file(wheel)
    with tempfile.TemporaryDirectory(prefix="praval-notebooks-") as temporary:
        workspace = Path(temporary)
        environment = _clean_environment(mode, workspace)
        venv_dir = workspace / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
        python = _python_in_venv(venv_dir)
        extras = {extra for item in selected for extra in item.extras}
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                _install_target(wheel, extras),
                *EXECUTION_DEPENDENCIES,
            ],
            cwd=workspace,
            env=environment,
            check=True,
        )
        package = _installed_info(python, workspace, wheel_hash)
        copied_examples = _copy_execution_inputs(manifest, workspace)
        script = Path(__file__).resolve()
        results = [
            _run_one(
                entry,
                python,
                script,
                copied_examples,
                report_dir,
                environment,
                mode,
            )
            for entry in selected
        ]

    passed = sum(item["status"] == "passed" for item in results)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if passed == len(results) else "failed",
        "mode": mode,
        "commit": commit_sha,
        "wheel": {
            "filename": wheel.name,
            "sha256": wheel_hash,
            "installed_sha256": package["wheel_sha256"],
            "version": package["version"],
            "source_isolated": True,
        },
        "results": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "skipped": 0,
        },
    }
    report_path = report_dir / f"notebook-certification-{mode}.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def _redact_notebook(value: Any, secrets: Sequence[str]) -> Any:
    if isinstance(value, str):
        return sanitize(value, secrets)
    if isinstance(value, list):
        return [_redact_notebook(item, secrets) for item in value]
    if isinstance(value, dict):
        return {key: _redact_notebook(item, secrets) for key, item in value.items()}
    return value


def execute_one(source: Path, output: Path, execution_cwd: Path, timeout: int) -> int:
    """Internal nbclient entry point executed from the clean wheel environment."""
    import nbformat
    from nbclient import NotebookClient

    notebook = nbformat.read(source, as_version=4)
    secrets = _secret_values(os.environ)
    status = 0
    try:
        client = NotebookClient(
            notebook,
            timeout=timeout,
            kernel_name="python3",
            resources={"metadata": {"path": str(execution_cwd)}},
            allow_errors=False,
        )
        client.execute()
    except Exception as exc:  # notebook errors must become sanitized evidence
        print(
            "Notebook execution failed: " + sanitize(str(exc), secrets), file=sys.stderr
        )
        status = 1
    finally:
        redacted = _redact_notebook(dict(notebook), secrets)
        output.parent.mkdir(parents=True, exist_ok=True)
        nbformat.write(nbformat.from_dict(redacted), output)
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--mode", choices=sorted(MODES - {"reference"}))
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--notebook-id")
    parser.add_argument(
        "--commit-sha", default=os.environ.get("GITHUB_SHA", "local-working-tree")
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--execute-one", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--execution-cwd", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--cell-timeout", type=int, help=argparse.SUPPRESS)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.execute_one is not None:
        if (
            args.output is None
            or args.execution_cwd is None
            or args.cell_timeout is None
        ):
            print(
                "internal notebook execution arguments are incomplete", file=sys.stderr
            )
            return 2
        return execute_one(
            args.execute_one, args.output, args.execution_cwd, args.cell_timeout
        )
    try:
        if args.manifest is None:
            raise ValueError("--manifest is required")
        manifest = load_manifest(args.manifest)
        if args.validate_only:
            certified = sum(item.certify for item in manifest.notebooks)
            print(
                f"Notebook manifest valid: {len(manifest.notebooks)} registered, "
                f"{certified} certified"
            )
            return 0
        if args.wheel is None or args.mode is None or args.report_dir is None:
            raise ValueError("--wheel, --mode, and --report-dir are required")
        report = run_certification(
            manifest,
            _find_wheel(args.wheel),
            args.mode,
            args.report_dir,
            args.commit_sha,
            args.notebook_id,
        )
    except (
        NotebookManifestError,
        OSError,
        RuntimeError,
        ValueError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"Notebook certification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report["summary"], sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
