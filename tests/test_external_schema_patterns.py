"""Untrusted tool schema patterns fail safely, even on short inputs."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from praval.tool_execution import (
    MAX_PATTERN_CHARS,
    arun_tool,
    cached_schema_validator,
    run_tool,
)


def test_short_catastrophic_external_pattern_finishes_in_child_process():
    code = textwrap.dedent(
        """
        from praval.tool_execution import run_tool
        invoked = []
        def external(**kwargs):
            invoked.append(kwargs)
            return "unsafe"
        result = run_tool({"function": external, "parameters": {
            "type": "object", "properties": {
                "s": {"type": "string", "pattern": "^(a|aa)+$"}
            }
        }}, {"s": "a" * 40 + "!"})
        assert result.is_error and not invoked, result
    """
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=environment,
        capture_output=True,
        text=True,
        timeout=8,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "object", "patternProperties": {"^(a|aa)+$": {"type": "string"}}},
        {
            "type": "object",
            "patternProperties": {"^(a|aa)+$": {}},
            "additionalProperties": False,
        },
        {
            "type": "object",
            "allOf": [{"patternProperties": {"^(a|aa)+$": {}}}],
            "unevaluatedProperties": False,
        },
        {
            "type": "object",
            "$defs": {"nested": {"patternProperties": {"^(a|aa)+$": {}}}},
            "$ref": "#/$defs/nested",
        },
    ],
)
def test_external_pattern_properties_paths_rejected_without_running_handler(schema):
    invoked = []

    def handler(**kwargs):
        invoked.append(kwargs)
        return "unsafe"

    result = run_tool(
        {"function": handler, "parameters": schema}, {"a" * 40 + "!": "x"}
    )
    assert result.is_error and "patternProperties is unsupported" in result.content
    assert invoked == []


@pytest.mark.parametrize(
    "keyword", ["additionalProperties", "unevaluatedProperties", "propertyNames"]
)
def test_nested_pattern_paths_use_timeout(keyword):
    schema = {"type": "object", keyword: {"type": "string", "pattern": "^(a|aa)+$"}}
    instance = (
        {"a" * 40 + "!": "x"} if keyword == "propertyNames" else {"key": "a" * 40 + "!"}
    )
    validator = cached_schema_validator(schema, external=True)
    errors = list(validator.iter_errors(instance))
    assert errors
    if keyword == "unevaluatedProperties":
        assert "unevaluated and invalid" in errors[0].message
    else:
        assert "pattern evaluation exceeded" in errors[0].message


def test_regular_external_pattern_matching_and_default_data_are_preserved():
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string", "pattern": "^[A-Z]+$"}},
        "default": {"patternProperties": {"key": "ordinary instance data"}},
    }
    validator = cached_schema_validator(schema, external=True)
    assert not list(validator.iter_errors({"name": "ABC"}))
    assert list(validator.iter_errors({"name": "abc"}))


def test_oversized_schema_pattern_is_rejected():
    def handler(**kwargs):
        raise AssertionError("handler must not run")

    schema = {
        "type": "object",
        "properties": {"name": {"pattern": "a" * (MAX_PATTERN_CHARS + 1)}},
    }
    result = run_tool({"function": handler, "parameters": schema}, {"name": "a"})
    assert result.is_error and "pattern exceeds" in result.content


@pytest.mark.asyncio
async def test_async_external_pattern_timeout_does_not_invoke_handler():
    invoked = []

    async def handler(**kwargs):
        invoked.append(kwargs)
        return "unsafe"

    schema = {"type": "object", "properties": {"name": {"pattern": "^(a|aa)+$"}}}
    result = await arun_tool(
        {"function": handler, "parameters": schema}, {"name": "a" * 40 + "!"}
    )
    assert result.is_error and "pattern evaluation exceeded" in result.content
    assert invoked == []


def test_root_schema_dialect_preserves_timed_referenced_patterns():
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "$defs": {"value": {"pattern": "^(a|aa)+$"}},
        "properties": {"name": {"$ref": "#/$defs/value"}},
    }
    errors = list(
        cached_schema_validator(schema, external=True).iter_errors(
            {"name": "a" * 40 + "!"}
        )
    )
    assert errors and "pattern evaluation exceeded" in errors[0].message


def test_nested_schema_dialect_cannot_bypass_timed_validator():
    def handler(**kwargs):
        raise AssertionError("handler must not run")

    schema = {
        "type": "object",
        "properties": {
            "name": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "pattern": "^(a|aa)+$",
            }
        },
    }
    result = run_tool(
        {"function": handler, "parameters": schema}, {"name": "a" * 40 + "!"}
    )
    assert result.is_error and "nested $schema" in result.content
