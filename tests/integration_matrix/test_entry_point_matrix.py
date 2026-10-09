"""Public Agent entry points exercised against real adapters and fake wire SDKs.

The full provider × entry × tool-shape cross product covers execution paths.
Call controls, schemas and HITL use separate slices to avoid duplicating that
product with toggles that do not change its transcript or side effects. These
are offline integration tests, so they deliberately carry no service marker.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Tuple

import pytest
from _entry_support import (
    ENTRY_POINTS,
    MATRIX_HARNESSES,
    ResponsesHarness,
    build_agent,
    run_entry,
)
from provider_harnesses import (
    QUESTION,
    CohereHarness,
    Entry,
    GeminiHarness,
    Harness,
    OpenAIHarness,
)

from praval.core.exceptions import InterventionRequired, ProviderError
from praval.models import ModelRequest, StructuredOutputConfig

SHAPES = {
    "none": [],
    "one": [[("lookup", {"city": "Paris"})]],
    "dependent-three": [
        [("lookup", {"city": "Paris"})],
        [("forecast", {"code": "PX-1"})],
        [("report", {"weather": "Sunny"})],
    ],
    "two-in-round": [[("lookup", {"city": "Paris"}), ("lookup", {"city": "Lyon"})]],
    "same-tool-twice": [
        [("lookup", {"city": "Paris"})],
        [("lookup", {"city": "Lyon"})],
    ],
}


def register_tools(agent: Any, log: List[Tuple[str, str]]) -> None:
    def lookup(city: str) -> str:
        log.append(("lookup", city))
        return {"Paris": "PX-1", "Lyon": "LY-2"}[city]

    def forecast(code: str) -> str:
        log.append(("forecast", code))
        return {"PX-1": "Sunny", "LY-2": "Rain"}[code]

    def report(weather: str) -> str:
        log.append(("report", weather))
        return f"Forecast: {weather}"

    for function in (lookup, forecast, report):
        agent.tool(function)


def expected_round(calls: List[Tuple[str, Dict[str, Any]]]) -> List[Entry]:
    values = {
        "Paris": "PX-1",
        "Lyon": "LY-2",
        "PX-1": "Sunny",
        "Sunny": "Forecast: Sunny",
    }
    return [
        *(("call", name, args) for name, args in calls),
        *(("result", values[next(iter(args.values()))]) for _, args in calls),
    ]


@pytest.mark.parametrize(
    "factory,entry,shape",
    [
        (factory, entry, shape)
        for factory in MATRIX_HARNESSES
        for entry in ENTRY_POINTS
        for shape in SHAPES
        if factory.name != "cohere" or entry not in {"stream", "astream"}
    ],
    ids=lambda value: getattr(value, "name", value),
)
def test_tool_transcripts_and_history_across_public_entries(
    factory: Any, monkeypatch: pytest.MonkeyPatch, entry: str, shape: str
) -> None:
    harness = factory()
    agent = build_agent(harness, monkeypatch)
    log: List[Tuple[str, str]] = []
    rounds = SHAPES[shape]
    if rounds:
        register_tools(agent, log)
    harness.responses = [
        *(harness.tool_turn(calls) for calls in rounds),
        harness.final_turn("The completed forecast."),
    ]
    try:
        text, response = run_entry(agent, entry, QUESTION)
        assert text == "The completed forecast."
        assert log == [
            (name, next(iter(args.values())))
            for calls in rounds
            for name, args in calls
        ]
        assert len(harness.requests) == len(rounds) + 1
        transcript: List[Entry] = []
        for index, request in enumerate(harness.requests):
            assert harness.transcript(request) == transcript
            assert harness.user_texts(request) == [QUESTION]
            if index < len(rounds):
                transcript.extend(expected_round(rounds[index]))
        assert agent.conversation_history == [
            {"role": "system", "content": "Matrix system instruction."},
            {"role": "user", "content": QUESTION},
            {"role": "assistant", "content": text},
        ]
        if response is not None and rounds:
            ids = [call.id for call in response.tool_calls]
            assert len(ids) == len(set(ids)) == len(log)
            assert [
                result["tool_call_id"] for result in response.metadata["tool_results"]
            ] == ids
        if isinstance(harness, GeminiHarness) and rounds:
            # Includes opaque signatures, thought text and native function ids.
            sent = [
                item
                for item in harness.requests[-1]["contents"]
                if item["role"] == "model"
            ]
            assert sent == harness.sent_turns
    finally:
        agent.close()


def wire_tool_names(harness: Harness, request: Dict[str, Any]) -> List[str]:
    if isinstance(harness, GeminiHarness):
        return [
            tool["name"]
            for group in request["tools"]
            for tool in group["functionDeclarations"]
        ]
    return [tool.get("function", tool)["name"] for tool in request["tools"]]


@pytest.mark.parametrize(
    "factory,entry",
    [
        (factory, entry)
        for factory in MATRIX_HARNESSES
        for entry in ENTRY_POINTS
        if factory.name != "cohere" or entry not in {"stream", "astream"}
    ],
    ids=lambda value: getattr(value, "name", value),
)
def test_per_call_allowlist_and_system_message_reach_every_continuation(
    factory: Any, monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    harness = factory()
    agent = build_agent(harness, monkeypatch)
    log: List[Tuple[str, str]] = []
    register_tools(agent, log)
    harness.responses = [
        harness.tool_turn([("lookup", {"city": "Paris"})]),
        harness.final_turn("PX-1"),
    ]
    try:
        run_entry(
            agent,
            entry,
            QUESTION,
            allowed_tool_names=["lookup"],
            additional_system_message="Per-call instruction for this forecast.",
        )
        assert log == [("lookup", "Paris")]
        for request in harness.requests:
            assert wire_tool_names(harness, request) == ["lookup"]
            if isinstance(harness, ResponsesHarness):
                while request.get("previous_response_id"):
                    request = harness.server[request["previous_response_id"]]["request"]
            assert "Per-call instruction for this forecast." in json.dumps(request)
            assert "Matrix system instruction." in json.dumps(request)
        assert list(agent.tools) == ["lookup", "forecast", "report"]
        assert all(
            "Per-call instruction" not in str(item)
            for item in agent.conversation_history
        )
    finally:
        agent.close()


@pytest.mark.parametrize("entry", ENTRY_POINTS)
def test_unknown_allowlist_fails_before_history_or_provider_call(
    monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    harness = OpenAIHarness()
    agent = build_agent(harness, monkeypatch)
    initial = list(agent.conversation_history)
    try:
        with pytest.raises(ValueError, match="Unknown allowed tools"):
            run_entry(agent, entry, QUESTION, allowed_tool_names=["missing"])
        assert agent.conversation_history == initial
        assert harness.requests == []
    finally:
        agent.close()


@pytest.mark.parametrize(
    "factory,entry",
    [
        (factory, entry)
        for factory in MATRIX_HARNESSES
        for entry in ENTRY_POINTS
        if factory.name != "cohere" or entry not in {"stream", "astream"}
    ],
    ids=lambda value: getattr(value, "name", value),
)
def test_hitl_pause_and_approved_resume_preserve_entry_point_tool_state(
    factory: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Any, entry: str
) -> None:
    harness = factory()
    agent = build_agent(harness, monkeypatch, hitl_db_path=str(tmp_path / "hitl.db"))
    log: List[Tuple[str, str]] = []
    register_tools(agent, log)
    agent.tools["forecast"]["requires_approval"] = True
    harness.responses = [
        harness.tool_turn([("lookup", {"city": "Paris"})]),
        harness.tool_turn([("forecast", {"code": "PX-1"})]),
        harness.final_turn("Approved forecast."),
    ]
    try:
        with pytest.raises(InterventionRequired) as raised:
            run_entry(agent, entry, QUESTION)
        assert log == [("lookup", "Paris")]
        assert len(harness.requests) == 2
        assert agent.conversation_history[-1] == {"role": "user", "content": QUESTION}
        pending = agent.get_pending_interventions()
        assert len(pending) == 1
        assert pending[0].id == raised.value.intervention_id
        agent.approve_intervention(
            raised.value.intervention_id, reviewer="matrix-reviewer"
        )
        assert agent.resume_run(raised.value.run_id) == "Approved forecast."
        assert log == [("lookup", "Paris"), ("forecast", "PX-1")]
        assert harness.transcript(harness.requests[-1]) == [
            ("call", "lookup", {"city": "Paris"}),
            ("result", "PX-1"),
            ("call", "forecast", {"code": "PX-1"}),
            ("result", "Sunny"),
        ]
        assert agent.get_pending_interventions() == []
        assert agent.conversation_history[-1] == {
            "role": "assistant",
            "content": "Approved forecast.",
        }
    finally:
        agent.close()


@pytest.mark.parametrize(
    "factory,entry,mode",
    [
        (factory, entry, mode)
        for factory in MATRIX_HARNESSES
        for entry in ["chat", "generate", "agenerate"]
        for mode in ["invalid", "valid", "unchecked"]
        if factory.name not in {"local", "cohere"} or mode == "invalid"
    ],
    ids=lambda value: getattr(value, "name", value),
)
def test_local_response_schema_validation_after_tool_continuation(
    factory: Any, monkeypatch: pytest.MonkeyPatch, entry: str, mode: str
) -> None:
    harness = factory()
    agent = build_agent(harness, monkeypatch)
    log: List[Tuple[str, str]] = []
    register_tools(agent, log)
    answer = '{"code":"PX-1"}' if mode == "valid" else '{"code":7}'
    harness.responses = [
        harness.tool_turn([("lookup", {"city": "Paris"})]),
        harness.final_turn(answer),
    ]
    schema = StructuredOutputConfig(
        schema={
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        },
        validate_locally=mode != "unchecked",
    )
    try:
        if not agent.runtime.resolve_capabilities(
            ModelRequest(
                messages=[],
                provider=harness.provider_name,
                model=harness.model,
                provider_options=dict(harness.provider_options),
            )
        ).structured_outputs:
            with pytest.raises(ProviderError, match="structured"):
                run_entry(agent, entry, QUESTION, response_schema=schema)
            assert harness.requests == [] and log == []
        elif mode != "invalid":
            text, _ = run_entry(agent, entry, QUESTION, response_schema=schema)
            assert text == answer
            assert agent.conversation_history[-1]["content"] == answer
        else:
            with pytest.raises(ProviderError, match="schema"):
                run_entry(agent, entry, QUESTION, response_schema=schema)
            assert agent.conversation_history[-1]["role"] == "user"
        if harness.requests:
            assert len(harness.requests) == 2
            assert log == [("lookup", "Paris")]
            assert harness.transcript(harness.requests[-1]) == expected_round(
                SHAPES["one"][0]
            )
    finally:
        agent.close()


@pytest.mark.parametrize("entry", ["stream", "astream"])
def test_cohere_stream_capability_refuses_before_sdk_execution(
    monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    harness = CohereHarness()
    agent = build_agent(harness, monkeypatch)
    try:
        with pytest.raises(ProviderError, match="does not support streaming"):
            run_entry(agent, entry, QUESTION)
        assert harness.requests == []
        assert agent.conversation_history[-1] == {"role": "user", "content": QUESTION}
    finally:
        agent.close()


@pytest.mark.parametrize(
    "factory",
    [
        factory
        for factory in MATRIX_HARNESSES
        if factory.name not in {"local", "cohere"}
    ],
    ids=lambda factory: factory.name,
)
@pytest.mark.parametrize("entry", ["stream", "astream"])
@pytest.mark.parametrize("with_tools", [False, True], ids=["native", "buffered-tools"])
@pytest.mark.parametrize(
    "answer",
    ['{"code":"PX-1"}', '{"code":7}', "not-json"],
    ids=["valid", "schema-mismatch", "invalid-json"],
)
def test_streamed_schema_validation_precedes_final_and_history_commit(
    factory: Any,
    monkeypatch: pytest.MonkeyPatch,
    entry: str,
    with_tools: bool,
    answer: str,
) -> None:
    harness = factory()
    agent = build_agent(harness, monkeypatch)
    log: List[Tuple[str, str]] = []
    if with_tools:
        register_tools(agent, log)
    harness.responses = [
        *([harness.tool_turn([("lookup", {"city": "Paris"})])] if with_tools else []),
        harness.final_turn(answer),
    ]
    schema = StructuredOutputConfig(
        schema={
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        },
        validate_locally=True,
    )
    events: List[Any] = []

    def collect() -> None:
        if entry == "stream":
            events.extend(agent.stream(QUESTION, response_schema=schema))
        else:

            async def collect_async() -> None:
                async for event in agent.astream(QUESTION, response_schema=schema):
                    events.append(event)

            asyncio.run(collect_async())

    try:
        if answer == '{"code":"PX-1"}':
            collect()
            assert events[-1].type == "final"
            assert events[-1].response.content == answer
            assert agent.conversation_history[-1] == {
                "role": "assistant",
                "content": answer,
            }
        else:
            with pytest.raises(ProviderError, match="schema|JSON"):
                collect()
            assert not any(event.type == "final" for event in events)
            assert agent.conversation_history[-1] == {
                "role": "user",
                "content": QUESTION,
            }
            if with_tools:
                assert [event.type for event in events] == [
                    "start",
                    "model_call",
                    "model_call",
                ]
        calls = [event for event in events if event.type == "model_call"]
        assert len(calls) == (2 if with_tools else 1)
        assert [event.metadata["status"] for event in calls] == ["ok"] * len(calls)
        assert len({event.metadata["call_id"] for event in calls}) == len(calls)
        assert all(event.usage is None for event in calls)
        assert len(harness.requests) == (2 if with_tools else 1)
        assert log == ([("lookup", "Paris")] if with_tools else [])
    finally:
        agent.close()


@pytest.mark.parametrize(
    "answer",
    ['{"code":"PX-1"}', '{"code":7}', "not-json"],
    ids=["valid", "schema-mismatch", "invalid-json"],
)
def test_concrete_async_provider_stream_validates_before_committing_final(
    monkeypatch: pytest.MonkeyPatch, answer: str
) -> None:
    """Exercise native async dispatch with real OpenAI stream event translation.

    Shipped SDK adapters currently expose synchronous streams. An async shim
    retains their real wire conversion while exercising the runtime contract
    used by providers that implement astream themselves.
    """
    harness = OpenAIHarness()
    agent = build_agent(harness, monkeypatch)
    harness.responses = [harness.final_turn(answer)]

    async def astream(provider: Any, request: ModelRequest, **options: Any) -> Any:
        for event in provider.stream(request, **options):
            yield event

    monkeypatch.setattr(type(agent.provider), "astream", astream, raising=False)
    events: List[Any] = []
    schema = StructuredOutputConfig(
        schema={"type": "object", "properties": {"code": {"type": "string"}}},
        validate_locally=True,
    )

    async def collect() -> None:
        async for event in agent.astream(QUESTION, response_schema=schema):
            events.append(event)

    try:
        if answer == '{"code":"PX-1"}':
            asyncio.run(collect())
            assert events[-1].type == "final"
            assert agent.conversation_history[-1]["content"] == answer
        else:
            with pytest.raises(ProviderError, match="schema|JSON"):
                asyncio.run(collect())
            assert [event.type for event in events] == ["start", "delta", "model_call"]
            assert agent.conversation_history[-1]["role"] == "user"
        calls = [event for event in events if event.type == "model_call"]
        assert len(calls) == 1
        assert calls[0].metadata["status"] == "ok" and calls[0].usage is None
        assert len(harness.requests) == 1 and harness.requests[0]["stream"] is True
    finally:
        agent.close()
