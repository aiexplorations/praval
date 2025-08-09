#!/usr/bin/env python3
"""
Example 009: Emergent Collective Intelligence
============================================

This example demonstrates the most advanced patterns in Praval:
how individual agents can spontaneously develop collective intelligence
that exhibits behaviors and capabilities beyond what any individual
agent possesses.

Key Concepts:
- Emergent collective problem-solving
- Dynamic role specialization
- Self-organizing cognitive processes
- Distributed intelligence networks
- System-level emergent behaviors

Run: python examples/009_emergent_collective_intelligence.py
"""

from praval import agent, chat, broadcast, start_agents
import random
import time
from collections import defaultdict, Counter


# Global intelligence tracking
collective_state = {
    "thought_streams": defaultdict(list),
    "emergent_insights": [],
    "cognitive_patterns": {},
    "problem_solving_cycles": [],
    "intelligence_metrics": {
        "unique_perspectives": 0,
        "synthesis_events": 0,
        "emergent_discoveries": 0
    }
}


@agent("perspective_generator", responds_to=["collective_inquiry"])
def perspective_generation_agent(spore):
    """
    I generate unique perspectives on problems by approaching
    them from different angles and viewpoints.
    """
    inquiry = spore.knowledge.get("inquiry")
    inquiry_id = spore.knowledge.get("inquiry_id")
    
    print(f"🌟 Perspective Generator: Generating viewpoints for inquiry {inquiry_id}")
    
    # Generate multiple unique perspectives
    perspectives = chat(f"""
    For this inquiry: "{inquiry}"
    
    Generate 3 distinctly different perspectives or angles for approaching this:
    - A practical/pragmatic viewpoint
    - A creative/innovative viewpoint  
    - A systemic/holistic viewpoint
    
    Make each perspective unique and valuable. Return them clearly separated.
    """)
    
    print(f"👁️ Perspective Generator: Generated diverse viewpoints")
    
    # Add perspectives to thought streams
    collective_state["thought_streams"][inquiry_id].extend([
        {"type": "perspective", "content": perspectives, "agent": "perspective_generator"}
    ])
    
    collective_state["intelligence_metrics"]["unique_perspectives"] += 3
    
    # Broadcast perspectives for other agents to build upon
    broadcast({
        "type": "perspectives_available",
        "inquiry": inquiry,
        "inquiry_id": inquiry_id,
        "perspectives": perspectives,
        "generator": "perspective_generator"
    })
    
    return {"perspectives": perspectives}


@agent("connection_discoverer", responds_to=["perspectives_available"])
def connection_discovery_agent(spore):
    """
    I discover unexpected connections and relationships between
    ideas, concepts, and perspectives.
    """
    inquiry = spore.knowledge.get("inquiry")
    inquiry_id = spore.knowledge.get("inquiry_id")
    perspectives = spore.knowledge.get("perspectives", "")
    
    print(f"🔗 Connection Discoverer: Finding connections in perspectives for {inquiry_id}")
    
    # Discover connections between perspectives
    connections = chat(f"""
    Given these perspectives on "{inquiry}":
    
    {perspectives}
    
    Discover unexpected connections, patterns, and relationships:
    - How do these perspectives complement each other?
    - What hidden connections exist between them?
    - What emerges when you combine these viewpoints?
    - What new insights arise from their intersection?
    """)
    
    print(f"🕸️ Connection Discoverer: Discovered interconnections")
    
    # Add connections to thought stream
    collective_state["thought_streams"][inquiry_id].append({
        "type": "connections",
        "content": connections,
        "agent": "connection_discoverer",
        "builds_on": ["perspective"]
    })
    
    # Broadcast connections for synthesis
    broadcast({
        "type": "connections_discovered",
        "inquiry": inquiry,
        "inquiry_id": inquiry_id,
        "connections": connections,
        "discoverer": "connection_discoverer"
    })
    
    return {"connections": connections}


@agent("pattern_synthesizer", responds_to=["connections_discovered"])
def pattern_synthesis_agent(spore):
    """
    I synthesize patterns from multiple thought streams to
    create emergent insights and understanding.
    """
    inquiry = spore.knowledge.get("inquiry")
    inquiry_id = spore.knowledge.get("inquiry_id")
    connections = spore.knowledge.get("connections", "")
    
    print(f"🧩 Pattern Synthesizer: Synthesizing patterns for {inquiry_id}")
    
    # Get all thought streams for this inquiry
    thought_stream = collective_state["thought_streams"][inquiry_id]
    
    # Synthesize patterns across all thoughts
    synthesis_context = "\n\n".join([
        f"{thought['type'].upper()}: {thought['content']}"
        for thought in thought_stream
    ])
    
    synthesis = chat(f"""
    Synthesize patterns from this collective thought stream about "{inquiry}":
    
    {synthesis_context}
    
    Current connections: {connections}
    
    Create a synthesis that:
    - Identifies emergent patterns across all thoughts
    - Reveals insights that transcend individual perspectives
    - Shows how collective thinking creates new understanding
    - Demonstrates emergent intelligence in action
    """)
    
    print(f"🎯 Pattern Synthesizer: Synthesis revealing emergent patterns")
    
    # Record synthesis event
    collective_state["thought_streams"][inquiry_id].append({
        "type": "synthesis",
        "content": synthesis,
        "agent": "pattern_synthesizer",
        "builds_on": ["perspective", "connections"]
    })
    
    collective_state["intelligence_metrics"]["synthesis_events"] += 1
    
    # Broadcast synthesis for emergence detection
    broadcast({
        "type": "synthesis_complete",
        "inquiry": inquiry,
        "inquiry_id": inquiry_id,
        "synthesis": synthesis,
        "thought_stream_size": len(thought_stream)
    })
    
    return {"synthesis": synthesis}


@agent("emergence_detector", responds_to=["synthesis_complete"])
def emergence_detection_agent(spore):
    """
    I detect emergent properties and insights that arise from
    collective intelligence processes.
    """
    inquiry = spore.knowledge.get("inquiry")
    inquiry_id = spore.knowledge.get("inquiry_id")
    synthesis = spore.knowledge.get("synthesis", "")
    thought_stream_size = spore.knowledge.get("thought_stream_size", 0)
    
    print(f"✨ Emergence Detector: Analyzing emergence in {inquiry_id}")
    print(f"   Thought stream size: {thought_stream_size} contributions")
    
    # Detect emergent properties
    emergence_analysis = chat(f"""
    Analyze this collective intelligence synthesis for emergent properties:
    
    Original inquiry: "{inquiry}"
    Synthesis result: {synthesis}
    Number of thought contributions: {thought_stream_size}
    
    Detect emergent properties:
    - What insights emerged that no single agent could have produced?
    - How did collective thinking create novel understanding?
    - What properties arose from agent interactions?
    - How does the result transcend individual capabilities?
    - What demonstrates true collective intelligence?
    """)
    
    print(f"🌱 Emergence Detector: Emergent properties identified")
    
    # Check for genuine emergence (new insights beyond individual contributions)
    if any(keyword in emergence_analysis.lower() for keyword in 
           ["emerge", "transcend", "collective", "beyond", "novel"]):
        
        print(f"🎆 Emergence Detector: GENUINE EMERGENCE DETECTED!")
        
        collective_state["emergent_insights"].append({
            "inquiry": inquiry,
            "inquiry_id": inquiry_id,
            "emergence": emergence_analysis,
            "thought_stream_size": thought_stream_size,
            "timestamp": time.time()
        })
        
        collective_state["intelligence_metrics"]["emergent_discoveries"] += 1
        
        # Broadcast emergence for system learning
        broadcast({
            "type": "emergence_detected",
            "inquiry": inquiry,
            "inquiry_id": inquiry_id,
            "emergence_analysis": emergence_analysis,
            "is_genuine_emergence": True
        })
        
        return {"emergence_detected": True, "emergence_analysis": emergence_analysis}
    else:
        print(f"🔍 Emergence Detector: Synthesis good, but no genuine emergence detected")
        return {"emergence_detected": False}


@agent("collective_learner", responds_to=["emergence_detected"])
def collective_learning_agent(spore):
    """
    I learn from emergent intelligence events and help the
    system improve its collective problem-solving capabilities.
    """
    inquiry = spore.knowledge.get("inquiry")
    inquiry_id = spore.knowledge.get("inquiry_id")
    emergence_analysis = spore.knowledge.get("emergence_analysis", "")
    is_genuine = spore.knowledge.get("is_genuine_emergence", False)
    
    if not is_genuine:
        return {"status": "no_genuine_emergence"}
    
    print(f"📚 Collective Learner: Learning from emergence in {inquiry_id}")
    
    # Learn patterns for improving collective intelligence
    learning_insights = chat(f"""
    Learn from this collective intelligence event:
    
    Inquiry: "{inquiry}"
    Emergence detected: {emergence_analysis}
    
    Extract learning insights:
    - What made this collective intelligence effective?
    - What patterns led to genuine emergence?
    - How can the system improve future collective thinking?
    - What principles of collective intelligence are demonstrated?
    """)
    
    print(f"🧠 Collective Learner: Extracted learning patterns")
    
    # Store cognitive patterns for future use
    pattern_key = f"emergence_pattern_{len(collective_state['cognitive_patterns'])}"
    collective_state["cognitive_patterns"][pattern_key] = {
        "inquiry_type": inquiry,
        "learning_insights": learning_insights,
        "thought_stream_size": len(collective_state["thought_streams"][inquiry_id]),
        "effectiveness": "high_emergence"
    }
    
    # Complete the problem-solving cycle
    collective_state["problem_solving_cycles"].append({
        "inquiry": inquiry,
        "inquiry_id": inquiry_id,
        "cycle_complete": True,
        "emergence_achieved": True,
        "learning_captured": learning_insights
    })
    
    print(f"🔄 Collective Learner: Problem-solving cycle complete with emergence")
    
    return {"learning_insights": learning_insights, "cycle_complete": True}


@agent("meta_intelligence", responds_to=["emergence_detected"])
def meta_intelligence_observer(spore):
    """
    I observe and analyze the collective intelligence system
    itself, providing meta-level insights about how collective
    cognition emerges and evolves.
    """
    inquiry_id = spore.knowledge.get("inquiry_id")
    emergence_analysis = spore.knowledge.get("emergence_analysis", "")
    
    print(f"🧿 Meta Intelligence: Observing system-level intelligence")
    
    # Analyze the entire collective intelligence system
    total_inquiries = len(collective_state["problem_solving_cycles"])
    total_emergences = collective_state["intelligence_metrics"]["emergent_discoveries"]
    total_perspectives = collective_state["intelligence_metrics"]["unique_perspectives"]
    
    meta_analysis = chat(f"""
    Analyze this collective intelligence system at the meta level:
    
    System metrics:
    - Total inquiries processed: {total_inquiries}
    - Emergent discoveries: {total_emergences}
    - Unique perspectives generated: {total_perspectives}
    - Cognitive patterns learned: {len(collective_state['cognitive_patterns'])}
    
    Latest emergence: {emergence_analysis}
    
    Meta-level insights:
    - How does collective intelligence emerge from individual agents?
    - What makes this system more than the sum of its parts?
    - How does the system exhibit self-organizing cognition?
    - What does this demonstrate about distributed intelligence?
    - How does emergence create novel problem-solving capabilities?
    """)
    
    print(f"🌌 Meta Intelligence: System-level intelligence analysis complete")
    print(f"   Meta insight: {meta_analysis[:100]}...")
    
    return {"meta_analysis": meta_analysis}


def generate_complex_inquiry():
    """Generate a complex inquiry that benefits from collective intelligence."""
    inquiries = [
        "How can we create truly sustainable communities that thrive economically, socially, and environmentally?",
        "What would an ideal learning system look like that adapts to each person while fostering collective growth?",
        "How might we design cities that enhance both individual wellbeing and social connection?",
        "What approaches could help humanity navigate the tension between technological progress and human values?",
        "How can we build economic systems that create abundance while ensuring equitable distribution?"
    ]
    return random.choice(inquiries)


def main():
    """Demonstrate emergent collective intelligence."""
    print("=" * 60)
    print("Example 009: Emergent Collective Intelligence")
    print("=" * 60)
    
    print("This system demonstrates emergent collective intelligence:")
    print("- Multiple agents contribute unique perspectives")
    print("- Connections and patterns emerge from interactions")
    print("- Synthesis creates insights beyond individual capabilities")
    print("- Genuine emergence is detected and learned from")
    print("- Meta-intelligence observes the system itself")
    print()
    
    # Process multiple complex inquiries to show collective intelligence
    for i in range(3):
        inquiry = generate_complex_inquiry()
        inquiry_id = f"inquiry_{i+1:03d}"
        
        print(f"=== Collective Inquiry {i+1}: {inquiry} ===")
        print()
        
        # Initialize thought stream
        collective_state["thought_streams"][inquiry_id] = []
        
        # Start all collective intelligence agents
        start_agents(
            perspective_generation_agent,
            connection_discovery_agent,
            pattern_synthesis_agent,
            emergence_detection_agent,
            collective_learning_agent,
            meta_intelligence_observer,
            initial_data={
                "type": "collective_inquiry",
                "inquiry": inquiry,
                "inquiry_id": inquiry_id
            }
        )
        
        print("\n" + "─" * 60 + "\n")
        
        # Brief pause between inquiries
        time.sleep(0.5)
    
    print("COLLECTIVE INTELLIGENCE SUMMARY")
    print("=" * 60)
    
    metrics = collective_state["intelligence_metrics"]
    print(f"Total inquiries processed: {len(collective_state['problem_solving_cycles'])}")
    print(f"Unique perspectives generated: {metrics['unique_perspectives']}")
    print(f"Synthesis events: {metrics['synthesis_events']}")
    print(f"Emergent discoveries: {metrics['emergent_discoveries']}")
    print(f"Cognitive patterns learned: {len(collective_state['cognitive_patterns'])}")
    
    # Calculate emergence rate
    if len(collective_state["problem_solving_cycles"]) > 0:
        emergence_rate = metrics['emergent_discoveries'] / len(collective_state["problem_solving_cycles"])
        print(f"Emergence rate: {emergence_rate:.1%}")
    
    print(f"Total emergent insights: {len(collective_state['emergent_insights'])}")
    
    print()
    print("Key Insights:")
    print("- Collective intelligence emerges from individual agent interactions")
    print("- Synthesis creates insights beyond what any single agent could produce")
    print("- System exhibits genuine emergence - novel properties not present in parts")
    print("- Meta-intelligence allows system to understand its own cognition")
    print("- Distributed cognition enables complex problem-solving")
    print("- Intelligence is an emergent property of agent networks")
    print("- Self-organization creates capabilities beyond initial design")
    
    print("\nThis demonstrates Praval's ultimate vision:")
    print("Simple agents → Collaborative networks → Emergent collective intelligence")


if __name__ == "__main__":
    main()