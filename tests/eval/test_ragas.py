"""Optional RAGAS 0.4 adapter tests through Praval runtime bridges."""

# flake8: noqa: E402

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

if sys.gettrace() is not None:
    pytest.skip(
        "RAGAS datasets/PyArrow registration is incompatible with traced import",
        allow_module_level=True,
    )
pytest.importorskip("ragas")

from praval.config import PravalConfig
from praval.eval import (
    EvalCase,
    EvaluationSubject,
    JudgeContext,
    LoadedEvalCase,
    ResultStatus,
    TargetResult,
)
from praval.eval.context import is_evaluation_call
from praval.eval.ragas import (
    RAGAS_METRIC_NAMES,
    PravalRagasEmbeddings,
    PravalRagasLLM,
    RagasConfigurationError,
    RagasMetricAdapter,
    RagasResponseError,
    create_ragas_metrics,
)
from praval.models import (
    ContentKind,
    ContentReference,
    ExecutionObservation,
    ModelResponse,
    ObservationFactStatus,
    ObservationKind,
    ObservationStatus,
    ToolCallObservation,
)

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def _reference(kind: ContentKind) -> ContentReference:
    return ContentReference(kind=kind, sha256="b" * 64, size_bytes=1)


def _context(
    *,
    expected="Paris",
    contexts=("Paris is in France",),
    expected_tools=("lookup",),
    observed_tools=("lookup",),
    tags=("geography",),
) -> JudgeContext:
    case = LoadedEvalCase(
        case=EvalCase(
            case_id="case-1",
            name="Case",
            input=_reference(ContentKind.PROMPT),
            expected_output=(
                _reference(ContentKind.RESPONSE) if expected is not None else None
            ),
            reference_contexts=tuple(_reference(ContentKind.CONTEXT) for _ in contexts),
            expected_tool_calls=expected_tools,
            tags=tags,
        ),
        input="Where is Paris?",
        expected_output=expected,
        reference_contexts=contexts,
    )
    observation = ExecutionObservation(
        observation_id="observation-1",
        run_id="target-run-1",
        kind=ObservationKind.AGENT,
        agent_name="target",
        started_at=NOW,
        ended_at=NOW + timedelta(milliseconds=1),
        duration_ms=1,
        status=ObservationStatus.OK,
        tool_calls=tuple(
            ToolCallObservation(
                tool_call_id=f"tool-{index}",
                name=name,
                status=ObservationFactStatus.OK,
                duration_ms=1,
            )
            for index, name in enumerate(observed_tools)
        ),
    )
    subject = EvaluationSubject.from_observation(
        evaluation_run_id="evaluation-1",
        case_id="case-1",
        observation=observation,
    )
    return JudgeContext(
        evaluation_run_id="evaluation-1",
        case=case,
        subject=subject,
        target_result=TargetResult(observation=observation, output="Paris"),
    )


class BridgePayload(BaseModel):
    accepted: bool


class FakeModelRuntime:
    def __init__(self, content: str = '{"accepted":true}') -> None:
        self.content = content
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append((kwargs, is_evaluation_call()))
        return ModelResponse(content=self.content, model="fake")

    async def ainvoke(self, **kwargs):
        self.calls.append((kwargs, is_evaluation_call()))
        return ModelResponse(content=self.content, model="fake")


class FakeFaithfulnessRuntime(FakeModelRuntime):
    async def ainvoke(self, **kwargs):
        name = kwargs["response_schema"].name
        payloads = {
            "StatementGeneratorOutput": {"statements": ["Paris is in France."]},
            "NLIStatementOutput": {
                "statements": [
                    {
                        "statement": "Paris is in France.",
                        "reason": "supported",
                        "verdict": 1,
                    }
                ]
            },
        }
        self.calls.append((kwargs, is_evaluation_call()))
        return ModelResponse(content=json.dumps(payloads[name]), model="fake")


class FakeEmbeddingRuntime:
    def __init__(self) -> None:
        self.calls = []

    def embed_text(self, text: str):
        self.calls.append((text, is_evaluation_call()))
        return [1.0, 0.0] if "Paris" in text else [0.0, 1.0]


def _config(**ragas) -> PravalConfig:
    return PravalConfig.model_validate({"eval": {"ragas": ragas}})


@pytest.mark.asyncio
async def test_praval_model_bridge_is_structured_versioned_and_marked() -> None:
    runtime = FakeModelRuntime()
    bridge = PravalRagasLLM(runtime, timeout_seconds=3)

    sync_result = bridge.generate("prompt", BridgePayload)
    async_result = await bridge.agenerate("prompt", BridgePayload)

    assert sync_result.accepted is True and async_result.accepted is True
    assert len(runtime.calls) == 2
    for call, marked in runtime.calls:
        assert marked is True
        assert call["response_schema"].strict is True
        assert call["response_schema"].name == "BridgePayload"
        assert call["metadata"]["praval.evaluation.kind"] == "ragas"
        assert call["timeout"] == 3


@pytest.mark.asyncio
async def test_praval_model_bridge_rejects_invalid_output_without_raw_content() -> None:
    bridge = PravalRagasLLM(FakeModelRuntime("not json"))

    with pytest.raises(RagasResponseError, match="invalid structured"):
        await bridge.agenerate("prompt", BridgePayload)


@pytest.mark.asyncio
async def test_embedding_bridge_marks_sync_and_async_runtime_calls() -> None:
    runtime = FakeEmbeddingRuntime()
    bridge = PravalRagasEmbeddings(runtime)

    assert bridge.embed_text("Paris") == [1.0, 0.0]
    assert await bridge.aembed_text("France") == [0.0, 1.0]
    assert runtime.calls == [("Paris", True), ("France", True)]


@pytest.mark.asyncio
async def test_rule_and_embedding_ragas_metrics_execute_without_model_calls() -> None:
    embedding = FakeEmbeddingRuntime()
    metrics = create_ragas_metrics(
        (
            "ragas.semantic_similarity",
            "ragas.tool_call_accuracy",
            "ragas.tool_call_f1",
        ),
        _config(),
        embedding_runtime=embedding,
        clock=lambda: NOW,
    )

    results = [await metric.evaluate(_context()) for metric in metrics.values()]

    assert [result.status for result in results] == [ResultStatus.PASSED] * 3
    assert [result.score for result in results] == [1.0, 1.0, 1.0]
    assert all(result.metric_version.startswith("ragas-0.4.") for result in results)


@pytest.mark.asyncio
async def test_required_fields_fail_before_paid_ragas_model_call() -> None:
    runtime = FakeModelRuntime()
    metrics = create_ragas_metrics(
        ("ragas.faithfulness",),
        _config(),
        model_runtime=runtime,
        clock=lambda: NOW,
    )

    result = await metrics["ragas.faithfulness"].evaluate(_context(contexts=()))

    assert result.status is ResultStatus.ERROR
    assert result.error_type == "MetricInputMissing"
    assert runtime.calls == []


@pytest.mark.asyncio
async def test_actual_ragas_llm_metric_uses_praval_structured_runtime() -> None:
    runtime = FakeFaithfulnessRuntime()
    metrics = create_ragas_metrics(
        ("ragas.faithfulness",),
        _config(),
        model_runtime=runtime,
        clock=lambda: NOW,
    )

    result = await metrics["ragas.faithfulness"].evaluate(_context())

    assert result.status is ResultStatus.PASSED
    assert result.score == 1.0
    assert [call[0]["response_schema"].name for call in runtime.calls] == [
        "StatementGeneratorOutput",
        "NLIStatementOutput",
    ]
    assert all(marked for _, marked in runtime.calls)


@pytest.mark.asyncio
async def test_adapter_normalizes_invalid_scores_failures_and_timeouts() -> None:
    async def invalid(context):
        del context
        return SimpleNamespace(value=float("nan"))

    async def failed(context):
        del context
        raise RuntimeError("provider secret")

    async def slow(context):
        del context
        await asyncio.sleep(0.05)
        return SimpleNamespace(value=1.0)

    adapters = (
        RagasMetricAdapter(
            name="ragas.tool_call_f1",
            scorer=invalid,
            timeout_seconds=1,
            clock=lambda: NOW,
        ),
        RagasMetricAdapter(
            name="ragas.tool_call_f1",
            scorer=failed,
            timeout_seconds=1,
            clock=lambda: NOW,
        ),
        RagasMetricAdapter(
            name="ragas.tool_call_f1",
            scorer=slow,
            timeout_seconds=0.001,
            clock=lambda: NOW,
        ),
    )

    results = [await adapter.evaluate(_context()) for adapter in adapters]

    assert [result.error_type for result in results] == [
        "RagasMetricError",
        "RagasMetricError",
        "MetricTimeout",
    ]


def test_ragas_factory_requires_explicit_profiles_and_known_metric_names() -> None:
    with pytest.raises(RagasConfigurationError, match="eval.ragas"):
        create_ragas_metrics(
            ("ragas.faithfulness",), PravalConfig(), model_runtime=None
        )
    with pytest.raises(RagasConfigurationError, match="unsupported"):
        create_ragas_metrics(("ragas.unknown",), _config())
    with pytest.raises(RagasConfigurationError, match="model"):
        create_ragas_metrics(("ragas.faithfulness",), _config())
    with pytest.raises(RagasConfigurationError, match="embedding"):
        create_ragas_metrics(("ragas.semantic_similarity",), _config())
    assert len(RAGAS_METRIC_NAMES) == 10
