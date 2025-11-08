"""
Praval Website Sidebar Example - Zero to Agent System

This example demonstrates the code shown on the Praval website sidebar.
Three specialized agents collaborate: researcher → analyst → writer

Setup:
------
1. Install Praval:
   pip install praval

2. Set your LLM API key (choose one):
   export OPENAI_API_KEY="sk-your-key-here"
   export ANTHROPIC_API_KEY="sk-ant-your-key-here"
   export COHERE_API_KEY="your-cohere-key-here"

   Or create a .env file with one of the above

3. Run:
   python examples/website_sidebar_example.py
"""

import os
import time
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Check for API key - at least one is required
if not any([
    os.getenv("OPENAI_API_KEY"),
    os.getenv("ANTHROPIC_API_KEY"),
    os.getenv("COHERE_API_KEY")
]):
    print("❌ ERROR: No LLM API key found!\n")
    print("Please set one of these environment variables:")
    print("  export OPENAI_API_KEY='sk-your-key-here'")
    print("  export ANTHROPIC_API_KEY='sk-ant-your-key-here'")
    print("  export COHERE_API_KEY='your-cohere-key-here'")
    print("\nOr create a .env file with your API key")
    exit(1)

print("✓ API key found - starting agents...\n")

# ============================================================================
# Import Praval components
# ============================================================================
from praval import agent, chat, broadcast, start_agents

# ============================================================================
# Define three specialized agents that coordinate through message passing
# ============================================================================

@agent("researcher", responds_to=["query"])
def researcher(spore):
    """I research topics deeply."""
    topic = spore.knowledge.get("topic", "AI")
    print(f"🔍 Researcher: Starting research on '{topic}'...")

    # chat() can only be called inside @agent decorated functions
    # It uses the LLM to generate a response
    findings = chat(f"Research: {topic}")

    print(f"   ✓ Research complete!\n")

    # broadcast() sends a message that other agents can receive
    # The "type" field determines which agents will respond
    broadcast({"type": "analysis_request", "data": findings})

@agent("analyst", responds_to=["analysis_request"])
def analyst(spore):
    """I analyze for insights."""
    data = spore.knowledge.get("data", "")
    print(f"📊 Analyst: Analyzing research findings...")

    # Analyze the research data using LLM
    insights = chat(f"Analyze: {data}")

    print(f"   ✓ Analysis complete!\n")

    # Broadcast to trigger the next agent in the chain
    broadcast({"type": "report", "insights": insights})

@agent("writer", responds_to=["report"])
def writer(spore):
    """I create polished reports."""
    insights = spore.knowledge.get("insights", "")
    print(f"✍️  Writer: Creating final report...\n")

    # Generate the polished report
    report = chat(f"Write: {insights}")

    # Display the final output
    print("=" * 70)
    print("📄 FINAL REPORT")
    print("=" * 70)
    print(report)
    print("=" * 70 + "\n")

# ============================================================================
# Main execution
# ============================================================================

if __name__ == "__main__":
    print("🚀 Starting three-agent collaboration system\n")
    print("-" * 70)

    # Launch the agent ecosystem with an initial query
    # The agents will coordinate automatically through message passing!
    start_agents(
        researcher,  # Responds to "query"
        analyst,     # Responds to "analysis_request"
        writer,      # Responds to "report"
        initial_data={"type": "query", "topic": "AI agents"}
    )

    # Give agents time to complete their async work
    # In production, you'd use proper event monitoring or callbacks
    print("\nWaiting for agents to complete their work...")
    time.sleep(15)  # Adjust based on LLM response times

    print("\n" + "=" * 70)
    print("HOW IT WORKS:")
    print("=" * 70)
    print("1. Researcher receives 'query' → researches → broadcasts 'analysis_request'")
    print("2. Analyst receives 'analysis_request' → analyzes → broadcasts 'report'")
    print("3. Writer receives 'report' → creates final report")
    print("\n✨ No central orchestrator - agents coordinate through messages!")
    print("=" * 70)
