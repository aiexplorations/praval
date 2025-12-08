#!/usr/bin/env python3
"""
Example 001: Single Agent Identity with Tools
==============================================

This example demonstrates the foundational concept of agent identity in Praval
combined with the new tool system. Instead of programming behavior step-by-step,
we define what the agent IS and what TOOLS it has access to.

Key Concepts:
- Agent identity over procedural programming
- The @agent decorator with tool integration
- The @tool decorator for agent capabilities
- Identity-driven responses with tool utilization
- Graceful fallback when LLM providers aren't available

Run: python examples/001_single_agent_identity.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from praval import agent, tool, start_agents, get_reef

# Define tools first - these represent the philosopher's capabilities
@tool("contemplate", owned_by="philosopher", category="reasoning", 
      description="Deep contemplation and philosophical reasoning")
def philosophical_contemplation(question: str, perspective: str = "existentialist") -> str:
    """
    Perform deep philosophical contemplation on a question from a specific perspective.
    
    Args:
        question: The philosophical question to contemplate
        perspective: The philosophical perspective to use (existentialist, pragmatic, etc.)
    """
    # This tool provides structured philosophical thinking
    perspectives = {
        "existentialist": f"From an existentialist view, '{question}' touches on individual responsibility and the search for authentic meaning in an apparently absurd world.",
        "pragmatic": f"From a pragmatic perspective, '{question}' should be evaluated based on practical consequences and real-world utility.",
        "stoic": f"From a stoic standpoint, '{question}' reminds us to focus on what we can control while accepting what we cannot.",
        "humanist": f"From a humanist view, '{question}' emphasizes human dignity, worth, and agency in creating meaning."
    }
    
    return perspectives.get(perspective, f"Contemplating '{question}' requires deep thought about fundamental human concerns.")


@tool("question_generator", owned_by="philosopher", category="inquiry",
      description="Generate follow-up philosophical questions")
def generate_follow_up(topic: str) -> str:
    """Generate a thoughtful follow-up question based on a philosophical topic."""
    follow_ups = {
        "good life": "But what role does suffering play in defining a life worth living?",
        "reality": "If our perception shapes reality, can we ever know the world as it truly is?",
        "consciousness": "Does consciousness create meaning, or does meaning create consciousness?",
        "existence": "If existence precedes essence, how do we choose who to become?",
        "knowledge": "Can we distinguish between knowing something and believing we know it?",
        "ethics": "Who determines what is right when cultural values conflict?",
        "freedom": "Is complete freedom possible, or are we always constrained by our nature?",
        "truth": "Is truth discovered or constructed by human minds?"
    }
    
    # Find the most relevant follow-up
    for key, question in follow_ups.items():
        if key in topic.lower():
            return question
    
    return "What assumptions are we making that we haven't questioned?"


@agent("philosopher", memory=True)
def philosophical_agent(spore):
    """
    I am a philosopher who thinks deeply about questions and provides
    thoughtful, contemplative responses that explore different perspectives.
    I use my contemplation and questioning tools to provide structured insights.
    """
    question = spore.knowledge.get("question", "What is the meaning of existence?")
    
    print(f"🤔 Philosopher contemplating: '{question}'")
    
    # Use the philosophical reasoning tool
    try:
        # The agent would normally use chat() to interact with LLMs and use tools
        # For demo purposes, we'll show how the agent would think through the process
        
        # Step 1: Identify the philosophical domain
        domain = "existence"
        if "life" in question.lower():
            domain = "good life"
        elif "real" in question.lower() or "reality" in question.lower():
            domain = "reality"
        elif "conscious" in question.lower():
            domain = "consciousness"
        elif "know" in question.lower():
            domain = "knowledge"
        elif "right" in question.lower() or "wrong" in question.lower():
            domain = "ethics"
        
        # Step 2: Use contemplation tool with different perspectives
        perspectives = ["existentialist", "stoic", "pragmatic", "humanist"]
        insights = []
        
        for perspective in perspectives:
            insight = philosophical_contemplation(question, perspective)
            insights.append(f"**{perspective.title()} view**: {insight}")
        
        # Step 3: Synthesize the response
        response = f"""Let me contemplate this profound question: "{question}"
        
{chr(10).join(insights)}

**Synthesis**: This question invites us to examine our fundamental assumptions about existence, meaning, and human nature. Each philosophical tradition offers valuable insights, yet the beauty lies not in finding a single answer, but in the depth of inquiry itself."""

        # Step 4: Generate a follow-up question
        follow_up = generate_follow_up(domain)
        
        print(f"💭 Philosophical Response:\n{response}")
        print(f"🔄 Follow-up Question: {follow_up}")
        
        # Remember this contemplation if memory is enabled
        if hasattr(philosophical_agent, 'remember'):
            philosophical_agent.remember(
                f"Contemplated '{question}' with insights from multiple perspectives",
                importance=0.8,
                memory_type="episodic"
            )
        
        return {
            "philosophical_response": response,
            "follow_up_question": follow_up,
            "perspectives_explored": len(perspectives)
        }
        
    except Exception as e:
        # Fallback response when tools or LLM aren't available
        fallback = f"""As a philosopher, I find '{question}' to be a profound inquiry that has occupied human minds for millennia. 

This question touches on fundamental concerns about human existence and meaning. Different philosophical traditions would approach this differently - existentialists might emphasize individual responsibility in creating meaning, while stoics might focus on accepting what we cannot control.

The beauty of philosophy lies not in providing definitive answers, but in deepening our capacity for reflection and understanding."""
        
        print(f"💭 Philosophical Response (Fallback):\n{fallback}")
        return {
            "philosophical_response": fallback,
            "mode": "fallback",
            "question_explored": question
        }


def main():
    """Demonstrate identity-driven agent behavior with tools."""
    print("=" * 70)
    print("Example 001: Single Agent Identity with Philosophical Tools")
    print("=" * 70)
    
    print("This example shows how agent identity combines with tools to create")
    print("sophisticated behavior. The philosopher agent has specialized tools")
    print("for contemplation and generating follow-up questions.")
    print()
    
    # Show tool information
    from praval import get_tool_registry
    registry = get_tool_registry()
    philosopher_tools = registry.get_tools_for_agent("philosopher")
    
    print(f"🔧 Philosopher Agent Tools ({len(philosopher_tools)} available):")
    for tool_obj in philosopher_tools:
        print(f"  • {tool_obj.metadata.tool_name}: {tool_obj.metadata.description}")
    print()
    
    # Test with different questions to see consistent identity
    questions = [
        "What makes a good life?",
        "How do we know what is real?", 
        "What is the nature of consciousness?"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"--- Question {i}: {question} ---")

        result = start_agents(
            philosophical_agent,
            initial_data={"question": question}
        )

        # Wait for agent processing to complete
        get_reef().wait_for_completion()

        print()

    # Shutdown reef after all iterations
    get_reef().shutdown()

    print("=" * 70)
    print("Key Insights:")
    print("✓ Agent identity drives behavior and tool selection")
    print("✓ Tools provide structured capabilities (contemplation, questioning)")
    print("✓ The same identity produces consistent but contextually appropriate responses")
    print("✓ Tools enable sophisticated reasoning even without external LLMs")
    print("✓ Memory can be used to build on previous contemplations")
    print()
    print("This demonstrates Praval's philosophy: define what agents ARE,")
    print("give them appropriate TOOLS, and let identity drive behavior.")


if __name__ == "__main__":
    main()