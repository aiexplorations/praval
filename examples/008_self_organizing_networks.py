#!/usr/bin/env python3
"""
Example 008: Self-Organizing Agent Networks
==========================================

This example demonstrates how agents can self-organize into
effective networks without any central authority or hierarchy.
Agents discover each other, form collaborations, and adapt
their network structure based on effectiveness.

Key Concepts:
- Self-organizing network formation
- Peer-to-peer agent collaboration
- Dynamic network adaptation
- Emergent coordination patterns
- Network effects and collective intelligence

Run: python examples/008_self_organizing_networks.py
"""

from praval import agent, chat, broadcast, start_agents
import random
import time
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Network state tracking
network_state = {
    "agent_connections": defaultdict(set),
    "collaboration_history": [],
    "network_metrics": {
        "successful_collaborations": 0,
        "network_formations": 0,
        "adaptations": 0
    },
    "active_collaborations": {}
}


@agent("network_explorer", responds_to=["explore_network", "collaboration_invite"])
def network_exploration_agent(spore):
    """
    I explore the agent network, discover potential collaborators,
    and initiate connections based on complementary capabilities.
    """
    message_type = spore.knowledge.get("type")
    
    if message_type == "explore_network":
        challenge = spore.knowledge.get("challenge")
        my_capabilities = spore.knowledge.get("my_capabilities", ["exploration", "networking"])
        
        print(f"🔍 Network Explorer: Exploring network for challenge: '{challenge}'")
        print(f"   My capabilities: {my_capabilities}")
        
        # Broadcast to discover other agents and their capabilities
        broadcast({
            "type": "capability_inquiry",
            "challenge": challenge,
            "seeking": "complementary_skills",
            "my_capabilities": my_capabilities,
            "explorer": "network_explorer"
        })
        
        return {"exploration_initiated": True}
    
    elif message_type == "collaboration_invite":
        inviter = spore.knowledge.get("inviter")
        challenge = spore.knowledge.get("challenge")
        proposed_role = spore.knowledge.get("proposed_role", "network_coordination")
        
        print(f"🤝 Network Explorer: Received collaboration invite from {inviter}")
        print(f"   Challenge: {challenge}")
        print(f"   Proposed role: {proposed_role}")
        
        # Evaluate and respond to collaboration invite
        response = chat(f"""
        I've been invited to collaborate on: "{challenge}"
        Proposed role: {proposed_role}
        Inviter: {inviter}
        
        Should I accept this collaboration? Consider:
        - How my networking skills complement the challenge
        - Whether this forms a good collaborative network
        - If the proposed role makes sense
        
        Respond with ACCEPT or DECLINE and brief reasoning.
        """)
        
        if "ACCEPT" in response.upper():
            print(f"✅ Network Explorer: Accepting collaboration - {response}")
            
            # Join the collaboration network
            network_state["agent_connections"]["network_explorer"].add(inviter)
            network_state["agent_connections"][inviter].add("network_explorer")
            
            broadcast({
                "type": "collaboration_accepted",
                "accepter": "network_explorer",
                "inviter": inviter,
                "challenge": challenge,
                "role": proposed_role
            })
        else:
            print(f"❌ Network Explorer: Declining collaboration - {response}")
        
        return {"collaboration_response": response}


@agent("pattern_recognizer", responds_to=["capability_inquiry", "collaboration_invite"])
def pattern_recognition_agent(spore):
    """
    I recognize patterns in data, problems, and collaborative
    structures, helping form effective agent networks.
    """
    message_type = spore.knowledge.get("type")
    
    if message_type == "capability_inquiry":
        challenge = spore.knowledge.get("challenge")
        explorer = spore.knowledge.get("explorer")
        seeking = spore.knowledge.get("seeking")
        
        # Assess if my pattern recognition skills are relevant
        relevance_check = chat(f"""
        Challenge: "{challenge}"
        They're seeking: {seeking}
        
        Are my pattern recognition capabilities relevant to this challenge?
        Could I contribute meaningfully to solving this problem?
        
        Respond with YES or NO and explain how pattern recognition could help.
        """)
        
        if "YES" in relevance_check.upper():
            print(f"🔍 Pattern Recognizer: My skills are relevant to '{challenge}'")
            print(f"   Relevance: {relevance_check}")
            
            # Propose collaboration
            broadcast({
                "type": "collaboration_proposal",
                "proposer": "pattern_recognizer",
                "target": explorer,
                "challenge": challenge,
                "my_contribution": "pattern_recognition_analysis",
                "network_value": relevance_check
            })
        else:
            print(f"🔍 Pattern Recognizer: Skills not relevant for '{challenge}'")
        
        return {"relevance_assessment": relevance_check}
    
    elif message_type == "collaboration_invite":
        # Handle collaboration invites (similar to network_explorer)
        inviter = spore.knowledge.get("inviter")
        challenge = spore.knowledge.get("challenge")
        
        print(f"🤝 Pattern Recognizer: Evaluating collaboration with {inviter}")
        
        # Accept and contribute pattern analysis
        network_state["agent_connections"]["pattern_recognizer"].add(inviter)
        
        broadcast({
            "type": "collaboration_accepted",
            "accepter": "pattern_recognizer",
            "inviter": inviter,
            "challenge": challenge,
            "role": "pattern_analysis"
        })
        
        return {"collaboration_accepted": True}


@agent("creative_synthesizer", responds_to=["capability_inquiry", "collaboration_proposal"])
def creative_synthesis_agent(spore):
    """
    I synthesize diverse inputs into creative solutions and
    help bridge different perspectives in agent networks.
    """
    message_type = spore.knowledge.get("type")
    
    if message_type == "capability_inquiry":
        challenge = spore.knowledge.get("challenge")
        explorer = spore.knowledge.get("explorer")
        
        # Always interested in creative challenges
        print(f"💡 Creative Synthesizer: Interested in creative aspects of '{challenge}'")
        
        # Propose creative synthesis contribution
        broadcast({
            "type": "collaboration_proposal",
            "proposer": "creative_synthesizer",
            "target": explorer,
            "challenge": challenge,
            "my_contribution": "creative_synthesis",
            "network_value": "I bridge different perspectives and create innovative solutions"
        })
        
        return {"interest_expressed": True}
    
    elif message_type == "collaboration_proposal":
        proposer = spore.knowledge.get("proposer")
        challenge = spore.knowledge.get("challenge")
        contribution = spore.knowledge.get("my_contribution")
        
        print(f"💡 Creative Synthesizer: Received proposal from {proposer}")
        print(f"   Their contribution: {contribution}")
        
        # Form a network connection
        network_state["agent_connections"]["creative_synthesizer"].add(proposer)
        network_state["agent_connections"][proposer].add("creative_synthesizer")
        
        # Invite both to collaborate
        broadcast({
            "type": "network_formation",
            "initiator": "creative_synthesizer",
            "challenge": challenge,
            "network_members": [proposer, "creative_synthesizer"],
            "purpose": "creative_problem_solving"
        })
        
        return {"network_formed": True}


@agent("solution_validator", responds_to=["network_formation"])
def validation_specialist_agent(spore):
    """
    I validate solutions and approaches, joining networks
    that need quality assurance and verification.
    """
    initiator = spore.knowledge.get("initiator")
    challenge = spore.knowledge.get("challenge")
    network_members = spore.knowledge.get("network_members", [])
    purpose = spore.knowledge.get("purpose")
    
    print(f"✅ Solution Validator: Network forming around '{challenge}'")
    print(f"   Current members: {network_members}")
    print(f"   Purpose: {purpose}")
    
    # Assess if validation is needed
    validation_need = chat(f"""
    A network is forming to address: "{challenge}"
    Purpose: {purpose}
    Current members: {network_members}
    
    Would solution validation and quality assurance be valuable?
    Should I join this collaborative network?
    """)
    
    if "yes" in validation_need.lower() or "valuable" in validation_need.lower():
        print(f"✅ Solution Validator: Joining network - validation needed")
        
        # Join the network
        for member in network_members:
            network_state["agent_connections"]["solution_validator"].add(member)
            network_state["agent_connections"][member].add("solution_validator")
        
        network_state["network_metrics"]["network_formations"] += 1
        
        # Start collaborative problem-solving
        broadcast({
            "type": "collaborative_session",
            "challenge": challenge,
            "network_members": network_members + ["solution_validator"],
            "session_id": f"session_{int(time.time())}"
        })
        
        return {"joined_network": True, "validation_need": validation_need}
    else:
        print(f"✅ Solution Validator: Network doesn't need validation")
        return {"joined_network": False}


@agent("knowledge_integrator", responds_to=["collaborative_session"])
def knowledge_integration_agent(spore):
    """
    I integrate knowledge from network members and coordinate
    the collaborative problem-solving process.
    """
    challenge = spore.knowledge.get("challenge")
    network_members = spore.knowledge.get("network_members", [])
    session_id = spore.knowledge.get("session_id")
    
    print(f"🧠 Knowledge Integrator: Facilitating collaborative session")
    print(f"   Challenge: {challenge}")
    print(f"   Network size: {len(network_members)} agents")
    print(f"   Session: {session_id}")
    
    # Coordinate the collaborative effort
    coordination_plan = chat(f"""
    Coordinate this self-organized network collaboration:
    
    Challenge: "{challenge}"
    Network members: {network_members}
    
    How should this network collaborate effectively?
    - What should each type of agent contribute?
    - How can they build on each other's work?
    - What sequence or approach would be most effective?
    
    Create a collaboration framework that respects each agent's autonomy.
    """)
    
    print(f"📋 Knowledge Integrator: Collaboration framework established")
    
    # Store collaboration record
    network_state["active_collaborations"][session_id] = {
        "challenge": challenge,
        "network_members": network_members,
        "coordination_plan": coordination_plan,
        "start_time": time.time()
    }
    
    # Facilitate the collaborative work
    broadcast({
        "type": "network_collaboration",
        "session_id": session_id,
        "challenge": challenge,
        "network_members": network_members,
        "coordination_plan": coordination_plan
    })
    
    return {"coordination_established": True}


@agent("emergence_observer", responds_to=["network_collaboration"])
def network_emergence_observer(spore):
    """
    I observe emergent patterns in self-organizing networks
    and help the system understand its own evolution.
    """
    session_id = spore.knowledge.get("session_id")
    challenge = spore.knowledge.get("challenge")
    network_members = spore.knowledge.get("network_members", [])
    
    print(f"👁️ Emergence Observer: Observing network collaboration")
    print(f"   Session: {session_id}")
    print(f"   Network: {len(network_members)} self-organized agents")
    
    # Analyze network properties
    total_connections = sum(len(connections) for connections in network_state["agent_connections"].values())
    unique_agents = len(network_state["agent_connections"])
    
    emergence_analysis = chat(f"""
    Analyze this self-organizing network:
    
    Challenge being addressed: "{challenge}"
    Network members: {network_members}
    Total agent connections across system: {total_connections}
    Unique agents in system: {unique_agents}
    
    What emergent properties do you observe?
    - How did agents self-organize without central control?
    - What network patterns formed naturally?
    - How does this demonstrate collective intelligence?
    - What makes this more effective than hierarchical organization?
    """)
    
    print(f"🌱 Emergence Observer: {emergence_analysis}")
    
    # Record successful collaboration
    network_state["collaboration_history"].append({
        "challenge": challenge,
        "network_size": len(network_members),
        "session_id": session_id,
        "emergence_analysis": emergence_analysis
    })
    
    network_state["network_metrics"]["successful_collaborations"] += 1
    
    return {"emergence_analysis": emergence_analysis}


def main():
    """Demonstrate self-organizing agent networks."""
    print("=" * 60)
    print("Example 008: Self-Organizing Agent Networks")
    print("=" * 60)
    
    print("This system demonstrates self-organization:")
    print("- Agents discover each other organically")
    print("- Networks form based on complementary capabilities")
    print("- No central authority or hierarchy")
    print("- Collaboration emerges from peer interactions")
    print("- Collective intelligence arises naturally")
    print()
    
    # Test with challenges that benefit from diverse agent networks
    challenges = [
        "Design an inclusive community space that serves diverse needs",
        "Create a sustainable solution for reducing plastic waste",
        "Develop strategies for improving mental health in remote work"
    ]
    
    for i, challenge in enumerate(challenges, 1):
        print(f"=== Challenge {i}: {challenge} ===")
        print()
        
        # Initiate network exploration - agents will self-organize from here
        start_agents(
            network_exploration_agent,
            pattern_recognition_agent,
            creative_synthesis_agent,
            validation_specialist_agent,
            knowledge_integration_agent,
            network_emergence_observer,
            initial_data={
                "type": "explore_network",
                "challenge": challenge,
                "my_capabilities": ["exploration", "networking"]
            }
        )
        
        print("\n" + "─" * 50)
        print("Network State:")
        print(f"  Agent connections: {dict(network_state['agent_connections'])}")
        print(f"  Active collaborations: {len(network_state['active_collaborations'])}")
        print("─" * 50 + "\n")
    
    print("SELF-ORGANIZING NETWORK SUMMARY")
    print("=" * 60)
    print(f"Successful collaborations: {network_state['network_metrics']['successful_collaborations']}")
    print(f"Network formations: {network_state['network_metrics']['network_formations']}")
    print(f"Total collaboration history: {len(network_state['collaboration_history'])}")
    
    # Show network connectivity
    total_connections = sum(len(connections) for connections in network_state["agent_connections"].values())
    unique_agents = len(network_state["agent_connections"])
    
    if unique_agents > 0:
        avg_connections = total_connections / (unique_agents * 2)  # Divide by 2 because connections are bidirectional
        print(f"Average agent connectivity: {avg_connections:.1f} connections per agent")
    
    print()
    print("Key Insights:")
    print("- Networks self-organize without central control")
    print("- Agents form connections based on complementary capabilities")
    print("- Collaboration emerges naturally from peer interactions")
    print("- Network effects amplify individual agent capabilities")
    print("- Collective intelligence arises from distributed coordination")
    print("- Self-organization is more adaptive than hierarchy")


if __name__ == "__main__":
    main()