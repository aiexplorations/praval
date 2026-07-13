"""OpenAI-compatible local LLM example.

Start a compatible server first, then run:
    python examples/local_llm_openai_compatible.py
"""

import os

from praval import Agent


def main() -> None:
    if os.getenv("PRAVAL_EXAMPLE_SMOKE") == "1":
        print("SKIP: Set PRAVAL_RUN_LIVE_EXAMPLES=1 to contact a local LLM server.")
        return
    provider = os.getenv("PRAVAL_LOCAL_PROVIDER", "ollama")
    model = os.getenv("PRAVAL_LOCAL_MODEL", "llama3")
    base_url = os.getenv("PRAVAL_LOCAL_BASE_URL")

    config = {"base_url": base_url} if base_url else None
    agent = Agent("local", provider=provider, model=model, config=config)

    print(agent.chat("Reply with one short sentence about local LLMs."))


if __name__ == "__main__":
    main()
