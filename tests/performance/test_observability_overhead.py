"""Measured O5 observability overhead release gates."""

from __future__ import annotations

import hashlib
import os
import statistics
import time
from collections.abc import Callable
from typing import Any

import pytest
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor,
    InMemoryLogRecordExporter,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from praval.config import ObservabilityConfig, PravalConfig
from praval.models.observation import ObservationKind
from praval.observability import configure_observability, shutdown_observability
from praval.runtime_observation import ObservationScope, record_model_facts

_TARGET_WORK_SECONDS = 0.05
_SAMPLES = 9
_SCOPE_BATCH_SIZE = 200


def _fake_provider_work(rounds: int) -> bytes:
    """Deterministic local work standing in for a fast fake provider."""
    digest = b"praval-observability-benchmark" * 128
    for _ in range(rounds):
        digest = hashlib.sha256(digest).digest()
    return digest


def _calibrate_rounds() -> int:
    rounds = 10000
    started = time.perf_counter()
    _fake_provider_work(rounds)
    elapsed = max(time.perf_counter() - started, 0.000001)
    return max(1, int(rounds * _TARGET_WORK_SECONDS / elapsed))


def _duration_ns(operation: Callable[[], Any]) -> int:
    started = time.process_time_ns()
    operation()
    return time.process_time_ns() - started


def _median_duration(operation: Callable[[], Any]) -> int:
    operation()
    return int(statistics.median(_duration_ns(operation) for _ in range(_SAMPLES)))


def _batch(operation: Callable[[], Any]) -> None:
    for _ in range(_SCOPE_BATCH_SIZE):
        operation()


def _incremental_scope_cost(observed: Callable[[], Any]) -> int:
    def empty() -> None:
        return None

    paired_costs: list[float] = []
    for _ in range(_SAMPLES):
        empty_samples: list[int] = []
        observed_samples: list[int] = []
        for operation, samples in (
            (empty, empty_samples),
            (observed, observed_samples),
            (observed, observed_samples),
            (empty, empty_samples),
        ):
            samples.append(_duration_ns(lambda: _batch(operation)))
        paired_costs.append(
            max(
                0.0,
                statistics.mean(observed_samples) - statistics.mean(empty_samples),
            )
            / _SCOPE_BATCH_SIZE
        )
    return int(statistics.median(paired_costs))


def _overhead_percent(baseline_ns: int, observed_ns: int) -> float:
    return max(0.0, ((observed_ns / baseline_ns) - 1) * 100)


def _observation_only() -> None:
    with ObservationScope(kind=ObservationKind.AGENT, agent_name="benchmark-agent"):
        record_model_facts(provider="fake", model="deterministic")


@pytest.mark.performance
def test_noop_and_in_memory_observability_overhead() -> None:
    if os.getenv("PRAVAL_RUN_PERFORMANCE_TESTS") != "1":
        pytest.skip("set PRAVAL_RUN_PERFORMANCE_TESTS=1 for the release benchmark")
    rounds = _calibrate_rounds()

    def provider_work() -> bytes:
        return _fake_provider_work(rounds)

    configure_observability(ObservabilityConfig(enabled=False))
    noop_baseline_ns = _median_duration(provider_work)
    noop_scope_ns = _incremental_scope_cost(_observation_only)
    noop_overhead = _overhead_percent(
        noop_baseline_ns, noop_baseline_ns + noop_scope_ns
    )
    shutdown_observability()

    tracer_provider = TracerProvider(shutdown_on_exit=False)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            InMemorySpanExporter(),
            max_queue_size=4096,
            max_export_batch_size=512,
        )
    )
    metric_reader = InMemoryMetricReader()
    meter_provider = MeterProvider(
        metric_readers=[metric_reader], shutdown_on_exit=False
    )
    logger_provider = LoggerProvider(shutdown_on_exit=False)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(
            InMemoryLogRecordExporter(),
            max_queue_size=4096,
            max_export_batch_size=512,
        )
    )
    configure_observability(
        PravalConfig(observability=ObservabilityConfig(enabled=True)),
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        logger_provider=logger_provider,
    )
    try:
        enabled_baseline_ns = _median_duration(provider_work)
        enabled_scope_ns = _incremental_scope_cost(_observation_only)
        enabled_overhead = _overhead_percent(
            enabled_baseline_ns, enabled_baseline_ns + enabled_scope_ns
        )
    finally:
        shutdown_observability()
        tracer_provider.shutdown()
        meter_provider.shutdown()
        logger_provider.shutdown()

    print(
        {
            "rounds": rounds,
            "noop_baseline_ms": noop_baseline_ns / 1_000_000,
            "noop_scope_ms": noop_scope_ns / 1_000_000,
            "noop_overhead_percent": noop_overhead,
            "enabled_baseline_ms": enabled_baseline_ns / 1_000_000,
            "enabled_scope_ms": enabled_scope_ns / 1_000_000,
            "enabled_overhead_percent": enabled_overhead,
        }
    )
    assert noop_overhead < 2.0
    assert enabled_overhead < 5.0
