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
            "from praval.models import ModelResponse, ProviderCapabilities",
        ]
        if extra == "mcp":
            checks.extend(
                [
                    "import mcp",
                    "from praval.mcp import MCPClient, MCPServerConfig",
                ]
            )
        else:
            checks.extend(
                [
                    "import importlib.util",
                    "assert importlib.util.find_spec('mcp') is None",
                ]
            )
        subprocess.run([str(python), "-c", "; ".join(checks)], check=True)
        example = Path(__file__).resolve().parents[1] / "examples"
        subprocess.run(
            [str(python), str(example / "model_runtime_fake_provider.py")], check=True
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist_dir", type=Path)
    parser.add_argument("--extra", default="", choices=("", "mcp"))
    args = parser.parse_args()
    smoke_install(args.dist_dir, args.extra)
    print(f"Clean wheel smoke test passed (extra={args.extra or 'minimal'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
