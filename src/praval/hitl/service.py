"""Service facade for HITL operations used by Agent APIs and CLI."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import InterventionDecision, InterventionRequest, SuspendedRunState
from .store import HITLStore, get_hitl_store


class HITLService:
    """High-level helper over HITLStore for common operations."""

    def __init__(
        self, db_path: Optional[str] = None, store: Optional[HITLStore] = None
    ):
        self.store = store or get_hitl_store(db_path)

    def get_pending_interventions(
        self,
        *,
        run_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[InterventionRequest]:
        return self.store.list_pending_interventions(
            run_id=run_id,
            agent_name=agent_name,
            limit=limit,
        )

    def list_interventions(
        self,
        *,
        run_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[InterventionRequest]:
        return self.store.list_interventions(
            run_id=run_id,
            agent_name=agent_name,
            limit=limit,
        )

    def get_intervention(self, intervention_id: str) -> Optional[InterventionRequest]:
        return self.store.get_intervention(intervention_id)

    def approve_intervention(
        self,
        intervention_id: str,
        *,
        reviewer: str,
        edited_args: Optional[Dict[str, Any]] = None,
    ) -> InterventionRequest:
        decision = (
            InterventionDecision.EDIT
            if edited_args is not None
            else InterventionDecision.APPROVE
        )
        return self.store.decide_intervention(
            intervention_id,
            decision=decision,
            reviewer=reviewer,
            edited_args=edited_args,
        )

    def reject_intervention(
        self,
        intervention_id: str,
        *,
        reviewer: str,
        reason: str,
    ) -> InterventionRequest:
        return self.store.decide_intervention(
            intervention_id,
            decision=InterventionDecision.REJECT,
            reviewer=reviewer,
            reason=reason,
        )

    def get_suspended_run(self, run_id: str) -> Optional[SuspendedRunState]:
        return self.store.get_suspended_run(run_id)

    def mark_run_completed(self, run_id: str, response: str) -> None:
        suspended = self.store.get_suspended_run(run_id)
        if suspended is None:
            return
        state = dict(suspended.state)
        state["final_response"] = response
        self.store.update_suspended_run_status(run_id, status="completed", state=state)

    def cancel_run(self, run_id: str, reason: str) -> None:
        suspended = self.store.get_suspended_run(run_id)
        if suspended is None:
            return
        state = dict(suspended.state)
        state["cancel_reason"] = reason
        self.store.update_suspended_run_status(run_id, status="cancelled", state=state)
