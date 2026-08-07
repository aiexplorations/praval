"""Exact-wheel execution and analysis for paper-validation experiments."""

from __future__ import annotations

import atexit
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import venv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .manifest import Experiment, Registry, load_registry
from .provenance import (
    EXPECTED_COMMIT,
    environment_metadata,
    inspect_wheel,
    redact_text,
    sha256_file,
    stable_json,
)
from .reporting import write_analysis_bundle

VALIDATION_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = VALIDATION_ROOT.parents[1]
DEFAULT_RUNS_ROOT = VALIDATION_ROOT / "results" / "runs"
SAFE_ENVIRONMENT_KEYS = {
    "PATH",
    "LANG",
    "LC_ALL",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    "TMPDIR",
}
MANAGED_SERVICE_ENVIRONMENT = {
    "POSTGRES_HOST": "127.0.0.1",
    "POSTGRES_PORT": "55432",
    "POSTGRES_DB": "praval_paper",
    "POSTGRES_USER": "praval_paper",
    "POSTGRES_PASSWORD": "praval-paper-validation",
    "REDIS_HOST": "127.0.0.1",
    "REDIS_PORT": "56379",
    "MINIO_ENDPOINT": "http://127.0.0.1:59000",
    "MINIO_ACCESS_KEY": "pravalminio",
    "MINIO_SECRET_KEY": "praval-minio-validation",
    "AWS_EC2_METADATA_DISABLED": "true",
    "QDRANT_URL": "http://127.0.0.1:56333",
    "RABBITMQ_URL": "amqp://guest:guest@127.0.0.1:55672/",
    "RABBITMQ_MANAGEMENT_URL": "http://127.0.0.1:55673",
    "OTLP_HTTP_ENDPOINT": "http://127.0.0.1:54318/v1/traces",
}
SERVICE_PROJECT = "praval-paper-validation"
PROTOCOL_VERSION = 2


def _registry() -> Registry:
    return load_registry(
        VALIDATION_ROOT / "claims.toml",
        VALIDATION_ROOT / "experiments.toml",
        repository_root=REPOSITORY_ROOT,
    )


def select_experiments(tier: str) -> List[Experiment]:
    """Return registered experiments for one evidence tier."""
    if tier not in {"offline", "services", "live", "comparative"}:
        raise ValueError(f"unknown evidence tier: {tier}")
    return sorted(
        (
            experiment
            for experiment in _registry().experiments.values()
            if experiment.tier == tier
        ),
        key=lambda experiment: experiment.id,
    )


def _python_in_venv(venv_dir: Path) -> Path:
    candidate = (
        venv_dir / "Scripts" / "python.exe"
        if os.name == "nt"
        else venv_dir / "bin" / "python"
    )
    if not candidate.is_file():
        raise RuntimeError(f"virtual environment has no Python: {candidate}")
    return candidate


def _clean_environment(
    experiments: Sequence[Experiment],
    tier: str,
    source_environment: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    source = source_environment or os.environ
    environment = {
        key: value
        for key, value in source.items()
        if key in SAFE_ENVIRONMENT_KEYS and value
    }
    if tier in {"live", "services", "comparative"}:
        allowed = {
            secret
            for experiment in experiments
            for secret in (experiment.required_secrets + experiment.optional_secrets)
        }
        for name in allowed:
            value = source.get(name)
            if value:
                environment[name] = value
        if tier == "services" and source.get("AWS_EC2_METADATA_DISABLED"):
            environment["AWS_EC2_METADATA_DISABLED"] = source[
                "AWS_EC2_METADATA_DISABLED"
            ]
    environment["PYTHONHASHSEED"] = "0"
    return environment


def _installed_package_info(python: Path) -> Dict[str, Any]:
    code = (
        "import importlib.metadata as m, json, pathlib, praval; "
        "d=m.distribution('praval'); "
        "u=d.read_text('direct_url.json'); "
        "print(json.dumps({'version':praval.__version__,"
        "'metadata_version':d.version,"
        "'path':str(pathlib.Path(praval.__file__).resolve()),"
        "'direct_url':u}))"
    )
    completed = subprocess.run(
        [str(python), "-I", "-c", code],
        cwd=Path(tempfile.gettempdir()),
        env=_clean_environment((), "offline"),
        capture_output=True,
        text=True,
        check=True,
    )
    raw_result = json.loads(completed.stdout)
    if not isinstance(raw_result, dict):
        raise RuntimeError("installed Praval metadata is not an object")
    result: Dict[str, Any] = raw_result
    package_path = Path(result["path"]).resolve()
    if REPOSITORY_ROOT.resolve() in package_path.parents:
        raise RuntimeError(f"Praval imported from source checkout: {package_path}")
    if result["version"] != result["metadata_version"]:
        raise RuntimeError("Praval package and distribution versions differ")
    direct_url = result.get("direct_url")
    installed_sha256 = ""
    if isinstance(direct_url, str) and direct_url:
        try:
            archive_info = json.loads(direct_url).get("archive_info", {})
            hashes = archive_info.get("hashes", {})
            if isinstance(hashes, dict):
                installed_sha256 = str(hashes.get("sha256", ""))
            if not installed_sha256:
                raw_hash = archive_info.get("hash", "")
                if isinstance(raw_hash, str) and raw_hash.startswith("sha256="):
                    installed_sha256 = raw_hash.split("=", 1)[1]
        except (AttributeError, TypeError, ValueError):
            installed_sha256 = ""
    result["installed_sha256"] = installed_sha256
    return result


def _dependency_versions(python: Path) -> List[Dict[str, str]]:
    code = (
        "import importlib.metadata as m,json;"
        "print(json.dumps(sorted([{'name':d.metadata['Name'],'version':d.version}"
        " for d in m.distributions() if d.metadata['Name']],"
        "key=lambda x:x['name'].lower())))"
    )
    completed = subprocess.run(
        [str(python), "-I", "-c", code],
        cwd=Path(tempfile.gettempdir()),
        env=_clean_environment((), "offline"),
        capture_output=True,
        text=True,
        check=True,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, list):
        raise RuntimeError("dependency inventory is not a list")
    return value


def _install_target(wheel: Path, tier: str) -> str:
    extras = {
        "offline": "secure,mcp,pdf,observability",
        "services": "all",
        "live": "secure,mcp,pdf,observability",
        "comparative": "",
    }[tier]
    return f"{wheel.resolve()}[{extras}]" if extras else str(wheel.resolve())


def _new_run_dir(tier: str, output_dir: Optional[Path]) -> Path:
    if output_dir is not None:
        resolved = output_dir.resolve()
        if resolved.exists() and any(resolved.iterdir()):
            raise ValueError(f"output directory must be empty: {resolved}")
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = DEFAULT_RUNS_ROOT / f"{stamp}-{tier}"
    suffix = 1
    while run_dir.exists():
        run_dir = DEFAULT_RUNS_ROOT / f"{stamp}-{tier}-{suffix}"
        suffix += 1
    run_dir.mkdir(parents=True)
    return run_dir


def _missing_requirements(
    experiments: Sequence[Experiment],
    tier: str,
    source_environment: Optional[Mapping[str, str]] = None,
) -> List[str]:
    if tier not in {"live", "services"}:
        return []
    required = {
        name for experiment in experiments for name in experiment.required_secrets
    }
    source = source_environment or os.environ
    return sorted(name for name in required if not source.get(name))


def _compose_command(*arguments: str) -> List[str]:
    return [
        "docker",
        "compose",
        "--project-name",
        SERVICE_PROJECT,
        "--file",
        str(VALIDATION_ROOT / "services.compose.yml"),
        *arguments,
    ]


def _stop_managed_services(run_dir: Path) -> None:
    completed = subprocess.run(
        _compose_command("down", "--volumes", "--remove-orphans"),
        cwd=VALIDATION_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    (run_dir / "services-down.log").write_text(
        completed.stdout + completed.stderr, encoding="utf-8"
    )


def _start_managed_services(run_dir: Path) -> Dict[str, str]:
    completed = subprocess.run(
        _compose_command("up", "--detach", "--wait", "--quiet-pull"),
        cwd=VALIDATION_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    (run_dir / "services-up.log").write_text(
        completed.stdout + completed.stderr, encoding="utf-8"
    )
    if completed.returncode != 0:
        _stop_managed_services(run_dir)
        raise RuntimeError("pinned paper-validation services failed to start")
    deadline = time.monotonic() + 60.0
    pending = {56333, 59000, 54318}
    while pending and time.monotonic() < deadline:
        for port in list(pending):
            with socket.socket() as connection:
                connection.settimeout(0.2)
                if connection.connect_ex(("127.0.0.1", port)) == 0:
                    pending.remove(port)
        if pending:
            time.sleep(0.2)
    if pending:
        _stop_managed_services(run_dir)
        raise RuntimeError(
            "pinned services did not open ports: "
            + ", ".join(str(port) for port in sorted(pending))
        )
    return dict(MANAGED_SERVICE_ENVIRONMENT)


def run_tier(
    *,
    tier: str,
    wheel: Path,
    output_dir: Optional[Path],
    seed: int,
    quick: bool,
) -> Dict[str, Any]:
    """Run one tier against the exact published Praval 0.8.1 wheel."""
    experiments = select_experiments(tier)
    identity = inspect_wheel(wheel)
    run_dir = _new_run_dir(tier, output_dir)
    started = datetime.now(timezone.utc)
    started_monotonic = time.monotonic()
    metadata = environment_metadata(REPOSITORY_ROOT)
    base_report: Dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_dir.name,
        "tier": tier,
        "status": "running",
        "canonical": not quick,
        "seed": seed,
        "protocol": {
            "version": PROTOCOL_VERSION,
            "sha256": sha256_file(VALIDATION_ROOT / "PROTOCOL.md"),
        },
        "started_at": started.isoformat(),
        "run_dir": str(run_dir),
        "wheel": {
            "filename": identity.filename,
            "version": identity.version,
            "sha256": identity.sha256,
            "provenance_commit": EXPECTED_COMMIT,
        },
        "environment": metadata,
        "experiments": [],
    }
    (run_dir / "run.json").write_text(stable_json(base_report), encoding="utf-8")
    if metadata["repository"]["v0.8.1_commit"] != EXPECTED_COMMIT:
        base_report.update(
            {
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "failure": "local v0.8.1 tag does not resolve to the expected commit",
            }
        )
        (run_dir / "run.json").write_text(stable_json(base_report), encoding="utf-8")
        return base_report

    source_environment = dict(os.environ)
    managed_services = False
    if tier == "services" and os.environ.get(
        "PRAVAL_PAPER_USE_EXTERNAL_SERVICES"
    ) not in {"1", "true", "yes"}:
        try:
            source_environment.update(_start_managed_services(run_dir))
            managed_services = True
            atexit.register(_stop_managed_services, run_dir)
            base_report["services"] = {
                "managed": True,
                "compose_file": "research/paper_validation/services.compose.yml",
                "images": sorted(
                    {
                        image
                        for experiment in experiments
                        for image in experiment.services
                    }
                ),
            }
        except RuntimeError as exc:
            base_report.update(
                {
                    "status": "failed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "failure": str(exc),
                }
            )
            (run_dir / "run.json").write_text(
                stable_json(base_report), encoding="utf-8"
            )
            return base_report
    missing = _missing_requirements(experiments, tier, source_environment)
    if missing:
        base_report.update(
            {
                "status": "not_run",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "limitations": [
                    "Required configuration was absent; no experiment was executed."
                ],
                "missing_requirements": missing,
                "experiments": [
                    {
                        "id": experiment.id,
                        "status": "not_run",
                        "reason": "missing required configuration",
                    }
                    for experiment in experiments
                ],
            }
        )
        (run_dir / "run.json").write_text(stable_json(base_report), encoding="utf-8")
        if managed_services:
            _stop_managed_services(run_dir)
            atexit.unregister(_stop_managed_services)
        return base_report

    secret_values = tuple(
        source_environment[name]
        for experiment in experiments
        for name in experiment.required_secrets + experiment.optional_secrets
        if source_environment.get(name)
    )
    with tempfile.TemporaryDirectory(prefix="praval-paper-validation-") as temporary:
        temporary_root = Path(temporary)
        venv_dir = temporary_root / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
        python = _python_in_venv(venv_dir)
        install = subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                _install_target(identity.path, tier),
            ],
            cwd=temporary_root,
            env=_clean_environment(experiments, tier, source_environment),
            capture_output=True,
            text=True,
            check=False,
        )
        (run_dir / "install.log").write_text(
            redact_text(install.stdout + install.stderr, secret_values=secret_values),
            encoding="utf-8",
        )
        if install.returncode != 0:
            base_report.update(
                {
                    "status": "failed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "failure": "exact-wheel dependency installation failed",
                }
            )
            (run_dir / "run.json").write_text(
                stable_json(base_report), encoding="utf-8"
            )
            if managed_services:
                _stop_managed_services(run_dir)
                atexit.unregister(_stop_managed_services)
            return base_report

        installed = _installed_package_info(python)
        if installed["installed_sha256"] != identity.sha256:
            base_report.update(
                {
                    "status": "failed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "failure": (
                        "installed wheel direct-url hash does not match the "
                        "supplied wheel"
                    ),
                }
            )
            (run_dir / "run.json").write_text(
                stable_json(base_report), encoding="utf-8"
            )
            if managed_services:
                _stop_managed_services(run_dir)
                atexit.unregister(_stop_managed_services)
            return base_report
        base_report["wheel"]["installed_version"] = installed["version"]
        base_report["wheel"]["installed_path"] = installed["path"]
        base_report["wheel"]["installed_sha256"] = installed["installed_sha256"]
        base_report["wheel"]["source_isolated"] = True
        base_report["dependencies"] = _dependency_versions(python)
        environment = _clean_environment(experiments, tier, source_environment)
        environment["PYTHONPATH"] = str(REPOSITORY_ROOT)
        environment["PRAVAL_VALIDATION_WHEEL_SHA256"] = identity.sha256
        experiment_results: List[Dict[str, Any]] = []
        worker_failures = False
        for experiment in experiments:
            worker_report_path = run_dir / "worker-report.json"
            worker_report_path.unlink(missing_ok=True)
            command = [
                str(python),
                "-m",
                "research.paper_validation.worker",
                "--tier",
                tier,
                "--output-dir",
                str(run_dir),
                "--seed",
                str(seed),
                "--experiment",
                experiment.id,
            ]
            if quick:
                command.append("--quick")
            stdout = ""
            stderr = ""
            timed_out = False
            try:
                completed = subprocess.run(
                    command,
                    cwd=temporary_root,
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=experiment.timeout_seconds,
                )
                stdout = completed.stdout
                stderr = completed.stderr
                worker_failures = worker_failures or completed.returncode != 0
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                worker_failures = True
                stdout = (
                    exc.stdout.decode("utf-8", errors="replace")
                    if isinstance(exc.stdout, bytes)
                    else exc.stdout or ""
                )
                stderr = (
                    exc.stderr.decode("utf-8", errors="replace")
                    if isinstance(exc.stderr, bytes)
                    else exc.stderr or ""
                )
            (run_dir / f"worker-{experiment.id}.stdout.log").write_text(
                redact_text(stdout, secret_values=secret_values),
                encoding="utf-8",
            )
            (run_dir / f"worker-{experiment.id}.stderr.log").write_text(
                redact_text(stderr, secret_values=secret_values),
                encoding="utf-8",
            )
            if timed_out:
                experiment_results.append(
                    {
                        "id": experiment.id,
                        "scenario": experiment.scenario,
                        "tier": experiment.tier,
                        "status": "failed",
                        "checks": {},
                        "metrics": {},
                        "sample_count": 0,
                        "details": {},
                        "limitations": [
                            "The experiment exceeded its registered timeout."
                        ],
                        "failure": (
                            f"timeout after {experiment.timeout_seconds} seconds"
                        ),
                        "artifacts": {},
                    }
                )
            elif worker_report_path.is_file():
                worker_report = json.loads(
                    worker_report_path.read_text(encoding="utf-8")
                )
                results = worker_report.get("experiments", [])
                if len(results) == 1 and results[0].get("id") == experiment.id:
                    experiment_results.append(results[0])
                else:
                    worker_failures = True
                    experiment_results.append(
                        {
                            "id": experiment.id,
                            "scenario": experiment.scenario,
                            "tier": experiment.tier,
                            "status": "failed",
                            "failure": "worker report did not match experiment",
                            "artifacts": {},
                        }
                    )
            else:
                worker_failures = True
                experiment_results.append(
                    {
                        "id": experiment.id,
                        "scenario": experiment.scenario,
                        "tier": experiment.tier,
                        "status": "failed",
                        "failure": "worker did not produce a report",
                        "artifacts": {},
                    }
                )
        consolidated_worker_report = {
            "schema_version": 1,
            "tier": tier,
            "canonical": not quick,
            "seed": seed,
            "status": "failed" if worker_failures else "passed",
            "experiments": experiment_results,
        }
        (run_dir / "worker-report.json").write_text(
            stable_json(consolidated_worker_report), encoding="utf-8"
        )
        base_report["experiments"] = experiment_results

    base_report["status"] = (
        "passed"
        if base_report["experiments"]
        and all(
            result.get("status") == "passed" for result in base_report["experiments"]
        )
        else "failed"
    )
    base_report["finished_at"] = datetime.now(timezone.utc).isoformat()
    base_report["duration_seconds"] = time.monotonic() - started_monotonic
    (run_dir / "run.json").write_text(stable_json(base_report), encoding="utf-8")
    if managed_services:
        _stop_managed_services(run_dir)
        atexit.unregister(_stop_managed_services)
    return base_report


def _claim_report(run: Mapping[str, Any]) -> Dict[str, Any]:
    registry = _registry()
    results = {
        value["id"]: value
        for value in run.get("experiments", [])
        if isinstance(value, dict) and value.get("id")
    }
    claims: List[Dict[str, Any]] = []
    for claim in registry.claims.values():
        related = [results[name] for name in claim.experiments if name in results]
        if claim.status in {"unsupported", "contradicted", "future_work"}:
            observed = claim.status
        elif related and all(item.get("status") == "passed" for item in related):
            observed = (
                "validated_with_scope"
                if run.get("canonical")
                else "provisional_smoke_result"
            )
        elif any(item.get("status") == "failed" for item in related):
            observed = "unsupported"
        else:
            observed = "not_evaluated"
        claims.append(
            {
                "id": claim.id,
                "declared_status": claim.status,
                "observed_status": observed,
                "experiments": list(claim.experiments),
                "evidence": list(claim.implementation_evidence),
                "citations": list(claim.citations),
                "permitted_wording": claim.permitted_wording,
                "limitations": list(claim.limitations),
            }
        )
    return {"schema_version": 1, "run_id": run.get("run_id"), "claims": claims}


def analyze_run(run_dir: Path) -> Dict[str, Path]:
    """Generate machine-readable and paper-ready summaries for one run."""
    root = run_dir.resolve()
    run_path = root / "run.json"
    if not run_path.is_file():
        raise ValueError(f"run has no run.json: {root}")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    analysis_dir = root / "analysis"
    paths = write_analysis_bundle(run, analysis_dir)
    claim_report = _claim_report(run)
    claim_path = analysis_dir / "claim-report.json"
    claim_path.write_text(stable_json(claim_report), encoding="utf-8")
    paths["claims"] = claim_path
    return paths


def export_paper(
    run_dir: Path, *, output_dir: Optional[Path] = None
) -> Dict[str, Path]:
    """Export generated analysis without hand-copying numeric values."""
    source_paths = analyze_run(run_dir)
    destination = (
        output_dir.resolve() if output_dir is not None else run_dir.resolve() / "paper"
    )
    destination.mkdir(parents=True, exist_ok=True)
    exported: Dict[str, Path] = {}
    for name, source in source_paths.items():
        target = destination / source.name
        shutil.copy2(source, target)
        exported[name] = target
    return exported
