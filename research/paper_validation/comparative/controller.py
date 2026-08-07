"""Install pinned frameworks and run the common JSONL comparison schedule."""

from __future__ import annotations

import json
import os
import random
import selectors
import socket
import subprocess
import sys
import tempfile
import time
import uuid
import venv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, TextIO, Tuple

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]

from ..provenance import redact_text, sha256_file, stable_json
from .proxy import load_dataset

COMPARATIVE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = COMPARATIVE_ROOT.parents[2]
FRAMEWORK_ORDER = ("praval", "langgraph", "crewai")


@dataclass(frozen=True)
class FrameworkSpec:
    """One exact framework artifact and version contract."""

    name: str
    distribution: str
    version: str
    source: str
    wheel_sha256: str
    lock: str
    lock_sha256: str
    python: str


@dataclass
class AdapterProcess:
    """One persistent framework adapter and its captured streams."""

    name: str
    process: subprocess.Popen[str]
    stderr_handle: TextIO
    noise_handle: TextIO
    ready: Mapping[str, Any]
    process_ready_seconds: float


def _load_specs() -> Dict[str, FrameworkSpec]:
    with (COMPARATIVE_ROOT / "frameworks.toml").open("rb") as handle:
        raw = tomllib.load(handle)
    if raw.get("schema_version") != 1:
        raise ValueError("frameworks.toml schema_version must be 1")
    values: Dict[str, FrameworkSpec] = {}
    for name, item in raw.get("framework", {}).items():
        values[name] = FrameworkSpec(
            name=name,
            distribution=str(item["distribution"]),
            version=str(item["version"]),
            source=str(item["source"]),
            wheel_sha256=str(item["wheel_sha256"]),
            lock=str(item["lock"]),
            lock_sha256=str(item["lock_sha256"]),
            python=str(item["python"]),
        )
    if set(values) != set(FRAMEWORK_ORDER):
        raise ValueError("framework manifest must pin Praval, LangGraph, and CrewAI")
    for spec in values.values():
        lock_path = (COMPARATIVE_ROOT / spec.lock).resolve()
        if COMPARATIVE_ROOT not in lock_path.parents or not lock_path.is_file():
            raise ValueError(f"{spec.name} lock path is unsafe or absent")
        if sha256_file(lock_path) != spec.lock_sha256:
            raise ValueError(f"{spec.name} lock hash does not match the manifest")
    return values


def _python_in_venv(root: Path) -> Path:
    path = root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not path.is_file():
        raise RuntimeError(f"framework environment has no Python: {path}")
    return path


def _run_logged(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    log_path: Path,
    timeout: int,
    secret_values: Sequence[str],
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        env=dict(environment),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        redact_text(
            completed.stdout + completed.stderr,
            secret_values=secret_values,
        ),
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"command failed; see {log_path.name}")
    return completed


def _base_environment() -> Dict[str, str]:
    allowed = {
        "PATH",
        "LANG",
        "LC_ALL",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "TMPDIR",
    }
    environment = {
        key: value for key, value in os.environ.items() if key in allowed and value
    }
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "CREWAI_DISABLE_TELEMETRY": "true",
            "OTEL_SDK_DISABLED": "true",
        }
    )
    return environment


def _prepare_framework_environment(
    spec: FrameworkSpec,
    *,
    root: Path,
    output_dir: Path,
    secret_values: Sequence[str],
) -> Tuple[Path, Dict[str, Any]]:
    environment_root = root / spec.name
    venv.EnvBuilder(with_pip=True, clear=True).create(environment_root)
    python = _python_in_venv(environment_root)
    download_root = root / "downloads" / spec.name
    download_root.mkdir(parents=True)
    environment = _base_environment()
    if spec.source == "pypi":
        _run_logged(
            [
                str(python),
                "-m",
                "pip",
                "download",
                "--disable-pip-version-check",
                "--only-binary=:all:",
                "--no-deps",
                "--dest",
                str(download_root),
                f"{spec.distribution}=={spec.version}",
            ],
            cwd=root,
            environment=environment,
            log_path=output_dir / "install" / f"{spec.name}-download.log",
            timeout=600,
            secret_values=secret_values,
        )
        wheels = list(download_root.glob("*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"{spec.name} did not resolve to exactly one wheel")
        wheel = wheels[0]
    else:
        wheel = (REPOSITORY_ROOT / spec.source).resolve()
    observed_hash = sha256_file(wheel)
    if observed_hash != spec.wheel_sha256:
        raise RuntimeError(
            f"{spec.name} wheel hash {observed_hash} does not match the manifest"
        )
    constraint_path = (COMPARATIVE_ROOT / spec.lock).resolve()
    _run_logged(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--constraint",
            str(constraint_path),
            str(wheel),
        ],
        cwd=root,
        environment=environment,
        log_path=output_dir / "install" / f"{spec.name}-install.log",
        timeout=1800,
        secret_values=secret_values,
    )
    version_check = _run_logged(
        [
            str(python),
            "-I",
            "-c",
            (
                "import importlib.metadata as m; "
                f"print(m.version({spec.distribution!r}))"
            ),
        ],
        cwd=root,
        environment=environment,
        log_path=output_dir / "install" / f"{spec.name}-version.log",
        timeout=60,
        secret_values=secret_values,
    ).stdout.strip()
    if version_check != spec.version:
        raise RuntimeError(
            f"{spec.name} installed {version_check}, expected {spec.version}"
        )
    freeze = _run_logged(
        [str(python), "-m", "pip", "freeze", "--all"],
        cwd=root,
        environment=environment,
        log_path=output_dir / "locks" / f"{spec.name}.txt",
        timeout=120,
        secret_values=secret_values,
    ).stdout
    lock_path = output_dir / "locks" / f"{spec.name}.txt"
    lock_path.write_text(freeze, encoding="utf-8")
    observed_versions = {
        line.split("==", 1)[0].strip().casefold(): line.split("==", 1)[1].strip()
        for line in freeze.splitlines()
        if "==" in line
    }
    required_versions = {
        line.split("==", 1)[0].strip().casefold(): line.split("==", 1)[1].strip()
        for line in constraint_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "==" in line
    }
    drift = {
        name: {
            "expected": version,
            "observed": observed_versions.get(name),
        }
        for name, version in required_versions.items()
        if observed_versions.get(name) != version
    }
    if drift:
        raise RuntimeError(
            f"{spec.name} installed dependencies differ from its frozen lock"
        )
    return python, {
        "distribution": spec.distribution,
        "version": spec.version,
        "wheel": wheel.name,
        "wheel_sha256": observed_hash,
        "frozen_constraint": spec.lock,
        "frozen_constraint_sha256": spec.lock_sha256,
        "observed_lock_path": str(lock_path.relative_to(output_dir)),
        "observed_lock_sha256": sha256_file(lock_path),
        "frozen_dependencies_verified": True,
    }


def _free_port() -> int:
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return int(connection.getsockname()[1])


def _wait_for_path(path: Path, process: subprocess.Popen[str], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            return
        if process.poll() is not None:
            raise RuntimeError("comparison proxy exited before becoming ready")
        time.sleep(0.05)
    raise TimeoutError("comparison proxy did not become ready")


def _start_proxy(
    *,
    mode: str,
    output_dir: Path,
    token: str,
    delay_seconds: float,
    environment: Mapping[str, str],
) -> Tuple[subprocess.Popen[str], str]:
    port = _free_port()
    ready_path = output_dir / f"{mode}-proxy-ready.json"
    events_path = output_dir / f"{mode}-proxy-events.jsonl"
    proxy_environment = dict(environment)
    proxy_environment["PYTHONPATH"] = str(REPOSITORY_ROOT)
    proxy_environment["PRAVAL_COMPARISON_PROXY_TOKEN"] = token
    if os.environ.get("OPENAI_API_KEY"):
        proxy_environment["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]
    if os.environ.get("PRAVAL_COMPARISON_OPENAI_MODEL"):
        proxy_environment["PRAVAL_COMPARISON_OPENAI_MODEL"] = os.environ[
            "PRAVAL_COMPARISON_OPENAI_MODEL"
        ]
    if os.environ.get("OPENAI_BASE_URL"):
        proxy_environment["OPENAI_BASE_URL"] = os.environ["OPENAI_BASE_URL"]
    stderr_path = output_dir / f"{mode}-proxy.stderr.log"
    stderr_handle = stderr_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "research.paper_validation.comparative.proxy",
            "--dataset",
            str(COMPARATIVE_ROOT / "dataset.jsonl"),
            "--events",
            str(events_path),
            "--ready-file",
            str(ready_path),
            "--port",
            str(port),
            "--mode",
            mode,
            "--delay-seconds",
            str(delay_seconds),
        ],
        cwd=REPOSITORY_ROOT,
        env=proxy_environment,
        stdout=subprocess.DEVNULL,
        stderr=stderr_handle,
        text=True,
    )
    setattr(process, "_praval_stderr_handle", stderr_handle)
    _wait_for_path(ready_path, process, 30)
    return process, f"http://127.0.0.1:{port}"


def _read_event(
    adapter: AdapterProcess,
    *,
    expected_event: str,
    timeout: float,
) -> Mapping[str, Any]:
    if adapter.process.stdout is None:
        raise RuntimeError(f"{adapter.name} adapter has no stdout")
    selector = selectors.DefaultSelector()
    selector.register(adapter.process.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            events = selector.select(max(0.01, deadline - time.monotonic()))
            if not events:
                continue
            line = adapter.process.stdout.readline()
            if not line:
                raise RuntimeError(f"{adapter.name} adapter closed stdout")
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                adapter.noise_handle.write(line)
                adapter.noise_handle.flush()
                continue
            if not isinstance(value, dict):
                adapter.noise_handle.write(line)
                adapter.noise_handle.flush()
                continue
            if value.get("event") == expected_event:
                return value
            adapter.noise_handle.write(line)
            adapter.noise_handle.flush()
        raise TimeoutError(
            f"{adapter.name} adapter did not emit {expected_event} in time"
        )
    finally:
        selector.close()


def _start_adapter(
    *,
    name: str,
    python: Path,
    proxy_url: str,
    token: str,
    output_dir: Path,
) -> AdapterProcess:
    environment = _base_environment()
    environment.update(
        {
            "PYTHONPATH": str(REPOSITORY_ROOT),
            "PRAVAL_COMPARISON_PROXY_URL": proxy_url,
            "PRAVAL_COMPARISON_PROXY_TOKEN": token,
        }
    )
    stderr_handle = (output_dir / f"{name}.stderr.log").open("w", encoding="utf-8")
    noise_handle = (output_dir / f"{name}.stdout-noise.log").open("w", encoding="utf-8")
    started = time.perf_counter_ns()
    process = subprocess.Popen(
        [
            str(python),
            "-m",
            "research.paper_validation.comparative.adapter",
            "--framework",
            name,
        ],
        cwd=Path(tempfile.gettempdir()),
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr_handle,
        text=True,
        bufsize=1,
    )
    placeholder = AdapterProcess(
        name=name,
        process=process,
        stderr_handle=stderr_handle,
        noise_handle=noise_handle,
        ready={},
        process_ready_seconds=0.0,
    )
    ready = _read_event(placeholder, expected_event="ready", timeout=180)
    placeholder.ready = ready
    placeholder.process_ready_seconds = (
        time.perf_counter_ns() - started
    ) / 1_000_000_000
    return placeholder


def _send_run(
    adapter: AdapterProcess,
    *,
    request_id: str,
    item: Mapping[str, Any],
) -> Mapping[str, Any]:
    if adapter.process.stdin is None:
        raise RuntimeError(f"{adapter.name} adapter has no stdin")
    adapter.process.stdin.write(
        json.dumps(
            {"action": "run", "request_id": request_id, "item": item},
            sort_keys=True,
        )
        + "\n"
    )
    adapter.process.stdin.flush()
    result = _read_event(adapter, expected_event="result", timeout=600)
    if result.get("request_id") != request_id:
        raise RuntimeError(f"{adapter.name} returned an out-of-order result")
    return result


def _stop_adapters(adapters: Mapping[str, AdapterProcess]) -> None:
    for adapter in adapters.values():
        if adapter.process.stdin is not None and adapter.process.poll() is None:
            try:
                adapter.process.stdin.write('{"action":"shutdown"}\n')
                adapter.process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
    for adapter in adapters.values():
        try:
            adapter.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            adapter.process.terminate()
            try:
                adapter.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                adapter.process.kill()
                adapter.process.wait(timeout=10)
        adapter.stderr_handle.close()
        adapter.noise_handle.close()


def _stop_proxy(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    handle = getattr(process, "_praval_stderr_handle", None)
    if handle is not None:
        handle.close()


def _normalized_text(value: Any) -> str:
    return " ".join(str(value).casefold().split())


def score_output(output: Any, expected: Mapping[str, Any]) -> Mapping[str, Any]:
    """Score exact facts and numerical values without a model judge."""
    if not isinstance(output, dict):
        return {
            "correct": False,
            "answer": False,
            "facts": False,
            "numbers": False,
        }
    answer_ok = _normalized_text(output.get("answer", "")) == _normalized_text(
        expected["answer"]
    )
    observed_facts = {
        _normalized_text(value)
        for value in output.get("facts", [])
        if isinstance(value, str)
    }
    expected_facts = {_normalized_text(value) for value in expected["facts"]}
    facts_ok = expected_facts <= observed_facts
    observed_numbers = [
        float(value)
        for value in output.get("numbers", [])
        if isinstance(value, (int, float))
    ]
    numbers_ok = all(
        any(abs(float(wanted) - observed) <= 1e-9 for observed in observed_numbers)
        for wanted in expected["numbers"]
    )
    return {
        "correct": answer_ok and facts_ok and numbers_ok,
        "answer": answer_ok,
        "facts": facts_ok,
        "numbers": numbers_ok,
    }


def _framework_rotation(offset: int) -> Sequence[str]:
    amount = offset % len(FRAMEWORK_ORDER)
    return FRAMEWORK_ORDER[amount:] + FRAMEWORK_ORDER[:amount]


def _run_track(
    *,
    track: str,
    pythons: Mapping[str, Path],
    dataset: Mapping[str, Mapping[str, Any]],
    output_dir: Path,
    seed: int,
    repetitions: int,
    warmups: int,
    delay_seconds: float,
) -> Mapping[str, Any]:
    token = uuid.uuid4().hex
    environment = _base_environment()
    proxy, proxy_url = _start_proxy(
        mode=track,
        output_dir=output_dir,
        token=token,
        delay_seconds=delay_seconds,
        environment=environment,
    )
    adapters: Dict[str, AdapterProcess] = {}
    rows: List[Dict[str, Any]] = []
    try:
        for framework in FRAMEWORK_ORDER:
            adapters[framework] = _start_adapter(
                name=framework,
                python=pythons[framework],
                proxy_url=proxy_url,
                token=token,
                output_dir=output_dir,
            )
        question_ids = sorted(dataset)
        phases: List[Tuple[str, int, int]] = [
            ("warmup", index, -1) for index in range(warmups)
        ] + [("measured", repetition, repetition) for repetition in range(repetitions)]
        for phase_index, (phase, phase_repetition, measured_repetition) in enumerate(
            phases
        ):
            ordered_questions = list(question_ids)
            random.Random(seed + phase_index * 1009).shuffle(ordered_questions)
            for question_index, question_id in enumerate(ordered_questions):
                item = dataset[question_id]
                frameworks = _framework_rotation(phase_index + question_index)
                for order_index, framework in enumerate(frameworks):
                    request_id = (
                        f"{track}:{phase}:{phase_repetition}:"
                        f"{question_id}:{framework}"
                    )
                    result = dict(
                        _send_run(
                            adapters[framework],
                            request_id=request_id,
                            item=item,
                        )
                    )
                    score = score_output(result.get("output"), item["expected"])
                    result.update(
                        {
                            "track": track,
                            "phase": phase,
                            "repetition": measured_repetition,
                            "question_id": question_id,
                            "framework_order": order_index,
                            "score": score,
                        }
                    )
                    rows.append(result)
        setup = {
            name: {
                **dict(adapter.ready),
                "process_ready_seconds": adapter.process_ready_seconds,
            }
            for name, adapter in adapters.items()
        }
    finally:
        _stop_adapters(adapters)
        _stop_proxy(proxy)
    return {"track": track, "setup": setup, "rows": rows}


def _samples_from_tracks(tracks: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    samples: List[Dict[str, Any]] = []
    for track in tracks:
        track_name = str(track["track"])
        for framework, setup in track["setup"].items():
            for field in ("setup_seconds", "process_ready_seconds"):
                samples.append(
                    {
                        "metric": f"comparison_{track_name}_{framework}_{field}",
                        "value": float(setup[field]),
                        "track": track_name,
                        "framework": framework,
                        "phase": "cold_start",
                    }
                )
        for row in track["rows"]:
            if row.get("status") != "passed":
                continue
            framework = str(row["framework"])
            phase = str(row["phase"])
            elapsed = float(row["elapsed_seconds"])
            model = float(row["model_seconds"])
            service = float(row["service_seconds"])
            base = {
                "track": track_name,
                "framework": framework,
                "phase": phase,
                "question_id": row["question_id"],
                "repetition": row["repetition"],
                "framework_order": row["framework_order"],
            }
            for metric, value in (
                ("elapsed_seconds", elapsed),
                ("model_seconds", model),
                ("framework_client_seconds", max(0.0, elapsed - service)),
                ("proxy_overhead_seconds", max(0.0, service - model)),
                ("correct", 1.0 if row["score"]["correct"] else 0.0),
                ("model_calls", float(row["model_calls"])),
                (
                    "input_tokens",
                    float(row.get("usage", {}).get("input_tokens", 0)),
                ),
                (
                    "output_tokens",
                    float(row.get("usage", {}).get("output_tokens", 0)),
                ),
            ):
                samples.append(
                    {
                        **base,
                        "metric": (
                            f"comparison_{track_name}_{framework}_{phase}_{metric}"
                        ),
                        "value": value,
                    }
                )
    return samples


def run_comparison(
    *,
    output_dir: Path,
    repetitions: int,
    warmups: int,
    seed: int,
    quick: bool,
) -> Mapping[str, Any]:
    """Run deterministic and optional live tracks in isolated environments."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset = load_dataset(COMPARATIVE_ROOT / "dataset.jsonl")
    specs = _load_specs()
    secret_values = tuple(
        value
        for name, value in os.environ.items()
        if value and any(marker in name for marker in ("KEY", "TOKEN", "SECRET"))
    )
    effective_repetitions = 1 if quick else repetitions
    effective_warmups = 1 if quick else warmups
    framework_metadata: Dict[str, Any] = {}
    tracks: List[Mapping[str, Any]] = []
    with tempfile.TemporaryDirectory(
        prefix="praval-comparison-environments-"
    ) as temporary:
        environment_root = Path(temporary)
        pythons: Dict[str, Path] = {}
        for framework in FRAMEWORK_ORDER:
            python, metadata = _prepare_framework_environment(
                specs[framework],
                root=environment_root,
                output_dir=output_dir,
                secret_values=secret_values,
            )
            pythons[framework] = python
            framework_metadata[framework] = metadata
        tracks.append(
            _run_track(
                track="delayed",
                pythons=pythons,
                dataset=dataset,
                output_dir=output_dir,
                seed=seed,
                repetitions=effective_repetitions,
                warmups=effective_warmups,
                delay_seconds=0.01 if quick else 0.05,
            )
        )
        live_configured = bool(
            os.environ.get("OPENAI_API_KEY")
            and os.environ.get("PRAVAL_COMPARISON_OPENAI_MODEL")
        )
        if live_configured and not quick:
            tracks.append(
                _run_track(
                    track="live",
                    pythons=pythons,
                    dataset=dataset,
                    output_dir=output_dir,
                    seed=seed,
                    repetitions=effective_repetitions,
                    warmups=effective_warmups,
                    delay_seconds=0.0,
                )
            )

    dependency_manifest = {
        "schema_version": 1,
        "python": sys.version.split()[0],
        "frameworks": framework_metadata,
    }
    dependency_path = (
        output_dir / "controlled-framework-comparison.dependency-locks.json"
    )
    dependency_path.write_text(stable_json(dependency_manifest), encoding="utf-8")
    combined_events = output_dir / "controlled-framework-comparison.proxy-events.jsonl"
    with combined_events.open("w", encoding="utf-8") as target:
        for track_name in ("delayed", "live"):
            source = output_dir / f"{track_name}-proxy-events.jsonl"
            if not source.is_file():
                continue
            for line in source.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    value = json.loads(line)
                    value["track"] = track_name
                    target.write(json.dumps(value, sort_keys=True) + "\n")

    rows = [row for track in tracks for row in track.get("rows", [])]
    delayed_rows = [row for row in rows if row["track"] == "delayed"]
    measured_delayed = [row for row in delayed_rows if row["phase"] == "measured"]
    expected_measured = 12 * len(FRAMEWORK_ORDER) * effective_repetitions
    checks = {
        "twelve_question_dataset": len(dataset) == 12,
        "exact_framework_versions": all(
            metadata["version"] == specs[name].version
            for name, metadata in framework_metadata.items()
        ),
        "exact_framework_wheel_hashes": all(
            metadata["wheel_sha256"] == specs[name].wheel_sha256
            for name, metadata in framework_metadata.items()
        ),
        "isolated_dependency_locks": all(
            metadata["frozen_dependencies_verified"] is True
            and metadata["frozen_constraint_sha256"] == specs[name].lock_sha256
            for name, metadata in framework_metadata.items()
        )
        and len(
            {
                metadata["observed_lock_sha256"]
                for metadata in framework_metadata.values()
            }
        )
        == len(FRAMEWORK_ORDER),
        "measured_schedule_complete": len(measured_delayed) == expected_measured,
        "two_model_calls_per_workflow": all(
            row.get("model_calls") == 2
            for row in measured_delayed
            if row.get("status") == "passed"
        ),
        "deterministic_outputs_correct": all(
            row.get("status") == "passed"
            and row.get("score", {}).get("correct") is True
            for row in measured_delayed
        ),
        "framework_order_counterbalanced": all(
            {
                row["framework_order"]
                for row in measured_delayed
                if row["framework"] == name
            }
            == {0, 1, 2}
            for name in FRAMEWORK_ORDER
        ),
    }
    limitations = [
        "The delayed-model track isolates coordination overhead and does not "
        "measure model quality.",
        "Framework adapters use an explicit two-stage workflow and do not "
        "represent every idiomatic application design.",
        "Timing results apply only to the recorded host, Python, dependency "
        "locks, and configured proxy delay.",
    ]
    if not any(track["track"] == "live" for track in tracks):
        limitations.append(
            "The optional live OpenAI track was not run because its key/model "
            "configuration was absent or this was a quick smoke run."
        )
    return {
        "checks": checks,
        "samples": _samples_from_tracks(tracks),
        "details": {
            "frameworks": framework_metadata,
            "tracks": tracks,
            "dataset_sha256": sha256_file(COMPARATIVE_ROOT / "dataset.jsonl"),
            "dependency_manifest_sha256": sha256_file(dependency_path),
            "proxy_events_sha256": sha256_file(combined_events),
        },
        "limitations": limitations,
    }
