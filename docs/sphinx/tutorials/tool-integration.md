# Tutorial: Tool Integration

Learn to equip agents with external tools and capabilities.

## Prerequisites
- `pip install -e .[dev]`
- At least one provider API key set (OpenAI, Anthropic, or Cohere)

## 1) Minimal Tool + Agent

```python
from praval import agent, tool, start_agents, get_reef

@tool("add_numbers", owned_by="calculator", category="math")
def add(x: int, y: int) -> int:
    return x + y

@agent("calculator", tools=["add_numbers"], auto_discover_tools=False)
def calc(spore):
    return {"result": add(2, 3)}

start_agents(calc, initial_data={"type": "run"})
get_reef().wait_for_completion()
get_reef().shutdown()
```

## 2) Shared Tool Across Agents

```python
from praval import agent, tool

@tool("logger", shared=True, category="utility")
def log(level: str, message: str) -> str:
    import logging
    logging.getLogger("praval.tools").info(f"[{level}] {message}")
    return "ok"

@agent("writer")
def writer(spore):
    log("info", "writing started")
    return {"status": "done"}
```

## 3) Direct Agent tools

```python
from praval import Agent

assistant = Agent("assistant", provider="openai", model="gpt-5.4-mini")


@assistant.tool
def get_weather(city: str) -> str:
    """Return the current weather for a city."""
    return f"Sunny in {city}"


try:
    print(assistant.chat("What's the weather in Paris? Use the tool."))
finally:
    assistant.close()
```

Do not mutate `Agent.tools` manually. Use `Agent.tool()` for a Python function,
the global `@tool` registry for shared decorated-agent tools, or
`Agent.add_tool_spec()` for an externally described JSON-schema tool such as an
MCP tool.

## See Also
- {doc}`../guide/tool-system`
- `examples/012_tools_basic.py`
- `examples/013_tools_shared.py`
- `examples/014_tools_categories.py`
