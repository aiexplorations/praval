"""Official-SDK server used by Praval's executable MCP demo."""

import asyncio
import sys

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

server = FastMCP(
    "praval-demo-certification",
    host="127.0.0.1",
    port=int(sys.argv[2]) if len(sys.argv) > 2 else 8000,
    stateless_http=True,
    json_response=True,
)


class Status(BaseModel):
    """Structured MCP certification response."""

    component: str
    status: str


@server.tool()
def echo(message: str) -> str:
    """Return the supplied message."""
    return f"echo:{message}"


@server.tool()
def status(component: str) -> Status:
    """Return structured component status."""
    return Status(component=component, status="ready")


@server.tool()
async def slow(seconds: float = 0.2) -> str:
    """Sleep briefly so the client timeout path is certifiable."""
    await asyncio.sleep(seconds)
    return "slow:complete"


if __name__ == "__main__":
    transport = (
        "streamable-http" if len(sys.argv) > 1 and sys.argv[1] == "http" else "stdio"
    )
    server.run(transport=transport)
