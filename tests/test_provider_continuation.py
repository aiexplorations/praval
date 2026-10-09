"""Multi-round tool continuation contracts for every provider adapter.

Each fake SDK client records a deep copy of every request, so these tests see
exactly what the adapter would send.  The runtime passes the original request
to every continuation; the adapters must still resend every earlier round.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import List, Tuple
from unittest.mock import patch

import pytest
from provider_harnesses import (
    HARNESSES,
    QUESTION,
    AnthropicHarness,
    Entry,
    GeminiHarness,
    GeminiNativeIdHarness,
    Harness,
    _runtime,
    _tools,
)

from praval.core.agent import Agent
from praval.core.exceptions import InterventionRequired
from praval.models import ModelMessage, ModelRequest, ToolResult


@pytest.fixture(params=HARNESSES, ids=lambda factory: factory.name)
def harness(request: pytest.FixtureRequest) -> Harness:
    return request.param()


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
