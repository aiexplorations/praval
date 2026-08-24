"""Executable contracts for the v0.8.3 observability documentation."""

import subprocess
import sys
import tomllib
from pathlib import Path

import praval.observability as observability

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "sphinx" / "observability"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_observability_is_a_top_level_documentation_area():
    required_pages = {
        "index.md",
        "quickstart.md",
        "configuration.md",
        "instrumentation.md",
        "distributed-tracing.md",
        "signals.md",
        "collectors.md",
        "sampling-performance.md",
        "privacy-security.md",
        "local-diagnostics.md",
        "lifecycle-troubleshooting.md",
        "api-migration.md",
    }

    assert {path.name for path in DOCS.glob("*.md")} >= required_pages
    index = _text(ROOT / "docs" / "sphinx" / "index.rst")
    assert "observability/index" in index
    assert "guide/observability" not in index


def test_observability_docs_state_safe_defaults_and_ownership_rules():
    current = "\n".join(_text(path) for path in sorted(DOCS.glob("*.md")))

    required = [
        "disabled by default",
        "metadata-only",
        "host-owned",
        "Praval-owned",
        "HTTP/protobuf",
        "gRPC",
        "W3C Trace Context",
        "one observation per agent or workflow",
        "SQLite",
        "single-process",
        "force_flush",
        "shutdown_observability",
    ]
    for phrase in required:
        assert phrase in current

    forbidden = [
        "Zero Configuration",
        "automatically stored",
        "auto-enabled in dev",
        "when Phase 3 is complete",
        "Coming Next (Phase 4)",
    ]
    for phrase in forbidden:
        assert phrase not in current


def test_observability_tutorial_matrix_is_covered_by_executable_evidence():
    index = _text(DOCS / "index.md")
    expected = {
        "Local development": "tests/observability/test_sqlite_exporter.py",
        "Host-owned SDK": "tests/observability/test_lifecycle.py",
        "Praval-owned SDK": "tests/observability/test_lifecycle.py",
        "Collector": "tests/integration/test_otel_collector.py",
        "Multi-container": "tests/integration/test_otel_collector.py",
        "RabbitMQ": "tests/integration/test_rabbitmq_trace_propagation.py",
        "Privacy": "tests/observability/test_privacy.py",
        "Failure isolation": "tests/observability/test_health.py",
        "Shutdown": "tests/observability/test_lifecycle.py",
    }

    for tutorial, evidence in expected.items():
        assert tutorial in index
        assert evidence in index
        assert (ROOT / evidence).exists()


def test_legacy_observability_pages_point_to_the_canonical_area():
    for relative in (
        Path("docs/observability/README.md"),
        Path("docs/observability/quickstart.md"),
    ):
        text = _text(ROOT / relative)
        assert "docs/sphinx/observability/index.md" in text
        assert "automatically stored" not in text
        assert "Zero Configuration" not in text


def test_observability_public_api_inventory_matches_the_runtime_exactly():
    manifest = tomllib.loads(_text(ROOT / "docs" / "api-surface.toml"))
    entry = next(
        item
        for item in manifest["submodules"]
        if item["name"] == "praval.observability"
    )

    assert set(entry["exports"]) == set(observability.__all__)
    assert len(entry["exports"]) == len(set(entry["exports"]))


def test_observability_examples_execute_with_the_managed_extra(tmp_path):
    examples = ROOT / "examples" / "observability"
    cases = [
        (
            "000_quickstart.py",
            ["--db", str(tmp_path / "telemetry.db")],
            "spans=1",
        ),
        ("001_host_owned_sdk.py", [], "owned_signals=[]"),
        ("002_configuration.py", [], "protocol=http/protobuf"),
        ("003_reef_context.py", [], "parentage=ok"),
    ]

    for filename, arguments, marker in cases:
        result = subprocess.run(
            [sys.executable, str(examples / filename), *arguments],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert marker in result.stdout


def test_observability_examples_are_privacy_safe_and_use_public_setup():
    text = "\n".join(
        _text(path)
        for path in sorted((ROOT / "examples" / "observability").glob("*.py"))
    )

    assert "configure_observability" in text
    assert "sys.path.insert" not in text
    assert 'PRAVAL_CAPTURE_CONTENT": "false' in text
    for unsafe in ("sk-", "Bearer ", "capture_content=True"):
        assert unsafe not in text

    wheel_smoke = _text(ROOT / "scripts" / "smoke_install.py")
    for filename in (
        "000_quickstart.py",
        "001_host_owned_sdk.py",
        "002_configuration.py",
        "003_reef_context.py",
    ):
        assert filename in wheel_smoke
