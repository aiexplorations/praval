"""Composed request, tool, streaming and durable HITL failure scenarios.

The fakes replace transport only. Agent, ModelRuntime, argument validation,
observation scopes, approval service and SQLite resume state remain real.
"""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from integration_matrix._failure_support import (
    Recorder,
    ScriptedProvider,
    make_agent,
    resume_agent,
    run_agent,
)

from praval.core.exceptions import (
    InterventionRequired,
    ProviderAuthenticationError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderQuotaError,
    ProviderRateLimitError,
    ProviderTransportError,
    ProviderUnavailableError,
)
from praval.hitl.service import HITLService
from praval.models import ToolResult
from praval.models.observation import ObservationKind, ObservationStatus
from praval.runtime_observation import ObservationScope, use_observation_recorder

ERRORS = [
    pytest.param(ProviderAuthenticationError, id="authentication"),
    pytest.param(ProviderInvalidRequestError, id="invalid-request"),
    pytest.param(ProviderQuotaError, id="quota"),
    pytest.param(ProviderRateLimitError, id="rate-limit"),
    pytest.param(ProviderUnavailableError, id="unavailable"),
    pytest.param(ProviderTransportError, id="transport"),
    pytest.param(RuntimeError, id="unknown-adapter"),
]
MODES = ["chat", "generate", "agenerate", "stream", "astream"]


@pytest.fixture(autouse=True)
def immediate_backoff() -> Any:
    with (
        patch("praval.model_runtime._sleep"),
        patch("praval.model_runtime._async_sleep", new=AsyncMock()),
        patch("praval.model_runtime._jitter", return_value=0.125),
    ):
        yield


def expected_error(error: Exception) -> type:
    return type(error) if isinstance(error, ProviderError) else ProviderError


def retryable(error: Exception) -> bool:
    return isinstance(error, ProviderError) and error.retryable


def assert_failure(exc: ProviderError, original: Exception, operation: str) -> None:
    assert type(exc) is expected_error(original)
    assert (exc.provider, exc.model, exc.operation) == (
        "openai",
        "gpt-4o-mini",
        operation,
    )
    assert exc.retryable == retryable(original)
    if not isinstance(original, ProviderError):
        assert exc.__cause__ is original


def assert_retry_facts(recorder: Recorder, count: int, operation: str) -> None:
    retries = [r for obs in recorder.observations for r in obs.retries]
    assert len(retries) == count
    assert [r.attempt for r in retries] == list(range(1, count + 1))
    assert all(r.operation == "model." + operation for r in retries)
    assert all(r.backoff_ms == 125.0 for r in retries)


@pytest.mark.parametrize("error_type", ERRORS)
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("phase", ["initial", "continue"])
@pytest.mark.parametrize("retries", [0, 2])
def test_agent_request_failure_isolated_from_side_effects(
    error_type: type, mode: str, phase: str, retries: int
) -> None:
    error = error_type("matrix transport failure")
    provider = ScriptedProvider(error, phase=phase)
    agent = make_agent(provider, retries=retries)
    writes = []

    def write(value: int) -> str:
        writes.append(value)
        return "written"

    agent.tools["write"] = {"function": write}
    recorder = Recorder()
    recovered = retryable(error) and retries > 0
    operation = "invoke" if phase == "initial" else "continue"
    try:
        with use_observation_recorder(recorder):
            if recovered:
                result = run_agent(agent, mode)
                content = (
                    result[-1].response.content
                    if isinstance(result, list)
                    else result if isinstance(result, str) else result.content
                )
                assert content == "done"
            else:
                with pytest.raises(ProviderError) as caught:
                    run_agent(agent, mode)
                assert_failure(caught.value, error, operation)
        assert len(provider.initial) == (2 if recovered and phase == "initial" else 1)
        assert len(provider.continuations) == (
            (2 if recovered and phase == "continue" else 1)
            if phase == "continue" or recovered
            else 0
        )
        assert writes == ([3] if phase == "continue" or recovered else [])
        assert_retry_facts(recorder, int(recovered), operation)
        assert len(recorder.observations) == 1
        assert recorder.observations[0].status is (
            ObservationStatus.OK if recovered else ObservationStatus.ERROR
        )
        assert recorder.observations[0].error_type == (
            None if recovered else expected_error(error).__name__
        )
        history = agent.conversation_history
        assert [entry["role"] for entry in history] == (
            ["user", "assistant"] if recovered else ["user"]
        )
        if recovered:
            assert history[-1]["content"] == "done"
        requests = provider.initial
        if len(requests) == 2:
            assert requests[0] == requests[1]
        if len(provider.continuations) == 2:
            assert provider.continuations[0] == provider.continuations[1]
    finally:
        agent.close()


@pytest.mark.parametrize("error_type", ERRORS)
@pytest.mark.parametrize("mode", ["stream", "astream"])
@pytest.mark.parametrize("phase", ["before", "midstream"])
@pytest.mark.parametrize("retries", [0, 2])
def test_native_stream_failure_obeys_visible_event_boundary(
    error_type: type, mode: str, phase: str, retries: int
) -> None:
    error = error_type("stream interrupted")
    provider = ScriptedProvider(error, phase=phase)
    agent = make_agent(provider, retries=retries)
    recorder = Recorder()
    recovered = phase == "before" and retryable(error) and retries > 0
    visible_events = []
    try:
        with use_observation_recorder(recorder):
            if recovered:
                events = run_agent(agent, mode, visible_events)
                assert [e.type for e in events] == ["start", "delta", "final"]
                assert events[1].delta == "partial"
            else:
                with pytest.raises(ProviderError) as caught:
                    run_agent(agent, mode, visible_events)
                assert_failure(caught.value, error, "stream")
        assert len(provider.streams) == 1 + int(recovered)
        assert provider.initial == provider.continuations == []
        assert_retry_facts(recorder, int(recovered), "stream")
        assert [event.type for event in visible_events] == (
            ["start", "delta", "final"]
            if recovered
            else ["start", "delta"] if phase == "midstream" else ["start"]
        )
        assert len(recorder.observations) == 1
        assert recorder.observations[0].status is (
            ObservationStatus.OK if recovered else ObservationStatus.ERROR
        )
        assert [e["role"] for e in agent.conversation_history] == (
            ["user", "assistant"] if recovered else ["user"]
        )
    finally:
        agent.close()


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("failure", ["handler", "typed-result", "invalid", "coerced"])
def test_tool_boundary_failure_reaches_provider_once(mode: str, failure: str) -> None:
    provider = ScriptedProvider(RuntimeError("unused"), phase="none")
    if failure == "invalid":
        provider.arguments = {"value": "not-an-integer"}
    elif failure == "coerced":
        provider.arguments = {"value": "3"}
    writes = []

    def write(value: int) -> Any:
        writes.append((value, type(value)))
        if failure == "handler":
            raise ValueError("tool exploded")
        if failure == "typed-result":
            return ToolResult(
                tool_call_id="ignored",
                name="ignored",
                content="tool refused",
                is_error=True,
            )
        return "written"

    agent = make_agent(provider, retries=2)
    agent.tools["write"] = {"function": write}
    recorder = Recorder()
    try:
        with use_observation_recorder(recorder):
            run_agent(agent, mode)
        assert len(provider.initial) == len(provider.continuations) == 1
        result = provider.continuations[0][2][0]
        assert result["tool_call_id"] == "write-1"
        assert result["is_error"] is (failure != "coerced")
        assert writes == ([] if failure == "invalid" else [(3, int)])
        if failure == "handler":
            assert result["content"] == "Error: ValueError: tool exploded"
        if failure == "typed-result":
            assert result["content"] == "tool refused"
        if failure == "invalid":
            assert "value" in result["content"]
        assert_retry_facts(recorder, 0, "continue")
    finally:
        agent.close()


@pytest.mark.parametrize("error_type", ERRORS)
@pytest.mark.parametrize("use_async", [False, True])
@pytest.mark.parametrize("retries", [0, 2])
def test_hitl_failed_resume_reuses_durable_completed_result(
    tmp_path: Any, error_type: type, use_async: bool, retries: int
) -> None:
    error = error_type("resume continuation failed")
    provider = ScriptedProvider(error, phase="continue")
    writes = []

    def write(value: int) -> str:
        writes.append(value)
        return "written"

    agent = make_agent(
        provider,
        retries=retries,
        hitl_enabled=True,
        hitl_db_path=str(tmp_path / "resume.db"),
    )
    agent.tools["write"] = {"function": write, "requires_approval": True}
    try:
        with pytest.raises(InterventionRequired) as pause:
            run_agent(agent, "agenerate" if use_async else "generate")
        run_id = pause.value.run_id
        service = HITLService(db_path=str(tmp_path / "resume.db"))
        service.approve_intervention(pause.value.intervention_id, reviewer="matrix")
        recovered = retryable(error) and retries > 0
        recorder = Recorder()
        with use_observation_recorder(recorder):
            with ObservationScope(kind=ObservationKind.AGENT, agent_name="resume"):
                if recovered:
                    assert resume_agent(agent, run_id, use_async) == "done"
                else:
                    with pytest.raises(ProviderError) as caught:
                        resume_agent(agent, run_id, use_async)
                    assert_failure(caught.value, error, "continue")
        assert writes == [3]
        stored = service.get_suspended_run(run_id)
        assert stored.status == ("completed" if recovered else "pending")
        # Serialize through JSON and re-read from SQLite, as a restart would.
        assert json.loads(json.dumps(stored.state)) == stored.state
        if not recovered:
            assert resume_agent(agent, run_id, use_async) == "done"
        assert writes == [3]
        assert len(provider.initial) == 1
        assert len(provider.continuations) == 2
        assert provider.continuations[0] == provider.continuations[1]
        assert_retry_facts(recorder, int(recovered), "continue")
        assert service.get_suspended_run(run_id).status == "completed"
        assert agent.conversation_history[-1] == {
            "role": "assistant",
            "content": "done",
        }
    finally:
        agent.close()


@pytest.mark.parametrize(
    "error_type",
    [ProviderRateLimitError, ProviderUnavailableError, ProviderTransportError],
)
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("retries", [1, 2])
def test_exhausted_retry_budget_never_reexecutes_handler(
    error_type: type, mode: str, retries: int
) -> None:
    error = error_type("persistent outage")
    provider = ScriptedProvider(error, phase="continue", failures=10)
    writes = []

    def write(value: int) -> str:
        writes.append(value)
        return "written"

    agent = make_agent(provider, retries=retries)
    agent.tools["write"] = {"function": write}
    recorder = Recorder()
    try:
        with use_observation_recorder(recorder):
            with pytest.raises(ProviderError) as caught:
                run_agent(agent, mode)
        assert_failure(caught.value, error, "continue")
        assert len(provider.initial) == 1
        assert len(provider.continuations) == retries + 1
        assert writes == [3]
        assert all(c == provider.continuations[0] for c in provider.continuations)
        assert_retry_facts(recorder, retries, "continue")
        assert agent.conversation_history == [{"role": "user", "content": "write once"}]
    finally:
        agent.close()


@pytest.mark.parametrize("use_async", [False, True])
@pytest.mark.parametrize("legacy_state", [False, True])
def test_hitl_old_state_and_new_runtime_resume(
    tmp_path: Any, use_async: bool, legacy_state: bool
) -> None:
    """Old runtime-v1 state without transcript or saved results is resumable."""
    provider = ScriptedProvider(ProviderUnavailableError("once"), phase="continue")
    writes = []

    def write(value: int) -> str:
        writes.append(value)
        return "written"

    options = dict(hitl_enabled=True, hitl_db_path=str(tmp_path / "restart.db"))
    agent = make_agent(provider, retries=0, **options)
    tools = {"write": {"function": write, "requires_approval": True}}
    agent.tools.update(tools)
    service = HITLService(db_path=options["hitl_db_path"])
    try:
        with pytest.raises(InterventionRequired) as pause:
            run_agent(agent, "agenerate" if use_async else "generate")
        run_id = pause.value.run_id
        service.approve_intervention(pause.value.intervention_id, reviewer="matrix")
        if legacy_state:
            stored = service.get_suspended_run(run_id)
            state = json.loads(json.dumps(stored.state))
            state["response"].pop("metadata", None)
            state.pop("resume_results", None)
            assert service.store.update_suspended_run_state(
                run_id, state, expected_status="pending"
            )
        with pytest.raises(ProviderUnavailableError):
            resume_agent(agent, run_id, use_async)
        assert writes == [3]
        assert service.get_suspended_run(run_id).status == "pending"
        agent.close()
        replacement = make_agent(provider, retries=0, **options)
        replacement.tools.update(tools)
        try:
            assert resume_agent(replacement, run_id, use_async) == "done"
            assert writes == [3]
            assert service.get_suspended_run(run_id).status == "completed"
            assert provider.continuations[0] == provider.continuations[1]
        finally:
            replacement.close()
    finally:
        agent.close()


@pytest.mark.parametrize("use_async", [False, True])
@pytest.mark.xfail(
    strict=True,
    reason=(
        "Durable HITL resume caches only the interrupted round. A later round's "
        "completed side effect is rerun when its continuation fails and resume "
        "is retried."
    ),
)
def test_hitl_later_round_failure_must_not_duplicate_effects(
    tmp_path: Any, use_async: bool
) -> None:
    provider = ScriptedProvider(ProviderUnavailableError("later failed"), phase="later")
    provider.second_round = True
    writes = []

    def write(value: int) -> str:
        writes.append(("approved", value))
        return "written"

    def later() -> str:
        writes.append(("later", 1))
        return "written later"

    agent = make_agent(
        provider, retries=0, hitl_enabled=True, hitl_db_path=str(tmp_path / "later.db")
    )
    agent.tools.update(
        {
            "write": {"function": write, "requires_approval": True},
            "later": {"function": later},
        }
    )
    try:
        with pytest.raises(InterventionRequired) as pause:
            run_agent(agent, "agenerate" if use_async else "generate")
        service = HITLService(db_path=str(tmp_path / "later.db"))
        service.approve_intervention(pause.value.intervention_id, reviewer="matrix")
        with pytest.raises(ProviderUnavailableError):
            resume_agent(agent, pause.value.run_id, use_async)
        assert writes == [("approved", 3), ("later", 1)]
        assert service.get_suspended_run(pause.value.run_id).status == "pending"
        assert resume_agent(agent, pause.value.run_id, use_async) == "done"
        assert service.get_suspended_run(pause.value.run_id).status == "completed"
        # This assertion must remain strong: the current code runs later twice.
        assert writes == [("approved", 3), ("later", 1)]
    finally:
        agent.close()


@pytest.mark.parametrize("use_async", [False, True])
@pytest.mark.parametrize("handler_kind", ["kwargs", "raw"])
@pytest.mark.parametrize("raw_args", ["not-json", "[1, 2]", "42"])
def test_hitl_malformed_arguments_must_not_invoke_schema_free_handler(
    tmp_path: Any, use_async: bool, handler_kind: str, raw_args: str
) -> None:
    import asyncio

    from praval.hitl.runtime import HITLRuntime

    writes = []

    def kwargs_handler(**kwargs: Any) -> str:
        writes.append(kwargs)
        return "executed malformed input"

    def raw_handler(raw: Any) -> str:
        writes.append(raw)
        return "executed malformed input"

    function = kwargs_handler if handler_kind == "kwargs" else raw_handler
    tools = [{"function": function, "requires_approval": True}]
    runtime = HITLRuntime(
        run_id="malformed",
        agent_name="failure-matrix",
        provider_name="openai",
        hitl_enabled=True,
        db_path=str(tmp_path / "malformed.db"),
    )
    with pytest.raises(InterventionRequired) as pause:
        runtime.execute_or_interrupt_result(
            tool_call_id="malformed-1",
            function_name=function.__name__,
            raw_args=raw_args,
            available_tools=tools,
            continuation_state={},
        )
    assert writes == []
    service = HITLService(db_path=str(tmp_path / "malformed.db"))
    approved = service.approve_intervention(
        pause.value.intervention_id, reviewer="matrix"
    )
    if use_async:
        result = asyncio.run(
            runtime.execute_with_decision_async(
                intervention=approved, available_tools=tools
            )
        )
    else:
        result = runtime.execute_with_decision_result(
            intervention=approved, available_tools=tools
        )
    assert writes == []
    assert result.is_error is True


@pytest.mark.parametrize("use_async", [False, True])
@pytest.mark.parametrize("requires_approval", [False, True])
@pytest.mark.parametrize(
    "raw_args", [None, "", "  ", "{}", {"raw": "not-json"}, '{"raw": "not-json"}']
)
def test_hitl_valid_objects_and_empty_arguments_preserve_handlers(
    tmp_path: Any, use_async: bool, requires_approval: bool, raw_args: Any
) -> None:
    import asyncio

    from praval.hitl.runtime import HITLRuntime

    writes = []

    def handler(**kwargs: Any) -> str:
        writes.append(kwargs)
        return "valid"

    tools = [{"function": handler, "requires_approval": requires_approval}]
    runtime = HITLRuntime(
        run_id="valid",
        agent_name="failure-matrix",
        provider_name="openai",
        hitl_enabled=True,
        db_path=str(tmp_path / "valid.db"),
    )
    kwargs = dict(
        tool_call_id="valid-1",
        function_name="handler",
        raw_args=raw_args,
        available_tools=tools,
        continuation_state={},
    )
    if requires_approval:
        with pytest.raises(InterventionRequired) as pause:
            runtime.execute_or_interrupt_result(**kwargs)
        service = HITLService(db_path=str(tmp_path / "valid.db"))
        approved = service.approve_intervention(
            pause.value.intervention_id, reviewer="matrix"
        )
        # Dict serialization must preserve argument validity provenance.
        decision_args = dict(intervention=approved.to_dict(), available_tools=tools)
        if use_async:
            result = asyncio.run(runtime.execute_with_decision_async(**decision_args))
        else:
            result = runtime.execute_with_decision_result(**decision_args)
    elif use_async:
        result = asyncio.run(runtime.execute_or_interrupt_async(**kwargs))
    else:
        result = runtime.execute_or_interrupt_result(**kwargs)
    expected = (
        {"raw": "not-json"}
        if raw_args in ({"raw": "not-json"}, '{"raw": "not-json"}')
        else {}
    )
    assert writes == [expected]
    assert result.content == "valid"
    assert result.is_error is False


@pytest.mark.parametrize("use_async", [False, True])
def test_hitl_edited_malformed_arguments_can_be_repaired(
    tmp_path: Any, use_async: bool
) -> None:
    import asyncio

    from praval.hitl.runtime import HITLRuntime

    writes = []

    def handler(**kwargs: Any) -> str:
        writes.append(kwargs)
        return "repaired"

    tools = [{"function": handler, "requires_approval": True}]
    runtime = HITLRuntime(
        run_id="edited",
        agent_name="failure-matrix",
        provider_name="openai",
        hitl_enabled=True,
        db_path=str(tmp_path / "edited.db"),
    )
    with pytest.raises(InterventionRequired) as pause:
        runtime.execute_or_interrupt_result(
            tool_call_id="bad-1",
            function_name="handler",
            raw_args="not-json",
            available_tools=tools,
            continuation_state={},
        )
    service = HITLService(db_path=str(tmp_path / "edited.db"))
    edited = service.approve_intervention(
        pause.value.intervention_id, reviewer="matrix", edited_args={"value": 3}
    )
    options = dict(intervention=edited.to_dict(), available_tools=tools)
    if use_async:
        result = asyncio.run(runtime.execute_with_decision_async(**options))
    else:
        result = runtime.execute_with_decision_result(**options)
    assert writes == [{"value": 3}]
    assert result.content == "repaired"
    assert result.is_error is False
