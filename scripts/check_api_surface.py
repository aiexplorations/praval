#!/usr/bin/env python3
"""Validate the documented Praval public API surface."""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from typing import Any, Dict, List

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.9/3.10 compatibility
    import tomli as tomllib


def validate_api_surface(root: Path) -> Dict[str, Any]:
    """Return API coverage data or raise ``ValueError`` for an invalid manifest."""
    manifest_path = root / "docs" / "api-surface.toml"
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("docs/api-surface.toml must use schema_version = 1")

    import praval

    documented: List[str] = []
    errors: List[str] = []
    for surface in manifest.get("surfaces", []):
        page = root / "docs" / "sphinx" / str(surface["documentation"])
        if not any(page.with_suffix(suffix).exists() for suffix in (".md", ".rst")):
            errors.append(
                f"surface {surface['name']!r} references missing page "
                f"{surface['documentation']!r}"
            )
        for name in surface.get("exports", []):
            documented.append(str(name))
            if not hasattr(praval, name):
                errors.append(f"documented export praval.{name} does not resolve")

    duplicates = sorted({name for name in documented if documented.count(name) > 1})
    exported = list(praval.__all__)
    missing = sorted(set(exported) - set(documented))
    unexpected = sorted(set(documented) - set(exported))
    if duplicates:
        errors.append("exports assigned to multiple surfaces: " + ", ".join(duplicates))
    if missing:
        errors.append("undocumented exports: " + ", ".join(missing))
    if unexpected:
        errors.append("manifest names not in praval.__all__: " + ", ".join(unexpected))

    submodules = []
    for entry in manifest.get("submodules", []):
        name = str(entry["name"])
        submodules.append(name)
        try:
            importlib.import_module(name)
        except Exception as exc:  # pragma: no cover - error reporting path
            errors.append(f"public submodule {name} failed to import: {exc}")
        page = root / "docs" / "sphinx" / str(entry["documentation"])
        if not any(page.with_suffix(suffix).exists() for suffix in (".md", ".rst")):
            errors.append(
                f"submodule {name!r} references missing page "
                f"{entry['documentation']!r}"
            )

    report: Dict[str, Any] = {
        "schema_version": 1,
        "exported": len(exported),
        "documented": len(set(documented)),
        "coverage_percent": round(100 * len(set(documented)) / len(exported), 2),
        "public_submodules": sorted(submodules),
        "errors": errors,
    }
    if errors:
        raise ValueError("\n".join(errors))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate_api_surface(args.root.resolve())
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
