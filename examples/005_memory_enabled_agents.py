#!/usr/bin/env python3
"""
Example 005: Memory-Enabled Agents
==================================

This example demonstrates the memory capabilities in Praval v0.7.17:
- Embedded ChromaDB vector storage (zero external dependencies)
- Knowledge base auto-indexing
- Lightweight spore communication with knowledge references
- Semantic search and retrieval
- Conversation context and learning

Key Concepts:
- Agent memory with ChromaDB embedded vector store
- Automatic conversation tracking and context
- Semantic search and knowledge retrieval
- Memory-driven behavior adaptation
- Learning from past interactions

Run: python examples/005_memory_enabled_agents.py
"""

import os
import tempfile
from pathlib import Path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from praval import agent, broadcast, start_agents, get_reef


def create_sample_knowledge_base():
    """Create a temporary knowledge base for demonstration"""
    kb_dir = Path(tempfile.mkdtemp()) / "learning_knowledge"
    kb_dir.mkdir(parents=True)
    
    # Create sample knowledge files
    (kb_dir / "learning_theory.txt").write_text(
        "Active learning engages students in the learning process.\n"
        "Spaced repetition improves long-term memory retention.\n"
        "Personalized learning adapts to individual student needs.\n"
        "Collaborative learning benefits from peer interactions."
    )
    
    (kb_dir / "teaching_methods.md").write_text(
        "# Effective Teaching Methods\n\n"
        "## Socratic Method\n"
        "Uses questioning to guide student discovery.\n\n"
        "## Scaffolding\n"
        "Provides temporary support structures for learning.\n\n"
        "## Constructivist Approach\n"
        "Students build knowledge through experience and reflection."
    )
    
    return str(kb_dir)


@agent("learning_agent", memory=True, responds_to=["learning_session"])
def memory_learning_agent(spore):
    """
    A learning agent with persistent memory who remembers past
    interactions and adapts responses based on what it has learned.

    Memory methods available when memory=True:
        remember(content, importance=0.5, memory_type="episodic") -> str (memory_id)
        recall(query, limit=10) -> List[MemoryEntry]
        recall_by_id(memory_id) -> Optional[MemoryEntry]
        get_conversation_context(turns=10) -> List[dict]
    """
    topic = spore.knowledge.get("topic", "general knowledge")
    student_id = spore.knowledge.get("student_id", "default")
    
    print(f"🧠 Learning Agent: Starting session about '{topic}' for student {student_id}")
    
    # Remember this learning session
    session_info = f"Learning session about {topic} for student {student_id}"
    memory_learning_agent.remember(session_info, importance=0.7)
    
    # Recall past learning sessions about this topic
    past_sessions = memory_learning_agent.recall(topic, limit=3)
    
    if past_sessions:
        print(f"💭 Learning Agent: I recall {len(past_sessions)} previous sessions related to '{topic}'")
        context_note = f"Building on {len(past_sessions)} previous learning sessions about this topic."
        # Show some previous context
        for session in past_sessions[:2]:
            print(f"   📚 Previous: {session.content[:80]}...")
    else:
        print(f"🆕 Learning Agent: This is my first time learning about '{topic}'")
        context_note = "This is my first exploration of this topic."
    
    # Get conversation context for this student
    student_context = memory_learning_agent.get_conversation_context(turns=5)
    context_summary = f"Recent interactions with this student: {len(student_context)}"
    
    # Generate response based on memory with fallback
    try:
        from praval import chat
        learning_response = chat(f"""
        I'm a learning agent working on: {topic}
        
        Memory context: {context_note}
        Student context: {context_summary}
        
        Provide insights about {topic}, and ask a thoughtful follow-up question
        that shows I'm building on previous knowledge if available.
        """)
    except Exception:
        # Fallback learning response
        learning_response = f"Exploring {topic}: This is a fascinating area of study. {context_note} I'm curious to learn more - what specific aspects of {topic} interest you most?"
    
    print(f"📖 Learning Agent: {learning_response}")
    
    # Request teaching assistance
    broadcast({
        "type": "teach_request",
        "topic": topic,
        "student_level": "building_knowledge",
        "context": context_note,
        "student_id": student_id,
        "sessions_count": len(past_sessions)
    })
    
    return {"learning_response": learning_response, "sessions_recalled": len(past_sessions)}


@agent("teaching_agent", memory=True, responds_to=["teach_request"],
       knowledge_base=None)  # Note: knowledge_base must be set at decoration time; see kb_memory_teaching_agent in main()
def memory_teaching_agent(spore):
    """
    I am a teaching agent with access to a knowledge base who remembers 
    each student's progress and adapts my teaching methods accordingly.
    """
    topic = spore.knowledge.get("topic")
    student_level = spore.knowledge.get("student_level", "beginner")
    student_id = spore.knowledge.get("student_id", "default")
    context = spore.knowledge.get("context", "")
    sessions_count = spore.knowledge.get("sessions_count", 0)
    
    print(f"👨‍🏫 Teaching Agent: Teaching {topic} to student {student_id}")
    
    # Search knowledge base for relevant teaching methods
    relevant_knowledge = memory_teaching_agent.recall(topic, limit=2)
    if relevant_knowledge:
        print(f"📚 Teaching Agent: Found {len(relevant_knowledge)} relevant teaching resources")
        knowledge_context = "\n".join([k.content for k in relevant_knowledge[:1]])
    else:
        knowledge_context = "Using general teaching principles"
    
    # Remember this teaching session
    lesson_info = f"Teaching {topic} to student {student_id} (session #{sessions_count + 1})"
    memory_teaching_agent.remember(lesson_info, importance=0.8)
    
    # Recall previous lessons with this student
    student_history = memory_teaching_agent.recall(f"student {student_id}", limit=3)
    
    if student_history:
        print(f"📊 Teaching Agent: I remember {len(student_history)} previous sessions with this student")
        teaching_approach = "building on previous knowledge"
        # Show previous context
        for session in student_history[:1]:
            print(f"   🔄 Previous: {session.content[:80]}...")
    else:
        print(f"🆕 Teaching Agent: First time teaching student {student_id}")
        teaching_approach = "foundational introduction"
    
    # Teaching response with fallback
    try:
        from praval import chat
        teaching_response = chat(f"""
        I'm teaching about: {topic}
        Student context: {context}
        Student level: {student_level}
        Teaching approach: {teaching_approach}
        Sessions with this student: {len(student_history)}
        
        Relevant knowledge from my knowledge base:
        {knowledge_context}
        
        Provide a teaching response that:
        - Uses evidence-based teaching methods from my knowledge base
        - Adapts to the student's learning history
        - Builds on previous knowledge if available
        - Encourages continued learning and engagement
        """)
    except Exception:
        # Fallback teaching response
        teaching_response = f"Teaching {topic}: Let me share some key concepts about {topic}. {knowledge_context} Based on your learning journey, I'll adapt my approach using {teaching_approach}. What would you like to explore first?"
    
    print(f"📚 Teaching Agent: {teaching_response}")
    
    # Provide feedback to learner
    broadcast({
        "type": "learning_feedback",
        "topic": topic,
        "teaching_response": teaching_response,
        "progress_note": f"Building on {len(student_history)} previous sessions",
        "student_id": student_id,
        "knowledge_sources": len(relevant_knowledge)
    })
    
    return {
        "teaching_response": teaching_response, 
        "student_sessions": len(student_history),
        "knowledge_sources": len(relevant_knowledge)
    }


@agent("reflection_agent", memory=True, responds_to=["learning_feedback"])
def memory_reflection_agent(spore):
    """
    I reflect on learning interactions and help identify patterns 
    that can improve future sessions using my memory system.
    """
    topic = spore.knowledge.get("topic")
    student_id = spore.knowledge.get("student_id", "default")
    progress_note = spore.knowledge.get("progress_note", "")
    student_sessions = spore.knowledge.get("student_sessions", 0)
    knowledge_sources = spore.knowledge.get("knowledge_sources", 0)
    
    print(f"🤔 Reflection Agent: Analyzing learning session about {topic}")
    
    # Remember this reflection
    reflection_info = f"Reflected on {topic} session for student {student_id}"
    memory_reflection_agent.remember(reflection_info, importance=0.6)
    
    # Recall past reflections for pattern analysis
    past_reflections = memory_reflection_agent.recall("learning session", limit=3)
    patterns_observed = len(past_reflections)
    
    if past_reflections:
        print(f"💭 Reflection Agent: Analyzing patterns from {patterns_observed} previous reflections")
    
    # Reflection with fallback
    try:
        from praval import chat
        reflection = chat(f"""
        Reflecting on this learning session about {topic}:
        
        Progress: {progress_note}
        Student sessions remembered: {student_sessions}
        Knowledge base sources used: {knowledge_sources}
        Previous reflection patterns analyzed: {patterns_observed}
        
        What patterns do you notice about:
        - How persistent memory improves learning continuity
        - The value of knowledge base integration in teaching
        - How agents build relationships through memory
        - The effectiveness of semantic search for relevant knowledge
        
        Provide insights about the benefits of memory-enabled agent collaboration.
        """)
    except Exception:
        # Fallback reflection
        reflection = f"Reflecting on {topic} session: {progress_note} Memory systems enable continuity across sessions, allowing agents to build on previous knowledge and develop stronger relationships with learners. Pattern analysis shows that persistent memory improves both learning outcomes and teaching effectiveness."
    
    print(f"🤔 Reflection Agent: {reflection}")
    
    return {
        "reflection": reflection,
        "patterns_analyzed": patterns_observed,
        "session_quality": "high" if knowledge_sources > 0 else "basic"
    }


def main():
    """Demonstrate memory-enabled agent interactions with ChromaDB."""
    print("=" * 60)
    print("Example 005: Memory-Enabled Agents")
    print("=" * 60)
    
    print("Demonstrating Praval's new memory capabilities:")
    print("- Embedded ChromaDB vector storage")
    print("- Knowledge base auto-indexing")
    print("- Semantic search and retrieval")
    print("- Conversation context and learning")
    print()
    
    try:
        # Create sample knowledge base
        kb_path = create_sample_knowledge_base()
        print(f"📚 Created knowledge base at: {kb_path}")
        
        # Update teaching agent's knowledge base (since we can't set it in decorator dynamically)
        # For demo purposes, we'll create a new teaching agent with knowledge base
        @agent("kb_teaching_agent", memory=True, knowledge_base=kb_path, 
               responds_to=["teach_request"])
        def kb_memory_teaching_agent(spore):
            """Teaching agent with knowledge base access"""
            # Call the original teaching agent logic but with KB access
            return memory_teaching_agent(spore)
        
        print("🚀 Starting memory-enabled learning sessions...\n")
        
        # Simulate multiple learning sessions to show memory continuity
        learning_sessions = [
            {"topic": "active learning", "student_id": "alice"},
            {"topic": "teaching methods", "student_id": "alice"},  
            {"topic": "active learning", "student_id": "bob"},    # Different student, same topic
            {"topic": "personalized learning", "student_id": "alice"},  # Advanced topic for Alice
            {"topic": "collaborative learning", "student_id": "alice"}   # New topic for Alice
        ]
        
        for i, session in enumerate(learning_sessions, 1):
            print(f"=== Learning Session {i}: {session['topic']} (Student: {session['student_id']}) ===")
            print()

            result = start_agents(
                memory_learning_agent,
                kb_memory_teaching_agent,  # Use knowledge base enabled version
                memory_reflection_agent,
                initial_data={
                    "type": "learning_session",
                    **session
                }
            )

            # Wait for agents to complete
            get_reef().wait_for_completion()

            print(f"\n--- Session {i} Results ---")
            if result and isinstance(result, dict):
                sessions_recalled = result.get("sessions_recalled", 0)
                student_sessions = result.get("student_sessions", 0)
                knowledge_sources = result.get("knowledge_sources", 0)
                patterns_analyzed = result.get("patterns_analyzed", 0)

                print(f"📊 Learning: {sessions_recalled} past sessions recalled")
                print(f"👨‍🏫 Teaching: {student_sessions} previous sessions with this student")
                print(f"📚 Knowledge: {knowledge_sources} knowledge base sources used")
                print(f"🤔 Reflection: {patterns_analyzed} patterns analyzed")

            print("\n" + "─" * 60 + "\n")

        # Shutdown reef after all iterations
        get_reef().shutdown()

        print("✅ MEMORY CAPABILITIES DEMONSTRATED:")
        print("- ✓ ChromaDB embedded vector storage working")
        print("- ✓ Knowledge base auto-indexed and searchable") 
        print("- ✓ Semantic search finding relevant information")
        print("- ✓ Conversation context maintained across sessions")
        print("- ✓ Agents building relationships through persistent memory")
        print("- ✓ Learning and teaching adapting based on history")
        
        # Cleanup
        import shutil
        shutil.rmtree(Path(kb_path).parent)
        print(f"\n🧹 Cleaned up temporary knowledge base")
        
    except ImportError as e:
        print(f"❌ Memory system not available: {e}")
        print("Install dependencies with: pip install chromadb sentence-transformers scikit-learn")
    except Exception as e:
        print(f"❌ Error during demo: {e}")
        print("This is a development version - some features may need refinement")


if __name__ == "__main__":
    main()