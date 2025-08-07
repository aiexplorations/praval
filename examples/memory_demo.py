#!/usr/bin/env python3
"""
Memory System Demonstration for Praval Agents

This example shows how to use Praval's memory capabilities:
- Short-term working memory
- Long-term vector memory with Qdrant
- Episodic conversation memory
- Semantic knowledge storage
"""

import sys
import os
import time
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path for local development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from praval import agent, chat, broadcast, start_agents
from praval.memory import MemoryManager, MemoryType, MemoryQuery

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global memory manager
memory_manager = None

def initialize_memory():
    """Initialize the memory management system"""
    global memory_manager
    
    qdrant_url = os.getenv('QDRANT_URL', 'http://localhost:6333')
    collection_name = os.getenv('PRAVAL_COLLECTION_NAME', 'praval_memories')
    
    print(f"🧠 Initializing memory system...")
    print(f"   Qdrant URL: {qdrant_url}")
    print(f"   Collection: {collection_name}")
    
    try:
        memory_manager = MemoryManager(
            qdrant_url=qdrant_url,
            collection_name=collection_name
        )
        
        # Test health
        health = memory_manager.health_check()
        print(f"   Health Check: {health}")
        
        return memory_manager
    except Exception as e:
        logger.error(f"Failed to initialize memory: {e}")
        print(f"❌ Memory initialization failed: {e}")
        print("🔄 Continuing with short-term memory only...")
        return None

@agent("memory_assistant", responds_to=["memory_request", "knowledge_query"])
def memory_assistant(spore):
    """An assistant that uses memory to provide personalized responses"""
    global memory_manager
    
    if not memory_manager:
        return {"response": "Memory system not available"}
    
    agent_id = "memory_assistant"
    request_type = spore.knowledge.get("type")
    
    if request_type == "memory_request":
        # Handle memory storage requests
        content = spore.knowledge.get("content", "")
        memory_type = spore.knowledge.get("memory_type", "short_term")
        
        print(f"💾 Storing memory: {content[:50]}...")
        
        # Convert string to MemoryType enum
        memory_type_enum = MemoryType.SHORT_TERM
        if memory_type == "semantic":
            memory_type_enum = MemoryType.SEMANTIC
        elif memory_type == "episodic":
            memory_type_enum = MemoryType.EPISODIC
        
        # Store the memory
        memory_id = memory_manager.store_memory(
            agent_id=agent_id,
            content=content,
            memory_type=memory_type_enum,
            metadata={"source": "user_input"},
            importance=0.8
        )
        
        response = f"Stored memory with ID: {memory_id}"
        print(f"✅ {response}")
        
        broadcast({
            "type": "memory_stored",
            "memory_id": memory_id,
            "content": content
        })
        
        return {"response": response}
    
    elif request_type == "knowledge_query":
        # Handle knowledge queries
        query_text = spore.knowledge.get("query", "")
        print(f"🔍 Searching memories for: {query_text}")
        
        # Search memories
        query = MemoryQuery(
            query_text=query_text,
            agent_id=agent_id,
            limit=5,
            similarity_threshold=0.3
        )
        
        results = memory_manager.search_memories(query)
        
        if results.entries:
            print(f"📋 Found {len(results.entries)} relevant memories")
            
            # Format response with found memories
            memory_context = "\n".join([
                f"- {entry.content[:100]}..." 
                for entry in results.entries[:3]
            ])
            
            # Use chat to generate a response based on memories
            chat_response = chat(f"""
Based on these memories:
{memory_context}

Answer this query: {query_text}

Provide a helpful response using the information from memories.
""")
            
            broadcast({
                "type": "knowledge_response",
                "query": query_text,
                "memories_found": len(results.entries),
                "response": chat_response
            })
            
            return {"response": chat_response, "memories_used": len(results.entries)}
        else:
            response = f"No relevant memories found for: {query_text}"
            print(f"❌ {response}")
            return {"response": response}

@agent("conversation_tracker", responds_to=["conversation_turn"])
def conversation_tracker(spore):
    """Tracks conversation history using episodic memory"""
    global memory_manager
    
    if not memory_manager:
        return {"response": "Memory system not available"}
    
    user_message = spore.knowledge.get("user_message", "")
    agent_response = spore.knowledge.get("agent_response", "")
    
    print(f"💬 Recording conversation turn...")
    
    # Store conversation turn
    memory_id = memory_manager.store_conversation_turn(
        agent_id="conversation_tracker",
        user_message=user_message,
        agent_response=agent_response,
        context={"timestamp": datetime.now().isoformat()}
    )
    
    print(f"✅ Conversation stored with ID: {memory_id}")
    
    # Get recent conversation context
    context = memory_manager.get_conversation_context(
        agent_id="conversation_tracker",
        turns=5
    )
    
    print(f"📜 Current conversation context: {len(context)} turns")
    
    return {
        "memory_id": memory_id,
        "context_turns": len(context)
    }

@agent("knowledge_builder", responds_to=["learn_fact"])
def knowledge_builder(spore):
    """Builds semantic knowledge base"""
    global memory_manager
    
    if not memory_manager:
        return {"response": "Memory system not available"}
    
    fact = spore.knowledge.get("fact", "")
    domain = spore.knowledge.get("domain", "general")
    confidence = spore.knowledge.get("confidence", 0.9)
    
    print(f"🧠 Learning new fact in domain '{domain}': {fact[:50]}...")
    
    # Store knowledge
    memory_id = memory_manager.store_knowledge(
        agent_id="knowledge_builder",
        knowledge=fact,
        domain=domain,
        confidence=confidence
    )
    
    print(f"✅ Knowledge stored with ID: {memory_id}")
    
    # Get domain knowledge count
    domain_knowledge = memory_manager.get_domain_knowledge(
        agent_id="knowledge_builder",
        domain=domain,
        limit=100
    )
    
    print(f"📚 Total knowledge in '{domain}' domain: {len(domain_knowledge)} items")
    
    broadcast({
        "type": "knowledge_learned",
        "domain": domain,
        "fact": fact,
        "memory_id": memory_id,
        "domain_total": len(domain_knowledge)
    })
    
    return {
        "memory_id": memory_id,
        "domain": domain,
        "knowledge_count": len(domain_knowledge)
    }

def demonstrate_memory_system():
    """Run a comprehensive memory system demonstration"""
    print("\n" + "="*60)
    print("🧠 PRAVAL MEMORY SYSTEM DEMONSTRATION")
    print("="*60)
    
    # Initialize memory
    global memory_manager
    memory_manager = initialize_memory()
    
    if not memory_manager:
        print("❌ Continuing with limited functionality...")
    
    print("\n🚀 Starting memory-enabled agents...")
    
    # Start agents
    start_agents(
        memory_assistant,
        conversation_tracker, 
        knowledge_builder,
        initial_data={"type": "system_start", "message": "Memory demo starting"}
    )
    
    print("\n📝 Testing memory operations...")
    
    # Test 1: Store some memories
    test_memories = [
        {
            "type": "memory_request",
            "content": "Python is a high-level programming language known for its simplicity and readability",
            "memory_type": "semantic"
        },
        {
            "type": "memory_request", 
            "content": "Praval agents use decorator syntax @agent to define their behavior",
            "memory_type": "semantic"
        },
        {
            "type": "memory_request",
            "content": "The user prefers technical documentation with code examples",
            "memory_type": "short_term"
        }
    ]
    
    for i, memory_data in enumerate(test_memories, 1):
        print(f"\n{i}. Storing memory: {memory_data['content'][:40]}...")
        start_agents(
            memory_assistant,
            initial_data=memory_data
        )
        time.sleep(0.5)  # Brief pause between operations
    
    # Test 2: Query memories
    test_queries = [
        "Tell me about Python programming",
        "How do Praval agents work?",
        "What does the user prefer?"
    ]
    
    print(f"\n🔍 Testing memory queries...")
    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Querying: {query}")
        start_agents(
            memory_assistant,
            initial_data={
                "type": "knowledge_query",
                "query": query
            }
        )
        time.sleep(0.5)
    
    # Test 3: Conversation tracking
    print(f"\n💬 Testing conversation tracking...")
    conversations = [
        ("Hello, I'm new to AI agents", "Welcome! I'm here to help you understand AI agents and their capabilities."),
        ("How do agents remember things?", "Agents use memory systems to store and retrieve information across conversations."),
        ("Can they learn from experience?", "Yes, agents can learn from interactions and improve their responses over time.")
    ]
    
    for i, (user_msg, agent_msg) in enumerate(conversations, 1):
        print(f"\n{i}. Recording conversation...")
        start_agents(
            conversation_tracker,
            initial_data={
                "type": "conversation_turn",
                "user_message": user_msg,
                "agent_response": agent_msg
            }
        )
        time.sleep(0.3)
    
    # Test 4: Knowledge building
    print(f"\n🧠 Testing knowledge building...")
    facts = [
        ("Machine learning is a subset of artificial intelligence", "ai", 0.95),
        ("Neural networks are inspired by biological brain structure", "ai", 0.9),
        ("Docker containers provide application isolation", "devops", 0.9),
        ("Qdrant is a vector database optimized for similarity search", "databases", 0.95)
    ]
    
    for i, (fact, domain, confidence) in enumerate(facts, 1):
        print(f"\n{i}. Learning fact in '{domain}' domain...")
        start_agents(
            knowledge_builder,
            initial_data={
                "type": "learn_fact",
                "fact": fact,
                "domain": domain,
                "confidence": confidence
            }
        )
        time.sleep(0.3)
    
    # Display memory statistics
    if memory_manager:
        print("\n📊 Memory System Statistics:")
        stats = memory_manager.get_memory_stats()
        print(f"   Short-term memory: {stats['short_term_memory']['total_memories']} entries")
        
        if stats['long_term_memory']['available']:
            lt_stats = stats['long_term_memory']
            print(f"   Long-term memory: {lt_stats.get('total_memories', 'N/A')} entries")
            print(f"   Vector size: {lt_stats.get('vector_size', 'N/A')}")
        else:
            print(f"   Long-term memory: Not available ({stats['long_term_memory'].get('error', 'Unknown error')})")
    
    print("\n" + "="*60)
    print("✅ MEMORY DEMONSTRATION COMPLETE")
    print("="*60)
    
    print("""
🎯 What was demonstrated:
• Short-term working memory for immediate access
• Long-term vector memory with Qdrant (if available) 
• Episodic conversation tracking
• Semantic knowledge building across domains
• Memory search and retrieval across all systems

🔧 Next steps:
• Run with docker-compose for full Qdrant integration
• Explore memory persistence across agent restarts
• Build domain-specific knowledge bases
• Implement memory importance scoring
""")

if __name__ == "__main__":
    try:
        demonstrate_memory_system()
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"❌ Demo failed: {e}")
    finally:
        if memory_manager:
            memory_manager.shutdown()
        print("👋 Goodbye!")