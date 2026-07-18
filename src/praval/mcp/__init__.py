"""Optional Model Context Protocol tool client support.

This submodule is intentionally not re-exported from :mod:`praval`. Install the
optional dependency with ``pip install 'praval[mcp]'`` before connecting.
"""

from .client import (
    MCPClient,
    MCPClientClosedError,
    MCPConnectionError,
    MCPError,
    MCPServerConfig,
    MCPToolError,
)

__all__ = [
    "MCPClient",
    "MCPClientClosedError",
    "MCPConnectionError",
    "MCPError",
    "MCPServerConfig",
    "MCPToolError",
]
