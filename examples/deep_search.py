#!/usr/bin/env python3
"""
Deep Search Example - Simple agent research demonstration
"""
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path for local development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from praval import agent, chat, broadcast, start_agents

# Create a specialized agent with just a decorator
@agent("research_expert", responds_to=["research_query"])
def research_agent(spore):
    """I'm an expert at finding and analyzing information."""
    query = spore.knowledge.get("query")
    print(f"🔍 Researching: {query}")
    
    result = chat(f"Research this topic deeply: {query}")
    
    print(f"✅ Research completed!")
    print(f"📊 Findings: {result[:200]}...")  # Show first 200 chars
    
    # Broadcast findings to other agents
    broadcast({
        "type": "research_complete",
        "findings": result,
        "confidence": 0.9
    })
    
    return {"research": result}

if __name__ == "__main__":
    print("🚀 Starting Deep Search Example")
    print("=" * 50)
    
    # Start the agent system
    start_agents(research_agent, initial_data={
        "type": "research_query", 
        "query": "quantum computing applications"
    })
    
    print("=" * 50)
    print("✅ Deep Search Complete!")
