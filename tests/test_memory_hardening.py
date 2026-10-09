"""WP7 memory hardening: what a run, an agent and its caches keep alive.

The assertions use object liveness (weak references after ``gc.collect()``),
thread counts and sizes this module controls, not process RSS, so allocator
noise cannot make them flaky.
"""

from __future__ import annotations

import gc
import json
import sqlite3
import threading
import time
import tracemalloc
import weakref
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple
from unittest.mock import patch

import pytest
from provider_harnesses import (
    HARNESSES,
    AnthropicHarness,
    CohereHarness,
    GeminiHarness,
    Harness,
    OpenAIHarness,
    _runtime,
)

from praval import agent as agent_decorator
from praval import decorators, tool_execution
from praval.core.agent import Agent
from praval.core.exceptions import InterventionRequired, StateError
from praval.core.reef import get_reef
from praval.core.storage import StateStorage
from praval.core.tool_registry import (
    Tool,
    ToolMetadata,
    get_tool_registry,
    reset_tool_registry,
)
from praval.hitl.store import reset_hitl_stores
from praval.models import ContentPart, ModelResponse, ToolCall
from praval.runtime_observation import use_observation_recorder

OUTPUT_SIZE = 2_000


def _output(index: int, size: int = OUTPUT_SIZE) -> str:
    """Return a distinct tool output, so transcripts cannot share one string."""
    return (f"{index:06d}" * (size // 6 + 1))[:size]


def _big_tool() -> Dict[str, Any]:
    def big(n: int) -> str:
        return _output(n)

    return {
        "function": big,
        "description": "Return a large report",
        "parameters": {"n": {"type": "int", "required": True}},
    }


def _route_fake_client(harness: Harness, runtime: Any) -> None:
    """Serve scripted turns without the deep copy the WP1 harness records."""

    def respond(**params: Any) -> Any:
        return harness.responses.pop(0)

    provider = runtime.provider
    if isinstance(harness, GeminiHarness):
        provider._post_json = lambda method, payload, timeout=None: respond()
    elif isinstance(harness, CohereHarness):
        provider.client.chat.side_effect = respond
    elif isinstance(harness, AnthropicHarness):
        provider.client.messages.create.side_effect = respond
    else:
        provider.client.chat.completions.create.side_effect = respond


@pytest.fixture(autouse=True)
def _isolated_hitl_store(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    # Agent passes a HITL context on every call, which opens the default store.
    monkeypatch.setenv("PRAVAL_HITL_DB_PATH", str(tmp_path / "hitl.db"))
    reset_hitl_stores()
    yield
    reset_hitl_stores()


# ---------------------------------------------------------------------------
# WP1 transcripts
# ---------------------------------------------------------------------------


def _tool_run(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, rounds: int
) -> Tuple[ModelResponse, List[int], List[weakref.ReferenceType[Any]]]:
    """Run ``rounds`` dependent tool rounds and observe each continued response."""
    runtime = _runtime(harness, monkeypatch)
    harness.responses = [harness.tool_turn([("big", {"n": i})]) for i in range(rounds)]
    harness.responses.append(harness.final_turn("done"))
    _route_fake_client(harness, runtime)

    sizes: List[int] = []
    refs: List[weakref.ReferenceType[Any]] = []
    original = runtime.provider.continue_with_tool_results

    def observed(request: Any, response: ModelResponse, results: Any) -> Any:
        metadata = runtime._serialize_runtime_response(response)["metadata"]
        sizes.append(len(json.dumps(metadata)))
        refs.append(weakref.ref(response))
        return original(request, response, results)

    runtime.provider.continue_with_tool_results = observed
    response = runtime.invoke(
        messages=[{"role": "user", "content": "Summarise the reports."}],
        tools=[_big_tool()],
        max_tool_rounds=rounds + 1,
    )
    return response, sizes, refs


@pytest.fixture(params=HARNESSES, ids=lambda factory: factory.name)
def harness_factory(request: pytest.FixtureRequest) -> Callable[[], Harness]:
    return request.param


def test_tool_loop_releases_every_earlier_response(harness_factory, monkeypatch):
    """Only the current response holds a transcript; earlier ones are freed."""
    response, sizes, refs = _tool_run(harness_factory(), monkeypatch, 30)

    gc.collect()
    assert len(refs) == 30
    assert [ref for ref in refs if ref() is not None] == []
    assert response.content == "done"
    assert len(sizes) == 30


def test_transcript_held_by_a_response_grows_linearly(harness_factory, monkeypatch):
    """A tool-call response's transcript is O(rounds), not O(rounds squared)."""
    _, short_sizes, _ = _tool_run(harness_factory(), monkeypatch, 10)
    _, long_sizes, _ = _tool_run(harness_factory(), monkeypatch, 40)

    # The round-N transcript holds N outputs plus per-round framing.
    assert long_sizes[-1] >= 40 * OUTPUT_SIZE
    assert long_sizes[-1] <= 40 * (OUTPUT_SIZE + 1_000)
    assert long_sizes[-1] / short_sizes[-1] < 4.5


def test_run_retains_linear_memory_after_many_rounds(monkeypatch):
    """What a finished 40-round run keeps is about 4x a 10-round run."""

    def retained(rounds: int) -> int:
        gc.collect()
        tracemalloc.start()
        try:
            response, _, _ = _tool_run(OpenAIHarness(), monkeypatch, rounds)
            gc.collect()
            size = tracemalloc.get_traced_memory()[0]
        finally:
            tracemalloc.stop()
        assert response.content == "done"
        return size

    short, long = retained(10), retained(40)
    # Quadratic retention would be 16x; allow fixed overhead and noise.
    assert long < 6 * short
    assert long < 40 * OUTPUT_SIZE * 8


def _hitl_row_size(
    harness_factory: Callable[[], Harness],
    monkeypatch: pytest.MonkeyPatch,
    db_path: str,
    pause_round: int,
) -> int:
    """Pause on an approval tool after ``pause_round`` rounds; return the row size."""
    harness = harness_factory()
    provider = harness.build(monkeypatch)
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=provider
    ):
        hitl_agent = Agent(
            f"hitl-memory-{pause_round}",
            provider=harness.provider_name,
            model=harness.model,
            hitl_enabled=True,
            hitl_db_path=db_path,
            config={
                "provider_options": dict(harness.provider_options),
                "max_tool_rounds": pause_round + 2,
            },
        )

    def big(n: int) -> str:
        return _output(n)

    def publish(n: int) -> str:
        return "published"

    hitl_agent.tool(big)
    hitl_agent.tool(publish)
    hitl_agent.tools["publish"]["requires_approval"] = True
    harness.responses = [
        harness.tool_turn([("big", {"n": i})]) for i in range(pause_round)
    ]
    harness.responses.append(harness.tool_turn([("publish", {"n": 0})]))
    runtime = type("R", (), {"provider": provider})()
    _route_fake_client(harness, runtime)

    with pytest.raises(InterventionRequired) as raised:
        hitl_agent.chat("Summarise and publish.")
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT length(state_json) FROM suspended_runs WHERE run_id = ?",
            (raised.value.run_id,),
        ).fetchone()
    return int(row[0])


def test_hitl_row_is_linear_in_rounds(harness_factory, monkeypatch, tmp_path):
    """The suspended-run row holds the transcript once plus all results."""
    db_path = str(tmp_path / "rows.db")
    sizes = {
        rounds: _hitl_row_size(harness_factory, monkeypatch, db_path, rounds)
        for rounds in (10, 40)
    }

    assert sizes[40] >= 40 * OUTPUT_SIZE
    # Transcript plus all_results repeats each output twice: about 2x, not N x.
    assert sizes[40] <= 40 * OUTPUT_SIZE * 2.5
    assert sizes[40] / sizes[10] < 4.5


# ---------------------------------------------------------------------------
# Conversation history and persisted state
# ---------------------------------------------------------------------------


class _ScriptedProvider:
    """Provider fake: optional tool rounds, then a final answer."""

    def __init__(self, tool_rounds: int = 0, output_size: int = 0) -> None:
        self.tool_rounds = tool_rounds
        self.output_size = output_size
        self._served = 0

    def invoke(self, request: Any, tools: Any = None) -> ModelResponse:
        self._served = 0
        return self._next()

    def continue_with_tool_results(
        self, request: Any, response: ModelResponse, results: Any
    ) -> ModelResponse:
        return self._next()

    def _next(self) -> ModelResponse:
        if self._served < self.tool_rounds:
            self._served += 1
            return ModelResponse(
                tool_calls=[
                    ToolCall(
                        id=f"call-{self._served}",
                        name="report",
                        arguments={"size": self.output_size},
                    )
                ]
            )
        return ModelResponse(content="final answer")


def _agent(
    name: str = "memory-agent",
    provider: Optional[Any] = None,
    **kwargs: Any,
) -> Agent:
    with patch(
        "praval.core.agent.ProviderFactory.create_provider",
        return_value=provider or _ScriptedProvider(),
    ):
        return Agent(name, provider="openai", model="gpt-test", **kwargs)


def test_large_tool_outputs_do_not_enter_history(tmp_path):
    """A 1 MB tool output is sent to the model but never kept in history."""
    storage = StateStorage(str(tmp_path / "state"))
    with patch("praval.core.agent.StateStorage", return_value=storage):
        tool_agent = _agent(
            provider=_ScriptedProvider(tool_rounds=3, output_size=1_000_000),
            persist_state=True,
        )

    def report(size: int) -> str:
        return "r" * size

    tool_agent.tool(report)
    for index in range(3):
        assert tool_agent.chat(f"question {index}") == "final answer"

    history_bytes = len(json.dumps(tool_agent.conversation_history))
    assert len(tool_agent.conversation_history) == 6
    assert history_bytes < 1_000
    assert (tmp_path / "state" / "memory-agent.json").stat().st_size < 2_000


def test_default_max_history_bounds_history_and_persisted_state(tmp_path):
    storage = StateStorage(str(tmp_path / "state"))
    with patch("praval.core.agent.StateStorage", return_value=storage):
        bounded = _agent(system_message="Be brief.", persist_state=True)
    state_file = tmp_path / "state" / "memory-agent.json"

    sizes = []
    for index in range(300):
        bounded.chat(f"question {index:04d}")
        if index in (99, 299):
            sizes.append(state_file.stat().st_size)

    assert bounded.max_history == 100
    assert len(bounded.conversation_history) <= 101
    assert bounded.conversation_history[0]["role"] == "system"
    assert sizes[1] <= sizes[0] * 1.05


def test_persisted_restarts_do_not_duplicate_the_system_message(tmp_path):
    """Each restart used to append another copy that trimming never drops."""
    storage = StateStorage(str(tmp_path / "state"))
    lengths = []
    for restart in range(6):
        with patch("praval.core.agent.StateStorage", return_value=storage):
            restarted = _agent(system_message="Be brief.", persist_state=True)
        restarted.chat(f"question {restart}")
        lengths.append(len(restarted.conversation_history))
        system_turns = [
            m for m in restarted.conversation_history if m["role"] == "system"
        ]
        assert system_turns == [{"role": "system", "content": "Be brief."}]
        restarted.close()

    assert lengths == [3, 5, 7, 9, 11, 13]


def test_changed_system_message_replaces_the_persisted_one(tmp_path):
    storage = StateStorage(str(tmp_path / "state"))
    for system_message in ("Old instructions.", "New instructions."):
        with patch("praval.core.agent.StateStorage", return_value=storage):
            restarted = _agent(system_message=system_message, persist_state=True)
        restarted.chat("question")
        system_turns = [
            m for m in restarted.conversation_history if m["role"] == "system"
        ]
        history = list(restarted.conversation_history)
        restarted.close()

    assert system_turns == [{"role": "system", "content": "New instructions."}]
    assert history[0] == {"role": "system", "content": "New instructions."}
    assert [m["role"] for m in history] == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
    ]


def test_persisted_system_message_is_kept_when_none_is_configured(tmp_path):
    storage = StateStorage(str(tmp_path / "state"))
    with patch("praval.core.agent.StateStorage", return_value=storage):
        first = _agent(system_message="Persisted.", persist_state=True)
    first.chat("question")
    first.close()

    with patch("praval.core.agent.StateStorage", return_value=storage):
        restarted = _agent(persist_state=True)
    system_turns = [m for m in restarted.conversation_history if m["role"] == "system"]
    restarted.close()

    assert system_turns == [{"role": "system", "content": "Persisted."}]


class _VisionProvider:
    def invoke(self, request: Any, tools: Any = None) -> ModelResponse:
        return ModelResponse(content="a cat")


def _image_turn(index: int, size: int = 200_000) -> List[ContentPart]:
    return [
        ContentPart.text_part(f"describe image {index}"),
        ContentPart.image_base64(_output(index, size)),
    ]


def test_multimodal_history_is_bounded_by_max_history():
    """History counts messages, so it holds at most max_history images."""
    vision_agent = _agent(provider=_VisionProvider(), max_history=4)
    for index in range(20):
        assert vision_agent.generate(_image_turn(index)).content == "a cat"

    images = [
        part
        for message in vision_agent.conversation_history
        if isinstance(message["content"], list)
        for part in message["content"]
        if part.type == "image_base64"
    ]
    assert len(vision_agent.conversation_history) == 4
    assert [part.data for part in images] == [
        _output(index, 200_000) for index in (18, 19)
    ]


def test_persisted_multimodal_turns_save_and_reload(tmp_path):
    """ContentPart turns used to fail to serialise and empty the state file."""
    storage = StateStorage(str(tmp_path / "state"))
    with patch("praval.core.agent.StateStorage", return_value=storage):
        vision_agent = _agent(provider=_VisionProvider(), persist_state=True)
    vision_agent.chat("first question")
    assert vision_agent.generate(_image_turn(1)).content == "a cat"

    state_file = tmp_path / "state" / "memory-agent.json"
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert [message["role"] for message in saved] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert saved[2]["content"][1]["data"] == _output(1, 200_000)

    with patch("praval.core.agent.StateStorage", return_value=storage):
        reloaded = _agent(provider=_VisionProvider(), persist_state=True)
    assert len(reloaded.conversation_history) == 4
    assert reloaded.generate(_image_turn(2)).content == "a cat"


def test_failed_state_save_keeps_the_previous_state(tmp_path):
    storage = StateStorage(str(tmp_path / "state"))
    storage.save("keeper", [{"role": "user", "content": "kept"}])

    with pytest.raises(StateError):
        storage.save("keeper", [{"role": "user", "content": object()}])

    assert storage.load("keeper") == [{"role": "user", "content": "kept"}]


# ---------------------------------------------------------------------------
# Abandoned chat() workers
# ---------------------------------------------------------------------------


class _BlockingProvider:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.response_ref: Optional[weakref.ReferenceType[Any]] = None

    def invoke(self, request: Any, tools: Any = None) -> ModelResponse:
        self.started.set()
        self.release.wait(5)
        response = ModelResponse(content="late answer " + "x" * 100_000)
        self.response_ref = weakref.ref(response)
        return response


def _wait_for(condition: Callable[[], bool], timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def _new_threads(before: Set[threading.Thread]) -> List[threading.Thread]:
    """Threads started since ``before`` that are still running."""
    return [thread for thread in threading.enumerate() if thread not in before]


def test_abandoned_chat_worker_releases_everything_once_provider_returns():
    provider = _BlockingProvider()
    slow_agent = _agent(provider=provider)
    agent_ref = weakref.ref(slow_agent)
    before = set(threading.enumerate())
    decorators._agent_context.agent = slow_agent

    with pytest.raises(TimeoutError):
        decorators.chat("question", timeout=0.05)

    # Until the provider returns, the worker thread keeps the call alive.
    assert provider.started.is_set()
    assert len(_new_threads(before)) == 1

    provider.release.set()
    assert _wait_for(lambda: not _new_threads(before))
    gc.collect()
    assert provider.response_ref is not None
    assert provider.response_ref() is None
    assert [m["role"] for m in slow_agent.conversation_history] == ["user"]

    decorators._agent_context.agent = None
    del slow_agent
    gc.collect()
    assert agent_ref() is None


def test_many_chat_timeouts_leave_no_threads_behind():
    provider = _BlockingProvider()
    slow_agent = _agent(provider=provider)
    before = set(threading.enumerate())
    decorators._agent_context.agent = slow_agent

    for _ in range(20):
        with pytest.raises(TimeoutError):
            decorators.chat("question", timeout=0.01)
    assert len(_new_threads(before)) == 20
    provider.release.set()

    assert _wait_for(lambda: not _new_threads(before))
    decorators._agent_context.agent = None


# ---------------------------------------------------------------------------
# Validator caches
# ---------------------------------------------------------------------------


def test_signature_validator_cache_does_not_keep_agents_alive():
    """A tool closure capturing its agent is cached weakly and released."""
    baseline = len(tool_execution._FUNCTION_VALIDATORS)
    refs = []
    for index in range(20):
        tool_agent = _agent(
            f"validator-{index}",
            provider=_ScriptedProvider(tool_rounds=1, output_size=10),
        )

        def report(size: int, owner: Agent = tool_agent) -> str:
            return owner.name * size

        tool_agent.tool(report)
        assert tool_agent.chat("question") == "final answer"
        assert len(tool_execution._FUNCTION_VALIDATORS) > baseline
        refs.append(weakref.ref(tool_agent))
        del tool_agent, report
        # The global tool registry holds the first "report" strongly; that
        # retention is covered by its own test below.
        reset_tool_registry()

    gc.collect()
    assert [ref for ref in refs if ref() is not None] == []
    assert len(tool_execution._FUNCTION_VALIDATORS) == baseline


def test_closed_agent_is_not_kept_alive_by_the_global_tool_registry():
    def build_and_close() -> weakref.ReferenceType[Any]:
        tool_agent = _agent("registry-owner")

        def lookup(city: str) -> str:
            return f"{tool_agent.name}:{city}"

        tool_agent.tool(lookup)
        tool_agent.close()
        return weakref.ref(tool_agent)

    ref = build_and_close()
    gc.collect()

    assert ref() is None


def test_close_leaves_tools_registered_by_others_in_the_registry():
    reset_tool_registry()
    registry = get_tool_registry()

    def shared_lookup(city: str) -> str:
        return city

    registry.register_tool(
        Tool(
            shared_lookup,
            ToolMetadata(tool_name="shared_lookup", owned_by="owner", shared=True),
        )
    )
    first = _agent("owner")
    second = _agent("other")

    def own_lookup(city: str) -> str:
        return city

    def collide(city: str) -> str:
        return city

    collide.__name__ = "own_lookup"
    first.tool(shared_lookup)
    first.tool(own_lookup)
    second.tool(collide)
    assert registry.get_tool("own_lookup").func is own_lookup

    second.close()
    assert registry.get_tool("own_lookup").func is own_lookup
    first.close()

    assert registry.get_tool("own_lookup") is None
    assert registry.get_tool("shared_lookup").func is shared_lookup
    reset_tool_registry()


def test_registry_keeps_an_entry_that_is_not_the_given_function():
    reset_tool_registry()
    registry = get_tool_registry()

    def lookup(city: str) -> str:
        return city

    def other(city: str) -> str:
        return city

    registry.register_tool(Tool(lookup, ToolMetadata("lookup", owned_by="a")))
    assert not registry.unregister_owned_tool("lookup", other, "a")
    assert not registry.unregister_owned_tool("lookup", lookup, "b")
    assert not registry.unregister_owned_tool("missing", lookup, "a")
    assert registry.unregister_owned_tool("lookup", lookup, "a")
    assert registry.get_tool("lookup") is None
    assert registry.get_registry_stats()["agents_with_tools"] == 0
    reset_tool_registry()


def test_schema_validator_cache_is_bounded():
    for index in range(tool_execution.SCHEMA_CACHE_SIZE + 50):
        schema = {
            "type": "object",
            "properties": {f"field_{index}": {"type": "string"}},
        }
        assert tool_execution.cached_schema_validator(schema) is not None

    info = tool_execution._schema_validator_for_key.cache_info()
    assert info.currsize <= tool_execution.SCHEMA_CACHE_SIZE


# ---------------------------------------------------------------------------
# Agent and Reef lifecycle
# ---------------------------------------------------------------------------


def test_discarded_agents_are_collected_without_threads_or_registrations():
    """One Agent per planner call (PravalClaw) must not accumulate."""
    reef = get_reef()
    threads_before = set(threading.enumerate())
    baseline_channels = len(reef.channels)

    def cycle(index: int) -> weakref.ReferenceType[Any]:
        planner = _agent(
            f"planner-{index}",
            provider=_ScriptedProvider(tool_rounds=2, output_size=100),
            system_message="Plan.",
        )

        def report(size: int) -> str:
            return planner.name * size

        planner.tool(report)
        assert planner.chat("plan this") == "final answer"
        return weakref.ref(planner)

    for index in range(20):
        cycle(index)
    gc.collect()
    tracemalloc.start()
    try:
        before = tracemalloc.get_traced_memory()[0]
        refs = [cycle(index) for index in range(20, 220)]
        gc.collect()
        growth = tracemalloc.get_traced_memory()[0] - before
    finally:
        tracemalloc.stop()

    assert [ref for ref in refs if ref() is not None] == []
    assert _new_threads(threads_before) == []
    assert len(reef.channels) == baseline_channels
    # 200 agents of history, tools and runtime would be several MB if kept.
    assert growth < 256 * 1024


def test_closed_decorated_agent_leaves_the_reef_and_is_collected():
    """close() used to leave the main-channel subscription holding the agent."""
    reef = get_reef()
    with patch(
        "praval.core.agent.ProviderFactory.create_provider",
        return_value=_ScriptedProvider(),
    ):

        @agent_decorator("closing_agent")
        def closing_agent(spore: Any) -> None:
            return None

    underlying = closing_agent._praval_agent
    main = reef.get_channel(reef.default_channel)
    assert main is not None
    assert main.subscribers.get("closing_agent")

    underlying.close()

    assert not main.subscribers.get("closing_agent")
    ref = weakref.ref(underlying)
    del underlying, closing_agent
    gc.collect()
    assert ref() is None


def test_closed_decorated_agents_do_not_accumulate_channels():
    reef = get_reef()
    baseline = len(reef.channels)
    with patch(
        "praval.core.agent.ProviderFactory.create_provider",
        return_value=_ScriptedProvider(),
    ):
        for index in range(20):

            @agent_decorator(f"short_lived_{index}")
            def short_lived(spore: Any) -> None:
                return None

            short_lived._praval_agent.close()

    assert len(reef.channels) == baseline


def test_close_keeps_an_owned_channel_that_has_other_subscribers():
    reef = get_reef()
    with patch(
        "praval.core.agent.ProviderFactory.create_provider",
        return_value=_ScriptedProvider(),
    ):

        @agent_decorator("busy_owner")
        def busy_owner(spore: Any) -> None:
            return None

    def listener(spore: Any) -> None:
        return None

    reef.subscribe("listener", listener, channel="busy_owner_channel")
    try:
        busy_owner._praval_agent.close()
        channel = reef.get_channel("busy_owner_channel")
        assert channel is not None
        assert not channel.subscribers.get("busy_owner")
    finally:
        channel = reef.get_channel("busy_owner_channel")
        if channel is not None:
            channel.unsubscribe("listener")
        assert reef.remove_channel_if_unused("busy_owner_channel")
    assert reef.get_channel("busy_owner_channel") is None


def test_close_keeps_an_explicitly_named_channel():
    reef = get_reef()
    with patch(
        "praval.core.agent.ProviderFactory.create_provider",
        return_value=_ScriptedProvider(),
    ):

        @agent_decorator("named_channel_agent", channel="team_channel")
        def named_channel_agent(spore: Any) -> None:
            return None

    named_channel_agent._praval_agent.close()
    try:
        assert reef.get_channel("team_channel") is not None
    finally:
        assert reef.remove_channel_if_unused("team_channel")


def test_reef_never_removes_the_default_channel():
    reef = get_reef()
    reef.create_channel(reef.default_channel)
    assert not reef.remove_channel_if_unused(reef.default_channel)
    assert reef.get_channel(reef.default_channel) is not None
    assert not reef.remove_channel_if_unused("no_such_channel")


def test_concurrent_subscribe_and_remove_never_orphan_a_subscriber():
    reef = get_reef()

    def handler(spore: Any) -> None:
        return None

    for iteration in range(50):
        name = f"race_channel_{iteration}"
        created = reef.create_channel(name)
        barrier = threading.Barrier(2)

        def subscribe() -> None:
            barrier.wait(5)
            reef.subscribe("racer", handler, channel=name)

        def remove() -> None:
            barrier.wait(5)
            reef.remove_channel_if_unused(name)

        threads = [threading.Thread(target=subscribe), threading.Thread(target=remove)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
        channel = reef.get_channel(name)
        # Either the subscriber landed first and the channel stays, or the
        # channel was removed first and the subscription was a no-op.
        if channel is not None:
            assert channel.subscribers.get("racer")
            channel.unsubscribe("racer")
            assert reef.remove_channel_if_unused(name)
        else:
            assert not created.subscribers.get("racer")
        assert reef.get_channel(name) is None


# ---------------------------------------------------------------------------
# Observation buffers
# ---------------------------------------------------------------------------


class _Recorder:
    def __init__(self) -> None:
        self.observations: List[Any] = []

    def record(self, observation: Any) -> None:
        self.observations.append(observation)


def test_observation_tool_call_buffer_is_bounded_in_long_runs():
    tool_agent = _agent(provider=_ScriptedProvider(tool_rounds=300, output_size=10))

    def report(size: int) -> str:
        return "r" * size

    tool_agent.tool(report)
    recorder = _Recorder()
    with use_observation_recorder(recorder):
        assert tool_agent.generate("question", max_tool_rounds=301).content == (
            "final answer"
        )

    assert len(recorder.observations) == 1
    assert len(recorder.observations[0].tool_calls) == 128
