"""WP7 concurrency hardening probes.

Each test tries to provoke one race named in the v0.8.4 plan (WP7,
"Concurrency"). Ordering is forced with barriers and events rather than
sleeps, and every wait is bounded by ``WAIT`` so a regression fails instead
of hanging. Tests marked ``xfail(strict=True)`` document defects that need a
design decision; they fail today by construction.
"""

from __future__ import annotations

import asyncio
import gc
import json
import logging
import random
import subprocess
import sys
import textwrap
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from typing import Any, Callable, Dict, Iterator, List
from unittest.mock import patch

import pytest

import praval.core.storage as storage_module
from praval import decorators, tool_execution
from praval.core.agent import Agent
from praval.core.exceptions import (
    InterventionRequired,
    PravalError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    StateError,
)
from praval.core.storage import StateStorage
from praval.decorators import _agent_context, achat, chat
from praval.hitl.models import InterventionDecision
from praval.hitl.service import HITLService
from praval.hitl.store import HITLStore, reset_hitl_stores
from praval.models import (
    ExecutionObservation,
    ModelEvent,
    ModelResponse,
    ProviderCapabilities,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from praval.runtime_observation import (
    has_active_observation,
    use_observation_recorder,
)

WAIT = 5.0


@pytest.fixture(autouse=True)
def _fresh_hitl_stores() -> Iterator[None]:
    reset_hitl_stores()
    yield
    reset_hitl_stores()


def _make_agent(provider: Any, name: str = "probe", **kwargs: Any) -> Agent:
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=provider
    ):
        return Agent(name, provider="fake", model="fake-model", **kwargs)


def _last_user_text(request: Any) -> str:
    for message in reversed(request.messages):
        role = message.get("role") if isinstance(message, dict) else message.role
        if role == "user":
            content = (
                message.get("content") if isinstance(message, dict) else message.content
            )
            return str(content)
    return ""


def _run_threads(targets: List[Callable[[], Any]]) -> List[Any]:
    """Run each target in its own thread; return results or raised exceptions."""
    results: List[Any] = [None] * len(targets)

    def runner(index: int, target: Callable[[], Any]) -> None:
        try:
            results[index] = target()
        except BaseException as exc:  # noqa: B902 - collected for assertions
            results[index] = exc

    threads = [
        threading.Thread(target=runner, args=(index, target), daemon=True)
        for index, target in enumerate(targets)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(WAIT)
        assert not thread.is_alive(), "worker thread did not finish"
    return results


# ---------------------------------------------------------------------------
# HITL: one approved tool, many resumers
# ---------------------------------------------------------------------------


class _GatedToolProvider:
    """Asks for one ``publish`` call, then answers with the tool result."""

    capabilities = ProviderCapabilities(tools=True)

    def __init__(self, fail_continuations: int = 0) -> None:
        self.fail_continuations = fail_continuations

    def invoke(self, request: Any) -> ModelResponse:
        return ModelResponse(
            tool_calls=[
                ToolCall(id="call-1", name="publish", arguments={"value": "release"})
            ]
        )

    def continue_with_tool_results(
        self, request: Any, response: Any, tool_results: List[ToolResult]
    ) -> ModelResponse:
        if self.fail_continuations > 0:
            self.fail_continuations -= 1
            raise ProviderInvalidRequestError("continuation rejected")
        return ModelResponse(content=f"Published {tool_results[0].content}")


def _gated_agent(
    db_path: str, executed: List[str], name: str = "publisher", **provider_kw: Any
) -> Agent:
    agent = _make_agent(
        _GatedToolProvider(**provider_kw),
        name=name,
        hitl_enabled=True,
        hitl_db_path=db_path,
    )

    @agent.tool
    def publish(value: str) -> str:
        executed.append(value)
        return value

    agent.tools["publish"]["requires_approval"] = True
    return agent


def _suspend_and_approve(agent: Agent) -> str:
    with pytest.raises(InterventionRequired) as raised:
        agent.chat("Publish the release")
    agent.approve_intervention(raised.value.intervention_id, reviewer="qa")
    return raised.value.run_id


def _barrier_after_read(service: HITLService, barrier: threading.Barrier) -> None:
    """Make every resumer read the run before any of them moves on."""
    original = service.get_suspended_run

    def read_then_wait(run_id: str) -> Any:
        suspended = original(run_id)
        barrier.wait(WAIT)
        return suspended

    service.get_suspended_run = read_then_wait  # type: ignore[method-assign]


def test_concurrent_resume_runs_approved_tool_once(tmp_path: Any) -> None:
    executed: List[str] = []
    agent = _gated_agent(str(tmp_path / "hitl.db"), executed)
    run_id = _suspend_and_approve(agent)
    _barrier_after_read(agent._get_hitl_service(), threading.Barrier(2))

    results = _run_threads(
        [lambda: agent.resume_run(run_id), lambda: agent.resume_run(run_id)]
    )

    assert executed == ["release"]
    assert sorted(type(result).__name__ for result in results) == ["ValueError", "str"]
    assert "Published release" in results
    answers = [m for m in agent.conversation_history if m["role"] == "assistant"]
    assert answers == [{"role": "assistant", "content": "Published release"}]
    suspended = HITLService(db_path=str(tmp_path / "hitl.db")).get_suspended_run(run_id)
    assert suspended is not None and suspended.status == "completed"


def test_resume_from_separate_stores_runs_tool_once(tmp_path: Any) -> None:
    """Two agents with their own store objects stand in for two processes."""
    db_path = str(tmp_path / "hitl.db")
    executed: List[str] = []
    first = _gated_agent(db_path, executed)
    run_id = _suspend_and_approve(first)
    second = _gated_agent(db_path, executed)
    barrier = threading.Barrier(2)
    for agent in (first, second):
        # Separate HITLStore objects do not share the in-process RLock, so
        # only SQLite can serialise the two resumers.
        agent._hitl_service = HITLService(store=HITLStore(db_path))
        _barrier_after_read(agent._hitl_service, barrier)

    results = _run_threads(
        [lambda: first.resume_run(run_id), lambda: second.resume_run(run_id)]
    )

    assert executed == ["release"]
    assert sorted(type(result).__name__ for result in results) == ["ValueError", "str"]


@pytest.mark.asyncio
async def test_concurrent_aresume_runs_async_tool_once(tmp_path: Any) -> None:
    executed: List[str] = []
    gate = asyncio.Event()
    agent = _make_agent(
        _GatedToolProvider(), hitl_enabled=True, hitl_db_path=str(tmp_path / "a.db")
    )

    async def publish(value: str) -> str:
        executed.append(value)
        await asyncio.wait_for(gate.wait(), WAIT)
        return value

    agent.add_tool_spec(
        ToolSpec(
            name="publish",
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
            requires_approval=True,
        ),
        publish,
        async_only=True,
    )
    with pytest.raises(InterventionRequired) as raised:
        await agent.agenerate("Publish the release")
    agent.approve_intervention(raised.value.intervention_id, reviewer="qa")
    run_id = raised.value.run_id

    # The first resumer is parked inside the tool when the second one starts.
    first = asyncio.create_task(agent.aresume_run(run_id))
    deadline = time.monotonic() + WAIT
    while not executed and time.monotonic() < deadline:
        await asyncio.sleep(0.001)
    assert executed == ["release"]
    second = asyncio.create_task(agent.aresume_run(run_id))
    await asyncio.wait({second}, timeout=WAIT)
    gate.set()
    results = await asyncio.wait_for(
        asyncio.gather(first, second, return_exceptions=True), WAIT
    )

    assert executed == ["release"]
    assert results[0] == "Published release"
    assert isinstance(results[1], ValueError)


def test_failed_resume_releases_run_for_retry(tmp_path: Any) -> None:
    """A resume interrupted before the tool returns leaves the run resumable."""
    executed: List[str] = []
    agent = _gated_agent(str(tmp_path / "hitl.db"), executed)
    run_id = _suspend_and_approve(agent)
    publish_tool = agent.tools["publish"]

    def publish(value: str) -> str:  # same name, so the resume resolves it
        raise KeyboardInterrupt()

    agent.tools["publish"] = {**publish_tool, "function": publish}

    with pytest.raises(KeyboardInterrupt):
        agent.resume_run(run_id)
    assert agent._get_hitl_service().get_suspended_run(run_id).status == "pending"

    agent.tools["publish"] = publish_tool
    assert agent.resume_run(run_id) == "Published release"
    assert executed == ["release"]


def test_resume_that_hits_a_second_gate_stays_resumable(tmp_path: Any) -> None:
    class TwoGateProvider(_GatedToolProvider):
        def invoke(self, request: Any) -> ModelResponse:
            return ModelResponse(
                tool_calls=[
                    ToolCall(id="call-1", name="publish", arguments={"value": "one"})
                ]
            )

        def continue_with_tool_results(
            self, request: Any, response: Any, tool_results: List[ToolResult]
        ) -> ModelResponse:
            if tool_results[-1].content == "one":
                return ModelResponse(
                    tool_calls=[
                        ToolCall(
                            id="call-2", name="publish", arguments={"value": "two"}
                        )
                    ]
                )
            return ModelResponse(content=f"Published {tool_results[-1].content}")

    executed: List[str] = []
    agent = _make_agent(
        TwoGateProvider(), hitl_enabled=True, hitl_db_path=str(tmp_path / "h.db")
    )

    @agent.tool
    def publish(value: str) -> str:
        executed.append(value)
        return value

    agent.tools["publish"]["requires_approval"] = True
    with pytest.raises(InterventionRequired) as first:
        agent.chat("Publish both")
    agent.approve_intervention(first.value.intervention_id, reviewer="qa")

    with pytest.raises(InterventionRequired) as second:
        agent.resume_run(first.value.run_id)

    service = agent._get_hitl_service()
    suspended = service.get_suspended_run(first.value.run_id)
    assert suspended.status == "pending"
    assert suspended.state["intervention_id"] == second.value.intervention_id
    agent.approve_intervention(second.value.intervention_id, reviewer="qa")
    assert agent.resume_run(first.value.run_id) == "Published two"
    assert executed == ["one", "two"]
    assert service.get_suspended_run(first.value.run_id).status == "completed"


def test_resume_retry_after_failed_continuation_runs_tool_once(
    tmp_path: Any,
) -> None:
    """The second resume reuses the stored tool result (at-most-once)."""
    executed: List[str] = []
    agent = _gated_agent(str(tmp_path / "hitl.db"), executed, fail_continuations=1)
    run_id = _suspend_and_approve(agent)

    with pytest.raises(PravalError):
        agent.resume_run(run_id)
    assert executed == ["release"]
    service = agent._get_hitl_service()
    suspended = service.get_suspended_run(run_id)
    assert suspended.status == "pending"
    stored = suspended.state["resume_results"]
    assert stored["intervention_id"] == suspended.state["intervention_id"]
    assert [r["content"] for r in stored["round_results"]] == ["release"]

    assert agent.resume_run(run_id) == "Published release"
    assert executed == ["release"]
    assert service.get_suspended_run(run_id).status == "completed"


@pytest.mark.asyncio
async def test_aresume_retry_after_failed_continuation_runs_tool_once(
    tmp_path: Any,
) -> None:
    executed: List[str] = []
    agent = _gated_agent(str(tmp_path / "hitl.db"), executed, fail_continuations=1)
    with pytest.raises(InterventionRequired) as raised:
        await agent.agenerate("Publish the release")
    agent.approve_intervention(raised.value.intervention_id, reviewer="qa")
    run_id = raised.value.run_id

    with pytest.raises(PravalError):
        await agent.aresume_run(run_id)
    assert executed == ["release"]
    assert await agent.aresume_run(run_id) == "Published release"
    assert executed == ["release"]


def test_resume_with_a_stale_decision_is_refused_and_released(
    tmp_path: Any,
) -> None:
    """A run that moved on to a newer intervention is not resumed with the old one."""
    executed: List[str] = []
    agent = _gated_agent(str(tmp_path / "hitl.db"), executed)
    run_id = _suspend_and_approve(agent)
    service = agent._get_hitl_service()
    stale = service.get_suspended_run(run_id)
    service.store.upsert_suspended_run(
        run_id=run_id,
        agent_name=stale.agent_name,
        provider_name=stale.provider_name,
        state={**stale.state, "intervention_id": "newer"},
    )
    service.get_suspended_run = lambda _run_id: stale  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="now waits on intervention 'newer'"):
        agent.resume_run(run_id)

    assert executed == []
    assert service.store.get_suspended_run(run_id).status == "pending"


class _GatedThenLoggedProvider(_GatedToolProvider):
    """Asks for a gated ``publish`` and an ungated ``log`` in one round."""

    def invoke(self, request: Any) -> ModelResponse:
        return ModelResponse(
            tool_calls=[
                ToolCall(id="call-1", name="publish", arguments={"value": "release"}),
                ToolCall(id="call-2", name="log", arguments={"value": "note"}),
            ]
        )

    def continue_with_tool_results(
        self, request: Any, response: Any, tool_results: List[ToolResult]
    ) -> ModelResponse:
        if self.fail_continuations > 0:
            self.fail_continuations -= 1
            raise ProviderInvalidRequestError("continuation rejected")
        return ModelResponse(
            content=" + ".join(result.content for result in tool_results)
        )


def test_resume_retry_reuses_later_calls_in_the_same_round(tmp_path: Any) -> None:
    executed: List[str] = []
    agent = _make_agent(
        _GatedThenLoggedProvider(fail_continuations=1),
        hitl_enabled=True,
        hitl_db_path=str(tmp_path / "hitl.db"),
    )

    @agent.tool
    def publish(value: str) -> str:
        executed.append(f"publish:{value}")
        return value

    @agent.tool
    def log(value: str) -> str:
        executed.append(f"log:{value}")
        return value

    agent.tools["publish"]["requires_approval"] = True
    run_id = _suspend_and_approve(agent)

    with pytest.raises(PravalError):
        agent.resume_run(run_id)
    assert agent.resume_run(run_id) == "release + note"
    assert executed == ["publish:release", "log:note"]


def test_stored_results_are_ignored_for_a_different_intervention(
    tmp_path: Any,
) -> None:
    """Results stored for one decision never stand in for another one."""
    executed: List[str] = []
    agent = _gated_agent(str(tmp_path / "hitl.db"), executed, fail_continuations=1)
    run_id = _suspend_and_approve(agent)
    with pytest.raises(PravalError):
        agent.resume_run(run_id)

    store = agent._get_hitl_service().store
    suspended = store.get_suspended_run(run_id)
    state = dict(suspended.state)
    state["resume_results"] = {**state["resume_results"], "intervention_id": "other"}
    store.upsert_suspended_run(
        run_id=run_id,
        agent_name=suspended.agent_name,
        provider_name=suspended.provider_name,
        state=state,
    )

    assert agent.resume_run(run_id) == "Published release"
    assert executed == ["release", "release"]


@pytest.mark.parametrize("separate_stores", [False, True])
def test_concurrent_decisions_apply_exactly_one(
    tmp_path: Any, separate_stores: bool
) -> None:
    db_path = str(tmp_path / "decide.db")
    shared = HITLStore(db_path)
    for iteration in range(20):
        intervention = shared.create_intervention(
            run_id=f"run-{iteration}",
            agent_name="a",
            provider_name="fake",
            tool_name="publish",
            tool_call_id="call",
            original_args={},
        )
        stores = (
            [HITLStore(db_path), HITLStore(db_path)]
            if separate_stores
            else [shared, shared]
        )
        barrier = threading.Barrier(2)
        decisions = [InterventionDecision.APPROVE, InterventionDecision.REJECT]
        random.Random(iteration).shuffle(decisions)

        def decide(store: HITLStore, decision: InterventionDecision) -> Any:
            barrier.wait(WAIT)
            return store.decide_intervention(
                intervention.id, decision=decision, reviewer=decision.value
            )

        results = _run_threads(
            [
                lambda s=stores[0], d=decisions[0]: decide(s, d),
                lambda s=stores[1], d=decisions[1]: decide(s, d),
            ]
        )
        winners = [r for r in results if not isinstance(r, BaseException)]
        losers = [r for r in results if isinstance(r, BaseException)]
        assert len(winners) == 1 and len(losers) == 1
        assert isinstance(losers[0], ValueError)
        stored = shared.get_intervention(intervention.id)
        assert stored is not None
        assert stored.decision == winners[0].decision
        assert stored.reviewer == winners[0].reviewer


# ---------------------------------------------------------------------------
# One Agent used from several threads
# ---------------------------------------------------------------------------


class _EchoProvider:
    def invoke(self, request: Any) -> ModelResponse:
        return ModelResponse(content=f"answer-{_last_user_text(request)}")


def test_parallel_calls_keep_every_turn_and_persisted_state(tmp_path: Any) -> None:
    agent = _make_agent(_EchoProvider(), max_history=None)
    agent.persist_state = True
    agent._storage = StateStorage(str(tmp_path / "state"))
    workers, calls = 8, 25
    barrier = threading.Barrier(workers)

    def worker(index: int) -> None:
        barrier.wait(WAIT)
        for call in range(calls):
            agent.chat(f"w{index}-{call}")

    _run_threads([lambda i=i: worker(i) for i in range(workers)])

    history = agent.conversation_history
    users = [m["content"] for m in history if m["role"] == "user"]
    answers = [m["content"] for m in history if m["role"] == "assistant"]
    assert len(users) == len(answers) == workers * calls
    assert sorted(answers) == sorted(f"answer-{text}" for text in users)
    saved = json.loads((tmp_path / "state" / "probe.json").read_text())
    assert saved == history


def test_overlapping_calls_keep_answers_next_to_their_questions() -> None:
    """Each answer is inserted directly after its own user turn."""
    entered = {"A": threading.Event(), "B": threading.Event()}
    release = {"A": threading.Event(), "B": threading.Event()}

    class Provider:
        def invoke(self, request: Any) -> ModelResponse:
            text = _last_user_text(request)
            entered[text].set()
            assert release[text].wait(WAIT)
            return ModelResponse(content=f"answer-{text}")

    agent = _make_agent(Provider(), max_history=None)
    first = threading.Thread(target=agent.chat, args=("A",), daemon=True)
    second = threading.Thread(target=agent.chat, args=("B",), daemon=True)
    first.start()
    assert entered["A"].wait(WAIT)
    second.start()
    assert entered["B"].wait(WAIT)
    release["B"].set()
    second.join(WAIT)
    release["A"].set()
    first.join(WAIT)

    history = agent.conversation_history
    for index, message in enumerate(history):
        if message["role"] == "assistant":
            question = history[index - 1]
            assert question["role"] == "user"
            assert message["content"] == f"answer-{question['content']}"


def test_answer_whose_user_turn_was_trimmed_away_is_dropped() -> None:
    """A late answer is not attached to another call's question."""
    entered = threading.Event()
    release = threading.Event()

    class Provider:
        def invoke(self, request: Any) -> ModelResponse:
            text = _last_user_text(request)
            if text == "A":
                entered.set()
                assert release.wait(WAIT)
            return ModelResponse(content=f"answer-{text}")

    agent = _make_agent(Provider(), max_history=2)
    first = threading.Thread(target=agent.chat, args=("A",), daemon=True)
    first.start()
    assert entered.wait(WAIT)
    agent.chat("B")
    agent.chat("C")
    release.set()
    first.join(WAIT)
    assert not first.is_alive()

    assert agent.conversation_history == [
        {"role": "user", "content": "C"},
        {"role": "assistant", "content": "answer-C"},
    ]


def test_unknown_keyword_warns_once_per_call_under_concurrency(
    caplog: pytest.LogCaptureFixture,
) -> None:
    agent = _make_agent(_EchoProvider())
    workers = 12
    barrier = threading.Barrier(workers)

    def call(index: int) -> str:
        barrier.wait(WAIT)
        return agent.chat(f"q{index}", bogus_option=index)

    with caplog.at_level(logging.WARNING, logger="praval.core.agent"):
        results = _run_threads([lambda i=i: call(i) for i in range(workers)])

    assert all(isinstance(result, str) for result in results)
    warned = [r for r in caplog.records if "bogus_option" in r.getMessage()]
    assert len(warned) == workers


def test_reader_never_sees_a_partial_state_file(tmp_path: Any) -> None:
    storage = StateStorage(str(tmp_path))
    old = [{"role": "user", "content": "old " * 2000}]
    new = [{"role": "user", "content": "new " * 4000}]
    storage.save("agent", old)
    half_written = threading.Event()
    finish = threading.Event()

    real_open = open

    class SlowHandle:
        """Write the first half, pause, then write the rest."""

        def __init__(self, handle: Any) -> None:
            self._handle = handle

        def __enter__(self) -> "SlowHandle":
            return self

        def __exit__(self, *exc: Any) -> None:
            self._handle.close()

        def write(self, text: str) -> None:
            self._handle.write(text[: len(text) // 2])
            self._handle.flush()
            half_written.set()
            assert finish.wait(WAIT)
            self._handle.write(text[len(text) // 2 :])

    def slow_open(path: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        handle = real_open(path, mode, *args, **kwargs)
        return SlowHandle(handle) if "r" not in mode else handle

    with patch.object(storage_module, "open", slow_open, create=True):
        writer = threading.Thread(target=storage.save, args=("agent", new))
        writer.start()
        try:
            assert half_written.wait(WAIT)
            during = storage.load("agent")
        finally:
            finish.set()
            writer.join(WAIT)

    assert during == old
    assert storage.load("agent") == new
    assert [p.name for p in tmp_path.iterdir()] == ["agent.json"]


def test_failed_state_write_keeps_previous_file(tmp_path: Any) -> None:
    storage = StateStorage(str(tmp_path))
    storage.save("agent", [{"role": "user", "content": "kept"}])

    with pytest.raises(StateError):
        storage.save("agent", [{"role": "user", "content": object()}])  # type: ignore

    assert storage.load("agent") == [{"role": "user", "content": "kept"}]
    assert [p.name for p in tmp_path.iterdir()] == ["agent.json"]


# ---------------------------------------------------------------------------
# Decorator chat()/achat() timeouts
# ---------------------------------------------------------------------------


def _bind_agent_context(agent: Agent) -> None:
    _agent_context.agent = agent


def _track_worker_calls(agent: Agent) -> Dict[str, Any]:
    """Record which thread ran each Agent.chat() and when it returned."""
    record: Dict[str, Any] = {"threads": [], "done": {}}
    original = Agent.chat

    def tracked(message: Any, **kwargs: Any) -> str:
        record["threads"].append(threading.current_thread())
        done = record["done"].setdefault(message, threading.Event())
        try:
            return original(agent, message, **kwargs)
        finally:
            done.set()

    agent.chat = tracked  # type: ignore[method-assign]
    return record


def test_chat_timeout_never_half_commits(tmp_path: Any) -> None:
    rng = random.Random(84)
    delays: Dict[str, float] = {}

    class Provider:
        def invoke(self, request: Any) -> ModelResponse:
            text = _last_user_text(request)
            threading.Event().wait(delays[text])
            return ModelResponse(content=f"answer-{text}")

    agent = _make_agent(Provider(), max_history=None)
    record = _track_worker_calls(agent)
    _bind_agent_context(agent)
    outcomes = {"returned": 0, "timed_out": 0}
    for index in range(40):
        message = f"m{index}"
        # Five calls that always finish, five that always time out, then
        # calls whose latency straddles the limit.
        if index < 5:
            delays[message], limit = 0.0, WAIT
        elif index < 10:
            delays[message], limit = 0.2, 0.01
        else:
            delays[message], limit = rng.uniform(0.0, 0.04), 0.02
        record["done"][message] = threading.Event()
        try:
            answer = chat(message, timeout=limit)
        except TimeoutError:
            answer = None
        assert record["done"][message].wait(WAIT)
        committed = [
            m
            for m in agent.conversation_history
            if m == {"role": "assistant", "content": f"answer-{message}"}
        ]
        if answer is None:
            outcomes["timed_out"] += 1
            assert committed == []
        else:
            outcomes["returned"] += 1
            assert answer == f"answer-{message}"
            assert len(committed) == 1
    assert outcomes["returned"] >= 5 and outcomes["timed_out"] >= 5


def test_chat_returns_answer_committed_while_the_limit_expires() -> None:
    import praval.decorators as decorators

    in_commit = threading.Event()
    cancel_called = threading.Event()

    class SpyToken(decorators._CallToken):
        def cancel(self) -> bool:
            cancel_called.set()
            return super().cancel()

    class BlockingStorage:
        def save(self, name: str, history: Any) -> None:
            in_commit.set()
            assert cancel_called.wait(WAIT)

    agent = _make_agent(_EchoProvider())
    agent.persist_state = True
    agent._storage = BlockingStorage()
    _bind_agent_context(agent)
    with patch.object(decorators, "_CallToken", SpyToken):
        answer = chat("late", timeout=1.0)

    assert in_commit.is_set() and cancel_called.is_set()
    assert answer == "answer-late"
    assert agent.conversation_history[-1] == {
        "role": "assistant",
        "content": "answer-late",
    }


def test_timed_out_chat_workers_exit_after_the_provider_returns() -> None:
    release = threading.Event()

    class Provider:
        def invoke(self, request: Any) -> ModelResponse:
            assert release.wait(WAIT)
            return ModelResponse(content="late")

    agent = _make_agent(Provider(), max_history=None)
    record = _track_worker_calls(agent)
    _bind_agent_context(agent)
    try:
        for index in range(20):
            started = time.monotonic()
            with pytest.raises(TimeoutError):
                chat(f"q{index}", timeout=0.01)
            assert time.monotonic() - started < 1.0
    finally:
        release.set()

    workers = record["threads"]
    assert len(set(workers)) == 20
    for worker in workers:
        worker.join(WAIT)
        assert not worker.is_alive()
    assert all(m["role"] != "assistant" for m in agent.conversation_history)


_PROBE_VAR: ContextVar[str] = ContextVar("probe_var", default="unset")


def test_context_vars_reach_chat_and_achat_workers() -> None:
    seen: List[str] = []

    class Provider:
        def invoke(self, request: Any) -> ModelResponse:
            seen.append(_PROBE_VAR.get())
            return ModelResponse(content="ok")

    agent = _make_agent(Provider())
    _bind_agent_context(agent)
    token = _PROBE_VAR.set("caller-value")
    try:
        assert chat("sync with limit", timeout=WAIT) == "ok"
        assert chat("sync without limit") == "ok"
        assert asyncio.run(achat("async", timeout=WAIT)) == "ok"
    finally:
        _PROBE_VAR.reset(token)
    assert seen == ["caller-value"] * 3


@pytest.mark.asyncio
async def test_hung_achat_calls_do_not_starve_later_calls() -> None:
    """achat() uses its own pool, not the loop's two-worker default executor."""
    release = threading.Event()

    class Provider:
        def invoke(self, request: Any) -> ModelResponse:
            if _last_user_text(request).startswith("hang"):
                release.wait(WAIT)
            return ModelResponse(content="ok")

    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=2)
    loop.set_default_executor(executor)
    agent = _make_agent(Provider(), max_history=None)
    _bind_agent_context(agent)
    try:
        for index in range(2):
            with pytest.raises(TimeoutError):
                await achat(f"hang-{index}", timeout=0.05)
        assert await achat("fast", timeout=0.5) == "ok"
    finally:
        release.set()


class _RefusingExecutor(ThreadPoolExecutor):
    def submit(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("achat() used the loop's default executor")


@pytest.mark.asyncio
async def test_achat_never_uses_the_loops_default_executor() -> None:
    class Provider:
        def invoke(self, request: Any) -> ModelResponse:
            return ModelResponse(content="ok")

    loop = asyncio.get_running_loop()
    loop.set_default_executor(_RefusingExecutor(max_workers=1))
    agent = _make_agent(Provider())
    _bind_agent_context(agent)
    assert await achat("q", timeout=WAIT) == "ok"
    assert await achat("q") == "ok"


def test_achat_pool_size_comes_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv(decorators.ACHAT_MAX_WORKERS_ENV, raising=False)
    assert decorators._achat_max_workers() == decorators.DEFAULT_ACHAT_MAX_WORKERS
    monkeypatch.setenv(decorators.ACHAT_MAX_WORKERS_ENV, "3")
    assert decorators._achat_max_workers() == 3
    for invalid in ("0", "-2", "many"):
        monkeypatch.setenv(decorators.ACHAT_MAX_WORKERS_ENV, invalid)
        with caplog.at_level(logging.WARNING, logger="praval.decorators"):
            assert (
                decorators._achat_max_workers() == decorators.DEFAULT_ACHAT_MAX_WORKERS
            )
        assert invalid in caplog.text


def test_achat_pool_is_bounded_and_reuses_idle_workers() -> None:
    executor = decorators._DaemonThreadExecutor(2, thread_name_prefix="probe-pool")
    release = threading.Event()
    try:
        held = [executor.submit(release.wait, WAIT) for _ in range(2)]
        queued = executor.submit(threading.current_thread)
        time.sleep(0.05)
        assert not queued.done()
        release.set()
        worker = queued.result(WAIT)
        assert all(future.result(WAIT) for future in held)
        assert worker.daemon and worker.name.startswith("probe-pool")
        names = {
            executor.submit(lambda: threading.current_thread().name).result(WAIT)
            for _ in range(10)
        }
        assert len(executor._threads) == 2
        assert names <= {t.name for t in executor._threads}
        failing = executor.submit(int, "not a number")
        with pytest.raises(ValueError):
            failing.result(WAIT)
    finally:
        release.set()
        executor.shutdown(wait=True)
    assert executor._threads == set()
    with pytest.raises(RuntimeError):
        executor.submit(int, "1")


def test_hung_achat_call_does_not_block_interpreter_exit(tmp_path: Any) -> None:
    script = tmp_path / "hung_achat.py"
    script.write_text(
        textwrap.dedent(
            """
            import asyncio
            import threading
            from unittest.mock import patch

            from praval.core.agent import Agent
            from praval.decorators import _agent_context, achat
            from praval.models import ModelResponse

            class Provider:
                def invoke(self, request):
                    threading.Event().wait(120)
                    return ModelResponse(content="late")

            with patch(
                "praval.core.agent.ProviderFactory.create_provider",
                return_value=Provider(),
            ):
                agent = Agent("exit-probe", provider="fake", model="fake-model")
            _agent_context.agent = agent

            async def main():
                try:
                    await achat("hang", timeout=0.05)
                except TimeoutError:
                    print("timed out", flush=True)

            asyncio.run(main())
            """
        )
    )
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "timed out" in result.stdout
    assert time.monotonic() - started < 30


# ---------------------------------------------------------------------------
# Retry backoff
# ---------------------------------------------------------------------------


class _FlakyProvider:
    """Fails with a rate limit ``failures`` times, then answers."""

    def __init__(self, failures: int, retry_after: float) -> None:
        self.failures = failures
        self.retry_after = retry_after
        self.calls = 0
        self.lock = threading.Lock()

    def invoke(self, request: Any) -> ModelResponse:
        with self.lock:
            self.calls += 1
            fail = self.calls <= self.failures
        if fail:
            raise ProviderRateLimitError(
                "slow down", retry_after_seconds=self.retry_after
            )
        return ModelResponse(content="ok")


async def _count_ticks_until(task: "asyncio.Future[Any]") -> int:
    ticks = 0
    while not task.done():
        await asyncio.sleep(0.01)
        ticks += 1
    return ticks


@pytest.mark.asyncio
async def test_async_retry_backoff_keeps_the_loop_running() -> None:
    provider = _FlakyProvider(failures=1, retry_after=0.2)
    agent = _make_agent(provider)

    def forbidden_sync_sleep(seconds: float) -> None:
        raise AssertionError("sync backoff used on the async path")

    with patch("praval.model_runtime._sleep", forbidden_sync_sleep):
        task = asyncio.ensure_future(agent.agenerate("hello"))
        ticks = await asyncio.wait_for(_count_ticks_until(task), WAIT)
        response = await task

    assert response.content == "ok"
    assert provider.calls == 2
    assert ticks >= 5


@pytest.mark.asyncio
async def test_achat_backoff_sleeps_off_the_event_loop() -> None:
    import praval.model_runtime as model_runtime

    provider = _FlakyProvider(failures=1, retry_after=0.2)
    agent = _make_agent(provider)
    _bind_agent_context(agent)
    loop_thread = threading.get_ident()
    sleeper_threads: List[int] = []
    real_sleep = model_runtime._sleep

    def recording_sleep(seconds: float) -> None:
        sleeper_threads.append(threading.get_ident())
        real_sleep(seconds)

    with patch.object(model_runtime, "_sleep", recording_sleep):
        task = asyncio.ensure_future(achat("hello", timeout=WAIT))
        ticks = await asyncio.wait_for(_count_ticks_until(task), WAIT)
        answer = await task

    assert answer == "ok"
    assert sleeper_threads and loop_thread not in sleeper_threads
    assert ticks >= 5


@pytest.mark.asyncio
async def test_cancelling_during_backoff_stops_promptly() -> None:
    import praval.model_runtime as model_runtime

    provider = _FlakyProvider(failures=100, retry_after=30.0)
    agent = _make_agent(provider)
    sleeping = asyncio.Event()
    real_async_sleep = model_runtime._async_sleep

    async def signalling_sleep(seconds: float) -> None:
        sleeping.set()
        await real_async_sleep(seconds)

    with patch.object(model_runtime, "_async_sleep", signalling_sleep):
        task = asyncio.ensure_future(agent.agenerate("hello"))
        await asyncio.wait_for(sleeping.wait(), WAIT)
        started = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, WAIT)

    assert time.monotonic() - started < 1.0
    assert provider.calls == 1
    assert agent.conversation_history[-1] == {"role": "user", "content": "hello"}


@pytest.mark.asyncio
async def test_async_retries_leave_no_unawaited_coroutines() -> None:
    class AsyncFlaky:
        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, request: Any) -> ModelResponse:
            raise AssertionError("sync path used")

        async def ainvoke(self, request: Any) -> ModelResponse:
            self.calls += 1
            if self.calls <= 2:
                raise ProviderRateLimitError("again", retry_after_seconds=0.0)
            return ModelResponse(content="ok")

    provider = AsyncFlaky()
    agent = _make_agent(provider)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        response = await agent.agenerate("hello")
        gc.collect()

    assert response.content == "ok"
    assert provider.calls == 3
    assert not [w for w in caught if "never awaited" in str(w.message)]


# ---------------------------------------------------------------------------
# Shared validator caches
# ---------------------------------------------------------------------------


def _make_tool(index: int) -> Callable[..., str]:
    def tool(x: int, label: str = "t") -> str:
        return f"{label}{x}{index}"

    return tool


def test_signature_validator_cache_under_concurrent_first_use_and_gc() -> None:
    gc.collect()
    baseline = len(tool_execution._FUNCTION_VALIDATORS)
    shared = _make_tool(-1)
    workers = 8
    barrier = threading.Barrier(workers + 1)
    stop = threading.Event()

    class Holder:
        def method(self, x: int) -> int:
            return x

    def worker(index: int) -> int:
        barrier.wait(WAIT)
        checked = 0
        for round_index in range(150):
            fresh = _make_tool(round_index)
            for func in (shared, fresh, Holder().method):
                args, error = tool_execution.validate_tool_arguments(
                    {"function": func, "name": "t"}, {"x": "3"}
                )
                assert error is None and args == {"x": 3}
                _, error = tool_execution.validate_tool_arguments(
                    {"function": func, "name": "t"}, {"x": "three"}
                )
                assert error is not None and error.is_error
                checked += 1
        return checked

    def collector() -> None:
        barrier.wait(WAIT)
        while not stop.is_set():
            gc.collect()
            # Yield between full collections: the probe stresses concurrent
            # cache access and collection, rather than starving workers under
            # coverage tracing. Keep the same worker completion deadline.
            stop.wait(0.01)

    collector_thread = threading.Thread(target=collector, daemon=True)
    collector_thread.start()
    try:
        results = _run_threads([lambda i=i: worker(i) for i in range(workers)])
    finally:
        stop.set()
        collector_thread.join(WAIT)

    assert results == [450] * workers
    gc.collect()
    # Only the still-referenced shared tool remains cached.
    assert len(tool_execution._FUNCTION_VALIDATORS) <= baseline + 1
    assert len(tool_execution._METHOD_VALIDATORS) <= 1


def test_schema_validator_cache_under_concurrent_first_use() -> None:
    workers = 8
    size = tool_execution.SCHEMA_CACHE_SIZE
    barrier = threading.Barrier(workers)

    def schema(index: int) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {f"p{index}": {"type": "integer"}},
            "required": [f"p{index}"],
        }

    def worker(offset: int) -> None:
        barrier.wait(WAIT)
        for index in range(size + 50):
            key = (index + offset) % (size + 50)
            validator = tool_execution.cached_schema_validator(schema(key))
            assert validator is not None
            assert validator.is_valid({f"p{key}": 1})
            assert not validator.is_valid({f"p{key}": "x"})

    results = _run_threads([lambda o=o: worker(o * 37) for o in range(workers)])

    assert results == [None] * workers
    info = tool_execution._schema_validator_for_key.cache_info()
    assert info.currsize <= size


# ---------------------------------------------------------------------------
# Streams abandoned from another thread or task
# ---------------------------------------------------------------------------


class _StreamingProvider:
    capabilities = ProviderCapabilities(streaming=True)

    def invoke(self, request: Any) -> ModelResponse:
        return ModelResponse(content="ab")

    def stream(self, request: Any, tools: Any = None) -> Iterator[ModelEvent]:
        yield ModelEvent(type="delta", delta="a")
        yield ModelEvent(type="delta", delta="b")
        yield ModelEvent(type="final", response=ModelResponse(content="ab"))


class _ObservationSink:
    def __init__(self) -> None:
        self.observations: List[ExecutionObservation] = []

    def record(self, observation: ExecutionObservation) -> None:
        self.observations.append(observation)


def test_stream_closed_from_another_thread_leaves_only_the_user_turn() -> None:
    agent = _make_agent(_StreamingProvider())
    sink = _ObservationSink()
    with use_observation_recorder(sink):
        events = agent.stream("first")
        assert next(events).type == "start"
        assert next(events).type == "delta"

        results = _run_threads([events.close])

        assert results == [None]
        assert agent.conversation_history == [{"role": "user", "content": "first"}]
        # The abandoned stream's scope no longer captures this thread's calls.
        assert not has_active_observation()
        assert agent.chat("second") == "ab"

    assert [o.request_mode for o in sink.observations] == ["stream", "chat"]
    assert sink.observations[0].run_id != sink.observations[1].run_id
    assert agent.conversation_history[-1] == {"role": "assistant", "content": "ab"}


def test_stream_finished_in_another_thread_commits_once() -> None:
    agent = _make_agent(_StreamingProvider())
    events = agent.stream("hello")
    assert next(events).type == "start"

    results = _run_threads([lambda: [event.type for event in events]])

    assert results == [["delta", "delta", "model_call", "final"]]
    assert agent.conversation_history == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "ab"},
    ]


@pytest.mark.asyncio
async def test_astream_abandoned_by_one_task_and_closed_by_another() -> None:
    hold = asyncio.Event()
    waiting = asyncio.Event()

    class AsyncStreamingProvider:
        capabilities = ProviderCapabilities(streaming=True)

        def invoke(self, request: Any) -> ModelResponse:
            return ModelResponse(content="ab")

        async def astream(
            self, request: Any, tools: Any = None
        ) -> Any:  # pragma: no cover - typed by the runtime
            yield ModelEvent(type="delta", delta="a")
            waiting.set()
            await asyncio.wait_for(hold.wait(), WAIT)
            yield ModelEvent(type="final", response=ModelResponse(content="ab"))

    agent = _make_agent(AsyncStreamingProvider())
    events = agent.astream("hello")

    async def consume_two() -> List[str]:
        return [(await events.__anext__()).type for _ in range(2)]

    assert await asyncio.create_task(consume_two()) == ["start", "delta"]
    await asyncio.wait_for(asyncio.create_task(events.aclose()), WAIT)
    assert agent.conversation_history == [{"role": "user", "content": "hello"}]

    # A consumer task cancelled while the provider is waiting commits nothing.
    async def consume_all() -> None:
        async for _ in agent.astream("again"):
            pass

    task = asyncio.create_task(consume_all())
    await asyncio.wait_for(waiting.wait(), WAIT)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, WAIT)
    assert all(m["role"] == "user" for m in agent.conversation_history)
