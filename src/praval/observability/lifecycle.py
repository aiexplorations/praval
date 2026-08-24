"""Explicit OpenTelemetry provider lifecycle for Praval.

This module imports only the OpenTelemetry API at module load. SDK providers,
processors, and exporters are imported lazily when Praval is asked to own a
pipeline.
"""

from __future__ import annotations

import importlib.metadata
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, cast
from urllib.parse import urlsplit, urlunsplit

from opentelemetry import _logs, metrics, trace

from praval.config import ObservabilityConfig, PravalConfig, load_config
from praval.core.exceptions import PravalConfigurationError

logger = logging.getLogger(__name__)

_INSTRUMENTATION_NAME = "praval"
_active_handle: "ObservabilityHandle | None" = None
_lifecycle_lock = threading.RLock()


@dataclass(frozen=True)
class _OwnedComponent:
    """One provider or processor that Praval may flush and close."""

    signal: str
    component: Any


@dataclass
class ObservabilityHandle:
    """Configured providers and the resources owned by Praval."""

    config: PravalConfig
    tracer_provider: Any
    meter_provider: Any
    logger_provider: Any
    owned_signals: frozenset[str] = frozenset()
    _owned_components: tuple[_OwnedComponent, ...] = field(
        default_factory=tuple, repr=False
    )
    _provider_identity: tuple[int | None, int | None, int | None] = field(
        default=(None, None, None), repr=False
    )
    _active: bool = field(default=True, init=False, repr=False)

    @property
    def active(self) -> bool:
        """Return whether this handle remains active."""
        return self._active

    def force_flush(self, timeout_millis: int | None = None) -> bool:
        """Flush only components owned by Praval within a total time bound."""
        if not self._active:
            return True
        timeout = timeout_millis or self.config.observability.flush_timeout_millis
        return _run_components(
            self._owned_components,
            method_name="force_flush",
            timeout_millis=timeout,
        )

    def shutdown(self, timeout_millis: int | None = None) -> bool:
        """Flush and close only components owned by Praval."""
        if not self._active:
            return True
        timeout = timeout_millis or self.config.observability.flush_timeout_millis
        started = time.monotonic()
        flushed = self.force_flush(timeout)
        elapsed = int((time.monotonic() - started) * 1000)
        remaining = max(1, timeout - elapsed)
        closed = _run_components(
            reversed(self._owned_components),
            method_name="shutdown",
            timeout_millis=remaining,
        )
        self._active = False
        return flushed and closed


def _bounded_call(call: Callable[[], Any], timeout_seconds: float) -> tuple[bool, Any]:
    """Run one lifecycle callback without allowing it to exceed the bound."""
    result: list[Any] = []
    errors: list[BaseException] = []

    def invoke() -> None:
        try:
            result.append(call())
        except BaseException as exc:  # lifecycle must isolate exporter failures
            errors.append(exc)

    worker = threading.Thread(target=invoke, name="praval-otel-lifecycle", daemon=True)
    worker.start()
    worker.join(timeout_seconds)
    if worker.is_alive():
        return False, None
    if errors:
        logger.warning("OpenTelemetry lifecycle operation failed: %s", errors[0])
        return False, None
    return True, result[0] if result else None


def _run_components(
    components: Any,
    *,
    method_name: str,
    timeout_millis: int,
) -> bool:
    """Run one lifecycle method across components under a shared deadline."""
    deadline = time.monotonic() + (timeout_millis / 1000)
    success = True
    for owned in components:
        method = getattr(owned.component, method_name, None)
        if method is None:
            continue
        lifecycle_method = cast(Callable[..., Any], method)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False

        def call(remaining: float = remaining) -> Any:
            if method_name == "force_flush":
                try:
                    return lifecycle_method(
                        timeout_millis=max(1, int(remaining * 1000))
                    )
                except TypeError:
                    return lifecycle_method()
            return lifecycle_method()

        completed, value = _bounded_call(call, remaining)
        success = success and completed and value is not False
    return success


def _package_version() -> str:
    try:
        return importlib.metadata.version("praval")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        return "0+unknown"


def _configuration_with_overrides(
    config: PravalConfig | ObservabilityConfig | None,
    *,
    service_name: str | None,
    service_version: str | None,
    deployment_environment: str | None,
    otlp_endpoint: str | None,
    otlp_protocol: str | None,
    traces_enabled: bool | None,
    metrics_enabled: bool | None,
    logs_enabled: bool | None,
    enable_explicitly: bool,
) -> PravalConfig:
    """Apply explicit lifecycle values over file and environment settings."""
    if isinstance(config, PravalConfig):
        base = config
    elif isinstance(config, ObservabilityConfig):
        base = PravalConfig(observability=config)
    else:
        base = load_config()
    data = base.model_dump(mode="python")
    app = data["app"]
    observability = data["observability"]
    otlp = observability["otlp"]
    if service_name is not None:
        app["service_name"] = service_name
    if service_version is not None:
        app["service_version"] = service_version
    if deployment_environment is not None:
        app["deployment_environment"] = deployment_environment
    if otlp_endpoint is not None:
        otlp["endpoint"] = otlp_endpoint
    if otlp_protocol is not None:
        otlp["protocol"] = otlp_protocol
    for name, value in (
        ("traces", traces_enabled),
        ("metrics", metrics_enabled),
        ("logs", logs_enabled),
    ):
        if value is not None:
            otlp[name] = value
    if enable_explicitly:
        observability["enabled"] = True
    try:
        return PravalConfig.model_validate(data)
    except ValueError as exc:
        raise PravalConfigurationError(str(exc)) from exc


def _resource(config: PravalConfig) -> Any:
    from opentelemetry.sdk.resources import Resource

    attributes: dict[str, str] = {
        "service.name": config.app.service_name,
        "telemetry.sdk.language": "python",
        "praval.version": _package_version(),
    }
    if config.app.service_version:
        attributes["service.version"] = config.app.service_version
    if config.app.deployment_environment:
        attributes["deployment.environment.name"] = config.app.deployment_environment
    return Resource.create(attributes)


def _sampler(config: ObservabilityConfig) -> Any:
    from opentelemetry.sdk.trace.sampling import (
        ALWAYS_OFF,
        ALWAYS_ON,
        ParentBased,
        TraceIdRatioBased,
    )

    if config.sampling == "always_on":
        return ALWAYS_ON
    if config.sampling == "always_off":
        return ALWAYS_OFF
    return ParentBased(TraceIdRatioBased(config.sample_ratio))


def _headers(config: ObservabilityConfig) -> dict[str, str] | None:
    variable = config.otlp.headers_env
    if variable is None:
        return None
    raw = os.getenv(variable)
    if raw is None:
        raise PravalConfigurationError(
            f"OTLP headers environment variable is not set: {variable}"
        )
    headers: dict[str, str] = {}
    for item in raw.split(","):
        key, separator, value = item.partition("=")
        if not separator or not key.strip():
            raise PravalConfigurationError(f"invalid OTLP header in {variable}")
        headers[key.strip()] = value.strip()
    return headers


def _http_signal_endpoint(endpoint: str, signal: str) -> str:
    """Append the OTLP HTTP signal path when given a collector base URL."""
    parsed = urlsplit(endpoint)
    path = parsed.path.rstrip("/")
    if path.endswith(("/v1/traces", "/v1/metrics", "/v1/logs")):
        path = path.rsplit("/v1/", 1)[0]
    path = f"{path}/v1/{signal}"
    return urlunsplit(
        (parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment)
    )


def _exporter(signal: str, config: ObservabilityConfig) -> Any:
    endpoint = config.otlp.endpoint
    if endpoint is None:
        raise PravalConfigurationError("an OTLP endpoint is required")
    headers = _headers(config)
    try:
        if config.otlp.protocol == "http/protobuf":
            if signal == "traces":
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )

                exporter_class: Any = OTLPSpanExporter
            elif signal == "metrics":
                from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
                    OTLPMetricExporter,
                )

                exporter_class = OTLPMetricExporter
            else:
                from opentelemetry.exporter.otlp.proto.http._log_exporter import (
                    OTLPLogExporter,
                )

                exporter_class = OTLPLogExporter
            return exporter_class(
                endpoint=_http_signal_endpoint(endpoint, signal),
                headers=headers,
                timeout=config.otlp.export_timeout_millis / 1000,
            )
        if signal == "traces":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter as GRPCSpanExporter,
            )

            exporter_class = GRPCSpanExporter
        elif signal == "metrics":
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                OTLPMetricExporter as GRPCMetricExporter,
            )

            exporter_class = GRPCMetricExporter
        else:
            from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
                OTLPLogExporter as GRPCLogExporter,
            )

            exporter_class = GRPCLogExporter
        return exporter_class(
            endpoint=endpoint,
            headers=headers,
            timeout=config.otlp.export_timeout_millis / 1000,
        )
    except ImportError as exc:
        raise PravalConfigurationError(
            "Praval-managed telemetry requires the observability extra: "
            "pip install 'praval[observability]'"
        ) from exc


def _build_providers(
    config: PravalConfig,
    tracer_provider: Any | None,
    meter_provider: Any | None,
    logger_provider: Any | None,
) -> tuple[Any, Any, Any, tuple[_OwnedComponent, ...], frozenset[str]]:
    """Create or attach the selected OpenTelemetry pipelines."""
    observability = config.observability
    otlp = observability.otlp
    endpoint = otlp.endpoint
    if endpoint and not observability.enabled:
        raise PravalConfigurationError(
            "an OTLP endpoint cannot be configured while observability is disabled"
        )
    if endpoint and not any((otlp.traces, otlp.metrics, otlp.logs)):
        raise PravalConfigurationError(
            "an OTLP endpoint requires at least one enabled signal"
        )
    if observability.local.enabled:
        raise PravalConfigurationError(
            "the local diagnostic exporter is not available until work package O5"
        )
    if not observability.enabled:
        return (
            trace.NoOpTracerProvider(),
            metrics.NoOpMeterProvider(),
            _logs.NoOpLoggerProvider(),
            (),
            frozenset(),
        )

    try:
        resource = _resource(config)
    except ImportError as exc:
        if any(
            provider is None
            for provider in (tracer_provider, meter_provider, logger_provider)
        ):
            raise PravalConfigurationError(
                "Praval-owned providers require the observability extra: "
                "pip install 'praval[observability]'"
            ) from exc
        resource = None

    owned: list[_OwnedComponent] = []
    owned_signals: set[str] = set()

    if otlp.traces:
        trace_exporter = _exporter("traces", observability) if endpoint else None
        if tracer_provider is None:
            try:
                from opentelemetry.sdk.trace import TracerProvider
                from opentelemetry.sdk.trace.export import BatchSpanProcessor
            except ImportError as exc:
                raise PravalConfigurationError(
                    "Praval-owned tracing requires the observability extra"
                ) from exc
            tracer_provider = TracerProvider(
                resource=resource,
                sampler=_sampler(observability),
                shutdown_on_exit=False,
            )
            if trace_exporter is not None:
                tracer_provider.add_span_processor(
                    BatchSpanProcessor(
                        trace_exporter,
                        max_queue_size=otlp.max_queue_size,
                        max_export_batch_size=otlp.max_export_batch_size,
                        schedule_delay_millis=otlp.schedule_delay_millis,
                        export_timeout_millis=otlp.export_timeout_millis,
                    )
                )
            owned.append(_OwnedComponent("traces", tracer_provider))
            owned_signals.add("traces")
        elif trace_exporter is not None:
            add_processor = getattr(tracer_provider, "add_span_processor", None)
            if add_processor is None:
                raise PravalConfigurationError(
                    "the supplied tracer provider cannot accept an OTLP processor"
                )
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            span_processor = BatchSpanProcessor(
                trace_exporter,
                max_queue_size=otlp.max_queue_size,
                max_export_batch_size=otlp.max_export_batch_size,
                schedule_delay_millis=otlp.schedule_delay_millis,
                export_timeout_millis=otlp.export_timeout_millis,
            )
            add_processor(span_processor)
            owned.append(_OwnedComponent("traces", span_processor))
            owned_signals.add("traces")
    else:
        tracer_provider = trace.NoOpTracerProvider()

    if otlp.metrics:
        if meter_provider is not None and endpoint:
            raise PravalConfigurationError(
                "OTLP metric readers cannot be attached to an existing meter provider; "
                "configure the reader in the host application or let Praval own it"
            )
        if meter_provider is None:
            try:
                from opentelemetry.sdk.metrics import MeterProvider
                from opentelemetry.sdk.metrics.export import (
                    PeriodicExportingMetricReader,
                )
            except ImportError as exc:
                raise PravalConfigurationError(
                    "Praval-owned metrics require the observability extra"
                ) from exc
            readers = []
            if endpoint:
                readers.append(
                    PeriodicExportingMetricReader(
                        _exporter("metrics", observability),
                        export_interval_millis=otlp.metric_export_interval_millis,
                        export_timeout_millis=otlp.export_timeout_millis,
                    )
                )
            meter_provider = MeterProvider(
                metric_readers=readers,
                resource=resource,
                shutdown_on_exit=False,
            )
            owned.append(_OwnedComponent("metrics", meter_provider))
            owned_signals.add("metrics")
    else:
        meter_provider = metrics.NoOpMeterProvider()

    if otlp.logs:
        log_exporter = _exporter("logs", observability) if endpoint else None
        if logger_provider is None:
            try:
                from opentelemetry.sdk._logs import LoggerProvider
                from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
            except ImportError as exc:
                raise PravalConfigurationError(
                    "Praval-owned logs require the observability extra"
                ) from exc
            logger_provider = LoggerProvider(
                resource=resource,
                shutdown_on_exit=False,
            )
            if log_exporter is not None:
                logger_provider.add_log_record_processor(
                    BatchLogRecordProcessor(
                        log_exporter,
                        max_queue_size=otlp.max_queue_size,
                        max_export_batch_size=otlp.max_export_batch_size,
                        schedule_delay_millis=otlp.schedule_delay_millis,
                        export_timeout_millis=otlp.export_timeout_millis,
                    )
                )
            owned.append(_OwnedComponent("logs", logger_provider))
            owned_signals.add("logs")
        elif log_exporter is not None:
            add_processor = getattr(logger_provider, "add_log_record_processor", None)
            if add_processor is None:
                raise PravalConfigurationError(
                    "the supplied logger provider cannot accept an OTLP processor"
                )
            from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

            log_processor = BatchLogRecordProcessor(
                log_exporter,
                max_queue_size=otlp.max_queue_size,
                max_export_batch_size=otlp.max_export_batch_size,
                schedule_delay_millis=otlp.schedule_delay_millis,
                export_timeout_millis=otlp.export_timeout_millis,
            )
            add_processor(log_processor)
            owned.append(_OwnedComponent("logs", log_processor))
            owned_signals.add("logs")
    else:
        logger_provider = _logs.NoOpLoggerProvider()

    return (
        tracer_provider,
        meter_provider,
        logger_provider,
        tuple(owned),
        frozenset(owned_signals),
    )


def configure_observability(
    config: PravalConfig | ObservabilityConfig | None = None,
    *,
    service_name: str | None = None,
    service_version: str | None = None,
    deployment_environment: str | None = None,
    otlp_endpoint: str | None = None,
    otlp_protocol: str | None = None,
    traces_enabled: bool | None = None,
    metrics_enabled: bool | None = None,
    logs_enabled: bool | None = None,
    tracer_provider: Any | None = None,
    meter_provider: Any | None = None,
    logger_provider: Any | None = None,
) -> ObservabilityHandle:
    """Configure Praval telemetry explicitly and return its ownership handle."""
    explicit = any(
        value is not None
        for value in (
            service_name,
            service_version,
            deployment_environment,
            otlp_endpoint,
            otlp_protocol,
            traces_enabled,
            metrics_enabled,
            logs_enabled,
            tracer_provider,
            meter_provider,
            logger_provider,
        )
    )
    resolved = _configuration_with_overrides(
        config,
        service_name=service_name,
        service_version=service_version,
        deployment_environment=deployment_environment,
        otlp_endpoint=otlp_endpoint,
        otlp_protocol=otlp_protocol,
        traces_enabled=traces_enabled,
        metrics_enabled=metrics_enabled,
        logs_enabled=logs_enabled,
        enable_explicitly=explicit,
    )
    identity = (
        id(tracer_provider) if tracer_provider is not None else None,
        id(meter_provider) if meter_provider is not None else None,
        id(logger_provider) if logger_provider is not None else None,
    )
    global _active_handle
    with _lifecycle_lock:
        if _active_handle is not None and _active_handle.active:
            if (
                _active_handle.config == resolved
                and _active_handle._provider_identity == identity
            ):
                return _active_handle
            raise PravalConfigurationError(
                "observability is already configured with different settings"
            )
        providers = _build_providers(
            resolved, tracer_provider, meter_provider, logger_provider
        )
        _active_handle = ObservabilityHandle(
            config=resolved,
            tracer_provider=providers[0],
            meter_provider=providers[1],
            logger_provider=providers[2],
            _owned_components=providers[3],
            owned_signals=providers[4],
            _provider_identity=identity,
        )
        return _active_handle


def configure_tracing(
    *,
    service_name: str,
    otlp_endpoint: str,
    protocol: str = "http/protobuf",
) -> ObservabilityHandle:
    """Configure a Praval-owned trace-only OTLP pipeline."""
    return configure_observability(
        service_name=service_name,
        otlp_endpoint=otlp_endpoint,
        otlp_protocol=protocol,
        traces_enabled=True,
        metrics_enabled=False,
        logs_enabled=False,
    )


def get_tracer(name: str = _INSTRUMENTATION_NAME) -> trace.Tracer:
    """Return an official OpenTelemetry tracer from the active provider."""
    handle = _active_handle
    if handle is None or not handle.active:
        return trace.get_tracer(name, _package_version())
    return cast(
        trace.Tracer,
        handle.tracer_provider.get_tracer(name, _package_version()),
    )


def get_meter(name: str = _INSTRUMENTATION_NAME) -> metrics.Meter:
    """Return an official OpenTelemetry meter from the active provider."""
    handle = _active_handle
    if handle is None or not handle.active:
        return metrics.get_meter(name, _package_version())
    return cast(
        metrics.Meter,
        handle.meter_provider.get_meter(name, _package_version()),
    )


def get_logger(name: str = _INSTRUMENTATION_NAME) -> Any:
    """Return an official OpenTelemetry logger from the active provider."""
    handle = _active_handle
    if handle is None or not handle.active:
        return _logs.get_logger(name, _package_version())
    return handle.logger_provider.get_logger(name, _package_version())


def force_flush(timeout_millis: int | None = None) -> bool:
    """Flush the active Praval-owned telemetry resources."""
    handle = _active_handle
    if handle is None:
        return True
    return handle.force_flush(timeout_millis)


def shutdown_observability(timeout_millis: int | None = None) -> bool:
    """Flush and shut down only the active resources owned by Praval."""
    global _active_handle
    with _lifecycle_lock:
        handle = _active_handle
        if handle is None:
            return True
        result = handle.shutdown(timeout_millis)
        _active_handle = None
        return result


def _reset_observability_for_tests() -> None:
    """Reset explicit lifecycle state; for test isolation only."""
    shutdown_observability(timeout_millis=100)


__all__ = [
    "ObservabilityHandle",
    "configure_observability",
    "configure_tracing",
    "force_flush",
    "get_logger",
    "get_meter",
    "get_tracer",
    "shutdown_observability",
]
