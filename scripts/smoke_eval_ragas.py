#!/usr/bin/env python3
"""Run RAGAS and metric-plugin checks against an installed Praval wheel."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from praval.config import PravalConfig
from praval.eval import (
    EvalCase,
    EvaluationSubject,
    JudgeContext,
    LoadedEvalCase,
    ResultStatus,
    TargetResult,
    discover_metric_plugins,
)
from praval.eval.ragas import create_ragas_metrics
from praval.models import (
    ContentKind,
    ContentReference,
    ExecutionObservation,
    ModelResponse,
    ObservationFactStatus,
    ObservationKind,
    ObservationStatus,
    ProviderCapabilities,
    ToolCallObservation,
)


class FakeRagasProvider:
    """Deterministic structured provider for the exact-wheel smoke."""

    provider_name = "fake"
    capabilities = ProviderCapabilities(structured_outputs=True)

    async def ainvoke(self, request, tools=None):
        del tools
        name = request.response_schema.name
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
        return ModelResponse(content=json.dumps(payloads[name]), model="fake-judge")


class FakeEmbeddingRuntime:
    """Deterministic configured embedding seam for the exact-wheel smoke."""

    def embed_text(self, text: str):
        del text
        return [1.0, 0.0]


def _reference(kind: ContentKind) -> ContentReference:
    return ContentReference(kind=kind, sha256="c" * 64, size_bytes=1)


def _context() -> JudgeContext:
    now = datetime.now(timezone.utc)
    case = LoadedEvalCase(
        case=EvalCase(
            case_id="wheel-case",
            name="Wheel case",
            input=_reference(ContentKind.PROMPT),
            expected_output=_reference(ContentKind.RESPONSE),
            reference_contexts=(_reference(ContentKind.CONTEXT),),
            expected_tool_calls=("lookup",),
        ),
        input="Where is Paris?",
        expected_output="Paris",
        reference_contexts=("Paris is in France.",),
    )
    observation = ExecutionObservation(
        observation_id="wheel-observation",
        run_id="wheel-target-run",
        kind=ObservationKind.AGENT,
        agent_name="wheel-target",
        started_at=now,
        ended_at=now + timedelta(milliseconds=1),
        duration_ms=1,
        status=ObservationStatus.OK,
        tool_calls=(
            ToolCallObservation(
                tool_call_id="wheel-tool",
                name="lookup",
                status=ObservationFactStatus.OK,
                duration_ms=1,
            ),
        ),
    )
    subject = EvaluationSubject.from_observation(
        evaluation_run_id="wheel-evaluation",
        case_id="wheel-case",
        observation=observation,
    )
    return JudgeContext(
        evaluation_run_id="wheel-evaluation",
        case=case,
        subject=subject,
        target_result=TargetResult(observation=observation, output="Paris"),
    )


async def main() -> None:
    plugins = discover_metric_plugins()
    assert "reference.word_overlap" in plugins
    config = PravalConfig.model_validate(
        {
            "models": {"ragas_judge": {"provider": "fake", "model": "fake-judge"}},
            "eval": {"ragas": {"model": "ragas_judge"}},
        }
    )
    metrics = create_ragas_metrics(
        (
            "ragas.faithfulness",
            "ragas.semantic_similarity",
            "ragas.tool_call_accuracy",
        ),
        config,
        provider_factory=lambda provider, runtime_config: FakeRagasProvider(),
        embedding_runtime=FakeEmbeddingRuntime(),
    )
    results = [await metric.evaluate(_context()) for metric in metrics.values()]
    assert [result.status for result in results] == [ResultStatus.PASSED] * 3
    assert [result.score for result in results] == [1.0, 1.0, 1.0]


if __name__ == "__main__":
    asyncio.run(main())
