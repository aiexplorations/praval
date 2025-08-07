#!/usr/bin/env python3
"""
Concurrent Knowledge Graph Mining with Praval's Async Agent Framework

Demonstrates how Praval's decorator approach with threading enables:
- True concurrent LLM processing across multiple agents
- Message type filtering to prevent broadcast storms  
- Automatic resource management with thread pools
- Pythonic async/await support for agents

Key Features:
- Concurrent agent execution (agents run in parallel threads)
- Message type discrimination (agents only respond to relevant messages)
- Two-phase mining: concept discovery → relationship exploration
- Thread-safe communication through reef channels
- Graceful shutdown and resource cleanup

Before (489 lines + manual threading):
- Complex classes and manual thread management
- Imperative setup and global state management
- Verbose agent creation functions
- Sequential execution blocking on LLM calls

After (~280 lines + automatic threading):
- Simple decorated functions with @agent
- Concurrent execution through ThreadPool
- Automatic coordination through typed messages
- Pure Python data structures with thread safety
"""

import json
import time
import logging
from typing import Dict, Any
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

from praval import agent, chat, broadcast, start_agents

# Configure simple logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Simple shared state - just Python data structures!
graph = {
    "nodes": set(), 
    "edges": [], 
    "explored": set(),  # Track which nodes have been explored for connections
    "metadata": {"seed": None, "target_size": 10}
}

# ==========================================
# CONCURRENT AGENTS AS DECORATED FUNCTIONS
# Each agent runs in its own thread via ThreadPool
# ==========================================

@agent("explorer", channel="knowledge", responds_to=["concept_request"]) 
def discover_concepts(spore):
    """Discover related concepts and add them to the graph.
    
    🧵 This agent runs concurrently with others in a ThreadPool.
    Multiple discovery requests can be processed in parallel.
    """
    concept = spore.knowledge.get("concept")
    if not concept or concept in graph["explored"]:
        return
    
    logging.info(f"🔍 Explorer discovering concepts for: {concept}")
    
    # Use LLM to find related concepts (this LLM call won't block other agents!)
    try:
        related = chat(f"List 3 concepts closely related to '{concept}'. Return only comma-separated names, avoid duplicates or near-synonyms of '{concept}'.", timeout=8.0)
    except TimeoutError:
        logging.warning(f"⏰ Concept discovery for '{concept}' timed out, skipping")
        return
    raw_concepts = [c.strip() for c in related.split(",") if c.strip() and len(c.strip()) > 1]
    
    # Deduplicate and filter concepts
    concepts = []
    for new_concept in raw_concepts:
        # Skip if too similar to existing concepts (simple check)
        if not any(new_concept.lower() in existing.lower() or existing.lower() in new_concept.lower() 
                  for existing in graph["nodes"]):
            concepts.append(new_concept)
    
    # Add to graph
    graph["nodes"].add(concept)
    graph["nodes"].update(concepts)
    graph["explored"].add(concept)  # Mark this concept as explored
    
    # Auto-broadcast discovery (return value automatically sent to channel)
    return {
        "type": "discovery",
        "source": concept,
        "found": concepts,
        "explorer": "explorer"
    }

@agent("relationship_explorer", channel="knowledge", auto_broadcast=False, responds_to=["discovery", "start_relationship_phase"])
def explore_node_relationships(spore):
    """Create relationships from discovery connections and add a few key cross-relationships.
    
    🧵 Runs concurrently with concept discovery - while explorer finds new concepts,
    this agent creates relationships from already discovered concepts in parallel.
    """
    spore_type = spore.knowledge.get("type", "unknown")
    
    # Create relationships immediately when concepts are discovered
    if spore_type == "discovery":
        source = spore.knowledge.get("source")
        found = spore.knowledge.get("found", [])
        
        logging.info(f"🔗 Creating discovery relationships from: {source}")
        
        relationships_created = 0
        for concept in found:
            if concept != source:
                # Generate specific relationship description with confidence
                try:
                    relationship_desc = chat(f"How is '{source}' specifically related to '{concept}'? Answer in 3-5 words describing the relationship type (e.g., 'is a subset of', 'enables', 'uses technique from'). Rate confidence as STRONG/MEDIUM/WEAK and format as 'CONFIDENCE: relationship'.", timeout=6.0)
                except TimeoutError:
                    logging.warning(f"⏰ Relationship description for '{source}' → '{concept}' timed out, using fallback")
                    relationship_desc = f"related to"
                
                # Parse confidence and relationship
                if ":" in relationship_desc:
                    confidence, relationship = relationship_desc.split(":", 1)
                    confidence = confidence.strip().lower()
                    relationship = relationship.strip()
                else:
                    confidence = "medium"
                    relationship = relationship_desc.strip()
                
                # Map confidence to strength
                strength_map = {"strong": "strong", "medium": "medium", "weak": "weak"}
                strength = strength_map.get(confidence, "medium")
                
                graph["edges"].append({
                    "source": source,
                    "target": concept, 
                    "relationship": relationship,
                    "strength": strength
                })
                relationships_created += 1
                logging.info(f"  ✅ {source} → {relationship_desc.strip()} → {concept}")
        
        # Relationships created - no need to broadcast since curator doesn't listen to discovery_connections
    
    # Add cross-relationships when mining phase is complete
    elif spore_type == "start_relationship_phase":
        logging.info("🔗 Adding key cross-relationships between concept clusters")
        
        all_nodes = list(graph["nodes"])
        existing_pairs = {(e["source"], e["target"]) for e in graph["edges"]}
        existing_pairs.update({(e["target"], e["source"]) for e in graph["edges"]})
        
        cross_relationships = 0
        max_cross_relationships = min(6, len(all_nodes))  # Limit total cross-relationships
        analysis_start = time.time()
        
        # Only analyze a few key cross-relationships (not all pairs) with time limit
        for i, concept_a in enumerate(all_nodes):
            if cross_relationships >= max_cross_relationships:
                logging.info(f"✅ Reached max cross-relationships limit ({max_cross_relationships})")
                break
                
            # Time limit: don't spend more than 15 seconds on cross-relationships
            if time.time() - analysis_start > 15:
                logging.info("⏰ Cross-relationship analysis time limit reached")
                break
            
            # Only check 2-3 distant pairs per concept (reduced from i+3:i+6)
            for concept_b in all_nodes[i+2:i+4]:  
                if (concept_a, concept_b) not in existing_pairs:
                    try:
                        analysis = chat(f"Are '{concept_a}' and '{concept_b}' closely related? If YES, describe their relationship in 3-5 words and rate confidence as STRONG/MEDIUM/WEAK. Format as 'CONFIDENCE: relationship' (e.g., 'MEDIUM: applies to'). If NO, reply 'NO'.", timeout=4.0)
                    except TimeoutError:
                        logging.warning(f"⏰ Cross-relationship analysis for '{concept_a}' ↔ '{concept_b}' timed out, skipping")
                        continue
                    
                    if not analysis.upper().startswith("NO"):
                        # Parse confidence and relationship
                        if ":" in analysis:
                            confidence, relationship = analysis.split(":", 1)
                            confidence = confidence.strip().lower()
                            relationship = relationship.strip()
                        else:
                            confidence = "medium"
                            relationship = analysis.replace("YES:", "").replace("Yes:", "").strip()
                        
                        # Map confidence to strength
                        strength_map = {"strong": "strong", "medium": "medium", "weak": "weak"}
                        strength = strength_map.get(confidence, "medium")
                        
                        if relationship and len(relationship) > 2:
                            graph["edges"].append({
                                "source": concept_a,
                                "target": concept_b,
                                "relationship": relationship,
                                "strength": strength
                            })
                            cross_relationships += 1
                            logging.info(f"✅ Cross-relationship: {concept_a} → {relationship} ({strength}) → {concept_b}")
                            
                            if cross_relationships >= max_cross_relationships:
                                break
        
        return {
            "type": "exploration_complete", 
            "cross_relationships": cross_relationships,
            "total_nodes": len(all_nodes),
            "total_edges": len(graph["edges"])
        }

@agent("curator", channel="knowledge", responds_to=["discovery", "exploration_complete"])
def monitor_progress(spore):
    """Monitor graph growth and coordinate two-phase mining process.
    
    🧵 Runs as coordinator agent, managing the mining phases while other
    agents work concurrently on concept discovery and relationship creation.
    """
    nodes = len(graph["nodes"])
    edges = len(graph["edges"])
    target = graph["metadata"]["target_size"]
    
    # Log progress for concept discovery phase
    if spore.knowledge.get("type") == "discovery":
        logging.info(f"📊 Concept Mining: {nodes}/{target} concepts discovered")
    
    # Handle relationship phase completion
    elif spore.knowledge.get("type") == "exploration_complete":
        exploration_rate = (edges / max(nodes, 1)) * 100
        logging.info(f"🎯 Mining Complete! {nodes} concepts, {edges} relationships ({exploration_rate:.1f}% connected)")
        return {"type": "complete", "final_size": nodes, "final_edges": edges}
    
    # Check if concept mining phase is complete
    if nodes >= target and spore.knowledge.get("type") != "systematic_connections":
        if not hasattr(monitor_progress, '_relationship_phase_started'):
            logging.info(f"✅ Concept mining complete ({nodes}/{target} concepts)")
            logging.info("🔄 Starting relationship exploration phase...")
            monitor_progress._relationship_phase_started = True
            broadcast({"type": "start_relationship_phase"}, message_type="start_relationship_phase")
        return
    
    # Continue concept exploration if target not reached
    if nodes < target:
        unexplored = [node for node in graph["nodes"] if node not in graph["explored"]]
        
        if unexplored:
            next_concept = unexplored[0]
            logging.info(f"🎯 Next concept: {next_concept}")
            broadcast({"concept": next_concept, "type": "concept_request"}, message_type="concept_request")

# ==========================================
# SIMPLE ORCHESTRATION FUNCTIONS
# ==========================================

def start_autonomous_mining(seed_concept: str, max_nodes: int = 10):
    """
    Start autonomous knowledge graph mining.
    
    This replaces the entire complex setup from the original version.
    """
    logging.info(f"🚀 Starting autonomous knowledge graph mining: {seed_concept}")
    logging.info(f"🎯 Target: {max_nodes} concepts")
    
    # Initialize graph
    graph["metadata"]["seed"] = seed_concept
    graph["metadata"]["target_size"] = max_nodes
    graph["nodes"].clear()
    graph["edges"].clear()
    graph["explored"].clear()
    
    # Reset curator state for new mining session
    if hasattr(monitor_progress, '_relationship_phase_started'):
        delattr(monitor_progress, '_relationship_phase_started')
    
    # Start all agents with initial concept - this single call starts everything!
    start_agents(
        discover_concepts, explore_node_relationships, monitor_progress,
        initial_data={"concept": seed_concept, "type": "concept_request"}, 
        channel="knowledge"
    )

def wait_for_completion(timeout: int = 45) -> Dict[str, Any]:
    """Wait for autonomous mining to complete both concept discovery and relationship exploration phases."""
    start_time = time.time()
    target = graph["metadata"]["target_size"]
    
    # Wait for concept discovery phase (should be fast with timeouts)
    logging.info("⏳ Waiting for concept discovery phase...")
    concept_timeout = min(timeout * 0.4, 20)  # Max 40% of total timeout for concepts
    
    while len(graph["nodes"]) < target and (time.time() - start_time) < concept_timeout:
        time.sleep(0.5)  # Check more frequently
    
    concept_time = time.time() - start_time
    remaining_time = timeout - concept_time
    
    # Wait for relationship exploration phase
    if len(graph["nodes"]) >= target and remaining_time > 0:
        logging.info("⏳ Waiting for relationship exploration phase...")
        relationship_start = time.time()
        initial_edges = len(graph["edges"])
        last_edge_count = initial_edges
        stall_counter = 0
        
        # Wait for relationship analysis with adaptive timeout
        while (time.time() - start_time) < timeout and stall_counter < 6:
            time.sleep(1)
            current_edges = len(graph["edges"])
            
            if current_edges > last_edge_count:
                # Progress made, reset stall counter
                last_edge_count = current_edges
                stall_counter = 0
                logging.info(f"🔗 Relationship progress: {current_edges} relationships created")
            else:
                stall_counter += 1
            
            # Early exit if we have reasonable relationships
            relationship_rate = current_edges / max(len(graph["nodes"]), 1)
            if relationship_rate > 1.5 and (time.time() - relationship_start) > 8:
                logging.info(f"✅ Sufficient relationships created ({relationship_rate:.1f} per node), completing")
                break
    
    total_time = time.time() - start_time
    if len(graph["nodes"]) < target:
        logging.warning(f"⏰ Mining timed out during concept discovery phase ({total_time:.1f}s)")
    elif stall_counter >= 6:
        logging.info(f"✅ Relationship exploration completed (no activity for {stall_counter}s)")
    
    logging.info(f"🏁 Mining completed in {total_time:.1f}s")
    return get_graph_stats()

def get_graph_stats() -> Dict[str, Any]:
    """Get current graph statistics."""
    total_nodes = len(graph["nodes"])
    total_edges = len(graph["edges"])
    
    return {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "exploration_rate": (total_edges / max(total_nodes, 1)) * 100,
        "seed_concept": graph["metadata"]["seed"]
    }

def save_graph_results(filename: str = None) -> str:
    """Save the knowledge graph to a JSON file."""
    if not filename:
        seed = graph["metadata"]["seed"].replace(" ", "_").lower()
        filename = f"autonomous_kg_{seed}.json"
    
    # Convert set to list for JSON serialization
    result = {
        "seed": graph["metadata"]["seed"],
        "nodes": list(graph["nodes"]),
        "edges": graph["edges"],
        "stats": get_graph_stats()
    }
    
    with open(filename, 'w') as f:
        json.dump(result, f, indent=2)
    
    logging.info(f"💾 Results saved to: {filename}")
    return filename

def print_results():
    """Print a summary of discovered knowledge."""
    stats = get_graph_stats()
    
    print(f"\n📊 Final Results:")
    print(f"  Nodes: {stats['total_nodes']}")
    print(f"  Edges: {stats['total_edges']}")
    print(f"  Exploration: {stats['exploration_rate']:.1f}%")
    
    if graph["nodes"]:
        print(f"\n🌟 Concepts discovered:")
        for i, node in enumerate(sorted(graph["nodes"]), 1):
            emoji = "🌱" if node == graph["metadata"]["seed"] else "💭"
            print(f"  {i:2}. {emoji} {node}")
        
        print(f"\n🔗 Relationships found:")
        # Group by source for better display with strength indicators
        by_source = defaultdict(list)
        strength_emojis = {"strong": "💪", "medium": "🔗", "weak": "〰️"}
        
        for edge in graph["edges"]:
            strength_emoji = strength_emojis.get(edge.get("strength", "medium"), "🔗")
            relationship_str = f"{strength_emoji} {edge['relationship']} → {edge['target']}"
            by_source[edge["source"]].append(relationship_str)
        
        count = 0
        for source, relationships in by_source.items():
            if count >= 6:  # Show more relationships since they're richer
                break
            print(f"  📍 {source}:")
            for rel in relationships[:4]:  # Show more per source
                print(f"     {rel}")
            if len(relationships) > 4:
                print(f"     ... and {len(relationships) - 4} more")
            count += 1
        
        if len(graph["edges"]) > 15:
            print(f"     ... and {len(graph['edges']) - 15} more relationships")

# ==========================================
# MAIN APPLICATION
# ==========================================

def main():
    """Self-organizing knowledge graph mining demo."""
    print("🏖️ Self-Organizing Knowledge Graph Miner")
    print("   Powered by Praval's Pythonic Decorator API")
    print("=" * 50)
    print("Agents autonomously coordinate through decorated functions!")
    print()
    
    try:
        # Interactive mining
        while True:
            seed = input("🌱 Enter concept to explore (or 'quit'): ").strip()
            if seed.lower() in ['quit', 'exit', 'q']:
                break
            
            if not seed:
                continue
            
            try:
                max_nodes = int(input("📊 Max nodes (default 8): ").strip() or "8")
                max_nodes = max(3, max_nodes)  # Minimum 3 nodes
                
                # Ask for confirmation if > 50 nodes
                if max_nodes > 50:
                    confirm = input(f"⚠️  Large graph ({max_nodes} nodes) may take a while. Continue? (y/N): ").strip().lower()
                    if confirm not in ['y', 'yes']:
                        continue
            except ValueError:
                max_nodes = 8
            
            print(f"\n🚀 Starting autonomous mining for: '{seed}'")
            print("=" * 40)
            
            # Start autonomous mining - everything is handled by decorated functions!
            start_autonomous_mining(seed, max_nodes)
            
            # Wait for completion
            final_stats = wait_for_completion(timeout=90)
            
            # Display and save results
            print_results()
            save_graph_results()
            
            print("=" * 50)
    
    except KeyboardInterrupt:
        print("\nGoodbye! 👋")
    except Exception as e:
        logging.error(f"System error: {e}")

if __name__ == "__main__":
    main()