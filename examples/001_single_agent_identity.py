#!/usr/bin/env python3
"""
Example 001: Single Agent Identity
==================================

This example demonstrates the foundational concept of agent identity in Praval.
Instead of programming behavior step-by-step, we define what the agent IS,
and let that identity drive its behavior.

Key Concepts:
- Agent identity over procedural programming
- The @agent decorator
- Identity-driven responses
- Simple chat interaction

Run: python examples/001_single_agent_identity.py
"""

from praval import agent, chat, start_agents


@agent("philosopher")
def philosophical_agent(spore):
    """
    I am a philosopher who thinks deeply about questions and provides
    thoughtful, contemplative responses that explore different perspectives.
    """
    question = spore.knowledge.get("question", "What is the meaning of existence?")
    
    # The agent's identity guides its response style
    response = chat(f"""
    As a philosopher, I contemplate this question deeply: "{question}"
    
    Provide a thoughtful, contemplative response that:
    - Explores multiple perspectives
    - Raises deeper questions
    - Shows philosophical depth
    - Is accessible yet profound
    """)
    
    print(f"🤔 Philosopher: {response}")
    return {"philosophical_response": response}


def main():
    """Demonstrate identity-driven agent behavior."""
    print("=" * 60)
    print("Example 001: Single Agent Identity")
    print("=" * 60)
    
    print("Demonstrating how agent identity drives behavior...")
    print()
    
    # Test with different questions to see consistent identity
    questions = [
        "What makes a good life?",
        "How do we know what is real?",
        "What is the nature of consciousness?"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"Question {i}: {question}")
        
        result = start_agents(
            philosophical_agent,
            initial_data={"question": question}
        )
        
        print()
    
    print("Notice how the agent maintains its philosophical identity")
    print("regardless of the specific question asked.")
    print()
    print("Key Insight: We defined what the agent IS (a philosopher)")
    print("rather than programming what it DOES step by step.")


if __name__ == "__main__":
    main()