#!/usr/bin/env python3
"""Run Praval demo certification against an exact wheel artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
import time
import venv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    import tomllib
except ImportError:  # pragma: no cover - exercised by the Python 3.9 CI job
    import tomli as tomllib  # type: ignore[no-redef]


SCHEMA_VERSION = 1
MODES = {"offline", "services", "live"}
EXECUTIONS = {"compile", "run"}
SECRET_NAME_FRAGMENTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTHORIZATION")
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
REQUIRED_LIVE_SECRETS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "COHERE_API_KEY",
    "GEMINI_API_KEY",
    "OPENAI_COMPATIBLE_BASE_URL",
    "OPENAI_COMPATIBLE_API_KEY",
)
MAX_CAPTURE_CHARS = 64 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
NON_DEMO_EXAMPLE_FILES = {
    "notebooks/__init__.py",
    "notebooks/fixtures/release_candidate/src/ledger.py",
    "notebooks/fixtures/release_candidate/tests/test_ledger.py",
    "notebooks/support.py",
}
# A demo may not report a successful result while declining to run the
# behaviour it claims to certify.  Keep this deliberately narrow: ordinary
# instructional text can mention credentials, but these forms are the
# conventional early-return messages used by examples.
SUCCESSFUL_SKIP_PATTERNS = (
    re.compile(r"(?mi)^\s*SKIP(?:PED)?\s*:"),
    re.compile(r"(?mi)^\s*set\s+.+(?:api[_\s-]*key|token).+\bto\s+run\b"),
    re.compile(
        r"(?mi)^\s*(?:missing|required)\s+.+\b(?:configuration|credential|key)\b"
    ),
)


class ManifestError(ValueError):
    """Raised when the demo manifest violates the certification contract."""


@dataclass(frozen=True)
class Demo:
    """One manifest-backed demo certification entry."""

    id: str
    path: Path
    features: Tuple[str, ...]
    modes: Tuple[str, ...]
    execution: str = "compile"
    extras: Tuple[str, ...] = ()
    providers: Tuple[str, ...] = ()
    services: Tuple[str, ...] = ()
    args: Tuple[str, ...] = ()
    timeout_seconds: int = 45
    expected_artifacts: Tuple[str, ...] = ()
    required_secrets: Tuple[str, ...] = ()


@dataclass(frozen=True)
class DemoManifest:
    """Validated demo manifest."""

    path: Path
    stable_features: Tuple[str, ...]
    demos: Tuple[Demo, ...]

    @property
    def examples_dir(self) -> Path:
        return self.path.parent

    @property
    def repository_root(self) -> Path:
        return self.examples_dir.parent


@dataclass
class DemoResult:
    """Sanitized result for one compiled or executed demo."""

    id: str
    path: str
    mode: str
    execution: str
    status: str
    attempts: int
    duration_seconds: float
    returncode: int
    stdout: str = ""
    stderr: str = ""
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    # Manifest metadata is copied into the report without copying any secret
    # values.  This makes the machine-readable certification self-describing.
    features: Tuple[str, ...] = ()
    providers: Tuple[str, ...] = ()
    services: Tuple[str, ...] = ()
    extras: Tuple[str, ...] = ()
    failure_reason: Optional[str] = None


def _string_tuple(value: Any, field_name: str, demo_id: str) -> Tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ManifestError(f"{demo_id}: {field_name} must be an array of strings")
    return tuple(value)


def _safe_relative_path(value: str, field_name: str, demo_id: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ManifestError(f"{demo_id}: {field_name} must stay inside examples/")
    return path


def load_manifest(path: Path) -> DemoManifest:
    """Load and fully validate a demo manifest."""
    resolved = path.resolve()
    with resolved.open("rb") as handle:
        raw = tomllib.load(handle)
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError(f"schema_version must be {SCHEMA_VERSION}")

    coverage = raw.get("coverage")
    if not isinstance(coverage, dict):
        raise ManifestError("manifest must define [coverage]")
    stable_features = _string_tuple(
        coverage.get("stable_features"), "stable_features", "coverage"
    )
    if not stable_features or len(stable_features) != len(set(stable_features)):
        raise ManifestError("stable_features must be non-empty and unique")

    raw_demos = raw.get("demo")
    if not isinstance(raw_demos, list) or not raw_demos:
        raise ManifestError("manifest must define at least one [[demo]] entry")

    demos: List[Demo] = []
    seen_ids = set()
    seen_paths = set()
    for item in raw_demos:
        if not isinstance(item, dict):
            raise ManifestError("each [[demo]] entry must be a table")
        demo_id = item.get("id")
        path_value = item.get("path")
        if not isinstance(demo_id, str) or not demo_id.strip():
            raise ManifestError("every demo must have a non-empty id")
        if demo_id in seen_ids:
            raise ManifestError(f"duplicate demo id: {demo_id}")
        if not isinstance(path_value, str) or not path_value.endswith(".py"):
            raise ManifestError(f"{demo_id}: path must name a Python file")
        relative_path = _safe_relative_path(path_value, "path", demo_id)
        normalized_path = relative_path.as_posix()
        if normalized_path in seen_paths:
            raise ManifestError(f"duplicate demo path: {normalized_path}")

        features = _string_tuple(item.get("features"), "features", demo_id)
        modes = _string_tuple(item.get("modes"), "modes", demo_id)
        execution = str(item.get("execution", "compile"))
        timeout_seconds = item.get("timeout_seconds", 45)
        if not features:
            raise ManifestError(f"{demo_id}: features must not be empty")
        if not modes or not set(modes).issubset(MODES):
            raise ManifestError(f"{demo_id}: modes must use {sorted(MODES)}")
        if execution not in EXECUTIONS:
            raise ManifestError(f"{demo_id}: execution must use {sorted(EXECUTIONS)}")
        if "live" in modes and execution != "run":
            raise ManifestError(f"{demo_id}: live demos must use execution = 'run'")
        if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
            raise ManifestError(f"{demo_id}: timeout_seconds must be positive")

        for value, field_name in (
            (item.get("expected_artifacts"), "expected_artifacts"),
            (item.get("required_secrets"), "required_secrets"),
        ):
            values = _string_tuple(value, field_name, demo_id)
            for entry in values:
                # Artifact templates may contain runner markers, but must not
                # permit a manifest to escape its report directory.
                if field_name == "expected_artifacts":
                    if "{examples_dir}" in entry or "{repo_root}" in entry:
                        raise ManifestError(
                            f"{demo_id}: expected_artifacts must stay inside report-dir"
                        )
                    candidate = entry.replace("{report_dir}", "")
                    if Path(candidate).is_absolute() or ".." in Path(candidate).parts:
                        raise ManifestError(
                            f"{demo_id}: expected_artifacts must stay inside report-dir"
                        )
                elif not entry.strip():
                    raise ManifestError(f"{demo_id}: required_secrets cannot be empty")

        demo = Demo(
            id=demo_id,
            path=relative_path,
            features=features,
            modes=modes,
            execution=execution,
            extras=_string_tuple(item.get("extras"), "extras", demo_id),
            providers=_string_tuple(item.get("providers"), "providers", demo_id),
            services=_string_tuple(item.get("services"), "services", demo_id),
            args=_string_tuple(item.get("args"), "args", demo_id),
            timeout_seconds=timeout_seconds,
            expected_artifacts=_string_tuple(
                item.get("expected_artifacts"), "expected_artifacts", demo_id
            ),
            required_secrets=_string_tuple(
                item.get("required_secrets"), "required_secrets", demo_id
            ),
        )
        demos.append(demo)
        seen_ids.add(demo_id)
        seen_paths.add(normalized_path)

    manifest = DemoManifest(
        path=resolved,
        stable_features=stable_features,
        demos=tuple(demos),
    )
    validate_manifest_inventory(manifest)
    validate_feature_coverage(manifest)
    return manifest


def validate_manifest_inventory(manifest: DemoManifest) -> None:
    """Require a manifest entry for every Python file under examples/."""
    discovered = {
        path.relative_to(manifest.examples_dir).as_posix()
        for path in manifest.examples_dir.rglob("*.py")
        if "__pycache__" not in path.parts
        and not any(part.startswith(".") for part in path.parts)
        and path.relative_to(manifest.examples_dir).as_posix()
        not in NON_DEMO_EXAMPLE_FILES
    }
    registered = {demo.path.as_posix() for demo in manifest.demos}
    missing = sorted(discovered - registered)
    stale = sorted(registered - discovered)
    if missing or stale:
        details = []
        if missing:
            details.append("unregistered: " + ", ".join(missing))
        if stale:
            details.append("missing files: " + ", ".join(stale))
        raise ManifestError("; ".join(details))


def validate_feature_coverage(manifest: DemoManifest) -> None:
    """Require executable certification evidence for every stable feature."""
    covered = {
        feature
        for demo in manifest.demos
        if demo.execution == "run"
        for feature in demo.features
    }
    missing = sorted(set(manifest.stable_features) - covered)
    if missing:
        raise ManifestError(
            "stable features without executable certification: " + ", ".join(missing)
        )


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _python_in_venv(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _find_wheel(value: Path) -> Path:
    value = value.resolve()
    if (
        value.is_file()
        and value.name.startswith("praval-")
        and value.name.endswith(".whl")
    ):
        return value
    if value.is_dir():
        wheels = sorted(value.glob("praval-*.whl"))
        if len(wheels) == 1:
            return wheels[0]
        raise ValueError(f"expected one Praval wheel in {value}, found {len(wheels)}")
    raise ValueError(f"wheel path does not exist or is not a Praval wheel: {value}")


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
        if not value:
            continue
        if name == "OPENAI_COMPATIBLE_BASE_URL" or any(
            fragment in name.upper() for fragment in SECRET_NAME_FRAGMENTS
        ):
            values.append(value)
    return tuple(sorted(set(values), key=len, reverse=True))


def sanitize_text(value: str, secrets: Iterable[str]) -> str:
    """Redact exact configured secrets and bound captured output size."""
    sanitized = value
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "***")
    if len(sanitized) > MAX_CAPTURE_CHARS:
        return sanitized[:MAX_CAPTURE_CHARS] + "\n...[output truncated]"
    return sanitized


def is_transient_failure(returncode: int, stdout: str, stderr: str) -> bool:
    """Return whether a failed demo is eligible for a bounded retry."""
    if returncode == 75:
        return True
    if returncode in {0, 2, 3}:
        return False
    combined = f"{stdout}\n{stderr}".lower()
    return any(pattern in combined for pattern in TRANSIENT_PATTERNS)


def _clean_environment(mode: str, report_dir: Path, root: Path) -> Dict[str, str]:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONSTARTUP", None)
    environment.pop("PYTHONINSPECT", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PRAVAL_DEMO_MODE"] = mode
    environment["PRAVAL_DEMO_REPORT_DIR"] = str(report_dir)
    environment["PRAVAL_DEMO_REPOSITORY_ROOT"] = str(root)
    environment["PRAVAL_OBSERVABILITY"] = "off"
    if mode != "live":
        for name in REQUIRED_LIVE_SECRETS + ("GOOGLE_API_KEY",):
            environment.pop(name, None)
        environment["PRAVAL_EXAMPLE_SMOKE"] = "1"
    else:
        environment.pop("PRAVAL_EXAMPLE_SMOKE", None)
        environment["PRAVAL_RUN_LIVE_EXAMPLES"] = "1"
        environment["PRAVAL_OBSERVABILITY"] = "on"
        environment["PRAVAL_TRACES_PATH"] = str(report_dir / "live-traces.sqlite3")
        environment["PRAVAL_HITL_DB_PATH"] = str(report_dir / "live-hitl.sqlite3")
    return environment


def _compile_demo(path: Path, pycache_dir: Path) -> None:
    target = pycache_dir / (path.as_posix().replace("/", "_") + "c")
    target.parent.mkdir(parents=True, exist_ok=True)
    py_compile.compile(str(path), cfile=str(target), doraise=True)


def _render_arg(value: str, manifest: DemoManifest, report_dir: Path) -> str:
    replacements = {
        "{examples_dir}": str(manifest.examples_dir),
        "{repo_root}": str(manifest.repository_root),
        "{report_dir}": str(report_dir),
    }
    rendered = value
    for marker, replacement in replacements.items():
        rendered = rendered.replace(marker, replacement)
    return rendered


def _artifact_evidence(
    demo: Demo, manifest: DemoManifest, report_dir: Path
) -> List[Dict[str, Any]]:
    evidence = []
    for artifact in demo.expected_artifacts:
        rendered = Path(_render_arg(artifact, manifest, report_dir))
        if not rendered.is_absolute():
            rendered = report_dir / rendered
        resolved = rendered.resolve()
        if report_dir.resolve() not in resolved.parents:
            raise RuntimeError(f"artifact path escapes report directory: {artifact}")
        if not resolved.is_file() or resolved.stat().st_size <= 0:
            raise RuntimeError(f"required artifact missing or empty: {artifact}")
        evidence.append(
            {
                "path": resolved.relative_to(report_dir.resolve()).as_posix(),
                "sha256": sha256_file(resolved),
                "size": resolved.stat().st_size,
            }
        )
    return evidence


def _run_demo(
    demo: Demo,
    manifest: DemoManifest,
    python: Path,
    mode: str,
    work_dir: Path,
    report_dir: Path,
    environment: Dict[str, str],
) -> DemoResult:
    start = time.monotonic()
    example_path = manifest.examples_dir / demo.path
    if demo.execution == "compile":
        _compile_demo(example_path, work_dir / "pycache")
        return DemoResult(
            id=demo.id,
            path=demo.path.as_posix(),
            mode=mode,
            execution=demo.execution,
            status="passed",
            attempts=1,
            duration_seconds=round(time.monotonic() - start, 3),
            returncode=0,
            features=demo.features,
            providers=demo.providers,
            services=demo.services,
            extras=demo.extras,
        )

    missing_secrets = [
        name for name in demo.required_secrets if not environment.get(name)
    ]
    if missing_secrets:
        reason = "required environment configuration is missing: " + ", ".join(
            missing_secrets
        )
        return DemoResult(
            id=demo.id,
            path=demo.path.as_posix(),
            mode=mode,
            execution=demo.execution,
            status="failed",
            attempts=0,
            duration_seconds=round(time.monotonic() - start, 3),
            returncode=2,
            stderr=reason,
            features=demo.features,
            providers=demo.providers,
            services=demo.services,
            extras=demo.extras,
            failure_reason=reason,
        )

    command = [
        str(python),
        str(example_path),
        *[_render_arg(arg, manifest, report_dir) for arg in demo.args],
    ]
    secrets = _secret_values(environment)
    attempts = 0
    completed: Optional[subprocess.CompletedProcess[str]] = None
    while attempts < 3:
        attempts += 1
        try:
            completed = subprocess.run(
                command,
                cwd=work_dir,
                env=environment,
                capture_output=True,
                text=True,
                timeout=demo.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raw_stdout = exc.stdout or ""
            raw_stderr = exc.stderr or ""
            stdout = (
                raw_stdout.decode("utf-8", errors="replace")
                if isinstance(raw_stdout, bytes)
                else str(raw_stdout)
            )
            stderr = (
                raw_stderr.decode("utf-8", errors="replace")
                if isinstance(raw_stderr, bytes)
                else str(raw_stderr)
            ) + "\nTimed out"
            completed = subprocess.CompletedProcess(command, 75, stdout, stderr)
        if completed.returncode == 0:
            combined_output = f"{completed.stdout}\n{completed.stderr}"
            if any(
                pattern.search(combined_output) for pattern in SUCCESSFUL_SKIP_PATTERNS
            ):
                completed = subprocess.CompletedProcess(
                    command,
                    3,
                    completed.stdout,
                    completed.stderr
                    + "\nRequired demo attempted to report a successful skip.",
                )
            break
        if (
            mode != "live"
            or attempts >= 3
            or not is_transient_failure(
                completed.returncode, completed.stdout, completed.stderr
            )
        ):
            break
        time.sleep(min(2**attempts, 4))

    assert completed is not None
    stdout = sanitize_text(completed.stdout, secrets)
    stderr = sanitize_text(completed.stderr, secrets)
    status = "passed" if completed.returncode == 0 else "failed"
    artifacts: List[Dict[str, Any]] = []
    if status == "passed":
        try:
            artifacts = _artifact_evidence(demo, manifest, report_dir)
        except RuntimeError as exc:
            status = "failed"
            completed = subprocess.CompletedProcess(
                command, 3, completed.stdout, f"{completed.stderr}\n{exc}"
            )
            stderr = sanitize_text(completed.stderr, secrets)
    failure_reason = None
    if status != "passed":
        failure_reason = (
            "timeout"
            if completed.returncode == 75 and "Timed out" in stderr
            else f"demo exited with status {completed.returncode}"
        )
    return DemoResult(
        id=demo.id,
        path=demo.path.as_posix(),
        mode=mode,
        execution=demo.execution,
        status=status,
        attempts=attempts,
        duration_seconds=round(time.monotonic() - start, 3),
        returncode=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        artifacts=artifacts,
        features=demo.features,
        providers=demo.providers,
        services=demo.services,
        extras=demo.extras,
        failure_reason=failure_reason,
    )


def _installed_package_info(
    python: Path, root: Path, expected_wheel_sha256: Optional[str] = None
) -> Dict[str, str]:
    code = (
        "import importlib.metadata, json, pathlib, praval; "
        "dist = importlib.metadata.distribution('praval'); "
        "direct = dist.read_text('direct_url.json'); "
        "print(json.dumps({'version': praval.__version__, "
        "'metadata_version': dist.version, "
        "'path': str(pathlib.Path(praval.__file__).resolve()), "
        "'direct_url': direct}))"
    )
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [str(python), "-I", "-c", code],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    info = json.loads(completed.stdout)
    package_path = Path(info["path"])
    if root.resolve() in package_path.parents:
        raise RuntimeError(f"Praval imported from source checkout: {package_path}")
    if info["version"] != info["metadata_version"]:
        raise RuntimeError(
            "installed praval.__version__ does not match distribution metadata"
        )
    direct_url = info.get("direct_url")
    installed_hash = ""
    if direct_url:
        try:
            direct = json.loads(direct_url)
            archive_info = direct.get("archive_info", {})
            raw_hash = archive_info.get("hash")
            if isinstance(raw_hash, str) and raw_hash.startswith("sha256="):
                installed_hash = raw_hash.split("=", 1)[1]
            elif isinstance(archive_info.get("hashes"), dict):
                installed_hash = str(archive_info["hashes"].get("sha256", ""))
        except (TypeError, ValueError, AttributeError):
            installed_hash = ""
    if expected_wheel_sha256 is not None:
        if not SHA256_RE.fullmatch(installed_hash):
            raise RuntimeError("installed Praval wheel hash is unavailable")
        if installed_hash != expected_wheel_sha256:
            raise RuntimeError(
                "installed Praval wheel SHA-256 does not match supplied wheel"
            )
    return {
        "version": str(info["version"]),
        "path": str(package_path),
        "wheel_sha256": installed_hash,
    }


def _provider_matrix(
    selected: Sequence[Demo], environment: Mapping[str, str]
) -> Dict[str, Any]:
    """Return provider/model evidence without exposing credentials.

    Provider names come from manifest metadata, while model identifiers come
    from the protected ``PRAVAL_<PROVIDER>_MODEL`` variables.  Missing model
    values are represented as ``null`` here; the demo itself remains
    responsible for failing when a live model is not configured.
    """
    providers: Dict[str, Dict[str, Any]] = {}
    for demo in selected:
        for provider in demo.providers:
            item = providers.setdefault(provider, {"demos": [], "model": None})
            if demo.id not in item["demos"]:
                item["demos"].append(demo.id)
            variable = "PRAVAL_" + provider.upper().replace("-", "_") + "_MODEL"
            model = environment.get(variable)
            if model:
                item["model"] = model
    return {name: providers[name] for name in sorted(providers)}


def run_certification(
    manifest: DemoManifest,
    wheel: Path,
    mode: str,
    report_dir: Path,
    commit_sha: str,
) -> Dict[str, Any]:
    """Run one complete certification mode and write its report."""
    selected = [demo for demo in manifest.demos if mode in demo.modes]
    if not selected:
        raise RuntimeError(f"manifest contains no demos for mode {mode}")
    if mode == "live":
        missing = [name for name in REQUIRED_LIVE_SECRETS if not os.getenv(name)]
        if missing:
            raise RuntimeError(
                "live certification configuration is incomplete: " + ", ".join(missing)
            )

    report_dir = report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    wheel_hash = sha256_file(wheel)
    with tempfile.TemporaryDirectory(prefix="praval-demo-") as temporary:
        work_dir = Path(temporary)
        venv_dir = work_dir / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
        python = _python_in_venv(venv_dir)
        extras = {extra for demo in selected for extra in demo.extras}
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                _install_target(wheel, extras),
            ],
            cwd=work_dir,
            check=True,
        )
        package = _installed_package_info(
            python, manifest.repository_root, expected_wheel_sha256=wheel_hash
        )
        if not wheel.name.startswith("praval-"):
            raise RuntimeError(f"not a Praval wheel: {wheel.name}")
        # Wheel versions are the segment between the distribution name and
        # the first compatibility tag.  Praval's 0.8 wheel has no hyphenated
        # version, but using the final three tags keeps this valid for future
        # universal wheels as well.
        wheel_parts = wheel.name[:-4].split("-")
        if len(wheel_parts) < 5:
            raise RuntimeError(f"invalid Praval wheel filename: {wheel.name}")
        wheel_version = wheel_parts[1].replace("_", "-")
        if package["version"] != wheel_version:
            raise RuntimeError(
                f"installed version {package['version']} does not match wheel "
                f"filename version {wheel_version}"
            )
        environment = _clean_environment(mode, report_dir, manifest.repository_root)
        results = [
            _run_demo(
                demo,
                manifest,
                python,
                mode,
                work_dir,
                report_dir,
                environment,
            )
            for demo in selected
        ]

    status = (
        "passed" if all(result.status == "passed" for result in results) else "failed"
    )
    artifact_index: Dict[str, Dict[str, Any]] = {}
    for result in results:
        for artifact in result.artifacts:
            artifact_index[artifact["path"]] = {
                "sha256": artifact["sha256"],
                "size": artifact["size"],
                "demo": result.id,
            }

    report: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": mode,
        "commit": commit_sha,
        "wheel": {
            "filename": wheel.name,
            "sha256": wheel_hash,
            "version": package["version"],
            "installed_sha256": package["wheel_sha256"],
            "installed_version": package["version"],
            "source_isolated": True,
        },
        "models": {
            name: value
            for name, value in sorted(os.environ.items())
            if name.startswith("PRAVAL_") and name.endswith("_MODEL") and value
        },
        "provider_matrix": _provider_matrix(selected, environment),
        "artifacts": artifact_index,
        "results": [result.__dict__ for result in results],
        "summary": {
            "total": len(results),
            "passed": sum(result.status == "passed" for result in results),
            "failed": sum(result.status == "failed" for result in results),
            "skipped": 0,
        },
    }
    report_path = report_dir / f"certification-{mode}.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--mode", choices=sorted(MODES))
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument(
        "--commit-sha", default=os.getenv("GITHUB_SHA", "local-working-tree")
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="validate manifest inventory and feature coverage without running demos",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Validate or execute exact-wheel demo certification."""
    args = build_parser().parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        if args.validate_only:
            print(
                f"Manifest valid: {len(manifest.demos)} demos, "
                f"{len(manifest.stable_features)} stable features"
            )
            return 0
        if args.wheel is None or args.mode is None or args.report_dir is None:
            raise ValueError("--wheel, --mode, and --report-dir are required to run")
        wheel = _find_wheel(args.wheel)
        report = run_certification(
            manifest,
            wheel,
            args.mode,
            args.report_dir,
            args.commit_sha,
        )
    except (
        ManifestError,
        OSError,
        RuntimeError,
        ValueError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"Demo certification failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report["summary"], sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
