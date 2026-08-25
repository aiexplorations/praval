"""Strict model and agent judge tests with deterministic fake providers."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from praval import Agent, ToolSpec
from praval.config import PravalConfig, ResolvedAgentConfig
from praval.core.registry import PravalRegistry
from praval.eval import (
    AgentJudge,
    EvalCase,
    EvaluationSubject,
    JudgeConfigurationError,
    JudgeContext,
    LoadedEvalCase,
    ModelJudge,
    ResultStatus,
    TargetResult,
    is_evaluation_call,
)
from praval.model_runtime import ModelRuntime
from praval.models import (
    ContentKind,
    ContentReference,
    ExecutionObservation,
    ModelResponse,
    ObservationKind,
    ObservationStatus,
    ProviderCapabilities,
    Usage,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def _reference(kind: ContentKind, value: Any) -> ContentReference:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return ContentReference(
        kind=kind,
        sha256=hashlib.sha256(encoded).hexdigest(),
        size_bytes=len(encoded),
    )


def _context(
    *, target_agent: str = "target-agent", target_model: str = "target-model"
) -> JudgeContext:
    loaded = LoadedEvalCase(
        case=EvalCase(
            case_id="case-1",
            name="Quality",
            input=_reference(ContentKind.PROMPT, {"question": "hello"}),
            expected_output=_reference(ContentKind.RESPONSE, "expected"),
            reference_contexts=(_reference(ContentKind.CONTEXT, "reference"),),
            expected_tool_calls=("lookup",),
        ),
        input={"question": "hello"},
        expected_output="expected",
        reference_contexts=("reference",),
    )
    observation = ExecutionObservation(
        observation_id="observation-1",
        run_id="execution-1",
        kind=ObservationKind.AGENT,
        agent_name=target_agent,
        response_id="response-1",
        provider="fake",
        model=target_model,
        started_at=NOW,
        ended_at=NOW + timedelta(milliseconds=10),
        duration_ms=10,
        status=ObservationStatus.OK,
    )
    subject = EvaluationSubject.from_observation(
        evaluation_run_id="evaluation-1",
        case_id=loaded.case.case_id,
        observation=observation,
    )
    return JudgeContext(
        evaluation_run_id="evaluation-1",
        case=loaded,
        subject=subject,
        target_result=TargetResult(
            observation=observation,
            output={"answer": "candidate"},
        ),
    )


def _payload(*, status: str = "passed", score: float | None = 0.9) -> str:
    return json.dumps(
        {
            "status": status,
            "score": score,
            "label": "pass" if status == "passed" else None,
            "explanation": "The candidate follows the rubric.",
            "evidence": ["candidate answer"],
        }
    )


class FakeJudgeProvider:
    provider_name = "fake"
    capabilities = ProviderCapabilities(structured_outputs=True, tools=True)

    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.requests = []
        self.tools = []
        self.evaluation_markers = []

    async def ainvoke(self, request, tools=None):
        self.requests.append(request)
        self.tools.append(list(tools or []))
        self.evaluation_markers.append(is_evaluation_call())
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            outcome = outcome()
        if asyncio.iscoroutine(outcome):
            outcome = await outcome
        return outcome


def _runtime(provider: FakeJudgeProvider) -> ModelRuntime:
    config = SimpleNamespace(
        model="judge-model",
        temperature=0.8,
        max_output_tokens=256,
        max_tool_rounds=8,
        retries=3,
        provider_options={},
        stream_options={},
        strict_tools=True,
        reasoning=None,
        response_schema=None,
        timeout=None,
    )
    return ModelRuntime(provider=provider, provider_name="fake", config=config)


@pytest.mark.asyncio
async def test_model_judge_uses_strict_envelope_and_records_bounded_facts() -> None:
    provider = FakeJudgeProvider(
        [
            ModelResponse(
                content=_payload(),
                model="judge-model",
                usage=Usage(input_tokens=10, output_tokens=4, total_tokens=14),
                metadata={"cost_usd": 0.012},
            )
        ]
    )
    judge = ModelJudge(
        name="quality",
        runtime=_runtime(provider),
        judge_version="judge-v1",
        rubric="Score correctness using only the supplied reference.",
        rubric_version="rubric-v3",
    )

    result = await judge.evaluate(_context())

    assert result.status is ResultStatus.PASSED
    assert result.score == 0.9
    assert result.label == "pass"
    assert result.explanation is None
    assert result.evidence[0].kind is ContentKind.JUDGE_EVIDENCE
    assert result.usage is not None
    assert result.usage.total_tokens == 14
    assert result.cost_usd == pytest.approx(0.012)
    assert result.attempt_count == 1
    assert result.duration_ms is not None
    assert result.prompt_sha256 == judge.prompt_sha256(_context())
    request = provider.requests[0]
    assert request.temperature == 0
    assert request.response_schema is not None
    assert request.response_schema.strict is True
    assert request.metadata["praval.evaluation"] is True
    assert request.metadata["praval.evaluation.judge"] == "quality"
    assert request.messages[0].role == "system"
    assert "trusted rubric" in request.messages[0].content.lower()
    assert "untrusted candidate" in request.messages[1].content.lower()
    assert provider.evaluation_markers == [True]
    assert is_evaluation_call() is False


@pytest.mark.asyncio
async def test_model_judge_retries_invalid_output_and_aggregates_usage() -> None:
    provider = FakeJudgeProvider(
        [
            ModelResponse(
                content='{"status":"passed","unexpected":true}',
                model="judge-model",
                usage=Usage(input_tokens=2, output_tokens=1, total_tokens=3),
                metadata={"cost_usd": 0.001},
            ),
            ModelResponse(
                content=_payload(),
                model="judge-model",
                usage=Usage(input_tokens=5, output_tokens=2, total_tokens=7),
                metadata={"cost_usd": 0.002},
            ),
        ]
    )
    judge = ModelJudge(
        name="quality",
        runtime=_runtime(provider),
        judge_version="1",
        rubric="Be correct.",
        rubric_version="1",
        max_attempts=2,
    )

    result = await judge.evaluate(_context())

    assert result.status is ResultStatus.PASSED
    assert result.attempt_count == 2
    assert result.usage is not None
    assert result.usage.input_tokens == 7
    assert result.usage.output_tokens == 3
    assert result.usage.total_tokens == 10
    assert result.cost_usd == pytest.approx(0.003)
    assert len(provider.requests) == 2


@pytest.mark.asyncio
async def test_model_judge_turns_timeout_and_invalid_schema_into_safe_errors() -> None:
    async def never_finishes() -> ModelResponse:
        await asyncio.sleep(1)
        return ModelResponse(content=_payload())

    timeout_provider = FakeJudgeProvider([never_finishes, never_finishes])
    timeout_judge = ModelJudge(
        name="quality",
        runtime=_runtime(timeout_provider),
        judge_version="1",
        rubric="Be correct.",
        rubric_version="1",
        timeout_seconds=0.01,
        max_attempts=2,
    )

    timeout = await timeout_judge.evaluate(_context())

    assert timeout.status is ResultStatus.ERROR
    assert timeout.error_type == "JudgeTimeoutError"
    assert timeout.attempt_count == 2
    assert timeout.score is None
    assert timeout.label is None

    invalid_provider = FakeJudgeProvider(
        [ModelResponse(content="not-json"), ModelResponse(content="[]")]
    )
    invalid_judge = ModelJudge(
        name="quality",
        runtime=_runtime(invalid_provider),
        judge_version="1",
        rubric="Be correct.",
        rubric_version="1",
        max_attempts=2,
    )

    invalid = await invalid_judge.evaluate(_context())

    assert invalid.status is ResultStatus.ERROR
    assert invalid.error_type == "JudgeResponseError"
    assert invalid.attempt_count == 2
    assert "not-json" not in invalid.model_dump_json()


@pytest.mark.asyncio
async def test_model_judge_rejects_self_evaluation_without_calling_provider() -> None:
    provider = FakeJudgeProvider([ModelResponse(content=_payload())])
    judge = ModelJudge(
        name="quality",
        runtime=_runtime(provider),
        judge_version="1",
        rubric="Be correct.",
        rubric_version="1",
    )

    result = await judge.evaluate(_context(target_model="judge-model"))

    assert result.status is ResultStatus.ERROR
    assert result.error_type == "SelfEvaluationRejected"
    assert provider.requests == []


@pytest.mark.asyncio
async def test_judge_cancellation_is_never_converted_to_a_result() -> None:
    provider = FakeJudgeProvider([asyncio.CancelledError()])
    judge = ModelJudge(
        name="quality",
        runtime=_runtime(provider),
        judge_version="1",
        rubric="Be correct.",
        rubric_version="1",
    )

    with pytest.raises(asyncio.CancelledError):
        await judge.evaluate(_context())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        '{"status":"passed","score":NaN,"label":"pass"}',
        '{"status":"passed","score":0.9}',
        '{"status":"passed","score":0.9,"label":"pass","evidence":[""]}',
    ],
)
async def test_model_judge_rejects_non_finite_and_incomplete_payloads(
    content: str,
) -> None:
    provider = FakeJudgeProvider([ModelResponse(content=content)])
    judge = ModelJudge(
        name="quality",
        runtime=_runtime(provider),
        judge_version="1",
        rubric="Be correct.",
        rubric_version="1",
        max_attempts=1,
    )

    result = await judge.evaluate(_context())

    assert result.status is ResultStatus.ERROR
    assert result.error_type == "JudgeResponseError"


@pytest.mark.asyncio
@pytest.mark.parametrize("cost", [True, -0.1])
async def test_model_judge_rejects_invalid_cost_metadata(cost: Any) -> None:
    provider = FakeJudgeProvider(
        [ModelResponse(content=_payload(), metadata={"cost_usd": cost})]
    )
    judge = ModelJudge(
        name="quality",
        runtime=_runtime(provider),
        judge_version="1",
        rubric="Be correct.",
        rubric_version="1",
        max_attempts=1,
    )

    result = await judge.evaluate(_context())

    assert result.status is ResultStatus.ERROR
    assert result.error_type == "JudgeResponseError"


@pytest.mark.asyncio
async def test_model_judge_reports_provider_error_and_supports_pydantic_config() -> (
    None
):
    provider = FakeJudgeProvider([RuntimeError("provider unavailable")])
    runtime = ModelRuntime(
        provider=provider,
        provider_name="fake",
        config=ResolvedAgentConfig(
            name="judge",
            provider="fake",
            model="judge-model",
            temperature=0.7,
        ),
    )
    judge = ModelJudge(
        name="quality",
        runtime=runtime,
        judge_version="1",
        rubric="Be correct.",
        rubric_version="1",
        max_attempts=1,
    )

    result = await judge.evaluate(_context())

    assert result.status is ResultStatus.ERROR
    assert result.error_type == "ProviderError"
    assert provider.requests[0].temperature == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("limit_name", "limit", "error_type"),
    [
        ("max_input_tokens", 3, "JudgeInputTokenLimitExceeded"),
        ("max_cost_usd", 0.001, "JudgeCostLimitExceeded"),
    ],
)
async def test_model_judge_enforces_usage_and_cost_budgets(
    limit_name: str, limit: float, error_type: str
) -> None:
    provider = FakeJudgeProvider(
        [
            ModelResponse(
                content=_payload(),
                usage=Usage(input_tokens=5, output_tokens=2, total_tokens=7),
                metadata={"cost_usd": 0.01},
            )
        ]
    )
    judge = ModelJudge(
        name="quality",
        runtime=_runtime(provider),
        judge_version="1",
        rubric="Be correct.",
        rubric_version="1",
        **{limit_name: limit},
    )

    result = await judge.evaluate(_context())

    assert result.status is ResultStatus.ERROR
    assert result.error_type == error_type
    assert result.attempt_count == 1
    assert result.usage is not None
    assert result.cost_usd == pytest.approx(0.01)


def test_judge_configuration_and_input_validation() -> None:
    provider = FakeJudgeProvider([ModelResponse(content=_payload())])
    common = {
        "name": "quality",
        "runtime": _runtime(provider),
        "judge_version": "1",
        "rubric": "Be correct.",
        "rubric_version": "1",
    }
    with pytest.raises(JudgeConfigurationError, match="name"):
        ModelJudge(**{**common, "name": ""})
    with pytest.raises(JudgeConfigurationError, match="timeout_seconds"):
        ModelJudge(**common, timeout_seconds=0)
    with pytest.raises(JudgeConfigurationError, match="max_attempts"):
        ModelJudge(**common, max_attempts=0)
    with pytest.raises(JudgeConfigurationError, match="max_input_tokens"):
        ModelJudge(**common, max_input_tokens=0)
    with pytest.raises(JudgeConfigurationError, match="max_cost_usd"):
        ModelJudge(**common, max_cost_usd=0)

    judge = ModelJudge(**common)
    context = _context()
    invalid_context = JudgeContext(
        evaluation_run_id=context.evaluation_run_id,
        case=context.case,
        subject=context.subject,
        target_result=TargetResult(
            observation=context.target_result.observation,
            output=object(),
        ),
    )
    with pytest.raises(Exception, match="finite JSON"):
        judge.prompt_sha256(invalid_context)


@pytest.mark.asyncio
async def test_judge_rejects_naive_clock() -> None:
    provider = FakeJudgeProvider([ModelResponse(content=_payload())])
    judge = ModelJudge(
        name="quality",
        runtime=_runtime(provider),
        judge_version="1",
        rubric="Be correct.",
        rubric_version="1",
        clock=lambda: NOW.replace(tzinfo=None),
    )

    with pytest.raises(JudgeConfigurationError, match="aware timestamp"):
        await judge.evaluate(_context())


@pytest.mark.asyncio
async def test_model_judge_resolves_validated_model_profile() -> None:
    provider = FakeJudgeProvider([ModelResponse(content=_payload())])
    config = PravalConfig.model_validate(
        {
            "models": {
                "judge-model-profile": {
                    "provider": "fake",
                    "model": "judge-model",
                    "temperature": 0.7,
                    "max_output_tokens": 321,
                }
            },
            "eval": {
                "judges": {
                    "quality": {
                        "model": "judge-model-profile",
                        "timeout_seconds": 2,
                        "max_attempts": 1,
                        "max_input_tokens": 100,
                        "max_cost_usd": 0.5,
                    }
                }
            },
        }
    )
    judge = ModelJudge.from_config(
        "quality",
        config,
        rubric="Be correct.",
        rubric_version="1",
        provider_factory=lambda provider_name, runtime_config: provider,
    )

    result = await judge.evaluate(_context())

    assert result.status is ResultStatus.PASSED
    assert provider.requests[0].temperature == 0
    assert provider.requests[0].max_output_tokens == 321
    assert judge.timeout_seconds == 2
    assert judge.max_attempts == 1


def test_model_judge_config_resolution_rejects_wrong_profile_kind() -> None:
    config = PravalConfig.model_validate(
        {
            "models": {
                "judge-model-profile": {
                    "provider": "fake",
                    "model": "judge-model",
                }
            },
            "agents": {"evaluator": {"model": "judge-model-profile"}},
            "eval": {"judges": {"quality": {"agent": "evaluator"}}},
        }
    )
    with pytest.raises(JudgeConfigurationError, match="unknown judge profile"):
        ModelJudge.from_config(
            "missing", config, rubric="Be correct.", rubric_version="1"
        )
    with pytest.raises(JudgeConfigurationError, match="does not reference a model"):
        ModelJudge.from_config(
            "quality", config, rubric="Be correct.", rubric_version="1"
        )


def test_model_judge_rejects_missing_model_in_manually_assembled_config() -> None:
    config = SimpleNamespace(
        eval=SimpleNamespace(
            judges={"quality": SimpleNamespace(model="missing-model")}
        ),
        models={},
    )

    with pytest.raises(JudgeConfigurationError, match="unknown model"):
        ModelJudge.from_config(
            "quality", config, rubric="Be correct.", rubric_version="1"
        )


@pytest.mark.asyncio
async def test_agent_judge_runs_normal_agent_flow_with_only_safe_allowed_tools(
    monkeypatch,
) -> None:
    provider = FakeJudgeProvider(
        [ModelResponse(content=_payload(), model="judge-model")]
    )
    monkeypatch.setattr(
        "praval.core.agent.ProviderFactory.create_provider",
        lambda *args, **kwargs: provider,
    )
    agent = Agent(
        "evaluator",
        provider="fake",
        model="judge-model",
        config={"temperature": 0, "retries": 0},
        system_message="You are the configured evaluator.",
    )

    def lookup(query: str) -> str:
        return query

    def mutate(value: str) -> str:
        return value

    agent.add_tool_spec(
        ToolSpec(
            name="lookup",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            metadata={"evaluation_safe": True, "read_only": True},
        ),
        lookup,
    )
    agent.add_tool_spec(
        ToolSpec(
            name="mutate",
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
            metadata={"evaluation_safe": False, "read_only": False},
        ),
        mutate,
    )
    original_history = list(agent.conversation_history)
    judge = AgentJudge(
        name="quality",
        agent=agent,
        judge_version="1",
        rubric="Use the lookup tool only if needed.",
        rubric_version="1",
        allowed_tools=("lookup",),
        tool_policy="evaluation_safe",
    )

    result = await judge.evaluate(_context())

    assert result.status is ResultStatus.PASSED
    assert [tool["name"] for tool in provider.tools[0]] == ["lookup"]
    assert agent.conversation_history == original_history
    assert provider.evaluation_markers == [True]
    agent.close()


@pytest.mark.asyncio
async def test_agent_judge_resolves_registered_agent_profile(monkeypatch) -> None:
    provider = FakeJudgeProvider(
        [ModelResponse(content=_payload(), model="judge-model")]
    )
    monkeypatch.setattr(
        "praval.core.agent.ProviderFactory.create_provider",
        lambda *args, **kwargs: provider,
    )
    agent = Agent(
        "evaluator",
        provider="fake",
        model="judge-model",
        config={"temperature": 0, "retries": 0},
    )

    def lookup(query: str) -> str:
        return query

    agent.add_tool_spec(
        ToolSpec(
            name="lookup",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            metadata={"evaluation_safe": True, "read_only": True},
        ),
        lookup,
    )
    registry = PravalRegistry()
    registry.register_agent(agent)
    config = PravalConfig.model_validate(
        {
            "models": {
                "judge-model-profile": {
                    "provider": "fake",
                    "model": "judge-model",
                    "temperature": 0,
                }
            },
            "agents": {
                "evaluator": {
                    "model": "judge-model-profile",
                    "tools": ["lookup"],
                    "max_tool_rounds": 3,
                }
            },
            "eval": {
                "judges": {
                    "quality": {
                        "agent": "evaluator",
                        "allowed_tools": ["lookup"],
                        "max_attempts": 1,
                    }
                }
            },
        }
    )
    judge = AgentJudge.from_config(
        "quality",
        config,
        rubric="Use lookup only when needed.",
        rubric_version="1",
        registry=registry,
    )

    result = await judge.evaluate(_context())

    assert result.status is ResultStatus.PASSED
    assert judge.allowed_tools == ("lookup",)
    assert judge.max_tool_rounds == 3
    agent.close()


def test_agent_judge_config_resolution_rejects_missing_agent_profiles() -> None:
    model_config = PravalConfig.model_validate(
        {
            "models": {
                "judge-model-profile": {
                    "provider": "fake",
                    "model": "judge-model",
                }
            },
            "eval": {"judges": {"quality": {"model": "judge-model-profile"}}},
        }
    )
    registry = PravalRegistry()
    with pytest.raises(JudgeConfigurationError, match="unknown judge profile"):
        AgentJudge.from_config(
            "missing",
            model_config,
            rubric="Be correct.",
            rubric_version="1",
            registry=registry,
        )
    with pytest.raises(JudgeConfigurationError, match="does not reference an agent"):
        AgentJudge.from_config(
            "quality",
            model_config,
            rubric="Be correct.",
            rubric_version="1",
            registry=registry,
        )

    agent_config = PravalConfig.model_validate(
        {
            "models": {
                "judge-model-profile": {
                    "provider": "fake",
                    "model": "judge-model",
                }
            },
            "agents": {"evaluator": {"model": "judge-model-profile"}},
            "eval": {"judges": {"quality": {"agent": "evaluator"}}},
        }
    )
    with pytest.raises(JudgeConfigurationError, match="not registered"):
        AgentJudge.from_config(
            "quality",
            agent_config,
            rubric="Be correct.",
            rubric_version="1",
            registry=registry,
        )


def test_agent_judge_rejects_unknown_or_unsafe_capabilities(monkeypatch) -> None:
    provider = FakeJudgeProvider([ModelResponse(content=_payload())])
    monkeypatch.setattr(
        "praval.core.agent.ProviderFactory.create_provider",
        lambda *args, **kwargs: provider,
    )
    agent = Agent("evaluator", provider="fake", model="judge-model")

    def mutate(value: str) -> str:
        return value

    agent.add_tool_spec(
        ToolSpec(
            name="mutate",
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
            metadata={"evaluation_safe": False, "read_only": False},
        ),
        mutate,
    )
    common = {
        "name": "quality",
        "agent": agent,
        "judge_version": "1",
        "rubric": "Be correct.",
        "rubric_version": "1",
    }

    with pytest.raises(JudgeConfigurationError, match="unknown tools"):
        AgentJudge(**common, allowed_tools=("missing",))
    with pytest.raises(JudgeConfigurationError, match="not evaluation-safe"):
        AgentJudge(**common, allowed_tools=("mutate",))
    agent.close()


def test_agent_judge_rejects_invalid_policy_bounds_and_persistent_history() -> None:
    agent = SimpleNamespace(
        name="evaluator",
        tools={},
        persist_state=False,
        config=SimpleNamespace(model="judge-model"),
        conversation_history=[],
    )
    common = {
        "name": "quality",
        "agent": agent,
        "judge_version": "1",
        "rubric": "Be correct.",
        "rubric_version": "1",
    }
    with pytest.raises(JudgeConfigurationError, match="tool policy"):
        AgentJudge(**common, tool_policy="unsafe")
    with pytest.raises(JudgeConfigurationError, match="max_tool_rounds"):
        AgentJudge(**common, max_tool_rounds=0)
    agent.persist_state = True
    with pytest.raises(JudgeConfigurationError, match="persist"):
        AgentJudge(**common)


def test_agent_judge_accepts_read_only_tool_policy() -> None:
    agent = SimpleNamespace(
        name="evaluator",
        tools={"lookup": {"metadata": {"read_only": True}}},
        persist_state=False,
        config=SimpleNamespace(model="judge-model"),
        conversation_history=[],
    )

    judge = AgentJudge(
        name="quality",
        agent=agent,
        judge_version="1",
        rubric="Be correct.",
        rubric_version="1",
        allowed_tools=("lookup",),
        tool_policy="read_only",
    )

    assert judge.allowed_tools == ("lookup",)


@pytest.mark.asyncio
async def test_agent_judge_rejects_non_model_response() -> None:
    class InvalidAgent:
        name = "evaluator"
        tools: dict[str, Any] = {}
        persist_state = False
        config = SimpleNamespace(model="judge-model")
        conversation_history: list[dict[str, Any]] = []

        async def agenerate(self, message: Any, **kwargs: Any) -> str:
            return "not a model response"

    judge = AgentJudge(
        name="quality",
        agent=InvalidAgent(),
        judge_version="1",
        rubric="Be correct.",
        rubric_version="1",
        max_attempts=1,
    )

    result = await judge.evaluate(_context())

    assert result.status is ResultStatus.ERROR
    assert result.error_type == "JudgeResponseError"
