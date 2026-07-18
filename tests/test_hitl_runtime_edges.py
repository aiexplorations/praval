"""Behavioral edge coverage for HITL policy, runtime, and service APIs."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

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
    assert runtime._parse_args('["not", "a", "mapping"]') == {}
    assert runtime._parse_args("not-json") == {}
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
    assert runtime._execute_tool({}, {}) == "Error: Tool function is not callable"

    def fail() -> None:
        raise RuntimeError("tool failed")

    assert runtime._execute_tool({"function": fail}, {}) == "Error: tool failed"


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
