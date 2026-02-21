"""Tests for HITL store and service lifecycle."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from praval.hitl.models import InterventionDecision, InterventionStatus
from praval.hitl.service import HITLService
from praval.hitl.store import HITLStore, get_hitl_store, reset_hitl_stores


def test_hitl_store_create_and_decide_intervention(tmp_path: Path):
    db_path = tmp_path / "hitl.db"
    store = HITLStore(str(db_path))

    intervention = store.create_intervention(
        run_id="run-1",
        agent_name="agent-a",
        provider_name="openai",
        tool_name="dangerous_tool",
        tool_call_id="call-1",
        original_args={"x": 1},
        risk_level="high",
        approval_reason="high risk",
    )

    assert intervention.status == InterventionStatus.PENDING
    assert intervention.tool_name == "dangerous_tool"

    decided = store.decide_intervention(
        intervention.id,
        decision=InterventionDecision.APPROVE,
        reviewer="alice",
    )

    assert decided.status == InterventionStatus.APPROVED
    assert decided.decision == InterventionDecision.APPROVE
    assert decided.reviewer == "alice"


def test_hitl_service_approve_and_reject(tmp_path: Path):
    db_path = tmp_path / "hitl.db"
    service = HITLService(db_path=str(db_path))

    intervention = service.store.create_intervention(
        run_id="run-2",
        agent_name="agent-b",
        provider_name="anthropic",
        tool_name="tool_b",
        tool_call_id="call-2",
        original_args={"name": "bob"},
    )

    pending = service.get_pending_interventions(agent_name="agent-b")
    assert len(pending) == 1

    approved = service.approve_intervention(
        intervention.id,
        reviewer="reviewer",
        edited_args={"name": "alice"},
    )
    assert approved.status == InterventionStatus.APPROVED
    assert approved.decision == InterventionDecision.EDIT
    assert approved.edited_args == {"name": "alice"}

    rejected_seed = service.store.create_intervention(
        run_id="run-3",
        agent_name="agent-b",
        provider_name="cohere",
        tool_name="tool_c",
        tool_call_id="call-3",
        original_args={},
    )
    rejected = service.reject_intervention(
        rejected_seed.id,
        reviewer="reviewer",
        reason="unsafe",
    )
    assert rejected.status == InterventionStatus.REJECTED
    assert rejected.decision == InterventionDecision.REJECT
    assert rejected.reason == "unsafe"


def test_hitl_store_persistence_recovery_after_restart(tmp_path: Path):
    db_path = tmp_path / "hitl.db"
    service_a = HITLService(db_path=str(db_path))

    intervention = service_a.store.create_intervention(
        run_id="run-restart-1",
        agent_name="agent-restart",
        provider_name="openai",
        tool_name="dangerous_action",
        tool_call_id="call-restart-1",
        original_args={"target": "prod"},
    )
    service_a.store.upsert_suspended_run(
        run_id="run-restart-1",
        agent_name="agent-restart",
        provider_name="openai",
        state={"schema": "openai_tool_v1", "current_index": 0},
        status="pending",
    )

    # Simulate process restart by creating a fresh service on same SQLite DB.
    service_b = HITLService(db_path=str(db_path))
    pending = service_b.get_pending_interventions(run_id="run-restart-1")
    assert len(pending) == 1
    assert pending[0].id == intervention.id

    suspended = service_b.get_suspended_run("run-restart-1")
    assert suspended is not None
    assert suspended.state["current_index"] == 0


def test_hitl_store_expire_list_and_decide_edge_cases(tmp_path: Path):
    store = HITLStore(str(tmp_path / "hitl.db"))

    expired = store.create_intervention(
        run_id="run-expired",
        agent_name="agent-e",
        provider_name="openai",
        tool_name="tool_e",
        tool_call_id="call-expired",
        original_args={"a": 1},
        expires_in_seconds=1,
    )
    no_expiry = store.create_intervention(
        run_id="run-open",
        agent_name="agent-e",
        provider_name="openai",
        tool_name="tool_open",
        tool_call_id="call-open",
        original_args={"b": 2},
        expires_in_seconds=0,
    )

    with store._connect() as conn:  # type: ignore[attr-defined]
        conn.execute(
            "UPDATE interventions SET expires_at = ? WHERE id = ?",
            (store._now_ts() - 1, expired.id),  # type: ignore[attr-defined]
        )
        conn.commit()

    # list_pending_interventions internally expires overdue records first.
    pending = store.list_pending_interventions(agent_name="agent-e")
    assert all(item.id != expired.id for item in pending)
    assert any(item.id == no_expiry.id for item in pending)

    expired_after = store.get_intervention(expired.id)
    assert expired_after is not None
    assert expired_after.status == InterventionStatus.EXPIRED

    # decide_intervention should fail for missing intervention IDs.
    try:
        store.decide_intervention(
            "missing-id",
            decision=InterventionDecision.APPROVE,
            reviewer="tester",
        )
        assert False, "Expected missing intervention to raise"
    except ValueError as exc:
        assert "not found" in str(exc)

    approved = store.decide_intervention(
        no_expiry.id,
        decision=InterventionDecision.APPROVE,
        reviewer="tester",
    )
    assert approved.status == InterventionStatus.APPROVED

    # Deciding again should hit "not pending" path.
    try:
        store.decide_intervention(
            no_expiry.id,
            decision=InterventionDecision.REJECT,
            reviewer="tester",
        )
        assert False, "Expected already-decided intervention to raise"
    except ValueError as exc:
        assert "not pending" in str(exc)


def test_hitl_store_suspended_run_lifecycle(tmp_path: Path):
    store = HITLStore(str(tmp_path / "hitl.db"))

    created = store.upsert_suspended_run(
        run_id="run-s1",
        agent_name="agent-s",
        provider_name="openai",
        state={"cursor": 0, "value": "a"},
    )
    assert created.status == "pending"
    assert created.state["cursor"] == 0

    store.update_suspended_run_status("run-s1", "waiting")
    waiting = store.get_suspended_run("run-s1")
    assert waiting is not None
    assert waiting.status == "waiting"
    assert waiting.state["value"] == "a"

    store.update_suspended_run_status("run-s1", "approved", state={"cursor": 3})
    approved = store.get_suspended_run("run-s1")
    assert approved is not None
    assert approved.status == "approved"
    assert approved.state == {"cursor": 3}
    assert approved.updated_at >= approved.created_at - timedelta(seconds=1)

    store.delete_suspended_run("run-s1")
    assert store.get_suspended_run("run-s1") is None


def test_get_hitl_store_cache_and_reset(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "cache-hitl.db"
    monkeypatch.setenv("PRAVAL_HITL_DB_PATH", str(db_path))

    reset_hitl_stores()
    store_a = get_hitl_store()
    store_b = get_hitl_store()
    assert store_a is store_b

    reset_hitl_stores()
    store_c = get_hitl_store()
    assert store_c is not store_a
