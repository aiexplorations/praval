"""Tests for externally described tools registered on an Agent."""

from unittest.mock import patch

import pytest

from praval import Agent
from praval.core.exceptions import PravalError
from praval.models import ModelResponse, ProviderCapabilities, ToolCall, ToolSpec


def test_add_tool_spec_preserves_schema_policy_and_metadata():
    agent = Agent("external-tools")
    spec = ToolSpec(
        name="weather__lookup",
        description="Look up weather",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        strict=True,
        requires_approval=True,
        risk_level="medium",
        approval_reason="Calls an external service",
        metadata={"source": "mcp"},
    )

    async def lookup(city: str) -> str:
        return city

    agent.add_tool_spec(spec, lookup, async_only=True)

    registered = agent.tools[spec.name]
    assert registered["function"].__name__ == spec.name
    assert registered["parameters"] == spec.parameters
    assert registered["strict"] is True
    assert registered["requires_approval"] is True
    assert registered["risk_level"] == "medium"
    assert registered["approval_reason"] == "Calls an external service"
    assert registered["metadata"] == {"source": "mcp"}
    assert registered["async_only"] is True


def test_add_tool_spec_rejects_duplicate_name_and_invalid_schema():
    agent = Agent("external-tools")

    def handler(**kwargs):
        return kwargs

    spec = ToolSpec(name="external", parameters={"type": "object", "properties": {}})
    agent.add_tool_spec(spec, handler)

    with pytest.raises(ValueError, match="already registered"):
        agent.add_tool_spec(spec, handler)

    invalid = ToolSpec(name="invalid", parameters={"type": "array"})
    with pytest.raises(ValueError, match="JSON Schema object"):
        agent.add_tool_spec(invalid, handler)


def test_add_tool_spec_rejects_non_async_handler_for_async_only_tool():
    agent = Agent("external-tools")
    spec = ToolSpec(name="external")

    def handler() -> str:
        return "sync"

    with pytest.raises(ValueError, match="async handler"):
        agent.add_tool_spec(spec, handler, async_only=True)


def test_sync_agent_api_explains_how_to_run_async_only_tool(tmp_path):
    class ToolProvider:
        capabilities = ProviderCapabilities(tools=True)

        def invoke(self, request):
            return ModelResponse(
                tool_calls=[ToolCall(id="call-1", name="server__tool", arguments={})]
            )

        def continue_with_tool_results(self, request, response, results):
            return ModelResponse(content=results[0].content)

    with patch(
        "praval.core.agent.ProviderFactory.create_provider",
        return_value=ToolProvider(),
    ):
        agent = Agent(
            "external-tools",
            provider="fake",
            model="fake-model",
            hitl_db_path=str(tmp_path / "hitl.db"),
        )

    async def handler() -> str:
        return "done"

    agent.add_tool_spec(ToolSpec(name="server__tool"), handler, async_only=True)
    with pytest.raises(PravalError, match="Agent.agenerate.*Agent.astream"):
        agent.generate("call the tool")
