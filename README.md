<div align="center">
  <img src="logo.png" alt="Praval Logo" width="200"/>
  
  # Praval
  
  **The Pythonic Multi-Agent AI Framework**
  
  Transform complex AI applications into simple, composable agent systems using decorator-based APIs, secure messaging, and distributed deployment.
  
  *Praval (प्रवाल) - Sanskrit for coral, representing how simple agents collaborate to create complex, intelligent ecosystems.*

  [![Version](https://img.shields.io/badge/version-0.7.6-blue.svg)](https://github.com/aiexplorations/praval/releases/tag/v0.7.6)
  [![Security](https://img.shields.io/badge/security-enterprise%20ready-green.svg)](#-secure-spores-messaging)
  [![Docker](https://img.shields.io/badge/docker-multi--service-blue.svg)](#-docker-deployment)
</div>

## Overview

**Praval is a revolutionary Python framework that transforms how we build AI applications.** Instead of monolithic systems, Praval enables you to create ecosystems of specialized agents that collaborate intelligently.

### 🚀 **Key Breakthrough: From Complexity to Simplicity**
- **489 lines → 50 lines**: Our decorator API dramatically reduces code complexity
- **Complex classes → Simple functions**: Agents become readable Python functions
- **Manual coordination → Self-organizing**: Agents coordinate through intelligent message passing
- **Imperative programming → Declarative agents**: Define what agents ARE, not what they DO

### ✨ **Core Capabilities**
- **🎯 Specialized Agents**: Each agent excels at one thing
- **🧠 Persistent Memory**: ChromaDB-powered semantic memory and knowledge search
- **🤝 Natural Collaboration**: Agents work together seamlessly
- **📡 Reef Communication**: Knowledge-first messaging between agents
- **🔄 Self-Organization**: Agents coordinate without central control
- **⚡ Pythonic API**: Clean, decorator-based agent definitions
- **🔒 Secure Messaging**: End-to-end encryption with enterprise-grade security
- **🐳 Distributed Deployment**: Multi-service Docker architecture with message queues
- **📡 Multi-Protocol Support**: AMQP, MQTT, STOMP for scalable messaging 

## ⭐ **The Praval Philosophy**

### **🧩 Simple Agents, Powerful Results**
```python
# Instead of complex monoliths...
complex_system = OneAgentDoesEverything()

# Praval encourages specialized collaboration
@agent("researcher", responds_to=["research_request"])
def research_specialist(spore):
    """I excel at finding and analyzing information."""
    return deep_research(spore.knowledge)

@agent("writer", responds_to=["write_request"])
def writing_specialist(spore):
    """I excel at creating compelling content."""
    return polished_writing(spore.knowledge)
```

### **🌊 Core Features**

#### **🎯 Decorator-Based Agent API**
- **@agent()**: Transform functions into intelligent agents
- **Automatic Registration**: Agents discover each other dynamically
- **Message Filtering**: Agents respond only to relevant communications
- **Thread-Safe Execution**: Concurrent processing with automatic resource management

#### **🏗️ Reef Communication System**
- **Knowledge-First Messaging**: All communication carries structured, semantic data
- **Spore Protocol**: JSON messages that agents broadcast and consume
- **Channel Management**: Organized communication streams
- **Self-Organization**: Agents coordinate without central orchestration

#### **🔧 Production-Ready Infrastructure**
- **Multi-LLM Support**: OpenAI, Anthropic, Cohere, and more
- **State Persistence**: Conversation memory and context management
- **Error Handling**: Graceful degradation and retry mechanisms
- **Resource Management**: Automatic cleanup and optimization

#### **🔒 Secure Spores Messaging** *(Enterprise Edition)*
- **End-to-End Encryption**: PyNaCl cryptography (Curve25519 + XSalsa20 + Poly1305)
- **Digital Signatures**: Ed25519 for message authenticity and integrity
- **Multi-Protocol Transport**: AMQP (RabbitMQ), MQTT (Mosquitto), STOMP (ActiveMQ)
- **TLS/SSL Security**: Certificate-based transport encryption
- **Key Management**: Automatic key rotation and forward secrecy
- **Distributed Architecture**: Horizontally scalable with message queue clustering

### **🏗️ Architecture Principles**

#### **🎯 Specialization Over Generalization**
```python
# ❌ Instead of one agent doing everything
general_agent = Agent("do_everything", "You can handle any task perfectly")

# ✅ Praval encourages focused specialists
@agent("researcher", responds_to=["research_query"])
def research_specialist(spore):
    """I excel at finding and analyzing information."""
    
@agent("writer", responds_to=["content_request"])
def writing_specialist(spore):
    """I excel at creating compelling content."""
```

#### **🌊 Reef Communication Philosophy**
- **Knowledge-First**: Every message carries structured, semantic data
- **Self-Organization**: Agents coordinate without central control
- **Emergent Intelligence**: Complex behaviors arise from simple interactions
- **Natural Flow**: Information flows like nutrients in a coral reef

#### **🛡️ Production-Ready Features**
- **Error Resilience**: Individual agent failures don't crash the system
- **Resource Management**: Automatic cleanup and thread pool optimization
- **Message Filtering**: Agents process only relevant communications
- **Graceful Degradation**: Systems adapt when agents are unavailable

## 📦 **Installation**

```bash
# Install from PyPI (recommended)
pip install praval

# Or with UV (faster)
uv pip install praval

# Install from source
git clone https://github.com/aiexplorations/praval.git
cd praval
pip install -e .
```

### **Development Installation**

```bash
# Clone and install in development mode
git clone https://github.com/aiexplorations/praval.git
cd praval

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with development dependencies
pip install -e ".[dev]"
```

### **Environment Setup**
```bash
# Required: At least one LLM API key
OPENAI_API_KEY=your_openai_key        # Recommended
ANTHROPIC_API_KEY=your_anthropic_key  # Optional
COHERE_API_KEY=your_cohere_key        # Optional

# Memory System (Optional)
QDRANT_URL=http://localhost:6333      # For vector storage
PRAVAL_COLLECTION_NAME=praval_memories

# Framework Configuration (Optional)
PRAVAL_LOG_LEVEL=INFO
PRAVAL_MAX_THREADS=10
PRAVAL_DEFAULT_PROVIDER=openai
PRAVAL_DEFAULT_MODEL=gpt-4o-mini

# Secure Spores Configuration (Enterprise)
PRAVAL_TRANSPORT_PROTOCOL=amqp        # amqp, mqtt, or stomp
PRAVAL_AMQP_URL=amqps://user:pass@host:5671/vhost
PRAVAL_MQTT_HOST=localhost
PRAVAL_MQTT_PORT=8883
PRAVAL_TLS_CA_CERT=/path/to/ca.pem
PRAVAL_TLS_CLIENT_CERT=/path/to/client.pem
PRAVAL_TLS_CLIENT_KEY=/path/to/client.key
```
## ⚡ **Quick Start**

### **1. Simple Agent Creation**
```python
from praval import agent, chat, broadcast, start_agents

# Create a specialized agent with just a decorator
@agent("research_expert", responds_to=["research_query"])
def research_agent(spore):
    """I'm an expert at finding and analyzing information."""
    query = spore.knowledge.get("query")
    result = chat(f"Research this topic deeply: {query}")
    
    # Broadcast findings to other agents
    broadcast({
        "type": "research_complete",
        "findings": result,
        "confidence": 0.9
    })
    
    return {"research": result}

# Start the agent system
start_agents(research_agent, initial_data={
    "type": "research_query", 
    "query": "quantum computing applications"
})
```

### **2. Multi-Agent Collaboration**
```python
@agent("analyzer", responds_to=["research_complete"])
def analysis_agent(spore):
    """I analyze research findings for insights."""
    findings = spore.knowledge.get("findings")
    analysis = chat(f"Analyze these findings for key insights: {findings}")
    return {"analysis": analysis}

@agent("writer", responds_to=["analysis_complete"])
def writing_agent(spore):
    """I create polished reports from analysis."""
    analysis = spore.knowledge.get("analysis")
    report = chat(f"Write a professional report: {analysis}")
    return {"report": report}

# All agents coordinate automatically!
start_agents(research_agent, analysis_agent, writing_agent)
```

## 🏛️ **Architecture Overview**

### **🧠 The Praval Mental Model**

Think of Praval as creating **AI coral reefs** - ecosystems where:
- 🐠 **Agents are organisms** with specialized roles
- 🌊 **The Reef is the communication medium** enabling knowledge flow
- 🌿 **Spores are knowledge packets** that agents exchange
- 🏛️ **Emergent intelligence** arises from collective interaction

### **⚙️ Core Components**

#### **🎭 Agents - The Specialized Workers**
```python
@agent("name", responds_to=["message_types"], channel="optional")
def agent_function(spore):
    """Define what the agent IS, not what it DOES"""
    # Agent processes spore.knowledge
    # Returns results or broadcasts to others
```
- **Identity-Based Design**: Agents are defined by their role, not procedures
- **Message Filtering**: Only process relevant communications
- **Automatic Registration**: Self-discovery and coordination
- **Thread-Safe Execution**: Concurrent processing with resource management

#### **🌊 The Reef - Communication Substrate**
- **Spore Protocol**: JSON messages carrying structured knowledge
- **Channel System**: Organized communication streams
- **Broadcast/Unicast**: Flexible message routing patterns
- **Message Persistence**: Reliable delivery and replay capabilities

#### **📦 Spores - Knowledge Containers**
```python
spore = {
    "id": "unique_identifier",
    "type": "research_finding",
    "knowledge": {
        "topic": "quantum_computing",
        "insights": [...],
        "confidence": 0.89
    },
    "from_agent": "researcher",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

#### **🔧 Built-in Capabilities**
- **Multi-LLM Support**: OpenAI, Anthropic, Cohere integration
- **State Persistence**: Conversation memory and context tracking
- **Error Handling**: Graceful failure recovery and retry logic
- **Resource Management**: Automatic thread pool and memory optimization
## 🚀 **Real-World Usage Patterns**

### **🎬 Complete Business Analysis Workflow**
*From VentureLens - see it in action:*

```python
from praval import agent, broadcast, start_agents

# Business analysis pipeline - each agent specializes
venture = {}  # Shared state

@agent("interviewer", responds_to=["start_interview", "answer_provided"])
def conduct_interview(spore):
    """I ask insightful questions about business ideas."""
    if venture.get("questions_asked", 0) < 8:
        # Generate contextual follow-up questions
        question = generate_smart_question(venture["responses"])
        print(f"💬 {question}")
        venture["current_question"] = question
    else:
        broadcast({"type": "interview_complete", "responses": venture["responses"]})

@agent("analyst", responds_to=["interview_complete"])
def analyze_viability(spore):
    """I evaluate business ideas across 6 dimensions."""
    responses = spore.knowledge["responses"]
    analysis = {
        "viability_score": 7.8,
        "problem_solution_fit": 8.5,
        "market_potential": 8.0,
        "strengths": ["Clear market need", "Strong differentiation"],
        "recommendations": ["Focus on MVP", "Validate with customers"]
    }
    broadcast({"type": "analysis_complete", "analysis": analysis})

@agent("reporter", responds_to=["analysis_complete"])
def generate_report(spore):
    """I create professional PDF reports."""
    analysis = spore.knowledge["analysis"]
    report = create_professional_pdf(analysis)
    broadcast({"type": "report_generated", "filename": report})

@agent("presenter", responds_to=["report_generated"], auto_broadcast=False)
def present_results(spore):
    """I present results and auto-open reports in browser."""
    filename = spore.knowledge["filename"]
    print(f"📄 Analysis complete: {filename}")
    open_in_browser(filename)  # Auto-open PDF and HTML

# Start the entire workflow with one command!
start_agents(
    conduct_interview, analyze_viability, generate_report, present_results,
    initial_data={"type": "start_interview", "idea": "AI-powered solopreneur toolkit"}
)
```

### **🧠 Knowledge Discovery Pipeline**
*From our knowledge graph miners:*

```python
@agent("domain_expert", responds_to=["explore_concept"])
def find_concepts(spore):
    """I identify core concepts and their relationships."""
    concept = spore.knowledge["concept"]
    related = chat(f"Find 10 concepts closely related to {concept}")
    
    broadcast({
        "type": "concepts_found",
        "base_concept": concept,
        "related_concepts": parse_concepts(related)
    })

@agent("relationship_analyst", responds_to=["concepts_found"])
def analyze_relationships(spore):
    """I determine how concepts connect to each other."""
    concepts = spore.knowledge["related_concepts"]
    relationships = []
    
    for concept_pair in combinations(concepts, 2):
        relationship = chat(f"How are {concept_pair[0]} and {concept_pair[1]} related?")
        relationships.append({
            "from": concept_pair[0],
            "to": concept_pair[1], 
            "relationship": relationship
        })
    
    broadcast({"type": "relationships_mapped", "relationships": relationships})

@agent("graph_builder", responds_to=["relationships_mapped"])
def build_knowledge_graph(spore):
    """I construct the final knowledge graph structure."""
    relationships = spore.knowledge["relationships"]
    graph = construct_graph(relationships)
    save_graph(graph, "knowledge_graph.json")
    print(f"🕸️ Knowledge graph built with {len(graph.nodes)} nodes!")

# Mine any topic automatically
start_agents(
    find_concepts, analyze_relationships, build_knowledge_graph,
    initial_data={"type": "explore_concept", "concept": "quantum computing"}
)
```

### **💬 Intelligent Conversation System**
*Multi-agent RAG chatbot pattern:*

```python
@agent("retriever", responds_to=["user_query"])
def find_relevant_context(spore):
    """I find relevant information from knowledge base."""
    query = spore.knowledge["query"]
    context = vector_search(query, top_k=5)
    
    broadcast({
        "type": "context_retrieved",
        "query": query,
        "context": context
    })

@agent("responder", responds_to=["context_retrieved"])
def generate_response(spore):
    """I craft responses using retrieved context."""
    query = spore.knowledge["query"]
    context = spore.knowledge["context"]
    
    response = chat(f"""
    Question: {query}
    Relevant Context: {context}
    
    Provide a comprehensive answer based on the context.
    """)
    
    return {"response": response}

# Each user query triggers the full RAG pipeline
start_agents(find_relevant_context, generate_response, 
    initial_data={"type": "user_query", "query": "How does quantum entanglement work?"})
```

### Reef Communication System

The **Reef** enables knowledge-first communication between agents through structured JSON messages called **spores**. Like coral reefs facilitate biological communication, the Reef connects all agents in a living communication network.

#### Core Concepts

- **Reef** - The message queue network connecting all agents
- **Spores** - JSON messages containing knowledge, data, or requests  
- **Channels** - Named communication channels within the reef
- **Knowledge-First** - All communication carries structured, semantic data

#### Basic Communication

```python
from praval import Agent, register_agent, get_reef

# Create and register agents
researcher = Agent("researcher", system_message="You research topics deeply")
analyzer = Agent("analyzer", system_message="You analyze data patterns")

register_agent(researcher)
register_agent(analyzer)

# Knowledge sharing between agents
researcher.send_knowledge("analyzer", {
    "topic": "quantum_computing",
    "findings": ["coherence_improved", "error_rates_reduced"],
    "confidence": 0.89,
    "source": "latest_research"
})

# Broadcasting discoveries to all agents
researcher.broadcast_knowledge({
    "breakthrough": "room_temperature_superconductor",
    "impact": "revolutionary",
    "verification_needed": True
})
```

#### Request-Response Pattern

```python
# Agent requests knowledge from another
analyzer.subscribe_to_channel("main")  # Subscribe to receive responses

def handle_requests(spore):
    if spore.spore_type == SporeType.REQUEST and spore.to_agent == "analyzer":
        # Process request and send response
        if spore.knowledge.get("query") == "analyze_data":
            response = {"result": "analysis_complete", "insights": [...]}
            get_reef().reply(
                from_agent="analyzer",
                to_agent=spore.from_agent, 
                response=response,
                reply_to_spore_id=spore.id
            )

# Override spore handler
analyzer.on_spore_received = handle_requests

# Request knowledge with timeout
response = researcher.request_knowledge("analyzer", {
    "query": "analyze_data",
    "dataset": "experiment_results",
    "priority": "high"
}, timeout=30)

if response:
    print(f"Analysis result: {response}")
```

#### Multi-Channel Communication

```python
reef = get_reef()

# Create specialized channels
reef.create_channel("research", max_capacity=500)  
reef.create_channel("alerts", max_capacity=100)
reef.create_channel("coordination", max_capacity=200)

# Agents subscribe to relevant channels
researcher.subscribe_to_channel("research")
researcher.subscribe_to_channel("coordination")

analyzer.subscribe_to_channel("alerts")
analyzer.subscribe_to_channel("coordination")

# Send to specific channels
researcher.send_knowledge("analyzer", {
    "paper": "quantum_error_correction",
    "significance": "breakthrough"
}, channel="research")

# Broadcast alerts
system_monitor = Agent("monitor")
system_monitor.broadcast_knowledge({
    "alert": "system_overload",
    "severity": "high",
    "action_required": True
}, channel="alerts")
```

#### Agent Coordination and Handoffs

```python
class CoordinatedAgent(Agent):
    def __init__(self, name, specialization):
        super().__init__(name)
        self.specialization = specialization
        self.active_tasks = {}
        
    def on_spore_received(self, spore):
        """Handle incoming spores with task coordination."""
        if spore.spore_type == SporeType.REQUEST:
            if self.can_handle_task(spore.knowledge):
                self.accept_task(spore)
            else:
                self.delegate_task(spore)
                
    def can_handle_task(self, task_data):
        """Check if this agent can handle the task."""
        return task_data.get("domain") == self.specialization
        
    def delegate_task(self, original_spore):
        """Hand off task to more suitable agent."""
        suitable_agent = self.find_suitable_agent(original_spore.knowledge)
        if suitable_agent:
            self.send_knowledge(suitable_agent, {
                "handoff": True,
                "original_request": original_spore.knowledge,
                "from_agent": original_spore.from_agent,
                "reason": f"Better handled by {suitable_agent}",
                "context": self.get_task_context()
            })

# Create coordinated multi-agent system
nlp_agent = CoordinatedAgent("nlp_specialist", "natural_language_processing")
cv_agent = CoordinatedAgent("cv_specialist", "computer_vision") 
coordinator = CoordinatedAgent("coordinator", "task_management")

for agent in [nlp_agent, cv_agent, coordinator]:
    register_agent(agent)
    agent.subscribe_to_channel("coordination")
```

### Simple Agent Creation

```python
from praval import Agent

# Create an agent with system message
agent = Agent(
    "assistant",
    system_message="You are a helpful assistant."
)

# Chat with the agent
response = agent.chat("Hello, how are you?")
print(response)
```

## ⚙️ **Configuration**

### **Environment Variables**
```bash
# LLM Provider Configuration
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
COHERE_API_KEY=your_cohere_key

# Praval Framework Settings
PRAVAL_DEFAULT_PROVIDER=openai     # Default LLM provider
PRAVAL_DEFAULT_MODEL=gpt-4-turbo    # Default model
PRAVAL_MAX_THREADS=10              # Thread pool size
PRAVAL_LOG_LEVEL=INFO              # Logging level
PRAVAL_REEF_CAPACITY=1000          # Message queue capacity
```

### **Runtime Configuration**
```python
from praval import configure

# Configure framework defaults
configure({
    "default_provider": "openai",
    "default_model": "gpt-4-turbo", 
    "max_concurrent_agents": 10,
    "reef_config": {
        "channel_capacity": 1000,
        "message_ttl": 3600  # seconds
    }
})
```

## 🛠️ **Development Guide**

### **Project Structure**
```
praval/
├── src/praval/
│   ├── __init__.py           # Main API exports
│   ├── decorators.py         # @agent decorator magic
│   ├── composition.py        # start_agents orchestration
│   └── core/
│       ├── agent.py          # Agent implementation
│       ├── reef.py           # Communication system
│       ├── registry.py       # Agent discovery
│       └── storage.py        # State persistence
├── examples/                 # Complete working examples
│   ├── venturelens.py        # Business analysis platform
│   ├── knowledge_graph_miner.py  # Advanced KG mining
│   ├── pythonic_knowledge_graph.py  # Simplified KG
│   ├── rag_chatbot.py        # RAG conversation system
│   └── arxiv_paper_downloader.py # Research automation
└── tests/                    # Comprehensive test suite
```

### **Testing & Validation**
```bash
# Run full test suite
pytest tests/ -v

# Test with coverage reporting
pytest --cov=praval --cov-report=html

# Test specific components
pytest tests/test_reef.py -v          # Communication system
pytest tests/test_agent.py -v         # Agent functionality
pytest tests/test_self_organizing_agents.py -v  # Multi-agent coordination

# Validate examples
python examples/pythonic_knowledge_graph.py
python examples/venturelens.py
```

### **Contributing Guidelines**
```python
# Follow Praval principles when adding new features:

# ✅ Good: Specialized, focused agents
@agent("validator", responds_to=["validation_request"])
def data_validator(spore):
    """I specialize in data quality validation."""
    
# ❌ Avoid: Monolithic, do-everything agents  
@agent("super_agent", responds_to=["everything"])
def handle_everything(spore):
    """I handle all possible tasks."""
```

## 🗺️ **Roadmap**

### **✅ Phase 1: Foundation Complete**
- **✓ Decorator API**: Clean `@agent()` decorator system
- **✓ Reef Communication**: Knowledge-first messaging protocol
- **✓ Multi-LLM Support**: OpenAI, Anthropic, Cohere integration
- **✓ Self-Organization**: Agents coordinate without central control
- **✓ Production Examples**: VentureLens business analyzer
- **✓ Concurrent Processing**: Thread-safe multi-agent execution
- **✓ Message Filtering**: Agents respond only to relevant communications

### **✅ Phase 2: Advanced Patterns Complete (v0.5.0)**
- **✓ Memory Integration**: ChromaDB embedded vector storage
- **✓ Comprehensive Testing**: 99% coverage on core decorators and composition
- **✓ Semantic Memory**: Persistent knowledge with semantic search
- **✓ Knowledge Base**: Auto-indexing of documents and files
- **✓ Multi-layered Memory**: Short-term, long-term, episodic, semantic memory
- **✓ Complex Workflows**: Multi-stage business analysis pipelines
- **✓ Dynamic Coordination**: Agents discover and delegate tasks

### **🚀 Phase 3: Enterprise Ready (Current)**
- **🚧 Streaming Responses**: Real-time token streaming from agents  
- **🚧 Tool Ecosystem**: External API and service integration
- **🚧 Visual Debugging**: Agent interaction visualization
- **📈 Observability Suite**: Comprehensive metrics and tracing
- **🔒 Security Framework**: Content filtering and access control
- **⚡ Performance Optimization**: Caching, rate limiting, cost management
- **🐝 Horizontal Scaling**: Distributed agent deployment

### **🎆 Phase 4: Advanced Intelligence**
- **🤖 Agent Evolution**: Self-improving agent capabilities
- **🌍 Multi-Modal Agents**: Vision, audio, and text integration
- **🎨 Creative Collaboration**: Agents for design, writing, and art
- **🔬 Scientific Discovery**: Agents for research and analysis
- **🏭 Industry Solutions**: Specialized agent packages for domains

## 🔄 **Versioning & Releases**

Praval follows [Semantic Versioning](https://semver.org/) with **automated version bumping**:

### **Current Status**: `v0.5.0` (Pre-1.0 Beta)

### **Automatic Release Process**
Every push to `main` triggers automatic version bumping based on commit messages:

#### 🔵 **Minor Release** (New features: `0.5.0 → 0.6.0`)
```bash
git commit -m "fix: Memory leak in agent cleanup"
git commit -m "docs: Update installation guide"  
git commit -m "test: Add coverage for edge cases"
```

#### 🟡 **Minor Release** (New features: `0.5.0 → 0.6.0`)
```bash
git commit -m "feat: Add streaming response capability"
git commit -m "add: New knowledge base integration"
git commit -m "enhance: Improve memory performance"
```

#### 🔴 **Major Release** (Breaking changes: `0.5.0 → 1.0.0`)
```bash
git commit -m "BREAKING CHANGE: Redesign agent decorator API"
git commit -m "major: Remove deprecated memory interface"
```

### **Installation from Releases**
```bash
# Latest development version
pip install git+https://github.com/aiexplorations/praval.git

# Specific version
pip install git+https://github.com/aiexplorations/praval.git@v0.5.0
```

### **Contributing**
See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for detailed guidelines on contributing and triggering version bumps.

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🎯 **Complete Examples**

### **📚 Memory-Enabled Learning System**
*`examples/005_memory_enabled_agents.py`* - **Showcasing Praval's memory capabilities**

**What it demonstrates**: A learning system where agents build relationships and knowledge through persistent memory.

**Multi-Agent Architecture**:
- **🧠 Learning Agent**: Remembers past sessions and builds on previous knowledge
- **👨‍🏫 Teaching Agent**: Adapts teaching methods based on student history
- **🤔 Reflection Agent**: Analyzes patterns from memory to improve future interactions

### **🔗 Agent Communication & Collaboration**
*Complete example series demonstrating core Praval patterns*

#### **Core Example Series**:
- **`001_single_agent_identity.py`**: How agent identity drives behavior
- **`002_agent_communication.py`**: Basic agent-to-agent communication  
- **`003_specialist_collaboration.py`**: Specialized agents working together
- **`004_registry_discovery.py`**: Dynamic agent discovery and coordination
- **`005_memory_enabled_agents.py`**: Persistent memory and learning
- **`006_resilient_agents.py`**: Error handling and fault tolerance
- **`007_adaptive_agent_systems.py`**: Self-adapting agent behaviors
- **`008_self_organizing_networks.py`**: Emergent network behaviors
- **`009_emergent_collective_intelligence.py`**: Complex behaviors from simple agents

```python
# Simple agent identity example
@agent("philosopher", responds_to=["deep_question"])
def philosopher_agent(spore):
    """I ask insightful questions about business ideas."""
    # Dynamic question generation using AI
    next_question = generate_smart_question(previous_answers)
    return ask_user(next_question)

@agent("analyst", responds_to=["interview_complete"])
def analyze_business_viability(spore):
    """I evaluate business ideas across multiple dimensions."""
    # Comprehensive analysis with scoring
    analysis = evaluate_idea(interview_data)
    return {"viability_score": 8.2, "analysis": analysis}
```

**Key Features**:
- ✨ **489 lines → 50 lines**: Dramatic code simplification
- 🧠 **Dynamic Questioning**: AI generates contextual follow-ups
- 📊 **Multi-Dimensional Analysis**: SWOT, financial projections, market research
- 📄 **Professional Reports**: LaTeX-styled PDFs with auto-browser opening
- 🔄 **Self-Organizing Workflow**: Agents coordinate the entire process

### **🕸️ Knowledge Graph Mining Suite**

#### **Advanced Multi-Threading Version** 
*`examples/knowledge_graph_miner.py`* - Concurrent agent processing

- **🧠 Domain Expert**: Identifies core concepts and relationships
- **🔍 Relationship Analyst**: Maps connections between concepts
- **⚡ Concurrent Execution**: True parallel LLM processing
- **📡 Thread-Safe Communication**: Reef messaging across threads
- **🎯 Message Filtering**: Agents respond only to relevant messages

#### **Pythonic Simplified Version**
*`examples/pythonic_knowledge_graph.py`* - Clean decorator API showcase

- **📉 Complexity Reduction**: From complex classes to simple functions
- **🎨 Declarative Design**: Define agent identity, not procedures  
- **⚙️ Automatic Coordination**: No manual threading or state management
- **✨ Emergent Intelligence**: Complex graphs from simple agent collaboration

### **💬 RAG Chatbot**
*`examples/rag_chatbot.py`* - Retrieval-augmented conversation system

- **🔍 Document Processing**: Intelligent text chunking and embedding
- **🧠 Context Retrieval**: Semantic search for relevant information
- **💭 Conversational Memory**: Multi-turn dialogue management
- **📚 Knowledge Integration**: Combines retrieved context with AI generation

### **📚 ArXiv Paper Downloader**
*`examples/arxiv_paper_downloader.py`* - Automated research paper acquisition

- **🔍 Query Processing**: Intelligent search term optimization
- **📄 Batch Downloads**: Efficient paper retrieval and organization
- **📊 Metadata Extraction**: Author, abstract, and citation information
- **🗂️ File Management**: Organized storage with deduplication

### **🎯 API Pattern Examples**
*`examples/target_api_examples.py`* - Core framework demonstrations

- **🏗️ Foundation Patterns**: Basic agent creation and registration
- **🤝 Collaboration Examples**: Agent-to-agent communication
- **🔧 Tool Integration**: External API and service connections
- **📋 Best Practices**: Recommended implementation patterns

## 🔒 **Secure Spores Messaging** *(Enterprise Edition)*

Praval includes an enterprise-grade secure messaging system that transforms the framework from local agent coordination to distributed, encrypted, multi-agent platforms.

### **🛡️ Security Features**
- **🔐 End-to-End Encryption**: PyNaCl cryptography (Curve25519 + XSalsa20 + Poly1305)
- **✅ Digital Signatures**: Ed25519 for message authenticity and integrity
- **🔄 Key Rotation**: Automatic key management with forward secrecy
- **🛡️ TLS Transport**: Certificate-based transport layer security
- **🔒 Tamper-Proof**: Authenticated encryption prevents message modification

### **📡 Supported Protocols**
- **🐰 AMQP**: RabbitMQ with TLS support and management plugins
- **📡 MQTT**: Eclipse Mosquitto with WebSocket and TLS support  
- **🔌 STOMP**: ActiveMQ with SSL and enterprise features
- **⚡ Redis**: High-performance key-value messaging (planned)
- **🚀 NATS**: Cloud-native messaging (planned)

### **🐳 Quick Start with Docker**

```bash
# Clone and start secure infrastructure
git clone https://github.com/aiexplorations/praval.git
cd praval

# Start the full secure messaging stack
docker-compose -f docker/docker-compose.secure.yml up -d

# Run secure spore demo
docker-compose exec praval-secure python examples/secure_spore_demo.py

# Development with Jupyter (secure environment)
docker-compose --profile dev up jupyter-secure
# Access: http://localhost:8889 (token: praval_secure_2024)
```

### **🏗️ Infrastructure Services**

The secure deployment includes:

| Service | Port | Purpose | TLS |
|---------|------|---------|-----|
| **RabbitMQ** | 5671/5672 | AMQP message broker | ✅ |
| **Mosquitto** | 8883/8884 | MQTT message broker | ✅ |
| **ActiveMQ** | 61614/61613 | STOMP message broker | ✅ |
| **Qdrant** | 6333 | Vector database for memory | ✅ |
| **Redis** | 6379 | Key registry & caching | ✅ |
| **Jupyter** | 8889 | Secure development environment | ✅ |

### **💻 Example: Secure Agent Communication**

```python
from praval.core.secure_reef import SecureReef
from praval.core.secure_spore import SecureSporeFactory

# Initialize secure messaging
secure_reef = SecureReef(
    transport_protocol='amqp',
    amqp_url='amqps://user:pass@rabbitmq:5671/secure',
    tls_config={
        'ca_cert': '/certs/ca.pem',
        'client_cert': '/certs/client.pem', 
        'client_key': '/certs/client.key'
    }
)

# Create secure spore factory with encryption
spore_factory = SecureSporeFactory(
    signing_key=ed25519_private_key,
    encryption_key=curve25519_private_key
)

# Send encrypted message between agents
secure_spore = spore_factory.create_secure_spore(
    knowledge={"classified_data": "top_secret_analysis"},
    to_agent="analyst_agent",
    encryption_enabled=True
)

await secure_reef.send_secure_spore(secure_spore)
```

## 🐳 **Docker Deployment**

Praval supports both local development and production deployment through comprehensive Docker infrastructure.

### **📦 Available Configurations**

#### **Development Mode**
```bash
# Standard development with local services
docker-compose up -d

# With Jupyter Lab
docker-compose --profile dev up jupyter
# Access: http://localhost:8888
```

#### **Secure Production Mode**
```bash
# Enterprise secure messaging infrastructure  
docker-compose -f docker/docker-compose.secure.yml up -d

# Includes: RabbitMQ, MQTT, STOMP, Qdrant, Redis, TLS certificates
# All services configured with enterprise security
```

### **🔧 Service Configuration**

**Standard Services:**
- **Praval App**: Main application container
- **Qdrant**: Vector database for agent memory (http://localhost:6333)
- **Jupyter**: Development environment (http://localhost:8888)

**Secure Services:**
- **All standard services** plus:
- **RabbitMQ**: Message broker with AMQP/MQTT/STOMP
- **Mosquitto**: Dedicated MQTT broker
- **ActiveMQ**: Enterprise STOMP messaging
- **Redis**: Key registry and caching
- **TLS Certificates**: Automatic certificate management

### **⚙️ Environment Variables**

```bash
# Core configuration
OPENAI_API_KEY=your_key
PRAVAL_LOG_LEVEL=INFO

# Secure messaging
PRAVAL_TRANSPORT_PROTOCOL=amqp
PRAVAL_AMQP_URL=amqps://praval:secure_pass@rabbitmq:5671/praval
PRAVAL_TLS_CA_CERT=/app/certs/ca_certificate.pem

# Development
JUPYTER_TOKEN=your_secure_token
```

### **📋 Health Monitoring**

All services include health checks and monitoring:

```bash
# Check service health
docker-compose ps

# View logs
docker-compose logs praval-secure
docker-compose logs rabbitmq

# Access management interfaces
# RabbitMQ: http://localhost:15672 (admin/secure_praval_2024)
# ActiveMQ: http://localhost:8161 (admin/secure_activemq_2024)
```

## 📞 **Community & Support**

### **👥 Getting Help**
- **🐛 GitHub Issues**: Report bugs and request features
- **📚 Documentation**: Comprehensive guides in `/docs`  
- **🎯 Examples**: Complete working applications in `/examples`
- **🧠 Philosophy**: Deep dive into Praval principles in `praval.md`
- **💬 Discussions**: Community Q&A and best practices

### **🎆 Showcase Your Work**
**Built something amazing with Praval?** We'd love to feature it!

- **🏆 Agent Showcases**: Highlight innovative agent architectures
- **🚀 Success Stories**: Share your production implementations
- **📚 Tutorial Contributions**: Help others learn Praval patterns
- **🎆 Community Examples**: Expand the examples library

### **🕰️ Quick Links**
- **🚀 Get Started**: Follow the Quick Start guide above
- **📊 See Results**: Run VentureLens for a complete demo
- **🧠 Understand Philosophy**: Read `praval.md` for design principles
- **🔧 Contribute**: Check development guidelines above