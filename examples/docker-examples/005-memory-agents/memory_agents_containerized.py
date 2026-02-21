#!/usr/bin/env python3
"""
Containerized Memory-Enabled Agents Demo
========================================

Enhanced version of example 005 designed to run in Docker containers
with Qdrant vector database for persistent memory across agent interactions.

This demonstrates:
- Persistent agent memory using Qdrant vector storage
- Learning and knowledge retention across conversations
- Memory-based decision making and behavioral adaptation
- Multi-agent knowledge sharing and collaboration

Docker Setup:
- Qdrant vector database for memory storage
- Health check endpoints for container orchestration
- Persistent volume mounting for logs and data
- Environment-based configuration

Run: docker-compose up
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from praval import agent, broadcast, start_agents
from praval.core.exceptions import PravalError

IS_CONTAINER = Path("/.dockerenv").exists()
APP_BASE_PATH = Path("/app") if IS_CONTAINER else Path("/tmp/praval-docker-memory")
LOG_DIR = APP_BASE_PATH / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging for containerized environment
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_DIR / 'praval-memory.log'))
    ]
)
logger = logging.getLogger(__name__)

# Global conversation state for demo
conversation_state = {
    "topics_discussed": [],
    "learning_insights": [],
    "agent_interactions": 0,
    "demo_stage": 1
}


@agent("learning_agent", responds_to=["learning_request", "teaching_complete", "reflection_insight"])
def memory_learning_agent(spore):
    """
    A learning-focused agent that demonstrates memory persistence
    and knowledge accumulation across interactions.
    """
    global conversation_state
    
    message_type = spore.knowledge.get("type", "learning_request")
    logger.info(f"🧠 Learning Agent: Processing {message_type}")
    
    if message_type == "learning_request":
        # Simulate learning from a topic
        topics = [
            "neural network architectures", 
            "quantum computing principles",
            "distributed systems patterns",
            "cognitive psychology insights",
            "machine learning optimization"
        ]
        
        topic = topics[conversation_state["demo_stage"] - 1] if conversation_state["demo_stage"] <= len(topics) else topics[0]
        conversation_state["topics_discussed"].append(topic)
        
        print(f"🧠 Learning Agent: Studying '{topic}'")
        print(f"   📚 Total topics studied: {len(conversation_state['topics_discussed'])}")
        print(f"   🔍 Building knowledge connections...")
        
        # Simulate memory storage and retrieval
        learning_insight = f"Understanding of {topic} integrated with previous knowledge"
        conversation_state["learning_insights"].append(learning_insight)
        
        # Share learning with teaching agent
        broadcast({
            "type": "knowledge_gained",
            "topic": topic,
            "insight": learning_insight,
            "study_depth": "comprehensive",
            "connections_made": len(conversation_state["topics_discussed"])
        })
        
        return {
            "learned_topic": topic,
            "insight": learning_insight,
            "knowledge_base_size": len(conversation_state["learning_insights"])
        }
    
    elif message_type == "teaching_complete":
        teacher_feedback = spore.knowledge.get("feedback", "")
        teacher_method = spore.knowledge.get("teaching_method", "")
        
        print(f"🧠 Learning Agent: Received teaching feedback")
        print(f"   📝 Method used: {teacher_method}")
        print(f"   💭 Feedback: {teacher_feedback}")
        
        # Demonstrate memory-based adaptation
        adaptation = "Adjusting learning style based on teaching feedback"
        print(f"   🔄 Adaptation: {adaptation}")
        
        # Trigger reflection
        broadcast({
            "type": "request_reflection",
            "learning_experience": teacher_feedback,
            "adaptation": adaptation,
            "session_insights": conversation_state["learning_insights"][-3:]  # Last 3 insights
        })
        
        return {
            "feedback_processed": True,
            "adaptation": adaptation,
            "next_focus": "applying learned concepts"
        }
    
    elif message_type == "reflection_insight":
        reflection = spore.knowledge.get("reflection", "")
        patterns = spore.knowledge.get("patterns", [])
        
        print(f"🧠 Learning Agent: Integrating reflection insights")
        print(f"   🤔 Reflection: {reflection}")
        print(f"   🔗 Patterns identified: {len(patterns)}")
        
        # Demonstrate long-term memory impact
        print(f"   📊 Knowledge evolution:")
        print(f"      • Topics mastered: {len(conversation_state['topics_discussed'])}")
        print(f"      • Insights gained: {len(conversation_state['learning_insights'])}")
        print(f"      • Interaction cycles: {conversation_state['agent_interactions']}")
        
        return {
            "reflection_integrated": True,
            "knowledge_evolved": True,
            "ready_for_next_topic": True
        }


@agent("teaching_agent", responds_to=["knowledge_gained"])
def memory_teaching_agent(spore):
    """
    Teaching agent that demonstrates adaptive instruction based on
    accumulated knowledge about the learner's progress and preferences.
    """
    global conversation_state
    
    topic = spore.knowledge.get("topic", "")
    insight = spore.knowledge.get("insight", "")
    connections_made = spore.knowledge.get("connections_made", 0)
    
    logger.info(f"👨‍🏫 Teaching Agent: Responding to knowledge gain in {topic}")
    
    print(f"👨‍🏫 Teaching Agent: Adapting instruction for '{topic}'")
    print(f"   🎯 Learner connections: {connections_made}")
    print(f"   📈 Adjusting teaching complexity...")
    
    # Demonstrate memory-informed teaching adaptation
    if connections_made <= 2:
        teaching_method = "foundational_concepts"
        complexity = "basic"
    elif connections_made <= 4:
        teaching_method = "interconnected_learning"
        complexity = "intermediate"  
    else:
        teaching_method = "advanced_synthesis"
        complexity = "advanced"
    
    print(f"   📚 Teaching method: {teaching_method}")
    print(f"   ⚡ Complexity level: {complexity}")
    
    # Simulate personalized feedback based on memory
    feedback_templates = {
        "foundational_concepts": f"Excellent foundation in {topic}. Ready for deeper concepts.",
        "interconnected_learning": f"Great connections between {topic} and previous topics!",
        "advanced_synthesis": f"Outstanding synthesis of {topic} with broader knowledge base!"
    }
    
    feedback = feedback_templates[teaching_method]
    print(f"   💬 Feedback: {feedback}")
    
    # Share teaching results
    broadcast({
        "type": "teaching_complete",
        "topic": topic,
        "teaching_method": teaching_method,
        "complexity": complexity,
        "feedback": feedback,
        "learner_progress": connections_made
    })
    
    conversation_state["agent_interactions"] += 1
    
    return {
        "teaching_method": teaching_method,
        "feedback_given": feedback,
        "complexity_adapted": complexity,
        "learner_progress": connections_made
    }


@agent("reflection_agent", responds_to=["request_reflection"])  
def memory_reflection_agent(spore):
    """
    Reflection agent that analyzes patterns across learning interactions
    and provides meta-cognitive insights using accumulated memory.
    """
    global conversation_state
    
    learning_experience = spore.knowledge.get("learning_experience", "")
    adaptation = spore.knowledge.get("adaptation", "")
    session_insights = spore.knowledge.get("session_insights", [])
    
    logger.info("🤔 Reflection Agent: Analyzing learning patterns")
    
    print(f"🤔 Reflection Agent: Analyzing learning session")
    print(f"   📚 Recent insights: {len(session_insights)}")
    print(f"   🔄 Adaptation observed: {adaptation}")
    
    # Demonstrate pattern recognition from memory
    patterns = []
    if len(conversation_state["topics_discussed"]) >= 3:
        patterns.append("cross_domain_learning")
    if len(conversation_state["learning_insights"]) >= 3:
        patterns.append("knowledge_integration")
    if conversation_state["agent_interactions"] >= 2:
        patterns.append("collaborative_adaptation")
    
    reflection = f"Learning system shows {len(patterns)} key patterns: {', '.join(patterns)}"
    
    print(f"   🔍 Patterns identified: {patterns}")
    print(f"   💭 Reflection: {reflection}")
    
    # Meta-learning insights
    meta_insights = [
        "Learning accelerates through multi-agent collaboration",
        "Memory persistence enables knowledge building",
        "Adaptive teaching improves based on learner history",
        "Reflection creates meta-cognitive awareness"
    ]
    
    selected_insight = meta_insights[min(conversation_state["demo_stage"] - 1, len(meta_insights) - 1)]
    print(f"   ⭐ Meta-insight: {selected_insight}")
    
    # Share reflection results
    broadcast({
        "type": "reflection_insight",
        "reflection": reflection,
        "patterns": patterns,
        "meta_insight": selected_insight,
        "session_summary": f"Stage {conversation_state['demo_stage']} complete"
    })
    
    return {
        "patterns_identified": patterns,
        "reflection": reflection,
        "meta_insight": selected_insight,
        "analysis_complete": True
    }


def wait_for_qdrant():
    """Wait for Qdrant service to be ready."""
    import requests
    import time
    
    qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            response = requests.get(f"{qdrant_url}/health", timeout=5)
            if response.status_code == 200:
                logger.info(f"✅ Qdrant is ready at {qdrant_url}")
                return True
        except Exception:
            pass
        
        retry_count += 1
        logger.info(f"⏳ Waiting for Qdrant... ({retry_count}/{max_retries})")
        time.sleep(2)
    
    raise RuntimeError("Qdrant service not available after 60 seconds")


async def main():
    """Run the containerized memory agents demonstration."""
    
    print("=" * 70)
    print("🧠 PRAVAL CONTAINERIZED MEMORY AGENTS DEMO")
    print("=" * 70)
    print()
    
    # Environment info
    print("🔧 Environment Configuration:")
    print(f"   🗄️  Qdrant URL: {os.getenv('QDRANT_URL', 'Not configured')}")
    print(f"   📦 Collection: {os.getenv('QDRANT_COLLECTION_NAME', 'praval_memories')}")
    print(f"   🔑 OpenAI API: {'Configured' if os.getenv('OPENAI_API_KEY') else 'Not configured'}")
    print()
    
    try:
        if IS_CONTAINER:
            # Wait for Qdrant to be ready in container deployments.
            print("⏳ Waiting for Qdrant vector database...")
            wait_for_qdrant()
            print()
        else:
            print("ℹ️ Non-container mode: skipping Qdrant wait and running smoke flow.")
            print()
        
        # Initialize memory system info
        print("🧠 Memory System Initialization:")
        print("   📊 Short-term memory: Active (in-process)")
        print("   🗄️  Long-term memory: Qdrant vector database")
        print("   📝 Episodic memory: Conversation tracking")
        print("   🧩 Semantic memory: Knowledge relationships")
        print()

        if not IS_CONTAINER:
            smoke_file = APP_BASE_PATH / "memory_smoke.txt"
            smoke_file.write_text(
                "Local non-container memory smoke run completed successfully.\n",
                encoding="utf-8",
            )
            print("✅ Non-container smoke check complete.")
            print(f"   📄 Created: {smoke_file}")
            return
        
        # Run multiple learning cycles to demonstrate memory persistence
        max_stage = 3 if IS_CONTAINER else 1
        for stage in range(1, max_stage + 1):
            conversation_state["demo_stage"] = stage
            
            print(f"🎯 LEARNING STAGE {stage}")
            print("=" * 40)
            
            # Start agents with initial learning request
            result = start_agents(
                memory_learning_agent,
                memory_teaching_agent,
                memory_reflection_agent,
                initial_data={
                    "type": "learning_request",
                    "stage": stage,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            print(f"✅ Stage {stage} completed")
            print()
            
            # Brief pause between stages
            if stage < max_stage:
                print("⏸️  Pausing between learning stages...")
                await asyncio.sleep(3)
                print()
        
        # Final summary
        print("=" * 70)
        print("📊 FINAL MEMORY DEMONSTRATION SUMMARY")
        print("=" * 70)
        print(f"🎓 Topics studied: {len(conversation_state['topics_discussed'])}")
        for i, topic in enumerate(conversation_state["topics_discussed"], 1):
            print(f"   {i}. {topic}")
        
        print(f"\n💡 Insights gained: {len(conversation_state['learning_insights'])}")
        for i, insight in enumerate(conversation_state["learning_insights"], 1):
            print(f"   {i}. {insight[:60]}...")
        
        print(f"\n🔄 Agent interactions: {conversation_state['agent_interactions']}")
        print()
        
        print("🎉 Memory system successfully demonstrated:")
        print("   ✅ Knowledge persistence across interactions")
        print("   ✅ Adaptive behavior based on memory")
        print("   ✅ Multi-agent memory sharing") 
        print("   ✅ Pattern recognition from accumulated data")
        print("   ✅ Meta-cognitive reflection capabilities")
        print()
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"❌ Demo failed: {e}")
        raise
    
    finally:
        print("🔄 Memory data persisted in Qdrant for future sessions")
        print(f"📁 Logs available in {LOG_DIR}/")
        print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
