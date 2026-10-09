"""Offline v0.8.4 acceptance: adapters, durable tools, retries and accounting.

Each scenario crosses three dependent tool rounds and a process restart. Cohere
does not advertise streaming, so its two streaming combinations are omitted;
the entry matrix separately checks that unsupported streams fail before calls.
"""

from __future__ import annotations

import asyncio
import copy
from typing import Any, List, Tuple
from unittest.mock import AsyncMock

import pytest
from integration_matrix._entry_support import (
    ENTRY_POINTS,
    MATRIX_HARNESSES,
    ResponsesHarness,
    build_agent,
    run_entry,
)
from provider_harnesses import (
    QUESTION,
    AnthropicHarness,
    CohereHarness,
    GeminiHarness,
    Harness,
)

from praval.core.agent import Agent
from praval.core.exceptions import InterventionRequired, ProviderUnavailableError
from praval.hitl.service import HITLService
from praval.metering import UsageMeter


def reported(harness: Harness, response: Any, index: int) -> Any:
    """Attach documented usage shapes at the SDK boundary, before conversion."""
    inputs, outputs = 4 + index, 1 + index
    usage = {"input_tokens": inputs, "output_tokens": outputs}
    if isinstance(harness, GeminiHarness):
        response["usageMetadata"] = {
            "promptTokenCount": inputs,
            "candidatesTokenCount": outputs,
            "totalTokenCount": inputs + outputs,
        }
    elif isinstance(harness, CohereHarness):
        response.meta = {"billed_units": usage}
    elif isinstance(harness, AnthropicHarness):
        response.usage = usage
    elif isinstance(harness, ResponsesHarness):
        response["usage"] = {**usage, "total_tokens": inputs + outputs}
    else:
        response.usage = {
            "prompt_tokens": inputs,
            "completion_tokens": outputs,
            "total_tokens": inputs + outputs,
        }
    return response


def register_tools(agent: Agent, log: List[Tuple[str, str]]) -> None:
    @agent.tool
    def lookup(city: str) -> str:
        log.append(("lookup", city))
        return "PX-1"

    @agent.tool
    def forecast(code: str) -> str:
        log.append(("forecast", code))
        return "Sunny"

    @agent.tool
    def deliver(weather: str) -> str:
        log.append(("deliver", weather))
        return "Forecast: Sunny"

    agent.tools["forecast"]["requires_approval"] = True


def install_failure(harness: Harness) -> None:
    original = harness.respond

    def respond(**params: Any) -> Any:
        if isinstance(harness.responses[0], Exception):
            harness.requests.append(copy.deepcopy(params))
            raise harness.responses.pop(0)
        return original(**params)

    harness.respond = respond  # type: ignore[method-assign]


@pytest.mark.parametrize(
    "factory,entry",
    [
        pytest.param(factory, entry, id=f"{factory.name}-{entry}")
        for factory in MATRIX_HARNESSES
        for entry in ENTRY_POINTS
        if not (factory is CohereHarness and entry in ("stream", "astream"))
    ],
)
def test_v084_release_gate(
    factory: Any, entry: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    first = factory()
    first.responses = [
        reported(
            first,
            first.tool_turn([("lookup", {}), ("lookup", {"city": "Paris"})]),
            1,
        ),
        reported(first, first.tool_turn([("forecast", {"code": "PX-1"})]), 2),
    ]
    db = str(tmp_path / "release-gate.db")
    agent = build_agent(first, monkeypatch, hitl_db_path=db)
    original_agent = agent
    log: List[Tuple[str, str]] = []
    register_tools(agent, log)
    tracked = UsageMeter()
    monkeypatch.setattr("praval.model_runtime._sleep", lambda duration: None)
    monkeypatch.setattr("praval.model_runtime._async_sleep", AsyncMock())
    try:
        with tracked.track(), pytest.raises(InterventionRequired) as pause:
            run_entry(agent, entry, QUESTION)
        assert log == [("lookup", "Paris")]
        assert len(first.requests) == 2
        assert original_agent.usage.totals.total_tokens == 16
        run_id = pause.value.run_id
        agent.approve_intervention(pause.value.intervention_id, reviewer="release-gate")
        agent.close()

        # A fresh client mirrors a separate process. Responses' conversation is
        # server-owned; Gemini's opaque signed content is restored from SQLite.
        second = factory()
        second._next_call = first._next_call
        if isinstance(second, ResponsesHarness):
            second.server = copy.deepcopy(first.server)
            second._response_id = first._response_id
        second.responses = [
            ProviderUnavailableError("temporary continuation outage"),
            reported(second, second.tool_turn([("deliver", {"weather": "Sunny"})]), 3),
            reported(second, second.final_turn("Forecast delivered."), 4),
        ]
        install_failure(second)
        agent = build_agent(second, monkeypatch, hitl_db_path=db)
        agent.config.retries = 1
        register_tools(agent, log)
        captured = []
        use_async = entry in ("agenerate", "astream")
        if use_async:
            original_resume = agent.runtime.resume_tool_flow_async

            async def observed(*args: Any, **kwargs: Any) -> Any:
                response = await original_resume(*args, **kwargs)
                captured.append(response)
                return response

            monkeypatch.setattr(agent.runtime, "resume_tool_flow_async", observed)
        else:
            original_sync = agent.runtime.resume_tool_flow

            def observed_sync(*args: Any, **kwargs: Any) -> Any:
                response = original_sync(*args, **kwargs)
                captured.append(response)
                return response

            monkeypatch.setattr(agent.runtime, "resume_tool_flow", observed_sync)
        with tracked.track():
            answer = (
                asyncio.run(agent.aresume_run(run_id))
                if use_async
                else agent.resume_run(run_id)
            )
        assert answer == "Forecast delivered."
        assert log == [("lookup", "Paris"), ("forecast", "PX-1"), ("deliver", "Sunny")]
        assert len(first.requests) + len(second.requests) == 5
        # The failed continuation resends precisely the same tool results.
        assert second.requests[0] == second.requests[1]
        transcript = second.transcript(second.requests[-1])
        assert [item for item in transcript if item[0] == "call"] == [
            ("call", "lookup", {}),
            ("call", "lookup", {"city": "Paris"}),
            ("call", "forecast", {"code": "PX-1"}),
            ("call", "deliver", {"weather": "Sunny"}),
        ]
        results = [item[1] for item in transcript if item[0] == "result"]
        assert len(results) == 4
        assert "city" in results[0] and "required" in results[0].lower()
        assert results[1:] == ["PX-1", "Sunny", "Forecast: Sunny"]
        assert second.user_texts(second.requests[-1]) == [QUESTION]
        if isinstance(second, GeminiHarness):
            restored = [
                content
                for content in second.requests[-1]["contents"]
                if content["role"] == "model"
            ]
            assert restored == first.sent_turns + second.sent_turns

        response = captured[0]
        calls = response.metadata["model_calls"]
        assert len(calls) == len({call["call_id"] for call in calls}) == 5
        assert [call["status"] for call in calls] == ["ok", "ok", "error", "ok", "ok"]
        assert all(call["run_id"] == run_id for call in calls)
        assert all(call["provider"] == first.provider_name for call in calls)
        assert response.metadata["usage_complete"] is False
        assert (response.usage.input_tokens, response.usage.output_tokens) == (26, 14)
        assert response.usage.total_tokens == tracked.totals.total_tokens == 40
        assert tracked.totals.calls == 5 and tracked.totals.failed_calls == 1
        assert tracked.totals.unreported_calls == 0 and tracked.totals.complete is False
        assert agent.usage.totals.calls == 3
        assert agent.usage.totals.total_tokens == 24
        stored = HITLService(db_path=db).get_suspended_run(run_id)
        assert stored.status == "completed"
        assert stored.state["model_calls"] == [
            {key: value for key, value in call.items() if value is not None}
            for call in calls
        ]
        assert agent.conversation_history[-1] == {
            "role": "assistant",
            "content": answer,
        }
    finally:
        agent.close()
        original_agent.close()


@pytest.mark.parametrize("factory", MATRIX_HARNESSES, ids=lambda factory: factory.name)
@pytest.mark.parametrize("entry", ["chat", "agenerate"])
def test_exhausted_continuation_preserves_side_effect_and_usage(
    factory: Any, entry: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retain the earlier release gate's exhausted retry regression, with meters."""
    harness = factory()
    harness.responses = [
        reported(harness, harness.tool_turn([("lookup", {"city": "Paris"})]), 1),
        *[ProviderUnavailableError("still overloaded") for _ in range(3)],
    ]
    install_failure(harness)
    agent = build_agent(harness, monkeypatch)
    agent.config.retries = 2
    log: List[Tuple[str, str]] = []
    register_tools(agent, log)
    monkeypatch.setattr("praval.model_runtime._sleep", lambda duration: None)
    monkeypatch.setattr("praval.model_runtime._async_sleep", AsyncMock())
    tracked = UsageMeter()
    try:
        with tracked.track(), pytest.raises(ProviderUnavailableError):
            run_entry(agent, entry, QUESTION)
        assert log == [("lookup", "Paris")]
        assert len(harness.requests) == 4
        assert harness.requests[1] == harness.requests[2] == harness.requests[3]
        assert harness.transcript(harness.requests[-1]) == [
            ("call", "lookup", {"city": "Paris"}),
            ("result", "PX-1"),
        ]
        assert agent.conversation_history[-1] == {"role": "user", "content": QUESTION}
        assert tracked.totals.calls == agent.usage.totals.calls == 4
        assert tracked.totals.failed_calls == 3
        assert tracked.totals.total_tokens == agent.usage.totals.total_tokens == 7
        assert tracked.totals.complete is False
    finally:
        agent.close()
