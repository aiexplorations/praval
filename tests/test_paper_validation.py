"""Tests for the Praval paper validation research harness."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from research.paper_validation.analysis import bootstrap_mean_ci, describe_samples
from research.paper_validation.audit import audit_paper
from research.paper_validation.book import (
    audit_book,
    parse_book_examples,
    validate_book,
)
from research.paper_validation.cli import build_parser
from research.paper_validation.comparative.adapter import _load_praval
from research.paper_validation.comparative.controller import (
    _load_specs,
    score_output,
)
from research.paper_validation.comparative.proxy import (
    ComparisonServer,
    load_dataset,
)
from research.paper_validation.curation import curate_runs
from research.paper_validation.evidence import (
    claim_evidence_report,
    metric_evidence_report,
    write_evidence_bundle,
)
from research.paper_validation.feature_audit import (
    audit_feature_diff,
    feature_diff_summary,
)
from research.paper_validation.manifest import (
    ManifestError,
    load_feature_inventory,
    load_history,
    load_registry,
)
from research.paper_validation.paper import (
    PROTECTED_INTRODUCTION,
    expand_evidence_includes,
    protected_introduction_is_present,
)
from research.paper_validation.paper_artifacts import ERA_DESCRIPTIONS
from research.paper_validation.probes import _max_rss_kib
from research.paper_validation.provenance import (
    EXPECTED_PRAVAL_VERSION,
    EXPECTED_WHEEL_SHA256,
    inspect_wheel,
    redact_data,
    redact_text,
    secret_values_from_environment,
)
from research.paper_validation.references import (
    load_references,
    references_to_bibtex,
    validate_claim_citations,
)
from research.paper_validation.reporting import write_analysis_bundle
from research.paper_validation.runner import select_experiments
from research.paper_validation.scenarios import run_scenario


def _write_manifests(
    root: Path,
    *,
    claim_experiments: str = '["runtime-contracts"]',
    evidence: str = '["src/praval/model_runtime.py"]',
    duplicate_claim: bool = False,
) -> tuple[Path, Path]:
    claims = root / "claims.toml"
    experiments = root / "experiments.toml"
    duplicate = (
        """
[[claim]]
id = "runtime-contract"
statement = "Duplicate."
category = "behavioral"
scope = "Duplicate."
paper_sections = ["Architecture"]
status = "proposed"
implementation_evidence = ["src/praval/model_runtime.py"]
citations = []
experiments = ["runtime-contracts"]
acceptance_rule = "Duplicate."
permitted_wording = "Duplicate."
limitations = []
"""
        if duplicate_claim
        else ""
    )
    claims.write_text(
        f"""
schema_version = 1

[[claim]]
id = "runtime-contract"
statement = "The runtime returns provider-neutral response objects."
category = "behavioral"
scope = "Supported provider profiles in Praval 0.8.1."
paper_sections = ["Architecture"]
status = "proposed"
implementation_evidence = {evidence}
citations = []
experiments = {claim_experiments}
acceptance_rule = "All common response invariants pass."
permitted_wording = "Praval normalizes supported provider responses."
limitations = ["Provider and model capability support still varies."]
{duplicate}
""",
        encoding="utf-8",
    )
    experiments.write_text(
        """
schema_version = 1

[[experiment]]
id = "runtime-contracts"
title = "Runtime contract conformance"
tier = "offline"
scenario = "runtime_contracts"
claim_ids = ["runtime-contract"]
repetitions = 3
warmups = 1
timeout_seconds = 60
fixtures = []
services = []
required_secrets = []
optional_secrets = []
expected_artifacts = ["runtime-contracts.json"]
validity_checks = ["Every request returns one final response."]
""",
        encoding="utf-8",
    )
    return claims, experiments


def test_registry_loads_linked_claims_and_experiments(tmp_path: Path) -> None:
    claims, experiments = _write_manifests(tmp_path)

    registry = load_registry(claims, experiments, repository_root=Path.cwd())

    assert registry.claims["runtime-contract"].status == "proposed"
    assert registry.claims["runtime-contract"].book_sections == ()
    assert registry.experiments["runtime-contracts"].tier == "offline"


def test_registry_loads_optional_book_sections(tmp_path: Path) -> None:
    claims, experiments = _write_manifests(tmp_path)
    source = claims.read_text(encoding="utf-8")
    claims.write_text(
        source.replace(
            'paper_sections = ["Architecture"]',
            'paper_sections = ["Architecture"]\n'
            'book_sections = ["Provider-neutral execution"]',
            1,
        ),
        encoding="utf-8",
    )

    registry = load_registry(claims, experiments, repository_root=Path.cwd())

    assert registry.claims["runtime-contract"].book_sections == (
        "Provider-neutral execution",
    )


def _write_test_book(
    root: Path,
    *,
    block: str,
    extra: str = "",
) -> Path:
    book = root / "book.md"
    book.write_text(
        """---
title: "Praval: Building Agent Systems with Praval 0.8.1"
subtitle: "Building Agent Systems with Praval 0.8.1"
date: "July 2026"
---

Book Edition 1.1

# Introduction

This reference covers the exact Praval release [@praval_pypi_0_8_1].

"""
        + block
        + "\n"
        + extra,
        encoding="utf-8",
    )
    return book


def test_book_examples_require_adjacent_unique_markers() -> None:
    source = """<!-- PRAVAL_BOOK_EXAMPLE id=first mode=run -->
```python
import praval
```

```python
print("missing")
```

<!-- PRAVAL_BOOK_EXAMPLE id=first mode=compile -->
```python
x = 1
```
"""

    examples, errors = parse_book_examples(source)

    assert [example.id for example in examples] == ["first", "first"]
    assert any("no valid adjacent marker" in error for error in errors)
    assert any("duplicate example id" in error for error in errors)


def test_book_display_examples_require_a_reason() -> None:
    source = """<!-- PRAVAL_BOOK_EXAMPLE id=partial mode=display -->
```python
value = ...
```
"""

    _, errors = parse_book_examples(source)

    assert errors == ("line 2: display example partial needs a reason",)


def test_book_audit_rejects_obsolete_apis_links_and_strong_claims(
    tmp_path: Path,
) -> None:
    book = _write_test_book(
        tmp_path,
        block="""<!-- PRAVAL_BOOK_EXAMPLE id=first mode=compile -->
```python
from praval.observability import PravalLogger
```
""",
        extra=("Praval is production-ready.\n\n" "[Missing local file](missing.md)\n"),
    )
    references = load_references(Path("research/paper_validation/references.toml"))

    audit = audit_book(
        book,
        repository_root=tmp_path,
        references=references,
    )

    assert audit.status == "failed"
    assert any("PravalLogger" in error for error in audit.errors)
    assert any("production-ready" in error for error in audit.errors)
    assert any("local link does not exist" in error for error in audit.errors)


def test_book_audit_allows_explicit_security_limitations(tmp_path: Path) -> None:
    book = _write_test_book(
        tmp_path,
        block="""<!-- PRAVAL_BOOK_EXAMPLE id=first mode=compile -->
```python
from praval import Agent
```
""",
        extra=(
            "Praval does not claim perfect forward secrecy, and this limitation "
            "must be handled by a deployment protocol.\n"
        ),
    )
    references = load_references(Path("research/paper_validation/references.toml"))

    audit = audit_book(
        book,
        repository_root=tmp_path,
        references=references,
    )

    assert audit.status == "passed"


def test_book_validation_runs_registered_example_against_exact_wheel(
    tmp_path: Path,
) -> None:
    wheel = Path("dist/praval-0.8.1-py3-none-any.whl")
    if not wheel.exists():
        pytest.skip("the exact 0.8.1 wheel is not present")
    book = _write_test_book(
        tmp_path,
        block="""<!-- PRAVAL_BOOK_EXAMPLE id=wheel-identity mode=run -->
```python
import praval

assert praval.__version__ == "0.8.1"
```
""",
    )
    references = load_references(Path("research/paper_validation/references.toml"))

    validation = validate_book(
        book,
        wheel=wheel,
        repository_root=Path.cwd(),
        references=references,
    )

    assert validation.status == "passed"
    assert validation.installed_package["version"] == "0.8.1"
    assert Path(validation.installed_package["path"]).resolve() != Path.cwd()
    assert validation.examples == (
        {"id": "wheel-identity", "mode": "run", "status": "passed"},
    )


def test_repository_manifests_cover_the_0_8_1_research_scope() -> None:
    root = Path.cwd()
    validation_root = root / "research" / "paper_validation"

    features = load_feature_inventory(
        validation_root / "features.toml", repository_root=root
    )
    registry = load_registry(
        validation_root / "claims.toml",
        validation_root / "experiments.toml",
        repository_root=root,
    )
    references = load_references(validation_root / "references.toml")
    history = load_history(validation_root / "history.toml", repository_root=root)
    validate_claim_citations(registry.claims, references)

    assert len(features) >= 25
    assert {"stable", "optional", "experimental", "unsupported"} <= {
        feature.classification for feature in features.values()
    }
    assert len(registry.claims) >= 12
    assert len(registry.experiments) >= 13
    assert len(references) >= 20
    assert len(history) >= 30
    assert {
        "bonabeau1999_swarm_intelligence",
        "hewitt1973actor",
        "hatcher1997_coral_systems",
        "kennedy_eberhart1995_pso",
        "kirkpatrick1983_simulated_annealing",
        "mcp_spec_2025_11_25",
        "nacl2012",
        "praval_release_0_7_22",
        "praval_blog_0_8_1_2026",
        "praval_blog_architecture_2025",
        "rajeshrs_praval_0_8_1_2026",
        "rajeshrs_praval_analytics_2025",
        "praval_source_history",
        "sampathkumar2010_wing_optimization",
    } <= set(references)
    assert {
        "intellectual-origins",
        "first-party-development-accounts",
        "runtime-provider-neutral-contract",
        "reef-choreography-scope",
        "secure-spore-bounded-claim",
        "historical-comparison-not-evidence",
        "pre-0-8-coordination-foundation",
        "praval-0-7-22-hitl-boundary",
        "praval-0-8-1-execution-transition",
        "initial-agent-coordination-foundation",
        "memory-data-transport-expansion",
        "coordination-operations-maturity",
    } <= set(registry.claims)
    assert history["0.8.0"].status == "withdrawn"
    assert history["0.8.1"].status == "supported"
    assert history["1.0.0"].status == "excluded_transient_state"
    assert set(ERA_DESCRIPTIONS) == {
        entry.era
        for entry in history.values()
        if entry.status != "excluded_transient_state"
    }
    assert ERA_DESCRIPTIONS["Provider-neutral execution transition"][0] == "0.8.1"


def test_history_rejects_impossible_chronology(tmp_path: Path) -> None:
    history = tmp_path / "history.toml"
    history.write_text(
        """
schema_version = 1

[[version]]
version = "0.1.0"
status = "development"
date = "2026-01-02"
commit = "1111111111111111111111111111111111111111"
tag = ""
era = "Initial"
summary = "Initial source state."
motivation = "Start the framework."
evidence = ["pyproject.toml"]
successor = "0.2.0"
notes = []

[[version]]
version = "0.2.0"
status = "supported"
date = "2026-01-01"
commit = "2222222222222222222222222222222222222222"
tag = "v0.2.0"
era = "Initial"
summary = "Supported source state."
motivation = "Publish the framework."
evidence = ["pyproject.toml"]
successor = ""
notes = []
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="chronological order"):
        load_history(history, repository_root=Path.cwd())


def test_feature_inventory_is_mapped_to_the_release_diff() -> None:
    root = Path.cwd()
    features = load_feature_inventory(
        root / "research" / "paper_validation" / "features.toml",
        repository_root=root,
    )

    result = audit_feature_diff(root, features)

    assert result["status"] == "passed"
    assert result["comparison"] == "v0.7.22..v0.8.1"
    assert result["release_commit_matches_expected"] is True
    assert result["changed_file_count"] >= 300
    assert result["commit_count"] >= 40
    assert "src/praval/model_runtime.py" in result["mapped_public_sources"]
    assert (
        "model-runtime"
        in result["mapped_public_sources"]["src/praval/model_runtime.py"]
    )
    summary = feature_diff_summary(result)
    assert "Capability inventory" in summary
    assert "Unmatched changed implementation files" in summary


def test_reference_registry_rejects_unresolved_claim_citation(
    tmp_path: Path,
) -> None:
    claims, experiments = _write_manifests(tmp_path)
    registry = load_registry(claims, experiments, repository_root=Path.cwd())
    claim = registry.claims["runtime-contract"]
    altered = claim.__class__(
        **{
            **claim.__dict__,
            "citations": ("missing-reference",),
        }
    )

    with pytest.raises(ManifestError, match="unknown citation"):
        validate_claim_citations({"runtime-contract": altered}, {})


def test_reference_registry_exports_deterministic_bibtex() -> None:
    references = load_references(Path("research/paper_validation/references.toml"))

    first = references_to_bibtex(references)
    second = references_to_bibtex(references)

    assert first == second
    assert "@inproceedings{hewitt1973actor" in first
    assert "urldate" in first


def test_registry_rejects_duplicate_claim_ids(tmp_path: Path) -> None:
    claims, experiments = _write_manifests(tmp_path, duplicate_claim=True)

    with pytest.raises(ManifestError, match="duplicate claim id"):
        load_registry(claims, experiments, repository_root=Path.cwd())


def test_registry_rejects_unknown_experiment_links(tmp_path: Path) -> None:
    claims, experiments = _write_manifests(
        tmp_path, claim_experiments='["missing-experiment"]'
    )

    with pytest.raises(ManifestError, match="unknown experiment"):
        load_registry(claims, experiments, repository_root=Path.cwd())


def test_registry_rejects_evidence_outside_repository(tmp_path: Path) -> None:
    claims, experiments = _write_manifests(tmp_path, evidence='["../secret"]')

    with pytest.raises(ManifestError, match="must stay inside the repository"):
        load_registry(claims, experiments, repository_root=Path.cwd())


def test_describe_samples_and_bootstrap_are_deterministic() -> None:
    summary = describe_samples([1.0, 2.0, 3.0, 4.0])
    first = bootstrap_mean_ci([1.0, 2.0, 3.0, 4.0], seed=17, resamples=500)
    second = bootstrap_mean_ci([1.0, 2.0, 3.0, 4.0], seed=17, resamples=500)

    assert summary["count"] == 4
    assert summary["mean"] == pytest.approx(2.5)
    assert summary["median"] == pytest.approx(2.5)
    assert summary["p95"] >= summary["median"]
    assert first == second
    assert first[0] < 2.5 < first[1]


def test_redaction_removes_secrets_and_authorization_values() -> None:
    value = redact_text(
        "OPENAI_API_KEY=paper-secret Authorization: Bearer abc123",
        secret_values=("paper-secret",),
    )

    assert "paper-secret" not in value
    assert "abc123" not in value
    assert "[REDACTED]" in value


def test_structured_redaction_and_environment_secret_detection() -> None:
    environment = {
        "OPENAI_API_KEY": "paper-secret",
        "RABBITMQ_URL": "amqp://user:password@example.invalid/",
        "PLAIN_VALUE": "retained",
    }
    secrets = secret_values_from_environment(environment)
    value = redact_data(
        {
            "nested": ["paper-secret"],
            "broker": environment["RABBITMQ_URL"],
            "plain": environment["PLAIN_VALUE"],
        },
        secret_values=secrets,
    )

    assert value["nested"] == ["[REDACTED]"]
    assert value["broker"] == "[REDACTED]"
    assert value["plain"] == "retained"


def test_max_rss_is_normalized_to_kib_on_macos() -> None:
    assert _max_rss_kib(4_194_304, "darwin") == pytest.approx(4096)
    assert _max_rss_kib(4096, "linux") == pytest.approx(4096)


def test_inspect_wheel_verifies_the_published_artifact() -> None:
    wheel = Path("dist/praval-0.8.1-py3-none-any.whl")
    if not wheel.exists():
        pytest.skip("the exact 0.8.1 wheel is not present")

    identity = inspect_wheel(wheel)

    assert identity.version == EXPECTED_PRAVAL_VERSION
    assert identity.sha256 == EXPECTED_WHEEL_SHA256


def test_write_analysis_bundle_emits_machine_and_paper_formats(
    tmp_path: Path,
) -> None:
    report = {
        "schema_version": 1,
        "run_id": "offline-test",
        "tier": "offline",
        "status": "passed",
        "experiments": [
            {
                "id": "runtime-contracts",
                "status": "passed",
                "metrics": {"duration_seconds": {"median": 0.01}},
            }
        ],
    }

    paths = write_analysis_bundle(report, tmp_path)

    assert json.loads(paths["json"].read_text(encoding="utf-8"))["status"] == "passed"
    assert "runtime-contracts" in paths["markdown"].read_text(encoding="utf-8")
    assert "\\begin{tabular}" in paths["latex"].read_text(encoding="utf-8")


def test_paper_audit_records_hashes_citations_and_legacy_claims(
    tmp_path: Path,
) -> None:
    report = tmp_path / "report"
    arxiv = tmp_path / "arxiv"
    report.mkdir()
    arxiv.mkdir()
    (report / "praval_technical_report.md").write_text(
        "The Actor implementation provides asynchronous message semantics "
        "for isolated agents [@hewitt1973actor]. The old benchmark reported "
        "that framework latency was reduced by 90% to a measured duration "
        "of 3.23s.\n",
        encoding="utf-8",
    )
    (arxiv / "praval.tex").write_text(
        r"\cite{hewitt1973actor,missing} No central controller.",
        encoding="utf-8",
    )
    (arxiv / "references.bib").write_text(
        "@article{hewitt1973actor,\n title={Actors}\n}\n"
        "@article{unused,\n title={Unused}\n}\n",
        encoding="utf-8",
    )

    result = audit_paper(tmp_path)

    assert set(result["hashes"]) == {
        "report/praval_technical_report.md",
        "arxiv/praval.tex",
        "arxiv/references.bib",
    }
    assert result["citations"]["missing"] == ["missing"]
    assert result["citations"]["uncited"] == ["unused"]
    assert {"90%", "3.23s"} <= {finding["token"] for finding in result["legacy_claims"]}
    assert any(
        finding["token"] == "No central controller"
        for finding in result["strong_claims"]
    )
    assert result["claim_inventory_summary"]["total"] >= 2
    assert any(
        claim["status"] == "unsupported" and "90%" in claim["text"]
        for claim in result["claim_inventory"]
    )


def test_cli_exposes_the_planned_command_surface() -> None:
    parser = build_parser()

    for argv in (
        ["audit"],
        ["validate"],
        ["run", "--tier", "offline"],
        ["analyze", "--run-dir", "run"],
        ["export-paper", "--run-dir", "run"],
    ):
        assert parser.parse_args(argv).command == argv[0]


def test_module_validate_command_accepts_repository_manifests() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "research.paper_validation", "validate"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["claims"] >= 12
    assert payload["experiments"] >= 13
    assert payload["features"] >= 25
    assert payload["history_versions"] >= 30


def test_tier_selection_uses_only_registered_experiments() -> None:
    selected = select_experiments("offline")

    assert len(selected) >= 10
    assert all(experiment.tier == "offline" for experiment in selected)
    assert "runtime-contracts" in {experiment.id for experiment in selected}
    assert "reef-scaling-rabbitmq" not in {experiment.id for experiment in selected}


@pytest.mark.parametrize(
    "scenario",
    [
        "runtime_contracts",
        "capability_resolution",
        "spore_v2_compatibility",
        "secure_spore_behavior",
    ],
)
def test_core_offline_scenarios_produce_executable_evidence(
    scenario: str, tmp_path: Path
) -> None:
    result = run_scenario(
        scenario,
        output_dir=tmp_path / scenario,
        repetitions=2,
        warmups=0,
        seed=7,
        quick=True,
    )

    assert result["status"] == "passed", result
    assert result["checks"]
    assert (tmp_path / scenario / "result.json").is_file()


def test_comparison_dataset_and_exact_scorer() -> None:
    dataset = load_dataset(Path("research/paper_validation/comparative/dataset.jsonl"))
    expected = dataset["q01"]["expected"]

    assert len(dataset) == 12
    assert score_output(expected, expected)["correct"] is True
    assert (
        score_output({**expected, "answer": "259 sensors"}, expected)["correct"]
        is False
    )


def test_comparison_frameworks_have_hash_verified_dependency_locks() -> None:
    specs = _load_specs()

    assert set(specs) == {"praval", "langgraph", "crewai"}
    assert all(spec.lock_sha256 for spec in specs.values())


def test_paper_include_requires_registered_experiment_and_exact_hash(
    tmp_path: Path,
) -> None:
    claims, experiments = _write_manifests(tmp_path)
    registry = load_registry(claims, experiments, repository_root=Path.cwd())
    generated = tmp_path / "generated"
    generated.mkdir()
    fragment = generated / "runtime.md"
    fragment.write_text("| result | value |\n| --- | ---: |\n| pass | 1 |\n")
    from research.paper_validation.provenance import sha256_file

    directive = (
        "{{PRAVAL_INCLUDE:runtime-contracts:runtime.md:" f"{sha256_file(fragment)}}}}}"
    )

    expanded, used = expand_evidence_includes(
        directive, paper_root=tmp_path, registry=registry
    )

    assert "| pass | 1 |" in expanded
    assert used == ("runtime-contracts",)


def test_paper_history_include_requires_an_exact_hash(tmp_path: Path) -> None:
    claims, experiments = _write_manifests(tmp_path)
    registry = load_registry(claims, experiments, repository_root=Path.cwd())
    generated = tmp_path / "generated"
    generated.mkdir()
    fragment = generated / "praval-version-history.md"
    fragment.write_text(
        "| Version | Status |\n| --- | --- |\n| 0.8.1 | supported |\n",
        encoding="utf-8",
    )
    from research.paper_validation.provenance import sha256_file

    directive = (
        "{{PRAVAL_HISTORY_INCLUDE:praval-version-history.md:"
        f"{sha256_file(fragment)}}}}}"
    )

    expanded, used = expand_evidence_includes(
        directive, paper_root=tmp_path, registry=registry
    )

    assert "| 0.8.1 | supported |" in expanded
    assert used == ()


def test_protected_paper_introduction_allows_only_line_wrapping() -> None:
    wrapped = PROTECTED_INTRODUCTION.replace(
        "large language model calls", "large language\nmodel calls"
    )

    assert protected_introduction_is_present(wrapped)
    assert not protected_introduction_is_present(
        wrapped.replace("must coordinate", "coordinates")
    )


def test_paper_value_requires_hash_pinned_generated_index(
    tmp_path: Path,
) -> None:
    claims, experiments = _write_manifests(tmp_path)
    registry = load_registry(claims, experiments, repository_root=Path.cwd())
    generated = tmp_path / "generated"
    generated.mkdir()
    values = generated / "paper-values.json"
    values.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "values": {
                    "runtime_latency": {
                        "experiment": "runtime-contracts",
                        "value": 0.01,
                        "rendered": "10.00 ms",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    from research.paper_validation.provenance import sha256_file

    directive = "{{PRAVAL_VALUE:runtime_latency:" f"{sha256_file(values)}}}}}"

    expanded, used = expand_evidence_includes(
        directive, paper_root=tmp_path, registry=registry
    )

    assert expanded == "10.00 ms"
    assert used == ("runtime-contracts",)


def test_evidence_aggregation_preserves_dimensions_and_scope(
    tmp_path: Path,
) -> None:
    claims, experiments = _write_manifests(tmp_path)
    registry = load_registry(claims, experiments, repository_root=Path.cwd())
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    samples = artifacts / "runtime-contracts.samples.jsonl"
    samples.write_text(
        '{"metric":"latency_seconds","provider":"fake","value":0.01}\n'
        '{"metric":"latency_seconds","provider":"fake","value":0.02}\n',
        encoding="utf-8",
    )
    run = {
        "run_id": "canonical-offline",
        "tier": "offline",
        "canonical": True,
        "_source_dir": str(tmp_path),
        "experiments": [
            {
                "id": "runtime-contracts",
                "status": "passed",
                "artifacts": {
                    samples.name: {
                        "path": f"artifacts/{samples.name}",
                    }
                },
            }
        ],
    }

    claims_report = claim_evidence_report([run], registry)
    metrics_report = metric_evidence_report([run], seed=9)

    assert claims_report["claims"][0]["observed_status"] == "validated"
    assert metrics_report["raw_sample_count"] == 2
    assert metrics_report["groups"][0]["dimensions"] == {"provider": "fake"}
    paths = write_evidence_bundle(
        [run], registry=registry, output_dir=tmp_path / "evidence"
    )
    assert b"\r\n" not in paths["metrics_csv"].read_bytes()


def test_curation_rejects_quick_runs_and_verifies_artifact_hashes(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    artifact_dir = run_dir / "artifacts"
    artifact_dir.mkdir(parents=True)
    artifact = artifact_dir / "result.json"
    artifact.write_text('{"status":"passed"}\n', encoding="utf-8")
    from research.paper_validation.provenance import sha256_file

    run = {
        "run_id": "offline-canonical",
        "tier": "offline",
        "status": "passed",
        "canonical": True,
        "experiments": [
            {
                "id": "runtime-contracts",
                "artifacts": {
                    artifact.name: {
                        "path": "artifacts/result.json",
                        "sha256": sha256_file(artifact),
                    }
                },
            }
        ],
    }
    (run_dir / "run.json").write_text(json.dumps(run), encoding="utf-8")

    outputs = curate_runs([run_dir], output_dir=tmp_path / "canonical")

    assert (outputs["offline-canonical"] / "artifacts" / artifact.name).is_file()
    run["canonical"] = False
    (run_dir / "run.json").write_text(json.dumps(run), encoding="utf-8")
    with pytest.raises(ValueError, match="quick run"):
        curate_runs([run_dir], output_dir=tmp_path / "rejected")


def test_praval_comparison_adapter_uses_two_proxy_calls(tmp_path: Path) -> None:
    dataset = load_dataset(Path("research/paper_validation/comparative/dataset.jsonl"))
    try:
        server = ComparisonServer(
            ("127.0.0.1", 0),
            dataset=dataset,
            events_path=tmp_path / "events.jsonl",
            mode="delayed",
            delay_seconds=0,
            token="test-token",
            openai_api_key="",
            openai_model="",
            openai_base_url="https://api.openai.com/v1",
        )
    except PermissionError:
        pytest.skip("the test sandbox does not allow loopback listeners")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    runner = _load_praval()
    try:
        output, measurements = runner(
            dataset["q01"],
            f"http://127.0.0.1:{server.server_address[1]}",
            "test-token",
            "test-run",
        )
    finally:
        runner.close()  # type: ignore[attr-defined]
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert output == dataset["q01"]["expected"]
    assert len(measurements) == 2
    assert {
        json.loads(line)["stage"]
        for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    } == {"extract", "answer"}
