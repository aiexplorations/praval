# Tool System

## Overview

Praval tools are lightweight, typed functions registered in a global registry and optionally bound to agents. Tools can be owned by a specific agent, shared across all agents, or organized by category. The registry powers discovery and assignment while agents expose helper methods for introspection.

## Define a Tool

Use the `@tool` decorator. All parameters must be type-annotated.

```python
from praval import tool

@tool(
    tool_name="add_numbers",
    owned_by="calculator",
    description="Add two numbers together",
    category="arithmetic",
    shared=False,
    version="1.0.0",
    requires_approval=True,
    risk_level="high",
    approval_reason="This tool changes billing data."
)
def add_numbers(x: float, y: float) -> float:
    """Add two numbers and return the result."""
    return x + y
```

## Registry Basics

```python
from praval import get_tool_registry

registry = get_tool_registry()
registry.list_all_tools()
registry.get_tools_for_agent("calculator")
registry.get_tools_by_category("arithmetic")
registry.get_shared_tools()
```

## Agent Integration

The `@agent` decorator supports tool selection:

- `tools`: list of tool names or callables to attach
- `tool_categories`: attach all tools in the listed categories
- `auto_discover_tools`: when `True` (default), attach tools that are owned by the agent, shared, or already assigned in the registry
- `hitl`: when `True`, the agent can pause on approval-gated tools (`False` by default)

```python
from praval import agent

@agent(
    "calculator",
    tools=["add_numbers"],
    tool_categories=["arithmetic"],
    auto_discover_tools=True,
    hitl=True
)
def calculator_agent(spore):
    return {"status": "ready"}
```

Agents expose helpers:

```python
calculator_agent.list_tools()
calculator_agent.get_tool("add_numbers")
calculator_agent.has_tool("add_numbers")
```

## Dynamic Assignment

You can assign tools at runtime via the registry or helpers:

```python
from praval import get_tool_registry

registry = get_tool_registry()
registry.assign_tool_to_agent("add_numbers", "calculator")
registry.remove_tool_from_agent("add_numbers", "calculator")
```

## Discovery Utilities

```python
from praval import discover_tools, list_tools

# Discover by category
math_tools = discover_tools(category="arithmetic")

# List tools with filters
list_tools(agent_name="calculator")
list_tools(shared_only=True)
```

## Execution Notes

Tools are plain Python functions. You can invoke them directly, and the
`Agent.chat(...)` flow passes registered tools to supported providers for
tool-calling where available.

### HITL Approval Metadata

Tool metadata now supports human-approval gating:

- `requires_approval` (`bool`): if `True`, tool calls require human decision.
- `risk_level` (`low|medium|high|critical`): operator-facing risk category.
- `approval_reason` (`str`): shown in intervention queue/UI for context.

If `requires_approval=True` and the agent is decorated with `hitl=False`,
Praval raises `HITLConfigurationError` to prevent silent bypass of policy.

### Intervention Workflow

When a gated tool call occurs on `@agent(..., hitl=True)`:

1. `Agent.chat(...)` raises `InterventionRequired`.
2. Human approves/rejects/edits via Python API or CLI.
3. Resume with `agent.resume_run(run_id)` (or `praval hitl resume <run_id>`).
