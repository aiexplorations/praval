"""Contracts for typed ``praval.toml`` configuration."""

from pathlib import Path

import pytest

from praval.config import PravalConfig, discover_config_path, load_config
from praval.core.exceptions import PravalConfigurationError


def _write_config(path: Path) -> None:
    path.write_text(
        """
schema_version = 1

[app]
service_name = "file-service"
deployment_environment = "test"

[models.default]
provider = "openai"
model = "file-model"

[models.judge]
provider = "anthropic"
model = "judge-model"
temperature = 0

[embeddings.evaluation]
provider = "openai"
model = "text-embedding-3-small"
dimensions = 1536
api_key_env = "OPENAI_API_KEY"

[agents.researcher]
model = "default"
max_tool_rounds = 8

[agents.quality_critic]
model = "judge"
tools = ["search_docs", "lookup_policy"]
memory_enabled = true
memory_namespace = "evaluation/quality_critic"
max_tool_rounds = 4

[observability]
enabled = true
capture_content = true
content_allowlist = ["gen_ai.prompt"]
sample_ratio = 0.5

[observability.otlp]
endpoint = "http://collector:4318"
protocol = "http/protobuf"
traces = true
metrics = true
logs = true

[eval]
enabled = true
store = "postgres"

[eval.ragas]
model = "judge"
embedding = "evaluation"
timeout_seconds = 45

[eval.stores.postgres]
dsn_env = "PRAVAL_EVAL_DATABASE_URL"

[eval.judges.quality]
agent = "quality_critic"
rubric = "Score grounded research quality."
rubric_version = "2026-08-25"
judge_version = "2"
allowed_tools = ["search_docs", "lookup_policy"]
tool_policy = "evaluation_safe"
allow_side_effects = false
hitl_mode = "suspend"
max_input_tokens = 16000
max_cost_usd = 0.25

[eval.suites.research_quality]
dataset = "evals/research_quality.jsonl"
target = "agent:researcher"
judges = ["quality"]
metrics = ["ragas.faithfulness"]

[[eval.suites.research_quality.gates]]
gate_id = "faithfulness-mean"
metric = "ragas.faithfulness"
aggregation = "mean"
operator = ">="
threshold = 0.85
baseline_max_regression = 0.05
""".strip(),
        encoding="utf-8",
    )


def test_load_config_precedence_and_agent_resolution(tmp_path: Path) -> None:
    config_path = tmp_path / "praval.toml"
    _write_config(config_path)

    config = load_config(
        config_path,
        environ={
            "OTEL_SERVICE_NAME": "environment-service",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://environment:4318",
            "PRAVAL_DEFAULT_MODEL": "environment-model",
        },
        overrides={
            "app": {"service_name": "explicit-service"},
            "observability": {"sample_ratio": 0.25},
        },
    )

    assert config.app.service_name == "explicit-service"
    assert config.observability.otlp.endpoint == "http://environment:4318"
    assert config.observability.sample_ratio == 0.25
    assert config.observability.capture_content is True
    assert config.observability.content_allowlist == ("gen_ai.prompt",)
    resolved = config.resolve_agent_profile("researcher", {"max_tool_rounds": 12})
    assert resolved.provider == "openai"
    assert resolved.model == "environment-model"
    assert resolved.max_tool_rounds == 12
    judge = config.eval.judges["quality"]
    assert judge.rubric_version == "2026-08-25"
    assert judge.judge_version == "2"
    assert config.eval.ragas is not None
    assert config.eval.ragas.model == "judge"
    assert config.eval.ragas.embedding == "evaluation"
    assert config.embeddings["evaluation"].api_key_env == "OPENAI_API_KEY"
    gate = config.eval.suites["research_quality"].gates[0]
    assert gate.gate_id == "faithfulness-mean"
    assert gate.baseline_max_regression == 0.05


def test_discover_config_uses_nearest_parent(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "project"
    nested = root / "src" / "package"
    nested.mkdir(parents=True)
    config_path = root / "praval.toml"
    _write_config(config_path)
    monkeypatch.delenv("PRAVAL_CONFIG_FILE", raising=False)

    assert discover_config_path(nested) == config_path


@pytest.mark.parametrize(
    "fragment",
    [
        "unknown_field = true",
        "sample_ratio = 2.0",
    ],
)
def test_unknown_and_invalid_fields_fail_before_runtime(
    tmp_path: Path, fragment: str
) -> None:
    path = tmp_path / "praval.toml"
    path.write_text(f"[observability]\n{fragment}\n", encoding="utf-8")

    with pytest.raises(PravalConfigurationError):
        load_config(path, environ={})


def test_cross_references_and_evaluator_safety_are_validated() -> None:
    with pytest.raises(PravalConfigurationError, match="unknown agent"):
        load_config(
            overrides={
                "eval": {
                    "judges": {"quality": {"agent": "missing"}},
                }
            },
            environ={},
        )

    with pytest.raises(PravalConfigurationError, match="side effects"):
        load_config(
            overrides={
                "models": {"judge": {"provider": "fake", "model": "judge"}},
                "eval": {
                    "judges": {
                        "quality": {"model": "judge", "allow_side_effects": True}
                    }
                },
            },
            environ={},
        )


def test_model_is_immutable_and_schema_version_is_strict() -> None:
    config = PravalConfig()
    with pytest.raises(Exception):
        config.app.service_name = "changed"
    with pytest.raises(PravalConfigurationError):
        load_config(overrides={"schema_version": 2}, environ={})


def test_otel_environment_can_disable_individual_exporters() -> None:
    config = load_config(
        overrides={"observability": {"enabled": True}},
        environ={
            "OTEL_TRACES_EXPORTER": "none",
            "OTEL_METRICS_EXPORTER": "otlp",
            "OTEL_LOGS_EXPORTER": "none",
        },
    )

    assert config.observability.otlp.traces is False
    assert config.observability.otlp.metrics is True
    assert config.observability.otlp.logs is False


def test_praval_service_name_overrides_standard_otel_name() -> None:
    config = load_config(
        environ={
            "OTEL_SERVICE_NAME": "otel-default",
            "PRAVAL_SERVICE_NAME": "praval-service",
        }
    )

    assert config.app.service_name == "praval-service"
