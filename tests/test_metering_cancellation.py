"""Reporter ownership survives cancellation of a threaded SDK request."""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import patch

import pytest

from praval._metering_runtime import provider_request
from praval.core.agent import Agent, AgentConfig
from praval.core.exceptions import ProviderTransportError
from praval.metering import UsageMeter, correlation
from praval.model_runtime import ModelRuntime
from praval.models import ModelResponse, ProviderCapabilities, Usage
from praval.runtime_observation import use_observation_recorder


class BlockingReportedProvider:
    capabilities = ProviderCapabilities()

    def __init__(self, *, before_report=False, completed_request=False):
        self.before_report = before_report
        self.completed_request = completed_request
        self.started = threading.Event()
        self.release = threading.Event()
        self.done = threading.Event()
        self.actual_requests = 0

    def request(self):
        self.actual_requests += 1
        return ModelResponse(
            content="answer",
            usage=Usage(input_tokens=3, output_tokens=2, total_tokens=5),
        )

    def invoke(self, request, tools=None):
        try:
            if self.completed_request:
                with provider_request() as report:
                    report.finish(self.request())
            if self.before_report:
                self.started.set()
                assert self.release.wait(5)
            with provider_request() as report:
                self.actual_requests += 1
                if not self.before_report:
                    self.started.set()
                    assert self.release.wait(5)
                response = ModelResponse(
                    content="late answer",
                    usage=Usage(input_tokens=3, output_tokens=2, total_tokens=5),
                )
                report.finish(response)
                return response
        finally:
            self.done.set()


@pytest.mark.parametrize("before_report", [False, True])
def test_cancelled_worker_has_one_record_after_late_sdk_return(before_report):
    provider = BlockingReportedProvider(before_report=before_report)
    runtime = ModelRuntime(
        provider=provider,
        provider_name="fake",
        config=AgentConfig(model="model", retries=0),
        agent_name="cancelled-agent",
    )
    tracked = UsageMeter()

    async def exercise():
        with tracked.track(), correlation("cancelled-request"):
            task = asyncio.create_task(
                runtime.ainvoke(messages=[{"role": "user", "content": "question"}])
            )
            assert await asyncio.to_thread(provider.started.wait, 5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert runtime.usage.totals.calls == 1
            assert runtime.usage.totals.failed_calls == 1
            provider.release.set()
            assert await asyncio.to_thread(provider.done.wait, 5)
        return tracked.calls

    try:
        records = asyncio.run(exercise())
    finally:
        provider.release.set()
    assert provider.actual_requests == 1
    assert runtime.usage.totals.calls == tracked.totals.calls == 1
    assert runtime.usage.totals.failed_calls == 1
    assert not tracked.totals.complete
    assert records[0].status == "error"
    assert records[0].correlation_id == "cancelled-request"
    assert records[0].agent_name == "cancelled-agent"


def test_cancelled_second_request_preserves_first_request_usage():
    provider = BlockingReportedProvider(completed_request=True)
    runtime = ModelRuntime(
        provider=provider,
        provider_name="fake",
        config=AgentConfig(model="model", retries=0),
    )

    async def exercise():
        task = asyncio.create_task(
            runtime.ainvoke(messages=[{"role": "user", "content": "question"}])
        )
        assert await asyncio.to_thread(provider.started.wait, 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert runtime.usage.totals.calls == 2
        provider.release.set()
        assert await asyncio.to_thread(provider.done.wait, 5)

    try:
        asyncio.run(exercise())
    finally:
        provider.release.set()
    assert provider.actual_requests == runtime.usage.totals.calls == 2
    assert [call.status for call in runtime.usage.calls] == ["ok", "error"]
    assert runtime.usage.totals.total_tokens == 5
    assert runtime.usage.totals.failed_calls == 1
    assert not runtime.usage.totals.complete


def test_failed_initial_request_observation_keeps_provider_and_model():
    class FailingProvider:
        capabilities = ProviderCapabilities()

        def invoke(self, request, tools=None):
            raise ProviderTransportError("offline")

    observations = []
    recorder = type(
        "Recorder", (), {"record": lambda self, item: observations.append(item)}
    )()
    with patch(
        "praval.core.agent.ProviderFactory.create_provider",
        return_value=FailingProvider(),
    ):
        instance = Agent(
            "initial-failure",
            provider="fake",
            model="failed-model",
            config={"retries": 0},
        )
    try:
        with use_observation_recorder(recorder), pytest.raises(ProviderTransportError):
            instance.generate("question")
        assert observations[-1].provider == "fake"
        assert observations[-1].model == "failed-model"
        assert observations[-1].model_calls == 1
    finally:
        instance.close()
