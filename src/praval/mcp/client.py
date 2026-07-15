"""Tools-only MCP client integration for Praval agents."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
import uuid
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..models import ToolResult, ToolSpec
from ..observability.tracing import SpanKind, get_tracer

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RESULT_SIZE = 1024 * 1024
TOOL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
MAX_TOOL_NAME_LENGTH = 64


class MCPError(RuntimeError):
    """Base error for Praval MCP client operations."""


class MCPConnectionError(MCPError):
    """Raised when an MCP connection cannot be established."""


class MCPClientClosedError(MCPError):
    """Raised when an MCP operation is attempted after closure."""


class MCPToolError(MCPError):
    """Raised for invalid MCP tool discovery or registration state."""


class MCPServerConfig(BaseModel):
    """Configuration for one stdio or Streamable HTTP MCP server."""

    model_config = ConfigDict(frozen=True)

    name: str
    transport: Literal["stdio", "streamable_http"]
    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    env: Optional[Dict[str, str]] = None
    cwd: Optional[Path] = None
    url: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    connection_timeout: float = DEFAULT_TIMEOUT_SECONDS
    tool_timeout: float = DEFAULT_TIMEOUT_SECONDS
    tool_name_prefix: Optional[str] = None
    require_approval: bool = True
    max_result_size: int = DEFAULT_MAX_RESULT_SIZE

    @model_validator(mode="after")
    def validate_transport(self) -> "MCPServerConfig":
        """Validate mutually exclusive transport settings and URL security."""
        if not self.name or not self.name.strip():
            raise ValueError("MCP server name cannot be empty")
        if not TOOL_NAME_PATTERN.fullmatch(self.name):
            raise ValueError(
                "MCP server name may contain only letters, numbers, underscores, "
                "and hyphens"
            )
        if self.connection_timeout <= 0 or self.tool_timeout <= 0:
            raise ValueError("MCP timeouts must be positive")
        if self.max_result_size <= 0:
            raise ValueError("MCP max_result_size must be positive")

        prefix = self.tool_name_prefix
        if prefix is not None:
            if not prefix:
                raise ValueError("MCP tool_name_prefix cannot be empty")
            if not TOOL_NAME_PATTERN.fullmatch(prefix):
                raise ValueError(
                    "MCP tool_name_prefix may contain only letters, numbers, "
                    "underscores, and hyphens"
                )

        if self.transport == "stdio":
            if not self.command:
                raise ValueError("stdio MCP configuration requires a command")
            if self.url or self.headers:
                raise ValueError("stdio MCP configuration cannot include HTTP fields")
            if "\x00" in self.command or "\n" in self.command:
                raise ValueError("stdio MCP command contains invalid characters")
            if any("\x00" in arg for arg in self.args):
                raise ValueError("stdio MCP argument contains invalid characters")
        else:
            if not self.url:
                raise ValueError("Streamable HTTP MCP configuration requires a URL")
            if self.command or self.args or self.env or self.cwd:
                raise ValueError(
                    "Streamable HTTP MCP configuration cannot include stdio fields"
                )
            self._validate_remote_url(self.url)
        return self

    @property
    def resolved_tool_name_prefix(self) -> str:
        """Return the configured namespace prefix or the server-name default."""
        return self.tool_name_prefix or f"{self.name}__"

    @staticmethod
    def _validate_remote_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("MCP HTTP URL cannot contain embedded credentials")
        if parsed.scheme == "https" and parsed.hostname:
            return
        if parsed.scheme != "http" or not parsed.hostname:
            raise ValueError("MCP HTTP URL must use HTTPS or loopback HTTP")
        host = parsed.hostname.lower()
        if host == "localhost":
            return
        try:
            if ipaddress.ip_address(host).is_loopback:
                return
        except ValueError:
            pass
        raise ValueError("Insecure MCP HTTP URLs are limited to loopback hosts")


class MCPClient:
    """Async tools-only MCP client with bounded execution and cleanup."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._stack: Optional[AsyncExitStack] = None
        self._session: Any = None
        self._initialize_result: Any = None
        self._tool_names: Dict[str, str] = {}
        self._closed = False

    async def __aenter__(self) -> "MCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    @property
    def connected(self) -> bool:
        """Return whether the MCP session is active."""
        return self._session is not None and not self._closed

    async def connect(self) -> None:
        """Connect and initialize the configured MCP server exactly once."""
        if self._closed:
            raise MCPClientClosedError(
                f"MCP client for server '{self.config.name}' is closed"
            )
        if self._session is not None:
            return

        stack = AsyncExitStack()
        try:
            sdk = self._load_sdk()
            async with self._timeout_scope(self.config.connection_timeout):
                streams = await self._enter_transport(stack, sdk)
            read_stream, write_stream = streams[0], streams[1]
            session = sdk["ClientSession"](
                read_stream,
                write_stream,
                read_timeout_seconds=timedelta(seconds=self.config.tool_timeout),
            )
            async with self._timeout_scope(self.config.connection_timeout):
                await stack.enter_async_context(session)
            initialized = await asyncio.wait_for(
                session.initialize(), timeout=self.config.connection_timeout
            )
            capabilities = getattr(initialized, "capabilities", None)
            if capabilities is None or getattr(capabilities, "tools", None) is None:
                raise MCPConnectionError(
                    f"MCP server '{self.config.name}' does not support tools"
                )
            self._stack = stack
            self._session = session
            self._initialize_result = initialized
        except asyncio.CancelledError:
            await stack.aclose()
            raise
        except Exception as exc:
            await stack.aclose()
            if isinstance(exc, MCPConnectionError):
                raise
            logger.warning("Failed to connect to MCP server '%s'", self.config.name)
            raise MCPConnectionError(
                f"Failed to connect to MCP server '{self.config.name}'"
            ) from None

    async def close(self) -> None:
        """Close the MCP session and any stdio process; safe to call twice."""
        if self._closed:
            return
        self._closed = True
        stack, self._stack = self._stack, None
        self._session = None
        self._initialize_result = None
        self._tool_names.clear()
        if stack is not None:
            await stack.aclose()

    async def list_tools(self) -> List[ToolSpec]:
        """Discover MCP tools and convert their schemas to Praval ToolSpecs."""
        session = self._require_session()
        discovered: List[ToolSpec] = []
        names: Dict[str, str] = {}
        cursor: Optional[str] = None

        while True:
            result = await asyncio.wait_for(
                session.list_tools(cursor=cursor),
                timeout=self.config.tool_timeout,
            )
            for tool in getattr(result, "tools", []):
                remote_name = str(getattr(tool, "name", "") or "")
                if not remote_name:
                    raise MCPToolError(
                        f"MCP server '{self.config.name}' returned an unnamed tool"
                    )
                public_name = f"{self.config.resolved_tool_name_prefix}{remote_name}"
                if len(
                    public_name
                ) > MAX_TOOL_NAME_LENGTH or not TOOL_NAME_PATTERN.fullmatch(
                    public_name
                ):
                    raise MCPToolError(
                        f"MCP tool name '{public_name}' is not provider compatible"
                    )
                if public_name in names:
                    raise MCPToolError(f"MCP tool name collision for '{public_name}'")
                schema = self._model_value(tool, "inputSchema", "input_schema") or {}
                if not isinstance(schema, dict):
                    raise MCPToolError(
                        f"MCP tool '{public_name}' returned an invalid input schema"
                    )
                annotations = self._json_value(getattr(tool, "annotations", None))
                output_schema = self._model_value(tool, "outputSchema", "output_schema")
                names[public_name] = remote_name
                discovered.append(
                    ToolSpec(
                        name=public_name,
                        description=str(getattr(tool, "description", "") or ""),
                        parameters=schema,
                        requires_approval=self.config.require_approval,
                        risk_level=self._risk_level(annotations),
                        approval_reason=(
                            f"Execute tool '{remote_name}' on MCP server "
                            f"'{self.config.name}'"
                            if self.config.require_approval
                            else ""
                        ),
                        metadata={
                            "source": "mcp",
                            "mcp_server": self.config.name,
                            "mcp_tool_name": remote_name,
                            "mcp_transport": self.config.transport,
                            "annotations": annotations,
                            "output_schema": output_schema,
                        },
                    )
                )
            cursor = getattr(result, "nextCursor", None) or getattr(
                result, "next_cursor", None
            )
            if not cursor:
                break

        self._tool_names = names
        return discovered

    async def register_tools(self, agent: Any) -> List[ToolSpec]:
        """Discover tools and register async handlers on an Agent."""
        if not callable(getattr(agent, "add_tool_spec", None)):
            raise TypeError("agent must provide add_tool_spec()")
        specs = await self.list_tools()
        for spec in specs:

            async def handler(
                _tool_name: str = spec.name, **arguments: Any
            ) -> ToolResult:
                return await self.call_tool(_tool_name, arguments)

            agent.add_tool_spec(spec, handler, async_only=True)
        return specs

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a discovered MCP tool and normalize its supported content."""
        session = self._require_session()
        if name not in self._tool_names:
            await self.list_tools()
        remote_name = self._tool_names.get(name)
        if remote_name is None:
            raise MCPToolError(f"Unknown MCP tool '{name}'")
        if not isinstance(arguments, dict):
            raise TypeError("MCP tool arguments must be a dictionary")

        tracer = get_tracer()
        with tracer.start_as_current_span(
            f"mcp.{self.config.name}.call_tool",
            kind=SpanKind.CLIENT,
            attributes={"mcp.server": self.config.name, "mcp.tool": remote_name},
        ) as span:
            try:
                result = await asyncio.wait_for(
                    session.call_tool(remote_name, arguments),
                    timeout=self.config.tool_timeout,
                )
                normalized = self._normalize_result(name, result)
                span.set_status("error" if normalized.is_error else "ok")
                return normalized
            except asyncio.CancelledError:
                span.set_status("error", "cancelled")
                raise
            except asyncio.TimeoutError:
                span.set_status("error", "timeout")
                return self._error_result(name, "MCP tool call timed out")
            except Exception as exc:
                span.set_status("error", type(exc).__name__)
                return self._error_result(
                    name,
                    f"MCP tool call failed: {self._sanitize_error(str(exc))}",
                )

    def _normalize_result(self, name: str, result: Any) -> ToolResult:
        text_blocks: List[str] = []
        for block in getattr(result, "content", []) or []:
            block_type = str(getattr(block, "type", "") or "")
            if block_type != "text":
                return self._error_result(
                    name,
                    f"Unsupported MCP result content type: {block_type or 'unknown'}",
                )
            text_blocks.append(str(getattr(block, "text", "") or ""))

        structured = getattr(result, "structuredContent", None)
        if structured is None:
            structured = getattr(result, "structured_content", None)
        structured_json: Optional[str] = None
        structured_value: Any = None
        if structured is not None:
            try:
                structured_value = self._structured_value(structured)
                structured_json = json.dumps(
                    structured_value,
                    allow_nan=False,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            except (TypeError, ValueError):
                return self._error_result(name, "Invalid structured MCP tool result")

        content = "\n".join(text_blocks)
        if not content and structured_json is not None:
            content = structured_json
        normalized_size = len(content.encode("utf-8"))
        if structured_json is not None and structured_json != content:
            normalized_size += len(structured_json.encode("utf-8"))
        if normalized_size > self.config.max_result_size:
            return self._error_result(name, "MCP tool result exceeded the size limit")

        is_error = bool(
            getattr(result, "isError", False) or getattr(result, "is_error", False)
        )
        if is_error:
            content = self._sanitize_error(content) or "MCP tool returned an error"
        metadata: Dict[str, Any] = {
            "mcp_server": self.config.name,
            "mcp_tool_name": self._tool_names.get(name, name),
        }
        if structured is not None and not is_error:
            metadata["structured_content"] = structured_value
        return ToolResult(
            tool_call_id=f"mcp-{uuid.uuid4()}",
            name=name,
            content=content,
            is_error=is_error,
            metadata=metadata,
        )

    def _error_result(self, name: str, message: str) -> ToolResult:
        return ToolResult(
            tool_call_id=f"mcp-{uuid.uuid4()}",
            name=name,
            content=self._sanitize_error(message),
            is_error=True,
            metadata={"mcp_server": self.config.name},
        )

    def _require_session(self) -> Any:
        if self._closed:
            raise MCPClientClosedError(
                f"MCP client for server '{self.config.name}' is closed"
            )
        if self._session is None:
            raise MCPConnectionError(
                f"MCP client for server '{self.config.name}' is not connected"
            )
        return self._session

    async def _enter_transport(self, stack: AsyncExitStack, sdk: Dict[str, Any]) -> Any:
        if self.config.transport == "stdio":
            parameters = sdk["StdioServerParameters"](
                command=self.config.command,
                args=list(self.config.args),
                env=dict(self.config.env) if self.config.env is not None else None,
                cwd=self.config.cwd,
            )
            return await stack.enter_async_context(sdk["stdio_client"](parameters))
        timeout = sdk["httpx"].Timeout(
            self.config.tool_timeout,
            connect=self.config.connection_timeout,
        )
        http_client = sdk["create_mcp_http_client"](
            headers=dict(self.config.headers),
            timeout=timeout,
        )
        await stack.enter_async_context(http_client)
        return await stack.enter_async_context(
            sdk["streamable_http_client"](
                self.config.url,
                http_client=http_client,
            )
        )

    @staticmethod
    def _load_sdk() -> Dict[str, Any]:
        try:
            import httpx
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            from mcp.client.streamable_http import streamable_http_client
            from mcp.shared._httpx_utils import create_mcp_http_client
        except ImportError:
            raise MCPConnectionError(
                "MCP support requires the optional dependency: "
                "pip install 'praval[mcp]'"
            ) from None
        return {
            "ClientSession": ClientSession,
            "StdioServerParameters": StdioServerParameters,
            "stdio_client": stdio_client,
            "streamable_http_client": streamable_http_client,
            "create_mcp_http_client": create_mcp_http_client,
            "httpx": httpx,
        }

    @staticmethod
    @asynccontextmanager
    async def _timeout_scope(timeout: float) -> AsyncIterator[None]:
        """Apply a timeout without moving async context entry to another task."""
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("MCP timeout requires an active asyncio task")

        timed_out = False

        def cancel_task() -> None:
            nonlocal timed_out
            timed_out = True
            task.cancel()

        handle = asyncio.get_running_loop().call_later(timeout, cancel_task)
        try:
            yield
        except asyncio.CancelledError:
            if timed_out:
                uncancel = getattr(task, "uncancel", None)
                if uncancel is not None:
                    uncancel()
                raise asyncio.TimeoutError from None
            raise
        finally:
            handle.cancel()

    def _sanitize_error(self, message: str) -> str:
        sanitized = str(message or "")
        secrets: List[str] = []
        if self.config.command:
            secrets.append(self.config.command)
        secrets.extend(self.config.args)
        secrets.extend((self.config.env or {}).values())
        secrets.extend(self.config.headers.values())
        for secret in sorted(
            (value for value in secrets if value), key=len, reverse=True
        ):
            sanitized = sanitized.replace(secret, "***")
        return sanitized

    @staticmethod
    def _json_value(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {
                str(key): MCPClient._json_value(item) for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [MCPClient._json_value(item) for item in value]
        if hasattr(value, "model_dump"):
            return MCPClient._json_value(value.model_dump(exclude_none=True))
        return str(value)

    @staticmethod
    def _structured_value(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {
                str(key): MCPClient._structured_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [MCPClient._structured_value(item) for item in value]
        if hasattr(value, "model_dump"):
            return MCPClient._structured_value(value.model_dump(exclude_none=True))
        raise TypeError("structured MCP content must be JSON-compatible")

    @staticmethod
    def _model_value(value: Any, *names: str) -> Any:
        for name in names:
            candidate = getattr(value, name, None)
            if candidate is not None:
                return MCPClient._json_value(candidate)
        return None

    @staticmethod
    def _risk_level(annotations: Any) -> str:
        if not isinstance(annotations, dict):
            return "medium"
        destructive = annotations.get("destructiveHint")
        if destructive is None:
            destructive = annotations.get("destructive_hint")
        read_only = annotations.get("readOnlyHint")
        if read_only is None:
            read_only = annotations.get("read_only_hint")
        if destructive is True:
            return "high"
        if read_only is True:
            return "low"
        return "medium"
