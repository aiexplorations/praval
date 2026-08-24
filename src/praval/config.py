"""Typed configuration loading for Praval applications.

Configuration is read without creating runtime resources. Values are merged in
this order: defaults, ``praval.toml``, environment variables, then explicit API
overrides.
"""

from __future__ import annotations

import os
import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .core.exceptions import PravalConfigurationError

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10 only
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]


class _ConfigModel(BaseModel):
    """Base for immutable configuration with strict unknown-field handling."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AppConfig(_ConfigModel):
    """Application resource identity."""

    service_name: str = "praval"
    service_version: str | None = None
    deployment_environment: str | None = None


class ModelProfileConfig(_ConfigModel):
    """Named foundation-model profile."""

    provider: str
    model: str
    temperature: float | None = None
    max_output_tokens: int | None = Field(default=None, gt=0)


class AgentProfileConfig(_ConfigModel):
    """Named agent defaults layered over a model profile."""

    model: str | None = None
    system_message: str | None = None
    tools: tuple[str, ...] = ()
    memory_enabled: bool = False
    memory_namespace: str | None = None
    max_tool_rounds: int = Field(default=8, gt=0, le=1000)

    @model_validator(mode="after")
    def validate_memory_namespace(self) -> "AgentProfileConfig":
        """Require a stable namespace whenever agent memory is enabled."""
        if self.memory_enabled and not self.memory_namespace:
            raise ValueError("memory_namespace is required when memory_enabled is true")
        return self


class OTLPConfig(_ConfigModel):
    """OTLP transport and batching settings."""

    endpoint: str | None = None
    protocol: Literal["http/protobuf", "grpc"] = "http/protobuf"
    traces: bool = True
    metrics: bool = True
    logs: bool = True
    headers_env: str | None = None
    max_queue_size: int = Field(default=2048, gt=0)
    max_export_batch_size: int = Field(default=512, gt=0)
    schedule_delay_millis: int = Field(default=5000, gt=0)
    export_timeout_millis: int = Field(default=30000, gt=0)
    metric_export_interval_millis: int = Field(default=60000, gt=0)

    @model_validator(mode="after")
    def validate_batch_bounds(self) -> "OTLPConfig":
        """Keep each export batch within its bounded queue."""
        if self.max_export_batch_size > self.max_queue_size:
            raise ValueError("max_export_batch_size cannot exceed max_queue_size")
        if self.headers_env and not self.headers_env.replace("_", "").isalnum():
            raise ValueError("headers_env must name an environment variable")
        return self


class LocalObservabilityConfig(_ConfigModel):
    """Optional local-only diagnostic trace retention."""

    enabled: bool = False
    path: str = "~/.praval/telemetry.db"
    max_traces: int = Field(default=10000, gt=0)
    max_age_days: int = Field(default=7, ge=0)


class ObservabilityConfig(_ConfigModel):
    """Observability signal and privacy configuration.

    The deprecated ``sample_rate``, ``otlp_endpoint``, and ``storage_path``
    inputs remain accepted for the v0.8.2 migration window.
    """

    enabled: bool = False
    capture_content: bool = False
    content_allowlist: tuple[str, ...] = ()
    sampling: Literal["always_on", "always_off", "parentbased_traceidratio"] = (
        "parentbased_traceidratio"
    )
    sample_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    flush_timeout_millis: int = Field(default=5000, gt=0)
    otlp: OTLPConfig = Field(default_factory=OTLPConfig)
    local: LocalObservabilityConfig = Field(default_factory=LocalObservabilityConfig)

    @model_validator(mode="before")
    @classmethod
    def map_legacy_fields(cls, value: Any) -> Any:
        """Map supported v0.8.2 field names to the typed nested schema."""
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        legacy = {
            "sample_rate": ("sample_ratio", None),
            "otlp_endpoint": ("endpoint", "otlp"),
            "storage_path": ("path", "local"),
        }
        for old_name, (new_name, section) in legacy.items():
            if old_name not in data:
                continue
            warnings.warn(
                f"ObservabilityConfig.{old_name} is deprecated; use {new_name}",
                DeprecationWarning,
                stacklevel=3,
            )
            old_value = data.pop(old_name)
            if section is None:
                data.setdefault(new_name, old_value)
                continue
            nested = dict(data.get(section, {}))
            nested.setdefault(new_name, old_value)
            data[section] = nested
        return data

    @property
    def sample_rate(self) -> float:
        """Return the deprecated sampling field."""
        return self.sample_ratio

    @property
    def otlp_endpoint(self) -> str | None:
        """Return the deprecated flat OTLP endpoint."""
        return self.otlp.endpoint

    @property
    def storage_path(self) -> str:
        """Return the deprecated expanded local path."""
        return str(Path(self.local.path).expanduser())

    def is_enabled(self) -> bool:
        """Return whether observability is enabled."""
        return self.enabled

    def should_sample(self) -> bool:
        """Provide the v0.8.2 probabilistic sampling helper."""
        if self.sample_ratio >= 1.0:
            return True
        if self.sample_ratio <= 0.0:
            return False
        import random

        return random.random() < self.sample_ratio

    @classmethod
    def from_env(cls) -> "ObservabilityConfig":
        """Load supported legacy observability environment variables."""
        mode = os.getenv("PRAVAL_OBSERVABILITY", "auto").lower()
        if mode not in {"auto", "on", "off"}:
            raise PravalConfigurationError(
                "PRAVAL_OBSERVABILITY must be one of: auto, on, off"
            )
        environment = os.getenv("ENVIRONMENT", "development").lower()
        enabled = mode == "on" or (
            mode == "auto" and environment not in {"production", "prod"}
        )
        try:
            sample_ratio = float(os.getenv("PRAVAL_SAMPLE_RATE", "1.0"))
            return cls(
                enabled=enabled,
                sample_ratio=sample_ratio,
                otlp=OTLPConfig(endpoint=os.getenv("PRAVAL_OTLP_ENDPOINT")),
                local=LocalObservabilityConfig(
                    path=os.getenv("PRAVAL_TRACES_PATH", "~/.praval/traces.db")
                ),
            )
        except (TypeError, ValueError) as exc:
            raise PravalConfigurationError(str(exc)) from exc


class OnlineEvalConfig(_ConfigModel):
    """Sampled online evaluation worker settings."""

    enabled: bool = False
    sample_ratio: float = Field(default=0.01, ge=0.0, le=1.0)
    queue_capacity: int = Field(default=1000, gt=0)
    workers: int = Field(default=2, gt=0)
    max_attempts: int = Field(default=3, gt=0, le=3)


class PostgresEvalStoreConfig(_ConfigModel):
    """PostgreSQL evaluation-store secret reference."""

    dsn_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")


class EvalStoresConfig(_ConfigModel):
    """Named evaluation-store settings."""

    postgres: PostgresEvalStoreConfig | None = None


class EvalJudgeConfig(_ConfigModel):
    """Evaluator-agent or direct-model safety and budget policy."""

    agent: str | None = None
    model: str | None = None
    timeout_seconds: float = Field(default=60.0, gt=0)
    max_attempts: int = Field(default=2, gt=0)
    allow_self_evaluation: bool = False
    allowed_tools: tuple[str, ...] = ()
    tool_policy: Literal["evaluation_safe", "read_only"] = "evaluation_safe"
    allow_side_effects: bool = False
    hitl_mode: Literal["suspend", "fail"] = "suspend"
    max_input_tokens: int = Field(default=16000, gt=0)
    max_cost_usd: float = Field(default=0.25, gt=0)

    @model_validator(mode="after")
    def validate_subject(self) -> "EvalJudgeConfig":
        """Require exactly one configured judge implementation."""
        if (self.agent is None) == (self.model is None):
            raise ValueError("a judge must reference exactly one agent or model")
        if self.allow_side_effects:
            raise ValueError("evaluator side effects are not supported in v0.8.3")
        return self


class EvalGateConfig(_ConfigModel):
    """One evaluation quality gate."""

    metric: str
    aggregation: Literal["mean", "minimum", "maximum", "percentile", "count"]
    operator: Literal[">=", ">", "<=", "<", "=="]
    threshold: float


class EvalSuiteConfig(_ConfigModel):
    """Offline or CI evaluation suite."""

    dataset: str
    target: str
    judges: tuple[str, ...] = ()
    metrics: tuple[str, ...] = ()
    gates: tuple[EvalGateConfig, ...] = ()


class EvalConfig(_ConfigModel):
    """Evaluation orchestration configuration."""

    enabled: bool = False
    store: Literal["sqlite", "postgres"] = "sqlite"
    offline_concurrency: int = Field(default=4, gt=0)
    online: OnlineEvalConfig = Field(default_factory=OnlineEvalConfig)
    stores: EvalStoresConfig = Field(default_factory=EvalStoresConfig)
    judges: dict[str, EvalJudgeConfig] = Field(default_factory=dict)
    suites: dict[str, EvalSuiteConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_store(self) -> "EvalConfig":
        """Require PostgreSQL configuration when that store is selected."""
        if self.store == "postgres" and self.stores.postgres is None:
            raise ValueError("eval.stores.postgres is required for the postgres store")
        if self.online.enabled and self.store != "postgres":
            raise ValueError("online evaluation requires the postgres store")
        return self


class ResolvedAgentConfig(_ConfigModel):
    """Resolved agent and model settings after precedence is applied."""

    name: str
    provider: str
    model: str
    temperature: float | None = None
    max_output_tokens: int | None = None
    system_message: str | None = None
    tools: tuple[str, ...] = ()
    memory_enabled: bool = False
    memory_namespace: str | None = None
    max_tool_rounds: int = Field(default=8, gt=0, le=1000)


class PravalConfig(_ConfigModel):
    """Complete schema-versioned Praval application configuration."""

    schema_version: Literal[1] = 1
    app: AppConfig = Field(default_factory=AppConfig)
    models: dict[str, ModelProfileConfig] = Field(default_factory=dict)
    agents: dict[str, AgentProfileConfig] = Field(default_factory=dict)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    eval: EvalConfig = Field(default_factory=EvalConfig)

    @model_validator(mode="after")
    def validate_references(self) -> "PravalConfig":
        """Validate cross-section references before runtime work starts."""
        if self.observability.enabled and not self.app.service_name.strip():
            raise ValueError(
                "app.service_name is required when observability is enabled"
            )
        for name, agent in self.agents.items():
            if agent.model is not None and agent.model not in self.models:
                raise ValueError(f"agents.{name}.model references unknown model")
        for name, judge in self.eval.judges.items():
            if judge.agent is not None:
                if judge.agent not in self.agents:
                    raise ValueError(f"eval.judges.{name} references unknown agent")
                agent_tools = set(self.agents[judge.agent].tools)
                disallowed = set(judge.allowed_tools) - agent_tools
                if disallowed:
                    raise ValueError(
                        f"eval.judges.{name}.allowed_tools are not configured "
                        f"on agent {judge.agent}: {sorted(disallowed)}"
                    )
            if judge.model is not None and judge.model not in self.models:
                raise ValueError(f"eval.judges.{name} references unknown model")
        for name, suite in self.eval.suites.items():
            unknown = set(suite.judges) - set(self.eval.judges)
            if unknown:
                raise ValueError(
                    f"eval.suites.{name} references unknown judges: {sorted(unknown)}"
                )
        return self

    def resolve_agent_profile(
        self,
        name: str,
        overrides: Mapping[str, Any] | None = None,
    ) -> ResolvedAgentConfig:
        """Resolve an agent over its named model and explicit overrides."""
        try:
            agent = self.agents[name]
        except KeyError as exc:
            raise PravalConfigurationError(f"unknown agent profile: {name}") from exc
        model_name = agent.model or "default"
        try:
            model = self.models[model_name]
        except KeyError as exc:
            raise PravalConfigurationError(
                f"agent {name} references unknown model profile: {model_name}"
            ) from exc
        values: dict[str, Any] = {
            "name": name,
            **model.model_dump(),
            **agent.model_dump(exclude={"model"}),
        }
        if overrides:
            values.update(overrides)
        try:
            return ResolvedAgentConfig.model_validate(values)
        except ValueError as exc:
            raise PravalConfigurationError(str(exc)) from exc


def discover_config_path(start: Path | None = None) -> Path | None:
    """Find the nearest ``praval.toml`` without reading user-home defaults."""
    configured = os.getenv("PRAVAL_CONFIG_FILE")
    if configured:
        path = Path(configured).expanduser()
        if not path.is_file():
            raise PravalConfigurationError(f"configuration file not found: {path}")
        return path.resolve()
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        candidate = directory / "praval.toml"
        if candidate.is_file():
            return candidate
    return None


def _deep_merge(base: Mapping[str, Any], update: Mapping[str, Any]) -> dict[str, Any]:
    """Merge nested configuration mappings without mutating inputs."""
    merged = dict(base)
    for key, value in update.items():
        existing = merged.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def _parse_bool(name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise PravalConfigurationError(f"{name} must be a boolean value")


def _environment_overrides(environ: Mapping[str, str]) -> dict[str, Any]:
    """Translate supported Praval and standard OTel environment variables."""
    result: dict[str, Any] = {}

    def assign(path: tuple[str, ...], value: Any) -> None:
        cursor = result
        for part in path[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[path[-1]] = value

    string_fields = {
        "PRAVAL_SERVICE_NAME": ("app", "service_name"),
        "OTEL_SERVICE_NAME": ("app", "service_name"),
        "PRAVAL_SERVICE_VERSION": ("app", "service_version"),
        "PRAVAL_ENVIRONMENT": ("app", "deployment_environment"),
        "PRAVAL_OTLP_ENDPOINT": ("observability", "otlp", "endpoint"),
        "OTEL_EXPORTER_OTLP_ENDPOINT": ("observability", "otlp", "endpoint"),
        "OTEL_EXPORTER_OTLP_PROTOCOL": ("observability", "otlp", "protocol"),
        "PRAVAL_TRACES_PATH": ("observability", "local", "path"),
    }
    for variable, path in string_fields.items():
        if variable in environ:
            assign(path, environ[variable])
    if "PRAVAL_OBSERVABILITY" in environ:
        value = environ["PRAVAL_OBSERVABILITY"].lower()
        if value == "auto":
            environment = environ.get("PRAVAL_ENVIRONMENT", "development").lower()
            enabled = environment not in {"production", "prod"}
        elif value in {"on", "off"}:
            enabled = value == "on"
        else:
            raise PravalConfigurationError(
                "PRAVAL_OBSERVABILITY must be one of: auto, on, off"
            )
        assign(("observability", "enabled"), enabled)
    numeric_fields = {
        "PRAVAL_SAMPLE_RATE": (("observability", "sample_ratio"), float),
    }
    for variable, (path, converter) in numeric_fields.items():
        if variable in environ:
            try:
                assign(path, converter(environ[variable]))
            except ValueError as exc:
                raise PravalConfigurationError(
                    f"{variable} has an invalid numeric value"
                ) from exc
    for variable, signal in (
        ("OTEL_TRACES_EXPORTER", "traces"),
        ("OTEL_METRICS_EXPORTER", "metrics"),
        ("OTEL_LOGS_EXPORTER", "logs"),
    ):
        if variable in environ and environ[variable].strip().lower() == "none":
            assign(("observability", "otlp", signal), False)
    for variable, field in (
        ("PRAVAL_DEFAULT_PROVIDER", "provider"),
        ("PRAVAL_DEFAULT_MODEL", "model"),
    ):
        if variable in environ:
            assign(("models", "default", field), environ[variable])
    if "PRAVAL_CAPTURE_CONTENT" in environ:
        assign(
            ("observability", "capture_content"),
            _parse_bool("PRAVAL_CAPTURE_CONTENT", environ["PRAVAL_CAPTURE_CONTENT"]),
        )
    return result


def load_config(
    path: Path | str | None = None,
    *,
    overrides: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> PravalConfig:
    """Load and validate Praval configuration with documented precedence."""
    config_path = Path(path).expanduser().resolve() if path is not None else None
    if config_path is None:
        config_path = discover_config_path()
    data: dict[str, Any] = {}
    if config_path is not None:
        if not config_path.is_file():
            raise PravalConfigurationError(
                f"configuration file not found: {config_path}"
            )
        try:
            with config_path.open("rb") as stream:
                parsed = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise PravalConfigurationError(
                f"cannot load configuration {config_path}: {exc}"
            ) from exc
        data = _deep_merge(data, parsed)
    try:
        environment = os.environ if environ is None else environ
        data = _deep_merge(data, _environment_overrides(environment))
        if overrides:
            data = _deep_merge(data, overrides)
        return PravalConfig.model_validate(data)
    except PravalConfigurationError:
        raise
    except ValueError as exc:
        raise PravalConfigurationError(str(exc)) from exc


_legacy_config: ObservabilityConfig | None = None


def get_legacy_observability_config() -> ObservabilityConfig:
    """Return the cached v0.8.2-compatible observability configuration."""
    global _legacy_config
    if _legacy_config is None:
        _legacy_config = ObservabilityConfig.from_env()
    return _legacy_config


def reset_legacy_observability_config() -> None:
    """Clear compatibility configuration state for tests."""
    global _legacy_config
    _legacy_config = None


__all__ = [
    "AgentProfileConfig",
    "AppConfig",
    "EvalConfig",
    "EvalGateConfig",
    "EvalJudgeConfig",
    "EvalSuiteConfig",
    "ModelProfileConfig",
    "ObservabilityConfig",
    "OTLPConfig",
    "PravalConfig",
    "ResolvedAgentConfig",
    "discover_config_path",
    "load_config",
]
