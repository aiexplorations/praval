"""Decorators, real agents, persistence and Reef exercised together offline."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import pytest
from _agent_system_support import ScriptedModel, answer_for, provider_patch
from _system_matrix_support import MODES, SHAPES, Storage, call_handler, make_worker

from praval.core.agent import Agent
from praval.core.exceptions import ProviderError
from praval.core.reef import Spore, SporeType, get_reef
from praval.core.tool_registry import get_tool_registry
from praval.decorators import _agent_context, achat, agent, chat
from praval.runtime_observation import has_active_observation


def message(question: str = "q", kind: str = "work") -> Spore:
    return Spore(
        id=f"spore-{question}",
        spore_type=SporeType.KNOWLEDGE,
        from_agent="sender",
        to_agent="worker",
        knowledge={"type": kind, "question": question},
        created_at=datetime.now(),
    )


def test_async_decorator_keeps_context_until_achat_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = ScriptedModel()
    with provider_patch(model, monkeypatch):

        @agent("worker", provider="openai", model="gpt-test", on_error="raise")
        async def worker(spore: Any) -> str:
            await asyncio.sleep(0)
            return await achat(spore.knowledge["question"])

    try:
        assert asyncio.run(worker._praval_agent.spore_handler(message())) == answer_for(
            "q"
        )
    finally:
        worker._praval_agent.close()


def test_raw_decorator_tool_registry_entry_is_released_on_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def echo(value: str) -> str:
        return value

    with provider_patch(ScriptedModel(), monkeypatch):

        @agent("worker", provider="openai", model="gpt-test", tools=[echo])
        def worker(spore: Any) -> None:
            pass

    assert get_tool_registry().get_tool("echo") is not None
    worker._praval_agent.close()
    assert get_tool_registry().get_tool("echo") is None


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("memory", [False, True], ids=["no-memory", "memory"])
@pytest.mark.parametrize("persistent", [False, True], ids=["transient", "persisted"])
def test_decorated_model_tool_memory_and_state_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    shape: str,
    memory: bool,
    persistent: bool,
) -> None:
    worker, model, log, store = make_worker(monkeypatch, mode, shape, memory=memory)
    current = worker._praval_agent
    storage = Storage()
    current.persist_state = persistent
    current._storage = storage if persistent else None
    results = [] if shape == "none" else ["E:q"]
    if shape == "dependent":
        results.append("L:E:q")
    try:
        result = call_handler(worker, message())
        assert result == {"type": "done", "answer": answer_for("q", results)}
        assert log == (
            []
            if shape == "none"
            else [("echo", "q")] + ([("label", "E:q")] if shape == "dependent" else [])
        )
        assert len(model.requests) == len(results) + 1
        assert current.conversation_history[-1]["content"] == result["answer"]
        if memory:
            assert len(store.turns) == 1
            assert store.turns[0]["agent_response"] == str(result)
            assert store.turns[0]["context"]["spore_id"] == "spore-q"
        else:
            assert store.turns == []
        assert (
            (storage.states["worker"] == current.conversation_history)
            if persistent
            else not storage.states
        )
        assert _agent_context.agent is None and not has_active_observation()
        channel = get_reef().get_channel("worker_channel")
        assert channel.wait_for_completion(timeout=5)
        assert [s.knowledge["type"] for s in channel.spores] == ["done"]
    finally:
        current.close()
    assert store.closed is memory
    assert get_tool_registry().get_tool("echo") is None


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("stage", ["before", "provider", "after"])
@pytest.mark.parametrize("policy", ["raise", "ignore", "callback"])
def test_handler_error_policy_and_context_cleanup(
    monkeypatch: pytest.MonkeyPatch, mode: str, stage: str, policy: str
) -> None:
    captured = []

    async def async_body(spore: Any) -> Any:
        if stage == "before":
            raise ValueError("before request")
        text = await achat("q") if mode == "async-achat" else chat("q")
        if stage == "after":
            raise LookupError("after request")
        return text

    def sync_body(spore: Any) -> Any:
        if stage == "before":
            raise ValueError("before request")
        text = chat("q")
        if stage == "after":
            raise LookupError("after request")
        return text

    worker, model, _, _ = make_worker(
        monkeypatch,
        mode,
        body=sync_body if mode == "sync-chat" else async_body,
        on_error=(
            (lambda error, spore: captured.append((type(error), spore.id)))
            if policy == "callback"
            else policy
        ),
    )
    if stage == "provider":
        model.on_request = lambda question: (_ for _ in ()).throw(
            ValueError("wire failed")
        )
    expected = (
        ValueError
        if stage == "before"
        else ProviderError if stage == "provider" else LookupError
    )
    try:
        if policy == "raise":
            with pytest.raises(expected):
                call_handler(worker, message())
        else:
            assert call_handler(worker, message()) is None
        assert len(model.requests) == (0 if stage == "before" else 1)
        assert captured == ([(expected, "spore-q")] if policy == "callback" else [])
        assert _agent_context.agent is None and not has_active_observation()
        with pytest.raises(RuntimeError, match="within @agent"):
            chat("outside")
    finally:
        worker._praval_agent.close()


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("stage", ["resolution", "storage"])
def test_memory_failures_remain_nonfatal_and_clean_context(
    monkeypatch: pytest.MonkeyPatch, mode: str, stage: str
) -> None:
    captured = []
    worker, _, _, memory = make_worker(
        monkeypatch,
        mode,
        memory=True,
        on_error=lambda error, spore: captured.append(type(error)),
    )
    spore = message()
    if stage == "resolution":
        spore.knowledge_references = ["memory://missing"]
        monkeypatch.setattr(
            worker._praval_agent,
            "resolve_spore_knowledge",
            lambda value: (_ for _ in ()).throw(KeyError("missing")),
        )
    else:
        monkeypatch.setattr(
            memory,
            "store_conversation_turn",
            lambda **kw: (_ for _ in ()).throw(OSError("storage down")),
        )
    try:
        assert call_handler(worker, spore)["answer"] == answer_for("q")
        assert captured == [KeyError if stage == "resolution" else OSError]
        assert _agent_context.agent is None and not has_active_observation()
    finally:
        worker._praval_agent.close()


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("delivery", ["broadcast", "request-reply"])
def test_concurrent_reef_delivery_keeps_questions_answers_and_tool_results_paired(
    monkeypatch: pytest.MonkeyPatch, mode: str, shape: str, delivery: str
) -> None:
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from _agent_system_support import question_answer_pairs
    from _system_matrix_support import plan, tools

    model = ScriptedModel(plan(shape))
    log = []
    reef = get_reef()
    barrier = threading.Barrier(4, timeout=5)
    model.on_request = lambda question: barrier.wait()

    def finish(spore: Any, text: str) -> Any:
        if delivery == "request-reply":
            reef.reply(
                "worker",
                spore.from_agent,
                {"answer": text},
                spore.id,
                channel="bus",
                correlation_id=spore.correlation_id,
                run_id=spore.run_id,
                trace_id=spore.trace_id,
                idempotency_key=spore.idempotency_key,
            )
        return {"type": "done", "answer": text}

    def sync(spore: Any) -> Any:
        return finish(spore, chat(spore.knowledge["question"]))

    async def asynchronous(spore: Any) -> Any:
        text = (
            await achat(spore.knowledge["question"])
            if mode == "async-achat"
            else chat(spore.knowledge["question"])
        )
        return finish(spore, text)

    with provider_patch(model, monkeypatch):
        worker = agent(
            "worker",
            provider="openai",
            model="gpt-test",
            channel="bus",
            responds_to=["work"],
            tools=tools(log) if shape != "none" else None,
            on_error="raise",
        )(sync if mode == "sync-chat" else asynchronous)
    questions = [f"q-{index}" for index in range(4)]
    try:
        if delivery == "broadcast":
            for question in questions:
                reef.broadcast(
                    "sender", {"type": "work", "question": question}, channel="bus"
                )
        else:
            with ThreadPoolExecutor(max_workers=4) as executor:
                replies = list(
                    executor.map(
                        lambda question: reef.request_and_wait(
                            "caller",
                            "worker",
                            {"type": "work", "question": question},
                            channel="bus",
                            timeout=8,
                        ),
                        questions,
                    )
                )
            assert [reply.knowledge["answer"] for reply in replies] == [
                answer_for(
                    question,
                    (
                        []
                        if shape == "none"
                        else [f"E:{question}"]
                        + ([f"L:E:{question}"] if shape == "dependent" else [])
                    ),
                )
                for question in questions
            ]
            assert reef._response_waiters == {}
        assert reef.get_channel("bus").wait_for_completion(timeout=8)
        pairs = question_answer_pairs(worker._praval_agent.conversation_history)
        assert len(pairs) == 4
        assert dict(pairs) == {
            question: answer_for(
                question,
                (
                    []
                    if shape == "none"
                    else [f"E:{question}"]
                    + ([f"L:E:{question}"] if shape == "dependent" else [])
                ),
            )
            for question in questions
        }
        assert len(model.requests) == 4 * (SHAPES.index(shape) + 1)
        assert sorted(log) == sorted(
            ([("echo", question) for question in questions] if shape != "none" else [])
            + (
                [("label", f"E:{question}") for question in questions]
                if shape == "dependent"
                else []
            )
        )
    finally:
        worker._praval_agent.close()


@pytest.mark.parametrize("ownership", ["raw", "decorated", "named"])
@pytest.mark.parametrize("restart", [False, True], ids=["close", "restart"])
def test_tool_registry_ownership_survives_decorator_close_and_restart(
    monkeypatch: pytest.MonkeyPatch, ownership: str, restart: bool
) -> None:
    from praval.tools import tool

    model = ScriptedModel(lambda question: [[("echo", {"value": question})]])
    calls = []

    def echo(value: str) -> str:
        calls.append(value)
        return value

    if ownership != "raw":
        echo = tool("echo", owned_by="external", shared=True)(echo)

    def create() -> Any:
        with provider_patch(model, monkeypatch):
            return agent(
                "worker",
                provider="openai",
                model="gpt-test",
                tools=["echo" if ownership == "named" else echo],
                on_error="raise",
            )(lambda spore: chat(spore.knowledge["question"]))

    worker = create()
    assert call_handler(worker, message()) == answer_for("q", ["q"])
    worker._praval_agent.close()
    assert (get_tool_registry().get_tool("echo") is None) == (ownership == "raw")
    if restart:
        second = create()
        assert call_handler(second, message("r")) == answer_for("r", ["r"])
        second._praval_agent.close()
    assert calls == (["q", "r"] if restart else ["q"])


@pytest.mark.parametrize("entry", ["chat", "agenerate"])
@pytest.mark.parametrize("shape", ["none", "dependent"])
def test_state_storage_restart_keeps_turns_and_uses_new_system_instruction(
    monkeypatch: pytest.MonkeyPatch, entry: str, shape: str
) -> None:
    from _system_matrix_support import plan, tools

    storage = Storage()
    monkeypatch.setattr("praval.core.agent.StateStorage", lambda: storage)
    model = ScriptedModel(plan(shape))

    def create(instruction: str) -> Agent:
        with provider_patch(model, monkeypatch):
            current = Agent(
                "persistent",
                provider="openai",
                model="gpt-test",
                persist_state=True,
                system_message=instruction,
            )
        for function in tools([]) if shape != "none" else []:
            current.tool(function)
        return current

    def run(current: Agent, question: str) -> str:
        return (
            current.chat(question)
            if entry == "chat"
            else asyncio.run(current.agenerate(question)).content
        )

    first = create("Old instruction")
    answer = run(first, "q")
    first.close()
    second = create("New instruction")
    try:
        assert second.conversation_history == [
            {"role": "system", "content": "New instruction"},
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": answer},
        ]
        next_answer = run(second, "r")
        assert storage.states["persistent"][-1]["content"] == next_answer
        assert [
            item["content"]
            for item in model.requests[-1]["messages"]
            if item["role"] == "system"
        ] == ["New instruction"]
    finally:
        second.close()


@pytest.mark.parametrize("raises", [False, True], ids=["normal", "exception"])
def test_app_closes_real_agent_tools_channels_and_reef_on_exit(
    monkeypatch: pytest.MonkeyPatch, raises: bool
) -> None:
    from praval.app import PravalApp

    model = ScriptedModel()
    app = PravalApp(use_global_reef=True)

    def execute() -> None:
        with app, provider_patch(model, monkeypatch):
            current = app.create_agent("owned", provider="openai", model="gpt-test")

            def echo(value: str) -> str:
                return value

            current.tool(echo)
            current.subscribe_to_channel("owned_channel")
            assert current.chat("q") == answer_for("q")
            if raises:
                raise ValueError("application failure")

    if raises:
        with pytest.raises(ValueError, match="application failure"):
            execute()
    else:
        execute()
    assert app._closed and app._agents == {}
    assert get_tool_registry().list_all_tools() == []
    with pytest.raises(RuntimeError, match="closed"):
        app.create_agent("late")
