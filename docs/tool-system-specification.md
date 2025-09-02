# Praval Tool System Specification

## Overview

The Praval Tool System provides a comprehensive framework for creating, registering, and managing tools that can be used by agents. This system extends Praval's decorator-based architecture to support modular, reusable tools that can be shared across multiple agents.

## Key Features

### 1. Declarative Tool Definition
Tools are defined using the `@tool` decorator, similar to how agents are defined with `@agent`:

```python
@tool(
    tool_name="mathematical_add",
    owned_by="calculator",
    description="Add two numbers together",
    category="arithmetic"
)
def add_numbers(x: float, y: float) -> float:
    """Add two numbers and return the result."""
    return x + y
```

### 2. Tool Registry
A centralized registry manages all tools and their relationships to agents:

```python
from praval import get_tool_registry

registry = get_tool_registry()
tools = registry.get_tools_for_agent("calculator")
all_tools = registry.list_all_tools()
```

### 3. Agent-Tool Association
Tools can be associated with agents in multiple ways:

- **Direct Ownership**: `owned_by="agent_name"`
- **Shared Tools**: `shared=True` (available to all agents)
- **Category-based**: `category="math"` (agents can request tools by category)
- **Runtime Assignment**: Tools can be dynamically assigned to agents

### 4. Type Safety and Validation
All tools must include proper type hints and validation:

```python
@tool("validator", owned_by="data_processor")
def validate_email(email: str) -> bool:
    """Validate email address format."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
```

## Architecture

### Core Components

1. **ToolRegistry**: Central registry for all tools
2. **Tool**: Individual tool wrapper with metadata
3. **ToolCollection**: Group of related tools
4. **@tool Decorator**: Function decorator for tool registration
5. **Agent Integration**: Seamless integration with existing agent system

### Tool Metadata Structure

```python
@dataclass
class ToolMetadata:
    tool_name: str
    owned_by: Optional[str] = None
    description: str = ""
    category: str = "general"
    shared: bool = False
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    return_type: str = "Any"
```

### Tool Registry Interface

```python
class ToolRegistry:
    def register_tool(self, tool: Tool) -> None
    def get_tool(self, tool_name: str) -> Optional[Tool]
    def get_tools_for_agent(self, agent_name: str) -> List[Tool]
    def get_tools_by_category(self, category: str) -> List[Tool]
    def get_shared_tools(self) -> List[Tool]
    def list_all_tools(self) -> List[Tool]
    def assign_tool_to_agent(self, tool_name: str, agent_name: str) -> bool
    def remove_tool_from_agent(self, tool_name: str, agent_name: str) -> bool
    def clear_registry(self) -> None
```

## Usage Patterns

### Pattern 1: Agent-Specific Tools

```python
from praval import agent, tool

@tool("calculator_add", owned_by="calculator")
def add(x: float, y: float) -> float:
    return x + y

@tool("calculator_multiply", owned_by="calculator")
def multiply(x: float, y: float) -> float:
    return x * y

@agent("calculator")
def calculator_agent(spore):
    # Tools are automatically available to this agent
    query = spore.knowledge.get("query", "")
    return {"result": "calculation complete"}
```

### Pattern 2: Shared Tools

```python
@tool("logger", shared=True, category="utility")
def log_message(level: str, message: str) -> str:
    import logging
    logger = logging.getLogger("praval.tools")
    getattr(logger, level.lower())(message)
    return f"Logged: {message}"

# Available to all agents automatically
@agent("data_processor")
def processor_agent(spore):
    # Can use the logger tool
    pass

@agent("analyzer")
def analyzer_agent(spore):
    # Can also use the logger tool
    pass
```

### Pattern 3: Category-Based Tools

```python
@tool("sin", category="trigonometry", owned_by="math_agent")
def sine(angle: float) -> float:
    import math
    return math.sin(math.radians(angle))

@tool("cos", category="trigonometry", owned_by="math_agent")
def cosine(angle: float) -> float:
    import math
    return math.cos(math.radians(angle))

# Agent can request all trigonometry tools
@agent("scientific_calculator")
def sci_calc_agent(spore):
    # Automatically gets access to trigonometry category tools
    pass
```

### Pattern 4: Dynamic Tool Assignment

```python
from praval import get_tool_registry

# Runtime tool assignment
registry = get_tool_registry()
registry.assign_tool_to_agent("advanced_math", "calculator")
registry.assign_tool_to_agent("data_export", "calculator")
```

## Integration with Existing Agent System

### Enhanced @agent Decorator

The existing `@agent` decorator will be enhanced to support tool integration:

```python
@agent(
    "calculator",
    tools=["math_add", "math_multiply"],  # Specific tools
    tool_categories=["arithmetic", "geometry"],  # Tool categories
    auto_discover_tools=True  # Automatically find owned tools
)
def calculator_agent(spore):
    pass
```

### Tool Method Exposure

The `@agent` decorator will expose tool-related methods:

```python
@agent("processor")
def data_processor(spore):
    pass

# Enhanced tool access
data_processor.add_tool("csv_parser")
data_processor.remove_tool("xml_parser")
data_processor.list_tools()
data_processor.tool_exists("json_parser")
```

## Error Handling and Validation

### Tool Validation

```python
class ToolValidationError(Exception):
    pass

# Automatic validation on registration
@tool("invalid_tool", owned_by="agent1")
def bad_tool(x, y):  # Missing type hints
    return x + y  # Will raise ToolValidationError
```

### Runtime Error Handling

```python
@tool("safe_divide", owned_by="calculator")
def divide(x: float, y: float) -> float:
    if y == 0:
        raise ValueError("Division by zero")
    return x / y

# Agent automatically handles tool errors
@agent("calculator")
def calc_agent(spore):
    try:
        # Tool execution is automatically wrapped in error handling
        pass
    except ValueError as e:
        return {"error": str(e)}
```

## Tool Discovery and Introspection

### Tool Discovery

```python
from praval import discover_tools

# Discover tools in a module
tools = discover_tools("my_project.math_tools")

# Discover tools with pattern
tools = discover_tools(pattern="*_tool.py")

# Discover tools by category
math_tools = discover_tools(category="mathematics")
```

### Tool Introspection

```python
tool_info = registry.get_tool("calculator_add")
print(f"Name: {tool_info.metadata.tool_name}")
print(f"Owner: {tool_info.metadata.owned_by}")
print(f"Category: {tool_info.metadata.category}")
print(f"Parameters: {tool_info.metadata.parameters}")
```

## Backward Compatibility

The new tool system maintains full backward compatibility with existing code:

1. Existing `agent.tool` decorator continues to work
2. Tools registered with old system are automatically migrated
3. Agent behavior remains unchanged for existing implementations

## Testing Requirements

### Unit Tests
- Tool registration and retrieval
- Agent-tool association
- Tool validation and error handling
- Registry operations (add, remove, list, search)

### Integration Tests  
- Tool execution within agent context
- Cross-agent tool sharing
- Category-based tool assignment
- Runtime tool management

### Performance Tests
- Tool lookup performance with large registries
- Memory usage with many tools
- Tool execution overhead

## Implementation Phases

### Phase 1: Core Infrastructure
- ToolRegistry implementation
- Tool metadata classes
- Basic @tool decorator
- Agent integration points

### Phase 2: Advanced Features
- Category-based tool management
- Shared tools system
- Tool discovery mechanisms
- Enhanced error handling

### Phase 3: Developer Experience
- CLI tools for tool management
- Tool documentation generation
- IDE integration helpers
- Performance monitoring

## Migration Guide

### For Existing Code

```python
# Before (current approach)
@agent("calculator")
def calc_agent(spore):
    pass

@calc_agent._praval_agent.tool
def add(x: float, y: float) -> float:
    return x + y

# After (new approach)
@tool("add", owned_by="calculator")
def add(x: float, y: float) -> float:
    return x + y

@agent("calculator")
def calc_agent(spore):
    pass
```

### Benefits of Migration
- Cleaner, more modular code
- Better tool reusability
- Enhanced type safety
- Improved debugging and introspection
- Better testing capabilities

This specification provides the foundation for a robust, scalable tool system that enhances Praval's capabilities while maintaining its simple, decorator-based philosophy.