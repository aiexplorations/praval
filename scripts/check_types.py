#!/usr/bin/env python3
"""Run strict current-Python and minimum-Python Praval type checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "src/praval/"

TYPE_CHECKS: Tuple[Tuple[str, Sequence[str]], ...] = (
    (
        "strict Python 3.13 typing",
        ("--python-version", "3.13", SOURCE),
    ),
    (
        "Python 3.9 compatibility typing",
        (
            "--python-version",
            "3.9",
            "--no-site-packages",
            "--ignore-missing-imports",
            "--disable-error-code",
            "import-untyped",
            "--disable-error-code",
            "no-any-return",
            SOURCE,
        ),
    ),
)


def _command(arguments: Sequence[str]) -> List[str]:
    return [sys.executable, "-m", "mypy", "--no-incremental", *arguments]


def main() -> int:
    """Run both fatal typing passes and return the first failure."""
    for label, arguments in TYPE_CHECKS:
        print(f"Running {label}", flush=True)
        result = subprocess.run(_command(arguments), cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
