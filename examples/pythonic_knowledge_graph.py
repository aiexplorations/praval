#!/usr/bin/env python3
"""
Pythonic Knowledge Graph Mining with Praval's Decorator API

This demonstrates the true power of Praval - turning complex multi-agent
coordination into simple, composable Python functions.

Compare to knowledge_graph_miner.py:
- 489 lines → ~50 lines
- Complex classes → Simple functions  
- Manual threading → Automatic coordination
- Imperative setup → Declarative agents
"""

import json
import time
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

from praval import agent, chat, broadcast, start_agents

# Simple shared state - just Python data structures!
graph = {
    "nodes": set(), 
    "edges": [], 
    "metadata": {"seed": None, "target_size": 10}
}

# ==========================================
# AGENTS AS SIMPLE DECORATED FUNCTIONS
# ==========================================

@agent("explorer", channel="knowledge") 
def discover_concepts(spore):
    """Discover related concepts and add them to the graph."""
    concept = spore.knowledge.get("concept")
    if not concept or concept in graph["nodes"]:
        return
    
    print(f"🔍 Exploring: {concept}")
    
    # Use LLM to find related concepts
    related = chat(f"List 3 concepts closely related to '{concept}'. Return only comma-separated names.")
    concepts = [c.strip() for c in related.split(",") if c.strip()]
    
    # Add to graph
    graph["nodes"].add(concept)
    graph["nodes"].update(concepts)
    
    # Auto-broadcast discovery (return value is automatically sent to channel)
    return {
        "type": "discovery",
        "source": concept,
        "found": concepts,
        "explorer": "explorer"
    }

@agent("connector", channel="knowledge")
def create_relationships(spore):
    """Create relationships between discovered concepts."""
    if spore.knowledge.get("type") != "discovery":
        return
    
    source = spore.knowledge.get("source")
    found = spore.knowledge.get("found", [])
    
    print(f"🔗 Connecting: {source} with {len(found)} concepts")
    
    # Create relationships using LLM
    for concept in found:
        if concept != source:
            relationship = chat(f"How is '{source}' related to '{concept}'? Answer in 2-4 words.")
            
            graph["edges"].append({
                "from": source,
                "to": concept, 
                "relationship": relationship.strip()
            })
    
    return {
        "type": "connections", 
        "count": len(found),
        "connector": "connector"
    }

@agent("curator", channel="knowledge")
def monitor_progress(spore):
    """Monitor graph growth and determine completion."""
    nodes = len(graph["nodes"])
    edges = len(graph["edges"])
    target = graph["metadata"]["target_size"]
    
    print(f"📊 Graph: {nodes} concepts, {edges} relationships")
    
    # Check if we've reached our goal
    if nodes >= target:
        print(f"🎯 Target reached! ({nodes}/{target} concepts)")
        return {"type": "complete", "final_size": nodes}
    
    # Keep exploring if we have unexplored concepts
    unexplored = [node for node in graph["nodes"] 
                 if not any(edge["from"] == node for edge in graph["edges"])]
    
    if unexplored and nodes < target * 1.5:  # Don't go too far over target
        next_concept = unexplored[0]
        print(f"🎯 Next target: {next_concept}")
        
        # Trigger more exploration by broadcasting
        broadcast({"concept": next_concept})

# ==========================================
# SIMPLE STARTUP AND ORCHESTRATION  
# ==========================================

def mine_knowledge_graph(seed_concept: str, target_nodes: int = 8) -> dict:
    """
    Mine a knowledge graph starting from a seed concept.
    
    This is the entire orchestration - just start the agents and let them work!
    """
    print(f"🚀 Mining knowledge graph: {seed_concept}")
    print(f"🎯 Target: {target_nodes} concepts")
    print("=" * 50)
    
    # Initialize
    graph["metadata"]["seed"] = seed_concept
    graph["metadata"]["target_size"] = target_nodes
    graph["nodes"].clear()
    graph["edges"].clear()
    
    # Start all agents and trigger with seed concept
    # This single line starts the entire self-organizing system!
    start_agents(
        discover_concepts, create_relationships, monitor_progress,
        initial_data={"concept": seed_concept}, 
        channel="knowledge"
    )
    
    # Let the agents work autonomously
    start_time = time.time()
    timeout = 30  # seconds
    
    while len(graph["nodes"]) < target_nodes and (time.time() - start_time) < timeout:
        time.sleep(1)
    
    return dict(graph)  # Return a copy

def save_graph(graph_data: dict, filename: str = None):
    """Save the knowledge graph to a JSON file."""
    if not filename:
        seed = graph_data["metadata"]["seed"].replace(" ", "_").lower()
        filename = f"pythonic_kg_{seed}.json"
    
    # Convert set to list for JSON serialization
    serializable = {
        "nodes": list(graph_data["nodes"]),
        "edges": graph_data["edges"],
        "metadata": graph_data["metadata"]
    }
    
    with open(filename, 'w') as f:
        json.dump(serializable, f, indent=2)
    
    print(f"💾 Saved to: {filename}")
    return filename

def print_graph_summary(graph_data: dict):
    """Print a nice summary of the discovered graph."""
    nodes = graph_data["nodes"]
    edges = graph_data["edges"]
    
    print("\n🌟 Discovered Concepts:")
    for i, node in enumerate(sorted(nodes), 1):
        emoji = "🌱" if node == graph_data["metadata"]["seed"] else "💭"
        print(f"  {i:2}. {emoji} {node}")
    
    print(f"\n🔗 Key Relationships:")
    # Group relationships by source
    by_source = defaultdict(list)
    for edge in edges:
        by_source[edge["from"]].append(f"{edge['relationship']} → {edge['to']}")
    
    for source, relationships in list(by_source.items())[:5]:  # Show top 5
        print(f"  📍 {source}:")
        for rel in relationships[:3]:  # Max 3 per source
            print(f"     {rel}")

# ==========================================
# INTERACTIVE DEMO
# ==========================================

def main():
    """Interactive knowledge graph mining demo."""
    print("🏖️ Pythonic Knowledge Graph Miner")
    print("   Powered by Praval's Decorator API")
    print("=" * 50)
    
    try:
        while True:
            seed = input("🌱 Enter concept to explore (or 'quit'): ").strip()
            if seed.lower() in ['quit', 'exit', 'q']:
                break
            
            if not seed:
                continue
            
            try:
                size = int(input("📊 Target concepts (default 8): ").strip() or "8")
                size = max(3, min(15, size))
            except ValueError:
                size = 8
            
            print()
            
            # Mine the graph - this is where the magic happens!
            result = mine_knowledge_graph(seed, size)
            
            # Display results
            print_graph_summary(result)
            
            # Save results
            filename = save_graph(result)
            
            print("\n" + "=" * 50)
    
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()