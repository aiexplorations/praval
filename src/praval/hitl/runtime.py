"""Runtime helpers for provider tool-call HITL gating."""

from __future__ import annotations

import inspect
import json
from typing import Any, Dict, List, Optional, Union

from ..core.exceptions import HITLConfigurationError, InterventionRequired
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
                mapping[func.__name__] = tool
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
        """Execute a tool call or interrupt if policy requires approval."""
        tool_map = self._tool_map(available_tools)
        tool_def = tool_map.get(function_name)
        if tool_def is None:
            return f"Unknown function: {function_name}"

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

            raise InterventionRequired(
                intervention_id=intervention.id,
                run_id=self.run_id,
                agent_name=self.agent_name,
                tool_name=function_name,
                reason=intervention.approval_reason,
            )

        return self._execute_tool(tool_def, args)

    def execute_with_decision(
        self,
        *,
        intervention: Union[InterventionRequest, Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
    ) -> str:
        """Execute the blocked tool call using a decided intervention."""
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
            return f"Rejected by human reviewer: {reason}"

        tool_map = self._tool_map(available_tools)
        tool_def = tool_map.get(intervention.tool_name)
        if tool_def is None:
            return f"Unknown function: {intervention.tool_name}"

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

        return self._execute_tool(tool_def, args)

    def _execute_tool(self, tool_def: Dict[str, Any], args: Dict[str, Any]) -> str:
        tool_func = tool_def.get("function")
        if not callable(tool_func):
            return "Error: Tool function is not callable"
        try:
            result = tool_func(**args)
            if inspect.iscoroutine(result):
                return (
                    "Error: Async tool functions are not supported in sync prov"
                    "ider flow"
                )
            return str(result)
        except (
            Exception
        ) as exc:  # pragma: no cover - error message path validated in provider tests
            return f"Error: {str(exc)}"
