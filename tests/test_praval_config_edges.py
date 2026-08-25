"""Validation and compatibility edges for typed Praval configuration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from praval.config import (
    AgentProfileConfig,
    EvalConfig,
    EvalJudgeConfig,
    ObservabilityConfig,
    OnlineEvalConfig,
    OTLPConfig,
    PravalConfig,
    discover_config_path,
    get_legacy_observability_config,
    load_config,
    reset_legacy_observability_config,
)
from praval.core.exceptions import PravalConfigurationError


def test_agent_otlp_and_judge_local_validation() -> None:
    with pytest.raises(ValidationError, match="memory_namespace"):
        AgentProfileConfig(memory_enabled=True)
    with pytest.raises(ValidationError, match="max_export_batch_size"):
        OTLPConfig(max_queue_size=2, max_export_batch_size=3)
    with pytest.raises(ValidationError, match="headers_env"):
        OTLPConfig(headers_env="NOT-AN-ENV")
    with pytest.raises(ValidationError, match="exactly one"):
        EvalJudgeConfig()
    with pytest.raises(ValidationError, match="exactly one"):
        EvalJudgeConfig(agent="agent", model="model")
    with pytest.raises(ValidationError, match="postgres"):
        EvalConfig(store="postgres")
    with pytest.raises(ValidationError, match="online evaluation"):
        EvalConfig(online={"enabled": True})
    with pytest.raises(ValidationError, match="lease_seconds"):
        OnlineEvalConfig(lease_seconds=60, job_timeout_seconds=60)
    with pytest.raises(ValidationError):
        OnlineEvalConfig(queue_capacity=100_001)
    with pytest.raises(ValidationError):
        OnlineEvalConfig(workers=65)


def test_legacy_observability_fields_map_to_nested_configuration(
    tmp_path: Path,
) -> None:
    path = tmp_path / "traces.db"
    with pytest.warns(DeprecationWarning) as caught:
        config = ObservabilityConfig(
            sample_rate=0.4,
            otlp_endpoint="http://collector:4318",
            storage_path=str(path),
        )

    assert len(caught) == 3
    assert config.sample_rate == 0.4
    assert config.otlp_endpoint == "http://collector:4318"
    assert config.storage_path == str(path)
    assert ObservabilityConfig.map_legacy_fields(None) is None


def test_legacy_environment_validation_and_cache(monkeypatch) -> None:
    monkeypatch.setenv("PRAVAL_OBSERVABILITY", "invalid")
    with pytest.raises(PravalConfigurationError, match="auto, on, off"):
        ObservabilityConfig.from_env()

    monkeypatch.setenv("PRAVAL_OBSERVABILITY", "on")
    monkeypatch.setenv("PRAVAL_SAMPLE_RATE", "invalid")
    with pytest.raises(PravalConfigurationError):
        ObservabilityConfig.from_env()

    monkeypatch.setenv("PRAVAL_SAMPLE_RATE", "0.2")
    reset_legacy_observability_config()
    first = get_legacy_observability_config()
    second = get_legacy_observability_config()
    assert first is second
    reset_legacy_observability_config()
    assert get_legacy_observability_config() is not first


@pytest.mark.parametrize(
    "overrides,match",
    [
        (
            {"app": {"service_name": ""}, "observability": {"enabled": True}},
            "service_name",
        ),
        (
            {"agents": {"a": {"model": "missing"}}},
            "unknown model",
        ),
        (
            {
                "models": {"m": {"provider": "fake", "model": "m"}},
                "agents": {"judge": {"model": "m", "tools": ["safe"]}},
                "eval": {
                    "judges": {"j": {"agent": "judge", "allowed_tools": ["unsafe"]}}
                },
            },
            "allowed_tools",
        ),
        (
            {
                "eval": {
                    "judges": {"j": {"model": "missing"}},
                }
            },
            "unknown model",
        ),
        (
            {"eval": {"ragas": {"model": "missing"}}},
            "eval.ragas.model",
        ),
        (
            {"eval": {"ragas": {"embedding": "missing"}}},
            "eval.ragas.embedding",
        ),
        (
            {
                "eval": {
                    "suites": {
                        "suite": {
                            "dataset": "cases.jsonl",
                            "target": "agent:a",
                            "judges": ["missing"],
                        }
                    }
                }
            },
            "unknown judges",
        ),
        (
            {
                "eval": {
                    "suites": {
                        "suite": {
                            "dataset": "cases.jsonl",
                            "target": "agent:a",
                            "gates": [
                                {
                                    "metric": "missing",
                                    "aggregation": "mean",
                                    "operator": ">=",
                                    "threshold": 0.8,
                                }
                            ],
                        }
                    }
                }
            },
            "unknown results",
        ),
    ],
)
def test_cross_section_validation_edges(overrides, match: str) -> None:
    with pytest.raises(PravalConfigurationError, match=match):
        load_config(overrides=overrides, environ={})


def test_agent_resolution_errors_are_configuration_errors() -> None:
    config = PravalConfig(
        agents={"defaulted": AgentProfileConfig()},
    )
    with pytest.raises(PravalConfigurationError, match="unknown agent"):
        config.resolve_agent_profile("missing")
    with pytest.raises(PravalConfigurationError, match="default"):
        config.resolve_agent_profile("defaulted")

    valid = PravalConfig(
        models={"m": {"provider": "fake", "model": "model"}},
        agents={"a": {"model": "m"}},
    )
    with pytest.raises(PravalConfigurationError):
        valid.resolve_agent_profile("a", {"max_tool_rounds": 0})


def test_discovery_explicit_file_and_file_start(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "praval.toml"
    config_path.write_text("schema_version = 1\n", encoding="utf-8")
    child_file = tmp_path / "child.py"
    child_file.write_text("", encoding="utf-8")
    monkeypatch.delenv("PRAVAL_CONFIG_FILE", raising=False)
    assert discover_config_path(child_file) == config_path

    monkeypatch.setenv("PRAVAL_CONFIG_FILE", str(config_path))
    assert discover_config_path() == config_path
    monkeypatch.setenv("PRAVAL_CONFIG_FILE", str(tmp_path / "missing.toml"))
    with pytest.raises(PravalConfigurationError, match="not found"):
        discover_config_path()


def test_load_config_file_and_environment_errors(tmp_path: Path) -> None:
    missing = tmp_path / "missing.toml"
    with pytest.raises(PravalConfigurationError, match="not found"):
        load_config(missing, environ={})

    invalid = tmp_path / "invalid.toml"
    invalid.write_text("[invalid", encoding="utf-8")
    with pytest.raises(PravalConfigurationError, match="cannot load"):
        load_config(invalid, environ={})

    with pytest.raises(PravalConfigurationError, match="auto, on, off"):
        load_config(environ={"PRAVAL_OBSERVABILITY": "invalid"})
    with pytest.raises(PravalConfigurationError, match="numeric"):
        load_config(environ={"PRAVAL_SAMPLE_RATE": "invalid"})
    with pytest.raises(PravalConfigurationError, match="boolean"):
        load_config(environ={"PRAVAL_CAPTURE_CONTENT": "invalid"})


@pytest.mark.parametrize(
    "environment,expected",
    [
        ({"PRAVAL_OBSERVABILITY": "on"}, True),
        ({"PRAVAL_OBSERVABILITY": "off"}, False),
        (
            {
                "PRAVAL_OBSERVABILITY": "auto",
                "PRAVAL_ENVIRONMENT": "production",
            },
            False,
        ),
    ],
)
def test_observability_environment_modes(environment, expected: bool) -> None:
    assert load_config(environ=environment).observability.enabled is expected


def test_all_supported_environment_values_are_applied() -> None:
    config = load_config(
        environ={
            "PRAVAL_SERVICE_NAME": "service",
            "PRAVAL_SERVICE_VERSION": "1.2.3",
            "PRAVAL_ENVIRONMENT": "staging",
            "PRAVAL_OTLP_ENDPOINT": "http://collector:4318",
            "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
            "PRAVAL_TRACES_PATH": "/tmp/traces.db",
            "PRAVAL_DEFAULT_PROVIDER": "fake",
            "PRAVAL_DEFAULT_MODEL": "model",
            "PRAVAL_CAPTURE_CONTENT": "yes",
        }
    )

    assert config.app.service_name == "service"
    assert config.app.service_version == "1.2.3"
    assert config.app.deployment_environment == "staging"
    assert config.observability.otlp.endpoint == "http://collector:4318"
    assert config.observability.otlp.protocol == "grpc"
    assert config.observability.local.path == "/tmp/traces.db"
    assert config.observability.capture_content is True
    assert config.models["default"].provider == "fake"
    assert (
        load_config(
            environ={"PRAVAL_CAPTURE_CONTENT": "no"}
        ).observability.capture_content
        is False
    )
