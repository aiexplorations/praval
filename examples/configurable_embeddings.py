"""Configure memory embeddings independently from the chat provider.

Set OPENAI_API_KEY before running this example. ChromaDB is used locally for
vector storage while OpenAI produces embeddings.
"""

import os

from praval import Agent


def main() -> int:
    """Create an agent whose chat and embedding configurations are separate."""
    if not os.getenv("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY to run this example.")
        return 0

    with Agent(
        "memory-demo",
        provider="openai",
        model="gpt-5.4-mini",
        memory_enabled=True,
        memory_config={
            "backend": "chromadb",
            "collection_name": "praval_embedding_example",
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimensions": 1536,
        },
    ) as agent:
        memory_id = agent.remember("Praval keeps embedding config separate.")
        matches = agent.recall("How is embedding configuration handled?")

    print(f"Stored memory: {memory_id}")
    print(f"Matches: {len(matches)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
