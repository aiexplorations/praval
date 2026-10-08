"""Durable metering for failed and resumed HITL continuations."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from praval._metering_runtime import RunCapture, call_dict
from praval.core.agent import Agent
from praval.core.exceptions import InterventionRequired, ProviderUnavailableError
from praval.hitl.service import HITLService
from praval.metering import ModelCall, UsageMeter
from praval.models import ModelResponse, ProviderCapabilities, ToolCall, Usage
from praval.models.observation import ObservationKind
from praval.runtime_observation import ObservationScope, use_observation_recorder


class Provider:
    capabilities = ProviderCapabilities(tools=True)

    def __init__(self, failures: int = 1) -> None:
        self.initial = 0
        self.continued = 0
        self.failures = failures

    def invoke(self, request: Any, tools: Any = None) -> ModelResponse:
        self.initial += 1
        return ModelResponse(
            tool_calls=[ToolCall(id="write-1", name="write", arguments={})],
            usage=Usage(input_tokens=7, output_tokens=2, total_tokens=9),
        )

    async def ainvoke(self, request: Any, tools: Any = None) -> ModelResponse:
        return self.invoke(request, tools)

    def continue_with_tool_results(
        self, request: Any, response: Any, results: Any
    ) -> ModelResponse:
        self.continued += 1
        if self.failures:
            self.failures -= 1
            raise ProviderUnavailableError("resume attempt failed")
        return ModelResponse(
            content="done",
            usage=Usage(input_tokens=11, output_tokens=3, total_tokens=14),
        )


class Recorder:
    def __init__(self) -> None:
        self.observations: list[Any] = []

    def record(self, observation: Any) -> None:
        self.observations.append(observation)


def make_agent(
    provider: Provider, path: Path, writes: list[int], retries: int
) -> Agent:
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=provider
    ):
        agent = Agent(
            "meter-hitl",
            provider="openai",
            model="gpt-4o-mini",
            config={"retries": retries},
            hitl_enabled=True,
            hitl_db_path=str(path),
        )

    def write() -> str:
        writes.append(1)
        return "written"

    agent.tools["write"] = {"function": write, "requires_approval": True}
    return agent


def invoke(agent: Agent, use_async: bool) -> None:
    if use_async:
        asyncio.run(agent.agenerate("write"))
    else:
        agent.generate("write")


def resume(agent: Agent, run_id: str, use_async: bool) -> str:
    return (
        asyncio.run(agent.aresume_run(run_id))
        if use_async
        else agent.resume_run(run_id)
    )


def capture_responses(
    agent: Agent, use_async: bool, responses: list[ModelResponse]
) -> None:
    if use_async:
        original = agent.runtime.resume_tool_flow_async

        async def observed(*args: Any, **kwargs: Any) -> ModelResponse:
            response = await original(*args, **kwargs)
            responses.append(response)
            return response

        agent.runtime.resume_tool_flow_async = observed
    else:
        original_sync = agent.runtime.resume_tool_flow

        def observed_sync(*args: Any, **kwargs: Any) -> ModelResponse:
            response = original_sync(*args, **kwargs)
            responses.append(response)
            return response

        agent.runtime.resume_tool_flow = observed_sync


@pytest.mark.parametrize("use_async", [False, True])
@pytest.mark.parametrize("restart", [False, True])
@pytest.mark.parametrize("retry_budget", [0, 1])
def test_hitl_request_history_survives_failed_resume_without_rebilling(
    tmp_path: Path, use_async: bool, restart: bool, retry_budget: int
) -> None:
    provider = Provider()
    writes: list[int] = []
    path = tmp_path / "meter.db"
    agent = make_agent(provider, path, writes, retry_budget)
    original_agent = agent
    seen = []
    agent.usage.subscribe(seen.append)
    tracked = UsageMeter()
    responses: list[ModelResponse] = []
    try:
        with tracked.track():
            with pytest.raises(InterventionRequired) as pause:
                invoke(agent, use_async)
        run_id = pause.value.run_id
        service = HITLService(db_path=str(path))
        service.approve_intervention(pause.value.intervention_id, reviewer="test")
        if retry_budget == 0:
            with tracked.track():
                with pytest.raises(ProviderUnavailableError):
                    resume(agent, run_id, use_async)
            failed_state = service.get_suspended_run(run_id)
            assert failed_state.status == "pending"
            assert [call["status"] for call in failed_state.state["model_calls"]] == [
                "ok",
                "error",
            ]
            checkpoint = failed_state.state.get("resume_results", {}).get("checkpoint")
            if checkpoint is not None:
                assert checkpoint["model_calls"] == failed_state.state["model_calls"]
        if restart:
            agent.close()
            agent = make_agent(provider, path, writes, retry_budget)
            agent.usage.subscribe(seen.append)
        capture_responses(agent, use_async, responses)
        recorder = Recorder()
        with (
            tracked.track(),
            use_observation_recorder(recorder),
            ObservationScope(
                kind=ObservationKind.AGENT,
                agent_name="caller-scope",
                run_id="unrelated-caller-run",
            ),
            patch("praval.model_runtime._sleep"),
            patch("praval.model_runtime._async_sleep", new=AsyncMock()),
        ):
            assert resume(agent, run_id, use_async) == "done"
        response = responses[0]
        calls = response.metadata["model_calls"]
        assert len(calls) == provider.initial + provider.continued == 3
        assert len({call["call_id"] for call in calls}) == 3
        assert [call["status"] for call in calls] == ["ok", "error", "ok"]
        assert all(call["run_id"] == run_id for call in calls)
        assert response.metadata["usage_complete"] is False
        assert response.usage.total_tokens == 23
        assert tracked.totals.calls == 3
        assert tracked.totals.failed_calls == 1
        assert tracked.totals.total_tokens == 23
        assert len(seen) == len({call.call_id for call in seen}) == 3
        assert agent.usage.totals.calls == (
            (2 if retry_budget else 1) if restart else 3
        )
        assert writes == [1]
        stored = service.get_suspended_run(run_id)
        assert stored.status == "completed"
        assert [
            {key: value for key, value in call.items() if value is not None}
            for call in calls
        ] == stored.state["model_calls"]
        checkpoint = stored.state.get("resume_results", {}).get("checkpoint")
        if checkpoint is not None:
            assert checkpoint["model_calls"] == calls
        # The current resume observation meters current attempts, not restored calls.
        assert recorder.observations[0].usage.total_tokens == 14
    finally:
        agent.close()
        original_agent.close()


def record(index: int, *, status: str = "ok") -> dict[str, Any]:
    return call_dict(
        ModelCall(
            provider="openai",
            model="gpt-4o-mini",
            operation="resume",
            round_index=1,
            attempt=1,
            status=status,
            usage=(
                Usage(input_tokens=index, total_tokens=index)
                if status == "ok"
                else None
            ),
            duration_ms=0.1,
            started_at=datetime(2026, 10, 8, tzinfo=timezone.utc)
            + timedelta(seconds=index),
            agent_name="meter-hitl",
            call_id=str(index),
            run_id="original-run",
            parent_run_id="original-parent",
            correlation_id=None,
            response_id=None,
        )
    )


@pytest.mark.parametrize("checkpoint_identity", ["decision", "other"])
def test_capture_unions_checkpoint_history_and_keeps_first_identity(
    checkpoint_identity: str,
) -> None:
    outer = [record(1), record(3, status="error")]
    previous = {
        "intervention_id": "decision",
        "model_calls": outer,
        "resume_results": {
            "intervention_id": checkpoint_identity,
            "checkpoint": {
                "schema": "model_runtime_tool_v1",
                "model_calls": [record(1), record(2)],
            },
        },
    }
    lifetime = UsageMeter()
    runtime = type("Runtime", (), {"usage": lifetime})()
    with ObservationScope(
        kind=ObservationKind.AGENT, agent_name="new-caller", run_id="new-run"
    ):
        capture = RunCapture(runtime, previous)
    expected = ["1", "2", "3"] if checkpoint_identity == "decision" else ["1", "3"]
    assert [call.call_id for call in capture.meter.calls] == expected
    assert capture.run_id == "original-run"
    assert capture.parent_run_id == "original-parent"
    assert capture.meter.totals.failed_calls == 1
    assert capture.meter.totals.complete is False
    assert lifetime.totals.calls == 0


@pytest.mark.parametrize("use_async", [False, True])
@pytest.mark.parametrize("failed_resume", [False, True])
def test_legacy_hitl_unknown_history_stays_incomplete_after_resume(
    tmp_path: Path, use_async: bool, failed_resume: bool
) -> None:
    provider = Provider(failures=int(failed_resume))
    writes: list[int] = []
    path = tmp_path / "legacy.db"
    agent = make_agent(provider, path, writes, retries=0)
    original_agent = agent
    responses: list[ModelResponse] = []
    try:
        with pytest.raises(InterventionRequired) as pause:
            invoke(agent, use_async)
        run_id = pause.value.run_id
        service = HITLService(db_path=str(path))
        service.approve_intervention(pause.value.intervention_id, reviewer="test")
        stored = service.get_suspended_run(run_id)
        legacy = dict(stored.state)
        legacy.pop("model_calls", None)
        legacy.pop("model_call_history_complete", None)
        assert service.store.update_suspended_run_state(
            run_id, legacy, expected_status="pending"
        )
        if failed_resume:
            with pytest.raises(ProviderUnavailableError):
                resume(agent, run_id, use_async)
            failed = service.get_suspended_run(run_id)
            assert failed.state["model_call_history_complete"] is False
            assert len(failed.state["model_calls"]) == 1
        # The missing-history marker must survive loading a fresh runtime too.
        agent.close()
        agent = make_agent(provider, path, writes, retries=0)
        capture_responses(agent, use_async, responses)
        assert resume(agent, run_id, use_async) == "done"
        response = responses[0]
        calls = response.metadata["model_calls"]
        assert len(calls) == 1 + int(failed_resume)
        assert response.metadata["usage_complete"] is False
        assert response.usage.total_tokens == 14
        assert all(call["run_id"] == run_id for call in calls)
        assert writes == [1]
        assert agent.usage.totals.calls == 1
        stored = service.get_suspended_run(run_id)
        assert stored.state["model_call_history_complete"] is False
        assert [
            {key: value for key, value in call.items() if value is not None}
            for call in calls
        ] == stored.state["model_calls"]
    finally:
        agent.close()
        original_agent.close()
