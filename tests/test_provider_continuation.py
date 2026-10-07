"""Multi-round tool continuation contracts for every provider adapter.

Each fake SDK client records a deep copy of every request, so these tests see
exactly what the adapter would send.  The runtime passes the original request
to every continuation; the adapters must still resend every earlier round.
"""

from __future__ import annotations

import asyncio
import copy
import json
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import Mock, patch

import pytest
from cohere.types.tool_call import ToolCall as CohereToolCall

from praval.core.agent import Agent, AgentConfig
from praval.core.exceptions import InterventionRequired
from praval.model_runtime import ModelRuntime
from praval.models import ModelMessage, ModelRequest, ToolResult
from praval.providers.anthropic import AnthropicProvider
from praval.providers.cohere import CohereProvider
from praval.providers.gemini import GeminiProvider
from praval.providers.openai import OpenAIProvider
from praval.providers.openai_compatible import OpenAICompatibleProvider

QUESTION = "What is the forecast for Paris?"
CODES = {"Paris": "PX-1", "Lyon": "LY-2"}

Call = Tuple[str, str, Dict[str, Any]]
Entry = Tuple[Any, ...]


class Harness:
    """Fake SDK client plus helpers that normalise one adapter's requests."""

    name = ""
    provider_name = ""
    model = ""
    provider_options: Dict[str, Any] = {}

    def __init__(self) -> None:
        self.requests: List[Dict[str, Any]] = []
        self.responses: List[Any] = []
        self._next_call = 0

    def respond(self, **params: Any) -> Any:
        self.requests.append(copy.deepcopy(params))
        return self.responses.pop(0)

    def call_id(self) -> str:
        self._next_call += 1
        return f"{self.name}-call-{self._next_call}"

    def build(self, monkeypatch: pytest.MonkeyPatch) -> Any:
        raise NotImplementedError

    def tool_turn(self, calls: List[Tuple[str, Dict[str, Any]]]) -> Any:
        raise NotImplementedError

    def final_turn(self, text: str) -> Any:
        raise NotImplementedError

    def transcript(self, request: Dict[str, Any]) -> List[Entry]:
        """Return ("call", name, args) and ("result", content) in order."""
        raise NotImplementedError

    def user_texts(self, request: Dict[str, Any]) -> List[str]:
        raise NotImplementedError

    def drop_transcript(self, metadata: Dict[str, Any]) -> None:
        """Turn response metadata into the shape v0.8.3 wrote."""
        raise NotImplementedError


class OpenAIHarness(Harness):
    name = "openai"
    provider_name = "openai"
    model = "gpt-test"

    def build(self, monkeypatch: pytest.MonkeyPatch) -> Any:
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
        client = Mock()
        client.chat.completions.create.side_effect = self.respond
        with patch("praval.providers.openai.openai.OpenAI", return_value=client):
            return OpenAIProvider(
                AgentConfig(provider="openai", model=self.model, max_tokens=100)
            )

    def tool_turn(self, calls: List[Tuple[str, Dict[str, Any]]]) -> Any:
        tool_calls = [
            {
                "id": self.call_id(),
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
            for name, args in calls
        ]
        return self._completion(None, tool_calls, "tool_calls")

    def final_turn(self, text: str) -> Any:
        return self._completion(text, None, "stop")

    def _completion(
        self, text: Optional[str], tool_calls: Optional[List[Any]], finish: str
    ) -> Any:
        message = SimpleNamespace(content=text, tool_calls=tool_calls)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message, finish_reason=finish)],
            usage=None,
        )

    def transcript(self, request: Dict[str, Any]) -> List[Entry]:
        entries: List[Entry] = []
        seen_ids = set()
        for message in request["messages"]:
            if message["role"] == "assistant" and message.get("tool_calls"):
                for tool_call in message["tool_calls"]:
                    seen_ids.add(tool_call["id"])
                    function = tool_call["function"]
                    entries.append(
                        ("call", function["name"], json.loads(function["arguments"]))
                    )
            elif message["role"] == "tool":
                assert message["tool_call_id"] in seen_ids
                entries.append(("result", message["content"]))
        return entries

    def user_texts(self, request: Dict[str, Any]) -> List[str]:
        return [m["content"] for m in request["messages"] if m["role"] == "user"]

    def drop_transcript(self, metadata: Dict[str, Any]) -> None:
        del metadata["openai_chat_messages"]


class OpenAICompatibleHarness(OpenAIHarness):
    name = "local"
    provider_name = "ollama"
    model = "llama-test"
    # Local models declare tool support per model; this one has it.
    provider_options = {"capabilities": {"tools": True}}

    def build(self, monkeypatch: pytest.MonkeyPatch) -> Any:
        client = Mock()
        client.chat.completions.create.side_effect = self.respond
        with patch(
            "praval.providers.openai_compatible.openai.OpenAI", return_value=client
        ):
            return OpenAICompatibleProvider(
                AgentConfig(provider="ollama", model=self.model, max_tokens=100)
            )


class AnthropicHarness(Harness):
    name = "anthropic"
    provider_name = "anthropic"
    model = "claude-test"

    def build(self, monkeypatch: pytest.MonkeyPatch) -> Any:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
        client = Mock()
        client.messages.create.side_effect = self.respond
        with patch(
            "praval.providers.anthropic.anthropic.Anthropic", return_value=client
        ):
            return AnthropicProvider(
                AgentConfig(provider="anthropic", model=self.model, max_tokens=100)
            )

    def tool_turn(self, calls: List[Tuple[str, Dict[str, Any]]]) -> Any:
        blocks: List[Any] = [{"type": "text", "text": "Checking."}]
        blocks.extend(
            {"type": "tool_use", "id": self.call_id(), "name": name, "input": args}
            for name, args in calls
        )
        return SimpleNamespace(content=blocks, stop_reason="tool_use", usage=None)

    def final_turn(self, text: str) -> Any:
        return SimpleNamespace(
            content=[{"type": "text", "text": text}],
            stop_reason="end_turn",
            usage=None,
        )

    def transcript(self, request: Dict[str, Any]) -> List[Entry]:
        entries: List[Entry] = []
        seen_ids = set()
        for message in request["messages"]:
            if not isinstance(message["content"], list):
                continue
            for block in message["content"]:
                if block["type"] == "tool_use":
                    seen_ids.add(block["id"])
                    entries.append(("call", block["name"], block["input"]))
                elif block["type"] == "tool_result":
                    assert block["tool_use_id"] in seen_ids
                    entries.append(("result", block["content"]))
        return entries

    def user_texts(self, request: Dict[str, Any]) -> List[str]:
        return [
            m["content"]
            for m in request["messages"]
            if m["role"] == "user" and isinstance(m["content"], str)
        ]

    def drop_transcript(self, metadata: Dict[str, Any]) -> None:
        del metadata["anthropic_messages"]


class GeminiHarness(Harness):
    """Gemini 3 style turns: every functionCall part carries a signature."""

    name = "gemini"
    provider_name = "gemini"
    model = "gemini-test"
    native_ids = False

    def __init__(self) -> None:
        super().__init__()
        self.sent_turns: List[Dict[str, Any]] = []

    def build(self, monkeypatch: pytest.MonkeyPatch) -> Any:
        provider = GeminiProvider(
            AgentConfig(provider="gemini", model=self.model, base_url="http://test")
        )
        monkeypatch.setattr(provider, "_post_json", self._post_json)
        return provider

    def _post_json(
        self, method: str, payload: Dict[str, Any], *, timeout: Any = None
    ) -> Dict[str, Any]:
        assert method == "generateContent"
        return self.respond(**payload)

    def tool_turn(self, calls: List[Tuple[str, Dict[str, Any]]]) -> Any:
        parts: List[Dict[str, Any]] = [
            {"text": "Planning the lookup.", "thought": True},
        ]
        for name, args in calls:
            call_id = self.call_id()
            function_call: Dict[str, Any] = {"name": name, "args": args}
            if self.native_ids:
                function_call["id"] = call_id
            parts.append(
                {
                    "functionCall": function_call,
                    "thoughtSignature": f"c2ln{self._next_call}==",
                }
            )
        parts.append({"text": "Calling tools now."})
        content = {"role": "model", "parts": parts}
        self.sent_turns.append(copy.deepcopy(content))
        return {"candidates": [{"content": content, "finishReason": "STOP"}]}

    def final_turn(self, text: str) -> Any:
        return {
            "candidates": [{"content": {"role": "model", "parts": [{"text": text}]}}]
        }

    def transcript(self, request: Dict[str, Any]) -> List[Entry]:
        entries: List[Entry] = []
        for content in request["contents"]:
            for part in content["parts"]:
                if "functionCall" in part:
                    call = part["functionCall"]
                    entries.append(("call", call["name"], call["args"]))
                elif "functionResponse" in part:
                    entries.append(
                        ("result", part["functionResponse"]["response"]["result"])
                    )
        return entries

    def user_texts(self, request: Dict[str, Any]) -> List[str]:
        return [
            part["text"]
            for content in request["contents"]
            if content["role"] == "user"
            for part in content["parts"]
            if "text" in part
        ]

    def drop_transcript(self, metadata: Dict[str, Any]) -> None:
        # v0.8.3 kept gemini_contents but rebuilt model turns from name/args.
        for content in metadata["gemini_contents"]:
            if content["role"] == "model":
                content["parts"] = [
                    {
                        "functionCall": {
                            "name": part["functionCall"]["name"],
                            "args": part["functionCall"]["args"],
                        }
                    }
                    for part in content["parts"]
                    if "functionCall" in part
                ]


class GeminiNativeIdHarness(GeminiHarness):
    name = "gemini-native"
    native_ids = True


class CohereHarness(Harness):
    name = "cohere"
    provider_name = "cohere"
    model = "command-test"

    def build(self, monkeypatch: pytest.MonkeyPatch) -> Any:
        monkeypatch.setenv("COHERE_API_KEY", "test-cohere-key")
        client = Mock()
        client.chat.side_effect = self.respond
        with patch("praval.providers.cohere.cohere.Client", return_value=client):
            return CohereProvider(AgentConfig(provider="cohere", model=self.model))

    def tool_turn(self, calls: List[Tuple[str, Dict[str, Any]]]) -> Any:
        # Real SDK ToolCall objects: v1 calls carry name and parameters, no id.
        return SimpleNamespace(
            text="I will use the tools.",
            tool_calls=[
                CohereToolCall(name=name, parameters=args) for name, args in calls
            ],
            finish_reason="COMPLETE",
        )

    def final_turn(self, text: str) -> Any:
        return SimpleNamespace(text=text, tool_calls=[], finish_reason="COMPLETE")

    def transcript(self, request: Dict[str, Any]) -> List[Entry]:
        entries: List[Entry] = []
        pending: List[Dict[str, Any]] = []

        def add_results(tool_results: List[Dict[str, Any]]) -> None:
            for tool_result in tool_results:
                assert tool_result["call"] in pending
                entries.append(("result", tool_result["outputs"][0]["result"]))

        for entry in request.get("chat_history") or []:
            if entry["role"] == "CHATBOT":
                pending = list(entry.get("tool_calls") or [])
                for call in pending:
                    entries.append(("call", call["name"], call["parameters"]))
            elif entry["role"] == "TOOL":
                add_results(entry["tool_results"])
        add_results(request.get("tool_results") or [])
        return entries

    def user_texts(self, request: Dict[str, Any]) -> List[str]:
        texts = [
            entry["message"]
            for entry in request.get("chat_history") or []
            if entry["role"] == "USER"
        ]
        if request.get("message"):
            texts.append(request["message"])
        return texts

    def drop_transcript(self, metadata: Dict[str, Any]) -> None:
        del metadata["cohere_chat_history"]


HARNESSES: List[Callable[[], Harness]] = [
    OpenAIHarness,
    OpenAICompatibleHarness,
    AnthropicHarness,
    GeminiHarness,
    GeminiNativeIdHarness,
    CohereHarness,
]


@pytest.fixture(params=HARNESSES, ids=lambda factory: factory.name)
def harness(request: pytest.FixtureRequest) -> Harness:
    return request.param()


def _tools(log: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    def lookup(city: str) -> str:
        log.append(("lookup", city))
        return CODES[city]

    def forecast(code: str) -> str:
        log.append(("forecast", code))
        return "Sunny" if code == "PX-1" else "Rain"

    return [
        {
            "function": lookup,
            "description": "Return the internal code for a city",
            "parameters": {"city": {"type": "str", "required": True}},
        },
        {
            "function": forecast,
            "description": "Return the forecast for an internal city code",
            "parameters": {"code": {"type": "str", "required": True}},
        },
    ]


def _runtime(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> ModelRuntime:
    provider = harness.build(monkeypatch)
    return ModelRuntime(
        provider=provider,
        provider_name=harness.provider_name,
        config=AgentConfig(
            provider=harness.provider_name,
            model=harness.model,
            provider_options=dict(harness.provider_options),
        ),
    )


def _dependent_script(harness: Harness) -> None:
    harness.responses = [
        harness.tool_turn([("lookup", {"city": "Paris"})]),
        harness.tool_turn([("forecast", {"code": "PX-1"})]),
        harness.final_turn("Sunny in Paris."),
    ]


FULL_DEPENDENT_TRANSCRIPT: List[Entry] = [
    ("call", "lookup", {"city": "Paris"}),
    ("result", "PX-1"),
    ("call", "forecast", {"code": "PX-1"}),
    ("result", "Sunny"),
]


def test_three_dependent_rounds_resend_every_earlier_round(harness, monkeypatch):
    runtime = _runtime(harness, monkeypatch)
    _dependent_script(harness)
    log: List[Tuple[str, str]] = []

    response = runtime.invoke(
        messages=[{"role": "user", "content": QUESTION}], tools=_tools(log)
    )

    assert response.content == "Sunny in Paris."
    assert log == [("lookup", "Paris"), ("forecast", "PX-1")]
    assert len(harness.requests) == 3
    first, second, third = harness.requests
    assert harness.transcript(first) == []
    # The second request is a snapshot: later rounds must not leak into it.
    assert harness.transcript(second) == FULL_DEPENDENT_TRANSCRIPT[:2]
    assert harness.transcript(third) == FULL_DEPENDENT_TRANSCRIPT
    for request in harness.requests:
        assert harness.user_texts(request) == [QUESTION]
    call_ids = [call.id for call in response.tool_calls]
    assert len(call_ids) == len(set(call_ids)) == 2


def test_three_dependent_rounds_async(harness, monkeypatch):
    runtime = _runtime(harness, monkeypatch)
    _dependent_script(harness)
    log: List[Tuple[str, str]] = []

    response = asyncio.run(
        runtime.ainvoke(
            messages=[{"role": "user", "content": QUESTION}], tools=_tools(log)
        )
    )

    assert response.content == "Sunny in Paris."
    assert harness.transcript(harness.requests[2]) == FULL_DEPENDENT_TRANSCRIPT


def test_same_tool_called_in_two_rounds_keeps_both_and_unique_ids(harness, monkeypatch):
    runtime = _runtime(harness, monkeypatch)
    harness.responses = [
        harness.tool_turn([("lookup", {"city": "Paris"})]),
        harness.tool_turn([("lookup", {"city": "Lyon"})]),
        harness.final_turn("Codes found."),
    ]
    log: List[Tuple[str, str]] = []

    response = runtime.invoke(
        messages=[{"role": "user", "content": QUESTION}], tools=_tools(log)
    )

    assert log == [("lookup", "Paris"), ("lookup", "Lyon")]
    assert harness.transcript(harness.requests[2]) == [
        ("call", "lookup", {"city": "Paris"}),
        ("result", "PX-1"),
        ("call", "lookup", {"city": "Lyon"}),
        ("result", "LY-2"),
    ]
    call_ids = [call.id for call in response.tool_calls]
    assert len(set(call_ids)) == 2
    assert [result["tool_call_id"] for result in response.metadata["tool_results"]] == (
        call_ids
    )


def test_two_calls_in_one_round_then_a_dependent_round(harness, monkeypatch):
    runtime = _runtime(harness, monkeypatch)
    harness.responses = [
        harness.tool_turn(
            [("lookup", {"city": "Paris"}), ("lookup", {"city": "Lyon"})]
        ),
        harness.tool_turn([("forecast", {"code": "LY-2"})]),
        harness.final_turn("Rain in Lyon."),
    ]
    log: List[Tuple[str, str]] = []

    response = runtime.invoke(
        messages=[{"role": "user", "content": QUESTION}], tools=_tools(log)
    )

    assert response.content == "Rain in Lyon."
    assert harness.transcript(harness.requests[1]) == [
        ("call", "lookup", {"city": "Paris"}),
        ("call", "lookup", {"city": "Lyon"}),
        ("result", "PX-1"),
        ("result", "LY-2"),
    ]
    assert harness.transcript(harness.requests[2]) == [
        ("call", "lookup", {"city": "Paris"}),
        ("call", "lookup", {"city": "Lyon"}),
        ("result", "PX-1"),
        ("result", "LY-2"),
        ("call", "forecast", {"code": "LY-2"}),
        ("result", "Rain"),
    ]
    call_ids = [call.id for call in response.tool_calls]
    assert len(set(call_ids)) == 3


def test_v083_state_without_transcript_still_continues(harness, monkeypatch):
    provider = harness.build(monkeypatch)
    harness.responses = [
        harness.tool_turn([("lookup", {"city": "Paris"})]),
        harness.final_turn("Code PX-1."),
    ]
    request = ModelRequest(
        provider=harness.provider_name,
        model=harness.model,
        messages=[ModelMessage(role="user", content=QUESTION)],
    )
    first = provider.invoke(request, tools=_tools([]))
    first.metadata = json.loads(json.dumps(first.metadata))
    harness.drop_transcript(first.metadata)
    call = first.tool_calls[0]

    continued = provider.continue_with_tool_results(
        request,
        first,
        [ToolResult(tool_call_id=call.id, name=call.name, content="PX-1")],
    )

    assert continued.content == "Code PX-1."
    assert harness.transcript(harness.requests[1]) == [
        ("call", "lookup", {"city": "Paris"}),
        ("result", "PX-1"),
    ]
    assert harness.user_texts(harness.requests[1]) == [QUESTION]


def test_hitl_pause_in_round_two_resumes_with_full_transcript_after_restart(
    harness, monkeypatch, tmp_path
):
    db_path = str(tmp_path / "continuation-hitl.db")
    log: List[Tuple[str, str]] = []

    def build_agent(active: Harness) -> Agent:
        provider = active.build(monkeypatch)
        with patch(
            "praval.core.agent.ProviderFactory.create_provider",
            return_value=provider,
        ):
            agent = Agent(
                "continuation-agent",
                provider=active.provider_name,
                model=active.model,
                hitl_enabled=True,
                hitl_db_path=db_path,
                config={"provider_options": dict(active.provider_options)},
            )
        for tool in _tools(log):
            agent.tool(tool["function"])
        agent.tools["forecast"]["requires_approval"] = True
        agent.tools["forecast"]["approval_reason"] = "Forecasts are billed"
        return agent

    first_agent = build_agent(harness)
    harness.responses = [
        harness.tool_turn([("lookup", {"city": "Paris"})]),
        harness.tool_turn([("forecast", {"code": "PX-1"})]),
    ]
    with pytest.raises(InterventionRequired) as raised:
        first_agent.chat(QUESTION)
    assert log == [("lookup", "Paris")]
    assert len(harness.requests) == 2

    # A new process: new provider, new client, state read back from SQLite.
    restarted = type(harness)()
    restarted._next_call = harness._next_call
    restarted.responses = [restarted.final_turn("Sunny in Paris.")]
    second_agent = build_agent(restarted)
    second_agent.approve_intervention(raised.value.intervention_id, reviewer="qa")

    answer = second_agent.resume_run(raised.value.run_id)

    assert answer == "Sunny in Paris."
    assert log == [("lookup", "Paris"), ("forecast", "PX-1")]
    assert len(restarted.requests) == 1
    assert restarted.transcript(restarted.requests[0]) == FULL_DEPENDENT_TRANSCRIPT
    assert restarted.user_texts(restarted.requests[0]) == [QUESTION]
    if isinstance(harness, GeminiHarness):
        # Signed model turns survive the JSON round trip byte for byte.
        sent_models = [
            content
            for content in restarted.requests[0]["contents"]
            if content["role"] == "model"
        ]
        assert json.dumps(sent_models) == json.dumps(harness.sent_turns)


def test_gemini_signed_parts_round_trip_and_native_ids_are_echoed(monkeypatch):
    harness = GeminiNativeIdHarness()
    runtime = _runtime(harness, monkeypatch)
    _dependent_script(harness)

    runtime.invoke(messages=[{"role": "user", "content": QUESTION}], tools=_tools([]))

    contents = harness.requests[2]["contents"]
    model_turns = [content for content in contents if content["role"] == "model"]
    assert json.dumps(model_turns) == json.dumps(harness.sent_turns)
    responses = [
        part["functionResponse"]
        for content in contents
        if content["role"] == "user"
        for part in content["parts"]
        if "functionResponse" in part
    ]
    assert [response["id"] for response in responses] == [
        "gemini-native-call-1",
        "gemini-native-call-2",
    ]


def test_gemini_generated_ids_are_unique_and_never_sent(monkeypatch):
    harness = GeminiHarness()
    runtime = _runtime(harness, monkeypatch)
    _dependent_script(harness)

    response = runtime.invoke(
        messages=[{"role": "user", "content": QUESTION}], tools=_tools([])
    )

    assert [call.id for call in response.tool_calls] == [
        "gemini-call-0",
        "gemini-call-1",
    ]
    contents = harness.requests[2]["contents"]
    assert "gemini-call" not in json.dumps(contents)
    model_turns = [content for content in contents if content["role"] == "model"]
    assert json.dumps(model_turns) == json.dumps(harness.sent_turns)


def test_anthropic_signed_thinking_blocks_are_returned_unchanged(monkeypatch):
    harness = AnthropicHarness()
    runtime = _runtime(harness, monkeypatch)
    thinking = {
        "type": "thinking",
        "thinking": "The code comes first.",
        "signature": "EqQBCkYIARgCKkA=",
    }
    redacted = {"type": "redacted_thinking", "data": "opaque=="}
    first = harness.tool_turn([("lookup", {"city": "Paris"})])
    first.content = [thinking, redacted, *first.content]
    # SDK block objects without model_dump exercise the attribute fallback.
    second = harness.tool_turn([("forecast", {"code": "PX-1"})])
    second.content = [
        SimpleNamespace(type="thinking", thinking="Now forecast.", signature="Zm9v"),
        *[SimpleNamespace(**block) for block in second.content],
    ]
    harness.responses = [first, second, harness.final_turn("Sunny in Paris.")]

    runtime.invoke(messages=[{"role": "user", "content": QUESTION}], tools=_tools([]))

    assistant_turns = [
        message["content"]
        for message in harness.requests[2]["messages"]
        if message["role"] == "assistant"
    ]
    assert assistant_turns[0][:2] == [thinking, redacted]
    assert assistant_turns[1][0] == {
        "type": "thinking",
        "thinking": "Now forecast.",
        "signature": "Zm9v",
    }
    assert harness.transcript(harness.requests[2]) == FULL_DEPENDENT_TRANSCRIPT
