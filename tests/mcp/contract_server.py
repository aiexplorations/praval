"""Official-SDK MCP server used by stdio and Streamable HTTP contract tests."""

import sys

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

server = FastMCP(
    "praval-contract-server",
    host="127.0.0.1",
    port=int(sys.argv[2]) if len(sys.argv) > 2 else 8000,
    stateless_http=True,
    json_response=True,
)


class WeatherResult(BaseModel):
    """Structured weather result used by the contract test."""

    city: str
    condition: str
    temperature: int


@server.tool()
def echo(message: str) -> str:
    """Echo a message."""
    return f"echo:{message}"


@server.tool()
def weather(city: str) -> WeatherResult:
    """Return structured fake weather."""
    return WeatherResult(city=city, condition="sunny", temperature=22)


if __name__ == "__main__":
    transport = (
        "streamable-http" if len(sys.argv) > 1 and sys.argv[1] == "http" else "stdio"
    )
    server.run(transport=transport)
