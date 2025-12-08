# Getting Started with Praval

Welcome to Praval! This guide will help you get up and running with the framework in minutes.

## What is Praval?

Praval is a Python framework for building multi-agent AI systems. Instead of creating monolithic AI applications, you create ecosystems of specialized agents that collaborate intelligently.

**The name**: *Praval (प्रवाल)* is Sanskrit for coral, representing how simple agents collaborate to create complex, intelligent ecosystems.

## Installation

### Minimal Installation

For basic agent functionality with LLM support:

```bash
pip install praval
```

### With Memory System

To enable persistent memory with vector search:

```bash
pip install praval[memory]
```

This adds:
- ChromaDB for vector storage
- Sentence Transformers for embeddings
- scikit-learn for similarity search

### With All Features

For the complete Praval experience:

```bash
pip install praval[all]
```

This includes:
- Memory system
- Secure messaging (enterprise features)
- PDF knowledge base support
- All storage providers (PostgreSQL, Redis, S3, Qdrant)

### For Development

If you're contributing to Praval:

```bash
git clone https://github.com/aiexplorations/praval.git
cd praval
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

## Prerequisites

### Python Version

Praval requires **Python 3.9 or higher**. We support:
- Python 3.9
- Python 3.10
- Python 3.11
- Python 3.12

### API Keys

You'll need at least one LLM provider API key. Praval supports:

**OpenAI** (recommended for beginners):
```bash
export OPENAI_API_KEY="sk-..."
```

**Anthropic** (Claude models):
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Cohere**:
```bash
export COHERE_API_KEY="..."
```

Praval automatically detects which provider to use based on available API keys.

## Your First Agent

Let's create a simple research agent:

```python
from praval import agent, chat, start_agents, get_reef

@agent("researcher")
def research_agent(spore):
    """I research topics and provide insights."""
    topic = spore.knowledge.get("topic", "AI")
    result = chat(f"Provide a brief overview of: {topic}")
    print(f"Research on {topic}: {result}")
    return {"summary": result}

# Start the agent system with initial data
start_agents(
    research_agent,
    initial_data={"topic": "quantum computing"}
)

# Wait for processing to complete
get_reef().wait_for_completion()
get_reef().shutdown()
```

**That's it!** You've created your first Praval agent.

## Understanding the Code

Let's break down what's happening:

### 1. The `@agent` Decorator

```python
@agent("researcher")
def research_agent(spore):
    ...
```

This transforms a regular Python function into an intelligent agent. The agent:
- Has a unique name: `"researcher"`
- Receives messages through the `spore` parameter
- Can communicate with other agents
- Has access to LLM capabilities

### 2. The `chat()` Function

```python
result = chat(f"Provide a brief overview of: {topic}")
```

This sends a prompt to your configured LLM provider and returns the response. It automatically:
- Selects the appropriate LLM provider
- Handles API communication
- Manages errors and retries

### 3. The Spore Object

```python
topic = spore.knowledge.get("topic", "AI")
```

A **Spore** is Praval's message format. It's a structured container carrying:
- `knowledge`: Data dictionary (including the message `type` field)
- `from_agent`: Who sent it (agent name)
- `spore_type`: Type of spore (BROADCAST, KNOWLEDGE, etc.)
- `metadata`: Additional context

### 4. Starting Agents

```python
start_agents(
    research_agent,
    initial_data={"topic": "quantum computing"}
)
```

This initializes and runs the agent system. It:
- Creates the Reef (message bus) if needed
- Registers all provided agents
- Broadcasts the `initial_data` to trigger the workflow
- Returns immediately (use `get_reef().wait_for_completion()` to wait)

## Multi-Agent Communication

Now let's create agents that collaborate:

```python
from praval import agent, chat, broadcast, start_agents, get_reef

@agent("researcher", responds_to=["research_request"])
def researcher(spore):
    """Research topics in depth."""
    topic = spore.knowledge.get("topic")
    findings = chat(f"Research this deeply: {topic}")

    # Broadcast findings to other agents
    broadcast({
        "type": "research_complete",
        "topic": topic,
        "findings": findings
    })

    return {"status": "research_complete"}

@agent("summarizer", responds_to=["research_complete"])
def summarizer(spore):
    """Create concise summaries."""
    findings = spore.knowledge.get("findings")
    summary = chat(f"Summarize this in 3 bullet points: {findings}")

    print(f"Summary:\n{summary}")
    return {"summary": summary}

# Start the system with initial data
start_agents(
    researcher,
    summarizer,
    initial_data={"type": "research_request", "topic": "neural networks"}
)

# Wait for all agents to complete processing
get_reef().wait_for_completion()
get_reef().shutdown()
```

**What happens:**

1. You broadcast a `research_request`
2. The `researcher` agent responds (it listens to `research_request`)
3. Researcher does its work and broadcasts `research_complete`
4. The `summarizer` agent responds (it listens to `research_complete`)
5. Summarizer creates and prints a summary

**Key insight**: Agents coordinate themselves. You don't orchestrate the workflow - you just declare what each agent responds to.

## Adding Memory

Give your agents persistent memory:

```python
@agent("expert", memory=True)
def expert_agent(spore):
    """An expert that learns from conversations."""
    question = spore.knowledge.get("question")

    # Recall similar past questions
    past_context = expert_agent.recall(question, limit=3)

    # Generate answer with context
    answer = chat(f"Question: {question}\nContext: {past_context}")

    # Remember this interaction
    expert_agent.remember(f"Q: {question}\nA: {answer}")

    return {"answer": answer}
```

Memory features:
- `remember(text)`: Store information
- `recall(query, limit=5)`: Retrieve similar memories
- `forget()`: Clear memory
- Works across sessions (persistent)

## Next Steps

Now that you have the basics:

1. **Read Core Concepts** - Understand Praval's architecture
2. **Follow Tutorials** - Build real applications step-by-step
3. **Explore Examples** - See production-ready patterns
4. **Check API Reference** - Deep dive into all capabilities

### Recommended Learning Path

**Beginners:**
1. Tutorial: Creating Your First Agent
2. Tutorial: Agent Communication
3. Example: Simple Calculator

**Intermediate:**
1. Tutorial: Memory-Enabled Agents
2. Tutorial: Tool Integration
3. Example: Knowledge Graph Miner

**Advanced:**
1. Tutorial: Multi-Agent Systems
2. Guide: Storage System
3. Guide: Secure Spores

## Common Patterns

### Pattern 1: Request-Response

```python
@agent("responder", responds_to=["request"])
def responder(spore):
    print("Handling request")
    return {"response": "done"}

# Trigger via start_agents with initial_data
start_agents(responder, initial_data={"type": "request"})
get_reef().wait_for_completion()
```

### Pattern 2: Pipeline

```python
@agent("step1", responds_to=["start"])
def step1(spore):
    broadcast({"type": "step2_input", "data": "processed"})

@agent("step2", responds_to=["step2_input"])
def step2(spore):
    broadcast({"type": "final_output", "result": "complete"})
```

### Pattern 3: Fan-Out/Fan-In

```python
# One trigger, multiple responders
@agent("worker1", responds_to=["task"])
def worker1(spore):
    broadcast({"type": "result", "from": "worker1"})

@agent("worker2", responds_to=["task"])
def worker2(spore):
    broadcast({"type": "result", "from": "worker2"})

@agent("aggregator", responds_to=["result"])
def aggregator(spore):
    # Collect all results
    pass
```

## Troubleshooting

### No API Key Found

```
Error: No valid API key found for any LLM provider
```

**Solution**: Set at least one API key:
```bash
export OPENAI_API_KEY="your-key-here"
```

### Import Errors

```
ImportError: cannot import name 'MemoryManager'
```

**Solution**: Install memory dependencies:
```bash
pip install praval[memory]
```

### Agents Not Responding

If agents aren't receiving messages:
1. Check you called `start_agents()`
2. Verify the `responds_to` types match broadcast types
3. Add debug prints to see message flow

## Configuration

### Environment Variables

```bash
# LLM Provider Selection
export PRAVAL_DEFAULT_PROVIDER=openai
export PRAVAL_DEFAULT_MODEL=gpt-4-turbo

# Memory Configuration
export QDRANT_URL=http://localhost:6333

# Logging
export PRAVAL_LOG_LEVEL=INFO
```

### Provider Selection

Praval uses environment variables for configuration. To select a specific provider and model programmatically, set the environment variables before importing praval:

```python
import os
os.environ["PRAVAL_DEFAULT_PROVIDER"] = "openai"
os.environ["PRAVAL_DEFAULT_MODEL"] = "gpt-4-turbo"

from praval import agent, chat, start_agents
# ... your agent code
```

## Getting Help

- **Documentation**: You're reading it!
- **GitHub Issues**: [Report bugs](https://github.com/aiexplorations/praval/issues)
- **Examples**: See `examples/` directory
- **API Reference**: Complete function documentation

Ready to dive deeper? Head to **Core Concepts** to understand Praval's architecture!
