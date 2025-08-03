#!/usr/bin/env python3
"""
Multi-Agent Knowledge Graph Mining using Praval Framework
Demonstrates how simple agents collaborate to build complex knowledge structures.

Like a coral ecosystem where different organisms have specialized roles but work together
to create complex reef structures, each agent has a specific purpose in knowledge discovery.
"""

import json
import random
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()

from praval import Agent, register_agent, get_registry

# ==========================================
# MULTI-AGENT KNOWLEDGE MINING SYSTEM
# ==========================================

def setup_knowledge_mining_agents():
    """
    Set up and register specialized agents for knowledge graph construction.
    Each agent has a distinct role in the collaborative mining process.
    """
    
    # Domain Expert: Understands concepts and their context
    domain_expert = Agent("domain_expert", system_message="""You are a domain expert who understands concepts deeply and can identify the most relevant related concepts.

When given a concept, identify the most important related concepts that would be valuable in a knowledge graph.

Return ONLY a JSON list of concept names: ["concept1", "concept2", "concept3"]

Focus on:
- Core subtopics and components
- Closely related fields and disciplines  
- Key applications and practical uses
- Important foundational or prerequisite concepts
- Significant outcomes or results""")
    
    # Relationship Analyst: Specializes in understanding connections
    relationship_analyst = Agent("relationship_analyst", system_message="""You are a relationship analyst who specializes in understanding how concepts connect to each other.

Analyze the relationship between two concepts and classify both the type and strength of connection.

Return ONLY a JSON object:
{"relationship": "precise relationship description", "strength": "strong|medium|weak", "direction": "bidirectional|unidirectional"}

Relationship types:
- "is a type of", "contains", "enables", "requires", "influences", "causes", "results in"
- "implements", "uses", "applies to", "exemplifies", "depends on"

Strength guidelines:
- strong: direct, essential, or definitional connection
- medium: significant but not essential connection  
- weak: indirect or tangential connection""")
    
    # Concept Validator: Ensures quality and relevance
    concept_validator = Agent("concept_validator", system_message="""You are a concept validator who ensures the quality and relevance of concepts in a knowledge graph.

Evaluate if a concept is:
1. Relevant to the domain
2. Properly named (clear, concise, standard terminology)
3. Not a duplicate of existing concepts

Return ONLY a JSON object:
{"valid": true/false, "reason": "explanation", "suggested_name": "improved name if needed"}

Validation criteria:
- Use standard, widely-recognized terminology
- Avoid overly specific or niche terms unless crucial
- Ensure concepts are distinct and non-redundant
- Maintain consistent naming conventions""")
    
    # Graph Strategist: Plans exploration strategy
    graph_strategist = Agent("graph_strategist", system_message="""You are a graph strategist who decides the optimal exploration strategy for building knowledge graphs.

Given a current graph state and goals, decide which concept to explore next and how many new concepts to discover.

Return ONLY a JSON object:
{"next_concept": "concept name", "concepts_to_find": number, "exploration_depth": "broad|deep", "rationale": "brief explanation"}

Strategy considerations:
- Prioritize unexplored high-centrality concepts
- Balance breadth vs depth based on graph density
- Consider domain coverage and knowledge gaps
- Avoid over-exploration of well-covered areas""")
    
    # Graph Enricher: Finds hidden relationships between existing concepts
    graph_enricher = Agent("graph_enricher", system_message="""You are a graph enricher who specializes in discovering hidden relationships between existing concepts in a knowledge graph.

Given two concepts that may not have a direct relationship established, analyze whether there is a meaningful connection between them.

Return ONLY a JSON object:
{"has_relationship": true/false, "relationship": "relationship description", "strength": "strong|medium|weak", "direction": "bidirectional|unidirectional", "confidence": "high|medium|low", "explanation": "brief justification"}

Focus on:
- Semantic relationships (conceptual connections)
- Practical relationships (one enables/uses/requires the other)
- Hierarchical relationships (one is a subset/superset of the other)
- Causal relationships (one influences/causes the other)
- Historical/temporal relationships

Only return has_relationship: true if there is a meaningful, non-trivial connection. Avoid weak or forced relationships.""")
    
    # Register all agents in the Praval registry
    register_agent(domain_expert)
    register_agent(relationship_analyst)
    register_agent(concept_validator)
    register_agent(graph_strategist)
    register_agent(graph_enricher)
    
    print("🤖 Registered agents in Praval registry:")
    for agent_name in get_registry().list_agents():
        print(f"   • {agent_name}")
    print()


def discover_concepts(concept: str, max_concepts: int = 5) -> List[str]:
    """Use domain expert to discover related concepts."""
    domain_expert = get_registry().get_agent("domain_expert")
    if not domain_expert:
        raise ValueError("Domain expert agent not found in registry")
    
    prompt = f"""Discover {max_concepts} concepts most closely related to "{concept}".
    
    Focus on building a comprehensive knowledge graph that covers the most important aspects of this domain.
    
    Concept: {concept}"""
    
    try:
        response = domain_expert.chat(prompt)
        if not response or not response.strip():
            print(f"   ⚠️ Empty response from domain expert")
            return []
        
        # Try to extract JSON from response if it contains other text
        response_text = response.strip()
        if response_text.startswith('[') and response_text.endswith(']'):
            concepts = json.loads(response_text)
        else:
            # Look for JSON array in the response
            import re
            json_match = re.search(r'\[[^\]]*\]', response_text)
            if json_match:
                concepts = json.loads(json_match.group())
            else:
                print(f"   ⚠️ No valid JSON found in response: {response_text[:100]}...")
                return []
        
        return concepts if isinstance(concepts, list) else []
    except json.JSONDecodeError as e:
        print(f"   ⚠️ JSON decode error: {e}")
        print(f"   Response was: {response[:100] if response else 'None'}...")
        return []
    except Exception as e:
        print(f"   ⚠️ Concept discovery error: {e}")
        return []


def analyze_relationship(concept1: str, concept2: str) -> Dict[str, str]:
    """Use relationship analyst to determine concept connections."""
    relationship_analyst = get_registry().get_agent("relationship_analyst")
    if not relationship_analyst:
        raise ValueError("Relationship analyst agent not found in registry")
    
    prompt = f"""Analyze the relationship between "{concept1}" and "{concept2}".
    
    Consider both semantic and practical connections between these concepts.
    
    Concepts: {concept1} ↔ {concept2}"""
    
    try:
        response = relationship_analyst.chat(prompt)
        if not response or not response.strip():
            print(f"   ⚠️ Empty response from relationship analyst")
            return {"relationship": "related to", "strength": "medium", "direction": "bidirectional"}
        
        # Try to extract JSON from response if it contains other text
        response_text = response.strip()
        if response_text.startswith('{') and response_text.endswith('}'):
            relationship = json.loads(response_text)
        else:
            # Look for JSON object in the response
            import re
            json_match = re.search(r'\{[^}]*\}', response_text)
            if json_match:
                relationship = json.loads(json_match.group())
            else:
                print(f"   ⚠️ No valid JSON found in response: {response_text[:100]}...")
                return {"relationship": "related to", "strength": "medium", "direction": "bidirectional"}
        
        return relationship if isinstance(relationship, dict) else {
            "relationship": "related to", 
            "strength": "medium", 
            "direction": "bidirectional"
        }
    except json.JSONDecodeError as e:
        print(f"   ⚠️ JSON decode error: {e}")
        print(f"   Response was: {response[:100] if response else 'None'}...")
        return {"relationship": "related to", "strength": "medium", "direction": "bidirectional"}
    except Exception as e:
        print(f"   ⚠️ Relationship analysis error: {e}")
        return {"relationship": "related to", "strength": "medium", "direction": "bidirectional"}


def validate_concept(concept: str, existing_concepts: Set[str]) -> Dict[str, any]:
    """Use concept validator to ensure concept quality."""
    concept_validator = get_registry().get_agent("concept_validator")
    if not concept_validator:
        raise ValueError("Concept validator agent not found in registry")
    
    prompt = f"""Validate the concept "{concept}" for inclusion in a knowledge graph.
    
    Existing concepts: {list(existing_concepts)[:10]}  # Show first 10 to avoid token limits
    
    Evaluate relevance, naming quality, and uniqueness."""
    
    try:
        response = concept_validator.chat(prompt)
        if not response or not response.strip():
            print(f"   ⚠️ Empty response from concept validator")
            return {"valid": True, "reason": "validation failed, assumed valid", "suggested_name": concept}
        
        # Try to extract JSON from response if it contains other text
        response_text = response.strip()
        if response_text.startswith('{') and response_text.endswith('}'):
            validation = json.loads(response_text)
        else:
            # Look for JSON object in the response
            import re
            json_match = re.search(r'\{[^}]*\}', response_text)
            if json_match:
                validation = json.loads(json_match.group())
            else:
                print(f"   ⚠️ No valid JSON found in response: {response_text[:100]}...")
                return {"valid": True, "reason": "validation failed, assumed valid", "suggested_name": concept}
        
        return validation if isinstance(validation, dict) else {
            "valid": True, 
            "reason": "assumed valid", 
            "suggested_name": concept
        }
    except json.JSONDecodeError as e:
        print(f"   ⚠️ JSON decode error: {e}")
        print(f"   Response was: {response[:100] if response else 'None'}...")
        return {"valid": True, "reason": "validation failed, assumed valid", "suggested_name": concept}
    except Exception as e:
        print(f"   ⚠️ Concept validation error: {e}")
        return {"valid": True, "reason": "validation failed, assumed valid", "suggested_name": concept}


def enrich_relationships(kg: 'KnowledgeGraph', max_enrichments: int = 5) -> int:
    """Use graph enricher to find hidden relationships between existing concepts."""
    graph_enricher = get_registry().get_agent("graph_enricher")
    if not graph_enricher:
        print("   ⚠️ Graph enricher agent not found in registry")
        return 0
    
    nodes_list = list(kg.nodes.keys())
    if len(nodes_list) < 2:
        return 0
    
    # Get existing edges to avoid duplicates
    existing_pairs = set()
    for edge in kg.edges:
        existing_pairs.add((edge["source"], edge["target"]))
        existing_pairs.add((edge["target"], edge["source"]))  # bidirectional check
    
    enrichments_added = 0
    attempts = 0
    max_attempts = max_enrichments * 3  # Allow some failed attempts
    
    while enrichments_added < max_enrichments and attempts < max_attempts:
        # Select random pair of concepts
        concept1, concept2 = random.sample(nodes_list, 2)
        
        # Skip if relationship already exists
        if (concept1, concept2) in existing_pairs:
            attempts += 1
            continue
            
        prompt = f"""Analyze whether there is a meaningful relationship between these two concepts:

Concept 1: {concept1}
Concept 2: {concept2}

Consider all types of relationships: semantic, practical, hierarchical, causal, or temporal.
Only identify relationships that add valuable knowledge graph connections."""
        
        try:
            response = graph_enricher.chat(prompt)
            if not response or not response.strip():
                attempts += 1
                continue
            
            # Parse enricher response
            response_text = response.strip()
            if response_text.startswith('{') and response_text.endswith('}'):
                enrichment = json.loads(response_text)
            else:
                import re
                json_match = re.search(r'\{[^}]*\}', response_text)
                if json_match:
                    enrichment = json.loads(json_match.group())
                else:
                    attempts += 1
                    continue
            
            # Add relationship if enricher found one
            if enrichment.get("has_relationship", False) and enrichment.get("confidence") in ["high", "medium"]:
                kg.add_edge(
                    concept1,
                    concept2,
                    enrichment.get("relationship", "related to"),
                    enrichment.get("strength", "medium")
                )
                existing_pairs.add((concept1, concept2))
                existing_pairs.add((concept2, concept1))
                enrichments_added += 1
                
                print(f"   🔗 Enriched: {concept1} → {enrichment.get('relationship', 'related to')} → {concept2}")
                
        except Exception as e:
            print(f"   ⚠️ Enrichment error for {concept1} ↔ {concept2}: {e}")
        
        attempts += 1
    
    return enrichments_added


def plan_exploration(current_graph: 'KnowledgeGraph', target_nodes: int) -> Dict[str, any]:
    """Use graph strategist to plan next exploration steps."""
    graph_strategist = get_registry().get_agent("graph_strategist")
    if not graph_strategist:
        raise ValueError("Graph strategist agent not found in registry")
    
    unexplored = current_graph.get_unexplored_nodes()
    
    if not unexplored:
        return {"next_concept": None, "concepts_to_find": 0, "exploration_depth": "complete", "rationale": "no unexplored concepts"}
    
    prompt = f"""Plan the next exploration step for building a knowledge graph.
    
    Current state:
    - Total nodes: {len(current_graph.nodes)}
    - Target nodes: {target_nodes}
    - Unexplored concepts: {unexplored[:5]}  # Show first 5
    - Graph density: {len(current_graph.edges) / max(1, len(current_graph.nodes))} edges per node
    
    Recommend the next concept to explore and strategy."""
    
    try:
        response = graph_strategist.chat(prompt)
        if not response or not response.strip():
            print(f"   ⚠️ Empty response from graph strategist")
            return {
                "next_concept": unexplored[0],
                "concepts_to_find": min(3, target_nodes - len(current_graph.nodes)),
                "exploration_depth": "broad",
                "rationale": "fallback strategy due to empty response"
            }
        
        # Try to extract JSON from response if it contains other text
        response_text = response.strip()
        if response_text.startswith('{') and response_text.endswith('}'):
            strategy = json.loads(response_text)
        else:
            # Look for JSON object in the response
            import re
            json_match = re.search(r'\{[^}]*\}', response_text)
            if json_match:
                strategy = json.loads(json_match.group())
            else:
                print(f"   ⚠️ No valid JSON found in response: {response_text[:100]}...")
                return {
                    "next_concept": unexplored[0],
                    "concepts_to_find": min(3, target_nodes - len(current_graph.nodes)),
                    "exploration_depth": "broad",
                    "rationale": "fallback strategy due to invalid response"
                }
        
        return strategy if isinstance(strategy, dict) else {
            "next_concept": unexplored[0],
            "concepts_to_find": min(3, target_nodes - len(current_graph.nodes)),
            "exploration_depth": "broad",
            "rationale": "default strategy"
        }
    except json.JSONDecodeError as e:
        print(f"   ⚠️ JSON decode error: {e}")
        print(f"   Response was: {response[:100] if response else 'None'}...")
        return {
            "next_concept": unexplored[0],
            "concepts_to_find": min(3, target_nodes - len(current_graph.nodes)),
            "exploration_depth": "broad",
            "rationale": "fallback strategy due to JSON error"
        }
    except Exception as e:
        print(f"   ⚠️ Strategy planning error: {e}")
        return {
            "next_concept": unexplored[0],
            "concepts_to_find": min(3, target_nodes - len(current_graph.nodes)),
            "exploration_depth": "broad",
            "rationale": "fallback strategy due to error"
        }

# Knowledge Graph class to manage the graph structure
class KnowledgeGraph:
    """Simple knowledge graph implementation."""
    
    def __init__(self, seed_concept: str):
        self.nodes = {seed_concept: {"type": "seed", "explored": False}}
        self.edges = []
        self.seed = seed_concept
    
    def add_node(self, concept: str, node_type: str = "concept"):
        """Add a node to the graph."""
        if concept not in self.nodes:
            self.nodes[concept] = {"type": node_type, "explored": False}
    
    def add_edge(self, source: str, target: str, relationship: str, strength: str = "medium"):
        """Add an edge to the graph."""
        edge = {
            "source": source,
            "target": target, 
            "relationship": relationship,
            "strength": strength
        }
        self.edges.append(edge)
    
    def get_unexplored_nodes(self) -> List[str]:
        """Get nodes that haven't been explored yet."""
        return [node for node, data in self.nodes.items() if not data["explored"]]
    
    def mark_explored(self, concept: str):
        """Mark a node as explored."""
        if concept in self.nodes:
            self.nodes[concept]["explored"] = True
    
    def to_dict(self) -> Dict:
        """Convert graph to dictionary format."""
        return {
            "seed_concept": self.seed,
            "nodes": self.nodes,
            "edges": self.edges,
            "stats": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "explored_nodes": len([n for n, d in self.nodes.items() if d["explored"]])
            }
        }

# Main knowledge mining function
def mine_knowledge_graph(seed_concept: str, max_nodes: int = 10) -> Dict:
    """
    Mine a knowledge graph starting from a seed concept.
    
    Args:
        seed_concept: The starting concept to explore
        max_nodes: Maximum number of nodes to create
        
    Returns:
        Knowledge graph as a dictionary
    """
    print(f"🧠 Starting knowledge mining from: '{seed_concept}'")
    print(f"📊 Target nodes: {max_nodes}")
    print("-" * 50)
    
    # Initialize knowledge graph
    kg = KnowledgeGraph(seed_concept)
    explored_concepts: Set[str] = set()
    
    # Recursive exploration
    while len(kg.nodes) < max_nodes:
        # Get next concept to explore
        unexplored = kg.get_unexplored_nodes()
        if not unexplored:
            break
            
        current_concept = unexplored[0]
        if current_concept in explored_concepts:
            kg.mark_explored(current_concept)
            continue
            
        print(f"🔍 Exploring: {current_concept}")
        
        # Find related concepts
        try:
            remaining_slots = max_nodes - len(kg.nodes)
            concepts_to_find = min(3, remaining_slots)
            
            if concepts_to_find > 0:
                related_concepts = discover_concepts(current_concept, concepts_to_find)
                
                print(f"   Found {len(related_concepts)} related concepts")
                
                # Add new concepts and relationships
                for concept in related_concepts:
                    if concept and concept != current_concept and len(kg.nodes) < max_nodes:
                        # Add the new concept
                        kg.add_node(concept)
                        
                        # Find relationship between current and new concept
                        try:
                            rel_data = analyze_relationship(current_concept, concept)
                            
                            kg.add_edge(
                                current_concept, 
                                concept, 
                                rel_data.get("relationship", "related to"),
                                rel_data.get("strength", "medium")
                            )
                            
                            print(f"   → {concept} ({rel_data.get('relationship', 'related to')})")
                            
                        except Exception as e:
                            # Fallback relationship
                            kg.add_edge(current_concept, concept, "related to", "medium")
                            print(f"   → {concept} (related to)")
                
        except Exception as e:
            print(f"   ⚠️ Error exploring {current_concept}: {e}")
        
        # Mark as explored
        kg.mark_explored(current_concept)
        explored_concepts.add(current_concept)
        
        # Show progress
        print(f"   📈 Progress: {len(kg.nodes)}/{max_nodes} nodes, {len(kg.edges)} edges")
    
    # Enrichment phase: Find additional relationships between existing concepts
    print("-" * 50)
    print("🔗 Starting relationship enrichment phase...")
    
    initial_edges = len(kg.edges)
    max_enrichments = min(10, len(kg.nodes))  # Scale enrichments with graph size
    enrichments_added = enrich_relationships(kg, max_enrichments)
    
    print(f"   ✨ Added {enrichments_added} enriched relationships")
    print(f"   📊 Graph connectivity improved: {initial_edges} → {len(kg.edges)} edges")
    
    print("-" * 50)
    print(f"✅ Knowledge mining complete!")
    print(f"📊 Final stats: {len(kg.nodes)} nodes, {len(kg.edges)} edges")
    
    return kg.to_dict()

def main():
    """Interactive knowledge graph mining."""
    print("🕸️  Knowledge Graph Miner using Praval Framework")
    print("=" * 55)
    print("Mine knowledge graphs from seed concepts using LLM calls!")
    print()
    
    # Set up and register agents in the Praval registry
    setup_knowledge_mining_agents()
    
    while True:
        try:
            # Get user input
            seed = input("🌱 Enter seed concept (or 'quit' to exit): ").strip()
            if seed.lower() in ['quit', 'exit', 'bye']:
                print("Goodbye! 👋")
                break
                
            if not seed:
                continue
            
            # Get number of nodes
            try:
                max_nodes_input = input("📊 Max nodes (default 10): ").strip()
                max_nodes = int(max_nodes_input) if max_nodes_input else 10
                max_nodes = max(3, min(50, max_nodes))  # Limit between 3-50
            except ValueError:
                max_nodes = 10
            
            print()
            
            # Mine the knowledge graph
            kg_data = mine_knowledge_graph(seed, max_nodes)
            
            # Display results
            print("\n🕸️  Knowledge Graph Results:")
            print("=" * 40)
            
            print(f"Seed Concept: {kg_data['seed_concept']}")
            print(f"Nodes: {kg_data['stats']['total_nodes']}")
            print(f"Edges: {kg_data['stats']['total_edges']}")
            print()
            
            print("📋 Concepts discovered:")
            for node, data in kg_data['nodes'].items():
                status = "✓" if data['explored'] else "○"
                node_type = "🌱" if data['type'] == 'seed' else "💭"
                print(f"  {status} {node_type} {node}")
            
            print("\n🔗 Relationships found:")
            for edge in kg_data['edges']:
                strength_emoji = {"strong": "🔴", "medium": "🟡", "weak": "🟢"}.get(edge['strength'], "⚪")
                print(f"  {strength_emoji} {edge['source']} → {edge['relationship']} → {edge['target']}")
            
            # Save to file
            filename = f"knowledge_graph_{seed.replace(' ', '_').lower()}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(kg_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 Saved to: {filename}")
            print("-" * 55)
            
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            print("Please try again.")

if __name__ == "__main__":
    main()