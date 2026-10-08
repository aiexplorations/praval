"""Shared fakes for the agents, Reef and decorators integration matrix.

``ScriptedModel`` is an OpenAI Chat Completions fake built on the shared
``OpenAIHarness``: it answers each request from the request itself, so many
agents and threads can share it without a response queue whose order would
depend on scheduling. For the newest user turn it asks for the tool rounds a
plan returns, then answers ``answer[<question>]`` followed by the tool results
of that turn.
"""

from __future__ import annotations

import copy
import threading
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple
from unittest.mock import patch

import pytest
from provider_harnesses import OpenAIHarness

PROVIDER = "openai"
MODEL = "gpt-test"
WAIT = 5.0

ToolCallPlan = List[Tuple[str, Dict[str, Any]]]
Plan = Callable[[str], List[ToolCallPlan]]

# Threads that belong to process-wide pools, not to one Reef or agent.
SHARED_THREAD_PREFIXES = ("praval-achat_", "asyncio_")


def no_tools(question: str) -> List[ToolCallPlan]:
    """Plan that never calls a tool."""
    return []


def answer_for(question: str, results: Sequence[str] = ()) -> str:
    """Return the answer ``ScriptedModel`` gives for a question and results."""
    text = f"answer[{question}]"
    if results:
        text += "|" + ",".join(results)
    return text


class ScriptedModel(OpenAIHarness):
    """Deterministic, thread-safe Chat Completions fake driven by a plan."""

    def __init__(self, plan: Plan = no_tools) -> None:
        super().__init__()
        self.plan = plan
        self._lock = threading.Lock()
        self._provider: Any = None
        # Called with the user text before answering; tests use it to hold a
        # request at a barrier or event.
        self.on_request: Optional[Callable[[str], None]] = None

    def provider(self, monkeypatch: pytest.MonkeyPatch) -> Any:
        """Return one adapter around the fake client, built on first use."""
        if self._provider is None:
            self._provider = self.build(monkeypatch)
        return self._provider

    def respond(self, **params: Any) -> Any:
        messages: List[Dict[str, Any]] = params["messages"]
        last_user = max(
            index for index, message in enumerate(messages) if message["role"] == "user"
        )
        question = str(messages[last_user]["content"])
        turn = messages[last_user + 1 :]
        rounds_done = sum(
            1
            for message in turn
            if message["role"] == "assistant" and message.get("tool_calls")
        )
        results = [str(m["content"]) for m in turn if m["role"] == "tool"]
        with self._lock:
            self.requests.append(copy.deepcopy(params))
        if self.on_request is not None:
            self.on_request(question)
        rounds = self.plan(question)
        with self._lock:
            if rounds_done < len(rounds):
                return self.tool_turn(rounds[rounds_done])
            return self.final_turn(answer_for(question, results))

    def questions(self) -> List[str]:
        """Return the newest user text of every recorded request, in order."""
        with self._lock:
            requests = list(self.requests)
        found: List[str] = []
        for request in requests:
            users = [m for m in request["messages"] if m["role"] == "user"]
            found.append(str(users[-1]["content"]))
        return found


@contextmanager
def provider_patch(
    model: ScriptedModel, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Make every Agent created inside the block use ``model``."""
    with patch(
        "praval.core.agent.ProviderFactory.create_provider",
        return_value=model.provider(monkeypatch),
    ):
        yield


def question_answer_pairs(history: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """Return (user, assistant) pairs that sit next to each other in history."""
    pairs: List[Tuple[str, str]] = []
    for index, message in enumerate(history[:-1]):
        following = history[index + 1]
        if message["role"] == "user" and following["role"] == "assistant":
            pairs.append((str(message["content"]), str(following["content"])))
    return pairs


def new_threads(before: Sequence[threading.Thread]) -> List[threading.Thread]:
    """Return live threads started since ``before``, ignoring shared pools."""
    known = set(before)
    return [
        thread
        for thread in threading.enumerate()
        if thread not in known
        and thread.is_alive()
        and not thread.name.startswith(SHARED_THREAD_PREFIXES)
    ]


def wait_for_threads_to_exit(before: Sequence[threading.Thread]) -> List[str]:
    """Join new threads for up to ``WAIT`` seconds; return names still alive."""
    for thread in new_threads(before):
        thread.join(WAIT)
    return sorted(thread.name for thread in new_threads(before))
