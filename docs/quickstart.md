# Praval Quickstart Guide

This guide covers the two main patterns for building AI agents with Praval.

## Pattern 1: Single Agent (Simple)

Use when you need **one agent** with LLM capabilities. No inter-agent communication needed.

```python
from praval import Agent

# Create a single agent
agent = Agent("assistant")

# Chat with the agent
response = agent.chat("What is machine learning?")
print(response)
```

**When to use:**
- Simple Q&A applications
- Single-purpose chatbots
- Quick prototypes

---

## Pattern 2: Multi-Agent System with @agent decorator

Use when you need **multiple agents** that communicate through the reef messaging system.

```python
from praval import agent, chat, broadcast, start_agents

@agent("researcher", responds_to=["research_request"])
def researcher(spore):
    """Researches a topic and broadcasts findings."""
    topic = spore.knowledge.get("topic", "unknown")
    print(f"[Researcher] Researching: {topic}")

    # chat() calls the LLM within this agent's context
    result = chat(f"Give 3 key facts about: {topic}")

    # broadcast() sends message to all other agents
    # The "type" field determines which agents receive it
    broadcast({
        "type": "research_complete",  # writer responds_to this
        "topic": topic,
        "findings": result
    })
    return {"status": "researched"}

@agent("writer", responds_to=["research_complete"])
def writer(spore):
    """Writes a summary based on research findings."""
    findings = spore.knowledge.get("findings", "")
    topic = spore.knowledge.get("topic", "")
    print(f"[Writer] Writing about: {topic}")

    article = chat(f"Write a brief summary about {topic}: {findings}")
    print(f"[Writer] Article:\n{article}")
    return {"article": article}

if __name__ == "__main__":
    # start_agents() runs the multi-agent system
    # initial_data triggers the first agent (researcher)
    start_agents(
        researcher, writer,
        initial_data={"type": "research_request", "topic": "coral reefs"}
    )
```

---

## Key Concepts

### 1. The `responds_to` Filter

Agents only process messages where `spore.knowledge["type"]` matches their `responds_to` list:

```python
@agent("analyzer", responds_to=["data_ready", "update_request"])
def analyzer(spore):
    msg_type = spore.knowledge.get("type")
    # This agent processes messages with type "data_ready" OR "update_request"
```

If `responds_to=None` (default), the agent receives ALL messages.

### 2. The `broadcast()` Function

`broadcast()` sends a message to all agents on the default channel ("main"):

```python
# Inside an @agent function:
broadcast({
    "type": "analysis_complete",  # Other agents filter on this
    "result": analysis_result,
    "confidence": 0.95
})
```

**Important:** `broadcast()` and `chat()` only work inside `@agent` decorated functions.

### 3. Message Flow

```
initial_data (type: "research_request")
         |
         v
   [researcher] ---- responds_to: ["research_request"]
         |
    broadcast(type: "research_complete")
         |
         v
     [writer] ------- responds_to: ["research_complete"]
         |
       done
```

### 4. The `spore` Object

Every agent receives a `spore` containing the message:

```python
@agent("processor", responds_to=["task"])
def processor(spore):
    # Access message data
    task_type = spore.knowledge.get("type")      # "task"
    task_data = spore.knowledge.get("data")      # custom data

    # Access metadata
    sender = spore.from_agent                     # who sent it
    channel = spore.channel                       # which channel
```

---

## Memory-Enabled Agents

Add persistent memory to your agents:

```python
@agent("assistant", memory=True, responds_to=["question"])
def assistant(spore):
    question = spore.knowledge.get("question")

    # Remember something
    assistant.remember(f"User asked: {question}", importance=0.8)

    # Recall related memories
    memories = assistant.recall(question, limit=5)

    context = "\n".join([m.content for m in memories])
    response = chat(f"Context: {context}\n\nQuestion: {question}")
    return {"answer": response}
```

---

## Common Patterns

### Pipeline Pattern (Sequential Processing)

```python
@agent("extractor", responds_to=["document"])
def extractor(spore):
    text = extract(spore.knowledge.get("doc"))
    broadcast({"type": "extracted", "text": text})

@agent("analyzer", responds_to=["extracted"])
def analyzer(spore):
    analysis = analyze(spore.knowledge.get("text"))
    broadcast({"type": "analyzed", "result": analysis})

@agent("reporter", responds_to=["analyzed"])
def reporter(spore):
    report = format_report(spore.knowledge.get("result"))
    print(report)
```

### Fan-Out Pattern (Parallel Processing)

```python
@agent("coordinator", responds_to=["start"])
def coordinator(spore):
    tasks = spore.knowledge.get("tasks")
    for task in tasks:
        broadcast({"type": "work_item", "task": task})

@agent("worker", responds_to=["work_item"])
def worker(spore):
    # Multiple instances can process in parallel
    result = process(spore.knowledge.get("task"))
    broadcast({"type": "work_done", "result": result})
```

---

## Environment Setup

```bash
# Required
export OPENAI_API_KEY=your_key_here

# Optional
export PRAVAL_DEFAULT_MODEL=gpt-4-turbo
export PRAVAL_LOG_LEVEL=INFO
```

---

## Next Steps

- See `examples/simple_multi_agent.py` for a complete working example
- Read `docs/reef-communication-specification.md` for advanced messaging
- Check `docs/memory-api-reference.md` for memory system details
