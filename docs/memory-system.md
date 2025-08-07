# Praval Memory System

**Comprehensive memory capabilities for intelligent, persistent AI agents**

## 🧠 Overview

Praval's memory system provides multi-layered memory capabilities that enable agents to:
- **Remember** conversations and interactions
- **Learn** from experiences over time  
- **Store** knowledge and facts persistently
- **Retrieve** relevant information contextually
- **Scale** to millions of memories with vector search

## 🏗️ Architecture

### Memory Layers

```
┌─────────────────────────────────────┐
│          Agent Interface            │
├─────────────────────────────────────┤
│         Memory Manager              │
│    (Unified coordination layer)     │
├─────────────────────────────────────┤
│  Short-term  │ Long-term │ Episodic │
│   Memory     │  Memory   │ Memory   │
│  (Working)   │ (Qdrant)  │(Convos)  │
├─────────────────────────────────────┤
│           Semantic Memory           │
│        (Knowledge & Facts)          │
└─────────────────────────────────────┘
```

### 1. **Short-term Memory**
- **Purpose**: Fast, working memory for immediate context
- **Storage**: In-process Python data structures
- **Capacity**: ~1000 entries (configurable)
- **Lifetime**: 24 hours (configurable)
- **Use Cases**: Current conversation, active tasks, temporary state

### 2. **Long-term Memory** 
- **Purpose**: Persistent, searchable vector storage
- **Storage**: Qdrant vector database
- **Capacity**: Millions of entries
- **Lifetime**: Persistent across restarts
- **Use Cases**: Important memories, learned patterns, semantic search

### 3. **Episodic Memory**
- **Purpose**: Conversation history and experience sequences
- **Storage**: Combines short-term + long-term
- **Features**: Timeline tracking, context windows, experience learning
- **Use Cases**: Dialogue continuity, experience-based improvement

### 4. **Semantic Memory**
- **Purpose**: Factual knowledge and concept relationships
- **Storage**: Long-term memory with semantic organization
- **Features**: Domain expertise, knowledge validation, concept linking
- **Use Cases**: Facts storage, domain learning, knowledge graphs

## 🚀 Quick Start

### Basic Setup

```python
from praval.memory import MemoryManager

# Initialize memory system
memory = MemoryManager(
    qdrant_url="http://localhost:6333",
    collection_name="my_agent_memories"
)

# Store a memory
memory_id = memory.store_memory(
    agent_id="my_agent",
    content="User prefers technical documentation with examples",
    memory_type=MemoryType.SHORT_TERM,
    importance=0.8
)

# Search memories
from praval.memory import MemoryQuery

query = MemoryQuery(
    query_text="user preferences documentation",
    agent_id="my_agent", 
    limit=5
)
results = memory.search_memories(query)

for entry in results.entries:
    print(f"Found: {entry.content}")
```

### With Docker Compose

```bash
# Start Qdrant and Praval services
docker-compose up -d

# Run memory demo
docker-compose exec praval-app python examples/memory_demo.py

# View in Jupyter (development)
docker-compose --profile dev up jupyter
# Open http://localhost:8888
```

## 🎯 Agent Integration

### Memory-Enabled Agents

```python
from praval import agent
from praval.memory import MemoryManager

# Global memory manager
memory = MemoryManager()

@agent("smart_assistant", responds_to=["user_query"])
def smart_assistant(spore):
    """Agent that remembers user preferences and past interactions"""
    
    user_query = spore.knowledge.get("query")
    agent_id = "smart_assistant"
    
    # Search relevant memories
    relevant_memories = memory.search_memories(MemoryQuery(
        query_text=user_query,
        agent_id=agent_id,
        limit=3
    ))
    
    # Get conversation context
    conversation_context = memory.get_conversation_context(
        agent_id=agent_id,
        turns=5
    )
    
    # Generate response using memory context
    memory_context = "\n".join([m.content for m in relevant_memories.entries])
    
    response = chat(f"""
    Based on previous interactions: {memory_context}
    
    User query: {user_query}
    
    Provide a personalized response using the memory context.
    """)
    
    # Store this interaction
    memory.store_conversation_turn(
        agent_id=agent_id,
        user_message=user_query,
        agent_response=response
    )
    
    return {"response": response}
```

## 📊 Memory Types

### MemoryType Enum

```python
from praval.memory import MemoryType

MemoryType.SHORT_TERM    # Working memory, temporary
MemoryType.EPISODIC      # Conversations, experiences  
MemoryType.SEMANTIC      # Knowledge, facts, concepts
MemoryType.PROCEDURAL    # Skills, how-to knowledge
MemoryType.EMOTIONAL     # Emotional context, associations
```

### Memory Entry Structure

```python
@dataclass
class MemoryEntry:
    id: str                    # Unique identifier
    agent_id: str             # Which agent owns this memory
    memory_type: MemoryType   # Type of memory
    content: str              # The actual memory content
    metadata: Dict[str, Any]  # Additional structured data
    embedding: List[float]    # Vector embedding (auto-generated)
    created_at: datetime      # When memory was created
    accessed_at: datetime     # Last access time
    access_count: int         # How many times accessed
    importance: float         # Importance score (0.0 to 1.0)
```

## 🔍 Search and Retrieval

### Advanced Search

```python
from praval.memory import MemoryQuery
from datetime import datetime, timedelta

# Complex search query
query = MemoryQuery(
    query_text="machine learning algorithms",
    memory_types=[MemoryType.SEMANTIC, MemoryType.EPISODIC],
    agent_id="ml_expert",
    limit=10,
    similarity_threshold=0.8,
    temporal_filter={
        "after": datetime.now() - timedelta(days=7),
        "before": datetime.now()
    }
)

results = memory.search_memories(query)
```

### Conversation Context

```python
# Get recent conversation turns
context = memory.get_conversation_context(
    agent_id="chatbot",
    turns=10  # Last 10 conversation turns
)

for turn in context:
    conv_data = turn.metadata.get("conversation_data", {})
    print(f"User: {conv_data.get('user_message', '')}")
    print(f"Agent: {conv_data.get('agent_response', '')}")
```

### Knowledge Search

```python
# Find knowledge in specific domain
ai_knowledge = memory.get_domain_knowledge(
    agent_id="expert_system",
    domain="artificial_intelligence",
    limit=20
)

# Store new knowledge
memory.store_knowledge(
    agent_id="expert_system", 
    knowledge="Transformers revolutionized NLP with attention mechanisms",
    domain="artificial_intelligence",
    confidence=0.95
)
```

## 🐳 Docker Deployment

### Simple Deployment

```yaml
# docker-compose.yml
version: '3.8'
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    
  praval-app:
    build: .
    environment:
      - QDRANT_URL=http://qdrant:6333
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on: [qdrant]
```

### Full Development Stack

```bash
# Start everything including Jupyter and PostgreSQL
docker-compose --profile dev --profile full up -d

# Services available:
# - Qdrant: http://localhost:6333 (vector database)
# - Praval App: Container with memory-enabled agents
# - Jupyter Lab: http://localhost:8888 (development)
# - PostgreSQL: localhost:5432 (structured data)
# - Redis: localhost:6379 (optional caching)
```

## 📈 Performance and Scaling

### Memory Optimization

```python
# Configure memory system for scale
memory = MemoryManager(
    qdrant_url="http://qdrant-cluster:6333",
    short_term_max_entries=5000,      # Larger working memory
    short_term_retention_hours=48     # Longer retention
)

# Use importance scoring for retention
memory.store_memory(
    agent_id="production_agent",
    content="Critical system configuration",
    importance=0.95,  # High importance = longer retention
    store_long_term=True
)
```

### Vector Database Scaling

- **Qdrant Clustering**: Multi-node deployment for high availability
- **Sharding**: Distribute collections across multiple instances
- **Replication**: Data redundancy and failover
- **Indexing**: Optimize vector search performance

### Memory Cleanup

```python
# Clear old, unimportant memories
memory.short_term_memory._cleanup_old_memories()

# Clear specific agent memories
memory.clear_agent_memories("old_agent")

# Archive old conversations
memory.episodic_memory.archive_old_episodes(cutoff_days=90)
```

## 🔧 Configuration

### Environment Variables

```bash
# Core settings
QDRANT_URL=http://localhost:6333
PRAVAL_COLLECTION_NAME=praval_memories
PRAVAL_LOG_LEVEL=INFO

# Memory configuration  
SHORT_TERM_MAX_ENTRIES=1000
SHORT_TERM_RETENTION_HOURS=24

# API Keys (at least one required)
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

### Programmatic Configuration

```python
memory = MemoryManager(
    qdrant_url="http://production-qdrant:6333",
    collection_name="production_memories",
    short_term_max_entries=2000,
    short_term_retention_hours=48
)

# Configure vector parameters
memory.long_term_memory.vector_size = 1536  # OpenAI embedding size
memory.long_term_memory.distance_metric = "cosine"
```

## 🚨 Troubleshooting

### Common Issues

**Qdrant Connection Failed**
```bash
# Check Qdrant status
curl http://localhost:6333/health

# Docker logs
docker-compose logs qdrant
```

**Memory Storage Errors**
```python
# Check memory system health
health = memory.health_check()
print(health)

# View statistics
stats = memory.get_memory_stats()
print(stats)
```

**Performance Issues**
- Increase Qdrant memory allocation
- Optimize similarity thresholds
- Use memory importance scoring
- Implement memory archiving

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable detailed memory logging
memory_logger = logging.getLogger('praval.memory')
memory_logger.setLevel(logging.DEBUG)
```

## 🎯 Best Practices

### Memory Design Patterns

1. **Layered Storage**: Use short-term for working memory, long-term for persistence
2. **Importance Scoring**: Priority-based retention and retrieval
3. **Domain Organization**: Group related knowledge by domain
4. **Context Windows**: Maintain conversation continuity with episodic memory
5. **Memory Hygiene**: Regular cleanup of old, unimportant memories

### Agent Patterns

```python
# Pattern 1: Memory-aware agent
@agent("memory_agent")
def memory_aware_agent(spore):
    # Always search relevant memories first
    memories = search_relevant_memories(spore.knowledge)
    # Use memory context in response generation
    response = generate_response_with_context(spore, memories)
    # Store interaction for future reference
    store_interaction(spore, response)
    
# Pattern 2: Learning agent
@agent("learning_agent") 
def learning_agent(spore):
    # Learn from successful interactions
    if spore.knowledge.get("feedback") == "positive":
        store_successful_pattern(spore)
    # Apply learned patterns to new situations
    similar_cases = find_similar_experiences(spore.knowledge)
    return apply_learned_approach(similar_cases, spore)
```

## 🔮 Advanced Features

### Memory Analytics

```python
# Analyze agent expertise
expertise = memory.semantic_memory.get_domain_expertise_level(
    agent_id="expert_agent",
    domain="machine_learning"
)
# Returns: expertise_level, knowledge_count, confidence_average

# Memory usage patterns
stats = memory.get_memory_stats()
# Analyze memory access patterns, popular domains, etc.
```

### Knowledge Validation

```python
# Validate new information against existing knowledge
validation = memory.semantic_memory.validate_knowledge(
    agent_id="fact_checker",
    statement="The Earth is flat",
    threshold=0.8
)
# Returns: is_consistent, confidence, supporting_evidence
```

### Memory Relationships

```python
# Find related concepts
related = memory.semantic_memory.find_related_concepts(
    agent_id="knowledge_agent",
    concept="neural networks",
    limit=10
)
# Returns memories related to neural networks
```

---

The Praval memory system transforms simple agents into intelligent, persistent entities that learn and remember across interactions. Start with basic memory storage and gradually incorporate advanced features like episodic learning and semantic knowledge building.