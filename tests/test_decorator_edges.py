"""Focused edge behavior for decorator tool discovery and error policy."""

import asyncio
import threading
import time
from types import SimpleNamespace
from typing import Any, Dict, Iterator, List, Optional, Tuple
from unittest.mock import Mock, patch

import pytest

import praval.decorators as decorators
from praval.core.agent import Agent
from praval.core.exceptions import ToolError
from praval.core.tool_registry import Tool, ToolMetadata
from praval.models import ModelRequest, ModelResponse, ProviderCapabilities


def test_decorator_error_policy_handles_callback_failure_and_unknown_value(caplog):
    error = RuntimeError("handler failed")
    callback = Mock(side_effect=RuntimeError("callback failed"))
    decorators._handle_agent_error(
        error, Mock(), "agent-a", callback, context="handler"
    )
    assert "custom error handler" in caplog.text

    decorators._handle_agent_error(
        error, Mock(), "agent-a", "unexpected", context="handler"
    )
    assert "Unknown on_error value" in caplog.text


def test_auto_register_tools_handles_untyped_parameters_and_registry_failure():
    agent = SimpleNamespace(tools={})

    def raw(value, optional="x"):
        return value

    tool = SimpleNamespace(
        func=raw,
        metadata=SimpleNamespace(
            tool_name="raw-tool",
            description="",
            requires_approval=True,
            risk_level="high",
            approval_reason="Review raw input",
        ),
    )
    registry = Mock()
    registry.get_tools_for_agent.return_value = [tool]
    with patch("praval.decorators.get_tool_registry", return_value=registry):
        decorators._auto_register_tools(agent, "agent-a")
    assert agent.tools["raw-tool"]["parameters"] == {
        "value": {"type": "any", "required": True},
        "optional": {"type": "any", "required": False},
    }

    with patch(
        "praval.decorators.get_tool_registry",
        side_effect=RuntimeError("registry failed"),
    ):
        decorators._auto_register_tools(agent, "agent-a")


def test_attach_tool_preserves_existing_definition():
    existing = {"function": Mock()}
    agent = SimpleNamespace(tools={"existing": existing})
    decorators._attach_tool(agent, "existing", Mock(), "new", {})
    assert agent.tools["existing"] is existing


def test_register_callable_tool_recovers_registry_races_and_failures():
    def decorated(value: int) -> int:
        return value

    metadata = ToolMetadata(tool_name="decorated", owned_by="agent-a")
    tool = Tool(decorated, metadata)
    decorated._praval_tool = tool
    registry = Mock()
    registry.get_tool.return_value = None
    registry.register_tool.side_effect = ToolError("already registered")
    with patch("praval.decorators.get_tool_registry", return_value=registry):
        assert decorators._register_callable_tool("agent-a", decorated) is tool

    def raw(value: int) -> int:
        return value

    existing = Mock()
    registry.reset_mock()
    registry.register_tool.side_effect = ToolError("race")
    registry.get_tool.return_value = existing
    with patch("praval.decorators.get_tool_registry", return_value=registry):
        assert decorators._register_callable_tool("agent-a", raw) is existing

    registry.register_tool.side_effect = RuntimeError("broken")
    with patch("praval.decorators.get_tool_registry", return_value=registry):
        assert decorators._register_callable_tool("agent-a", raw) is None


def test_agent_decorator_forwards_runtime_config_and_ignores_bad_tool_entries():
    underlying = Mock()
    underlying.tools = {}
    reef = Mock(default_channel="main")
    registry = Mock()
    registry.get_tools_by_category.return_value = []
    registry.get_tool.return_value = None

    def callable_tool(value: int) -> int:
        return value

    with (
        patch("praval.decorators.Agent", return_value=underlying) as agent_class,
        patch("praval.decorators.get_reef", return_value=reef),
        patch("praval.decorators.get_tool_registry", return_value=registry),
        patch("praval.decorators._register_callable_tool", return_value=None),
    ):

        @decorators.agent(
            "configured",
            provider="gemini",
            model="gemini-test",
            config={"temperature": 0.2},
            tools=["missing", callable_tool, 42],
            tool_categories=["search"],
            auto_discover_tools=False,
        )
        def configured(spore):
            return None

    assert configured._praval_name == "configured"
    agent_class.assert_called_once_with(
        name="configured",
        system_message=None,
        memory_enabled=False,
        memory_config=None,
        knowledge_base=None,
        hitl_enabled=False,
        provider="gemini",
        model="gemini-test",
        config={"temperature": 0.2},
    )


def test_error_policy_raise_reraises_original_error():
    error = ValueError("bad input")
    with pytest.raises(ValueError, match="bad input"):
        decorators._handle_agent_error(
            error, Mock(), "agent-a", "raise", context="handler"
        )


class BlockingProvider:
    """Answers at once, except for "slow" prompts, which wait for ``release``."""

    provider_name = "fake"
    capabilities = ProviderCapabilities(tools=True)

    def __init__(self) -> None:
        self.release = threading.Event()
        self.slow_started = threading.Event()
        self.slow_running = threading.Event()
        self.requests: List[ModelRequest] = []

    def invoke(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        prompt = [m for m in request.messages if m.role == "user"][-1].content
        if str(prompt).startswith("slow"):
            self.slow_running.set()
            self.slow_started.set()
            try:
                self.release.wait(10)
            finally:
                self.slow_running.clear()
        return ModelResponse(content=f"answer:{prompt}", model="fake-model")


def _context_agent(
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[Agent, BlockingProvider, List[Tuple[Any, bool]], threading.Event]:
    """Build a real agent bound to the decorator context, spying on commits."""
    provider = BlockingProvider()
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=provider
    ):
        agent = Agent(
            "chat-agent",
            provider="fake",
            model="fake-model",
            system_message="Be brief.",
            config=config,
        )
    commits: List[Tuple[Any, bool]] = []
    slow_finished = threading.Event()
    commit_answer = agent._commit_answer

    def spy(content: Any, token: Any = None) -> bool:
        committed = commit_answer(content, token)
        commits.append((content, committed))
        if str(content).startswith("answer:slow"):
            slow_finished.set()
        return committed

    agent._commit_answer = spy  # type: ignore[method-assign]
    decorators._agent_context.agent = agent
    return agent, provider, commits, slow_finished


@pytest.fixture
def context_agent() -> Iterator[Any]:
    built: List[BlockingProvider] = []

    def build(config: Optional[Dict[str, Any]] = None) -> Any:
        result = _context_agent(config)
        built.append(result[1])
        return result

    try:
        yield build
    finally:
        for provider in built:
            provider.release.set()
        decorators._agent_context.agent = None


def test_chat_timeout_raises_on_time_while_worker_still_runs(context_agent):
    agent, provider, commits, slow_finished = context_agent()

    started = time.perf_counter()
    with pytest.raises(TimeoutError, match="timed out after 0.01 seconds"):
        decorators.chat("slow question", timeout=0.01)
    elapsed = time.perf_counter() - started

    # The old implementation joined the worker, so it returned only after the
    # provider did (never, here, until release is set below).
    assert elapsed < 0.5
    assert provider.slow_started.wait(2)
    assert provider.slow_running.is_set()

    provider.release.set()
    assert slow_finished.wait(5)
    assert commits == [("answer:slow question", False)]
    assert all(
        m["content"] != "answer:slow question" for m in agent.conversation_history
    )


def test_abandoned_answer_never_lands_after_a_second_chat(context_agent):
    agent, provider, commits, slow_finished = context_agent()

    with pytest.raises(TimeoutError):
        decorators.chat("slow question", timeout=0.01)
    assert provider.slow_started.wait(2)

    # The handler moves on while the first worker is still waiting.
    assert decorators.chat("fast question", timeout=5) == "answer:fast question"
    assert provider.slow_running.is_set()

    provider.release.set()
    assert slow_finished.wait(5)

    contents = [m["content"] for m in agent.conversation_history]
    assert "answer:slow question" not in contents
    assert contents[-2:] == ["fast question", "answer:fast question"]
    assert ("answer:slow question", False) in commits
    assert ("answer:fast question", True) in commits


def test_chat_defaults_to_agent_configured_timeout(context_agent):
    agent, provider, _, slow_finished = context_agent({"timeout": 0.05})

    with pytest.raises(TimeoutError, match="timed out after 0.05 seconds"):
        decorators.chat("slow question")

    provider.release.set()
    assert slow_finished.wait(5)
    assert agent.conversation_history[-1]["content"] == "slow question"


def test_chat_without_any_timeout_waits_for_the_provider(context_agent):
    agent, provider, _, _ = context_agent()
    assert agent.config.timeout is None

    def release_later() -> None:
        assert provider.slow_started.wait(5)
        time.sleep(0.2)
        provider.release.set()

    releaser = threading.Thread(target=release_later)
    releaser.start()
    try:
        assert decorators.chat("slow question") == "answer:slow question"
    finally:
        provider.release.set()
        releaser.join(5)
    assert agent.conversation_history[-1]["content"] == "answer:slow question"


def test_chat_and_achat_forward_per_call_options(context_agent):
    agent, provider, _, _ = context_agent()

    @agent.tool
    def alpha(value: str) -> str:
        """First tool."""
        return value

    @agent.tool
    def beta(value: str) -> str:
        """Second tool."""
        return value

    decorators.chat("one", timeout=5, allowed_tool_names=["beta"])
    assert [tool.name for tool in provider.requests[-1].tools] == ["beta"]

    asyncio.run(
        decorators.achat(
            "two",
            additional_system_message="Extra rule.",
            allowed_tool_names=["alpha"],
        )
    )
    request = provider.requests[-1]
    assert [tool.name for tool in request.tools] == ["alpha"]
    assert request.messages[0].content == "Extra rule."

    mock_agent = Mock()
    mock_agent.chat.return_value = "ok"
    decorators._agent_context.agent = mock_agent
    reasoning = {"effort": "low"}
    assert decorators.chat("three", reasoning=reasoning) == "ok"
    mock_agent.chat.assert_called_with("three", reasoning=reasoning)
    assert asyncio.run(decorators.achat("four", timeout=5, reasoning=reasoning)) == "ok"
    mock_agent.chat.assert_called_with("four", reasoning=reasoning)


def test_achat_timeout_discards_late_answer(context_agent):
    agent, provider, commits, slow_finished = context_agent()

    async def run() -> float:
        started = time.perf_counter()
        with pytest.raises(TimeoutError, match="timed out after 0.01 seconds"):
            await decorators.achat("slow question", timeout=0.01)
        elapsed = time.perf_counter() - started
        assert await decorators.achat("fast question", timeout=5) == (
            "answer:fast question"
        )
        assert provider.slow_running.is_set()
        # asyncio.run() waits for executor threads at shutdown; release first.
        provider.release.set()
        return elapsed

    assert asyncio.run(run()) < 0.5
    assert slow_finished.wait(5)
    contents = [m["content"] for m in agent.conversation_history]
    assert "answer:slow question" not in contents
    assert contents[-1] == "answer:fast question"
    assert ("answer:slow question", False) in commits


def test_chat_returns_answer_committed_as_the_limit_expired():
    token_holder: Dict[str, Any] = {}

    class CommitsLate:
        config = SimpleNamespace(timeout=None)

        def chat(self, message: str) -> str:
            token = Agent._take_call_token()
            token_holder["token"] = token
            # Commit, then return only after the caller's limit has expired.
            assert token is not None and token.try_commit(lambda: None)
            time.sleep(0.1)
            return "committed answer"

    decorators._agent_context.agent = CommitsLate()
    try:
        assert decorators.chat("hi", timeout=0.01) == "committed answer"
    finally:
        decorators._agent_context.agent = None
    assert token_holder["token"].cancel() is False
