# Recipe: a memory-enabled agent

Install the optional memory dependencies:

```bash
python -m pip install "praval[memory]"
```

Memory is attached to an agent explicitly. Chat provider selection and
embedding provider selection are separate decisions.

```python
from praval import agent


@agent(
    "researcher",
    provider="ollama",
    memory={
        "backend": "chromadb",
        "collection_name": "research-notes",
        "embedding_provider": "sentence-transformers",
        "embedding_model": "all-MiniLM-L6-v2",
    },
)
def researcher(spore):
    note = spore.knowledge["note"]
    researcher.remember(note)
    matches = researcher.recall(note, limit=3)
    return {
        "type": "memory_updated",
        "match_ids": [match.id for match in matches],
    }
```

The decorated function exposes `remember()`, `recall()`, `recall_by_id()`, and
conversation-context helpers only when memory is enabled. There is no public
`forget()` convenience method; remove entries through the documented memory
manager/backend API when your retention policy requires deletion.

## Collection compatibility

Persist the embedding provider, model, and dimensions with a collection.
Vectors from incompatible configurations cannot be compared safely. Use a new
collection and re-index when changing embedding identity.

The memory course notebooks show short-term, episodic, semantic, long-term,
Qdrant, and cleanup behavior with visible state.
