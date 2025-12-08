#!/usr/bin/env python3
"""
Simple Multi-Agent Example - Praval Framework

This example demonstrates the core multi-agent pattern:
1. Define agents with @agent decorator
2. Use responds_to to filter messages by type
3. Use broadcast() to send messages to other agents
4. Use start_agents() to run the system

Message Flow:
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

Usage:
    export OPENAI_API_KEY=your_key
    python simple_multi_agent.py
"""
import os
from praval import agent, chat, broadcast, start_agents, get_reef


@agent("researcher", responds_to=["research_request"])
def researcher(spore):
    """
    Researches a topic and broadcasts findings to other agents.

    - responds_to=["research_request"] means this agent only processes
      messages where spore.knowledge["type"] == "research_request"
    - broadcast() sends to ALL agents on the default channel
    """
    topic = spore.knowledge.get("topic", "unknown")
    print(f"\n[Researcher] Received request to research: {topic}")

    # chat() calls the LLM within this agent's context
    result = chat(f"Give 3 interesting facts about: {topic}")
    print(f"[Researcher] Found facts:\n{result}")

    # broadcast() sends message to all agents on default channel ("main")
    # The "type" field is used by other agents' responds_to filter
    broadcast({
        "type": "research_complete",  # writer agent responds to this type
        "topic": topic,
        "findings": result
    })

    return {"status": "research_complete"}


@agent("writer", responds_to=["research_complete"])
def writer(spore):
    """
    Writes a summary based on research findings.

    - responds_to=["research_complete"] means this agent only processes
      messages where spore.knowledge["type"] == "research_complete"
    """
    findings = spore.knowledge.get("findings", "")
    topic = spore.knowledge.get("topic", "unknown")
    print(f"\n[Writer] Received research on: {topic}")

    # chat() calls the LLM to generate the article
    article = chat(
        f"Write a brief, engaging paragraph about {topic} "
        f"using these facts:\n{findings}"
    )

    print(f"\n[Writer] Generated article:")
    print("-" * 40)
    print(article)
    print("-" * 40)

    return {"article": article}


if __name__ == "__main__":
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: Set OPENAI_API_KEY environment variable")
        print("  export OPENAI_API_KEY=your_key")
        exit(1)

    print("=" * 50)
    print("Praval Multi-Agent Example")
    print("=" * 50)

    # start_agents() does the following:
    # 1. Registers all agents with the reef
    # 2. Subscribes agents to their channels
    # 3. Broadcasts initial_data to trigger the first agent
    # 4. Runs until no more messages to process

    start_agents(
        researcher,
        writer,
        initial_data={
            "type": "research_request",  # Matches researcher's responds_to
            "topic": "coral reef ecosystems"
        }
    )

    # Wait for all agents to complete processing
    get_reef().wait_for_completion()
    get_reef().shutdown()

    print("\n[System] All agents completed processing")
