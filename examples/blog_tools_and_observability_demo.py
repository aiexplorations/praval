"""
Blog tools demo for Praval.

This script exercises the tooling snippet from
`aiexplorations_blogposts/praval_post.md`:
  - A simple @tool-based web_search helper
  - An agent that uses the tool in its body

This demo intentionally avoids LLM calls so it can run without
external API keys; it checks that the tooling pattern in the blog
post is syntactically and structurally valid.
"""

from dataclasses import dataclass

from praval import agent
from praval.tools import tool, register_tool_with_agent


@tool("web_search", description="Search the web", shared=True)
def search_web(query: str) -> str:
    # Placeholder implementation for the blog demo.
    # In a real application, this would call an actual search API.
    return f"Pretend search results for: {query}"


@agent("researcher")
def research_agent(spore):
    """Research agent that can use the web_search tool."""
    query = spore.knowledge.get("query", "Praval multi-agent framework")
    results = search_web(query)
    return {"results": results}


@dataclass
class SimpleSpore:
    """Minimal spore-like object for local testing."""

    knowledge: dict


def main() -> None:
    # Explicitly associate the tool with the agent for this demo
    register_tool_with_agent("web_search", "researcher")
    spore = SimpleSpore({"query": "agentic AI frameworks"})
    result = research_agent(spore)
    print("Agent result:", result)


if __name__ == "__main__":
    main()
