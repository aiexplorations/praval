"""v0.8.4 release gate: wave-1 behaviours exercised together on every adapter.

One scenario per adapter, driven through ``Agent`` with fake SDK clients:

1. Round 1: the model calls ``lookup`` twice, once with invalid arguments and
   once correctly. The invalid call must never reach the handler.
2. The continuation that sends round 1's results fails once with a retryable
   error. Only that request is retried; no tool runs again.
3. Round 2: the model calls ``forecast``, which needs approval, so the run
   pauses for HITL.
4. A new agent, provider and client (a restarted process) approve and resume
   from SQLite. The final request must carry both earlier rounds in full.
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Dict, List, Tuple
from unittest.mock import patch

import pytest
from test_provider_continuation import (
    HARNESSES,
    QUESTION,
    Harness,
    _tools,
)

from praval.core.agent import Agent
from praval.core.exceptions import InterventionRequired, ProviderUnavailableError


@pytest.fixture(params=HARNESSES, ids=lambda factory: factory.name)
def harness(request: pytest.FixtureRequest) -> Harness:
    return request.param()


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch: pytest.MonkeyPatch) -> List[float]:
    delays: List[float] = []
    monkeypatch.setattr("praval.model_runtime._sleep", delays.append)
    return delays


def _failing_once(harness: Harness, fail_on_request: int) -> Callable[..., Any]:
    """Wrap ``harness.respond`` so request number ``fail_on_request`` fails once."""
    original = harness.respond
    seen = {"count": 0}

    def respond(**params: Any) -> Any:
        seen["count"] += 1
        if seen["count"] == fail_on_request:
            harness.requests.append(copy.deepcopy(params))
            raise ProviderUnavailableError("upstream overloaded", status_code=503)
        return original(**params)

    return respond


def _agent(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    db_path: str,
    log: List[Tuple[str, str]],
) -> Agent:
    provider = harness.build(monkeypatch)
    with patch(
        "praval.core.agent.ProviderFactory.create_provider", return_value=provider
    ):
        agent = Agent(
            "release-gate-agent",
            provider=harness.provider_name,
            model=harness.model,
            system_message="You answer weather questions.",
            hitl_enabled=True,
            hitl_db_path=db_path,
            config={"provider_options": dict(harness.provider_options), "retries": 2},
        )
    for tool in _tools(log):
        agent.tool(tool["function"])
    agent.tools["forecast"]["requires_approval"] = True
    agent.tools["forecast"]["approval_reason"] = "Forecasts are billed"
    return agent


def _is_error_result(entry: Tuple[Any, ...]) -> bool:
    content = entry[1]
    text = content if isinstance(content, str) else str(content)
    return entry[0] == "result" and "Error" in text and "city" in text


def test_wave_one_behaviours_hold_together(harness, monkeypatch, tmp_path, no_backoff):
    db_path = str(tmp_path / "release-gate.db")
    log: List[Tuple[str, str]] = []

    # Request 2 is the first continuation (round 1's results); it fails once.
    harness.respond = _failing_once(harness, fail_on_request=2)  # type: ignore
    first_agent = _agent(harness, monkeypatch, db_path, log)
    harness.responses = [
        harness.tool_turn([("lookup", {}), ("lookup", {"city": "Paris"})]),
        harness.tool_turn([("forecast", {"code": "PX-1"})]),
    ]

    with pytest.raises(InterventionRequired) as raised:
        first_agent.chat(QUESTION)

    # The invalid call never ran; the retry did not repeat round 1's tools.
    assert log == [("lookup", "Paris")]
    assert len(no_backoff) == 1
    assert len(harness.requests) == 3
    # The retried request is the failed one, resent unchanged.
    assert harness.transcript(harness.requests[1]) == harness.transcript(
        harness.requests[2]
    )
    round_one = harness.transcript(harness.requests[2])
    assert [entry[:2] for entry in round_one if entry[0] == "call"] == [
        ("call", "lookup"),
        ("call", "lookup"),
    ]
    results = [entry for entry in round_one if entry[0] == "result"]
    assert len(results) == 2
    assert _is_error_result(results[0])
    assert results[1] == ("result", "PX-1")

    # Restart: new provider and client; state comes back from SQLite.
    restarted = type(harness)()
    restarted._next_call = harness._next_call
    restarted.responses = [restarted.final_turn("Sunny in Paris.")]
    second_agent = _agent(restarted, monkeypatch, db_path, log)
    second_agent.approve_intervention(raised.value.intervention_id, reviewer="qa")

    answer = second_agent.resume_run(raised.value.run_id)

    assert answer == "Sunny in Paris."
    assert log == [("lookup", "Paris"), ("forecast", "PX-1")]
    assert len(restarted.requests) == 1
    final = restarted.transcript(restarted.requests[0])
    assert final[: len(round_one)] == round_one
    assert final[len(round_one) :] == [
        ("call", "forecast", {"code": "PX-1"}),
        ("result", "Sunny"),
    ]
    assert restarted.user_texts(restarted.requests[0]) == [QUESTION]


def test_failed_continuation_after_side_effect_surfaces_without_rerun(
    harness, monkeypatch, tmp_path
):
    """With retries exhausted, the error surfaces and no tool runs twice."""
    log: List[Tuple[str, str]] = []
    original = harness.respond
    calls: Dict[str, int] = {"count": 0}

    def respond(**params: Any) -> Any:
        calls["count"] += 1
        if calls["count"] > 1:
            raise ProviderUnavailableError("still overloaded", status_code=503)
        return original(**params)

    harness.respond = respond  # type: ignore[method-assign]
    agent = _agent(harness, monkeypatch, str(tmp_path / "exhausted.db"), log)
    harness.responses = [harness.tool_turn([("lookup", {"city": "Paris"})])]

    with pytest.raises(ProviderUnavailableError):
        agent.chat(QUESTION)

    assert log == [("lookup", "Paris")]
    # One initial request plus three attempts of the continuation (retries=2).
    assert calls["count"] == 4
    assert agent.conversation_history[-1] == {"role": "user", "content": QUESTION}
