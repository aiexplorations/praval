"""Contracts that keep public documentation aligned with the package."""

import ast
import importlib.util
import inspect
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.9/3.10 compatibility
    import tomli as tomllib

import praval
from praval import Agent, DataManager, ModelRuntime, PravalApp, StorageRegistry

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"praval_docs_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


api_surface = _load_script("check_api_surface")
release_metadata = _load_script("check_release_metadata")
docs_builder = _load_script("build_exact_wheel_docs")


def _local_markdown_links(text):
    repository_prefix = "https://github.com/aiexplorations/praval/blob/main/"
    for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
        target = target.strip().split(maxsplit=1)[0]
        if target.startswith(repository_prefix):
            target = target[len(repository_prefix) :]
        elif target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        yield unquote(target.split("#", maxsplit=1)[0])


def _assert_repository_links_resolve(text):
    for target in _local_markdown_links(text):
        path = Path(target)
        assert not path.is_absolute(), f"absolute repository link: {target}"
        assert (ROOT / path).exists(), f"missing repository link: {target}"


def test_every_top_level_export_is_classified_and_documented():
    report = api_surface.validate_api_surface(ROOT)

    assert report["exported"] == 88
    assert report["documented"] == 88
    assert report["coverage_percent"] == 100.0
    assert report["errors"] == []


def test_feature_claims_reference_real_evidence():
    manifest = tomllib.loads((ROOT / "docs/feature-claims.toml").read_text())

    assert manifest["schema_version"] == 1
    claim_ids = [claim["id"] for claim in manifest["claims"]]
    assert len(claim_ids) == len(set(claim_ids))
    for claim in manifest["claims"]:
        assert claim["statement"].endswith(".")
        for evidence in claim["evidence"]:
            assert (ROOT / evidence).exists(), f"missing evidence: {evidence}"


def test_documented_key_signatures_match_the_runtime():
    assert list(inspect.signature(Agent).parameters)[:3] == [
        "name",
        "provider",
        "model",
    ]
    assert "hitl_enabled" in inspect.signature(Agent).parameters
    assert "async_only" in inspect.signature(Agent.add_tool_spec).parameters
    assert inspect.iscoroutinefunction(DataManager.store)
    assert inspect.iscoroutinefunction(DataManager.get)
    assert inspect.iscoroutinefunction(DataManager.query)
    assert inspect.iscoroutinefunction(DataManager.delete)
    assert inspect.iscoroutinefunction(StorageRegistry.register_provider)
    assert hasattr(ModelRuntime, "invoke") and hasattr(ModelRuntime, "ainvoke")
    assert "use_global_reef" in inspect.signature(PravalApp).parameters


def test_readme_python_blocks_compile():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```python\n(.*?)```", readme, flags=re.DOTALL)

    assert len(blocks) >= 3
    for index, block in enumerate(blocks):
        ast.parse(block, filename=f"README.md:python-block-{index}")


def test_readme_has_layered_navigation_and_resolving_links():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    headings = [
        "## Choose where to start",
        "## How the pieces fit",
        "## Install",
        "## Check your installation",
        "## Quick start: call a model",
        "## Quick start: connect agents through Reef",
        "## Capability map",
        "## Learning center",
        "### Visual course",
        "### Capstones",
        "### Runnable examples",
        "## Documentation map",
        "## Important boundaries",
        "## Development and release validation",
    ]

    positions = [readme.index(heading) for heading in headings]
    assert positions == sorted(positions)
    _assert_repository_links_resolve(readme)
    assert "Why the 0.8 line starts at 0.8.1" in readme
    assert "praval doctor --json" in readme
    assert "Version 0.8.1 is the first supported" in readme


def test_release_changelog_is_substantial_and_linked():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    start = changelog.index("## [0.8.1] - 2026-07-18")
    end = changelog.index("## [0.7.22]", start)
    section = changelog[start:end]
    headings = [
        "### Release overview",
        "### Highlights",
        "### Added",
        "### Changed",
        "### Fixed",
        "### Compatibility",
        "### Migration guidance",
        "### Learning resources",
        "### Validation and publication",
        "### Known limitations",
        "### Deferred",
    ]

    positions = [section.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert "README.md#learning-center" in section
    assert "examples/notebooks/README.md" in section
    assert "docs/sphinx/guide/demo-certification.md" in section
    assert not re.search(r"\b\d{3,5} passed\b", section)
    assert not re.search(r"\b\d{2}\.\d{2}%\b", section)
    _assert_repository_links_resolve(section)


def test_current_docs_reject_known_false_or_private_examples():
    current = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "docs/sphinx").rglob("*"))
        if path.is_file() and path.suffix in {".md", ".rst"}
    )

    forbidden = [
        "from praval import configure",
        "from praval.providers import get_provider",
        "dm.register_provider(",
        "dm.retrieve(",
        "._praval_agent",
        "## Coming Soon",
        "external Reef (Redis",
    ]
    for value in forbidden:
        assert value not in current


def test_release_metadata_has_one_authoritative_version():
    assert release_metadata.validate(ROOT) == []
    assert release_metadata.project_version(ROOT) == praval.__version__


def test_documentation_sanitizer_and_tree_hash(tmp_path):
    site = tmp_path / "site"
    (site / ".doctrees").mkdir(parents=True)
    (site / ".doctrees/state").write_text("cache")
    (site / "index.html").write_text("<h1>Praval</h1>")
    (site / ".buildinfo.bak").write_text("backup")
    (site / ".buildinfo").write_text("generated")
    (site / ".nojekyll").write_text("")

    docs_builder.sanitize_site(site)
    first = docs_builder.tree_sha256(site)
    second = docs_builder.tree_sha256(site)

    assert first == second
    assert not (site / ".doctrees").exists()
    assert not (site / ".buildinfo.bak").exists()
    assert not (site / ".buildinfo").exists()
    assert not (site / ".nojekyll").exists()
    assert len(first) == 64


def test_release_notes_delegate_volatile_values_to_evidence():
    notes = (ROOT / "docs/releases/RELEASE_NOTES_0.8.1.md").read_text()

    assert notes.splitlines()[0] == "# Praval 0.8.1"
    assert "Why there is no supported 0.8.0" in notes
    assert not re.search(r"\b\d{3,5} passed\b", notes)
    assert not re.search(r"\b\d{2}\.\d{2}%\b", notes)
    assert "build-manifest.json" in notes
    assert "documentation manifest" in notes.lower()


def test_dist_policy_is_documented_as_distributions_only():
    release = (ROOT / "RELEASE.md").read_text()

    assert "`dist/` contains exactly one `.whl` file" in release
    assert "`evidence/` contains checksums" in release
    assert "twine upload dist/praval-0.8.1-py3-none-any.whl" in release
    assert "Do not use a wildcard" in release


def test_api_surface_report_is_json_serializable():
    report = api_surface.validate_api_surface(ROOT)
    assert json.loads(json.dumps(report))["coverage_percent"] == 100.0
