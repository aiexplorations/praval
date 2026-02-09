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

## 3) Category-Based Tools + Provider Tool Calls

```python
from praval import agent, tool, Agent

@tool("weather", category="external", shared=True)
def get_weather(city: str) -> str:
    return f"Sunny in {city}"

@agent("assistant", tool_categories=["external"], auto_discover_tools=False)
def assistant(spore):
    return {"answer": "Ask me the weather."}

llm = Agent("assistant")
llm.tools["weather"] = {
    "function": get_weather,
    "description": "Get weather",
    "parameters": {"city": {"type": "str", "required": True}}
}
print(llm.chat("What's the weather in Paris?"))
```

## See Also
- [Tool System Guide](../guide/tool-system.md)
- `examples/012_tools_basic.py`
- `examples/013_tools_shared.py`
- `examples/014_tools_categories.py`
