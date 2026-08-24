"""OpenTelemetry lifecycle and ownership contracts."""

import subprocess
import sys
import time
from pathlib import Path

import pytest

from praval.config import ObservabilityConfig, PravalConfig
from praval.core.exceptions import PravalConfigurationError
from praval.observability.lifecycle import (
    ObservabilityHandle,
    _OwnedComponent,
    configure_observability,
    force_flush,
    get_logger,
    get_meter,
    get_tracer,
    shutdown_observability,
)


class FakeProvider:
    """Application-owned provider with observable lifecycle methods."""

    def __init__(self) -> None:
        self.flush_calls = 0
        self.shutdown_calls = 0

    def get_tracer(self, *args):
        return ("tracer", args)

    def get_meter(self, *args):
        return ("meter", args)

    def get_logger(self, *args):
        return ("logger", args)

    def force_flush(self, timeout_millis=None):
        self.flush_calls += 1
        return True

    def shutdown(self):
        self.shutdown_calls += 1


def test_application_owned_providers_are_used_but_not_closed() -> None:
    tracer_provider = FakeProvider()
    meter_provider = FakeProvider()
    logger_provider = FakeProvider()

    handle = configure_observability(
        service_name="host-service",
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        logger_provider=logger_provider,
    )

    assert handle.owned_signals == frozenset()
    assert get_tracer()[0] == "tracer"
    assert get_meter()[0] == "meter"
    assert get_logger()[0] == "logger"
    assert force_flush() is True
    assert shutdown_observability() is True
    for provider in (tracer_provider, meter_provider, logger_provider):
        assert provider.flush_calls == 0
        assert provider.shutdown_calls == 0


def test_repeated_identical_setup_is_idempotent_and_different_setup_fails() -> None:
    providers = (FakeProvider(), FakeProvider(), FakeProvider())
    first = configure_observability(
        service_name="service",
        tracer_provider=providers[0],
        meter_provider=providers[1],
        logger_provider=providers[2],
    )
    second = configure_observability(
        service_name="service",
        tracer_provider=providers[0],
        meter_provider=providers[1],
        logger_provider=providers[2],
    )

    assert second is first
    with pytest.raises(PravalConfigurationError, match="already configured"):
        configure_observability(
            service_name="different",
            tracer_provider=providers[0],
            meter_provider=providers[1],
            logger_provider=providers[2],
        )


def test_praval_owned_components_flush_and_shutdown_once() -> None:
    provider = FakeProvider()
    handle = ObservabilityHandle(
        config=PravalConfig(
            observability=ObservabilityConfig(enabled=True, flush_timeout_millis=100)
        ),
        tracer_provider=provider,
        meter_provider=provider,
        logger_provider=provider,
        owned_signals=frozenset({"traces"}),
        _owned_components=(_OwnedComponent("traces", provider),),
    )

    assert handle.shutdown() is True
    assert provider.flush_calls == 1
    assert provider.shutdown_calls == 1
    assert handle.shutdown() is True
    assert provider.flush_calls == 1
    assert provider.shutdown_calls == 1


def test_trace_only_pipeline_uses_official_sdk_and_batch_processor(monkeypatch) -> None:
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    monkeypatch.setattr(
        "praval.observability.lifecycle._exporter",
        lambda signal, config: exporter,
    )
    handle = configure_observability(
        service_name="managed-service",
        otlp_endpoint="http://collector:4318",
        traces_enabled=True,
        metrics_enabled=False,
        logs_enabled=False,
    )

    with get_tracer().start_as_current_span("managed-operation"):
        pass
    assert force_flush(timeout_millis=500) is True
    assert [span.name for span in exporter.get_finished_spans()] == [
        "managed-operation"
    ]
    assert handle.owned_signals == frozenset({"traces"})
    assert shutdown_observability(timeout_millis=500) is True


def test_lifecycle_timeout_is_bounded() -> None:
    class SlowProvider(FakeProvider):
        def force_flush(self, timeout_millis=None):
            time.sleep(0.2)
            return True

    provider = SlowProvider()
    handle = ObservabilityHandle(
        config=PravalConfig(observability=ObservabilityConfig(enabled=True)),
        tracer_provider=provider,
        meter_provider=provider,
        logger_provider=provider,
        owned_signals=frozenset({"traces"}),
        _owned_components=(_OwnedComponent("traces", provider),),
    )
    started = time.monotonic()

    assert handle.force_flush(timeout_millis=20) is False
    assert time.monotonic() - started < 0.15


def test_endpoint_is_rejected_when_host_pipeline_cannot_attach(monkeypatch) -> None:
    monkeypatch.setattr(
        "praval.observability.lifecycle._exporter", lambda signal, config: object()
    )
    config = PravalConfig(
        observability=ObservabilityConfig(
            enabled=True,
            otlp={
                "endpoint": "http://collector:4318",
                "traces": True,
                "metrics": False,
                "logs": False,
            },
        )
    )

    with pytest.raises(PravalConfigurationError, match="cannot accept"):
        configure_observability(
            config,
            tracer_provider=FakeProvider(),
            meter_provider=FakeProvider(),
            logger_provider=FakeProvider(),
        )


def test_import_has_no_files_threads_or_runtime_instrumentation(tmp_path: Path) -> None:
    script = """
import json
import threading
from pathlib import Path

before_files = sorted(str(path) for path in Path.cwd().rglob('*'))
before_threads = sorted(thread.name for thread in threading.enumerate())
import praval.observability
from praval.observability.instrumentation import is_instrumented
after_files = sorted(str(path) for path in Path.cwd().rglob('*'))
after_threads = sorted(thread.name for thread in threading.enumerate())
print(json.dumps({
    'files': before_files == after_files,
    'threads': before_threads == after_threads,
    'instrumented': is_instrumented(),
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == (
        '{"files": true, "threads": true, "instrumented": false}'
    )
