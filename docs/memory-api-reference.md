# Praval Memory API Reference

This document describes the memory methods available to agents with `memory=True`.

## Enabling Memory

```python
from praval import agent, chat

@agent("assistant", memory=True, responds_to=["question"])
def assistant(spore):
    # Memory methods are now available on the function
    assistant.remember(...)
    assistant.recall(...)
```

## Memory Methods

### `remember(content, importance=0.5, memory_type="episodic")`

Store a memory entry.

**Parameters:**
- `content` (str): The content to remember
- `importance` (float, optional): Importance score 0.0-1.0. Higher values persist longer. Default: 0.5
- `memory_type` (str, optional): Type of memory. Options: "episodic", "semantic", "short_term". Default: "episodic"

**Returns:** `str` - Memory ID

**Example:**
```python
@agent("learner", memory=True)
def learner(spore):
    question = spore.knowledge.get("question")

    # Remember with default importance
    memory_id = learner.remember(f"User asked: {question}")

    # Remember with high importance
    learner.remember(
        f"Important insight: {insight}",
        importance=0.9,
        memory_type="semantic"
    )
```

---

### `recall(query, limit=10)`

Retrieve memories relevant to a query using semantic search.

**Parameters:**
- `query` (str): Search query to find relevant memories
- `limit` (int, optional): Maximum number of memories to return. Default: 10

**Returns:** `List[MemoryEntry]` - List of matching memory entries

**MemoryEntry attributes:**
- `id` (str): Unique memory identifier
- `content` (str): The memory content
- `agent_id` (str): Which agent created the memory
- `memory_type` (MemoryType): Type of memory
- `importance` (float): Importance score
- `timestamp` (datetime): When created
- `metadata` (dict): Additional metadata

**Example:**
```python
@agent("assistant", memory=True)
def assistant(spore):
    question = spore.knowledge.get("question")

    # Recall relevant memories
    memories = assistant.recall(question, limit=5)

    # Build context from memories
    context = "\n".join([m.content for m in memories])

    response = chat(f"Context:\n{context}\n\nQuestion: {question}")
    return {"answer": response}
```

---

### `recall_by_id(memory_id)`

Retrieve a specific memory by its ID.

**Parameters:**
- `memory_id` (str): The ID of the memory to retrieve

**Returns:** `Optional[MemoryEntry]` - The memory entry or None if not found

**Example:**
```python
@agent("reviewer", memory=True)
def reviewer(spore):
    memory_id = spore.knowledge.get("memory_id")

    memory = reviewer.recall_by_id(memory_id)
    if memory:
        print(f"Found: {memory.content}")
```

---

### `get_conversation_context(turns=10)`

Retrieve recent conversation history for context.

**Parameters:**
- `turns` (int, optional): Number of recent conversation turns to retrieve. Default: 10

**Returns:** `List[dict]` - List of conversation entries

**Example:**
```python
@agent("assistant", memory=True)
def assistant(spore):
    # Get recent conversation history
    context = assistant.get_conversation_context(turns=5)

    # Use context to inform response
    history = "\n".join([str(c) for c in context])
    response = chat(f"Previous context:\n{history}\n\nNew question: {question}")
```

---

## Memory Types

```python
from praval import MemoryType

MemoryType.SHORT_TERM   # Fast, temporary working memory
MemoryType.LONG_TERM    # Persistent vector storage
MemoryType.EPISODIC     # Conversation/experience history
MemoryType.SEMANTIC     # Facts and knowledge
```

---

## Configuration Options

### Via Decorator

```python
@agent("assistant",
       memory=True,  # Enable with defaults
       knowledge_base="/path/to/docs/")  # Auto-index files
def assistant(spore):
    ...
```

### Via Dictionary Config

```python
@agent("assistant",
       memory={
           "backend": "chromadb",  # or "qdrant", "memory"
           "collection_name": "my_memories",
           "short_term_max_entries": 1000,
           "short_term_retention_hours": 24
       })
def assistant(spore):
    ...
```

---

## Environment Variables

```bash
# Vector database URL (for Qdrant backend)
QDRANT_URL=http://localhost:6333

# Collection name
PRAVAL_COLLECTION_NAME=praval_memories

# Auto-load knowledge base
PRAVAL_KNOWLEDGE_BASE=/path/to/knowledge/
```

---

## Backend Options

| Backend | Description | Persistence |
|---------|-------------|-------------|
| `chromadb` | Embedded vector DB (default) | Local file |
| `qdrant` | Qdrant vector database | Remote server |
| `memory` | In-memory only | None |
| `auto` | Try chromadb, fallback to qdrant, then memory | Varies |

---

## Complete Example

```python
from praval import agent, chat, broadcast, start_agents

@agent("teacher", memory=True, responds_to=["lesson_request"])
def teacher(spore):
    """Teaching agent that remembers past lessons."""
    topic = spore.knowledge.get("topic")

    # Check if we've taught this before
    past_lessons = teacher.recall(f"lesson about {topic}", limit=3)

    if past_lessons:
        context = "Previous lessons:\n" + "\n".join([m.content for m in past_lessons])
        lesson = chat(f"{context}\n\nCreate a NEW lesson about {topic}")
    else:
        lesson = chat(f"Create an introductory lesson about {topic}")

    # Remember this lesson
    teacher.remember(
        f"Taught lesson about {topic}: {lesson[:200]}...",
        importance=0.8,
        memory_type="episodic"
    )

    broadcast({"type": "lesson_ready", "content": lesson})
    return {"lesson": lesson}

@agent("student", memory=True, responds_to=["lesson_ready"])
def student(spore):
    """Student that learns and remembers lessons."""
    lesson = spore.knowledge.get("content")

    # Store the lesson as semantic knowledge
    student.remember(
        f"Learned: {lesson}",
        importance=0.7,
        memory_type="semantic"
    )

    understanding = chat(f"Summarize what you learned: {lesson}")
    return {"summary": understanding}

if __name__ == "__main__":
    start_agents(
        teacher, student,
        initial_data={"type": "lesson_request", "topic": "photosynthesis"}
    )
```
