# Runtime Migration

This release keeps old APIs working and adds structured runtime APIs for new
work. Use this page to migrate incrementally.

## `Agent.chat()` to `Agent.generate()`

Old:

```python
answer = agent.chat("Summarize this")
```

New:

```python
response = agent.generate("Summarize this")
answer = response.content
```

Use `generate()` when you need provider/model metadata, usage, structured
outputs, reasoning, multimodal input, or consistent per-call options.

## Provider Strings to Provider and Model

Old compact strings still work:

```python
Agent("assistant", model="openai:gpt-5.4-mini")
```

Preferred explicit form:

```python
Agent("assistant", provider="openai", model="gpt-5.4-mini")
```

## Tool Behavior

Legacy provider tool-call handling remains compatible. New calls use
provider-neutral runtime orchestration for OpenAI, Anthropic, Cohere, and
Gemini. Provider-hosted tools and provider-hosted MCP descriptors are not
inferred from client tools; they require the experimental opt-in documented in
{doc}`providers`. Direct stdio and Streamable HTTP MCP connections use the
first-class tools-only client documented in {doc}`mcp`.

## `Spore.knowledge` to V2 Payload Fields

`Spore.knowledge` remains the compatibility field. New code can also populate
`content_parts`, `knowledge_references`, and `data_references`. Rich Spores use
the V2 JSON envelope; knowledge-only Spores retain the legacy wire body. Do not
place bytes directly in a Spore. Use base64 content parts or storage references.

## Embedding Configuration

Chat model settings no longer select the memory embedding model. Configure the
embedding space in `memory_config`:

```python
agent = Agent(
    "researcher",
    provider="openai",
    model="gpt-5.4-mini",
    memory_enabled=True,
    memory_config={
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 1536,
    },
)
```

Changing provider, model, or dimensions changes vector space. Existing Chroma
or Qdrant collections must be re-embedded, or a new collection name must be
used. Praval records the embedding identity and raises
`EmbeddingConfigurationError` when it can prove a collection is incompatible.

## Local LLMs

Old provider strings such as `openai` with custom `base_url` continue to work,
but new local code should use `provider="ollama"`, `provider="vllm"`,
`provider="lmstudio"`, `provider="llama-cpp"`, or
`provider="openai-compatible"` so capability resolution uses the right profile.
