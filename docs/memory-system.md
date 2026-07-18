# Memory

Memory is optional and can be installed with:

```bash
pip install praval[memory]
```

Agents can use memory through decorator configuration or `Agent` settings:

```python
from praval import agent

@agent("researcher", memory=True)
def researcher(spore):
    researcher.remember("important fact")
    return {"matches": researcher.recall("important")}
```

The memory system is independent of provider capability resolution. Model
runtime changes do not require a memory backend unless your agent explicitly
uses one.

## Provider-Neutral Embeddings

Memory embedding configuration is separate from the agent's chat model:

```python
from praval import Agent

agent = Agent(
    "researcher",
    provider="anthropic",
    model="claude-sonnet-5",
    memory_enabled=True,
    memory_config={
        "backend": "chromadb",
        "collection_name": "research_v2",
        "embedding_provider": "gemini",
        "embedding_model": "gemini-embedding-2",
        "embedding_dimensions": 768,
        "embedding_provider_options": {
            # Prefer GEMINI_API_KEY/GOOGLE_API_KEY in the environment.
        },
    },
)
```

Supported embedding runtimes are:

| Provider | Default model | Notes |
| --- | --- | --- |
| `sentence-transformers` / `local` | `all-MiniLM-L6-v2` | Local model with deterministic lexical fallback. |
| `openai` | `text-embedding-3-small` | Uses the OpenAI SDK and its normal credential resolution. |
| `openai-compatible` | `text-embedding-3-small` | Set the server `base_url` and the model it exposes. |
| `gemini` | `gemini-embedding-2` | Supports text and `ContentPart` media inputs. |

You can also inject a configured `EmbeddingRuntime` as `embedding_runtime`.
Both Chroma-backed `EmbeddedVectorStore` and Qdrant-backed `LongTermMemory`
use this same abstraction.

## Re-indexing Safety

Embedding vectors from different providers, models, or dimensions are not
interchangeable. Praval stores embedding identity metadata on new collections
and points. If a known mismatch is found, initialization raises
`EmbeddingConfigurationError` with re-index guidance. To migrate:

1. create a new collection name;
2. embed the source documents with the new configuration;
3. verify retrieval quality;
4. switch readers; and
5. retire the old collection only after rollback is no longer needed.

Older collections may not contain identity metadata. Treat those as an
explicit migration decision rather than assuming compatibility.
