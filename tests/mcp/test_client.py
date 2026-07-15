"""Unit tests for Praval's tools-only MCP client."""

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from praval import Agent
from praval.mcp import (
    MCPClient,
    MCPClientClosedError,
    MCPConnectionError,
    MCPServerConfig,
    MCPToolError,
)


class FakeSession:
    def __init__(self, *, tools=None, result=None, error=None, delay=0):
        self.tools = list(tools or [])
        self.result = result
        self.error = error
        self.delay = delay
        self.calls = []

    async def list_tools(self, cursor=None):
        return SimpleNamespace(tools=self.tools, nextCursor=None)

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.result


def stdio_config(**overrides):
    values = {
        "name": "weather",
        "transport": "stdio",
        "command": sys.executable,
    }
    values.update(overrides)
    return MCPServerConfig(**values)


def attach_session(client, session):
    client._session = session
    return client


def make_agent() -> Agent:
    """Create an Agent without relying on developer API credentials."""
    with patch("praval.core.agent.ProviderFactory.create_provider"):
        return Agent("mcp-agent", provider="fake", model="fake-model")


def test_server_config_validates_transport_and_insecure_urls():
    with pytest.raises(ValidationError, match="requires a command"):
        MCPServerConfig(name="local", transport="stdio")
    with pytest.raises(ValidationError, match="cannot include HTTP fields"):
        stdio_config(url="https://example.com/mcp")
    with pytest.raises(ValidationError, match="loopback"):
        MCPServerConfig(
            name="remote",
            transport="streamable_http",
            url="http://example.com/mcp",
        )

    loopback = MCPServerConfig(
        name="remote",
        transport="streamable_http",
        url="http://127.0.0.1:8000/mcp",
    )
    assert loopback.resolved_tool_name_prefix == "remote__"


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"name": ""}, "name cannot be empty"),
        ({"connection_timeout": 0}, "timeouts must be positive"),
        ({"max_result_size": 0}, "max_result_size must be positive"),
        ({"tool_name_prefix": ""}, "tool_name_prefix cannot be empty"),
        ({"name": "bad server"}, "letters, numbers"),
        ({"tool_name_prefix": "bad prefix"}, "letters, numbers"),
        ({"command": "bad\ncommand"}, "invalid characters"),
        ({"args": ["bad\x00arg"]}, "invalid characters"),
    ],
)
def test_stdio_config_rejects_invalid_values(overrides, message):
    with pytest.raises(ValidationError, match=message):
        stdio_config(**overrides)


def test_http_config_accepts_https_and_localhost_and_rejects_stdio_fields():
    https = MCPServerConfig(
        name="remote", transport="streamable_http", url="https://example.com/mcp"
    )
    localhost = MCPServerConfig(
        name="local", transport="streamable_http", url="http://localhost:8000/mcp"
    )
    assert https.url.startswith("https://")
    assert localhost.url.startswith("http://localhost")

    with pytest.raises(ValidationError, match="cannot include stdio fields"):
        MCPServerConfig(
            name="remote",
            transport="streamable_http",
            url="https://example.com/mcp",
            command=sys.executable,
        )
    with pytest.raises(ValidationError, match="requires a URL"):
        MCPServerConfig(name="remote", transport="streamable_http")
    with pytest.raises(ValidationError, match="embedded credentials"):
        MCPServerConfig(
            name="remote",
            transport="streamable_http",
            url="https://user:secret@example.com/mcp",
        )
    with pytest.raises(ValidationError, match="HTTPS or loopback"):
        MCPServerConfig(
            name="remote", transport="streamable_http", url="ftp://example.com/mcp"
        )


@pytest.mark.asyncio
async def test_list_tools_namespaces_schema_policy_and_annotations():
    tool = SimpleNamespace(
        name="forecast",
        description="Forecast weather",
        inputSchema={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        outputSchema={"type": "object"},
        annotations=SimpleNamespace(model_dump=lambda **kwargs: {"readOnlyHint": True}),
    )
    client = attach_session(MCPClient(stdio_config()), FakeSession(tools=[tool]))

    specs = await client.list_tools()

    assert [spec.name for spec in specs] == ["weather__forecast"]
    assert specs[0].parameters == tool.inputSchema
    assert specs[0].requires_approval is True
    assert specs[0].risk_level == "low"
    assert specs[0].metadata["mcp_tool_name"] == "forecast"
    assert specs[0].metadata["output_schema"] == {"type": "object"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tools, message",
    [
        (
            [
                SimpleNamespace(
                    name="",
                    description="",
                    inputSchema={},
                    outputSchema=None,
                    annotations=None,
                )
            ],
            "unnamed tool",
        ),
        (
            [
                SimpleNamespace(
                    name="same",
                    description="",
                    inputSchema={},
                    outputSchema=None,
                    annotations=None,
                ),
                SimpleNamespace(
                    name="same",
                    description="",
                    inputSchema={},
                    outputSchema=None,
                    annotations=None,
                ),
            ],
            "collision",
        ),
        (
            [
                SimpleNamespace(
                    name="bad",
                    description="",
                    inputSchema=object(),
                    outputSchema=None,
                    annotations=None,
                )
            ],
            "invalid input schema",
        ),
        (
            [
                SimpleNamespace(
                    name="bad.tool",
                    description="",
                    inputSchema={},
                    outputSchema=None,
                    annotations=None,
                )
            ],
            "provider compatible",
        ),
    ],
)
async def test_list_tools_rejects_invalid_discovery_results(tools, message):
    client = attach_session(MCPClient(stdio_config()), FakeSession(tools=tools))
    with pytest.raises(MCPToolError, match=message):
        await client.list_tools()


@pytest.mark.asyncio
async def test_register_tools_uses_agent_registry_and_async_handler():
    tool = SimpleNamespace(
        name="forecast",
        description="Forecast weather",
        inputSchema={"type": "object", "properties": {}},
        outputSchema=None,
        annotations=None,
    )
    result = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="sunny")],
        structuredContent=None,
        isError=False,
    )
    session = FakeSession(tools=[tool], result=result)
    client = attach_session(MCPClient(stdio_config(require_approval=False)), session)
    agent = make_agent()

    await client.register_tools(agent)
    registered = agent.tools["weather__forecast"]
    tool_result = await registered["function"]()

    assert registered["async_only"] is True
    assert registered["requires_approval"] is False
    assert tool_result.content == "sunny"
    assert session.calls == [("forecast", {})]


@pytest.mark.asyncio
async def test_register_tools_requires_agent_tool_seam():
    client = attach_session(MCPClient(stdio_config()), FakeSession())
    with pytest.raises(TypeError, match="add_tool_spec"):
        await client.register_tools(object())


@pytest.mark.asyncio
async def test_call_tool_keeps_structured_result_metadata():
    tool = SimpleNamespace(
        name="forecast",
        description="",
        inputSchema={"type": "object", "properties": {}},
        outputSchema=None,
        annotations=None,
    )
    result = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="sunny")],
        structuredContent={"temperature": 22},
        isError=False,
    )
    client = attach_session(
        MCPClient(stdio_config()), FakeSession(tools=[tool], result=result)
    )

    normalized = await client.call_tool("weather__forecast", {"city": "Pune"})

    assert normalized.content == "sunny"
    assert normalized.is_error is False
    assert normalized.metadata["structured_content"] == {"temperature": 22}


@pytest.mark.asyncio
async def test_call_tool_supports_structured_only_and_sanitized_remote_errors():
    tool = SimpleNamespace(
        name="forecast",
        description="",
        inputSchema={"type": "object", "properties": {}},
        outputSchema=None,
        annotations=SimpleNamespace(
            model_dump=lambda **kwargs: {"destructiveHint": True}
        ),
    )
    secret = "header-secret"
    result = SimpleNamespace(
        content=[],
        structuredContent={"temperature": 22},
        isError=False,
    )
    config = MCPServerConfig(
        name="remote",
        transport="streamable_http",
        url="https://example.com/mcp",
        headers={"Authorization": secret},
    )
    session = FakeSession(tools=[tool], result=result)
    client = attach_session(MCPClient(config), session)

    specs = await client.list_tools()
    structured = await client.call_tool("remote__forecast", {})
    assert specs[0].risk_level == "high"
    assert structured.content == '{"temperature":22}'

    session.result = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=f"failed with {secret}")],
        structuredContent=None,
        isError=True,
    )
    failed = await client.call_tool("remote__forecast", {})
    assert failed.is_error is True
    assert secret not in failed.content

    session.result = SimpleNamespace(
        content=[],
        structuredContent={"credential": secret},
        isError=True,
    )
    structured_error = await client.call_tool("remote__forecast", {})
    assert secret not in structured_error.content
    assert "structured_content" not in structured_error.metadata


@pytest.mark.asyncio
async def test_call_tool_rejects_unsupported_and_oversized_results():
    tool = SimpleNamespace(
        name="forecast",
        description="",
        inputSchema={"type": "object", "properties": {}},
        outputSchema=None,
        annotations=None,
    )
    session = FakeSession(
        tools=[tool],
        result=SimpleNamespace(
            content=[SimpleNamespace(type="image", data="abc")],
            structuredContent=None,
            isError=False,
        ),
    )
    client = attach_session(MCPClient(stdio_config(max_result_size=5)), session)

    unsupported = await client.call_tool("weather__forecast", {})
    assert unsupported.is_error is True
    assert "Unsupported" in unsupported.content

    session.result = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="too large")],
        structuredContent=None,
        isError=False,
    )
    oversized = await client.call_tool("weather__forecast", {})
    assert oversized.is_error is True
    assert "size limit" in oversized.content

    session.result = SimpleNamespace(
        content=[],
        structuredContent={"binary": b"abc"},
        isError=False,
    )
    binary = await client.call_tool("weather__forecast", {})
    assert binary.is_error is True
    assert "Invalid structured" in binary.content


@pytest.mark.asyncio
async def test_call_tool_timeout_and_errors_are_sanitized():
    tool = SimpleNamespace(
        name="forecast",
        description="",
        inputSchema={"type": "object", "properties": {}},
        outputSchema=None,
        annotations=None,
    )
    client = attach_session(
        MCPClient(stdio_config(tool_timeout=0.001)),
        FakeSession(tools=[tool], delay=0.02),
    )
    timeout = await client.call_tool("weather__forecast", {})
    assert timeout.is_error is True
    assert "timed out" in timeout.content

    secret = "super-secret-token"
    client = attach_session(
        MCPClient(stdio_config(env={"TOKEN": secret})),
        FakeSession(tools=[tool], error=RuntimeError(f"remote exposed {secret}")),
    )
    failed = await client.call_tool("weather__forecast", {})
    assert failed.is_error is True
    assert secret not in failed.content
    assert "***" in failed.content


@pytest.mark.asyncio
async def test_call_tool_validates_name_arguments_connection_and_cancellation():
    disconnected = MCPClient(stdio_config())
    with pytest.raises(MCPConnectionError, match="not connected"):
        await disconnected.call_tool("weather__forecast", {})

    tool = SimpleNamespace(
        name="forecast",
        description="",
        inputSchema={"type": "object", "properties": {}},
        outputSchema=None,
        annotations=None,
    )
    session = FakeSession(tools=[tool], delay=1)
    client = attach_session(MCPClient(stdio_config()), session)
    with pytest.raises(MCPToolError, match="Unknown MCP tool"):
        await client.call_tool("weather__missing", {})
    with pytest.raises(TypeError, match="dictionary"):
        await client.call_tool("weather__forecast", [])

    task = asyncio.create_task(client.call_tool("weather__forecast", {}))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_close_is_idempotent_and_rejects_later_calls():
    client = attach_session(MCPClient(stdio_config()), FakeSession())

    await client.close()
    await client.close()

    with pytest.raises(MCPClientClosedError, match="closed"):
        await client.call_tool("weather__forecast", {})
