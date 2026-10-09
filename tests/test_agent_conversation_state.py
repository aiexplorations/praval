"""Conversation history and per-call options across every Agent entry point."""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

from praval.core.agent import Agent, _CallToken
from praval.core.exceptions import PravalError, ProviderError
from praval.models import (
    ModelEvent,
    ModelRequest,
    ModelResponse,
    ProviderCapabilities,
)

SYSTEM = {"role": "system", "content": "Be brief."}


class FakeProvider:
    """Provider that answers from the last user message and records requests."""

    provider_name = "fake"
    capabilities = ProviderCapabilities(
        tools=True, streaming=True, native_streaming=True
    )

    def __init__(self, fail_stream: bool = False) -> None:
        self.requests: List[ModelRequest] = []
        self.fail_stream = fail_stream

    def _answer(self, request: ModelRequest) -> str:
        users = [m for m in request.messages if m.role == "user"]
        return f"answer:{users[-1].content}"

    def invoke(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(content=self._answer(request), model="fake-model")

    def stream(self, request: ModelRequest) -> Any:
        self.requests.append(request)
        answer = self._answer(request)
        half = len(answer) // 2
        yield ModelEvent(type="delta", delta=answer[:half])
        if self.fail_stream:
            raise RuntimeError("stream broke")
        yield ModelEvent(type="delta", delta=answer[half:])
        yield ModelEvent(
            type="final", response=ModelResponse(content=answer, model="fake-model")
        )

    async def astream(self, request: ModelRequest) -> Any:
        for event in self.stream(request):
            yield event


class RecordingStorage:
    """In-memory stand-in for StateStorage that records each save."""

    def __init__(self) -> None:
        self.saves: List[List[Dict[str, Any]]] = []

    def save(self, name: str, history: List[Dict[str, Any]]) -> None:
        self.saves.append([dict(message) for message in history])


def _agent(
    provider: Optional[FakeProvider] = None,
    *,
    system_message: Optional[str] = SYSTEM["content"],
    **kwargs: Any,
) -> Agent:
    with patch(
        "praval.core.agent.ProviderFactory.create_provider",
        return_value=provider or FakeProvider(),
    ):
        return Agent(
            "state-agent",
            provider="fake",
            model="fake-model",
            system_message=system_message,
            **kwargs,
        )


def _tool_unit(index: int) -> List[Dict[str, Any]]:
    """A user turn whose answer used one tool round."""
    call_id = f"call-{index}"
    return [
        {"role": "user", "content": f"question {index}"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": call_id, "name": "lookup", "arguments": {}}],
        },
        {"role": "tool", "tool_call_id": call_id, "content": f"result {index}"},
        {"role": "assistant", "content": f"answer {index}"},
    ]


def _assert_whole_units(history: List[Dict[str, Any]]) -> None:
    non_system = [m for m in history if m.get("role") != "system"]
    assert non_system, "the newest unit must always be kept"
    assert non_system[0]["role"] == "user"
    for position, message in enumerate(non_system):
        if message["role"] == "tool":
            earlier = non_system[:position]
            call_ids = {
                call["id"]
                for m in earlier
                if m["role"] == "assistant"
                for call in m.get("tool_calls", [])
            }
            assert message["tool_call_id"] in call_ids


@pytest.mark.parametrize("max_history", range(1, 11))
def test_system_message_survives_trimming_for_every_limit(max_history: int) -> None:
    agent = _agent(max_history=max_history)
    for turn in range(12):
        agent.chat(f"turn {turn}")

    history = agent.conversation_history
    assert history[0] == SYSTEM
    assert sum(1 for m in history if m["role"] == "system") == 1
    assert history[-2:] == [
        {"role": "user", "content": "turn 11"},
        {"role": "assistant", "content": "answer:turn 11"},
    ]
    non_system = [m for m in history if m["role"] != "system"]
    assert len(non_system) == max(2, max_history - max_history % 2)
    _assert_whole_units(history)
    # Every request carried the system message and its own user turn.
    for turn, request in enumerate(agent.provider.requests):
        assert request.messages[0].role == "system"
        assert request.messages[-1].content == f"turn {turn}"


@pytest.mark.parametrize("max_history", range(0, 14))
def test_trimming_never_leaves_orphan_tool_messages(max_history: int) -> None:
    agent = _agent(max_history=None)
    history: List[Dict[str, Any]] = [dict(SYSTEM)]
    for index in range(3):
        history.extend(_tool_unit(index))
    agent.conversation_history = history
    agent.max_history = max_history

    agent._trim_history()

    trimmed = agent.conversation_history
    assert trimmed[0] == SYSTEM
    _assert_whole_units(trimmed)
    non_system = [m for m in trimmed if m["role"] != "system"]
    kept_units = max(1, max_history // 4)
    assert len(non_system) == 4 * min(3, kept_units)
    assert non_system[-1] == {"role": "assistant", "content": "answer 2"}


def test_trimming_keeps_interleaved_system_messages_in_place() -> None:
    agent = _agent(system_message=None, max_history=2)
    agent.conversation_history = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "a1"},
        {"role": "system", "content": "mid"},
        {"role": "user", "content": "b"},
        {"role": "assistant", "content": "b1"},
    ]
    agent._trim_history()
    assert agent.conversation_history == [
        {"role": "system", "content": "mid"},
        {"role": "user", "content": "b"},
        {"role": "assistant", "content": "b1"},
    ]


def test_zero_limit_keeps_system_and_current_turn_only() -> None:
    agent = _agent(max_history=0)
    agent.chat("first")
    assert agent.conversation_history == [
        SYSTEM,
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "answer:first"},
    ]
    agent.chat("second")
    assert [m.content for m in agent.provider.requests[-1].messages] == [
        SYSTEM["content"],
        "second",
    ]


def _run_exchange(entry_point: str) -> Agent:
    agent = _agent()
    for prompt in ("one", "two"):
        if entry_point == "chat":
            assert agent.chat(prompt) == f"answer:{prompt}"
        elif entry_point == "generate":
            assert agent.generate(prompt).content == f"answer:{prompt}"
        elif entry_point == "agenerate":
            response = asyncio.run(agent.agenerate(prompt))
            assert response.content == f"answer:{prompt}"
        elif entry_point == "stream":
            events = list(agent.stream(prompt))
            assert events[-1].type == "final"
        else:

            async def consume(text: str) -> List[ModelEvent]:
                return [event async for event in agent.astream(text)]

            events = asyncio.run(consume(prompt))
            assert events[-1].type == "final"
    return agent


def test_every_entry_point_leaves_equal_history() -> None:
    expected = [
        SYSTEM,
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "answer:one"},
        {"role": "user", "content": "two"},
        {"role": "assistant", "content": "answer:two"},
    ]
    for entry_point in ("chat", "generate", "agenerate", "stream", "astream"):
        agent = _run_exchange(entry_point)
        assert agent.conversation_history == expected, entry_point
        # The second request carried the first exchange.
        second = agent.provider.requests[-1]
        assert [m.content for m in second.messages] == [
            m["content"] for m in expected[:-1]
        ], entry_point


def test_stream_commits_before_final_is_yielded_and_persists() -> None:
    agent = _agent()
    storage = RecordingStorage()
    agent.persist_state = True
    agent._storage = storage

    for event in agent.stream("hello"):
        if event.type == "final":
            break

    assert agent.conversation_history[-1] == {
        "role": "assistant",
        "content": "answer:hello",
    }
    assert storage.saves[-1] == agent.conversation_history


def test_abandoned_and_failed_streams_keep_only_the_user_turn() -> None:
    agent = _agent()
    events = agent.stream("abandon")
    assert next(events).type == "start"
    events.close()
    assert agent.conversation_history == [
        SYSTEM,
        {"role": "user", "content": "abandon"},
    ]

    failing = _agent(FakeProvider(fail_stream=True))
    # The runtime wraps unexpected stream failures as ProviderError.
    with pytest.raises(ProviderError, match="stream broke") as raised:
        list(failing.stream("fail"))
    assert isinstance(raised.value.__cause__, RuntimeError)
    assert failing.conversation_history == [
        SYSTEM,
        {"role": "user", "content": "fail"},
    ]

    async def consume_failing() -> None:
        async for _ in failing.astream("fail again"):
            pass

    with pytest.raises(ProviderError, match="stream broke"):
        asyncio.run(consume_failing())
    assert failing.conversation_history[-1] == {
        "role": "user",
        "content": "fail again",
    }


def _register_tools(agent: Agent) -> None:
    @agent.tool
    def alpha(value: str) -> str:
        """First tool."""
        return value

    @agent.tool
    def beta(value: str) -> str:
        """Second tool."""
        return value


@pytest.mark.parametrize("entry_point", ["chat", "generate", "stream", "astream"])
def test_sync_and_streaming_entry_points_apply_call_controls(
    entry_point: str,
) -> None:
    agent = _agent()
    _register_tools(agent)
    options = {
        "allowed_tool_names": ["beta"],
        "additional_system_message": "Use beta only.",
    }

    if entry_point == "chat":
        agent.chat("hi", **options)
    elif entry_point == "generate":
        agent.generate("hi", **options)
    elif entry_point == "stream":
        list(agent.stream("hi", **options))
    else:

        async def consume() -> None:
            async for _ in agent.astream("hi", **options):
                pass

        asyncio.run(consume())

    request = agent.provider.requests[-1]
    assert [tool.name for tool in request.tools] == ["beta"]
    assert request.messages[0].content == "Use beta only."
    assert request.messages[1].content == SYSTEM["content"]
    # The extra system message is request-only; it never enters history.
    assert all(m["content"] != "Use beta only." for m in agent.conversation_history)


def test_generate_without_allowed_tool_names_sends_every_tool() -> None:
    agent = _agent()
    _register_tools(agent)
    agent.generate("hi")
    assert [tool.name for tool in agent.provider.requests[-1].tools] == [
        "alpha",
        "beta",
    ]


def test_unknown_allowed_tool_fails_before_history_changes() -> None:
    agent = _agent()
    _register_tools(agent)
    for call in (
        lambda: agent.chat("hi", allowed_tool_names=["gamma"]),
        lambda: agent.generate("hi", allowed_tool_names=["gamma"]),
        lambda: agent.stream("hi", allowed_tool_names=["gamma"]),
        lambda: asyncio.run(agent.agenerate("hi", allowed_tool_names=["gamma"])),
    ):
        with pytest.raises(ValueError, match="Unknown allowed tools"):
            call()
    assert agent.conversation_history == [SYSTEM]
    assert agent.provider.requests == []


@pytest.mark.parametrize(
    "entry_point", ["chat", "generate", "agenerate", "stream", "astream"]
)
def test_unknown_keyword_warns_once_per_keyword_and_names_entry_point(
    entry_point: str, caplog: pytest.LogCaptureFixture
) -> None:
    agent = _agent()
    kwargs = {"temprature": 0.1, "max_token": 5}
    caplog.set_level(logging.WARNING, logger="praval.core.agent")

    if entry_point == "chat":
        agent.chat("hi", **kwargs)
    elif entry_point == "generate":
        agent.generate("hi", **kwargs)
    elif entry_point == "agenerate":
        asyncio.run(agent.agenerate("hi", **kwargs))
    elif entry_point == "stream":
        list(agent.stream("hi", **kwargs))
    else:

        async def consume() -> None:
            async for _ in agent.astream("hi", **kwargs):
                pass

        asyncio.run(consume())

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    for name in kwargs:
        matching = [w for w in warnings if f"'{name}'" in w]
        assert len(matching) == 1, warnings
        assert f"Agent.{entry_point}()" in matching[0]
    # The call still ran and answered.
    assert agent.conversation_history[-1]["content"] == "answer:hi"


def test_known_options_do_not_warn_and_reach_the_runtime(
    caplog: pytest.LogCaptureFixture,
) -> None:
    agent = _agent()
    caplog.set_level(logging.WARNING, logger="praval.core.agent")
    agent.generate(
        "hi",
        provider_options={"seed": 3},
        metadata={"workflow": "test"},
        timeout=4.0,
        max_tool_rounds=2,
        stream=False,
    )
    assert not [r for r in caplog.records if r.levelno == logging.WARNING]
    request = agent.provider.requests[-1]
    assert request.provider_options.get("seed") == 3
    assert request.metadata.get("workflow") == "test"
    assert request.timeout == 4.0


def test_stream_keyword_is_unknown_where_the_runtime_does_not_take_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    agent = _agent()
    caplog.set_level(logging.WARNING, logger="praval.core.agent")
    asyncio.run(agent.agenerate("hi", stream=True))
    assert "Agent.agenerate() ignored unknown keyword argument 'stream'" in (
        caplog.text
    )


def test_cancelled_call_token_discards_the_answer() -> None:
    agent = _agent()
    token = _CallToken()
    agent._append_user_turn("late")
    assert token.cancel() is True
    assert agent._commit_answer("late answer", token) is False
    assert agent.conversation_history == [SYSTEM, {"role": "user", "content": "late"}]


def test_committed_call_token_cannot_be_cancelled() -> None:
    agent = _agent()
    token = _CallToken()
    assert agent._commit_answer("answer", token) is True
    assert token.cancel() is False
    assert agent.conversation_history[-1] == {"role": "assistant", "content": "answer"}


def test_failed_chat_keeps_user_turn_and_wraps_error() -> None:
    class BrokenProvider(FakeProvider):
        def invoke(self, request: ModelRequest) -> ModelResponse:
            raise RuntimeError("provider down")

    agent = _agent(BrokenProvider())
    with pytest.raises(PravalError, match="provider down"):
        agent.chat("hi")
    assert agent.conversation_history == [SYSTEM, {"role": "user", "content": "hi"}]
