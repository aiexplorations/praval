"""Tests for Agent-level HITL APIs and behavior."""

from unittest.mock import Mock, patch

import pytest

from praval.core.agent import Agent
from praval.core.exceptions import InterventionRequired
from praval.hitl.service import HITLService


class _RaisingProvider:
    def generate(self, messages, tools=None, hitl_context=None):
        raise InterventionRequired(
            intervention_id="int-1",
            run_id=hitl_context["run_id"],
            agent_name=hitl_context["agent_name"],
            tool_name="tool_a",
            reason="approval required",
        )


class _ResumableProvider:
    def generate(self, messages, tools=None, hitl_context=None):
        return "ok"

    def resume_tool_flow(self, suspended_state, tools, hitl_context=None):
        return "resumed-response"


def test_agent_chat_raises_intervention_required():
    with patch(
        "praval.core.agent.ProviderFactory.create_provider",
        return_value=_RaisingProvider(),
    ):
        agent = Agent("a1", provider="openai", hitl_enabled=True)

    with pytest.raises(InterventionRequired):
        agent.chat("hello")


def test_agent_resume_run_and_intervention_api(tmp_path):
    db_path = str(tmp_path / "hitl.db")
    with patch(
        "praval.core.agent.ProviderFactory.create_provider",
        return_value=_ResumableProvider(),
    ):
        agent = Agent("a2", provider="openai", hitl_enabled=True, hitl_db_path=db_path)

    service = HITLService(db_path=db_path)
    intervention = service.store.create_intervention(
        run_id="run-a2",
        agent_name="a2",
        provider_name="openai",
        tool_name="tool_x",
        tool_call_id="call-x",
        original_args={"x": 1},
    )
    service.store.upsert_suspended_run(
        run_id="run-a2",
        agent_name="a2",
        provider_name="openai",
        state={"schema": "openai_tool_v1", "intervention_id": intervention.id},
        status="pending",
    )

    pending = agent.get_pending_interventions(run_id="run-a2")
    assert len(pending) == 1

    agent.approve_intervention(intervention.id, reviewer="qa")

    response = agent.resume_run("run-a2")
    assert response == "resumed-response"
    assert agent.conversation_history[-1]["content"] == "resumed-response"


def test_agent_hitl_default_disabled():
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=Mock()
    ):
        agent = Agent("a3", provider="openai")
    assert agent._hitl_enabled is False
