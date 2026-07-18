"""Certify MCP stdio and Streamable HTTP through the installed Praval wheel."""

from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import time
from pathlib import Path

from support import CertificationProvider, report_dir, write_json_artifact

from praval import Agent, InterventionRequired, get_provider_registry
from praval.mcp import MCPClient, MCPServerConfig
from praval.models import ProviderProfile

SERVER = Path(__file__).with_name("mcp_server.py")


def free_port() -> int:
    """Reserve an available loopback port."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_port(port: int, timeout: float = 10) -> None:
    """Wait until the Streamable HTTP server accepts connections."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.1)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise RuntimeError("MCP Streamable HTTP server did not start")


async def certify_stdio() -> dict:
    """Discover, invoke, and close an official-SDK stdio server."""
    config = MCPServerConfig(
        name="stdio",
        transport="stdio",
        command=sys.executable,
        args=[str(SERVER)],
        require_approval=False,
    )
    async with MCPClient(config) as client:
        specs = await client.list_tools()
        text = await client.call_tool("stdio__echo", {"message": "praval"})
        structured = await client.call_tool("stdio__status", {"component": "mcp"})
        assert {spec.name for spec in specs} >= {
            "stdio__echo",
            "stdio__status",
            "stdio__slow",
        }
        assert text.content == "echo:praval"
        assert structured.metadata["structured_content"]["status"] == "ready"
    assert client.connected is False
    return {"discovery": True, "text": True, "structured": True, "closed": True}


async def certify_approval_and_timeout() -> dict:
    """Exercise MCP approval/resume and bounded timeout behavior."""
    registry = get_provider_registry()
    registry.register_provider(
        "certification-mcp-fake",
        CertificationProvider,
        default_model="certification-model",
        capabilities=CertificationProvider.capabilities,
    )
    registry.register_profile(
        ProviderProfile(
            provider="certification-mcp-fake",
            model="certification-model",
            default=True,
            capabilities=CertificationProvider.capabilities,
        )
    )
    config = MCPServerConfig(
        name="approval",
        transport="stdio",
        command=sys.executable,
        args=[str(SERVER)],
        require_approval=True,
    )
    agent = Agent(
        "mcp-approval-certification",
        provider="certification-mcp-fake",
        model="certification-model",
        hitl_enabled=True,
        hitl_db_path=str(report_dir() / "mcp-hitl.sqlite3"),
    )
    async with MCPClient(config) as client:
        specs = await client.register_tools(agent)
        assert all(spec.requires_approval for spec in specs)
        try:
            await agent.agenerate("Use the MCP echo tool with message praval.")
        except InterventionRequired as interruption:
            agent.approve_intervention(
                interruption.intervention_id, reviewer="mcp-certification"
            )
            resumed = await agent.aresume_run(interruption.run_id)
            assert "echo:2" in resumed or "echo:praval" in resumed
        else:
            raise AssertionError("MCP approval did not interrupt the async agent")

    timeout_config = MCPServerConfig(
        name="timeout",
        transport="stdio",
        command=sys.executable,
        args=[str(SERVER)],
        require_approval=False,
        tool_timeout=1.0,
    )
    async with MCPClient(timeout_config) as timeout_client:
        timeout = await timeout_client.call_tool("timeout__slow", {"seconds": 2.0})
        assert timeout.is_error and "timed out" in timeout.content
    agent.close()
    return {"approval_resume": True, "timeout": True}


async def certify_http() -> dict:
    """Discover, invoke, and close an official-SDK Streamable HTTP server."""
    port = free_port()
    process = subprocess.Popen(
        [sys.executable, str(SERVER), "http", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_for_port(port)
        config = MCPServerConfig(
            name="http",
            transport="streamable_http",
            url=f"http://127.0.0.1:{port}/mcp",
            headers={"X-Praval-Certification": "true"},
            require_approval=False,
        )
        async with MCPClient(config) as client:
            specs = await client.list_tools()
            result = await client.call_tool("http__status", {"component": "http"})
            assert {spec.name for spec in specs} >= {
                "http__echo",
                "http__status",
                "http__slow",
            }
            assert result.metadata["structured_content"] == {
                "component": "http",
                "status": "ready",
            }
        assert client.connected is False
        return {"discovery": True, "structured": True, "closed": True}
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


async def main() -> None:
    """Run both supported transports and write evidence."""
    evidence = {
        "stdio": await certify_stdio(),
        "streamable_http": await certify_http(),
        "approval_and_timeout": await certify_approval_and_timeout(),
    }
    write_json_artifact("mcp-transports.json", evidence)
    print("CERTIFIED: MCP stdio and Streamable HTTP")


if __name__ == "__main__":
    asyncio.run(main())
