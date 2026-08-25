"""Black-box OTLP trace, metric, and log receipt by a real Collector."""

from __future__ import annotations

import json
import os
import socket
import time
import uuid
from pathlib import Path

import pytest

from praval.config import AppConfig, ObservabilityConfig, PravalConfig
from praval.models.observation import ObservationKind
from praval.observability import (
    configure_observability,
    force_flush,
    shutdown_observability,
)
from praval.runtime_observation import ObservationScope, record_model_facts


def _collector_endpoint(protocol: str) -> str:
    variable = (
        "PRAVAL_TEST_OTLP_HTTP_ENDPOINT"
        if protocol == "http/protobuf"
        else "PRAVAL_TEST_OTLP_GRPC_ENDPOINT"
    )
    default = (
        "http://127.0.0.1:14318" if protocol == "http/protobuf" else "127.0.0.1:14317"
    )
    return os.getenv(variable, default)


def _collector_available(endpoint: str) -> bool:
    target = endpoint.removeprefix("http://").removeprefix("https://")
    host, separator, port = target.rpartition(":")
    if not separator:
        return False
    try:
        with socket.create_connection((host, int(port)), timeout=0.25):
            return True
    except OSError:
        return False


def _wait_for_export(path: Path, needle: str) -> str:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if path.exists():
            payload = path.read_text(encoding="utf-8")
            if needle in payload:
                return payload
        time.sleep(0.1)
    pytest.fail(f"Collector output {path.name} did not contain {needle!r}")


@pytest.mark.integration
@pytest.mark.parametrize("protocol", ["http/protobuf", "grpc"])
def test_real_collector_receives_all_signals(protocol: str) -> None:
    output_value = os.getenv("PRAVAL_TEST_OTLP_OUTPUT_DIR")
    endpoint = _collector_endpoint(protocol)
    if output_value is None or not _collector_available(endpoint):
        pytest.skip("the O5 OpenTelemetry Collector fixture is not running")
    output_dir = Path(output_value)
    service_name = f"praval-o5-{protocol.split('/')[0]}-{uuid.uuid4().hex}"
    configure_observability(
        PravalConfig(
            app=AppConfig(service_name=service_name),
            observability=ObservabilityConfig(
                enabled=True,
                sampling="always_on",
                otlp={
                    "endpoint": endpoint,
                    "protocol": protocol,
                    "traces": True,
                    "metrics": True,
                    "logs": True,
                    "schedule_delay_millis": 100,
                    "metric_export_interval_millis": 100,
                    "export_timeout_millis": 2000,
                },
            ),
        )
    )
    try:
        with ObservationScope(
            kind=ObservationKind.AGENT,
            agent_name="collector-agent",
        ):
            record_model_facts(
                provider="test",
                model="collector-model",
                usage={"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
            )
        assert force_flush(5000) is True
    finally:
        shutdown_observability(5000)

    traces = _wait_for_export(output_dir / "traces.json", service_name)
    metrics = _wait_for_export(output_dir / "metrics.json", service_name)
    logs = _wait_for_export(output_dir / "logs.json", service_name)
    assert "praval.agent.invoke" in traces
    assert "praval.execution.invocations" in metrics
    assert "Praval execution completed" in logs
    for payload in (traces, metrics, logs):
        for line in payload.splitlines():
            if line.strip():
                assert isinstance(json.loads(line), dict)
