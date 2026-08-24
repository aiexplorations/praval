"""Runtime observation aggregation and telemetry correlation tests."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Iterator
from unittest.mock import Mock, patch

import pytest
from opentelemetry.trace import INVALID_SPAN, StatusCode

from praval.composition import AgentSession
from praval.config import AppConfig, ObservabilityConfig, OTLPConfig, PravalConfig
from praval.core.agent import Agent, AgentConfig
from praval.core.exceptions import PravalError, ProviderError
from praval.decorators import agent, chat
from praval.model_runtime import ModelRuntime
from praval.models import (
    AudioResponse,
    ModelEvent,
    ModelResponse,
    ProviderCapabilities,
    ToolCall,
    Usage,
)
from praval.models.observation import (
    ContentKind,
    ExecutionObservation,
    ObservationFactStatus,
    ObservationKind,
    ObservationStatus,
    ReefHandoffObservation,
    TokenUsageObservation,
    ToolCallObservation,
)
from praval.observability import configure_observability, shutdown_observability
from praval.runtime_observation import (
    CompositeObservationRecorder,
    ObservationScope,
    ToolCallScope,
    configure_observation_recorder,
    has_active_observation,
    operation_span,
    record_content_reference,
    record_handoff,
    record_model_facts,
    record_tool_call,
    use_observation_recorder,
)

sdk_export = pytest.importorskip("opentelemetry.sdk.trace.export")
in_memory_export = pytest.importorskip(
    "opentelemetry.sdk.trace.export.in_memory_span_exporter"
)


class MemoryRecorder:
    """Collect immutable observations for assertions."""

    def __init__(self) -> None:
        self.observations: list[ExecutionObservation] = []

    def record(self, observation: ExecutionObservation) -> None:
        self.observations.append(observation)


class FailingRecorder:
    """Represent an unavailable exporter/evaluation consumer."""

    def record(self, observation: ExecutionObservation) -> None:
        raise RuntimeError("consumer unavailable")


def test_recorder_configuration_is_available_from_observability_facade() -> None:
    from praval.observability import (
        CompositeObservationRecorder as PublicCompositeRecorder,
    )
    from praval.observability import (
        configure_observation_recorder,
    )
    from praval.observability import use_observation_recorder as public_use_recorder

    assert PublicCompositeRecorder is CompositeObservationRecorder
    assert callable(configure_observation_recorder)
    assert public_use_recorder is use_observation_recorder


def test_default_recorder_validates_boundaries_and_aggregates_fact_variants() -> None:
    class ProviderUsage:
        prompt_tokens = 2
        completion_tokens = 3
        reasoning_tokens = 1
        cache_read_tokens = 4
        cache_write_tokens = 5
        total_tokens = 5

    recorder = MemoryRecorder()
    previous = configure_observation_recorder(recorder)
    try:
        assert has_active_observation() is False
        with pytest.raises(ValueError, match="require agent identity"):
            ObservationScope(kind=ObservationKind.AGENT)
        with pytest.raises(ValueError, match="require workflow identity"):
            ObservationScope(kind=ObservationKind.WORKFLOW)

        with ObservationScope(
            kind=ObservationKind.AGENT,
            agent_name="fact-variants",
        ):
            assert has_active_observation() is True
            record_model_facts(provider="first", model="one", usage=ProviderUsage())
            record_model_facts(
                provider="second",
                model="two",
                usage=TokenUsageObservation(input_tokens=1, total_tokens=1),
            )
            record_model_facts(provider=None, model=None)
            record_handoff(
                ReefHandoffObservation(
                    handoff_id="handoff-1",
                    source_agent_id="fact-variants",
                    target_agent_id="next-agent",
                    status=ObservationFactStatus.OK,
                )
            )
    finally:
        configure_observation_recorder(previous)

    observation = recorder.observations[0]
    assert observation.provider == "multiple"
    assert observation.model == "multiple"
    assert observation.usage.input_tokens == 3
    assert observation.usage.output_tokens == 3
    assert observation.usage.total_tokens == 6
    assert observation.handoffs[0].target_agent_id == "next-agent"


def test_timeout_skipped_tool_and_unusual_content_are_privacy_safe() -> None:
    class DumpableContent:
        def model_dump(self, *, mode: str) -> dict[str, str]:
            assert mode == "json"
            return {"value": "private"}

    class UnserializableContent:
        def __str__(self) -> str:
            raise RuntimeError("cannot serialize")

    recorder = MemoryRecorder()
    with use_observation_recorder(recorder):
        with pytest.raises(TimeoutError):
            with ObservationScope(
                kind=ObservationKind.AGENT,
                agent_name="timeout-agent",
            ):
                with ToolCallScope(tool_call_id="skipped", name="approval") as tool:
                    tool.skip_fact()
                record_content_reference(ContentKind.MEDIA, bytearray(b"audio"))
                record_content_reference(ContentKind.CONTEXT, DumpableContent())
                unavailable = record_content_reference(
                    ContentKind.RESPONSE,
                    UnserializableContent(),
                )
                raise TimeoutError("provider deadline")

    observation = recorder.observations[0]
    assert observation.status is ObservationStatus.TIMEOUT
    assert observation.error_type == "TimeoutError"
    assert observation.tool_calls == ()
    assert unavailable.sha256 == hashlib.sha256(
        b"<unavailable:UnserializableContent>"
    ).hexdigest()
    assert "private" not in observation.model_dump_json()


def test_operation_span_failures_never_replace_application_results(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import praval.runtime_observation as runtime_observation

    class BrokenStartTracer:
        def start_as_current_span(self, *args: object, **kwargs: object) -> object:
            raise RuntimeError("start failed")

    monkeypatch.setattr(runtime_observation, "_get_tracer", lambda: BrokenStartTracer())
    with operation_span("broken.start") as span:
        assert span is INVALID_SPAN

    class BrokenCloseManager:
        def __enter__(self) -> object:
            return INVALID_SPAN

        def __exit__(self, *args: object) -> None:
            raise RuntimeError("close failed")

    class BrokenCloseTracer:
        def start_as_current_span(self, *args: object, **kwargs: object) -> object:
            return BrokenCloseManager()

    monkeypatch.setattr(runtime_observation, "_get_tracer", lambda: BrokenCloseTracer())
    with operation_span("broken.close"):
        result = "unchanged"
    assert result == "unchanged"

    application_error = ValueError("application failed")
    with pytest.raises(ValueError) as caught:
        with operation_span("broken.error.close"):
            raise application_error
    assert caught.value is application_error
    assert "Operation span start failed" in caplog.text
    assert caplog.text.count("Operation span close failed") == 2


@pytest.fixture
def trace_exporter() -> Iterator[object]:
    handle = configure_observability(
        PravalConfig(
            app=AppConfig(service_name="runtime-observation-test"),
            observability=ObservabilityConfig(
                enabled=True,
                otlp=OTLPConfig(traces=True, metrics=False, logs=False),
            ),
        )
    )
    exporter = in_memory_export.InMemorySpanExporter()
    handle.tracer_provider.add_span_processor(sdk_export.SimpleSpanProcessor(exporter))
    yield exporter
    shutdown_observability()


def test_same_agent_scope_is_joined_and_recorded_once() -> None:
    recorder = MemoryRecorder()

    with use_observation_recorder(recorder):
        with ObservationScope(
            kind=ObservationKind.AGENT,
            agent_id="agent-1",
            agent_name="researcher",
            run_id="run-1",
        ) as outer:
            with ObservationScope(
                kind=ObservationKind.AGENT,
                agent_id="agent-1",
                agent_name="researcher",
                run_id="ignored-run",
            ) as inner:
                record_model_facts(
                    provider="openai",
                    model="test-model",
                    usage={"input_tokens": 3, "output_tokens": 2},
                )

    assert outer.owns_scope is True
    assert inner.owns_scope is False
    assert inner.run_id == "run-1"
    assert len(recorder.observations) == 1
    observation = recorder.observations[0]
    assert observation.run_id == "run-1"
    assert observation.usage is not None
    assert observation.usage.total_tokens == 5


def test_agent_and_workflow_each_record_aggregated_shared_facts() -> None:
    recorder = MemoryRecorder()

    with use_observation_recorder(recorder):
        with ObservationScope(
            kind=ObservationKind.WORKFLOW,
            workflow_id="workflow-1",
            workflow_name="research-flow",
        ):
            for index in range(2):
                with ObservationScope(
                    kind=ObservationKind.AGENT,
                    agent_id=f"agent-{index}",
                    agent_name=f"worker-{index}",
                ):
                    record_model_facts(
                        provider="openai",
                        model="test-model",
                        usage={"input_tokens": 2, "output_tokens": 1},
                    )

    agents = [
        item for item in recorder.observations if item.kind is ObservationKind.AGENT
    ]
    workflow = next(
        item for item in recorder.observations if item.kind is ObservationKind.WORKFLOW
    )
    assert len(agents) == 2
    assert [item.usage.total_tokens for item in agents if item.usage] == [3, 3]
    assert workflow.usage is not None
    assert workflow.usage.total_tokens == 6


def test_content_is_hashed_without_storing_raw_payload() -> None:
    recorder = MemoryRecorder()
    prompt = "private customer prompt"

    with use_observation_recorder(recorder):
        with ObservationScope(
            kind=ObservationKind.AGENT,
            agent_name="privacy-agent",
        ):
            fact = record_content_reference(ContentKind.PROMPT, prompt)

    assert fact.sha256 == hashlib.sha256(prompt.encode()).hexdigest()
    assert fact.size_bytes == len(prompt.encode())
    serialized = recorder.observations[0].model_dump_json()
    assert prompt not in serialized
    assert recorder.observations[0].privacy.content_captured is False


def test_lower_level_operation_without_scope_emits_no_observation() -> None:
    recorder = MemoryRecorder()

    with use_observation_recorder(recorder):
        with operation_span("praval.embedding.invoke"):
            record_model_facts(provider="local", model="embed-test")
            record_tool_call(
                ToolCallObservation(
                    tool_call_id="call-1",
                    name="lookup",
                    status=ObservationFactStatus.OK,
                    duration_ms=1,
                )
            )

    assert recorder.observations == []


def test_recorder_failures_are_isolated_but_application_errors_propagate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    successful = MemoryRecorder()
    recorder = CompositeObservationRecorder(FailingRecorder(), successful)
    original = ValueError("application failure")

    with use_observation_recorder(recorder):
        with pytest.raises(ValueError) as caught:
            with ObservationScope(
                kind=ObservationKind.AGENT,
                agent_name="failing-agent",
            ):
                raise original

    assert caught.value is original
    assert successful.observations[0].status is ObservationStatus.ERROR
    assert successful.observations[0].error_type == "ValueError"
    assert "Observation recorder failed" in caplog.text


def test_broken_host_tracer_and_oversized_metadata_do_not_change_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import praval.runtime_observation as runtime_observation

    class BrokenTracer:
        def start_as_current_span(self, *args: object, **kwargs: object) -> object:
            raise RuntimeError("host tracer unavailable")

    recorder = MemoryRecorder()
    monkeypatch.setattr(runtime_observation, "_get_tracer", lambda: BrokenTracer())
    long_identity = "agent" * 100

    with use_observation_recorder(recorder):
        with ObservationScope(
            kind=ObservationKind.AGENT,
            agent_id=long_identity,
            request_mode="mode" * 100,
        ):
            record_model_facts(
                provider="provider" * 100,
                model="model" * 200,
                response_id="response" * 100,
                usage={"input_tokens": "not-an-integer"},
            )
            result = "application result"

    assert result == "application result"
    observation = recorder.observations[0]
    assert len(observation.agent_id) == 256
    assert len(observation.request_mode) == 128
    assert len(observation.provider) == 256
    assert len(observation.model) == 512
    assert observation.usage is None
    assert observation.trace_id is None


@pytest.mark.asyncio
async def test_parallel_agent_scopes_are_context_isolated() -> None:
    recorder = MemoryRecorder()

    async def worker(index: int) -> None:
        with ObservationScope(
            kind=ObservationKind.AGENT,
            agent_id=f"agent-{index}",
        ):
            await asyncio.sleep(0)
            record_model_facts(
                provider="provider",
                model=f"model-{index}",
                usage={"input_tokens": index + 1},
            )

    with use_observation_recorder(recorder):
        await asyncio.gather(worker(0), worker(1))

    by_agent = {item.agent_id: item for item in recorder.observations}
    assert by_agent["agent-0"].model == "model-0"
    assert by_agent["agent-1"].model == "model-1"
    assert by_agent["agent-0"].usage.input_tokens == 1
    assert by_agent["agent-1"].usage.input_tokens == 2


def test_observation_and_root_span_share_identity_status_usage_and_timing(
    trace_exporter: object,
) -> None:
    recorder = MemoryRecorder()

    with use_observation_recorder(recorder):
        with ObservationScope(
            kind=ObservationKind.AGENT,
            agent_id="agent-correlated",
            run_id="run-correlated",
        ):
            record_model_facts(
                provider="openai",
                model="model-correlated",
                response_id="response-1",
                terminal_outcome="stop",
                usage={"input_tokens": 7, "output_tokens": 4},
            )

    observation = recorder.observations[0]
    spans = trace_exporter.get_finished_spans()  # type: ignore[attr-defined]
    root = next(span for span in spans if span.name == "praval.agent.invoke")
    assert observation.trace_id == f"{root.context.trace_id:032x}"
    assert observation.span_id == f"{root.context.span_id:016x}"
    assert root.attributes["praval.observation.id"] == observation.observation_id
    assert root.attributes["praval.run.id"] == observation.run_id
    assert root.attributes["praval.observation.status"] == observation.status.value
    assert root.attributes["praval.duration_ms"] == observation.duration_ms
    assert root.attributes["gen_ai.usage.input_tokens"] == 7
    assert root.attributes["gen_ai.usage.output_tokens"] == 4
    assert root.status.status_code is StatusCode.OK


def _test_agent(name: str = "observed-agent") -> Agent:
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=Mock()
    ):
        return Agent(name, provider="openai", model="test-model")


def test_direct_agent_chat_records_one_privacy_safe_observation() -> None:
    recorder = MemoryRecorder()
    observed_agent = _test_agent()
    observed_agent.runtime.generate_text = Mock(return_value="private answer")

    with use_observation_recorder(recorder):
        result = observed_agent.chat("private question")

    assert result == "private answer"
    assert len(recorder.observations) == 1
    observation = recorder.observations[0]
    assert observation.agent_id == "observed-agent"
    assert observation.request_mode == "chat"
    assert observation.status is ObservationStatus.OK
    assert [item.kind for item in observation.content_references] == [
        ContentKind.PROMPT,
        ContentKind.RESPONSE,
    ]
    assert "private question" not in observation.model_dump_json()
    assert "private answer" not in observation.model_dump_json()


def test_direct_agent_error_retains_compatibility_and_records_failure() -> None:
    recorder = MemoryRecorder()
    observed_agent = _test_agent()
    provider_error = RuntimeError("provider failed")
    observed_agent.runtime.invoke = Mock(side_effect=provider_error)

    with use_observation_recorder(recorder):
        with pytest.raises(PravalError) as caught:
            observed_agent.generate("question")

    assert caught.value.__cause__ is provider_error
    assert recorder.observations[0].status is ObservationStatus.ERROR
    assert recorder.observations[0].error_type == "PravalError"


def test_stream_observation_closes_on_consumption_and_records_cancellation() -> None:
    recorder = MemoryRecorder()
    observed_agent = _test_agent()

    def two_events(**kwargs: object) -> Iterator[str]:
        yield "first"
        yield "second"

    observed_agent.runtime.stream = two_events  # type: ignore[method-assign]

    with use_observation_recorder(recorder):
        events = observed_agent.stream("question")
        assert recorder.observations == []
        assert next(events) == "first"
        events.close()

    assert len(recorder.observations) == 1
    assert recorder.observations[0].status is ObservationStatus.CANCELLED
    assert recorder.observations[0].request_mode == "stream"


def test_transcription_and_speech_emit_media_observations() -> None:
    recorder = MemoryRecorder()
    observed_agent = _test_agent("media-agent")
    observed_agent.provider.transcribe = Mock(
        return_value=AudioResponse(text="private transcript", model="audio-model")
    )
    observed_agent.provider.speak = Mock(
        return_value=AudioResponse(
            data=b"private audio bytes",
            model="speech-model",
            mime_type="audio/mpeg",
        )
    )

    with use_observation_recorder(recorder):
        assert observed_agent.transcribe(b"private input audio") == "private transcript"
        assert observed_agent.speak("private speech input") == b"private audio bytes"

    transcription, speech = recorder.observations
    assert transcription.request_mode == "transcription"
    assert transcription.model == "audio-model"
    assert [item.kind for item in transcription.content_references] == [
        ContentKind.MEDIA,
        ContentKind.RESPONSE,
    ]
    assert speech.request_mode == "speech"
    assert speech.model == "speech-model"
    assert [item.kind for item in speech.content_references] == [
        ContentKind.PROMPT,
        ContentKind.MEDIA,
    ]
    serialized = "".join(item.model_dump_json() for item in recorder.observations)
    assert "private transcript" not in serialized
    assert "private speech input" not in serialized
    observed_agent.close()


def test_invalid_transcription_response_is_recorded_without_rewriting_error() -> None:
    recorder = MemoryRecorder()
    observed_agent = _test_agent("invalid-media-agent")
    observed_agent.provider.transcribe = Mock(return_value=object())

    with use_observation_recorder(recorder):
        with pytest.raises(ProviderError) as caught:
            observed_agent.transcribe(b"audio")

    assert "invalid transcription response" in str(caught.value)
    assert recorder.observations[0].status is ObservationStatus.ERROR
    assert recorder.observations[0].error_type == "ProviderError"
    observed_agent.close()


def test_decorated_handler_and_nested_chat_emit_one_agent_observation() -> None:
    recorder = MemoryRecorder()

    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=Mock()
    ):

        @agent(
            "decorated-observed",
            provider="openai",
            model="test-model",
            auto_broadcast=False,
            auto_discover_tools=False,
        )
        def observed_handler(spore: object) -> dict[str, str]:
            return {"answer": chat("nested private question")}

    underlying_agent = getattr(observed_handler, "_praval_agent")
    underlying_agent.runtime.generate_text = Mock(return_value="nested answer")
    spore = Mock(id="spore-1", knowledge={"type": "request"})
    handler = underlying_agent._custom_spore_handler

    with use_observation_recorder(recorder):
        result = handler(spore)

    assert result == {"answer": "nested answer"}
    assert len(recorder.observations) == 1
    observation = recorder.observations[0]
    assert observation.agent_name == "decorated-observed"
    assert observation.request_mode == "handler"
    assert observation.conversation_id == "spore-1"
    assert len(observation.content_references) == 3
    underlying_agent.close()


def test_handled_decorated_handler_error_is_observed_as_error() -> None:
    recorder = MemoryRecorder()

    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=Mock()
    ):

        @agent(
            "handled-error-agent",
            provider="openai",
            auto_broadcast=False,
            auto_discover_tools=False,
            on_error="ignore",
        )
        def failing_handler(spore: object) -> None:
            raise LookupError("handled by policy")

    underlying_agent = getattr(failing_handler, "_praval_agent")
    handler = underlying_agent._custom_spore_handler

    with use_observation_recorder(recorder):
        assert handler(Mock(id="spore-2", knowledge={})) is None

    assert recorder.observations[0].status is ObservationStatus.ERROR
    assert recorder.observations[0].error_type == "LookupError"
    underlying_agent.close()


def test_agent_session_records_workflow_success_and_failure() -> None:
    recorder = MemoryRecorder()

    with use_observation_recorder(recorder):
        with AgentSession("successful-workflow"):
            record_model_facts(
                provider="provider",
                model="model",
                usage={"input_tokens": 1},
            )
        with pytest.raises(RuntimeError, match="workflow failed"):
            with AgentSession("failed-workflow"):
                raise RuntimeError("workflow failed")

    by_name = {item.workflow_name: item for item in recorder.observations}
    assert by_name["successful-workflow"].status is ObservationStatus.OK
    assert by_name["successful-workflow"].usage.input_tokens == 1
    assert by_name["failed-workflow"].status is ObservationStatus.ERROR
    assert by_name["failed-workflow"].error_type == "RuntimeError"


def _model_runtime(provider: object, **config: object) -> ModelRuntime:
    config_values = {
        "provider": "test-provider",
        "model": "test-model",
        "retries": 0,
        **config,
    }
    return ModelRuntime(
        provider=provider,
        provider_name="test-provider",
        config=AgentConfig(**config_values),
    )


def test_model_runtime_aggregates_response_identity_usage_and_finish_reason() -> None:
    class Provider:
        capabilities = ProviderCapabilities()

        def invoke(self, request: object) -> ModelResponse:
            return ModelResponse(
                content="answer",
                usage=Usage(input_tokens=5, output_tokens=3, total_tokens=8),
                finish_reason="stop",
                metadata={"response_id": "response-42"},
            )

    recorder = MemoryRecorder()
    with use_observation_recorder(recorder):
        with ObservationScope(kind=ObservationKind.AGENT, agent_id="model-agent"):
            response = _model_runtime(Provider()).invoke(
                messages=[{"role": "user", "content": "question"}]
            )

    assert response.content == "answer"
    observation = recorder.observations[0]
    assert observation.provider == "test-provider"
    assert observation.model == "test-model"
    assert observation.response_id == "response-42"
    assert observation.terminal_outcome == "stop"
    assert observation.usage.input_tokens == 5
    assert observation.usage.output_tokens == 3
    assert observation.usage.total_tokens == 8


def test_model_runtime_retry_is_aggregated_and_provider_error_is_preserved() -> None:
    original = ProviderError("temporary")

    class FlakyProvider:
        capabilities = ProviderCapabilities()

        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, request: object) -> ModelResponse:
            self.calls += 1
            if self.calls == 1:
                raise original
            return ModelResponse(content="recovered")

    recorder = MemoryRecorder()
    provider = FlakyProvider()
    with use_observation_recorder(recorder):
        with ObservationScope(kind=ObservationKind.AGENT, agent_id="retry-agent"):
            _model_runtime(provider, retries=1).invoke(
                messages=[{"role": "user", "content": "question"}]
            )

    retry = recorder.observations[0].retries[0]
    assert provider.calls == 2
    assert retry.attempt == 1
    assert retry.operation == "model.invoke"
    assert retry.reason_type == "ProviderError"

    with pytest.raises(ProviderError) as caught:
        _model_runtime(FlakyProvider()).invoke(
            messages=[{"role": "user", "content": "question"}]
        )
    assert caught.value is original


@pytest.mark.asyncio
async def test_async_model_runtime_aggregates_usage() -> None:
    class AsyncProvider:
        capabilities = ProviderCapabilities()

        async def ainvoke(self, request: object) -> ModelResponse:
            await asyncio.sleep(0)
            return ModelResponse(
                content="async answer",
                usage=Usage(input_tokens=2, output_tokens=4, total_tokens=6),
            )

    recorder = MemoryRecorder()
    with use_observation_recorder(recorder):
        with ObservationScope(kind=ObservationKind.AGENT, agent_id="async-model"):
            await _model_runtime(AsyncProvider()).ainvoke(
                messages=[{"role": "user", "content": "question"}]
            )

    assert recorder.observations[0].usage.total_tokens == 6


def test_native_stream_records_ttft_and_does_not_double_count_usage(
    trace_exporter: object,
) -> None:
    usage = Usage(input_tokens=3, output_tokens=2, total_tokens=5)

    class StreamingProvider:
        capabilities = ProviderCapabilities(streaming=True, native_streaming=True)

        def stream(self, request: object) -> Iterator[ModelEvent]:
            yield ModelEvent(type="delta", delta="answer")
            yield ModelEvent(type="usage", usage=usage)
            yield ModelEvent(
                type="final",
                response=ModelResponse(
                    content="answer",
                    usage=usage,
                    finish_reason="stop",
                ),
            )

    recorder = MemoryRecorder()
    with use_observation_recorder(recorder):
        with ObservationScope(kind=ObservationKind.AGENT, agent_id="stream-model"):
            events = list(
                _model_runtime(StreamingProvider()).stream(
                    messages=[{"role": "user", "content": "question"}]
                )
            )

    assert [event.type for event in events] == ["start", "delta", "usage", "final"]
    assert recorder.observations[0].usage.total_tokens == 5
    model_span = next(
        span
        for span in trace_exporter.get_finished_spans()  # type: ignore[attr-defined]
        if span.name == "model.invoke"
    )
    assert model_span.attributes["gen_ai.server.time_to_first_token"] >= 0


def test_typed_tool_round_limit_honors_request_override_and_emits_event(
    trace_exporter: object,
) -> None:
    class EndlessProvider:
        capabilities = ProviderCapabilities(tools=True)

        def invoke(self, request: object) -> ModelResponse:
            return ModelResponse(
                tool_calls=[ToolCall(id="call-0", name="ping", arguments={})]
            )

        def continue_with_tool_results(
            self,
            request: object,
            response: object,
            results: object,
        ) -> ModelResponse:
            return ModelResponse(
                tool_calls=[ToolCall(id="call-next", name="ping", arguments={})]
            )

    def ping() -> str:
        return "pong"

    recorder = MemoryRecorder()
    runtime = _model_runtime(EndlessProvider(), max_tool_rounds=4)
    with use_observation_recorder(recorder):
        with pytest.raises(ProviderError, match=r"maximum tool rounds \(1\)"):
            with ObservationScope(kind=ObservationKind.AGENT, agent_id="limit-agent"):
                runtime.invoke(
                    messages=[{"role": "user", "content": "ping"}],
                    tools=[{"function": ping}],
                    max_tool_rounds=1,
                )

    assert recorder.observations[0].status is ObservationStatus.ERROR
    model_span = next(
        span
        for span in trace_exporter.get_finished_spans()  # type: ignore[attr-defined]
        if span.name == "model.invoke"
    )
    limit_event = next(
        event for event in model_span.events if event.name == "praval.limit.reached"
    )
    assert limit_event.attributes["praval.limit.name"] == "tool_rounds"
    assert limit_event.attributes["praval.limit.value"] == 1


def test_agent_config_rejects_invalid_tool_round_limit() -> None:
    with pytest.raises(ValueError, match="max_tool_rounds must be positive"):
        AgentConfig(max_tool_rounds=0)
    with pytest.raises(ValueError, match="max_tool_rounds must not exceed 1000"):
        AgentConfig(max_tool_rounds=1001)
