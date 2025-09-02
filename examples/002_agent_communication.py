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

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from praval import agent, broadcast, start_agents


@agent("questioner", responds_to=["start_dialogue"])
def curious_questioner(spore):
    """
    I am naturally curious and love to ask thoughtful questions
    about any topic that interests me.
    """
    topic = spore.knowledge.get("topic", "artificial intelligence")
    
    # Generate a thoughtful question with fallback
    try:
        from praval import chat
        question = chat(f"""
        As a curious person, generate one thoughtful, engaging question about {topic}.
        Make it something that would spark interesting discussion.
        Return only the question.
        """)
    except Exception:
        # Fallback questions when LLM is not available
        fallback_questions = {
            "creativity": "What role does failure play in the creative process?",
            "learning": "How does the way we teach affect what students actually learn?",
            "collaboration": "What makes some teams more creative than others?"
        }
        question = fallback_questions.get(topic.lower(), f"What interests you most about {topic}?")
    
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
    
    # Provide a thoughtful response with fallback
    try:
        from praval import chat
        answer = chat(f"""
        Someone asked this thoughtful question about {topic}: "{question}"
        
        As a knowledgeable person, provide an informative, engaging answer that:
        - Addresses the question directly
        - Provides useful insights
        - Is clear and accessible
        - Might spark further discussion
        """)
    except Exception:
        # Fallback responses when LLM is not available
        answer = f"That's a fascinating question about {topic}: '{question}'. This touches on fundamental aspects of human nature and how we interact with the world. Different perspectives would approach this differently, but what's most important is how we apply these insights in practice."
    
    print(f"💡 Responder: {answer}")
    
    # Continue the conversation by asking a follow-up with fallback
    try:
        from praval import chat
        follow_up = chat(f"""
        Based on my answer about {topic}, generate a brief follow-up question
        that could deepen the discussion. Return only the question.
        """)
    except Exception:
        # Fallback follow-up questions
        fallback_followups = {
            "creativity": "How do cultural differences shape creative expression?",
            "learning": "What role does emotion play in how we remember things?",
            "collaboration": "How do we balance individual expertise with collective wisdom?"
        }
        follow_up = fallback_followups.get(topic.lower(), f"What practical steps could we take to improve {topic}?")
    
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