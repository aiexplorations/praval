"""Tests for exact-wheel demo manifest and certification infrastructure."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "manifest.toml"
SPEC = importlib.util.spec_from_file_location(
    "praval_run_demos", ROOT / "scripts" / "run_demos.py"
)
assert SPEC is not None and SPEC.loader is not None
run_demos = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run_demos
SPEC.loader.exec_module(run_demos)

Demo = run_demos.Demo
DemoManifest = run_demos.DemoManifest
ManifestError = run_demos.ManifestError
_artifact_evidence = run_demos._artifact_evidence
_clean_environment = run_demos._clean_environment
_find_wheel = run_demos._find_wheel
_install_target = run_demos._install_target
_run_demo = run_demos._run_demo
_installed_package_info = run_demos._installed_package_info
is_transient_failure = run_demos.is_transient_failure
load_manifest = run_demos.load_manifest
sanitize_text = run_demos.sanitize_text
_provider_matrix = run_demos._provider_matrix


def test_repository_manifest_registers_every_python_example():
    manifest = load_manifest(MANIFEST)

    discovered = {
        path.relative_to(ROOT / "examples").as_posix()
        for path in (ROOT / "examples").rglob("*.py")
        if "__pycache__" not in path.parts
    }
    discovered -= run_demos.NON_DEMO_EXAMPLE_FILES
    assert {demo.path.as_posix() for demo in manifest.demos} == discovered
    assert len(manifest.demos) == 47


def test_every_stable_feature_has_executable_certification():
    manifest = load_manifest(MANIFEST)
    covered = {
        feature
        for demo in manifest.demos
        if demo.execution == "run"
        for feature in demo.features
    }

    assert set(manifest.stable_features) <= covered
    assert {"offline", "services", "live"} == {
        mode for demo in manifest.demos for mode in demo.modes
    }


def test_provider_matrix_contains_manifest_providers_without_secrets():
    manifest = load_manifest(MANIFEST)
    selected = [demo for demo in manifest.demos if "live" in demo.modes]
    matrix = _provider_matrix(
        selected,
        {
            "PRAVAL_OPENAI_MODEL": "gpt-test",
            "OPENAI_API_KEY": "do-not-report",
        },
    )

    assert set(matrix) == {
        "openai",
        "anthropic",
        "cohere",
        "gemini",
        "openai-compatible",
    }
    assert matrix["openai"]["model"] == "gpt-test"
    assert "do-not-report" not in repr(matrix)


def test_manifest_rejects_duplicate_demo_ids(tmp_path):
    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / "one.py").write_text("print('one')\n", encoding="utf-8")
    (examples / "two.py").write_text("print('two')\n", encoding="utf-8")
    manifest = examples / "manifest.toml"
    manifest.write_text(
        """
schema_version = 1
[coverage]
stable_features = ["feature"]
[[demo]]
id = "duplicate"
path = "one.py"
features = ["feature"]
modes = ["offline"]
execution = "run"
[[demo]]
id = "duplicate"
path = "two.py"
features = ["feature"]
modes = ["offline"]
execution = "run"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="duplicate demo id"):
        load_manifest(manifest)


def test_manifest_rejects_stable_feature_without_executable_demo(tmp_path):
    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / "only.py").write_text("print('only')\n", encoding="utf-8")
    manifest = examples / "manifest.toml"
    manifest.write_text(
        """
schema_version = 1
[coverage]
stable_features = ["required"]
[[demo]]
id = "compile-only"
path = "only.py"
features = ["required"]
modes = ["offline"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="without executable certification"):
        load_manifest(manifest)


def test_sanitize_text_redacts_secrets_and_bounds_output():
    secret = "super-secret-value"
    value = f"header {secret} trailer" + ("x" * (70 * 1024))

    sanitized = sanitize_text(value, [secret])

    assert secret not in sanitized
    assert "***" in sanitized
    assert sanitized.endswith("...[output truncated]")


@pytest.mark.parametrize(
    ("returncode", "output", "expected"),
    [
        (75, "", True),
        (1, "HTTP 429 rate limit", True),
        (1, "connection reset", True),
        (2, "missing key", False),
        (3, "assertion", False),
        (1, "invalid schema", False),
    ],
)
def test_transient_failure_classification(returncode, output, expected):
    assert is_transient_failure(returncode, output, "") is expected


def test_clean_offline_environment_removes_provider_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "https://private.example")
    monkeypatch.setenv("PYTHONPATH", "/unsafe/source")

    environment = _clean_environment("offline", tmp_path, ROOT)

    assert "OPENAI_API_KEY" not in environment
    assert "OPENAI_COMPATIBLE_BASE_URL" not in environment
    assert "PYTHONPATH" not in environment
    assert environment["PRAVAL_EXAMPLE_SMOKE"] == "1"
    assert environment["PRAVAL_OBSERVABILITY"] == "off"


def test_install_target_validates_extras(tmp_path):
    wheel = tmp_path / "praval-0.8.0-py3-none-any.whl"

    assert _install_target(wheel, ["mcp", "pdf", "mcp"]).endswith("[mcp,pdf]")
    with pytest.raises(ValueError, match="invalid wheel extra"):
        _install_target(wheel, ["mcp; echo unsafe"])


def test_find_wheel_requires_exactly_one_praval_wheel(tmp_path):
    wheel = tmp_path / "praval-0.8.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    assert _find_wheel(tmp_path) == wheel

    (tmp_path / "praval-0.8.1-py3-none-any.whl").write_bytes(b"wheel")
    with pytest.raises(ValueError, match="expected one Praval wheel"):
        _find_wheel(tmp_path)

    other = tmp_path / "other-0.8.0-py3-none-any.whl"
    other.write_bytes(b"wheel")
    with pytest.raises(ValueError, match="not a Praval wheel"):
        _find_wheel(other)


def test_artifact_evidence_hashes_only_report_owned_files(tmp_path):
    examples = tmp_path / "examples"
    examples.mkdir()
    manifest_path = examples / "manifest.toml"
    manifest_path.write_text("", encoding="utf-8")
    report = tmp_path / "report"
    report.mkdir()
    artifact = report / "evidence.json"
    artifact.write_text('{"ready": true}\n', encoding="utf-8")
    demo = Demo(
        id="artifact",
        path=Path("artifact.py"),
        features=("artifact",),
        modes=("offline",),
        expected_artifacts=("evidence.json",),
    )
    manifest = DemoManifest(manifest_path, ("artifact",), (demo,))

    evidence = _artifact_evidence(demo, manifest, report)

    assert evidence[0]["path"] == "evidence.json"
    assert len(evidence[0]["sha256"]) == 64


def test_manifest_allows_report_dir_artifact_template(tmp_path):
    examples = tmp_path / "examples"
    examples.mkdir()
    manifest_path = examples / "manifest.toml"
    manifest_path.write_text("", encoding="utf-8")
    report = tmp_path / "report"
    report.mkdir()
    artifact = report / "evidence.json"
    artifact.write_text("ready\n", encoding="utf-8")
    demo = Demo(
        id="artifact",
        path=Path("artifact.py"),
        features=("artifact",),
        modes=("offline",),
        expected_artifacts=("{report_dir}/evidence.json",),
    )
    manifest = DemoManifest(manifest_path, ("artifact",), (demo,))

    evidence = _artifact_evidence(demo, manifest, report)

    assert evidence[0]["path"] == "evidence.json"


def test_successful_skip_output_is_a_failure(tmp_path):
    examples = tmp_path / "examples"
    examples.mkdir()
    script = examples / "skip.py"
    script.write_text("print('SKIP: not certified')\n", encoding="utf-8")
    manifest_path = examples / "manifest.toml"
    manifest_path.write_text("", encoding="utf-8")
    demo = Demo(
        id="no-skip",
        path=Path("skip.py"),
        features=("skip",),
        modes=("offline",),
        execution="run",
    )
    manifest = DemoManifest(manifest_path, ("skip",), (demo,))
    work = tmp_path / "work"
    report = tmp_path / "report"
    work.mkdir()
    report.mkdir()

    result = _run_demo(
        demo,
        manifest,
        Path(sys.executable),
        "offline",
        work,
        report,
        _clean_environment("offline", report, tmp_path),
    )

    assert result.status == "failed"
    assert result.returncode == 3
    assert "successful skip" in result.stderr


def test_successful_missing_configuration_output_is_a_failure(tmp_path):
    examples = tmp_path / "examples"
    examples.mkdir()
    script = examples / "missing.py"
    script.write_text(
        "print('Set OPENAI_API_KEY to run this example.')\n", encoding="utf-8"
    )
    manifest_path = examples / "manifest.toml"
    manifest_path.write_text("", encoding="utf-8")
    demo = Demo(
        id="no-missing-config",
        path=Path("missing.py"),
        features=("missing",),
        modes=("offline",),
        execution="run",
    )
    work = tmp_path / "work"
    report = tmp_path / "report"
    work.mkdir()
    report.mkdir()

    result = _run_demo(
        demo,
        DemoManifest(manifest_path, ("missing",), (demo,)),
        Path(sys.executable),
        "offline",
        work,
        report,
        _clean_environment("offline", report, tmp_path),
    )

    assert result.status == "failed"
    assert result.returncode == 3


def test_timeout_is_reported_as_a_sanitized_failure(tmp_path):
    examples = tmp_path / "examples"
    examples.mkdir()
    script = examples / "slow.py"
    script.write_text(
        "import sys, time\nprint('before-timeout', flush=True)\ntime.sleep(2)\n",
        encoding="utf-8",
    )
    manifest_path = examples / "manifest.toml"
    manifest_path.write_text("", encoding="utf-8")
    demo = Demo(
        id="timeout",
        path=Path("slow.py"),
        features=("timeout",),
        modes=("offline",),
        execution="run",
        timeout_seconds=1,
    )
    work = tmp_path / "work"
    report = tmp_path / "report"
    work.mkdir()
    report.mkdir()

    result = _run_demo(
        demo,
        DemoManifest(manifest_path, ("timeout",), (demo,)),
        Path(sys.executable),
        "offline",
        work,
        report,
        _clean_environment("offline", report, tmp_path),
    )

    assert result.status == "failed"
    assert result.returncode == 75
    assert result.failure_reason == "timeout"
    assert "before-timeout" in result.stdout
