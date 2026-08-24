"""Contracts for the Evaluation documentation area and executable patterns."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from praval.config import PravalConfig

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[2]
EVALUATION_DOCS = ROOT / "docs" / "sphinx" / "evaluation"


def _load_example(name: str):
    path = ROOT / "examples" / "evaluation" / name
    spec = importlib.util.spec_from_file_location(f"praval_eval_example_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_evaluation_area_contains_every_planned_guide() -> None:
    expected = {
        "index.md",
        "quickstart.md",
        "configuration.md",
        "patterns.md",
        "evaluator-agents.md",
        "evaluator-flow.md",
        "direct-model-judges.md",
        "datasets-suites.md",
        "agents-workflows.md",
        "metrics-ragas.md",
        "gates-ci.md",
        "online.md",
        "stores-retention.md",
        "telemetry.md",
        "privacy-cost-security.md",
        "production-recipes.md",
        "troubleshooting.md",
        "api-reference.md",
    }
    assert {path.name for path in EVALUATION_DOCS.glob("*.md")} == expected
    index = (EVALUATION_DOCS / "index.md").read_text()
    for name in expected - {"index.md"}:
        assert name.removesuffix(".md") in index


def test_recommended_patterns_state_the_safety_and_observation_contracts() -> None:
    patterns = (EVALUATION_DOCS / "patterns.md").read_text()
    required = (
        "exactly one immutable `ExecutionObservation`",
        "Least-privilege evaluator",
        "allowed_tools",
        "Side-effecting evaluator tools are not supported",
        "dedicated namespace",
        "Anti-patterns",
        "examples/evaluation/001_paired_agents.py",
    )
    for phrase in required:
        assert phrase in patterns


def test_production_recipes_cover_every_operational_step_and_release_path() -> None:
    recipes = (EVALUATION_DOCS / "production-recipes.md").read_text()
    for phrase in (
        "Prerequisites",
        "Install",
        "Complete `praval.toml`",
        "Run",
        "Expected output",
        "Inspect",
        "Failure and cleanup",
        "Next",
        "PostgreSQL shared store",
        "RAGAS through Praval runtimes",
        "Sampled online evaluation",
        "Metadata-only and redacted-content deployment",
        "Failure and graceful-shutdown exercise",
        "Correlate an evaluation result with its trace",
    ):
        assert phrase in recipes

    toml_blocks = re.findall(r"```toml\n(.*?)```", recipes, flags=re.DOTALL)
    assert len(toml_blocks) == 6
    for block in toml_blocks:
        PravalConfig.model_validate(tomllib.loads(block))


@pytest.mark.asyncio
async def test_quickstart_example_produces_one_passing_subject(tmp_path) -> None:
    example = _load_example("000_quickstart.py")
    result = await example.run(tmp_path / "quickstart.db")

    assert result == {
        "run_status": "completed",
        "passed_cases": 1,
        "gate_status": "passed",
        "subject_count": 1,
        "observation_kind": "agent",
    }


@pytest.mark.asyncio
async def test_paired_agent_example_is_positive_bounded_and_safe(tmp_path) -> None:
    example = _load_example("001_paired_agents.py")
    result = await example.run(tmp_path / "paired.db")

    assert result["run_status"] == "completed"
    assert result["judge_status"] == "passed"
    assert result["subject_count"] == 1
    assert result["target_agent"] == "answerer"
    assert result["allowed_tools"] == ["policy_lookup"]


@pytest.mark.asyncio
async def test_workflow_example_aggregates_handoffs_and_tools_once(tmp_path) -> None:
    example = _load_example("002_workflow_evaluation.py")
    result = await example.run(tmp_path / "workflow.db")

    assert result["run_status"] == "completed"
    assert result["passed_cases"] == 1
    assert result["subject_count"] == 1
    assert result["subject_kind"] == "workflow"
    assert result["tool_facts"] == 1
    assert result["handoff_facts"] == 1
    assert set(result["metric_statuses"].values()) == {"passed"}


def test_evaluation_examples_import_only_public_praval_modules() -> None:
    for path in sorted((ROOT / "examples" / "evaluation").glob("*.py")):
        source = path.read_text()
        assert "praval.eval." not in source
        assert "praval.observability." not in source
        assert "praval.runtime_observation" not in source

    wheel_smoke = (ROOT / "scripts" / "smoke_install.py").read_text()
    assert "000_quickstart.py" in wheel_smoke
    assert "001_paired_agents.py" in wheel_smoke
    assert "002_workflow_evaluation.py" in wheel_smoke
