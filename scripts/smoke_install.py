#!/usr/bin/env python3
"""Install a built wheel in a clean environment and run offline smoke checks."""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
import venv
from pathlib import Path
from typing import List


def _venv_python(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def smoke_install(dist_dir: Path, extra: str = "") -> None:
    wheels = sorted(dist_dir.glob("praval-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one Praval wheel, found {len(wheels)}")
    wheel_requirement = str(wheels[0].resolve())
    if extra:
        wheel_requirement = f"{wheel_requirement}[{extra}]"

    with tempfile.TemporaryDirectory(prefix="praval-smoke-") as temp_dir:
        environment = Path(temp_dir) / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _venv_python(environment)
        subprocess.run(
            [str(python), "-m", "pip", "install", wheel_requirement], check=True
        )
        checks: List[str] = [
            "import importlib.metadata",
            "import praval",
            "assert praval.__version__ == importlib.metadata.version('praval')",
            "from praval.model_runtime import ModelRuntime",
            "from praval.models import ExecutionObservation, ModelResponse",
            "from praval.models import NOOP_OBSERVATION_RECORDER",
            "from praval.models import ProviderCapabilities",
            "from praval.eval import EvalRunner, EvaluationStore, Gate",
            "from praval.eval import ExactMatchMetric, ModelJudge",
            "from opentelemetry.trace import SpanKind as OTelSpanKind",
            "from praval.observability import SpanKind",
            "assert SpanKind is OTelSpanKind",
        ]
        if extra == "mcp":
            checks.extend(
                [
                    "import mcp",
                    "from praval.mcp import MCPClient, MCPServerConfig",
                ]
            )
        elif extra == "observability":
            checks.extend(
                [
                    "import opentelemetry.sdk",
                    "import opentelemetry.exporter.otlp.proto.http",
                    "import opentelemetry.exporter.otlp.proto.grpc",
                    "from praval.observability import configure_observability",
                    "from praval.observability import force_flush, get_logger",
                    "from praval.observability import get_meter, get_tracer",
                    "from praval.observability import shutdown_observability",
                    "handle = configure_observability(service_name='wheel-smoke')",
                    "assert handle.owned_signals == {'traces', 'metrics', 'logs'}",
                    "assert force_flush(500)",
                    "assert shutdown_observability(500)",
                ]
            )
        elif extra == "eval-ragas":
            checks.extend(
                [
                    "import ragas",
                    "from praval.eval import discover_metric_plugins",
                    "from praval.eval.ragas import PravalRagasEmbeddings",
                    "from praval.eval.ragas import PravalRagasLLM",
                    "from praval.eval.ragas import create_ragas_metrics",
                ]
            )
        else:
            checks.extend(
                [
                    "import importlib.util",
                    "assert importlib.util.find_spec('mcp') is None",
                    "assert importlib.util.find_spec('opentelemetry.sdk') is None",
                    "assert importlib.util.find_spec('ragas') is None",
                    "from praval.observability import get_logger, get_meter",
                    "from praval.observability import get_tracer",
                    "span = get_tracer().start_span('wheel-no-sdk')",
                    "assert not span.is_recording()",
                ]
            )
        subprocess.run([str(python), "-c", "; ".join(checks)], check=True)
        subprocess.run([str(python), "-m", "praval.cli", "eval", "--help"], check=True)
        example = Path(__file__).resolve().parents[1] / "examples"
        if extra == "observability":
            observability_examples = example / "observability"
            cases = (
                (
                    "000_quickstart.py",
                    "--db",
                    str(Path(temp_dir) / "telemetry.db"),
                ),
                ("001_host_owned_sdk.py",),
                ("002_configuration.py",),
                ("003_reef_context.py",),
            )
            for case in cases:
                subprocess.run(
                    [str(python), str(observability_examples / case[0]), *case[1:]],
                    cwd=temp_dir,
                    check=True,
                )
        elif extra == "eval-ragas":
            subprocess.run(
                [
                    str(python),
                    str(Path(__file__).resolve().parent / "smoke_eval_ragas.py"),
                ],
                cwd=temp_dir,
                check=True,
            )
        elif not extra:
            evaluation_examples = example / "evaluation"
            for filename, database in (
                ("000_quickstart.py", "evaluation-quickstart.db"),
                ("001_paired_agents.py", "evaluation-paired-agents.db"),
                ("002_workflow_evaluation.py", "evaluation-workflow.db"),
            ):
                subprocess.run(
                    [
                        str(python),
                        str(evaluation_examples / filename),
                        "--db",
                        str(Path(temp_dir) / database),
                    ],
                    cwd=temp_dir,
                    check=True,
                )
        subprocess.run(
            [str(python), str(example / "model_runtime_fake_provider.py")], check=True
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist_dir", type=Path)
    parser.add_argument(
        "--extra",
        default="",
        choices=("", "mcp", "observability", "eval-ragas"),
    )
    args = parser.parse_args()
    smoke_install(args.dist_dir, args.extra)
    print(f"Clean wheel smoke test passed (extra={args.extra or 'minimal'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
