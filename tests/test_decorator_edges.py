"""Focused edge behavior for decorator tool discovery and error policy."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import praval.decorators as decorators
from praval.core.exceptions import ToolError
from praval.core.tool_registry import Tool, ToolMetadata


def test_decorator_error_policy_handles_callback_failure_and_unknown_value(caplog):
    error = RuntimeError("handler failed")
    callback = Mock(side_effect=RuntimeError("callback failed"))
    decorators._handle_agent_error(
        error, Mock(), "agent-a", callback, context="handler"
    )
    assert "custom error handler" in caplog.text

    decorators._handle_agent_error(
        error, Mock(), "agent-a", "unexpected", context="handler"
    )
    assert "Unknown on_error value" in caplog.text


def test_auto_register_tools_handles_untyped_parameters_and_registry_failure():
    agent = SimpleNamespace(tools={})

    def raw(value, optional="x"):
        return value

    tool = SimpleNamespace(
        func=raw,
        metadata=SimpleNamespace(
            tool_name="raw-tool",
            description="",
            requires_approval=True,
            risk_level="high",
            approval_reason="Review raw input",
        ),
    )
    registry = Mock()
    registry.get_tools_for_agent.return_value = [tool]
    with patch("praval.decorators.get_tool_registry", return_value=registry):
        decorators._auto_register_tools(agent, "agent-a")
    assert agent.tools["raw-tool"]["parameters"] == {
        "value": {"type": "any", "required": True},
        "optional": {"type": "any", "required": False},
    }

    with patch(
        "praval.decorators.get_tool_registry",
        side_effect=RuntimeError("registry failed"),
    ):
        decorators._auto_register_tools(agent, "agent-a")


def test_attach_tool_preserves_existing_definition():
    existing = {"function": Mock()}
    agent = SimpleNamespace(tools={"existing": existing})
    decorators._attach_tool(agent, "existing", Mock(), "new", {})
    assert agent.tools["existing"] is existing


def test_register_callable_tool_recovers_registry_races_and_failures():
    def decorated(value: int) -> int:
        return value

    metadata = ToolMetadata(tool_name="decorated", owned_by="agent-a")
    tool = Tool(decorated, metadata)
    decorated._praval_tool = tool
    registry = Mock()
    registry.get_tool.return_value = None
    registry.register_tool.side_effect = ToolError("already registered")
    with patch("praval.decorators.get_tool_registry", return_value=registry):
        assert decorators._register_callable_tool("agent-a", decorated) is tool

    def raw(value: int) -> int:
        return value

    existing = Mock()
    registry.reset_mock()
    registry.register_tool.side_effect = ToolError("race")
    registry.get_tool.return_value = existing
    with patch("praval.decorators.get_tool_registry", return_value=registry):
        assert decorators._register_callable_tool("agent-a", raw) is existing

    registry.register_tool.side_effect = RuntimeError("broken")
    with patch("praval.decorators.get_tool_registry", return_value=registry):
        assert decorators._register_callable_tool("agent-a", raw) is None


def test_agent_decorator_forwards_runtime_config_and_ignores_bad_tool_entries():
    underlying = Mock()
    underlying.tools = {}
    reef = Mock(default_channel="main")
    registry = Mock()
    registry.get_tools_by_category.return_value = []
    registry.get_tool.return_value = None

    def callable_tool(value: int) -> int:
        return value

    with (
        patch("praval.decorators.Agent", return_value=underlying) as agent_class,
        patch("praval.decorators.get_reef", return_value=reef),
        patch("praval.decorators.get_tool_registry", return_value=registry),
        patch("praval.decorators._register_callable_tool", return_value=None),
    ):

        @decorators.agent(
            "configured",
            provider="gemini",
            model="gemini-test",
            config={"temperature": 0.2},
            tools=["missing", callable_tool, 42],
            tool_categories=["search"],
            auto_discover_tools=False,
        )
        def configured(spore):
            return None

    assert configured._praval_name == "configured"
    agent_class.assert_called_once_with(
        name="configured",
        system_message=None,
        memory_enabled=False,
        memory_config=None,
        knowledge_base=None,
        hitl_enabled=False,
        provider="gemini",
        model="gemini-test",
        config={"temperature": 0.2},
    )


def test_error_policy_raise_reraises_original_error():
    error = ValueError("bad input")
    with pytest.raises(ValueError, match="bad input"):
        decorators._handle_agent_error(
            error, Mock(), "agent-a", "raise", context="handler"
        )
