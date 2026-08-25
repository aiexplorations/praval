"""Optional RAGAS 0.4 adapter over provider-neutral Praval runtimes.

Import this module only when the ``eval-ragas`` extra is installed. Core
``praval.eval`` contracts never expose RAGAS, LangChain, or datasets types.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
from datetime import datetime, timezone
from importlib import metadata
from typing import Any, Awaitable, Callable, Mapping, cast

from pydantic import ValidationError
from ragas.embeddings.base import BaseRagasEmbedding
from ragas.llms.base import InstructorBaseRagasLLM
from ragas.messages import AIMessage, HumanMessage, ToolCall
from ragas.metrics.collections import (
    AgentGoalAccuracyWithoutReference,
    AgentGoalAccuracyWithReference,
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    FactualCorrectness,
    Faithfulness,
    SemanticSimilarity,
    ToolCallAccuracy,
    ToolCallF1,
    TopicAdherence,
)

from praval.config import PravalConfig
from praval.core.agent import AgentConfig
from praval.embeddings import EmbeddingRuntime
from praval.model_runtime import ModelRuntime
from praval.models import ModelResponse, StructuredOutputConfig
from praval.providers.factory import ProviderFactory

from .context import evaluation_call_scope
from .models import MetricResult, ResultStatus
from .runner import JudgeContext

RAGAS_METRIC_NAMES = (
    "ragas.agent_goal_accuracy",
    "ragas.context_precision",
    "ragas.context_recall",
    "ragas.factual_correctness",
    "ragas.faithfulness",
    "ragas.response_relevancy",
    "ragas.semantic_similarity",
    "ragas.tool_call_accuracy",
    "ragas.tool_call_f1",
    "ragas.topic_adherence",
)

_LLM_METRICS = {
    "ragas.agent_goal_accuracy",
    "ragas.context_precision",
    "ragas.context_recall",
    "ragas.factual_correctness",
    "ragas.faithfulness",
    "ragas.response_relevancy",
    "ragas.topic_adherence",
}
_EMBEDDING_METRICS = {
    "ragas.response_relevancy",
    "ragas.semantic_similarity",
}


class RagasConfigurationError(ValueError):
    """RAGAS configuration or its optional dependency is not usable."""


class RagasResponseError(ValueError):
    """A RAGAS model response did not satisfy its requested schema."""


class RagasMetricInputError(ValueError):
    """A case is missing data required by its selected RAGAS metric."""


def _json_text(value: Any, *, field: str) -> str:
    if isinstance(value, str):
        rendered = value
    else:
        try:
            rendered = json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise RagasMetricInputError(f"{field} must contain finite JSON") from exc
    if not rendered.strip():
        raise RagasMetricInputError(f"{field} is required")
    return rendered


class PravalRagasLLM(InstructorBaseRagasLLM):
    """Bridge RAGAS structured prompts through a configured ``ModelRuntime``."""

    def __init__(self, runtime: ModelRuntime, *, timeout_seconds: float = 60.0):
        if timeout_seconds <= 0:
            raise RagasConfigurationError("RAGAS model timeout must be positive")
        self.runtime = runtime
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _schema(response_model: Any) -> StructuredOutputConfig:
        return StructuredOutputConfig(
            schema=response_model.model_json_schema(),
            name=response_model.__name__,
            strict=True,
        )

    @staticmethod
    def _parse(response: ModelResponse, response_model: Any) -> Any:
        try:
            return response_model.model_validate_json(response.content)
        except (AttributeError, TypeError, ValueError, ValidationError) as exc:
            raise RagasResponseError("invalid structured RAGAS response") from exc

    def generate(self, prompt: str, response_model: Any) -> Any:
        with evaluation_call_scope():
            response = self.runtime.invoke(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Execute this versioned RAGAS evaluation prompt. "
                            "Return only the requested structured result."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_schema=self._schema(response_model),
                timeout=self.timeout_seconds,
                metadata={
                    "praval.evaluation": True,
                    "praval.evaluation.kind": "ragas",
                },
            )
        return self._parse(response, response_model)

    async def agenerate(self, prompt: str, response_model: Any) -> Any:
        with evaluation_call_scope():
            response = await self.runtime.ainvoke(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Execute this versioned RAGAS evaluation prompt. "
                            "Return only the requested structured result."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_schema=self._schema(response_model),
                timeout=self.timeout_seconds,
                metadata={
                    "praval.evaluation": True,
                    "praval.evaluation.kind": "ragas",
                },
            )
        return self._parse(response, response_model)


class PravalRagasEmbeddings(BaseRagasEmbedding):
    """Bridge RAGAS embeddings through a configured ``EmbeddingRuntime``."""

    def __init__(self, runtime: EmbeddingRuntime):
        self.runtime = runtime
        super().__init__()

    def embed_text(self, text: str, **kwargs: Any) -> list[float]:
        del kwargs
        with evaluation_call_scope():
            return self.runtime.embed_text(text)

    async def aembed_text(self, text: str, **kwargs: Any) -> list[float]:
        del kwargs
        with evaluation_call_scope():
            return await asyncio.to_thread(self.runtime.embed_text, text)


class RagasMetricAdapter:
    """Normalize one selected RAGAS score into a Praval ``MetricResult``."""

    def __init__(
        self,
        *,
        name: str,
        scorer: Callable[[JudgeContext], Awaitable[Any]],
        timeout_seconds: float,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if name not in RAGAS_METRIC_NAMES:
            raise RagasConfigurationError(f"unsupported RAGAS metric: {name}")
        if timeout_seconds <= 0:
            raise RagasConfigurationError("RAGAS metric timeout must be positive")
        self.name = name
        self.version = f"ragas-{metadata.version('ragas')}"
        self._scorer = scorer
        self.timeout_seconds = timeout_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _result(
        self,
        context: JudgeContext,
        *,
        status: ResultStatus,
        score: float | None = None,
        error_type: str | None = None,
    ) -> MetricResult:
        return MetricResult.create(
            evaluation_run_id=context.evaluation_run_id,
            case_id=context.case.case.case_id,
            subject_id=context.subject.subject_id,
            metric=self.name,
            metric_version=self.version,
            status=status,
            score=score,
            label="measured" if score is not None else None,
            error_type=error_type,
            created_at=self._clock(),
        )

    async def evaluate(self, context: JudgeContext) -> MetricResult:
        try:
            result = await asyncio.wait_for(
                self._scorer(context), timeout=self.timeout_seconds
            )
            score = float(result.value)
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise RagasResponseError("RAGAS score must be finite and in [0, 1]")
            return self._result(context, status=ResultStatus.PASSED, score=score)
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            return self._result(
                context,
                status=ResultStatus.ERROR,
                error_type="MetricTimeout",
            )
        except RagasMetricInputError:
            return self._result(
                context,
                status=ResultStatus.ERROR,
                error_type="MetricInputMissing",
            )
        except Exception:
            return self._result(
                context,
                status=ResultStatus.ERROR,
                error_type="RagasMetricError",
            )


def _single_turn(context: JudgeContext) -> tuple[str, str]:
    return (
        _json_text(context.case.input, field="input"),
        _json_text(context.target_result.output, field="response"),
    )


def _reference(context: JudgeContext) -> str:
    if context.case.expected_output is None:
        raise RagasMetricInputError("expected_output is required")
    return _json_text(context.case.expected_output, field="expected_output")


def _contexts(context: JudgeContext) -> list[str]:
    if not context.case.reference_contexts:
        raise RagasMetricInputError("reference_contexts are required")
    return [
        _json_text(value, field="reference_contexts")
        for value in context.case.reference_contexts
    ]


def _messages(context: JudgeContext) -> list[Any]:
    user_input, response = _single_turn(context)
    tool_calls = [
        ToolCall(name=fact.name, args={})
        for fact in context.subject.observation.tool_calls
    ]
    return [
        HumanMessage(content=user_input),
        AIMessage(content=response, tool_calls=tool_calls or None),
    ]


def _expected_tool_calls(context: JudgeContext) -> list[ToolCall]:
    if not context.case.case.expected_tool_calls:
        raise RagasMetricInputError("expected_tool_calls are required")
    return [
        ToolCall(name=name, args={}) for name in context.case.case.expected_tool_calls
    ]


def _model_runtime(
    config: PravalConfig,
    profile_name: str,
    provider_factory: Callable[[str, Any], Any],
) -> ModelRuntime:
    profile = config.models[profile_name]
    output_limit = profile.max_output_tokens or 2048
    runtime_config = AgentConfig(
        provider=profile.provider,
        model=profile.model,
        temperature=0.0,
        max_tokens=output_limit,
        max_output_tokens=output_limit,
        retries=0,
        provider_options={},
    )
    provider = provider_factory(profile.provider, runtime_config)
    return ModelRuntime(
        provider=provider,
        provider_name=profile.provider,
        config=runtime_config,
    )


def _embedding_runtime(config: PravalConfig, profile_name: str) -> EmbeddingRuntime:
    profile = config.embeddings[profile_name]
    options: dict[str, Any] = {}
    if profile.base_url is not None:
        options["base_url"] = profile.base_url
    if profile.api_key_env is not None:
        value = os.environ.get(profile.api_key_env)
        if not value:
            raise RagasConfigurationError(
                f"embedding credential environment is unset: {profile.api_key_env}"
            )
        options["api_key"] = value
    return EmbeddingRuntime(
        provider=profile.provider,
        model=profile.model,
        dimensions=profile.dimensions,
        provider_options=options,
    )


def create_ragas_metrics(
    names: tuple[str, ...],
    config: PravalConfig,
    *,
    provider_factory: Callable[[str, Any], Any] | None = None,
    model_runtime: ModelRuntime | None = None,
    embedding_runtime: EmbeddingRuntime | None = None,
    clock: Callable[[], datetime] | None = None,
) -> Mapping[str, RagasMetricAdapter]:
    """Create only requested RAGAS metrics from explicit Praval profiles."""
    requested = set(names)
    unknown = requested - set(RAGAS_METRIC_NAMES)
    if unknown:
        raise RagasConfigurationError(f"unsupported RAGAS metrics: {sorted(unknown)}")
    ragas_config = config.eval.ragas
    needs_llm = bool(requested & _LLM_METRICS)
    needs_embeddings = bool(requested & _EMBEDDING_METRICS)
    if ragas_config is None and (needs_llm or needs_embeddings):
        raise RagasConfigurationError("eval.ragas configuration is required")
    timeout = ragas_config.timeout_seconds if ragas_config is not None else 60.0
    if needs_llm and model_runtime is None:
        if ragas_config is None or ragas_config.model is None:
            raise RagasConfigurationError("eval.ragas.model is required")
        model_runtime = _model_runtime(
            config,
            ragas_config.model,
            provider_factory or ProviderFactory.create_provider,
        )
    if needs_embeddings and embedding_runtime is None:
        if ragas_config is None or ragas_config.embedding is None:
            raise RagasConfigurationError("eval.ragas.embedding is required")
        embedding_runtime = _embedding_runtime(config, ragas_config.embedding)

    llm = (
        PravalRagasLLM(model_runtime, timeout_seconds=timeout)
        if model_runtime is not None
        else None
    )
    embeddings = (
        PravalRagasEmbeddings(embedding_runtime)
        if embedding_runtime is not None
        else None
    )
    required_llm = cast(PravalRagasLLM, llm)
    required_embeddings = cast(PravalRagasEmbeddings, embeddings)
    strict_tool_order = (
        ragas_config.strict_tool_order if ragas_config is not None else True
    )

    scorers: dict[str, Callable[[JudgeContext], Awaitable[Any]]] = {}
    if "ragas.faithfulness" in requested:
        faithfulness_metric = Faithfulness(llm=required_llm)

        async def faithfulness(context: JudgeContext) -> Any:
            user_input, response = _single_turn(context)
            return await faithfulness_metric.ascore(
                user_input=user_input,
                response=response,
                retrieved_contexts=_contexts(context),
            )

        scorers["ragas.faithfulness"] = faithfulness
    if "ragas.response_relevancy" in requested:
        response_relevancy_metric = AnswerRelevancy(
            llm=required_llm, embeddings=required_embeddings
        )

        async def response_relevancy(context: JudgeContext) -> Any:
            user_input, response = _single_turn(context)
            return await response_relevancy_metric.ascore(
                user_input=user_input, response=response
            )

        scorers["ragas.response_relevancy"] = response_relevancy
    if "ragas.context_precision" in requested:
        context_precision_metric = ContextPrecision(llm=required_llm)

        async def context_precision(context: JudgeContext) -> Any:
            user_input, _ = _single_turn(context)
            return await context_precision_metric.ascore(
                user_input=user_input,
                reference=_reference(context),
                retrieved_contexts=_contexts(context),
            )

        scorers["ragas.context_precision"] = context_precision
    if "ragas.context_recall" in requested:
        context_recall_metric = ContextRecall(llm=required_llm)

        async def context_recall(context: JudgeContext) -> Any:
            user_input, _ = _single_turn(context)
            return await context_recall_metric.ascore(
                user_input=user_input,
                reference=_reference(context),
                retrieved_contexts=_contexts(context),
            )

        scorers["ragas.context_recall"] = context_recall
    if "ragas.factual_correctness" in requested:
        factual_correctness_metric = FactualCorrectness(llm=required_llm)

        async def factual_correctness(context: JudgeContext) -> Any:
            _, response = _single_turn(context)
            return await factual_correctness_metric.ascore(
                response=response,
                reference=_reference(context),
            )

        scorers["ragas.factual_correctness"] = factual_correctness
    if "ragas.semantic_similarity" in requested:
        semantic_similarity_metric = SemanticSimilarity(embeddings=required_embeddings)

        async def semantic_similarity(context: JudgeContext) -> Any:
            _, response = _single_turn(context)
            return await semantic_similarity_metric.ascore(
                response=response,
                reference=_reference(context),
            )

        scorers["ragas.semantic_similarity"] = semantic_similarity
    if "ragas.topic_adherence" in requested:
        topic_adherence_metric = TopicAdherence(llm=required_llm)

        async def topic_adherence(context: JudgeContext) -> Any:
            if not context.case.case.tags:
                raise RagasMetricInputError("tags are required as reference topics")
            return await topic_adherence_metric.ascore(
                user_input=_messages(context),
                reference_topics=list(context.case.case.tags),
            )

        scorers["ragas.topic_adherence"] = topic_adherence
    if "ragas.agent_goal_accuracy" in requested:
        with_reference = AgentGoalAccuracyWithReference(llm=required_llm)
        without_reference = AgentGoalAccuracyWithoutReference(llm=required_llm)

        async def agent_goal_accuracy(context: JudgeContext) -> Any:
            messages = _messages(context)
            if context.case.expected_output is None:
                return await without_reference.ascore(user_input=messages)
            return await with_reference.ascore(
                user_input=messages,
                reference=_reference(context),
            )

        scorers["ragas.agent_goal_accuracy"] = agent_goal_accuracy
    if "ragas.tool_call_accuracy" in requested:
        tool_call_accuracy_metric = ToolCallAccuracy(strict_order=strict_tool_order)

        async def tool_call_accuracy(context: JudgeContext) -> Any:
            return await tool_call_accuracy_metric.ascore(
                user_input=_messages(context),
                reference_tool_calls=_expected_tool_calls(context),
            )

        scorers["ragas.tool_call_accuracy"] = tool_call_accuracy
    if "ragas.tool_call_f1" in requested:
        tool_call_f1_metric = ToolCallF1()

        async def tool_call_f1(context: JudgeContext) -> Any:
            return await tool_call_f1_metric.ascore(
                user_input=_messages(context),
                reference_tool_calls=_expected_tool_calls(context),
            )

        scorers["ragas.tool_call_f1"] = tool_call_f1

    return {
        name: RagasMetricAdapter(
            name=name,
            scorer=scorers[name],
            timeout_seconds=timeout,
            clock=clock,
        )
        for name in names
    }


__all__ = [
    "PravalRagasEmbeddings",
    "PravalRagasLLM",
    "RAGAS_METRIC_NAMES",
    "RagasConfigurationError",
    "RagasMetricInputError",
    "RagasMetricAdapter",
    "RagasResponseError",
    "create_ragas_metrics",
]
