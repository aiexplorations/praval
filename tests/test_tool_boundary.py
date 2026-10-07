"""Typed tool boundary: argument validation, typed results, response checks."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from praval import Agent
from praval.core.agent import AgentConfig
from praval.core.exceptions import (
    InterventionRequired,
    ProviderError,
    ProviderInvalidResponseError,
)
from praval.hitl.models import InterventionDecision
from praval.hitl.store import get_hitl_store
from praval.model_runtime import (
    ModelRuntime,
    _execute_legacy_tool_call_result,
    execute_legacy_tool_call,
    execute_legacy_tool_call_async,
    normalize_structured_output_config,
)
from praval.models import (
    ModelResponse,
    ProviderCapabilities,
    StructuredOutputConfig,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from praval.models.observation import (
    ExecutionObservation,
    ObservationFactStatus,
    ObservationKind,
)
from praval.runtime_observation import ObservationScope, use_observation_recorder
from praval.tool_execution import (
    _signature_validator,
    cached_schema_validator,
    tool_result,
    validate_tool_arguments,
)

ORDER_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "sku": {"type": "string"},
        "quantity": {"type": "integer"},
    },
    "required": ["sku", "quantity"],
    "additionalProperties": False,
}


class CallRecorder:
    """Typed tool handler that records every call it receives."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def add(self, x: int, y: int = 1) -> int:
        self.calls.append({"x": x, "y": y})
        return x + y


def _call(tools: List[Dict[str, Any]], name: str, args: Any) -> ToolResult:
    return _execute_legacy_tool_call_result(
        hitl_context=None,
        tool_call_id="call-1",
        function_name=name,
        raw_args=args,
        available_tools=tools,
    )


async def _acall(tools: List[Dict[str, Any]], name: str, args: Any) -> ToolResult:
    return await execute_legacy_tool_call_async(
        hitl_context=None,
        tool_call_id="call-1",
        function_name=name,
        raw_args=args,
        available_tools=tools,
    )


def _make_agent() -> Agent:
    """Create an Agent without relying on developer API credentials."""
    with patch("praval.core.agent.ProviderFactory.create_provider"):
        return Agent("boundary-agent", provider="fake", model="fake-model")


def _runtime(provider: Any) -> ModelRuntime:
    return ModelRuntime(
        provider=provider,
        provider_name="fake",
        config=AgentConfig(provider="fake", model="fake-model"),
    )


class OneToolCallProvider:
    """Requests one tool call, then answers with the tool result it received."""

    capabilities = ProviderCapabilities(tools=True, structured_outputs=True)

    def __init__(self, name: str, arguments: Dict[str, Any], answer: str = "") -> None:
        self.name = name
        self.arguments = arguments
        self.answer = answer
        self.results: List[ToolResult] = []

    def invoke(self, request: Any) -> ModelResponse:
        return ModelResponse(
            tool_calls=[ToolCall(id="call-1", name=self.name, arguments=self.arguments)]
        )

    def continue_with_tool_results(
        self, request: Any, response: ModelResponse, results: List[ToolResult]
    ) -> ModelResponse:
        self.results.extend(results)
        return ModelResponse(content=self.answer or results[0].content)


class AnswerProvider:
    """Returns a fixed final answer without tool calls."""

    capabilities = ProviderCapabilities(structured_outputs=True)

    def __init__(self, content: str) -> None:
        self.content = content

    def invoke(self, request: Any) -> ModelResponse:
        return ModelResponse(content=self.content)


# --- Python callables: pydantic validation from the signature ---


def test_invalid_python_arguments_never_call_the_handler() -> None:
    recorder = CallRecorder()
    tools = [{"name": "add", "function": recorder.add}]

    result = _call(tools, "add", {"x": "three", "z": 1})

    assert recorder.calls == []
    assert result.is_error is True
    assert result.tool_call_id == "call-1"
    assert result.name == "add"
    assert result.content.startswith("Error: Invalid arguments for tool 'add': ")
    assert "x: Input should be a valid integer" in result.content
    assert "expected int" in result.content
    assert "z: unexpected argument" in result.content


def test_missing_required_python_argument_is_named() -> None:
    recorder = CallRecorder()

    result = _call([{"name": "add", "function": recorder.add}], "add", {"y": 2})

    assert recorder.calls == []
    assert result.is_error is True
    assert "x: missing required argument, expected int" in result.content


def test_python_arguments_are_coerced_in_lax_mode() -> None:
    recorder = CallRecorder()

    result = _call(
        [{"name": "add", "function": recorder.add}], "add", '{"x": "3", "y": 4.0}'
    )

    assert result == ToolResult(tool_call_id="call-1", name="add", content="7")
    assert recorder.calls == [{"x": 3, "y": 4}]
    assert all(type(value) is int for value in recorder.calls[0].values())


def test_python_defaults_are_left_to_the_handler() -> None:
    recorder = CallRecorder()

    result = _call([{"name": "add", "function": recorder.add}], "add", {"x": 2})

    assert result.content == "3"
    assert recorder.calls == [{"x": 2, "y": 1}]


def test_var_keyword_handlers_accept_extra_arguments() -> None:
    received: Dict[str, Any] = {}

    def configure(mode: str, **options: Any) -> str:
        received.update(options, mode=mode)
        return "ok"

    result = _call([{"function": configure}], "configure", {"mode": "fast", "depth": 2})

    assert result.is_error is False
    assert received == {"mode": "fast", "depth": 2}


def test_unresolvable_annotation_skips_only_that_parameter() -> None:
    class LocalOnly:
        pass

    seen: List[Any] = []

    def lookup(item: LocalOnly, count: int) -> str:
        seen.append((item, count))
        return "ok"

    # This module uses postponed annotations, so ``LocalOnly`` is a string the
    # tool boundary cannot resolve from module globals; ``count`` still is.
    assert _call([{"function": lookup}], "lookup", {"item": "x", "count": "2"}) == (
        ToolResult(tool_call_id="call-1", name="lookup", content="ok")
    )
    assert seen == [("x", 2)]
    invalid = _call([{"function": lookup}], "lookup", {"item": "x", "count": "a"})
    assert invalid.is_error is True
    assert "count:" in invalid.content and "item" not in invalid.content
    assert len(seen) == 1


def test_malformed_json_arguments_report_missing_fields() -> None:
    recorder = CallRecorder()

    result = _call([{"name": "add", "function": recorder.add}], "add", "{not json")

    assert recorder.calls == []
    assert "x: missing required argument" in result.content


# --- JSON-Schema-only tools: jsonschema validation ---


def test_json_schema_tool_registered_through_add_tool_spec_is_validated() -> None:
    agent = _make_agent()
    calls: List[Dict[str, Any]] = []

    def place_order(**arguments: Any) -> str:
        calls.append(arguments)
        return "placed"

    agent.add_tool_spec(
        ToolSpec(name="place_order", parameters=ORDER_SCHEMA), place_order
    )
    tools = list(agent.tools.values())

    invalid = _call(tools, "place_order", {"quantity": "3", "colour": "red"})

    assert calls == []
    assert invalid.is_error is True
    assert invalid.content.startswith(
        "Error: Invalid arguments for tool 'place_order': "
    )
    assert "colour: unexpected argument" in invalid.content
    # jsonschema does not coerce: "3" stays a string and is rejected.
    assert "quantity: got string, expected integer" in invalid.content
    assert "sku: missing required argument, expected string" in invalid.content

    valid = _call(tools, "place_order", {"sku": "A1", "quantity": 3})
    assert valid.content == "placed"
    assert calls == [{"sku": "A1", "quantity": 3}]


def test_json_schema_nested_errors_name_the_path() -> None:
    schema = {
        "type": "object",
        "properties": {
            "items": {"type": "array", "items": {"type": "integer"}},
            "mode": {"enum": ["fast", "slow"]},
        },
    }

    def handler(**arguments: Any) -> str:
        raise AssertionError("handler must not run")

    tool = {"name": "batch", "function": handler, "parameters": schema}
    _, error = validate_tool_arguments(tool, {"items": [1, "two"], "mode": "medium"})

    assert error is not None
    assert "items.1: got string, expected integer" in error.content
    assert "mode: " in error.content and 'expected one of "fast", "slow"' in (
        error.content
    )


def test_json_schema_dialect_declared_by_the_schema_is_honoured() -> None:
    draft7 = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {"tags": {"type": "array", "items": [{"type": "string"}]}},
    }

    def handler(**arguments: Any) -> str:
        return "ok"

    tool = {"name": "tag", "function": handler, "parameters": draft7}

    # Draft-07 tuple validation through ``items`` as a list.
    assert validate_tool_arguments(tool, {"tags": ["a", 2]})[1] is None
    _, error = validate_tool_arguments(tool, {"tags": [1]})
    assert error is not None
    assert "tags.0: got integer, expected string" in error.content


def test_invalid_json_schema_is_skipped_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(**arguments: Any) -> str:
        return "ran"

    tool = {
        "name": "broken",
        "function": handler,
        "parameters": {"type": "object", "properties": {"a": {"type": 5}}},
    }

    with caplog.at_level(logging.WARNING, logger="praval.tool_execution"):
        assert _call([tool], "broken", {"a": 1}).content == "ran"
    assert "Invalid JSON Schema" in caplog.text


def test_legacy_type_map_with_var_keyword_handler_is_not_validated() -> None:
    def handler(**arguments: Any) -> str:
        return repr(arguments)

    tool = {
        "name": "legacy",
        "function": handler,
        "parameters": {"value": {"type": "any", "required": True}},
    }

    assert _call([tool], "legacy", {"value": 3}).content == "{'value': 3}"


# --- One result type ---


def test_handler_returned_error_tool_result_stays_an_error_in_sync() -> None:
    def lookup(query: str) -> ToolResult:
        return ToolResult(
            tool_call_id="handler-id",
            name="handler-name",
            content="lookup failed",
            is_error=True,
            metadata={"source": "test"},
        )

    provider = OneToolCallProvider("lookup", {"query": "praval"})
    response = _runtime(provider).invoke(
        messages=[{"role": "user", "content": "look up"}],
        tools=[{"function": lookup}],
    )

    assert provider.results == [
        ToolResult(
            tool_call_id="call-1",
            name="lookup",
            content="lookup failed",
            is_error=True,
            metadata={"source": "test"},
        )
    ]
    assert response.metadata["tool_results"][0]["is_error"] is True
    # The legacy string API returns the content of the same typed result.
    assert (
        execute_legacy_tool_call(
            hitl_context=None,
            tool_call_id="call-2",
            function_name="lookup",
            raw_args={"query": "x"},
            available_tools=[{"function": lookup}],
        )
        == "lookup failed"
    )


@pytest.mark.asyncio
async def test_sync_and_async_produce_identical_results() -> None:
    recorder = CallRecorder()

    async def async_add(x: int, y: int = 1) -> int:
        return x + y

    def fail(x: int) -> int:
        raise ValueError(f"bad {x}")

    sync_tools = [
        {"name": "add", "function": recorder.add},
        {"name": "fail", "function": fail},
    ]
    async_tools = [
        {"name": "add", "function": async_add},
        {"name": "fail", "function": fail},
    ]
    cases = [
        ("add", {"x": "nope"}),
        ("add", {"x": "4"}),
        ("fail", {"x": 2}),
        ("missing", {}),
    ]
    for name, args in cases:
        assert _call(sync_tools, name, args) == await _acall(async_tools, name, args)

    assert (await _acall(async_tools, "fail", {"x": 2})).content == (
        "Error: ValueError: bad 2"
    )
    assert (await _acall(async_tools, "missing", {})).is_error is True


def test_tool_result_wrapping_keeps_legacy_error_prefixes() -> None:
    assert tool_result("Error: failed", tool_call_id="a", name="t").is_error is True
    assert tool_result("Unknown function: t").is_error is True
    assert tool_result("Rejected by human reviewer: no").is_error is True
    assert tool_result({"ok": True}).content == "{'ok': True}"
    assert tool_result("fine").is_error is False


def test_runtime_invalid_arguments_reach_the_model_as_error_results() -> None:
    recorder = CallRecorder()
    provider = OneToolCallProvider("add", {"x": "lots"})

    response = _runtime(provider).invoke(
        messages=[{"role": "user", "content": "add"}],
        tools=[{"name": "add", "function": recorder.add}],
    )

    assert recorder.calls == []
    assert provider.results[0].is_error is True
    assert provider.results[0].tool_call_id == "call-1"
    assert response.content.startswith("Error: Invalid arguments for tool 'add'")


@pytest.mark.asyncio
async def test_async_only_json_schema_tool_is_validated_in_ainvoke() -> None:
    agent = _make_agent()
    calls: List[Dict[str, Any]] = []

    async def place_order(**arguments: Any) -> ToolResult:
        calls.append(arguments)
        return ToolResult(tool_call_id="mcp", name="place_order", content="placed")

    agent.add_tool_spec(
        ToolSpec(name="place_order", parameters=ORDER_SCHEMA),
        place_order,
        async_only=True,
    )
    provider = OneToolCallProvider("place_order", {"sku": "A1"})

    await _runtime(provider).ainvoke(
        messages=[{"role": "user", "content": "order"}],
        tools=list(agent.tools.values()),
    )

    assert calls == []
    assert provider.results[0].is_error is True
    assert "quantity: missing required argument" in provider.results[0].content


# --- HITL-approved calls ---


def _hitl_context(tmp_path: Path, run_id: str) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "agent_name": "boundary-agent",
        "provider_name": "fake",
        "enabled": True,
        "db_path": str(tmp_path / "hitl.sqlite3"),
    }


def _approve(tmp_path: Path, run_id: str, intervention_id: str) -> Dict[str, Any]:
    store = get_hitl_store(str(tmp_path / "hitl.sqlite3"))
    decided = store.decide_intervention(
        intervention_id=intervention_id,
        decision=InterventionDecision.APPROVE,
        reviewer="reviewer",
    )
    suspended = store.get_suspended_run(run_id)
    assert suspended is not None
    return {"state": suspended.state, "intervention": decided.to_dict()}


def test_hitl_approved_invalid_arguments_never_call_the_handler(
    tmp_path: Path,
) -> None:
    recorder = CallRecorder()
    tools = [{"name": "add", "function": recorder.add, "requires_approval": True}]
    provider = OneToolCallProvider("add", {"x": "lots"})
    runtime = _runtime(provider)
    context = _hitl_context(tmp_path, "run-sync")

    with pytest.raises(InterventionRequired) as interrupted:
        runtime.invoke(
            messages=[{"role": "user", "content": "add"}],
            tools=tools,
            hitl_context=context,
        )
    approved = _approve(tmp_path, "run-sync", interrupted.value.intervention_id)

    response = runtime.resume_tool_flow(
        approved["state"],
        tools,
        hitl_context={**context, "resume_intervention": approved["intervention"]},
    )

    assert recorder.calls == []
    assert provider.results[0].is_error is True
    assert provider.results[0].tool_call_id == "call-1"
    assert response.content.startswith("Error: Invalid arguments for tool 'add'")


@pytest.mark.asyncio
async def test_hitl_approved_invalid_arguments_async_match_sync(
    tmp_path: Path,
) -> None:
    recorder = CallRecorder()
    tools = [{"name": "add", "function": recorder.add, "requires_approval": True}]
    provider = OneToolCallProvider("add", {"x": "lots"})
    runtime = _runtime(provider)
    context = _hitl_context(tmp_path, "run-async")

    with pytest.raises(InterventionRequired) as interrupted:
        await runtime.ainvoke(
            messages=[{"role": "user", "content": "add"}],
            tools=tools,
            hitl_context=context,
        )
    approved = _approve(tmp_path, "run-async", interrupted.value.intervention_id)

    await runtime.resume_tool_flow_async(
        approved["state"],
        tools,
        hitl_context={**context, "resume_intervention": approved["intervention"]},
    )

    assert recorder.calls == []
    assert provider.results == [_call(tools[:1], "add", {"x": "lots"})]


# --- Local structured-output validation ---


def test_validate_locally_is_off_by_default() -> None:
    config = normalize_structured_output_config({"schema": ORDER_SCHEMA})
    assert config is not None and config.validate_locally is False

    response = _runtime(AnswerProvider("not json")).invoke(
        messages=[{"role": "user", "content": "x"}], response_schema=config
    )

    assert response.content == "not json"


def test_validate_locally_rejects_non_json() -> None:
    config = StructuredOutputConfig(schema=ORDER_SCHEMA, validate_locally=True)

    with pytest.raises(ProviderInvalidResponseError, match="not valid JSON"):
        _runtime(AnswerProvider("Sure! Here it is")).invoke(
            messages=[{"role": "user", "content": "x"}], response_schema=config
        )


def test_validate_locally_rejects_schema_mismatch_with_paths() -> None:
    config = normalize_structured_output_config(
        {"schema": ORDER_SCHEMA, "validate_locally": True}
    )

    with pytest.raises(ProviderInvalidResponseError) as raised:
        _runtime(AnswerProvider('{"sku": 7, "quantity": 2, "x": 1}')).invoke(
            messages=[{"role": "user", "content": "x"}], response_schema=config
        )

    message = str(raised.value)
    assert isinstance(raised.value, ProviderError)
    assert "provider 'fake' model 'fake-model'" in message
    assert "$.sku: 7 is not of type 'string'" in message
    assert "$: Additional properties are not allowed" in message


def test_validate_locally_passes_valid_output() -> None:
    config = StructuredOutputConfig(schema=ORDER_SCHEMA, validate_locally=True)

    response = _runtime(AnswerProvider('{"sku": "A1", "quantity": 2}')).invoke(
        messages=[{"role": "user", "content": "x"}], response_schema=config
    )

    assert response.content == '{"sku": "A1", "quantity": 2}'


@pytest.mark.asyncio
async def test_validate_locally_applies_to_ainvoke() -> None:
    config = StructuredOutputConfig(schema=ORDER_SCHEMA, validate_locally=True)
    runtime = _runtime(AnswerProvider('{"sku": "A1"}'))

    with pytest.raises(ProviderInvalidResponseError, match="'quantity' is a required"):
        await runtime.ainvoke(
            messages=[{"role": "user", "content": "x"}], response_schema=config
        )


def test_validate_locally_checks_the_final_answer_after_tools() -> None:
    config = StructuredOutputConfig(schema=ORDER_SCHEMA, validate_locally=True)
    recorder = CallRecorder()
    provider = OneToolCallProvider(
        "add", {"x": 1}, answer='{"sku": "A1", "quantity": 2}'
    )

    response = _runtime(provider).invoke(
        messages=[{"role": "user", "content": "x"}],
        tools=[{"name": "add", "function": recorder.add}],
        response_schema=config,
    )

    assert recorder.calls == [{"x": 1, "y": 1}]
    assert response.content == '{"sku": "A1", "quantity": 2}'


def test_validate_locally_applies_to_hitl_resume(tmp_path: Path) -> None:
    config = StructuredOutputConfig(schema=ORDER_SCHEMA, validate_locally=True)
    recorder = CallRecorder()
    tools = [{"name": "add", "function": recorder.add, "requires_approval": True}]
    provider = OneToolCallProvider("add", {"x": 1}, answer="not json")
    runtime = _runtime(provider)
    context = _hitl_context(tmp_path, "run-schema")

    with pytest.raises(InterventionRequired) as interrupted:
        runtime.invoke(
            messages=[{"role": "user", "content": "x"}],
            tools=tools,
            hitl_context=context,
            response_schema=config,
        )
    approved = _approve(tmp_path, "run-schema", interrupted.value.intervention_id)

    with pytest.raises(ProviderInvalidResponseError, match="not valid JSON"):
        runtime.resume_tool_flow(
            approved["state"],
            tools,
            hitl_context={**context, "resume_intervention": approved["intervention"]},
        )
    assert recorder.calls == [{"x": 1, "y": 1}]


# --- Observation facts and validator edge cases ---


class ObservationRecorder:
    def __init__(self) -> None:
        self.observations: List[ExecutionObservation] = []

    def record(self, observation: ExecutionObservation) -> None:
        self.observations.append(observation)


def test_observed_status_comes_from_the_typed_result() -> None:
    def lookup(query: str) -> ToolResult:
        return ToolResult(
            tool_call_id="handler-id", name="x", content="no prefix", is_error=True
        )

    recorder = CallRecorder()
    tools = [{"function": lookup}, {"name": "add", "function": recorder.add}]
    observations = ObservationRecorder()
    with use_observation_recorder(observations):
        with ObservationScope(kind=ObservationKind.AGENT, agent_id="boundary"):
            for call_id, name, args in [
                ("model-call-1", "lookup", {"query": "q"}),
                ("model-call-2", "add", {"x": "bad"}),
                ("model-call-3", "add", {"x": 1}),
            ]:
                _execute_legacy_tool_call_result(
                    hitl_context=None,
                    tool_call_id=call_id,
                    function_name=name,
                    raw_args=args,
                    available_tools=tools,
                )

    facts = observations.observations[0].tool_calls
    assert [fact.status for fact in facts] == [
        ObservationFactStatus.ERROR,
        ObservationFactStatus.ERROR,
        ObservationFactStatus.OK,
    ]
    assert [fact.tool_call_id for fact in facts] == [
        "model-call-1",
        "model-call-2",
        "model-call-3",
    ]


def test_json_schema_errors_report_received_json_types() -> None:
    schema = {
        "type": "object",
        "properties": {
            name: {"type": "string"}
            for name in ("none", "flag", "ratio", "items", "mapping", "count")
        },
    }
    schema["properties"]["either"] = {"type": ["integer", "null"]}

    def handler(**arguments: Any) -> str:
        return "ok"

    tool = {"name": "types", "function": handler, "parameters": schema}
    _, error = validate_tool_arguments(
        tool,
        {
            "none": None,
            "flag": True,
            "ratio": 1.5,
            "items": [1],
            "mapping": {"a": 1},
            "count": 2,
            "either": "x",
        },
    )

    assert error is not None
    for expected in (
        "none: got null",
        "flag: got boolean",
        "ratio: got number",
        "items: got array",
        "mapping: got object",
        "count: got integer",
        "either: got string, expected integer or null",
    ):
        assert expected in error.content


def test_long_schema_messages_are_truncated() -> None:
    schema = {
        "type": "object",
        "properties": {"code": {"type": "string", "pattern": "^[a-z]{3}$"}},
    }

    def handler(**arguments: Any) -> str:
        return "ok"

    tool = {"name": "codes", "function": handler, "parameters": schema}
    _, error = validate_tool_arguments(tool, {"code": "X" * 500})

    assert error is not None
    detail = error.content.split("code: ", 1)[1]
    assert detail.endswith("..., expected string")
    assert len(detail) < 240


def test_unserializable_schema_and_uninspectable_callables_are_not_validated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="praval.tool_execution"):
        assert cached_schema_validator({"type": "object", "default": object()}) is None
    assert "not serializable" in caplog.text

    # Builtins without an inspectable signature pass arguments through.
    tool = {"name": "max", "function": max}
    assert validate_tool_arguments(tool, {"a": 1}) == ({"a": 1}, None)


def test_signature_cache_is_weak_and_handles_methods_and_unhashables() -> None:
    first = CallRecorder()
    second = CallRecorder()
    validator = _signature_validator(first.add)
    assert validator is not None
    # Bound methods of every instance share the underlying function's entry.
    assert _signature_validator(second.add) is validator

    class Unhashable:
        __hash__ = None  # type: ignore[assignment]
        __slots__ = ()

        def __call__(self, value: int) -> int:
            return value

    handler = Unhashable()
    result = _call([{"name": "u", "function": handler}], "u", {"value": "5"})
    assert result.content == "5"
    assert _call([{"name": "u", "function": handler}], "u", {"value": "x"}).is_error
