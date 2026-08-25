"""Official OpenTelemetry trace-core and compatibility contract tests."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from opentelemetry import trace
from opentelemetry.trace import SpanKind, StatusCode, TraceFlags

from praval.config import AppConfig, ObservabilityConfig, OTLPConfig, PravalConfig
from praval.observability import configure_observability, shutdown_observability
from praval.observability.tracing import TraceContext, get_current_span, get_tracer
from praval.observability.tracing.tracer import generate_span_id, generate_trace_id

sdk_trace = pytest.importorskip("opentelemetry.sdk.trace")
sdk_export = pytest.importorskip("opentelemetry.sdk.trace.export")
in_memory_export = pytest.importorskip(
    "opentelemetry.sdk.trace.export.in_memory_span_exporter"
)


class TraceHarness:
    """Praval-owned provider with an official in-memory exporter."""

    def __init__(
        self,
        *,
        sampling: str = "always_on",
        sample_ratio: float = 1.0,
    ) -> None:
        config = PravalConfig(
            app=AppConfig(
                service_name="trace-core-test",
                service_version="0.8.3-test",
                deployment_environment="test",
            ),
            observability=ObservabilityConfig(
                enabled=True,
                sampling=sampling,
                sample_ratio=sample_ratio,
                otlp=OTLPConfig(traces=True, metrics=False, logs=False),
            ),
        )
        self.handle = configure_observability(config)
        self.exporter = in_memory_export.InMemorySpanExporter()
        self.handle.tracer_provider.add_span_processor(
            sdk_export.SimpleSpanProcessor(self.exporter)
        )
        self.tracer = get_tracer("praval.trace-core-tests")

    def close(self) -> None:
        """Close the Praval-owned provider."""
        shutdown_observability()


@pytest.fixture
def harness() -> Iterator[TraceHarness]:
    trace_harness = TraceHarness()
    yield trace_harness
    trace_harness.close()


def test_compatibility_names_are_official_opentelemetry_objects() -> None:
    from praval.observability import Span
    from praval.observability import SpanKind as PravalSpanKind
    from praval.observability import SpanStatus, Tracer
    from praval.observability.tracing.span import NoOpSpan

    assert Span is trace.Span
    assert Tracer is trace.Tracer
    assert PravalSpanKind is trace.SpanKind
    assert SpanStatus is trace.StatusCode
    assert NoOpSpan is trace.NonRecordingSpan
    assert isinstance(get_tracer(), trace.Tracer)


def test_trace_core_contains_no_custom_span_or_tracer_implementation() -> None:
    import praval.observability.tracing as tracing_module

    tracing_root = Path(tracing_module.__file__).parent
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in tracing_root.glob("*.py")
    )

    assert "class Span:" not in source
    assert "class Tracer:" not in source
    assert "threading.local" not in source


def test_service_resource_and_parentage_are_exported(harness: TraceHarness) -> None:
    with harness.tracer.start_as_current_span("parent") as parent:
        with harness.tracer.start_as_current_span(
            "child", kind=SpanKind.CLIENT
        ) as child:
            assert get_current_span() is child
            assert (
                child.get_span_context().trace_id == parent.get_span_context().trace_id
            )

    spans = {span.name: span for span in harness.exporter.get_finished_spans()}
    assert spans["child"].parent.span_id == spans["parent"].context.span_id
    assert spans["child"].kind is SpanKind.CLIENT
    assert spans["parent"].resource.attributes["service.name"] == "trace-core-test"
    assert spans["parent"].resource.attributes["service.version"] == "0.8.3-test"
    assert spans["parent"].resource.attributes["deployment.environment.name"] == "test"


def test_context_manager_records_exception_and_error_status(
    harness: TraceHarness,
) -> None:
    with pytest.raises(ValueError, match="trace failure"):
        with harness.tracer.start_as_current_span("failing-operation"):
            raise ValueError("trace failure")

    span = harness.exporter.get_finished_spans()[0]
    assert span.status.status_code is StatusCode.ERROR
    exception_events = [event for event in span.events if event.name == "exception"]
    assert len(exception_events) == 1
    assert exception_events[0].attributes["exception.type"].endswith("ValueError")
    assert "trace failure" in exception_events[0].attributes["exception.message"]


def test_parent_based_sampler_honors_remote_parent_decision() -> None:
    harness = TraceHarness(
        sampling="parentbased_traceidratio",
        sample_ratio=0.0,
    )
    try:
        with harness.tracer.start_as_current_span("root-not-sampled") as root:
            assert root.is_recording() is False

        sampled_parent = TraceContext(
            trace_id="1" * 32,
            span_id="2" * 16,
            trace_flags=int(TraceFlags.SAMPLED),
        )
        with harness.tracer.start_as_current_span(
            "sampled-child", context=sampled_parent.as_context()
        ) as sampled_child:
            assert sampled_child.is_recording() is True

        unsampled_parent = TraceContext(
            trace_id="3" * 32,
            span_id="4" * 16,
            trace_flags=int(TraceFlags.DEFAULT),
        )
        with harness.tracer.start_as_current_span(
            "unsampled-child", context=unsampled_parent.as_context()
        ) as unsampled_child:
            assert unsampled_child.is_recording() is False

        spans = harness.exporter.get_finished_spans()
        assert [span.name for span in spans] == ["sampled-child"]
        assert spans[0].parent.span_id == int("2" * 16, 16)
        assert spans[0].context.trace_id == int("1" * 32, 16)
    finally:
        harness.close()


@pytest.mark.asyncio
async def test_current_span_is_isolated_between_async_tasks(
    harness: TraceHarness,
) -> None:
    first_entered = asyncio.Event()
    second_entered = asyncio.Event()

    async def worker(
        name: str,
        own_event: asyncio.Event,
        peer_event: asyncio.Event,
    ) -> tuple[int, int]:
        with harness.tracer.start_as_current_span(f"{name}.parent") as parent:
            parent_id = parent.get_span_context().span_id
            own_event.set()
            await peer_event.wait()
            await asyncio.sleep(0)
            assert get_current_span().get_span_context().span_id == parent_id
            with harness.tracer.start_as_current_span(f"{name}.child") as child:
                child_id = child.get_span_context().span_id
                await asyncio.sleep(0)
                assert get_current_span().get_span_context().span_id == child_id
            assert get_current_span().get_span_context().span_id == parent_id
            return parent_id, child_id

    first, second = await asyncio.gather(
        worker("first", first_entered, second_entered),
        worker("second", second_entered, first_entered),
    )

    assert first[0] != second[0]
    spans = {span.name: span for span in harness.exporter.get_finished_spans()}
    assert spans["first.child"].parent.span_id == spans["first.parent"].context.span_id
    assert (
        spans["second.child"].parent.span_id == spans["second.parent"].context.span_id
    )
    assert (
        spans["first.child"].context.trace_id != spans["second.child"].context.trace_id
    )
    assert get_current_span().get_span_context().is_valid is False


def test_legacy_trace_context_uses_official_remote_parent(
    harness: TraceHarness,
) -> None:
    class Spore:
        metadata: dict[str, Any] = {}

    with harness.tracer.start_as_current_span("source") as source:
        context = TraceContext.from_span(source)
        spore = Spore()
        context.inject_into_spore(spore)

    extracted = TraceContext.from_spore(spore)
    assert extracted == context
    assert TraceContext.from_spore(type("NoMetadata", (), {})()) is None
    with harness.tracer.start_as_current_span(
        "consumer", context=extracted.as_context()
    ):
        pass

    spans = {span.name: span for span in harness.exporter.get_finished_spans()}
    assert spans["consumer"].parent.span_id == spans["source"].context.span_id
    assert spans["consumer"].context.trace_id == spans["source"].context.trace_id


def test_legacy_trace_context_validates_and_safely_reads_metadata(
    harness: TraceHarness,
) -> None:
    with pytest.raises(ValueError, match="trace_id"):
        TraceContext(trace_id="0" * 32, span_id="2" * 16)
    with pytest.raises(ValueError, match="span_id"):
        TraceContext(trace_id="1" * 32, span_id="invalid")
    with pytest.raises(ValueError, match="unsupported bits"):
        TraceContext(trace_id="1" * 32, span_id="2" * 16, trace_flags=4)
    with pytest.raises(ValueError, match="invalid span"):
        TraceContext.from_span(trace.INVALID_SPAN)

    assert TraceContext.current() is None
    with harness.tracer.start_as_current_span("current-context") as current:
        assert TraceContext.current() == TraceContext.from_span(current)

    invalid_spores = [
        type("MissingIds", (), {"metadata": {"trace_id": "1" * 32}})(),
        type(
            "InvalidFlags",
            (),
            {
                "metadata": {
                    "trace_id": "1" * 32,
                    "span_id": "2" * 16,
                    "trace_flags": "sampled",
                }
            },
        )(),
        type(
            "InvalidId",
            (),
            {"metadata": {"trace_id": "bad", "span_id": "2" * 16}},
        )(),
    ]
    assert all(TraceContext.from_spore(spore) is None for spore in invalid_spores)

    context = TraceContext(trace_id="1" * 32, span_id="2" * 16)
    context.inject_into_spore(object())
    immutable_metadata = type("Immutable", (), {"metadata": ()})()
    context.inject_into_spore(immutable_metadata)
    assert immutable_metadata.metadata["trace_id"] == "1" * 32


def test_generated_identifiers_are_valid_and_unique() -> None:
    trace_ids = {generate_trace_id() for _ in range(100)}
    span_ids = {generate_span_id() for _ in range(100)}

    assert len(trace_ids) == 100
    assert len(span_ids) == 100
    assert all(len(value) == 32 and int(value, 16) for value in trace_ids)
    assert all(len(value) == 16 and int(value, 16) for value in span_ids)


def test_core_trace_path_imports_and_runs_without_optional_sdk_modules() -> None:
    script = r"""
import importlib.abc
import sys

class BlockSDK(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith("opentelemetry.sdk"):
            raise ImportError("optional OpenTelemetry SDK blocked")
        return None

sys.meta_path.insert(0, BlockSDK())
from praval.models import ExecutionObservation, NOOP_OBSERVATION_RECORDER
from praval.observability.tracing import SpanKind, get_tracer

with get_tracer().start_as_current_span("no-sdk", kind=SpanKind.INTERNAL) as span:
    assert not span.is_recording()
assert not any(name.startswith("opentelemetry.sdk") for name in sys.modules)
assert ExecutionObservation.__name__ == "ExecutionObservation"
assert NOOP_OBSERVATION_RECORDER.__class__.__name__ == "NoOpObservationRecorder"
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
