"""Fake SDK clients for every provider adapter, shared by integration tests.

Each harness builds a real Praval adapter around a fake SDK client (or, for
Gemini, a patched ``_post_json``). The fake records a deep copy of every
request, so tests can assert exactly what the adapter would send, and returns
scripted responses built with ``tool_turn`` and ``final_turn``.
"""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import Mock, patch

import pytest
from cohere.types.tool_call import ToolCall as CohereToolCall

from praval.core.agent import AgentConfig
from praval.model_runtime import ModelRuntime
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
