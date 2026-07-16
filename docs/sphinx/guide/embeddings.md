# Embeddings

`EmbeddingRuntime` provides a provider-neutral embedding boundary. It supports
SentenceTransformers, OpenAI, Gemini, and explicitly configured
OpenAI-compatible endpoints.

Chat and embedding configuration are independent. Choose the embedding
provider and vector size for the collection that will store the resulting
vectors; changing either requires a compatible collection or re-indexing.

```python
from praval import EmbeddingRuntime

runtime = EmbeddingRuntime(
    provider="openai",
    model="text-embedding-3-small",
)
response = runtime.embed(["coral reefs", "agent collaboration"])
print(len(response.embeddings))
```

Provider calls require the corresponding credentials. Local embeddings require
the `memory` extra. See the vector-memory course notebook for a complete Qdrant
collection lifecycle and cleanup example.
