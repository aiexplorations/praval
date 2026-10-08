"""Small dependency fakes shared by the component matrices."""

from __future__ import annotations

import asyncio
import copy
from typing import Any, Dict, List, Tuple

import pytest
from _agent_system_support import ScriptedModel, provider_patch

from praval.core.agent import Agent
from praval.decorators import achat, agent, chat
from praval.models import ExecutionObservation

MODES = ["sync-chat", "async-chat", "async-achat"]
SHAPES = ["none", "one", "dependent"]


class Memory:
    def __init__(self) -> None:
        self.turns: List[Dict[str, Any]] = []
        self.closed = False

    def store_conversation_turn(self, **values: Any) -> None:
        self.turns.append(values)

    def shutdown(self) -> None:
        self.closed = True


class Storage:
    def __init__(self) -> None:
        self.states: Dict[str, List[Dict[str, Any]]] = {}
        self.saves: List[Tuple[str, Any]] = []

    def save(self, name: str, history: List[Dict[str, Any]]) -> None:
        self.states[name] = copy.deepcopy(history)
        self.saves.append((name, copy.deepcopy(history)))

    def load(self, name: str) -> Any:
        return copy.deepcopy(self.states.get(name))


class Recorder:
    def __init__(self) -> None:
        self.observations: List[ExecutionObservation] = []

    def record(self, observation: ExecutionObservation) -> None:
        self.observations.append(observation)


def plan(shape: str) -> Any:
    def scripted(question: str) -> Any:
        if shape == "none":
            return []
        calls = [[("echo", {"value": question})]]
        if shape == "dependent":
            calls.append([("label", {"value": f"E:{question}"})])
        return calls

    return scripted


def tools(log: List[Tuple[str, str]]) -> List[Any]:
    def echo(value: str) -> str:
        log.append(("echo", value))
        return f"E:{value}"

    def label(value: str) -> str:
        log.append(("label", value))
        return f"L:{value}"

    return [echo, label]


def call_handler(worker: Any, spore: Any) -> Any:
    result = worker._praval_agent.spore_handler(spore)
    return asyncio.run(result) if asyncio.iscoroutine(result) else result


def make_worker(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    shape: str = "none",
    *,
    memory: bool = False,
    on_error: Any = "raise",
    channel: str = "worker_channel",
    body: Any = None,
) -> Tuple[Any, ScriptedModel, List[Tuple[str, str]], Memory]:
    model = ScriptedModel(plan(shape))
    log: List[Tuple[str, str]] = []
    memory_store = Memory()
    monkeypatch.setattr(
        Agent,
        "_init_memory_system",
        lambda self, config: setattr(self, "memory", memory_store),
    )

    def sync(spore: Any) -> Any:
        if body:
            return body(spore)
        return {"type": "done", "answer": chat(spore.knowledge["question"])}

    async def asynchronous(spore: Any) -> Any:
        await asyncio.sleep(0)
        if body:
            result = body(spore)
            return await result if asyncio.iscoroutine(result) else result
        question = spore.knowledge["question"]
        text = await achat(question) if mode == "async-achat" else chat(question)
        return {"type": "done", "answer": text}

    with provider_patch(model, monkeypatch):
        worker = agent(
            "worker",
            provider="openai",
            model="gpt-test",
            memory=memory,
            tools=tools(log) if shape != "none" else None,
            channel=channel,
            responds_to=["work"],
            on_error=on_error,
        )(sync if mode == "sync-chat" else asynchronous)
    return worker, model, log, memory_store
