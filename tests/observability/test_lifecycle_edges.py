"""Edge coverage for explicit OpenTelemetry configuration and ownership."""

import time

import pytest
from opentelemetry import _logs, metrics, trace
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import LogExporter, LogRecordExportResult
from opentelemetry.sdk.metrics.export import MetricExporter, MetricExportResult
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from praval.config import ObservabilityConfig, PravalConfig
from praval.core.exceptions import PravalConfigurationError
from praval.observability import lifecycle
from praval.observability.health import (
    get_telemetry_health,
    reset_telemetry_health,
)
from praval.observability.lifecycle import (
    ObservabilityHandle,
    _build_providers,
    _configuration_with_overrides,
    _exporter,
    _headers,
    _http_signal_endpoint,
    _OwnedComponent,
    _resource,
    _run_components,
    _sampler,
    configure_observability,
    configure_tracing,
    force_flush,
    get_logger,
    get_meter,
    get_tracer,
    shutdown_observability,
)


class MemoryMetricExporter(MetricExporter):
    """Non-network metric exporter for lifecycle tests."""

    def export(self, metrics_data, timeout_millis=10000, **kwargs):
        return MetricExportResult.SUCCESS

    def force_flush(self, timeout_millis=10000):
        return True

    def shutdown(self, timeout_millis=30000, **kwargs):
        return None


class MemoryLogExporter(LogExporter):
    """Non-network log exporter for lifecycle tests."""

    def export(self, batch):
        return LogRecordExportResult.SUCCESS

    def force_flush(self, timeout_millis=10000):
        return True

    def shutdown(self):
        return None


def _enabled_config(**otlp_overrides) -> PravalConfig:
    otlp = {"traces": True, "metrics": True, "logs": True, **otlp_overrides}
    return PravalConfig(observability=ObservabilityConfig(enabled=True, otlp=otlp))


def test_configuration_override_paths_and_validation() -> None:
    config = _configuration_with_overrides(
        ObservabilityConfig(enabled=False),
        service_name="service",
        service_version="1.0",
        deployment_environment="test",
        otlp_endpoint="http://collector:4318",
        otlp_protocol="grpc",
        traces_enabled=True,
        metrics_enabled=False,
        logs_enabled=False,
        enable_explicitly=True,
    )
    assert config.app.model_dump() == {
        "service_name": "service",
        "service_version": "1.0",
        "deployment_environment": "test",
    }
    assert config.observability.enabled is True
    assert config.observability.otlp.protocol == "grpc"
    assert config.observability.otlp.metrics is False

    with pytest.raises(PravalConfigurationError):
        _configuration_with_overrides(
            config,
            service_name=None,
            service_version=None,
            deployment_environment=None,
            otlp_endpoint=None,
            otlp_protocol="invalid",
            traces_enabled=None,
            metrics_enabled=None,
            logs_enabled=None,
            enable_explicitly=False,
        )


def test_resource_sampler_headers_and_http_endpoint(monkeypatch) -> None:
    config = PravalConfig(
        app={
            "service_name": "service",
            "service_version": "1.2",
            "deployment_environment": "staging",
        },
        observability=ObservabilityConfig(enabled=True),
    )
    attributes = _resource(config).attributes
    assert attributes["service.name"] == "service"
    assert attributes["service.version"] == "1.2"
    assert attributes["deployment.environment.name"] == "staging"

    assert _sampler(ObservabilityConfig(sampling="always_on")).get_description()
    assert _sampler(ObservabilityConfig(sampling="always_off")).get_description()
    assert _sampler(ObservabilityConfig(sample_ratio=0.4)).get_description()

    assert _headers(ObservabilityConfig()) is None
    header_config = ObservabilityConfig(otlp={"headers_env": "OTLP_HEADERS"})
    with pytest.raises(PravalConfigurationError, match="not set"):
        _headers(header_config)
    monkeypatch.setenv("OTLP_HEADERS", "authorization=secret,x-tenant=test")
    assert _headers(header_config) == {
        "authorization": "secret",
        "x-tenant": "test",
    }
    monkeypatch.setenv("OTLP_HEADERS", "invalid")
    with pytest.raises(PravalConfigurationError, match="invalid OTLP header"):
        _headers(header_config)

    assert _http_signal_endpoint("http://collector:4318", "traces") == (
        "http://collector:4318/v1/traces"
    )
    assert (
        _http_signal_endpoint("http://collector:4318/v1/logs?tenant=a", "metrics")
        == "http://collector:4318/v1/metrics?tenant=a"
    )


@pytest.mark.parametrize("protocol", ["http/protobuf", "grpc"])
@pytest.mark.parametrize("signal", ["traces", "metrics", "logs"])
def test_official_exporters_construct_for_each_signal(
    protocol: str, signal: str
) -> None:
    config = ObservabilityConfig(
        enabled=True,
        otlp={"endpoint": "http://127.0.0.1:4318", "protocol": protocol},
    )
    exporter = _exporter(signal, config)
    assert exporter is not None
    exporter.shutdown()


def test_exporter_requires_endpoint() -> None:
    with pytest.raises(PravalConfigurationError, match="endpoint"):
        _exporter("traces", ObservabilityConfig(enabled=True))


def test_optional_health_and_signal_helpers_tolerate_missing_sdk_modules(
    monkeypatch,
) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "praval.observability.signals", None)
    lifecycle._reset_signal_state()
    lifecycle._initialize_signal_state()
    monkeypatch.setitem(sys.modules, "praval.observability.health", None)
    lifecycle._reset_health_state()
    lifecycle._record_lifecycle_failure("traces")
    with pytest.raises(PravalConfigurationError, match="observability extra"):
        lifecycle._local_span_exporter(
            ObservabilityConfig(enabled=True, local={"enabled": True})
        )


def test_provider_configuration_rejects_incompatible_combinations() -> None:
    with pytest.raises(PravalConfigurationError, match="disabled"):
        _build_providers(
            PravalConfig(
                observability=ObservabilityConfig(
                    enabled=False,
                    otlp={"endpoint": "http://collector:4318"},
                )
            ),
            None,
            None,
            None,
        )
    with pytest.raises(PravalConfigurationError, match="one enabled signal"):
        _build_providers(
            PravalConfig(
                observability=ObservabilityConfig(
                    enabled=True,
                    otlp={
                        "endpoint": "http://collector:4318",
                        "traces": False,
                        "metrics": False,
                        "logs": False,
                    },
                )
            ),
            None,
            None,
            None,
        )
    with pytest.raises(PravalConfigurationError, match="requires observability"):
        _build_providers(
            PravalConfig(
                observability=ObservabilityConfig(
                    enabled=False, local={"enabled": True}
                )
            ),
            None,
            None,
            None,
        )
    with pytest.raises(PravalConfigurationError, match="requires traces"):
        _build_providers(
            PravalConfig(
                observability=ObservabilityConfig(
                    enabled=True,
                    otlp={"traces": False},
                    local={"enabled": True},
                )
            ),
            None,
            None,
            None,
        )

    providers = _build_providers(PravalConfig(), None, None, None)
    assert isinstance(providers[0], trace.NoOpTracerProvider)
    assert isinstance(providers[1], metrics.NoOpMeterProvider)
    assert isinstance(providers[2], _logs.NoOpLoggerProvider)


def test_managed_all_signal_providers_without_exporters() -> None:
    handle = configure_observability(service_name="managed")
    assert handle.owned_signals == frozenset({"traces", "metrics", "logs"})
    assert force_flush(500) is True
    assert shutdown_observability(500) is True


def test_local_diagnostic_exporter_is_batched_and_lifecycle_bound(tmp_path) -> None:
    from praval.observability.storage import get_trace_store

    handle = configure_observability(
        PravalConfig(
            observability=ObservabilityConfig(
                enabled=True,
                otlp={
                    "traces": True,
                    "metrics": False,
                    "logs": False,
                    "schedule_delay_millis": 10000,
                },
                local={
                    "enabled": True,
                    "path": str(tmp_path / "local.db"),
                    "max_traces": 10,
                    "max_age_days": 7,
                },
            )
        )
    )
    with get_tracer().start_as_current_span("local-operation") as span:
        trace_id = format(span.get_span_context().trace_id, "032x")

    assert force_flush(500) is True
    assert handle.local_trace_store is get_trace_store()
    assert [row["name"] for row in get_trace_store().get_trace(trace_id)] == [
        "local-operation"
    ]
    assert shutdown_observability(500) is True
    with pytest.raises(PravalConfigurationError, match="not enabled"):
        get_trace_store()


def test_local_and_otlp_exporters_receive_the_same_span(monkeypatch, tmp_path) -> None:
    from praval.observability.storage import get_trace_store

    otlp_exporter = InMemorySpanExporter()
    monkeypatch.setattr(
        lifecycle,
        "_exporter",
        lambda signal, config: otlp_exporter,
    )
    configure_observability(
        PravalConfig(
            observability=ObservabilityConfig(
                enabled=True,
                otlp={
                    "endpoint": "http://collector:4318",
                    "traces": True,
                    "metrics": False,
                    "logs": False,
                },
                local={"enabled": True, "path": str(tmp_path / "local.db")},
            )
        )
    )
    with get_tracer().start_as_current_span("dual-export") as span:
        trace_id = format(span.get_span_context().trace_id, "032x")

    assert force_flush(500) is True
    assert [span.name for span in otlp_exporter.get_finished_spans()] == ["dual-export"]
    assert [row["name"] for row in get_trace_store().get_trace(trace_id)] == [
        "dual-export"
    ]


def test_managed_all_signal_export_pipeline(monkeypatch) -> None:
    exporters = {
        "traces": InMemorySpanExporter(),
        "metrics": MemoryMetricExporter(),
        "logs": MemoryLogExporter(),
    }
    monkeypatch.setattr(
        lifecycle,
        "_exporter",
        lambda signal, config: exporters[signal],
    )
    handle = configure_observability(
        service_name="managed",
        otlp_endpoint="http://collector:4318",
    )
    with get_tracer().start_as_current_span("operation"):
        pass
    assert handle.owned_signals == frozenset({"traces", "metrics", "logs"})
    assert force_flush(500) is True
    assert shutdown_observability(500) is True


def test_exporter_downtime_is_visible_without_changing_application_result(
    monkeypatch,
    caplog,
) -> None:
    class UnavailableSpanExporter:
        def export(self, spans):
            raise ConnectionError("collector unavailable with token=private")

        def force_flush(self, timeout_millis=30000):
            return True

        def shutdown(self):
            return None

    reset_telemetry_health()
    monkeypatch.setattr(
        lifecycle,
        "_exporter",
        lambda signal, config: UnavailableSpanExporter(),
    )
    configure_observability(
        service_name="downtime-test",
        otlp_endpoint="http://collector:4318",
        traces_enabled=True,
        metrics_enabled=False,
        logs_enabled=False,
    )

    with get_tracer().start_as_current_span("application-operation"):
        result = "unchanged"
    assert result == "unchanged"
    assert force_flush(500) is True

    health = get_telemetry_health()["traces"]
    assert health.export_attempts == 1
    assert health.export_failures == 1
    assert health.export_exceptions == 1
    assert "token=private" not in caplog.text
    assert "OpenTelemetry export failed" in caplog.text
    assert shutdown_observability(500) is True


def test_host_trace_and_log_processors_are_owned_but_providers_are_not(
    monkeypatch,
) -> None:
    exporters = {
        "traces": InMemorySpanExporter(),
        "logs": MemoryLogExporter(),
    }
    monkeypatch.setattr(
        lifecycle,
        "_exporter",
        lambda signal, config: exporters[signal],
    )
    tracer_provider = TracerProvider(shutdown_on_exit=False)
    logger_provider = LoggerProvider(shutdown_on_exit=False)
    providers = _build_providers(
        _enabled_config(endpoint="http://collector:4318", metrics=False),
        tracer_provider,
        None,
        logger_provider,
    )
    owned = providers[3]
    assert {component.signal for component in owned} == {"traces", "logs"}
    assert all(component.component is not tracer_provider for component in owned)
    assert all(component.component is not logger_provider for component in owned)
    assert _run_components(owned, method_name="shutdown", timeout_millis=500)
    tracer_provider.shutdown()
    logger_provider.shutdown()


def test_host_metric_and_logger_attachment_failures(monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "_exporter", lambda signal, config: object())
    with pytest.raises(PravalConfigurationError, match="metric readers"):
        _build_providers(
            _enabled_config(endpoint="http://collector:4318", traces=False, logs=False),
            None,
            object(),
            None,
        )
    with pytest.raises(PravalConfigurationError, match="logger provider"):
        _build_providers(
            _enabled_config(
                endpoint="http://collector:4318", traces=False, metrics=False
            ),
            None,
            None,
            object(),
        )


def test_lifecycle_error_fallback_and_inactive_paths() -> None:
    class ErrorComponent:
        def force_flush(self, timeout_millis=None):
            raise RuntimeError("flush failed")

    class NoTimeoutComponent:
        def force_flush(self):
            return True

    class FalseComponent:
        def force_flush(self, timeout_millis=None):
            return False

        def shutdown(self):
            return None

    assert not _run_components(
        (_OwnedComponent("traces", ErrorComponent()),),
        method_name="force_flush",
        timeout_millis=100,
    )
    assert _run_components(
        (_OwnedComponent("traces", NoTimeoutComponent()),),
        method_name="force_flush",
        timeout_millis=100,
    )
    assert _run_components(
        (_OwnedComponent("traces", object()),),
        method_name="force_flush",
        timeout_millis=100,
    )
    component = FalseComponent()
    handle = ObservabilityHandle(
        config=_enabled_config(),
        tracer_provider=component,
        meter_provider=component,
        logger_provider=component,
        _owned_components=(_OwnedComponent("traces", component),),
    )
    assert handle.shutdown(100) is False
    assert handle.force_flush(100) is True


def test_lifecycle_failures_are_counted_without_leaking_error_text(caplog) -> None:
    class ErrorComponent:
        def force_flush(self, timeout_millis=None):
            raise RuntimeError("api_key=private-lifecycle-secret")

    reset_telemetry_health()
    assert not _run_components(
        (_OwnedComponent("logs", ErrorComponent()),),
        method_name="force_flush",
        timeout_millis=100,
    )

    assert get_telemetry_health()["logs"].lifecycle_failures == 1
    assert "RuntimeError" in caplog.text
    assert "private-lifecycle-secret" not in caplog.text


def test_public_no_configuration_fallbacks_and_trace_convenience(monkeypatch) -> None:
    assert get_tracer("fallback") is not None
    assert get_meter("fallback") is not None
    assert get_logger("fallback") is not None
    assert force_flush() is True
    assert shutdown_observability() is True

    exporter = InMemorySpanExporter()
    monkeypatch.setattr(lifecycle, "_exporter", lambda signal, config: exporter)
    handle = configure_tracing(
        service_name="trace-service",
        otlp_endpoint="http://collector:4318",
    )
    assert handle.owned_signals == frozenset({"traces"})


def test_shared_deadline_exhaustion() -> None:
    class SlowComponent:
        def shutdown(self):
            time.sleep(0.03)

    components = (
        _OwnedComponent("traces", SlowComponent()),
        _OwnedComponent("logs", SlowComponent()),
    )
    assert (
        _run_components(components, method_name="shutdown", timeout_millis=10) is False
    )
