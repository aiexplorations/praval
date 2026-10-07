"""Runtime helpers for provider tool-call HITL gating."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from ..core.exceptions import HITLConfigurationError, InterventionRequired
from ..models import ToolResult
from ..models.observation import HITLDecisionObservation
from ..runtime_observation import record_hitl_decision
from ..tool_execution import arun_tool, error_result, run_tool
from .models import InterventionDecision, InterventionRequest, InterventionStatus
from .policy import approval_reason, requires_approval, risk_level
from .store import HITLStore, get_hitl_store


class HITLRuntime:
    """Provider-facing runtime for tool execution with optional HITL pauses."""

    def __init__(
        self,
        *,
        run_id: str,
        agent_name: str,
        provider_name: str,
        hitl_enabled: bool,
        db_path: Optional[str] = None,
        trace_id: Optional[str] = None,
    ):
        self.run_id = run_id
        self.agent_name = agent_name
        self.provider_name = provider_name
        self.hitl_enabled = hitl_enabled
        self.trace_id = trace_id
        self.store: HITLStore = get_hitl_store(db_path)

    @staticmethod
    def _record_event(name: str, attributes: Dict[str, Any]) -> None:
        try:
            from ..observability.tracing import get_current_span

            span = get_current_span()
            if span:
                span.add_event(name, attributes)
        except Exception:
            # Observability is optional; do not fail HITL flow on event errors.
            pass

    @staticmethod
    def _tool_map(available_tools: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        mapping: Dict[str, Dict[str, Any]] = {}
        for tool in available_tools or []:
            func = tool.get("function")
            if callable(func):
                mapping[str(tool.get("name") or func.__name__)] = tool
        return mapping

    @staticmethod
    def _parse_args(raw_args: Any) -> Dict[str, Any]:
        if raw_args is None:
            return {}
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args)
                if isinstance(parsed, dict):
                    return parsed
                return {}
            except json.JSONDecodeError:
                return {}
        return {}

    def execute_or_interrupt(
        self,
        *,
        tool_call_id: str,
        function_name: str,
        raw_args: Any,
        available_tools: List[Dict[str, Any]],
        continuation_state: Dict[str, Any],
    ) -> str:
        """Execute a tool call or interrupt if policy requires approval.

        Returns the result content; ``execute_or_interrupt_result`` returns the
        typed ``ToolResult``.
        """
        return self.execute_or_interrupt_result(
            tool_call_id=tool_call_id,
            function_name=function_name,
            raw_args=raw_args,
            available_tools=available_tools,
            continuation_state=continuation_state,
        ).content

    def execute_or_interrupt_result(
        self,
        *,
        tool_call_id: str,
        function_name: str,
        raw_args: Any,
        available_tools: List[Dict[str, Any]],
        continuation_state: Dict[str, Any],
    ) -> ToolResult:
        """Execute a tool call or interrupt, returning a typed ``ToolResult``."""
        tool_def, args = self._prepare_or_interrupt(
            tool_call_id=tool_call_id,
            function_name=function_name,
            raw_args=raw_args,
            available_tools=available_tools,
            continuation_state=continuation_state,
        )
        if tool_def is None:
            return error_result(
                f"Unknown function: {function_name}", name=function_name
            )
        return self._execute_tool(tool_def, args)

    async def execute_or_interrupt_async(
        self,
        *,
        tool_call_id: str,
        function_name: str,
        raw_args: Any,
        available_tools: List[Dict[str, Any]],
        continuation_state: Dict[str, Any],
    ) -> ToolResult:
        """Async tool execution with the same approval interruption policy."""
        tool_def, args = self._prepare_or_interrupt(
            tool_call_id=tool_call_id,
            function_name=function_name,
            raw_args=raw_args,
            available_tools=available_tools,
            continuation_state=continuation_state,
        )
        if tool_def is None:
            return error_result(
                f"Unknown function: {function_name}", name=function_name
            )
        return await self._execute_tool_async(tool_def, args)

    def _prepare_or_interrupt(
        self,
        *,
        tool_call_id: str,
        function_name: str,
        raw_args: Any,
        available_tools: List[Dict[str, Any]],
        continuation_state: Dict[str, Any],
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Resolve a tool call and create an intervention when required."""
        tool_map = self._tool_map(available_tools)
        tool_def = tool_map.get(function_name)
        if tool_def is None:
            return None, {}

        args = self._parse_args(raw_args)
        if requires_approval(tool_def):
            if not self.hitl_enabled:
                raise HITLConfigurationError(
                    f"Tool '{function_name}' requires approval but agent "
                    f"'{self.agent_name}' has hitl=False"
                )

            intervention = self.store.create_intervention(
                run_id=self.run_id,
                agent_name=self.agent_name,
                provider_name=self.provider_name,
                tool_name=function_name,
                tool_call_id=tool_call_id,
                original_args=args,
                risk_level=risk_level(tool_def),
                approval_reason=approval_reason(tool_def),
                trace_id=self.trace_id,
                metadata={
                    "provider": self.provider_name,
                    "tool_call_id": tool_call_id,
                },
            )

            suspended_state = dict(continuation_state)
            suspended_state["intervention_id"] = intervention.id

            self.store.upsert_suspended_run(
                run_id=self.run_id,
                agent_name=self.agent_name,
                provider_name=self.provider_name,
                state=suspended_state,
                status="pending",
            )

            self._record_event(
                "hitl.intervention.created",
                {
                    "run_id": self.run_id,
                    "agent_name": self.agent_name,
                    "provider_name": self.provider_name,
                    "tool_name": function_name,
                    "tool_call_id": tool_call_id,
                    "intervention_id": intervention.id,
                    "risk_level": intervention.risk_level,
                },
            )
            record_hitl_decision(
                HITLDecisionObservation(
                    decision_id=intervention.id[:256],
                    decision="requested",
                    tool_name=function_name[:256] or None,
                )
            )

            raise InterventionRequired(
                intervention_id=intervention.id,
                run_id=self.run_id,
                agent_name=self.agent_name,
                tool_name=function_name,
                reason=intervention.approval_reason,
            )

        return tool_def, args

    def execute_with_decision(
        self,
        *,
        intervention: Union[InterventionRequest, Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
    ) -> str:
        """Execute the blocked tool call using a decided intervention.

        Returns the result content; ``execute_with_decision_result`` returns
        the typed ``ToolResult``.
        """
        return self.execute_with_decision_result(
            intervention=intervention,
            available_tools=available_tools,
        ).content

    def execute_with_decision_result(
        self,
        *,
        intervention: Union[InterventionRequest, Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
    ) -> ToolResult:
        """Execute a decided intervention, returning a typed ``ToolResult``."""
        tool_def, args, result = self._prepare_decision(
            intervention=intervention,
            available_tools=available_tools,
        )
        if result is not None:
            return result
        if tool_def is None:
            return error_result("Unknown function")
        return self._execute_tool(tool_def, args)

    async def execute_with_decision_async(
        self,
        *,
        intervention: Union[InterventionRequest, Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
    ) -> ToolResult:
        """Execute an approved or edited tool decision asynchronously."""
        tool_def, args, result = self._prepare_decision(
            intervention=intervention,
            available_tools=available_tools,
        )
        if result is not None:
            return result
        if tool_def is None:
            return error_result("Unknown function")
        return await self._execute_tool_async(tool_def, args)

    def _prepare_decision(
        self,
        *,
        intervention: Union[InterventionRequest, Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any], Optional[ToolResult]]:
        """Normalize a decision and resolve the tool without executing it."""
        if isinstance(intervention, dict):
            decision_raw = intervention.get("decision")
            status_raw = intervention.get("status", InterventionStatus.APPROVED.value)
            intervention = InterventionRequest(
                id=str(intervention.get("id", "")),
                run_id=str(intervention.get("run_id", self.run_id)),
                agent_name=str(intervention.get("agent_name", self.agent_name)),
                provider_name=str(
                    intervention.get("provider_name", self.provider_name)
                ),
                tool_name=str(intervention.get("tool_name", "")),
                tool_call_id=str(intervention.get("tool_call_id", "")),
                status=InterventionStatus(str(status_raw)),
                decision=(
                    InterventionDecision(str(decision_raw)) if decision_raw else None
                ),
                reason=str(intervention.get("reason", "") or ""),
                reviewer=str(intervention.get("reviewer", "") or ""),
                original_args=dict(intervention.get("original_args", {}) or {}),
                edited_args=(
                    dict(intervention.get("edited_args") or {})
                    if intervention.get("edited_args") is not None
                    else None
                ),
            )
        if intervention.decision is None:
            raise ValueError("Intervention has no decision")

        if intervention.decision == InterventionDecision.REJECT:
            reason = intervention.reason or "Rejected by human reviewer"
            self._record_event(
                "hitl.intervention.decided",
                {
                    "run_id": intervention.run_id,
                    "agent_name": intervention.agent_name,
                    "tool_name": intervention.tool_name,
                    "decision": intervention.decision.value,
                    "reviewer": intervention.reviewer,
                },
            )
            self._record_decision_fact(intervention)
            return (
                None,
                {},
                error_result(
                    f"Rejected by human reviewer: {reason}",
                    name=intervention.tool_name,
                ),
            )

        tool_map = self._tool_map(available_tools)
        tool_def = tool_map.get(intervention.tool_name)
        if tool_def is None:
            return (
                None,
                {},
                error_result(
                    f"Unknown function: {intervention.tool_name}",
                    name=intervention.tool_name,
                ),
            )

        if intervention.decision == InterventionDecision.EDIT:
            args = intervention.edited_args or {}
        else:
            args = intervention.original_args or {}

        self._record_event(
            "hitl.intervention.decided",
            {
                "run_id": intervention.run_id,
                "agent_name": intervention.agent_name,
                "tool_name": intervention.tool_name,
                "decision": intervention.decision.value,
                "reviewer": intervention.reviewer,
            },
        )
        self._record_decision_fact(intervention)

        return tool_def, args, None

    @staticmethod
    def _record_decision_fact(intervention: InterventionRequest) -> None:
        """Aggregate a privacy-safe human decision into active observations."""
        if not intervention.id:
            return
        decisions: Dict[
            InterventionDecision, Literal["approved", "edited", "rejected"]
        ] = {
            InterventionDecision.APPROVE: "approved",
            InterventionDecision.EDIT: "edited",
            InterventionDecision.REJECT: "rejected",
        }
        intervention_decision = intervention.decision
        if intervention_decision is None:
            return
        decision = decisions.get(intervention_decision)
        if decision is None:
            return
        record_hitl_decision(
            HITLDecisionObservation(
                decision_id=intervention.id[:256],
                decision=decision,
                tool_name=intervention.tool_name[:256] or None,
                reviewer_type="human" if intervention.reviewer else None,
            )
        )

    def _execute_tool(
        self, tool_def: Dict[str, Any], args: Dict[str, Any]
    ) -> ToolResult:
        """Validate arguments and run an approved or ungated tool."""
        if tool_def.get("async_only"):
            return error_result(
                "Error: This tool is async-only; use Agent.agenerate() "
                "or Agent.astream()."
            )
        return run_tool(tool_def, args)

    async def _execute_tool_async(
        self, tool_def: Dict[str, Any], args: Dict[str, Any]
    ) -> ToolResult:
        """Validate arguments and run a tool on the caller's event loop."""
        return await arun_tool(tool_def, args)
