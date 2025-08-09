#!/usr/bin/env python3
"""
Example 002: Agent Communication
================================

This example demonstrates the foundational communication pattern in Praval.
Agents communicate through structured messages (spores) using the broadcast
and responds_to mechanisms.

Key Concepts:
- Agent-to-agent communication
- The broadcast() function
- Message filtering with responds_to
- Spore knowledge structure
- Natural conversation flow

Run: python examples/002_agent_communication.py
"""

from praval import agent, chat, broadcast, start_agents


@agent("questioner", responds_to=["start_dialogue"])
def curious_questioner(spore):
    """
    I am naturally curious and love to ask thoughtful questions
    about any topic that interests me.
    """
    topic = spore.knowledge.get("topic", "artificial intelligence")
    
    # Generate a thoughtful question
    question = chat(f"""
    As a curious person, generate one thoughtful, engaging question about {topic}.
    Make it something that would spark interesting discussion.
    Return only the question.
    """)
    
    print(f"🤔 Questioner: {question}")
    
    # Broadcast the question to any agents who might be interested
    broadcast({
        "type": "question_posed",
        "topic": topic,
        "question": question,
        "from": "questioner"
    })
    
    return {"question": question}


@agent("responder", responds_to=["question_posed"])
def thoughtful_responder(spore):
    """
    I am a knowledgeable person who enjoys providing thoughtful,
    informative answers to interesting questions.
    """
    question = spore.knowledge.get("question")
    topic = spore.knowledge.get("topic")
    
    if not question:
        return
    
    # Provide a thoughtful response
    answer = chat(f"""
    Someone asked this thoughtful question about {topic}: "{question}"
    
    As a knowledgeable person, provide an informative, engaging answer that:
    - Addresses the question directly
    - Provides useful insights
    - Is clear and accessible
    - Might spark further discussion
    """)
    
    print(f"💡 Responder: {answer}")
    
    # Continue the conversation by asking a follow-up
    follow_up = chat(f"""
    Based on my answer about {topic}, generate a brief follow-up question
    that could deepen the discussion. Return only the question.
    """)
    
    print(f"🔄 Responder: {follow_up}")
    
    # Broadcast the follow-up to continue the dialogue
    broadcast({
        "type": "question_posed",
        "topic": topic,
        "question": follow_up,
        "from": "responder"
    })
    
    return {"answer": answer, "follow_up": follow_up}


def main():
    """Demonstrate agent communication patterns."""
    print("=" * 60)
    print("Example 002: Agent Communication")
    print("=" * 60)
    
    print("Starting a dialogue between two agents...")
    print("The questioner will ask about a topic,")
    print("and the responder will answer and ask a follow-up.")
    print()
    
    # Start the dialogue with different topics
    topics = ["creativity", "learning", "collaboration"]
    
    for topic in topics:
        print(f"--- Dialogue about: {topic.upper()} ---")
        
        # This will trigger both agents through their communication
        start_agents(
            curious_questioner,
            thoughtful_responder,
            initial_data={"type": "start_dialogue", "topic": topic}
        )
        
        print()
    
    print("Key Insights:")
    print("- Agents communicate through structured messages (spores)")
    print("- responds_to filters ensure agents only handle relevant messages")
    print("- broadcast() enables natural, asynchronous communication")
    print("- Conversations can continue through chained broadcasts")


if __name__ == "__main__":
    main()