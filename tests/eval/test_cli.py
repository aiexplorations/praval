"""Exact public CLI flows for offline evaluation and explicit baselines."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from praval import Agent
from praval.cli import main
from praval.config import PravalConfig
from praval.core.registry import register_agent
from praval.eval.cli import _project_root, _store
from praval.eval.errors import EvaluationExecutionError
from praval.eval.postgres import PostgresEvaluationStore
from praval.models import ModelResponse, ProviderCapabilities, Usage


class EvalCLIProvider:
    provider_name = "fake"
    capabilities = ProviderCapabilities(structured_outputs=True, tools=True)

    def __init__(self) -> None:
        self.score = 0.9

    async def ainvoke(self, request, tools=None):
        schema_name = (
            request.response_schema.name
            if request.response_schema is not None
            else None
        )
        if schema_name == "StatementGeneratorOutput":
            return ModelResponse(
                content=json.dumps({"statements": ["The answer is ok."]}),
                model="judge-model",
            )
        if schema_name == "NLIStatementOutput":
            return ModelResponse(
                content=json.dumps(
                    {
                        "statements": [
                            {
                                "statement": "The answer is ok.",
                                "reason": "supported",
                                "verdict": 1,
                            }
                        ]
                    }
                ),
                model="judge-model",
            )
        if request.metadata.get("praval.evaluation"):
            return ModelResponse(
                content=json.dumps(
                    {
                        "status": "passed" if self.score >= 0.8 else "failed",
                        "score": self.score,
                        "label": "pass" if self.score >= 0.8 else "fail",
                        "evidence": [],
                    }
                ),
                model="judge-model",
                usage=Usage(input_tokens=4, output_tokens=2, total_tokens=6),
            )
        return ModelResponse(
            content='{"answer":"ok"}',
            model="target-model",
            metadata={"response_id": "target-response-1"},
            usage=Usage(input_tokens=2, output_tokens=2, total_tokens=4),
        )


def _project(tmp_path, database) -> tuple[str, str]:
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(
        '{"id":"case-1","input":{"question":"hello"},'
        '"expected_output":{"answer":"ok"}}\n',
        encoding="utf-8",
    )
    config = tmp_path / "praval.toml"
    config.write_text(
        f"""
schema_version = 1

[models.target]
provider = "fake"
model = "target-model"

[models.judge]
provider = "fake"
model = "judge-model"
temperature = 0

[agents.target]
model = "target"

[eval]
enabled = true
store = "sqlite"
offline_concurrency = 2

[eval.ragas]
model = "judge"

[eval.stores.sqlite]
path = "{database}"

[eval.judges.quality]
model = "judge"
rubric = "Score exact answer quality."
rubric_version = "1"
judge_version = "1"
max_attempts = 1

[eval.suites.release]
dataset = "cases.jsonl"
target = "agent:target"
judges = ["quality"]

[[eval.suites.release.gates]]
gate_id = "quality-mean"
metric = "quality"
aggregation = "mean"
operator = ">="
threshold = 0.8
""".strip(),
        encoding="utf-8",
    )
    return str(config), str(database)


def test_eval_cli_run_compare_and_explicit_baseline_flow(
    tmp_path, monkeypatch, capsys
) -> None:
    provider = EvalCLIProvider()
    monkeypatch.setattr(
        "praval.core.agent.ProviderFactory.create_provider",
        lambda *args, **kwargs: provider,
    )
    target = Agent("target", provider="fake", model="target-model")
    register_agent(target)
    config, database = _project(tmp_path, tmp_path / "evaluation.db")

    assert (
        main(
            [
                "eval",
                "run",
                "release",
                "--config",
                config,
                "--run-id",
                "baseline-run",
                "--json",
            ]
        )
        == 0
    )
    baseline_run = json.loads(capsys.readouterr().out)
    assert baseline_run["passed_cases"] == 1
    assert baseline_run["gates"][0]["status"] == "passed"

    assert (
        main(
            [
                "eval",
                "baseline",
                "set",
                "release",
                "baseline-run",
                "--promoted-by",
                "release-owner",
                "--config",
                config,
                "--json",
            ]
        )
        == 0
    )
    baseline = json.loads(capsys.readouterr().out)
    assert baseline["source_evaluation_run_id"] == "baseline-run"

    provider.score = 0.6
    assert (
        main(
            [
                "eval",
                "run",
                "release",
                "--config",
                config,
                "--run-id",
                "current-run",
                "--json",
            ]
        )
        == 1
    )
    current = json.loads(capsys.readouterr().out)
    assert current["gates"][0]["status"] == "failed"

    assert (
        main(
            [
                "eval",
                "compare",
                "current-run",
                "--suite",
                "release",
                "--max-regression",
                "0.1",
                "--config",
                config,
                "--json",
            ]
        )
        == 1
    )
    comparison = json.loads(capsys.readouterr().out)
    assert comparison["baseline_run_id"] == "baseline-run"
    assert comparison["regressed"] is True
    assert comparison["metrics"][0]["delta"] == pytest.approx(-0.3)
    target.close()


def test_eval_cli_reports_operational_errors_with_exit_two(tmp_path, capsys) -> None:
    config, database = _project(tmp_path, tmp_path / "evaluation.db")

    assert main(["eval", "run", "missing", "--config", config]) == 2
    assert "unknown evaluation suite" in capsys.readouterr().out
    assert database.endswith("evaluation.db")
    assert main(["eval"]) == 2
    assert "subcommand is required" in capsys.readouterr().out


def test_eval_cli_plain_output_and_explicit_compare_baseline(
    tmp_path, monkeypatch, capsys
) -> None:
    provider = EvalCLIProvider()
    monkeypatch.setattr(
        "praval.core.agent.ProviderFactory.create_provider",
        lambda *args, **kwargs: provider,
    )
    target = Agent("target", provider="fake", model="target-model")
    register_agent(target)
    config, _ = _project(tmp_path, tmp_path / "plain.db")

    assert (
        main(
            [
                "eval",
                "run",
                "release",
                "--config",
                config,
                "--run-id",
                "plain-base",
            ]
        )
        == 0
    )
    assert "Evaluation plain-base" in capsys.readouterr().out
    assert (
        main(
            [
                "eval",
                "baseline",
                "set",
                "--suite",
                "release",
                "--run",
                "plain-base",
                "--promoted-by",
                "owner",
                "--config",
                config,
            ]
        )
        == 0
    )
    assert "now points to plain-base" in capsys.readouterr().out
    provider.score = 0.6
    assert (
        main(
            [
                "eval",
                "run",
                "release",
                "--config",
                config,
                "--run-id",
                "plain-current",
                "--module",
                "json",
            ]
        )
        == 1
    )
    capsys.readouterr()
    assert (
        main(
            [
                "eval",
                "compare",
                "plain-current",
                "--baseline",
                "plain-base",
                "--max-regression",
                "0.1",
                "--config",
                config,
            ]
        )
        == 1
    )
    assert (
        "Comparison plain-current vs plain-base: regressed" in capsys.readouterr().out
    )
    target.close()


def test_eval_cli_supports_registered_evaluator_agent(
    tmp_path, monkeypatch, capsys
) -> None:
    provider = EvalCLIProvider()
    monkeypatch.setattr(
        "praval.core.agent.ProviderFactory.create_provider",
        lambda *args, **kwargs: provider,
    )
    target = Agent("target", provider="fake", model="target-model")
    evaluator = Agent("evaluator", provider="fake", model="judge-model")
    register_agent(target)
    register_agent(evaluator)
    config, _ = _project(tmp_path, tmp_path / "agent-judge.db")
    config_path = Path(config)
    text = config_path.read_text(encoding="utf-8")
    text = text.replace(
        '[eval.judges.quality]\nmodel = "judge"',
        '[agents.evaluator]\nmodel = "judge"\n\n'
        '[eval.judges.quality]\nagent = "evaluator"',
    )
    config_path.write_text(text, encoding="utf-8")

    assert (
        main(
            [
                "eval",
                "run",
                "release",
                "--config",
                config,
                "--run-id",
                "agent-judge-run",
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["passed_cases"] == 1
    target.close()
    evaluator.close()


@pytest.mark.skipif(
    sys.gettrace() is not None,
    reason="RAGAS datasets/PyArrow registration is incompatible with traced import",
)
def test_eval_cli_runs_actual_ragas_metric_with_configured_model(
    tmp_path, monkeypatch, capsys
) -> None:
    provider = EvalCLIProvider()
    monkeypatch.setattr(
        "praval.core.agent.ProviderFactory.create_provider",
        lambda *args, **kwargs: provider,
    )
    monkeypatch.setattr(
        "praval.eval.ragas.ProviderFactory.create_provider",
        lambda *args, **kwargs: provider,
    )
    target = Agent("target", provider="fake", model="target-model")
    register_agent(target)
    config, _ = _project(tmp_path, tmp_path / "ragas.db")
    config_path = Path(config)
    content = config_path.read_text(encoding="utf-8")
    content = content.replace(
        'judges = ["quality"]', 'metrics = ["ragas.faithfulness"]'
    ).replace('metric = "quality"', 'metric = "ragas.faithfulness"')
    config_path.write_text(content, encoding="utf-8")
    (tmp_path / "cases.jsonl").write_text(
        '{"id":"case-1","input":{"question":"hello"},'
        '"expected_output":{"answer":"ok"},'
        '"reference_contexts":["The answer is ok."]}\n',
        encoding="utf-8",
    )

    assert (
        main(
            [
                "eval",
                "run",
                "release",
                "--config",
                config,
                "--run-id",
                "ragas-run",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed_cases"] == 1
    assert payload["gates"][0]["metric"] == "ragas.faithfulness"
    target.close()


def test_eval_cli_store_selection_and_preflight_errors(
    tmp_path, monkeypatch, capsys
) -> None:
    assert _project_root(None) == Path.cwd()
    config = PravalConfig.model_validate(
        {
            "eval": {
                "store": "postgres",
                "stores": {"postgres": {"dsn_env": "TEST_EVAL_DSN"}},
            }
        }
    )
    monkeypatch.delenv("TEST_EVAL_DSN", raising=False)
    with pytest.raises(EvaluationExecutionError, match="environment is unset"):
        _store(config, root=tmp_path, sqlite_path=None)
    monkeypatch.setenv("TEST_EVAL_DSN", "postgresql://example/eval")
    assert isinstance(
        _store(config, root=tmp_path, sqlite_path=None), PostgresEvaluationStore
    )

    config_path, _ = _project(tmp_path, tmp_path / "errors.db")
    path = Path(config_path)
    content = path.read_text(encoding="utf-8")
    path.write_text(
        content.replace('target = "agent:target"', 'target = "workflow:missing"'),
        encoding="utf-8",
    )
    assert main(["eval", "run", "release", "--config", config_path]) == 2
    assert "requires an agent" in capsys.readouterr().out

    path.write_text(content, encoding="utf-8")
    assert main(["eval", "run", "release", "--config", config_path]) == 2
    assert "not registered" in capsys.readouterr().out

    path.write_text(
        content.replace(
            'judges = ["quality"]',
            'judges = ["quality"]\nmetrics = ["custom"]',
        ),
        encoding="utf-8",
    )
    assert main(["eval", "run", "release", "--config", config_path]) == 2
    assert "unknown evaluation metrics" in capsys.readouterr().out

    path.write_text(content, encoding="utf-8")
    assert (
        main(
            [
                "eval",
                "compare",
                "missing",
                "--config",
                config_path,
            ]
        )
        == 2
    )
    assert "--suite is required" in capsys.readouterr().out
    assert (
        main(
            [
                "eval",
                "compare",
                "missing",
                "--suite",
                "release",
                "--config",
                config_path,
            ]
        )
        == 2
    )
    assert "no active baseline" in capsys.readouterr().out


def test_eval_cli_redacts_unexpected_operational_error_details(
    tmp_path, monkeypatch, capsys
) -> None:
    config, _ = _project(tmp_path, tmp_path / "unexpected.db")
    module = tmp_path / "failing_eval_module.py"
    module.write_text(
        'raise RuntimeError("provider secret must not escape")\n', encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    assert (
        main(
            [
                "eval",
                "run",
                "release",
                "--config",
                config,
                "--module",
                "failing_eval_module",
            ]
        )
        == 2
    )
    output = capsys.readouterr().out
    assert "RuntimeError" in output
    assert "provider secret" not in output
