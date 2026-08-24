"""Evaluation target adapters for ordinary registered Praval agents."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from praval.core.agent import Agent
from praval.models import ExecutionObservation, ModelResponse, ObservationKind
from praval.runtime_observation import use_observation_recorder

from .dataset import LoadedEvalCase
from .errors import EvaluationExecutionError
from .runner import TargetResult


@dataclass
class _CaptureRecorder:
    observations: list[ExecutionObservation] = field(default_factory=list)

    def record(self, observation: ExecutionObservation) -> None:
        self.observations.append(observation)


def _target_input(value: object) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise EvaluationExecutionError(
            "evaluation target input must contain finite JSON values"
        ) from exc


class AgentEvaluationTarget:
    """Run one ordinary agent per case and capture its single observation."""

    def __init__(self, agent: Agent, *, isolate_conversation: bool = True) -> None:
        if agent.persist_state:
            raise EvaluationExecutionError(
                "offline evaluation targets must not persist case conversation state"
            )
        self.agent = agent
        self.isolate_conversation = isolate_conversation
        self._lock = asyncio.Lock()

    async def evaluate(self, case: LoadedEvalCase) -> TargetResult:
        """Execute one case through the normal agent runtime."""
        message = _target_input(case.input)
        recorder = _CaptureRecorder()
        async with self._lock:
            original_history = list(self.agent.conversation_history)
            try:
                with use_observation_recorder(recorder):
                    response = await self.agent.agenerate(message)
            finally:
                if self.isolate_conversation:
                    self.agent.conversation_history[:] = original_history
        if not isinstance(response, ModelResponse):
            raise EvaluationExecutionError(
                "evaluation target agent returned an invalid response"
            )
        matching = [
            observation
            for observation in recorder.observations
            if observation.kind is ObservationKind.AGENT
            and observation.agent_name == self.agent.name
        ]
        if len(matching) != 1:
            raise EvaluationExecutionError(
                "evaluation target must produce exactly one agent observation"
            )
        return TargetResult(observation=matching[0], output=response.content)


__all__ = ["AgentEvaluationTarget"]
