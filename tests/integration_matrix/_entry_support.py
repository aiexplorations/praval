"""Offline wire clients and public-entry helpers for the WP9a matrix."""

from __future__ import annotations

import asyncio
import copy
import json
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple
from unittest.mock import Mock, patch

import pytest
from provider_harnesses import (
    HARNESSES,
    AnthropicHarness,
    Entry,
    GeminiHarness,
    Harness,
    OpenAIHarness,
)

from praval.core.agent import Agent, AgentConfig
from praval.providers.openai import OpenAIProvider

ENTRY_POINTS = ["chat", "generate", "agenerate", "stream", "astream"]


class ResponsesHarness(OpenAIHarness):
    """Model the Responses server's previous_response_id continuation chain.

    Responses sends only the latest outputs, unlike Chat Completions. Assert
    each call_id against the actual earlier response and reconstruct the server
    conversation for cross-adapter transcript comparisons.
    """

    name = "openai-responses"
    provider_options = {"endpoint": "responses"}

    def __init__(self) -> None:
        super().__init__()
        self.server: Dict[str, Dict[str, Any]] = {}
        self._response_id = 0

    def build(self, monkeypatch: pytest.MonkeyPatch) -> Any:
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
        client = Mock()
        client.responses.create.side_effect = self.respond
        with patch("praval.providers.openai.openai.OpenAI", return_value=client):
            return OpenAIProvider(AgentConfig(provider="openai", model=self.model))

    def tool_turn(self, calls: List[Tuple[str, Dict[str, Any]]]) -> Any:
        return self._response(
            "",
            [
                {
                    "type": "function_call",
                    "call_id": self.call_id(),
                    "name": name,
                    "arguments": json.dumps(args),
                }
                for name, args in calls
            ],
        )

    def final_turn(self, text: str) -> Any:
        return self._response(text, [])

    def _response(self, text: str, output: List[Any]) -> Dict[str, Any]:
        self._response_id += 1
        return {
            "id": f"response-{self._response_id}",
            "output_text": text,
            "output": output
            or [
                {"type": "message", "content": [{"type": "output_text", "text": text}]}
            ],
        }

    def respond(self, **params: Any) -> Any:
        result = super().respond(**params)
        self.server[result["id"]] = {"request": copy.deepcopy(params), "reply": result}
        if params.get("stream"):
            return iter(
                [
                    {
                        "type": "response.output_text.delta",
                        "delta": result["output_text"],
                    },
                    {"type": "response.completed", "response": result},
                ]
            )
        return result

    def transcript(self, request: Dict[str, Any]) -> List[Entry]:
        previous_id = request.get("previous_response_id")
        if not previous_id:
            return []
        previous = self.server[previous_id]
        entries = self.transcript(previous["request"])
        calls = [
            item
            for item in previous["reply"]["output"]
            if item["type"] == "function_call"
        ]
        entries.extend(
            ("call", call["name"], json.loads(call["arguments"])) for call in calls
        )
        assert [item["call_id"] for item in request["input"]] == [
            call["call_id"] for call in calls
        ]
        assert all(item["type"] == "function_call_output" for item in request["input"])
        entries.extend(("result", item["output"]) for item in request["input"])
        return entries

    def user_texts(self, request: Dict[str, Any]) -> List[str]:
        if request.get("previous_response_id"):
            return self.user_texts(
                self.server[request["previous_response_id"]]["request"]
            )
        return [item["content"] for item in request["input"] if item["role"] == "user"]


MATRIX_HARNESSES = [*HARNESSES, ResponsesHarness]


def build_provider(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Install fake native streams at the SDK/HTTP boundary, never the runtime."""
    provider = harness.build(monkeypatch)
    if isinstance(harness, AnthropicHarness):
        # Force the adapter's SDK create(stream=True) path.
        provider.client.messages.stream = None
        provider.client.messages.create.side_effect = lambda **params: (
            iter(
                [
                    {
                        "type": "content_block_delta",
                        "delta": {"text": harness.respond(**params).content[0]["text"]},
                    }
                ]
            )
            if params.get("stream")
            else harness.respond(**params)
        )
    elif isinstance(harness, GeminiHarness):
        monkeypatch.setattr(
            provider,
            "_post_stream",
            lambda method, payload, **kwargs: iter([harness.respond(**payload)]),
        )
    elif isinstance(harness, OpenAIHarness) and not isinstance(
        harness, ResponsesHarness
    ):

        def respond(**params: Any) -> Any:
            response = harness.respond(**params)
            if params.get("stream"):
                return iter(
                    [
                        SimpleNamespace(
                            choices=[
                                SimpleNamespace(
                                    delta={
                                        "content": response.choices[0].message.content
                                    },
                                    finish_reason="stop",
                                )
                            ],
                            usage=None,
                        )
                    ]
                )
            return response

        provider.client.chat.completions.create.side_effect = respond
    return provider


def build_agent(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    *,
    hitl_db_path: str = "",
) -> Agent:
    provider = build_provider(harness, monkeypatch)
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=provider
    ):
        return Agent(
            "entry-matrix",
            provider=harness.provider_name,
            model=harness.model,
            system_message="Matrix system instruction.",
            hitl_enabled=bool(hitl_db_path),
            hitl_db_path=hitl_db_path or None,
            config={"provider_options": dict(harness.provider_options)},
        )


def run_entry(
    agent: Agent, entry: str, message: str, **options: Any
) -> Tuple[str, Any]:
    if entry == "chat":
        return agent.chat(message, **options), None
    if entry == "generate":
        response = agent.generate(message, **options)
        return response.content, response
    if entry == "agenerate":
        response = asyncio.run(agent.agenerate(message, **options))
        return response.content, response
    if entry == "stream":
        events = list(agent.stream(message, **options))
    else:

        async def collect() -> List[Any]:
            return [event async for event in agent.astream(message, **options)]

        events = asyncio.run(collect())
    assert events[0].type == "start"
    finals = [event for event in events if event.type == "final"]
    assert len(finals) == 1 and events[-1].type == "final"
    assert "".join(event.delta for event in events if event.type == "delta") == (
        finals[0].response.content
    )
    return finals[0].response.content, finals[0].response
