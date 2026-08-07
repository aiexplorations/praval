"""Artifact identity, environment metadata, and secret redaction."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

EXPECTED_PRAVAL_VERSION = "0.8.1"
EXPECTED_WHEEL_SHA256 = (
    "70b0220a2ced6c0bd066423566c4e1811caa9015b128604d2bc5b3c8d57379c5"
)
EXPECTED_COMMIT = "fa20513e7cc982fd8d94b81c19e55a9427a6f48c"

AUTHORIZATION_RE = re.compile(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+")
SECRET_ASSIGNMENT_RE = re.compile(
    r"\b([A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*)\s*=\s*[^\s,;]+"
)


@dataclass(frozen=True)
class WheelIdentity:
    """Verified identity read from an exact wheel."""

    path: Path
    filename: str
    version: str
    sha256: str


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of one file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_wheel(path: Path) -> WheelIdentity:
    """Verify that a wheel is the published Praval 0.8.1 artifact."""
    resolved = path.resolve()
    if not resolved.is_file() or resolved.suffix != ".whl":
        raise ValueError(f"wheel does not exist: {path}")
    digest = sha256_file(resolved)
    if digest != EXPECTED_WHEEL_SHA256:
        raise ValueError(
            "wheel SHA-256 does not match the published Praval 0.8.1 artifact"
        )
    with zipfile.ZipFile(resolved) as archive:
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ValueError("wheel must contain exactly one METADATA file")
        metadata = Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))
    if metadata.get("Name", "").lower() != "praval":
        raise ValueError("wheel metadata does not identify Praval")
    version = metadata.get("Version", "")
    if version != EXPECTED_PRAVAL_VERSION:
        raise ValueError(
            f"wheel version is {version!r}, expected {EXPECTED_PRAVAL_VERSION}"
        )
    return WheelIdentity(
        path=resolved,
        filename=resolved.name,
        version=version,
        sha256=digest,
    )


def redact_text(text: str, *, secret_values: Iterable[str] = ()) -> str:
    """Redact known secret values and common authorization assignments."""
    redacted = str(text)
    for secret in sorted(
        {value for value in secret_values if value}, key=len, reverse=True
    ):
        redacted = redacted.replace(secret, "[REDACTED]")
    redacted = AUTHORIZATION_RE.sub(r"\1[REDACTED]", redacted)
    redacted = SECRET_ASSIGNMENT_RE.sub(r"\1=[REDACTED]", redacted)
    return redacted


def secret_values_from_environment(
    environment: Mapping[str, str],
) -> Sequence[str]:
    """Return credential-like values without exposing their names or contents."""
    markers = ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH", "CREDENTIAL")
    return tuple(
        value
        for name, value in environment.items()
        if value
        and (
            any(marker in name.upper() for marker in markers)
            or ("://" in value and "@" in value)
        )
    )


def redact_data(value: Any, *, secret_values: Iterable[str] = ()) -> Any:
    """Recursively redact strings before structured evidence is persisted."""
    secrets = tuple(secret_values)
    if isinstance(value, str):
        return redact_text(value, secret_values=secrets)
    if isinstance(value, dict):
        return {
            key: redact_data(item, secret_values=secrets) for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_data(item, secret_values=secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_data(item, secret_values=secrets) for item in value)
    return value


def _run_git(repository_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def environment_metadata(repository_root: Path) -> Dict[str, Any]:
    """Capture reproducibility metadata without reading credential values."""
    try:
        commit = _run_git(repository_root, "rev-parse", "HEAD")
        dirty = bool(_run_git(repository_root, "status", "--porcelain"))
        tag_commit = _run_git(repository_root, "rev-parse", "v0.8.1^{}")
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
        dirty = True
        tag_commit = "unknown"
    return {
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "repository": {
            "commit": commit,
            "dirty": dirty,
            "v0.8.1_commit": tag_commit,
            "expected_v0.8.1_commit": EXPECTED_COMMIT,
        },
    }


def stable_json(value: Any) -> str:
    """Serialize evidence using stable ordering."""
    return json.dumps(value, indent=2, sort_keys=True) + "\n"
