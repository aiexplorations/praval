"""Audit, validate, and build the maintained Praval 0.8.1 book."""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import tempfile
import venv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .provenance import inspect_wheel
from .references import Reference, write_bibtex

EXAMPLE_MARKER_RE = re.compile(
    r"<!--\s*PRAVAL_BOOK_EXAMPLE\s+"
    r"id=(?P<id>[a-z0-9][a-z0-9-]*)\s+"
    r"mode=(?P<mode>run|compile|display)"
    r'(?:\s+reason="(?P<reason>[^"]+)")?\s*-->'
)
PYTHON_FENCE_RE = re.compile(r"^```(?:python|py)\s*$")
CLOSING_FENCE_RE = re.compile(r"^```\s*$")
PANDOC_CITE_BLOCK_RE = re.compile(r"\[([^\]]*@[^\]]+)\]")
PANDOC_CITE_KEY_RE = re.compile(r"@([A-Za-z0-9_:.+\-/]+)")
MARKDOWN_LINK_RE = re.compile(
    r"!?\[[^\]]*\]\((?P<target><[^>]+>|[^)\s]+)(?:\s+[^)]*)?\)"
)
WARNING_RE = re.compile(r"\bwarning\b|overfull|underfull", re.IGNORECASE)

OBSOLETE_PATTERNS = {
    "PravalLogger": re.compile(r"\bPravalLogger\b"),
    "MetricsCollector": re.compile(r"\bMetricsCollector\b"),
    "TracingContext": re.compile(r"\bTracingContext\b"),
    "praval.resilience": re.compile(r"\bpraval\.resilience\b"),
    "praval.health": re.compile(r"\bpraval\.health\b"),
    "start_agents max_concurrent": re.compile(
        r"start_agents\s*\([^)]*\bmax_concurrent\s*=", re.DOTALL
    ),
    "source-tree path injection": re.compile(
        r"sys\.path\.(?:insert|append)\s*\([^)]*(?:/src|[\"']src[\"'])",
        re.DOTALL,
    ),
}
UNSUPPORTED_CLAIM_PATTERNS = {
    "specialists are always better": re.compile(
        r"\bspecialists? (?:are|is) always better\b", re.IGNORECASE
    ),
    "no central controller": re.compile(
        r"\bno central (?:controller|coordinator)\b", re.IGNORECASE
    ),
    "production-ready": re.compile(r"\bproduction[- ]ready\b", re.IGNORECASE),
    "perfect forward secrecy": re.compile(
        r"\bperfect forward secrecy\b", re.IGNORECASE
    ),
    "horizontal scaling out of the box": re.compile(
        r"\bhorizontal scaling out of the box\b", re.IGNORECASE
    ),
}
LIMITATION_WORDS = re.compile(
    r"\b(?:does not|do not|not supported|unsupported|cannot|no built-in|"
    r"must not|should not|limitation)\b",
    re.IGNORECASE,
)
REQUIRED_BOOK_TEXT = (
    "Building Agent Systems with Praval 0.8.1",
    "Book Edition 1.1",
    "July 2026",
)


@dataclass(frozen=True)
class BookExample:
    """One registered Python block from the book."""

    id: str
    mode: str
    reason: str
    line: int
    source: str


@dataclass(frozen=True)
class BookAudit:
    """Static audit outcome for the Markdown book."""

    status: str
    errors: Tuple[str, ...]
    warnings: Tuple[str, ...]
    examples: Tuple[BookExample, ...]
    citations: Tuple[str, ...]


@dataclass(frozen=True)
class BookValidation:
    """Exact-wheel validation outcome for registered book examples."""

    status: str
    errors: Tuple[str, ...]
    audit: BookAudit
    wheel: Mapping[str, str]
    installed_package: Mapping[str, str]
    examples: Tuple[Mapping[str, Any], ...]


def _citation_keys(source: str) -> Tuple[str, ...]:
    keys = {
        key.group(1)
        for block in PANDOC_CITE_BLOCK_RE.finditer(source)
        for key in PANDOC_CITE_KEY_RE.finditer(block.group(1))
    }
    return tuple(sorted(keys))


def _line_for_offset(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def parse_book_examples(source: str) -> Tuple[Tuple[BookExample, ...], Tuple[str, ...]]:
    """Parse adjacent example markers and Python fences."""
    lines = source.splitlines()
    examples: List[BookExample] = []
    errors: List[str] = []
    used_marker_lines = set()
    marker_lines = {
        index for index, line in enumerate(lines) if "PRAVAL_BOOK_EXAMPLE" in line
    }
    seen_ids = set()
    index = 0
    while index < len(lines):
        if not PYTHON_FENCE_RE.fullmatch(lines[index].strip()):
            index += 1
            continue
        fence_line = index + 1
        marker_index = index - 1
        if marker_index < 0:
            errors.append(f"line {fence_line}: Python block has no adjacent marker")
            marker = None
        else:
            marker = EXAMPLE_MARKER_RE.fullmatch(lines[marker_index].strip())
            if marker is None:
                errors.append(
                    f"line {fence_line}: Python block has no valid adjacent marker"
                )
            else:
                used_marker_lines.add(marker_index)
        closing = index + 1
        while closing < len(lines) and not CLOSING_FENCE_RE.fullmatch(
            lines[closing].strip()
        ):
            closing += 1
        if closing == len(lines):
            errors.append(f"line {fence_line}: Python block is not closed")
            break
        code = "\n".join(lines[index + 1 : closing]) + "\n"
        if marker is not None:
            example_id = marker.group("id")
            mode = marker.group("mode")
            reason = marker.group("reason") or ""
            if example_id in seen_ids:
                errors.append(f"line {fence_line}: duplicate example id: {example_id}")
            seen_ids.add(example_id)
            if mode == "display" and len(reason.strip()) < 10:
                errors.append(
                    f"line {fence_line}: display example {example_id} needs a reason"
                )
            try:
                ast.parse(code, filename=f"<book:{example_id}>")
            except SyntaxError as exc:
                errors.append(
                    f"line {fence_line}: example {example_id} has invalid Python: "
                    f"{exc.msg}"
                )
            examples.append(
                BookExample(
                    id=example_id,
                    mode=mode,
                    reason=reason.strip(),
                    line=fence_line,
                    source=code,
                )
            )
        index = closing + 1
    for marker_line in sorted(marker_lines - used_marker_lines):
        errors.append(
            f"line {marker_line + 1}: example marker is not adjacent to a Python block"
        )
    return tuple(examples), tuple(errors)


def _local_link_errors(book: Path, source: str, repository_root: Path) -> List[str]:
    errors: List[str] = []
    root = repository_root.resolve()
    for match in MARKDOWN_LINK_RE.finditer(source):
        raw_target = match.group("target").strip("<>")
        target = raw_target.split("#", 1)[0]
        if (
            not target
            or target.startswith("#")
            or "://" in target
            or target.startswith("mailto:")
        ):
            continue
        candidate = (book.parent / target).resolve()
        if candidate != root and root not in candidate.parents:
            errors.append(
                f"line {_line_for_offset(source, match.start())}: "
                f"local link leaves the repository: {raw_target}"
            )
        elif not candidate.exists():
            errors.append(
                f"line {_line_for_offset(source, match.start())}: "
                f"local link does not exist: {raw_target}"
            )
    return errors


def audit_book(
    book: Path,
    *,
    repository_root: Path,
    references: Mapping[str, Reference],
) -> BookAudit:
    """Audit book structure, examples, citations, links, and strong claims."""
    resolved = book.resolve()
    if not resolved.is_file():
        raise ValueError(f"book does not exist: {book}")
    source = resolved.read_text(encoding="utf-8")
    examples, parse_errors = parse_book_examples(source)
    errors = list(parse_errors)
    warnings: List[str] = []

    for required in REQUIRED_BOOK_TEXT:
        if required not in source:
            errors.append(f"book is missing required edition text: {required}")

    for label, pattern in OBSOLETE_PATTERNS.items():
        match = pattern.search(source)
        if match is not None:
            errors.append(
                f"line {_line_for_offset(source, match.start())}: "
                f"obsolete book pattern remains: {label}"
            )

    for label, pattern in UNSUPPORTED_CLAIM_PATTERNS.items():
        for match in pattern.finditer(source):
            line_start = source.rfind("\n", 0, match.start()) + 1
            line_end = source.find("\n", match.end())
            line = source[line_start : line_end if line_end >= 0 else len(source)]
            if not LIMITATION_WORDS.search(line):
                errors.append(
                    f"line {_line_for_offset(source, match.start())}: "
                    f"unsupported strong claim remains: {label}"
                )

    version_patterns = (
        re.compile(r"Praval Version:\s*0\.7\.6", re.IGNORECASE),
        re.compile(r"Current Version:\s*0\.7\.6", re.IGNORECASE),
        re.compile(r"Building Agent Systems with Praval 0\.7\.6", re.IGNORECASE),
    )
    for pattern in version_patterns:
        match = pattern.search(source)
        if match is not None:
            errors.append(
                f"line {_line_for_offset(source, match.start())}: "
                "obsolete 0.7.6 edition claim remains"
            )

    errors.extend(_local_link_errors(resolved, source, repository_root))
    citations = _citation_keys(source)
    unresolved = sorted(set(citations) - set(references))
    if unresolved:
        errors.append("unresolved book citation keys: " + ", ".join(unresolved))
    if not citations:
        warnings.append("book has no registered citations")
    if not examples:
        errors.append("book has no registered Python examples")

    return BookAudit(
        status="passed" if not errors else "failed",
        errors=tuple(sorted(set(errors))),
        warnings=tuple(sorted(set(warnings))),
        examples=examples,
        citations=citations,
    )


def audit_to_dict(audit: BookAudit) -> Dict[str, Any]:
    """Return a stable JSON-compatible book audit."""
    return {
        "schema_version": 1,
        "status": audit.status,
        "errors": list(audit.errors),
        "warnings": list(audit.warnings),
        "citations": list(audit.citations),
        "examples": [
            {
                "id": example.id,
                "mode": example.mode,
                "reason": example.reason,
                "line": example.line,
            }
            for example in audit.examples
        ],
    }


def _python_in_venv(venv_dir: Path) -> Path:
    python = (
        venv_dir / "Scripts" / "python.exe"
        if os.name == "nt"
        else venv_dir / "bin" / "python"
    )
    if not python.is_file():
        raise RuntimeError(f"book validation environment has no Python: {python}")
    return python


def _validation_environment() -> Dict[str, str]:
    allowed = {"PATH", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR", "TMPDIR"}
    environment = {
        key: value for key, value in os.environ.items() if key in allowed and value
    }
    environment["PYTHONHASHSEED"] = "0"
    environment["PRAVAL_OBSERVABILITY"] = "off"
    return environment


def _installed_package(python: Path, repository_root: Path) -> Dict[str, str]:
    code = (
        "import importlib.metadata as m,json,pathlib,praval;"
        "print(json.dumps({'version':praval.__version__,"
        "'metadata_version':m.version('praval'),"
        "'path':str(pathlib.Path(praval.__file__).resolve())}))"
    )
    completed = subprocess.run(
        [str(python), "-I", "-c", code],
        cwd=Path(tempfile.gettempdir()),
        env=_validation_environment(),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "could not import installed Praval wheel: " + completed.stderr.strip()
        )
    result = dict(json.loads(completed.stdout))
    package_path = Path(result["path"]).resolve()
    repository = repository_root.resolve()
    if package_path == repository or repository in package_path.parents:
        raise RuntimeError(f"Praval imported from source checkout: {package_path}")
    if result["version"] != "0.8.1" or result["metadata_version"] != "0.8.1":
        raise RuntimeError("installed book-validation package is not Praval 0.8.1")
    return {key: str(value) for key, value in result.items()}


def validate_book(
    book: Path,
    *,
    wheel: Path,
    repository_root: Path,
    references: Mapping[str, Reference],
) -> BookValidation:
    """Validate all registered examples against the exact Praval 0.8.1 wheel."""
    audit = audit_book(
        book,
        repository_root=repository_root,
        references=references,
    )
    identity = inspect_wheel(wheel)
    if audit.status != "passed":
        return BookValidation(
            status="failed",
            errors=audit.errors,
            audit=audit,
            wheel={
                "filename": identity.filename,
                "version": identity.version,
                "sha256": identity.sha256,
            },
            installed_package={},
            examples=(),
        )

    errors: List[str] = []
    outcomes: List[Mapping[str, Any]] = []
    installed: Dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="praval-book-validation-") as temporary:
        temporary_root = Path(temporary)
        venv_dir = temporary_root / "venv"
        venv.EnvBuilder(
            with_pip=True,
            clear=True,
            system_site_packages=True,
        ).create(venv_dir)
        python = _python_in_venv(venv_dir)
        install = subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-deps",
                "--force-reinstall",
                str(identity.path),
            ],
            cwd=temporary_root,
            env=_validation_environment(),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if install.returncode != 0:
            raise RuntimeError(
                "exact wheel installation failed: " + install.stderr.strip()
            )
        installed = _installed_package(python, repository_root)
        scripts_dir = temporary_root / "examples"
        scripts_dir.mkdir()
        for example in audit.examples:
            script = scripts_dir / f"{example.id}.py"
            script.write_text(example.source, encoding="utf-8")
            if example.mode == "run":
                command = [str(python), "-I", str(script)]
            else:
                command = [
                    str(python),
                    "-I",
                    "-m",
                    "py_compile",
                    str(script),
                ]
            completed = subprocess.run(
                command,
                cwd=temporary_root,
                env=_validation_environment(),
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            outcome = {
                "id": example.id,
                "mode": example.mode,
                "status": "passed" if completed.returncode == 0 else "failed",
            }
            outcomes.append(outcome)
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout).strip()
                errors.append(f"example {example.id} failed: {detail}")

    return BookValidation(
        status="passed" if not errors else "failed",
        errors=tuple(errors),
        audit=audit,
        wheel={
            "filename": identity.filename,
            "version": identity.version,
            "sha256": identity.sha256,
        },
        installed_package=installed,
        examples=tuple(outcomes),
    )


def validation_to_dict(validation: BookValidation) -> Dict[str, Any]:
    """Return a stable JSON-compatible exact-wheel validation report."""
    return {
        "schema_version": 1,
        "status": validation.status,
        "errors": list(validation.errors),
        "wheel": dict(validation.wheel),
        "installed_package": dict(validation.installed_package),
        "audit": audit_to_dict(validation.audit),
        "examples": [dict(example) for example in validation.examples],
    }


def build_book(
    book: Path,
    *,
    output: Path,
    repository_root: Path,
    references: Mapping[str, Reference],
    pandoc: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the validated Markdown book with Pandoc and XeLaTeX."""
    audit = audit_book(
        book,
        repository_root=repository_root,
        references=references,
    )
    if audit.status != "passed":
        raise ValueError("book audit failed: " + "; ".join(audit.errors))
    pandoc_binary = pandoc or shutil.which("pandoc")
    if not pandoc_binary:
        raise RuntimeError("pandoc is required to build the book")
    if not shutil.which("xelatex"):
        raise RuntimeError("xelatex is required to build the book")

    destination = output.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="praval-book-build-") as temporary:
        temporary_root = Path(temporary)
        bibliography = write_bibtex(references, temporary_root / "references.bib")
        temporary_pdf = temporary_root / "praval-book.pdf"
        command = [
            pandoc_binary,
            str(book.resolve()),
            "--from",
            "markdown+citations",
            "--standalone",
            "--citeproc",
            "--bibliography",
            str(bibliography),
            "--pdf-engine=xelatex",
            "--toc",
            "--number-sections",
            "--resource-path",
            os.pathsep.join(
                (str(repository_root.resolve()), str(book.resolve().parent))
            ),
            "-V",
            "geometry:margin=0.85in",
            "-V",
            "fontsize=10pt",
            "-V",
            "colorlinks=true",
            "--output",
            str(temporary_pdf),
        ]
        completed = subprocess.run(
            command,
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
        )
        log = completed.stdout + completed.stderr
        if completed.returncode != 0:
            raise RuntimeError("book build failed: " + log.strip())
        warning_lines = [
            line.strip() for line in log.splitlines() if WARNING_RE.search(line)
        ]
        if warning_lines:
            raise RuntimeError(
                "book build emitted warnings: " + " | ".join(warning_lines)
            )
        shutil.copy2(temporary_pdf, destination)
    return {
        "book": str(book.resolve()),
        "output": str(destination),
        "status": "passed",
        "audit": audit_to_dict(audit),
    }
