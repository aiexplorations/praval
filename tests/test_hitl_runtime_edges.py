"""Behavioral edge coverage for HITL policy, runtime, and service APIs."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator, List
from unittest.mock import Mock, patch

import pytest

import praval.hitl.store as hitl_store_module
from praval.core.agent import Agent
from praval.core.exceptions import HITLConfigurationError, InterventionRequired
from praval.hitl.models import (
    InterventionDecision,
    InterventionRequest,
    InterventionStatus,
    SuspendedRunState,
)
from praval.hitl.policy import approval_reason, requires_approval, risk_level
from praval.hitl.runtime import HITLRuntime
from praval.hitl.service import HITLService
from praval.hitl.store import reset_hitl_stores
from praval.model_runtime import _build_hitl_runtime
from praval.models import ModelResponse, ProviderCapabilities, ToolCall, ToolResult


def _runtime(*, enabled: bool = False, store: Mock | None = None) -> HITLRuntime:
    with patch("praval.hitl.runtime.get_hitl_store", return_value=store or Mock()):
        return HITLRuntime(
            run_id="run-1",
            agent_name="agent-1",
            provider_name="provider-1",
            hitl_enabled=enabled,
            trace_id="trace-1",
        )


def _intervention(
    decision: InterventionDecision | None,
    *,
    tool_name: str = "multiply",
    original_args: dict | None = None,
    edited_args: dict | None = None,
    reason: str = "",
) -> InterventionRequest:
    return InterventionRequest(
        id="intervention-1",
        run_id="run-1",
        agent_name="agent-1",
        provider_name="provider-1",
        tool_name=tool_name,
        tool_call_id="call-1",
        status=InterventionStatus.APPROVED,
        decision=decision,
        original_args=original_args or {"value": 2},
        edited_args=edited_args,
        reason=reason,
        reviewer="reviewer",
    )


def test_hitl_policy_normalizes_defaults_and_invalid_risk():
    assert requires_approval({}, default=True) is True
    assert requires_approval({"requires_approval": 1}) is True
    assert risk_level({}) == "low"
    assert risk_level({"risk_level": " HIGH "}) == "high"
    assert risk_level({"risk_level": "unknown"}) == "low"
    assert approval_reason({}) == ""
    assert approval_reason({"approval_reason": None}) == ""
    assert approval_reason({"approval_reason": "Operator check"}) == "Operator check"


def test_hitl_runtime_parses_args_and_reports_unknown_tools():
    runtime = _runtime()
    assert runtime._parse_args(None) == {}
    assert runtime._parse_args({"value": 1}) == {"value": 1}
    assert runtime._parse_args('["not", "a", "mapping"]') == {
        "raw": '["not", "a", "mapping"]'
    }
    assert runtime._parse_args("not-json") == {"raw": "not-json"}
    assert runtime._parse_args("") == {}
    assert runtime._parse_args(42) == {}
    assert runtime._tool_map([{}, {"function": "not-callable"}]) == {}
    assert (
        runtime.execute_or_interrupt(
            tool_call_id="call-1",
            function_name="missing",
            raw_args={},
            available_tools=[],
            continuation_state={},
        )
        == "Unknown function: missing"
    )


def test_hitl_runtime_requires_configuration_for_gated_tools():
    runtime = _runtime(enabled=False)

    def deploy(target: str) -> str:
        return target

    with pytest.raises(HITLConfigurationError, match="requires approval"):
        runtime.execute_or_interrupt(
            tool_call_id="call-1",
            function_name="deploy",
            raw_args='{"target": "prod"}',
            available_tools=[{"function": deploy, "requires_approval": True}],
            continuation_state={},
        )


def test_hitl_runtime_persists_interruption_state():
    store = Mock()
    store.create_intervention.return_value = SimpleNamespace(
        id="intervention-1",
        risk_level="critical",
        approval_reason="Production change",
    )
    runtime = _runtime(enabled=True, store=store)

    def deploy(target: str) -> str:
        return target

    with pytest.raises(InterventionRequired) as raised:
        runtime.execute_or_interrupt(
            tool_call_id="call-1",
            function_name="deploy",
            raw_args={"target": "prod"},
            available_tools=[
                {
                    "function": deploy,
                    "requires_approval": True,
                    "risk_level": "critical",
                    "approval_reason": "Production change",
                }
            ],
            continuation_state={"cursor": 2},
        )

    assert raised.value.intervention_id == "intervention-1"
    store.create_intervention.assert_called_once()
    suspended = store.upsert_suspended_run.call_args.kwargs
    assert suspended["state"] == {"cursor": 2, "intervention_id": "intervention-1"}
    assert suspended["status"] == "pending"


@pytest.mark.asyncio
async def test_hitl_runtime_executes_async_tool_inside_running_loop():
    runtime = _runtime()

    async def double(value: int) -> int:
        return value * 2

    result = runtime.execute_or_interrupt(
        tool_call_id="call-1",
        function_name="double",
        raw_args='{"value": 4}',
        available_tools=[{"function": double}],
        continuation_state={},
    )

    assert result == "8"


def test_hitl_runtime_executes_decisions_and_reports_tool_errors():
    runtime = _runtime()

    def multiply(value: int) -> int:
        return value * 3

    tools = [{"function": multiply}]
    assert (
        runtime.execute_with_decision(
            intervention=_intervention(InterventionDecision.APPROVE),
            available_tools=tools,
        )
        == "6"
    )
    assert (
        runtime.execute_with_decision(
            intervention=_intervention(
                InterventionDecision.EDIT, edited_args={"value": 5}
            ),
            available_tools=tools,
        )
        == "15"
    )
    assert (
        runtime.execute_with_decision(
            intervention=_intervention(InterventionDecision.REJECT, reason="unsafe"),
            available_tools=tools,
        )
        == "Rejected by human reviewer: unsafe"
    )
    assert (
        runtime.execute_with_decision(
            intervention=_intervention(
                InterventionDecision.APPROVE, tool_name="missing"
            ),
            available_tools=tools,
        )
        == "Unknown function: missing"
    )
    not_callable = runtime._execute_tool({}, {})
    assert not_callable.content == "Error: Tool function is not callable"
    assert not_callable.is_error is True

    def fail() -> None:
        raise RuntimeError("tool failed")

    failed = runtime._execute_tool({"function": fail}, {})
    assert failed.content == "Error: RuntimeError: tool failed"
    assert failed.is_error is True


def test_hitl_runtime_accepts_dict_decisions_and_requires_a_decision():
    runtime = _runtime()

    def multiply(value: int) -> int:
        return value * 2

    assert (
        runtime.execute_with_decision(
            intervention={
                "id": "intervention-1",
                "tool_name": "multiply",
                "tool_call_id": "call-1",
                "status": "APPROVED",
                "decision": "EDIT",
                "original_args": {"value": 1},
                "edited_args": {"value": 7},
            },
            available_tools=[{"function": multiply}],
        )
        == "14"
    )

    with pytest.raises(ValueError, match="no decision"):
        runtime.execute_with_decision(
            intervention=_intervention(None), available_tools=[]
        )


def test_hitl_runtime_validates_edited_arguments_before_execution():
    runtime = _runtime()
    calls = []

    def multiply(value: int) -> int:
        calls.append(value)
        return value * 3

    tools = [{"function": multiply}]
    edited = runtime.execute_with_decision_result(
        intervention=_intervention(
            InterventionDecision.EDIT, edited_args={"value": "many"}
        ),
        available_tools=tools,
    )

    assert calls == []
    assert edited.is_error is True
    assert edited.content.startswith("Error: Invalid arguments for tool 'multiply'")
    assert "value: Input should be a valid integer" in edited.content
    coerced = runtime.execute_with_decision_result(
        intervention=_intervention(
            InterventionDecision.EDIT, edited_args={"value": "4"}
        ),
        available_tools=tools,
    )
    assert coerced.content == "12"
    assert calls == [4]


def test_hitl_runtime_typed_results_classify_rejection_and_unknown_tools():
    runtime = _runtime()

    def echo(value: int) -> int:
        return value

    tools = [{"function": echo}]
    rejected = runtime.execute_with_decision_result(
        intervention=_intervention(InterventionDecision.REJECT, reason="unsafe"),
        available_tools=tools,
    )
    unknown = runtime.execute_or_interrupt_result(
        tool_call_id="call-1",
        function_name="missing",
        raw_args={},
        available_tools=tools,
        continuation_state={},
    )

    assert rejected.content == "Rejected by human reviewer: unsafe"
    assert rejected.is_error is True
    assert unknown.content == "Unknown function: missing"
    assert unknown.is_error is True


def test_hitl_runtime_async_only_tool_is_an_error_result_in_sync():
    runtime = _runtime()

    async def lookup(query: str) -> str:
        return query

    result = runtime._execute_tool(
        {"function": lookup, "async_only": True}, {"query": "x"}
    )

    assert result.is_error is True
    assert "async-only" in result.content


@pytest.mark.asyncio
async def test_hitl_runtime_async_paths_return_typed_results_without_calling():
    runtime = _runtime()
    calls = []

    async def multiply(value: int) -> int:
        calls.append(value)
        return value * 3

    tools = [{"function": multiply}]
    invalid = await runtime.execute_with_decision_async(
        intervention=_intervention(
            InterventionDecision.APPROVE, original_args={"value": [1]}
        ),
        available_tools=tools,
    )
    valid = await runtime.execute_or_interrupt_async(
        tool_call_id="call-1",
        function_name="multiply",
        raw_args={"value": 2},
        available_tools=tools,
        continuation_state={},
    )

    assert calls == [2]
    assert invalid.is_error is True
    assert "value: Input should be a valid integer" in invalid.content
    assert valid.content == "6" and valid.is_error is False


def test_hitl_service_delegates_and_updates_suspended_runs():
    store = Mock()
    service = HITLService(store=store)
    pending = [Mock()]
    interventions = [Mock(), Mock()]
    store.list_pending_interventions.return_value = pending
    store.list_interventions.return_value = interventions
    store.get_intervention.return_value = Mock(id="i-1")

    assert (
        service.get_pending_interventions(run_id="r", agent_name="a", limit=3)
        is pending
    )
    assert (
        service.list_interventions(run_id="r", agent_name="a", limit=4) is interventions
    )
    assert service.get_intervention("i-1").id == "i-1"

    state = SuspendedRunState(
        run_id="r",
        agent_name="a",
        provider_name="p",
        status="pending",
        state={"cursor": 1},
    )
    store.get_suspended_run.return_value = state
    service.mark_run_completed("r", "done")
    store.update_suspended_run_status.assert_called_with(
        "r", status="completed", state={"cursor": 1, "final_response": "done"}
    )
    service.cancel_run("r", "operator request")
    store.update_suspended_run_status.assert_called_with(
        "r",
        status="cancelled",
        state={"cursor": 1, "cancel_reason": "operator request"},
    )

    store.get_suspended_run.return_value = None
    service.mark_run_completed("missing", "ignored")
    service.cancel_run("missing", "ignored")


class _OneToolProvider:
    """Asks for one ``lookup`` call, then answers with its result."""

    capabilities = ProviderCapabilities(tools=True)

    def invoke(self, request: Any) -> ModelResponse:
        return ModelResponse(
            tool_calls=[ToolCall(id="call-1", name="lookup", arguments={"key": "a"})]
        )

    def continue_with_tool_results(
        self, request: Any, response: Any, tool_results: List[ToolResult]
    ) -> ModelResponse:
        return ModelResponse(content=f"found {tool_results[0].content}")


@pytest.fixture
def isolated_hitl_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    """Point every HITL database location (env, default, HOME) at tmp_path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PRAVAL_HITL_DB_PATH", str(tmp_path / "env-hitl.db"))
    monkeypatch.setattr(
        "praval.hitl.store._DEFAULT_DB_PATH", str(tmp_path / "default-hitl.db")
    )
    reset_hitl_stores()
    yield tmp_path
    reset_hitl_stores()


def _db_files(root: Path) -> List[Path]:
    return sorted(root.rglob("*.db"))


def _tool_agent(**kwargs: Any) -> Agent:
    with patch(
        "praval.core.agent.ProviderFactory.create_provider",
        return_value=_OneToolProvider(),
    ):
        agent = Agent("no-hitl", provider="fake", model="fake-model", **kwargs)

    @agent.tool
    def lookup(key: str) -> str:
        return key.upper()

    return agent


def test_tool_call_without_hitl_never_opens_a_hitl_store(
    isolated_hitl_paths: Path,
) -> None:
    agent = _tool_agent()

    assert agent.chat("look it up") == "found A"
    assert _db_files(isolated_hitl_paths) == []
    assert hitl_store_module._store_by_path == {}


@pytest.mark.asyncio
async def test_async_tool_call_without_hitl_never_opens_a_hitl_store(
    isolated_hitl_paths: Path,
) -> None:
    agent = _tool_agent()

    response = await agent.agenerate("look it up")
    assert response.content == "found A"
    assert _db_files(isolated_hitl_paths) == []


def test_gated_tool_without_hitl_still_raises_and_opens_no_store(
    isolated_hitl_paths: Path,
) -> None:
    agent = _tool_agent()
    agent.tools["lookup"]["requires_approval"] = True

    with pytest.raises(HITLConfigurationError, match="has hitl=False"):
        agent.chat("look it up")
    assert _db_files(isolated_hitl_paths) == []


def test_gated_tool_with_hitl_still_suspends_and_resumes(
    isolated_hitl_paths: Path,
) -> None:
    agent = _tool_agent(hitl_enabled=True)
    agent.tools["lookup"]["requires_approval"] = True

    with pytest.raises(InterventionRequired) as raised:
        agent.chat("look it up")
    assert _db_files(isolated_hitl_paths) == [isolated_hitl_paths / "env-hitl.db"]
    agent.approve_intervention(raised.value.intervention_id, reviewer="qa")
    assert agent.resume_run(raised.value.run_id) == "found A"


def test_hitl_runtime_is_built_only_when_enabled_or_resuming() -> None:
    context = {
        "enabled": False,
        "run_id": "run-1",
        "agent_name": "agent-1",
        "provider_name": "provider-1",
    }
    with patch("praval.hitl.runtime.get_hitl_store", return_value=Mock()) as store:
        assert _build_hitl_runtime(context) is None
        assert _build_hitl_runtime(None) is None
        assert _build_hitl_runtime({**context, "enabled": True, "run_id": ""}) is None
        store.assert_not_called()

        enabled = _build_hitl_runtime({**context, "enabled": True})
        assert enabled is not None and enabled.hitl_enabled is True
        resuming = _build_hitl_runtime(context, for_resume=True)
        assert resuming is not None and resuming.hitl_enabled is False
