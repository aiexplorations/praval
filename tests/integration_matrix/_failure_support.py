"""Deterministic provider scripts for the composed failure matrix."""

import asyncio
from typing import Any, List, Optional
from unittest.mock import patch

from praval.core.agent import Agent
from praval.models import ModelEvent, ModelResponse, ProviderCapabilities, ToolCall


class Recorder:
    def __init__(self) -> None:
        self.observations: List[Any] = []

    def record(self, observation: Any) -> None:
        self.observations.append(observation)


class ScriptedProvider:
    """Capture real runtime requests; fail at one named request boundary."""

    capabilities = ProviderCapabilities(
        tools=True, streaming=True, native_streaming=True
    )

    def __init__(self, error: Exception, *, phase: str, failures: int = 1) -> None:
        self.error = error
        self.phase = phase
        self.failures = failures
        self.initial: List[Any] = []
        self.continuations: List[Any] = []
        self.streams: List[Any] = []
        self.second_round = False
        self.arguments: Any = {"value": 3}

    def _fail(self, phase: str) -> None:
        if self.phase == phase and self.failures:
            self.failures -= 1
            raise self.error

    def invoke(self, request: Any, tools: Any = None) -> ModelResponse:
        self.initial.append(request.model_dump())
        self._fail("initial")
        if request.tools:
            return ModelResponse(
                tool_calls=[
                    ToolCall(id="write-1", name="write", arguments=self.arguments)
                ]
            )
        return ModelResponse(content="done", finish_reason="stop")

    async def ainvoke(self, request: Any, tools: Any = None) -> ModelResponse:
        return self.invoke(request, tools)

    def continue_with_tool_results(
        self, request: Any, response: ModelResponse, results: Any
    ) -> ModelResponse:
        self.continuations.append(
            (
                request.model_dump(),
                response.model_dump(),
                [r.model_dump() for r in results],
            )
        )
        if results[0].tool_call_id == "write-1":
            self._fail("continue")
            if self.second_round:
                return ModelResponse(
                    tool_calls=[ToolCall(id="write-2", name="later", arguments={})]
                )
        else:
            self._fail("later")
        return ModelResponse(content="done", finish_reason="stop")

    def stream(self, request: Any, tools: Any = None) -> Any:
        self.streams.append(request.model_dump())
        if self.phase == "before":
            self._fail("before")
        yield ModelEvent(type="delta", delta="partial")
        self._fail("midstream")
        yield ModelEvent(type="final", response=ModelResponse(content="done"))

    async def astream(self, request: Any, tools: Any = None) -> Any:
        for event in self.stream(request, tools):
            yield event


def make_agent(provider: ScriptedProvider, *, retries: int, **kwargs: Any) -> Agent:
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=provider
    ):
        return Agent(
            "failure-matrix",
            provider="openai",
            model="gpt-4o-mini",
            config={"retries": retries},
            **kwargs,
        )


def run_agent(agent: Agent, mode: str, events: Optional[List[Any]] = None) -> Any:
    collected = events if events is not None else []
    if mode == "chat":
        return agent.chat("write once")
    if mode == "generate":
        return agent.generate("write once")
    if mode == "stream":
        for event in agent.stream("write once"):
            collected.append(event)
        return collected

    async def run() -> Any:
        if mode == "agenerate":
            return await agent.agenerate("write once")
        async for event in agent.astream("write once"):
            collected.append(event)
        return collected

    return asyncio.run(run())


def resume_agent(agent: Agent, run_id: str, use_async: bool) -> str:
    if use_async:
        return asyncio.run(agent.aresume_run(run_id))
    return agent.resume_run(run_id)
