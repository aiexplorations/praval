"""Exact metering across public entry points, retries, tools and scopes."""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from praval.core.agent import Agent, AgentConfig
from praval.core.exceptions import ProviderUnavailableError
from praval.metering import ModelCall, Price, PriceTable, UsageMeter, correlation
from praval.model_runtime import ModelRuntime
from praval.models import (
    ModelEvent,
    ModelResponse,
    ProviderCapabilities,
    ToolCall,
    Usage,
)
from praval.runtime_observation import use_observation_recorder


def call(
    index: int = 1,
    *,
    usage: Usage | None = None,
    status: str = "ok",
    model: str = "test",
) -> ModelCall:
    return ModelCall(
        "fake",
        model,
        "invoke",
        None,
        1,
        status,
        usage,
        1.0,
        datetime.now(timezone.utc),
        "meter-test",
        str(index),
        "run",
        None,
        None,
        None,
    )


@pytest.mark.parametrize("bound", [1, 2, 10])
@pytest.mark.parametrize("count", [0, 1, 11, 100])
def test_eviction_preserves_exact_totals_and_cost(bound, count):
    meter = UsageMeter(bound)
    for index in range(count):
        meter.record(
            call(index, usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15))
        )
    assert len(meter.calls) == min(bound, count)
    assert meter.totals.calls == count
    assert meter.totals.total_tokens == 15 * count
    assert meter.totals.complete
    estimate = meter.cost(PriceTable({("fake", "test"): Price(2, 4)}))
    assert estimate.amount == pytest.approx(count * 40 / 1_000_000)
    assert estimate.priced_calls == count and estimate.complete


@pytest.mark.parametrize("read_price", [None, 0, 1, 3])
@pytest.mark.parametrize("write_price", [None, 0, 1, 3])
@pytest.mark.parametrize("reasoning", [0, 5])
def test_cost_prices_token_subsets_once(read_price, write_price, reasoning):
    meter = UsageMeter()
    meter.record(
        call(
            usage=Usage(
                input_tokens=100,
                output_tokens=10,
                total_tokens=110,
                cache_read_tokens=20,
                cache_write_tokens=30,
                reasoning_tokens=reasoning,
            )
        )
    )
    estimate = meter.cost(
        PriceTable({("fake", "test"): Price(2, 4, read_price, write_price)})
    )
    expected = (
        50 * 2
        + 20 * (2 if read_price is None else read_price)
        + 30 * (2 if write_price is None else write_price)
        + 10 * 4
    )
    assert estimate.amount == pytest.approx(expected / 1_000_000)
    assert estimate.complete and estimate.unpriced_calls == 0


@pytest.mark.parametrize("status", ["ok", "error"])
@pytest.mark.parametrize("reported", [False, True])
@pytest.mark.parametrize("priced", [False, True])
def test_incomplete_usage_and_prices_are_explicit(status, reported, priced):
    meter = UsageMeter()
    usage = Usage(input_tokens=1, output_tokens=2, total_tokens=3) if reported else None
    meter.record(call(usage=usage, status=status))
    estimate = meter.cost(PriceTable({("fake", "test"): Price(1, 2)} if priced else {}))
    assert meter.totals.failed_calls == int(status == "error")
    assert meter.totals.unreported_calls == int(status == "ok" and not reported)
    assert meter.totals.complete == (reported and status == "ok")
    assert estimate.priced_calls == int(reported and priced)
    assert estimate.complete == (reported and priced and status == "ok")


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan")])
@pytest.mark.parametrize(
    "field",
    [
        "input_per_million",
        "output_per_million",
        "cache_read_per_million",
        "cache_write_per_million",
    ],
)
def test_invalid_prices_fail_at_construction(value, field):
    values = {"input_per_million": 1, "output_per_million": 1, field: value}
    with pytest.raises(ValueError, match="finite and non-negative"):
        Price(**values)


def test_mixed_currency_is_rejected():
    with pytest.raises(ValueError, match="mix currencies"):
        PriceTable({("a", "b"): Price(1, 1), ("a", "c"): Price(1, 1, currency="INR")})


def test_records_and_subscribers_cannot_mutate_owned_usage():
    meter = UsageMeter()
    usage = Usage(input_tokens=3, total_tokens=3)
    meter.subscribe(lambda item: setattr(item.usage, "input_tokens", 999))
    meter.record(call(usage=usage))
    usage.input_tokens = 100
    meter.calls[0].usage.input_tokens = 200
    assert meter.calls[0].usage.input_tokens == 3
    assert meter.totals.input_tokens == 3


def test_subscriber_failure_isolated_removed_and_unsubscribe_idempotent(caplog):
    meter = UsageMeter()
    seen = []
    broken = []

    def failing(item):
        broken.append(item.call_id)
        raise ValueError("secret-application-content")

    meter.subscribe(failing)
    unsubscribe = meter.subscribe(seen.append)
    meter.record(call(1))
    meter.record(call(2))
    unsubscribe()
    unsubscribe()
    meter.record(call(3))
    assert broken == ["1"] and [item.call_id for item in seen] == ["1", "2"]
    assert "secret-application-content" not in caplog.text
    assert meter.totals.calls == 3


def test_concurrent_records_exact_after_eviction():
    meter = UsageMeter(2)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(
            pool.map(
                lambda i: meter.record(
                    call(i, usage=Usage(input_tokens=1, total_tokens=1))
                ),
                range(1000),
            )
        )
    assert meter.totals.calls == meter.totals.input_tokens == 1000
    assert len(meter.calls) == 2
    assert meter.totals_by_model()[("fake", "test")] == meter.totals


def test_reset_retains_subscriptions_and_clears_model_costs():
    meter = UsageMeter()
    seen = []
    meter.subscribe(seen.append)
    meter.record(call(1, usage=Usage(input_tokens=1, total_tokens=1)))
    meter.reset()
    assert not meter.calls and not meter.totals_by_model()
    assert meter.totals.calls == 0
    meter.record(call(2))
    assert [item.call_id for item in seen] == ["1", "2"]


class FakeProvider:
    capabilities = ProviderCapabilities(
        tools=True, streaming=True, native_streaming=True
    )

    def __init__(self, rounds=0, fail=False, reported=True):
        self.rounds, self.fail, self.reported = rounds, fail, reported
        self.requests = 0

    def respond(self):
        self.requests += 1
        if self.fail and self.requests == 1:
            raise ProviderUnavailableError("retry me")
        step = self.requests - int(self.fail)
        usage = (
            Usage(input_tokens=step * 10, output_tokens=step, total_tokens=step * 11)
            if self.reported
            else None
        )
        return ModelResponse(
            content="done" if step > self.rounds else "",
            usage=usage,
            tool_calls=(
                [ToolCall(id=f"tool-{step}", name="lookup", arguments={"x": step})]
                if step <= self.rounds
                else []
            ),
        )

    def invoke(self, request, tools=None):
        return self.respond()

    def continue_with_tool_results(self, request, response, results):
        return self.respond()

    def stream(self, request, tools=None):
        response = self.respond()
        yield ModelEvent(type="delta", delta=response.content)
        if response.usage is not None:
            yield ModelEvent(type="usage", usage=response.usage)
        yield ModelEvent(type="final", response=response)

    async def astream(self, request, tools=None):
        for event in self.stream(request, tools):
            yield event


@pytest.mark.parametrize(
    "entry", ["chat", "generate", "agenerate", "stream", "astream"]
)
@pytest.mark.parametrize("rounds", [0, 1, 3])
@pytest.mark.parametrize("retry", [False, True])
@pytest.mark.parametrize("reported", [False, True])
def test_agent_entry_points_record_every_request_and_reconcile(
    entry, rounds, retry, reported, monkeypatch
):
    monkeypatch.setattr("praval.model_runtime._sleep", lambda _: None)
    monkeypatch.setattr("praval.model_runtime._async_sleep", _no_sleep)
    provider = FakeProvider(rounds, retry, reported)
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=provider
    ):
        agent = Agent(
            "meter-test", provider="fake", model="test", config={"retries": 1}
        )
    effects = []

    @agent.tool
    def lookup(x: int) -> str:
        effects.append(x)
        return str(x)

    outer, inner = UsageMeter(), UsageMeter()
    observations = []
    recorder = type(
        "Recorder", (), {"record": lambda self, item: observations.append(item)}
    )()
    events = []
    with (
        outer.track(),
        outer.track(),
        inner.track(),
        correlation("application-42"),
        use_observation_recorder(recorder),
    ):
        if entry == "agenerate":
            result = asyncio.run(agent.agenerate("hello"))
        elif entry == "astream":

            async def collect():
                return [event async for event in agent.astream("hello")]

            events = asyncio.run(collect())
            result = events[-1].response
        elif entry == "stream":
            events = list(agent.stream("hello"))
            result = events[-1].response
        else:
            result = getattr(agent, entry)("hello")
    expected_calls = rounds + 1 + int(retry)
    expected_tokens = sum(range(1, rounds + 2)) * 11 if reported else 0
    assert effects == list(range(1, rounds + 1))
    assert provider.requests == expected_calls
    assert agent.usage.totals == outer.totals == inner.totals
    assert (
        outer.totals.calls == expected_calls
        and outer.totals.total_tokens == expected_tokens
    )
    assert outer.totals.failed_calls == int(retry)
    assert outer.totals.complete == (reported and not retry)
    assert len({item.call_id for item in outer.calls}) == expected_calls
    assert all(
        item.correlation_id == "application-42" and item.agent_name == "meter-test"
        for item in outer.calls
    )
    assert [item.attempt for item in outer.calls][: 1 + int(retry)] == (
        [1, 2] if retry else [1]
    )
    assert all(
        item.round_index == index
        for index, item in enumerate(outer.calls[1 + int(retry) :])
    )
    assert agent.conversation_history[-1]["content"] == "done"
    assert observations[-1].model_calls == expected_calls
    assert (
        observations[-1].usage.total_tokens if observations[-1].usage else 0
    ) == expected_tokens
    if entry != "chat":
        assert result.content == "done"
        assert len(result.metadata["model_calls"]) == expected_calls
        json.dumps(result.metadata["model_calls"])
        assert (result.usage.total_tokens if result.usage else 0) == expected_tokens
        assert result.metadata["usage_complete"] == (reported and not retry)
    if events:
        assert (
            len([event for event in events if event.type == "model_call"])
            == expected_calls
        )
    agent.close()


async def _no_sleep(delay):
    pass


@pytest.mark.parametrize("entry", ["stream", "astream"])
def test_abandoned_native_stream_records_one_incomplete_call(entry):
    provider = FakeProvider()
    runtime = ModelRuntime(
        provider=provider,
        provider_name="fake",
        config=AgentConfig(provider="fake", model="test"),
    )
    messages = [{"role": "user", "content": "hello"}]
    if entry == "stream":
        events = runtime.stream(messages=messages)
        assert next(events).type == "start"
        assert next(events).type == "delta"
        events.close()
    else:

        async def abandon():
            events = runtime.astream(messages=messages)
            assert (await events.__anext__()).type == "start"
            assert (await events.__anext__()).type == "delta"
            await events.aclose()

        asyncio.run(abandon())
    assert runtime.usage.totals.calls == runtime.usage.totals.failed_calls == 1
    assert not runtime.usage.totals.complete


def test_generator_run_meter_does_not_leak_into_other_invocations():
    runtime = ModelRuntime(
        provider=FakeProvider(),
        provider_name="fake",
        config=AgentConfig(provider="fake", model="test"),
    )
    events = runtime.stream(messages=[{"role": "user", "content": "first"}])
    next(events)
    next(events)
    other = runtime.invoke(messages=[{"role": "user", "content": "second"}])
    assert len(other.metadata["model_calls"]) == 1
    final = list(events)[-1].response
    assert len(final.metadata["model_calls"]) == 1
    assert final.usage.total_tokens == 11 and other.usage.total_tokens == 22
