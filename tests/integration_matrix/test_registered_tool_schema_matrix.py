"""Registered JSON Schema declarations survive real provider request building."""

import copy
import json
from typing import Any, Dict

import pytest
from _entry_support import ENTRY_POINTS, MATRIX_HARNESSES, build_agent, run_entry
from provider_harnesses import AnthropicHarness, CohereHarness, GeminiHarness

from praval.models import ToolSpec

SCHEMA = {
    "type": "object",
    "description": "Read a file with typed options.",
    "properties": {
        "path": {"type": "string", "description": "File to read"},
        "offset": {"type": "integer", "minimum": 0},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        "enabled": {"type": "boolean"},
        "options": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["text", "lines"]},
                "weights": {"type": "array", "items": {"type": "number"}},
                "label": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            },
            "required": ["mode"],
            "additionalProperties": False,
        },
    },
    "required": ["path", "offset", "enabled"],
    "additionalProperties": False,
}


def declarations(harness: Any, request: Dict[str, Any]) -> Any:
    if isinstance(harness, GeminiHarness):
        return request["tools"][0]["functionDeclarations"]
    return [tool.get("function", tool) for tool in request["tools"]]


def assert_schema(harness: Any, declaration: Dict[str, Any], schema: Any) -> None:
    if isinstance(harness, GeminiHarness):
        assert "parameters" not in declaration
        actual = declaration["parametersJsonSchema"]
    elif isinstance(harness, AnthropicHarness):
        actual = declaration["input_schema"]
    elif isinstance(harness, CohereHarness):
        assert "parameters" not in declaration
        actual = json.loads(declaration["description"].split("Input JSON Schema: ")[1])
        definitions = declaration["parameter_definitions"]
        assert set(definitions) == set(schema.get("properties") or {})
        native_types = {
            "string": "str",
            "integer": "int",
            "boolean": "bool",
            "object": "Dict",
        }
        for name, details in (schema.get("properties") or {}).items():
            assert definitions[name]["type"] == native_types[details["type"]]
            assert definitions[name]["required"] == (name in schema.get("required", []))
    else:
        actual = declaration["parameters"]
    assert actual == schema


def reported_usage(harness: Any, response: Any) -> Any:
    if isinstance(harness, GeminiHarness):
        response["usageMetadata"] = {
            "promptTokenCount": 5,
            "candidatesTokenCount": 2,
            "totalTokenCount": 7,
        }
    elif isinstance(harness, CohereHarness):
        response.meta = {"billed_units": {"input_tokens": 5, "output_tokens": 2}}
    else:
        usage = {
            "input_tokens": 5,
            "output_tokens": 2,
            "prompt_tokens": 5,
            "completion_tokens": 2,
            "total_tokens": 7,
        }
        if isinstance(response, dict):
            response["usage"] = usage
        else:
            response.usage = usage
    return response


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
def test_add_tool_spec_schema_reaches_every_dependent_request(
    factory: Any, entry: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = factory()
    schema = copy.deepcopy(SCHEMA)
    original = copy.deepcopy(schema)
    executions = []

    def read_handler(**kwargs: Any) -> str:
        executions.append(kwargs)
        return "next.txt"

    def finish_handler(**kwargs: Any) -> str:
        assert executions == [arguments]
        assert kwargs == {"path": "next.txt"}
        return "completed"

    arguments = {
        "path": "start.txt",
        "offset": 2,
        "limit": 10,
        "enabled": True,
        "options": {"mode": "lines", "weights": [0.5, 1], "label": None},
    }
    finish_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
        "additionalProperties": False,
    }
    harness.responses = [
        reported_usage(harness, harness.tool_turn([("read_file", arguments)])),
        reported_usage(harness, harness.tool_turn([("finish", {"path": "next.txt"})])),
        reported_usage(harness, harness.final_turn("completed")),
    ]
    with build_agent(harness, monkeypatch) as agent:
        for name, parameters, handler in (
            ("read_file", schema, read_handler),
            ("finish", finish_schema, finish_handler),
        ):
            agent.add_tool_spec(
                ToolSpec(name=name, description=name, parameters=parameters), handler
            )
        text, response = run_entry(agent, entry, "Read the file, then finish.")
        assert text == "completed"
        assert executions == [arguments]
        assert len(harness.requests) == agent.usage.totals.calls == 3
        assert agent.usage.totals.total_tokens == 21
        for request in harness.requests:
            tools = declarations(harness, request)
            assert [tool["name"] for tool in tools] == ["read_file", "finish"]
            assert_schema(harness, tools[0], original)
            assert_schema(harness, tools[1], finish_schema)
        assert schema == original
        assert agent.tools["read_file"]["parameters"] == original
        if response is not None:
            assert response.metadata["usage_complete"]
            assert response.usage.total_tokens == 21
            assert all(call["usage"] for call in response.metadata["model_calls"])
            assert len(response.tool_calls) == 2
            assert all(
                not item["is_error"] for item in response.metadata["tool_results"]
            )


@pytest.mark.parametrize("factory", MATRIX_HARNESSES, ids=lambda value: value.name)
@pytest.mark.parametrize(
    "schema", [{"type": "object"}, {"type": "object", "properties": {}}]
)
def test_registered_no_argument_object_schema(
    factory: Any, schema: Dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = factory()
    harness.responses = [
        harness.tool_turn([("ping", {})]),
        harness.final_turn("pong"),
    ]
    with build_agent(harness, monkeypatch) as agent:
        agent.add_tool_spec(
            ToolSpec(name="ping", description="Ping", parameters=schema), lambda: "pong"
        )
        assert agent.generate("Ping").content == "pong"
        for request in harness.requests:
            assert_schema(harness, declarations(harness, request)[0], schema)


@pytest.mark.parametrize("factory", MATRIX_HARNESSES, ids=lambda value: value.name)
def test_registered_schema_rejects_wrong_boolean_before_handler(
    factory: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = factory()
    executions = []

    def handler(**kwargs: Any) -> str:
        executions.append(kwargs)
        return "unexpected"

    harness.responses = [
        harness.tool_turn(
            [("read_file", {"path": "start.txt", "offset": 2, "enabled": "true"})]
        ),
        harness.final_turn("rejected"),
    ]
    with build_agent(harness, monkeypatch) as agent:
        agent.add_tool_spec(
            ToolSpec(name="read_file", description="Read", parameters=SCHEMA), handler
        )
        response = agent.generate("Read")
        assert response.content == "rejected"
        assert executions == []
        result = response.metadata["tool_results"][0]
        assert result["is_error"] and "enabled" in result["content"]
        assert len(harness.requests) == 2
        for request in harness.requests:
            assert_schema(harness, declarations(harness, request)[0], SCHEMA)
