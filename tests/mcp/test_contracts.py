"""Transport contract tests using the official MCP Python SDK server."""

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from praval.mcp import MCPClient, MCPServerConfig

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="the official MCP Python SDK requires Python 3.10 or newer",
)

SERVER_PATH = Path(__file__).with_name("contract_server.py")


def _free_port():
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", 0))
        except PermissionError:
            pytest.skip("host sandbox does not permit loopback socket binding")
        return sock.getsockname()[1]


def _wait_for_port(port, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.1)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise RuntimeError(f"MCP contract server did not start on port {port}")


@pytest.mark.asyncio
async def test_stdio_initialize_discover_invoke_and_shutdown():
    config = MCPServerConfig(
        name="local",
        transport="stdio",
        command=sys.executable,
        args=[str(SERVER_PATH)],
        require_approval=False,
    )

    async with MCPClient(config) as client:
        specs = await client.list_tools()
        result = await client.call_tool("local__echo", {"message": "hello"})

        assert {spec.name for spec in specs} == {"local__echo", "local__weather"}
        assert result.content == "echo:hello"
        assert result.is_error is False

    assert client.connected is False


@pytest.mark.asyncio
async def test_streamable_http_initialize_discover_invoke_and_shutdown():
    port = _free_port()
    process = subprocess.Popen(
        [sys.executable, str(SERVER_PATH), "http", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_port(port)
        config = MCPServerConfig(
            name="remote",
            transport="streamable_http",
            url=f"http://127.0.0.1:{port}/mcp",
            headers={"X-Praval-Test": "contract"},
            require_approval=False,
        )

        async with MCPClient(config) as client:
            specs = await client.list_tools()
            result = await client.call_tool("remote__weather", {"city": "Pune"})

            assert {spec.name for spec in specs} == {
                "remote__echo",
                "remote__weather",
            }
            assert result.is_error is False
            assert result.metadata["structured_content"] == {
                "city": "Pune",
                "condition": "sunny",
                "temperature": 22,
            }
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
