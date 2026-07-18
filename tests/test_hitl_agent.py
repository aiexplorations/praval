"""Tests for Agent-level HITL APIs and behavior."""

import asyncio
from unittest.mock import Mock, patch

import pytest

from praval.core.agent import Agent
from praval.core.exceptions import InterventionRequired
from praval.hitl.service import HITLService
from praval.models import (
    ModelResponse,
    ProviderCapabilities,
    ToolCall,
    ToolResult,
    ToolSpec,
)


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


def test_agent_resumes_runtime_owned_tool_after_approval(tmp_path):
    executed = []

    class RuntimeToolProvider:
        capabilities = ProviderCapabilities(tools=True)

        def invoke(self, request):
            return ModelResponse(
                tool_calls=[
                    ToolCall(
                        id="call-runtime-1",
                        name="publish",
                        arguments={"value": "release"},
                    )
                ],
                metadata={"conversation_id": "conversation-1"},
            )

        def continue_with_tool_results(self, request, response, tool_results):
            assert response.metadata["conversation_id"] == "conversation-1"
            return ModelResponse(content=f"Published {tool_results[0].content}")

    db_path = str(tmp_path / "runtime-hitl.db")
    with patch(
        "praval.core.agent.ProviderFactory.create_provider",
        return_value=RuntimeToolProvider(),
    ):
        agent = Agent(
            "runtime-agent",
            provider="fake",
            model="fake-model",
            hitl_enabled=True,
            hitl_db_path=db_path,
        )

    @agent.tool
    def publish(value: str) -> str:
        executed.append(value)
        return value

    agent.tools["publish"]["requires_approval"] = True
    agent.tools["publish"]["approval_reason"] = "Publishing changes external state"

    with pytest.raises(InterventionRequired) as raised:
        agent.chat("Publish the release")

    assert executed == []
    agent.approve_intervention(raised.value.intervention_id, reviewer="release-manager")

    response = agent.resume_run(raised.value.run_id)

    assert response == "Published release"
    assert executed == ["release"]
    assert agent.conversation_history[-1] == {
        "role": "assistant",
        "content": "Published release",
    }
    suspended = HITLService(db_path=db_path).get_suspended_run(raised.value.run_id)
    assert suspended is not None
    assert suspended.status == "completed"


@pytest.mark.asyncio
async def test_agent_resumes_async_only_tool_on_original_loop(tmp_path):
    caller_loop = asyncio.get_running_loop()
    executed = []

    class AsyncRuntimeToolProvider:
        capabilities = ProviderCapabilities(tools=True)

        async def ainvoke(self, request):
            return ModelResponse(
                tool_calls=[
                    ToolCall(
                        id="call-mcp-1",
                        name="server__publish",
                        arguments={"value": "release"},
                    )
                ]
            )

        def continue_with_tool_results(self, request, response, tool_results):
            return ModelResponse(content=f"Published {tool_results[0].content}")

    db_path = str(tmp_path / "async-runtime-hitl.db")
    with patch(
        "praval.core.agent.ProviderFactory.create_provider",
        return_value=AsyncRuntimeToolProvider(),
    ):
        agent = Agent(
            "async-runtime-agent",
            provider="fake",
            model="fake-model",
            hitl_enabled=True,
            hitl_db_path=db_path,
        )

    async def publish(value: str) -> ToolResult:
        assert asyncio.get_running_loop() is caller_loop
        executed.append(value)
        return ToolResult(
            tool_call_id="mcp-internal",
            name="server__publish",
            content=value,
            metadata={"source": "mcp"},
        )

    agent.add_tool_spec(
        ToolSpec(
            name="server__publish",
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
            requires_approval=True,
            approval_reason="Publishing changes external state",
        ),
        publish,
        async_only=True,
    )

    with pytest.raises(InterventionRequired) as raised:
        await agent.agenerate("Publish the release")

    assert executed == []
    agent.approve_intervention(raised.value.intervention_id, reviewer="release-manager")

    response = await agent.aresume_run(raised.value.run_id)

    assert response == "Published release"
    assert executed == ["release"]
    suspended = HITLService(db_path=db_path).get_suspended_run(raised.value.run_id)
    assert suspended is not None
    assert suspended.status == "completed"
