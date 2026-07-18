# MCP Tool Clients

Praval 0.8 can consume tools from Model Context Protocol servers without
creating a second tool registry. Discovered tools become normal Praval
`ToolSpec` entries, so provider-neutral model execution, HITL approval,
tracing, timeouts, and error handling continue to apply.

Install the optional SDK support on Python 3.10 or newer:

```bash
pip install 'praval[mcp]'
```

Praval core continues to support Python 3.9. The official MCP Python SDK v1
requires Python 3.10 or newer, so MCP connections are not available on Python
3.9.

## Local stdio server

The stdio transport starts the configured program directly. Praval never
passes the command through a shell.

```python
import asyncio

from praval import Agent
from praval.mcp import MCPClient, MCPServerConfig


async def main() -> None:
    agent = Agent(
        "researcher",
        provider="openai",
        model="gpt-5.4-mini",
        hitl_enabled=True,
    )
    config = MCPServerConfig(
        name="filesystem",
        transport="stdio",
        command="python",
        args=["servers/filesystem_server.py"],
        env={"DATA_ROOT": "/safe/research-data"},
        cwd="/opt/praval-mcp",
    )

    async with MCPClient(config) as client:
        await client.register_tools(agent)
        response = await agent.agenerate("Summarize the available notes.")
        print(response.content)


asyncio.run(main())
```

The default tool prefix is the server name followed by two underscores. A
server tool named `read_file` is exposed to the model as
`filesystem__read_file`. Set `tool_name_prefix` when a different namespace is
needed.

## Remote Streamable HTTP server

Use Streamable HTTP for remote MCP servers. Static headers are caller supplied
and are redacted from Praval errors.

```python
config = MCPServerConfig(
    name="catalog",
    transport="streamable_http",
    url="https://mcp.example.com/api",
    headers={"Authorization": "Bearer ..."},
    connection_timeout=15,
    tool_timeout=30,
)

async with MCPClient(config) as client:
    tools = await client.register_tools(agent)
    print([tool.name for tool in tools])
    response = await agent.agenerate("Find the current catalog entry.")
```

Remote endpoints must use HTTPS. Plain HTTP is accepted only for loopback
hosts such as `127.0.0.1` and `localhost`, which supports local development and
CI contract tests.

## Approval and async execution

MCP tools require approval by default. When a model selects one, Praval raises
`InterventionRequired` before sending the call to the MCP server. Approve and
resume on the same event loop:

```python
from praval import InterventionRequired

try:
    response = await agent.agenerate("Publish the selected catalog entry.")
except InterventionRequired as pending:
    agent.approve_intervention(
        pending.intervention_id,
        reviewer="release-manager",
    )
    text = await agent.aresume_run(pending.run_id)
```

Set `require_approval=False` only for a server whose tools are safe to run
without a human decision. MCP handlers are async-only in 0.8. Use
`Agent.agenerate()` or `Agent.astream()`. A sync agent call that selects an MCP
tool fails with an instruction to use the async API; Praval does not move a
live MCP session between event loops.

## Result handling

Text result blocks are joined into one `ToolResult.content` value. Structured
content is serialized when needed and retained in
`ToolResult.metadata["structured_content"]`. The default normalized result
limit is 1 MiB and can be changed with `max_result_size`.

Images, embedded resources, audio, and other binary MCP result blocks are
rejected with a structured tool error in 0.8. Remote tool failures become
sanitized tool errors instead of leaking configured headers, environment
values, commands, or credentials.

## Lifecycle and security

- Keep the `MCPClient` context open while an agent may use its registered
  tools. Leaving the context closes the session and any spawned stdio process.
- Calls after closure fail. Automatic reconnect is intentionally disabled.
- Stdio configuration cannot contain HTTP fields. HTTP configuration cannot
  contain a command, arguments, environment, or working directory.
- Tool discovery is namespaced per server, and duplicate or invalid schemas
  are rejected.
- Connection and tool calls have bounded timeouts. Cancellation closes partial
  connection state.
- OAuth negotiation is not included. Callers may provide static headers and
  are responsible for acquiring and rotating them.

## MCP clients and provider-hosted descriptors

These are separate capabilities:

- `praval.mcp.MCPClient` opens and owns a direct MCP client connection, then
  registers discovered tools in the normal Praval tool runtime.
- Provider-hosted MCP descriptors are raw provider options passed to a model
  vendor that owns the connection. They remain experimental and
  provider-specific.

Praval never reinterprets a provider-hosted descriptor as a local MCP client.

## Explicitly unsupported in 0.8

- Legacy SSE transport
- Resources and prompts
- Sampling and elicitation
- Experimental MCP tasks
- MCP server hosting
- Managed OAuth flows
- Binary and image results
- Automatic reconnect
- Sync MCP event-loop bridging

