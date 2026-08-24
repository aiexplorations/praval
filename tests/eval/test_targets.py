"""Registered-agent evaluation target adapter tests."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from praval import Agent
from praval.eval import AgentEvaluationTarget, EvalCase, EvaluationExecutionError
from praval.eval.dataset import LoadedEvalCase
from praval.models import ContentKind, ContentReference, ModelResponse, Usage


def _reference() -> ContentReference:
    return ContentReference(kind=ContentKind.PROMPT, sha256="a" * 64, size_bytes=2)


def _case(value) -> LoadedEvalCase:
    return LoadedEvalCase(
        case=EvalCase(case_id="case-1", name="Case", input=_reference()),
        input=value,
        expected_output=None,
        reference_contexts=(),
    )


class FakeProvider:
    provider_name = "fake"

    def __init__(self) -> None:
        self.requests = []

    async def ainvoke(self, request, tools=None):
        self.requests.append(request)
        return ModelResponse(
            content=json.dumps({"answer": "ok"}),
            model="target-model",
            usage=Usage(input_tokens=3, output_tokens=2, total_tokens=5),
            metadata={"response_id": "response-1"},
        )


@pytest.mark.asyncio
async def test_agent_target_returns_one_observation_and_restores_history(
    monkeypatch,
) -> None:
    provider = FakeProvider()
    monkeypatch.setattr(
        "praval.core.agent.ProviderFactory.create_provider",
        lambda *args, **kwargs: provider,
    )
    agent = Agent(
        "target",
        provider="fake",
        model="target-model",
        system_message="Return structured answers.",
    )
    original_history = list(agent.conversation_history)
    target = AgentEvaluationTarget(agent)

    result = await target.evaluate(_case({"question": "hello"}))

    assert result.output == '{"answer": "ok"}'
    assert result.observation.agent_name == "target"
    assert result.observation.response_id == "response-1"
    assert result.observation.usage is not None
    assert result.observation.usage.total_tokens == 5
    assert agent.conversation_history == original_history
    assert provider.requests[0].messages[-1].content == '{"question":"hello"}'
    agent.close()


@pytest.mark.asyncio
async def test_agent_target_rejects_non_json_input_before_paid_execution(
    monkeypatch,
) -> None:
    provider = FakeProvider()
    monkeypatch.setattr(
        "praval.core.agent.ProviderFactory.create_provider",
        lambda *args, **kwargs: provider,
    )
    agent = Agent("target", provider="fake", model="target-model")
    target = AgentEvaluationTarget(agent)

    with pytest.raises(EvaluationExecutionError, match="finite JSON"):
        await target.evaluate(_case(object()))

    assert provider.requests == []
    agent.close()


def test_agent_target_rejects_persistent_case_state() -> None:
    agent = SimpleNamespace(persist_state=True)

    with pytest.raises(EvaluationExecutionError, match="must not persist"):
        AgentEvaluationTarget(agent)


@pytest.mark.asyncio
async def test_agent_target_requires_model_response_and_one_observation() -> None:
    class InvalidAgent:
        persist_state = False
        name = "invalid"
        conversation_history = []

        async def agenerate(self, message):
            return "invalid"

    with pytest.raises(EvaluationExecutionError, match="invalid response"):
        await AgentEvaluationTarget(InvalidAgent()).evaluate(_case("hello"))

    class UnobservedAgent(InvalidAgent):
        async def agenerate(self, message):
            return ModelResponse(content="valid")

    with pytest.raises(EvaluationExecutionError, match="exactly one"):
        await AgentEvaluationTarget(UnobservedAgent()).evaluate(_case("hello"))
