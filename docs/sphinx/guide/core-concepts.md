# Core Concepts

Understanding Praval's architecture and design philosophy.

## The Coral Reef Metaphor

Praval is inspired by coral reef ecosystems:

> **Coral polyps** are simple organisms with specialized functions. Individually, they're not complex. But when thousands of polyps collaborate, they create magnificent coral reefs - some of the most complex and productive ecosystems on Earth.

Similarly, in Praval:
- **Agents** are like coral polyps - simple, specialized functions
- **The Reef** is the communication substrate connecting them
- **Spores** are the messages carrying knowledge between agents
- **Complex intelligence** emerges from agent collaboration

## Design Principles

### 1. Specialization Over Generalization

Each agent excels at **one thing**.

**Good:**
```python
@agent("researcher")
def research_agent(spore):
    """I research topics in depth."""
    topic = spore.knowledge.get("topic")
    return {"research": chat(f"Research: {topic}")}
```

**Avoid:**
```python
@agent("super_agent")
def do_everything(spore):
    """I research, analyze, summarize, format, and deploy."""
    # Too many responsibilities!
```

**Why?** Specialized agents are:
- Easier to understand and maintain
- Can run concurrently
- Fail independently (resilience)
- Can be reused across projects

### 2. Declarative Design

Define **what agents ARE**, not **what they DO**.

The `@agent` decorator is **declarative** - you specify:
- Agent's identity (`name`)
- What it responds to (`responds_to`)
- Its capabilities (`system_message`)
- Its resources (`memory`, `knowledge_base`)

You **don't** specify:
- When it runs (agents self-organize)
- How it coordinates (handled by Reef)
- Order of execution (emergent from message flow)

### 3. Emergent Intelligence

Complex behaviors emerge from simple agent interactions.

**Example**: A business analysis system doesn't need a "master orchestrator". Instead:

1. **Interviewer** asks questions → broadcasts `question_asked`
2. **Researcher** hears it → researches → broadcasts `research_ready`
3. **Analyst** hears research → analyzes → broadcasts `analysis_ready`
4. **Reporter** hears analysis → generates report → broadcasts `report_ready`

Each agent only knows its own job. The workflow emerges naturally.

### 4. Zero Configuration

Sensible defaults, progressive enhancement.

**Basic agent:**
```python
@agent("simple")
def simple_agent(spore):
    return chat("Hello")
```

No configuration needed. It just works.

**Enhanced agent:**
```python
@agent("advanced",
       channel="knowledge",
       responds_to=["specific_events"],
       memory=True,
       knowledge_base="./docs/")
def advanced_agent(spore):
    # All features enabled
    pass
```

You add features as needed, not upfront.

### 5. Composability

Agents combine naturally through standard interfaces.

All agents:
- Receive **Spores** (standard message format)
- Use **chat()** (standard LLM interface)
- Return **dictionaries** (standard data format)
- Communicate via **broadcast()** (standard messaging)

This means any agent can work with any other agent.

## Core Components

### Agents

**What**: Functions decorated with `@agent()` that become autonomous agents.

**Signature**:
```python
@agent(name, channel=None, system_message=None,
       auto_broadcast=True, responds_to=None,
       memory=False, knowledge_base=None)
def agent_function(spore):
    return {"result": "..."}
```

**Key attributes:**
- `name`: Unique identifier
- `responds_to`: List of message types to handle
- `memory`: Enable persistent memory
- `knowledge_base`: Auto-index documents

**Agent capabilities:**
- `chat(prompt)`: Talk to LLM
- `broadcast(message)`: Send to other agents
- `remember(text)`: Store in memory (if enabled)
- `recall(query)`: Retrieve from memory (if enabled)

### Spores

**What**: Structured messages carrying knowledge between agents.

**Structure** (Spore dataclass):
```python
Spore(
    id="unique-uuid",                    # Auto-generated
    spore_type=SporeType.BROADCAST,      # Enum: KNOWLEDGE, BROADCAST, etc.
    from_agent="researcher",             # Sender agent name
    to_agent=None,                       # Target (None for broadcasts)
    knowledge={                          # Data payload
        "type": "message_type",          # Message type for filtering
        "key": "value",
        ...
    },
    created_at=datetime.now(),
    metadata={...}                       # Optional: extra context
)
```

**Accessing spore data:**
```python
def my_agent(spore):
    msg_type = spore.knowledge.get("type")  # Type is in knowledge dict
    data = spore.knowledge.get("key")
    sender = spore.from_agent               # Note: from_agent, not sender
```

**Message filtering** with `responds_to`:
```python
@agent("listener", responds_to=["event_a", "event_b"])
def listener(spore):
    # Agent only receives spores where knowledge["type"] matches responds_to
    msg_type = spore.knowledge.get("type")
    if msg_type == "event_a":
        # Handle event A
    elif msg_type == "event_b":
        # Handle event B
```

### The Reef

**What**: The communication substrate connecting all agents.

**Key features:**
- **Message routing**: Delivers spores to interested agents
- **Channels**: Organize communication streams
- **Async delivery**: Non-blocking message passing
- **History tracking**: Maintains message logs

**The Reef is automatic** - you rarely interact with it directly:

```python
# This happens automatically when you:
broadcast({"type": "event"})

# Behind the scenes:
# 1. Reef receives the spore
# 2. Finds all agents listening to "event"
# 3. Delivers to each one asynchronously
# 4. Logs the transaction
```

**Manual Reef access** (advanced):
```python
from praval import get_reef

reef = get_reef()
reef.wait_for_completion()  # Wait for all agents to finish
reef.shutdown()             # Clean up resources
stats = reef.get_network_stats()  # Get communication statistics
```

### Registry

**What**: Catalog of all agents in the system.

**Automatic registration**:
```python
@agent("worker")  # Automatically registered
def worker(spore):
    pass
```

**Discovery**:
```python
from praval import get_registry

registry = get_registry()
all_agents = registry.list_agents()
worker = registry.get_agent("worker")
```

**Use cases:**
- Debugging: See all active agents
- Monitoring: Track agent states
- Dynamic dispatch: Route to agents by capability

## Communication Patterns

### Pattern 1: Broadcast & Filter

**Most common pattern** in Praval.

```python
@agent("listener1", responds_to=["event"])
def listener1(spore):
    print("Listener 1 heard event")

@agent("listener2", responds_to=["event"])
def listener2(spore):
    print("Listener 2 heard event")

@agent("listener3", responds_to=["other_event"])
def listener3(spore):
    print("Listener 3 won't hear 'event'")

# Trigger via start_agents
start_agents(listener1, listener2, listener3, initial_data={"type": "event"})
get_reef().wait_for_completion()
# Output:
# Listener 1 heard event
# Listener 2 heard event
```

### Pattern 2: Request-Response

Agent makes a request, another responds.

```python
@agent("requester")
def requester(spore):
    broadcast({"type": "data_request", "query": "user_data"})
    # Continue with other work...

@agent("responder", responds_to=["data_request"])
def responder(spore):
    query = spore.knowledge.get("query")
    data = fetch_data(query)
    broadcast({"type": "data_response", "data": data})
```

### Pattern 3: Pipeline

Chain of agents, each processing and passing along.

```python
@agent("ingestion", responds_to=["raw_data"])
def ingestion(spore):
    clean = clean_data(spore.knowledge.get("data"))
    broadcast({"type": "clean_data", "data": clean})

@agent("analysis", responds_to=["clean_data"])
def analysis(spore):
    results = analyze(spore.knowledge.get("data"))
    broadcast({"type": "analyzed_data", "results": results})

@agent("reporting", responds_to=["analyzed_data"])
def reporting(spore):
    report = generate_report(spore.knowledge.get("results"))
    broadcast({"type": "final_report", "report": report})
```

### Pattern 4: Coordinator

One agent orchestrates others.

```python
@agent("coordinator")
def coordinator(spore):
    task = spore.knowledge.get("task")

    # Dispatch to specialists
    broadcast({"type": "research_task", "topic": task})
    broadcast({"type": "analysis_task", "subject": task})
    broadcast({"type": "summary_task", "item": task})

    # Collect results in another agent...

@agent("researcher", responds_to=["research_task"])
def researcher(spore):
    # Do research
    broadcast({"type": "research_complete", "findings": "..."})
```

## Memory System

Praval provides multi-layered memory for agents that need to remember.

### Memory Types

1. **Short-term Memory**: Working memory, temporary
2. **Long-term Memory**: Persistent vector storage
3. **Episodic Memory**: Conversation history
4. **Semantic Memory**: Facts and knowledge

### Enabling Memory

```python
@agent("learner", memory=True)
def learner(spore):
    question = spore.knowledge.get("question")

    # Store
    learner.remember(f"Asked: {question}")

    # Retrieve
    context = learner.recall(question, limit=5)

    # Use context
    answer = chat(f"Context: {context}\nQuestion: {question}")
    return {"answer": answer}
```

### Knowledge Base

Auto-index documents for instant agent knowledge:

```python
@agent("expert", memory=True, knowledge_base="./docs/")
def expert(spore):
    # Agent automatically has access to all documents in ./docs/
    query = spore.knowledge.get("query")

    # Semantic search across documents
    relevant = expert.recall(query)

    return {"answer": chat(f"Based on: {relevant}\nAnswer: {query}")}
```

See [Memory System Guide](memory-system.md) for details.

## Tool System

Agents can use external tools and APIs.

### Defining Tools

```python
from praval import tool

@tool("calculator", description="Performs mathematical calculations")
def calculator(expression: str) -> float:
    """Evaluates a mathematical expression."""
    return eval(expression)  # Simplified for demo

@tool("web_search")
def search_web(query: str) -> str:
    """Searches the web and returns results."""
    # Implementation...
    return results
```

### Using Tools in Agents

```python
@agent("assistant")
def assistant(spore):
    # Agent automatically discovers registered tools
    question = spore.knowledge.get("question")

    # LLM can suggest tool usage via chat
    result = chat(f"Answer this using available tools: {question}")

    return {"answer": result}
```

See [Tool System Guide](tool-system.md) for details.

## Storage System

Unified interface for data persistence across providers.

### Supported Providers

- **FileSystem**: Local file storage
- **PostgreSQL**: Relational database
- **Redis**: In-memory cache
- **S3**: Cloud object storage
- **Qdrant**: Vector database

### Using Storage

```python
from praval import get_data_manager

@agent("data_agent")
def data_agent(spore):
    dm = get_data_manager()

    # Store data
    ref = dm.store(
        data={"user": "alice", "score": 95},
        storage_type="postgresql",
        metadata={"category": "user_data"}
    )

    # Retrieve data
    data = dm.retrieve(ref)

    return {"stored_ref": ref, "data": data}
```

See [Storage Guide](storage.md) for details.

## LLM Provider System

Praval supports multiple LLM providers with automatic selection.

### Supported Providers

- **OpenAI**: GPT-4, GPT-3.5-turbo, etc.
- **Anthropic**: Claude models
- **Cohere**: Command and Generate models

### Provider Selection

**Automatic** (based on API keys):
```python
# Just use chat() - Praval picks the provider
result = chat("Hello, world!")
```

**Explicit**:
```python
from praval.providers import get_provider

provider = get_provider("openai", model="gpt-4-turbo")
result = provider.generate("Hello, world!")
```

### Configuration

**Via environment:**
```bash
export PRAVAL_DEFAULT_PROVIDER=anthropic
export PRAVAL_DEFAULT_MODEL=claude-3-opus-20240229
```

**Programmatic** (set environment before import):
```python
import os
os.environ["PRAVAL_DEFAULT_PROVIDER"] = "openai"
os.environ["PRAVAL_DEFAULT_MODEL"] = "gpt-4-turbo"

from praval import agent, chat, start_agents
```

## Agent Lifecycle

Understanding how agents work through their lifecycle:

### 1. Definition

```python
@agent("worker")
def worker(spore):
    return {"status": "done"}
```

When Python executes this:
- Decorator creates Agent instance
- Wraps the function
- Registers with Registry
- Subscribes to Reef

### 2. Activation & Execution

```python
start_agents(
    worker,
    initial_data={"type": "task", "data": "..."}
)
get_reef().wait_for_completion()
```

This:
- Initializes the Reef
- Registers all provided agents
- Broadcasts `initial_data` to trigger the workflow
- `wait_for_completion()` blocks until all agents finish

For each matching agent:
- Reef delivers spore
- Agent function executes
- Return value captured
- Auto-broadcast if enabled

### 4. Communication

Agents can:
- Receive spores (automatic via `responds_to`)
- Send broadcasts (explicit via `broadcast()`)
- Chat with LLM (via `chat()`)
- Store/retrieve data (via storage system)

## Error Handling

### Agent Resilience

**Key principle**: One agent's failure doesn't crash the system.

```python
@agent("risky")
def risky_agent(spore):
    try:
        # Potentially failing operation
        result = dangerous_operation()
        return {"result": result}
    except Exception as e:
        # Handle gracefully
        broadcast({"type": "error", "error": str(e)})
        return {"status": "failed", "error": str(e)}
```

### Reef Guarantees

The Reef ensures:
- Messages are logged even if delivery fails
- Agent failures are isolated
- Other agents continue operating
- Errors are traceable

## Performance Considerations

### Concurrency

Agents run concurrently by default:
- Each agent in separate execution context
- Messages delivered asynchronously
- No blocking between agents

### Memory Usage

For memory-enabled agents:
- Short-term memory is RAM-based (fast, limited)
- Long-term memory is disk-based (slower, unlimited)
- Configure limits based on your needs

### Scaling

**Vertical** (single machine):
```python
configure({
    "max_concurrent_agents": 20  # More parallel agents
})
```

**Horizontal** (multiple machines):
- Use external Reef (Redis, RabbitMQ)
- Shared storage backend
- See advanced deployment guides

## Best Practices

### 1. Keep Agents Small

```python
# Good
@agent("parser")
def parse_data(spore):
    return {"parsed": parse(spore.knowledge.get("raw"))}

# Too big
@agent("everything")
def do_everything(spore):
    # 500 lines of code doing 10 different things
```

### 2. Use Descriptive Names

```python
# Good
@agent("user_data_validator")
@agent("email_notification_sender")

# Unclear
@agent("thing1")
@agent("processor")
```

### 3. Document System Messages

```python
@agent("analyzer", system_message="""
You are a financial data analyzer specializing in:
- Revenue trend analysis
- Cost optimization
- Profit margin calculation

Be precise and cite data sources.
""")
def analyzer(spore):
    # Agent has clear instructions
    pass
```

### 4. Filter Messages Specifically

```python
# Good - specific filtering
@agent("handler", responds_to=["user_login", "user_logout"])

# Too broad - receives everything
@agent("handler")  # No filtering
```

### 5. Handle Errors Gracefully

```python
@agent("robust")
def robust_agent(spore):
    try:
        result = risky_operation()
        return {"result": result}
    except ValueError as e:
        return {"error": "invalid_input", "detail": str(e)}
    except Exception as e:
        return {"error": "unknown", "detail": str(e)}
```

## Next Steps

Now that you understand core concepts:

- **Tutorials**: Build real applications
- **API Reference**: Detailed function documentation
- **Examples**: Production-ready patterns
- **Advanced Guides**: Memory, Tools, Storage systems
