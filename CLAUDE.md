# Praval - AI Multi-Agent Framework

**The Pythonic Multi-Agent AI Framework for building intelligent, collaborative agent systems**

> *Praval (प्रवाल) - Sanskrit for coral, representing how simple agents collaborate to create complex, intelligent ecosystems.*

## 🚨 IMPORTANT: Always Use Virtual Environment

**CRITICAL REMINDER**: Always activate and use the virtual environment for all Python operations:
```bash
source venv/bin/activate  # Always run this first!
```

All pytest, pip, python commands must be run within the activated venv. Never forget this step!

## 🚀 Project Overview

Praval is a revolutionary Python framework that transforms complex AI applications into simple, composable agent systems. Instead of monolithic AI systems, Praval enables you to create ecosystems of specialized agents that collaborate intelligently through a coral reef-inspired architecture.

### Key Stats
- **Version**: 0.3.0
- **Python Support**: 3.9, 3.10, 3.11, 3.12
- **License**: MIT
- **Architecture**: Multi-agent, decorator-based, self-organizing

## 🏗️ Repository Structure

```
praval/
├── src/praval/                    # Core framework code
│   ├── __init__.py               # Main API exports
│   ├── decorators.py             # @agent decorator implementation
│   ├── composition.py            # Agent orchestration (start_agents)
│   ├── core/                     # Core framework components
│   │   ├── agent.py             # Agent base class and functionality
│   │   ├── reef.py              # Communication system (Spore protocol)
│   │   ├── registry.py          # Agent discovery and registration
│   │   ├── storage.py           # State persistence and management
│   │   └── exceptions.py        # Framework-specific exceptions
│   ├── memory/                   # Comprehensive memory system (NEW)
│   │   ├── memory_manager.py    # Unified memory coordination
│   │   ├── short_term_memory.py # Working memory (fast, temporary)
│   │   ├── long_term_memory.py  # Qdrant vector storage (persistent)
│   │   ├── episodic_memory.py   # Conversation history tracking
│   │   ├── semantic_memory.py   # Knowledge and facts storage
│   │   └── memory_types.py      # Memory type definitions
│   └── providers/                # LLM provider integrations
│       ├── openai.py            # OpenAI provider
│       ├── anthropic.py         # Anthropic Claude provider
│       ├── cohere.py            # Cohere provider
│       └── factory.py           # Provider factory and selection
├── examples/                     # Complete working examples
│   ├── venturelens.py           # Business analysis platform (FLAGSHIP)
│   ├── knowledge_graph_miner.py # Advanced multi-threading KG mining
│   ├── pythonic_knowledge_graph.py # Simplified KG demonstration
│   ├── rag_chatbot.py           # RAG conversation system
│   ├── memory_demo.py           # Memory system demonstration
│   ├── deep_search.py           # Deep search capabilities
│   ├── arxiv_paper_downloader.py # Research paper automation
│   ├── target_api_examples.py   # Core API pattern demonstrations
│   └── rl_rag_chatbot_working.py # Reinforcement learning RAG
├── tests/                        # Comprehensive test suite
│   ├── test_*.py                # Core functionality tests
│   ├── integration/             # Integration tests (NEW)
│   └── validation/              # Validation and demo scripts (NEW)
│       ├── validate_core.py     # Core framework validation
│       └── validate_implementation.py # Implementation validation
├── docs/                         # Documentation (ORGANIZED)
│   ├── memory-system.md         # Comprehensive memory system docs
│   ├── reef-communication-specification.md # Communication protocol
│   ├── phase1-specification.md  # Framework specifications
│   ├── claude-code-prompt.md    # Claude Code integration
│   ├── memory/                  # Memory-specific documentation
│   │   └── qdrant_agent_memory.md # Qdrant integration design
│   └── generated/               # Generated reports and analyses
│       ├── VentureLens_Demo_Analysis_*.md # Demo analysis reports
│       └── VentureLens_Demo_Analysis_*.pdf # Generated PDFs
├── docker/                       # Docker configuration
│   ├── jupyter/                 # Jupyter Lab setup
│   └── postgres/                # PostgreSQL initialization
├── pyproject.toml               # Modern Python packaging
├── docker-compose.yml           # Multi-service deployment
├── Dockerfile                   # Main application container
├── Dockerfile.jupyter          # Jupyter development container
├── requirements.txt            # Python dependencies
└── praval.md                   # Framework philosophy and design principles
```

## 🎯 Core Capabilities

### **1. Decorator-Based Agent API**
Transform functions into intelligent agents with simple decorators:

```python
from praval import agent, chat, broadcast, start_agents

@agent("researcher", responds_to=["research_query"])
def research_agent(spore):
    """I'm an expert at finding and analyzing information."""
    query = spore.knowledge.get("query")
    result = chat(f"Research this topic deeply: {query}")
    
    broadcast({
        "type": "research_complete",
        "findings": result,
        "confidence": 0.9
    })
    
    return {"research": result}
```

### **2. Reef Communication System**
Knowledge-first messaging between agents through structured "spores":

- **Spore Protocol**: JSON messages carrying structured knowledge
- **Channel Management**: Organized communication streams
- **Self-Organization**: Agents coordinate without central orchestration
- **Message Filtering**: Agents respond only to relevant communications

### **3. Multi-LLM Provider Support**
Seamless integration with multiple AI providers:
- **OpenAI**: GPT-4, GPT-3.5-turbo
- **Anthropic**: Claude models
- **Cohere**: Command and Generate models
- **Automatic Selection**: Based on available API keys

### **4. Comprehensive Memory System** 🧠 *(NEW)*
Multi-layered memory capabilities for persistent, intelligent agents:

- **Short-term Memory**: Fast working memory for immediate context
- **Long-term Memory**: Qdrant vector database for semantic search
- **Episodic Memory**: Conversation history and experience tracking
- **Semantic Memory**: Factual knowledge and concept relationships

## 🌟 Flagship Examples

### **VentureLens - AI Business Analyzer** 🏆
*`examples/venturelens.py`* - The premier demonstration of Praval's capabilities

**What it does**: A comprehensive business idea analysis platform that interviews users through AI agents and generates professional PDF reports.

**Multi-Agent Architecture**:
- **👨‍💼 Interviewer Agent**: Dynamic intelligent question generation
- **🔬 Research Agent**: Market intelligence gathering
- **📊 Analyst Agent**: Business viability evaluation across 6 dimensions
- **📝 Reporter Agent**: Professional markdown report creation
- **🎨 Presenter Agent**: PDF generation and auto-browser opening

**Key Features**:
- ✨ **489 lines → 50 lines**: Dramatic code simplification through decorator API
- 🧠 **Dynamic Questioning**: AI generates contextual follow-ups
- 📊 **Multi-Dimensional Analysis**: SWOT, financial projections, market research
- 📄 **Professional Reports**: LaTeX-styled PDFs with auto-browser opening
- 🔄 **Self-Organizing Workflow**: Agents coordinate the entire process

### **Knowledge Graph Mining Suite** 🕸️
Concurrent agent processing for building rich knowledge structures:

- **Advanced Version** (`knowledge_graph_miner.py`): Multi-threaded concurrent execution
- **Pythonic Version** (`pythonic_knowledge_graph.py`): Clean decorator API showcase

### **Memory-Enabled RAG Chatbot** 💬
*`examples/rag_chatbot.py`, `memory_demo.py`* - Intelligent conversation with persistent memory

- **Document Processing**: Intelligent chunking and embedding
- **Context Retrieval**: Semantic search for relevant information
- **Conversational Memory**: Multi-turn dialogue with long-term retention
- **Knowledge Integration**: Combines retrieved context with AI generation

## 🧠 Memory System

The comprehensive memory system enables agents to:
- **Remember** conversations and interactions across sessions
- **Learn** from experiences over time
- **Store** knowledge and facts persistently in Qdrant
- **Retrieve** relevant information contextually using vector search
- **Scale** to millions of memories with production-grade performance

### Memory Architecture
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

## 🐳 Docker Deployment

### Quick Start
```bash
# Clone and setup
git clone https://github.com/your-org/praval.git
cd praval

# Start with Docker Compose
docker-compose up -d

# Run flagship example
docker-compose exec praval-app python examples/venturelens.py

# Development with Jupyter
docker-compose --profile dev up jupyter
# Open http://localhost:8888
```

### Services Available
- **Qdrant**: http://localhost:6333 (vector database for memory)
- **Praval App**: Main application container
- **Jupyter Lab**: http://localhost:8888 (development environment)
- **PostgreSQL**: localhost:5432 (structured data storage)

## 🛠️ Development Setup

### Requirements
- **Python**: 3.9+ required
- **Dependencies**: Managed via pyproject.toml
- **Optional**: Docker for full deployment stack

### Core Dependencies
```toml
dependencies = [
    "openai>=1.0.0",
    "anthropic>=0.8.0", 
    "cohere>=4.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0"
]
```

### Development Tools
```toml
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.0.0",
    "isort>=5.12.0",
    "flake8>=6.0.0",
    "mypy>=1.0.0",
    "pre-commit>=3.0.0"
]
```

## 🧪 Testing

### Test Structure
- **Unit Tests**: Core functionality (`test_*.py`)
- **Integration Tests**: Multi-component interactions (`tests/integration/`)
- **Validation Scripts**: End-to-end validation (`tests/validation/`)
- **Example Tests**: Verify examples work correctly

### Running Tests
```bash
# Full test suite
pytest tests/ -v

# With coverage
pytest --cov=praval --cov-report=html

# Specific components
pytest tests/test_reef.py -v          # Communication system
pytest tests/test_agent.py -v         # Agent functionality
pytest tests/test_memory.py -v        # Memory system
```

## 📚 Key Documentation

### Framework Philosophy
- **`praval.md`**: Core philosophy and design principles
- **"Simple agents, powerful results"**: Specialization over generalization
- **Coral reef metaphor**: Complex ecosystems from simple collaboration

### Technical Specifications
- **`docs/memory-system.md`**: Comprehensive memory capabilities
- **`docs/reef-communication-specification.md`**: Spore protocol details
- **`docs/phase1-specification.md`**: Framework architecture

### Memory System Deep Dive
- **Multi-layered Architecture**: Short-term, long-term, episodic, semantic
- **Qdrant Integration**: Production-scale vector database
- **Zero Configuration**: Works out-of-the-box with sensible defaults
- **Progressive Enhancement**: Basic to advanced features

## 🚀 Framework Evolution

### ✅ Phase 1: Foundation (Complete)
- **✓ Decorator API**: Clean `@agent()` decorator system
- **✓ Reef Communication**: Knowledge-first messaging protocol
- **✓ Multi-LLM Support**: OpenAI, Anthropic, Cohere integration
- **✓ Self-Organization**: Agents coordinate without central control
- **✓ Production Examples**: VentureLens business analyzer

### 🔄 Phase 2: Advanced Patterns (Current)
- **✓ Complex Workflows**: Multi-stage business analysis pipelines
- **✓ Memory Integration**: Comprehensive memory system with Qdrant
- **🚧 Streaming Responses**: Real-time token streaming from agents
- **🚧 Tool Ecosystem**: External API and service integration
- **🚧 Visual Debugging**: Agent interaction visualization

### 🚀 Phase 3: Enterprise Ready
- **📈 Observability Suite**: Comprehensive metrics and tracing
- **🔒 Security Framework**: Content filtering and access control
- **⚡ Performance Optimization**: Caching, rate limiting, cost management
- **🐝 Horizontal Scaling**: Distributed agent deployment

## 🎯 Development Guidelines

### Code Quality Standards
- **Black**: Code formatting (line-length: 88)
- **isort**: Import organization (black profile)
- **mypy**: Type checking (strict mode)
- **pytest**: Comprehensive testing (>90% coverage)

### Architecture Principles
1. **Specialization Over Generalization**: Each agent excels at one thing
2. **Declarative Design**: Define what agents ARE, not what they DO
3. **Emergent Intelligence**: Complex behaviors from simple interactions
4. **Zero Configuration**: Sensible defaults, progressive enhancement
5. **Composability**: Agents combine naturally through standard interfaces

### Best Practices
- Follow the **Specialist Pattern**: Focused, single-purpose agents
- Use the **Registry Pattern**: Dynamic agent discovery and composition
- Implement **Memory-Aware Agents**: Leverage persistent memory for continuity
- Apply **Error Resilience**: Individual agent failures don't crash the system
- Maintain **Observable Behavior**: Agent communications are visible and loggable

## 🔧 Configuration

### Environment Variables
```bash
# LLM Provider Configuration
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
COHERE_API_KEY=your_cohere_key

# Praval Framework Settings
PRAVAL_DEFAULT_PROVIDER=openai
PRAVAL_DEFAULT_MODEL=gpt-4-turbo
PRAVAL_MAX_THREADS=10
PRAVAL_LOG_LEVEL=INFO

# Memory System Configuration
QDRANT_URL=http://localhost:6333
PRAVAL_COLLECTION_NAME=praval_memories
SHORT_TERM_MAX_ENTRIES=1000
SHORT_TERM_RETENTION_HOURS=24
```

### Runtime Configuration
```python
from praval import configure

configure({
    "default_provider": "openai",
    "default_model": "gpt-4-turbo",
    "max_concurrent_agents": 10,
    "reef_config": {
        "channel_capacity": 1000,
        "message_ttl": 3600
    },
    "memory_config": {
        "qdrant_url": "http://localhost:6333",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
    }
})
```

## 🎆 Recent Updates (Current Branch: qdrant_memory)

### Memory System Integration
- **Comprehensive memory system** with multi-layered architecture
- **Qdrant vector database** integration for semantic search
- **Zero-configuration setup** with sensible defaults
- **Progressive enhancement** from basic to advanced features

### Repository Organization
- **Restructured tests**: Moved validation scripts to `tests/validation/`
- **Organized documentation**: Memory docs in `docs/memory/`
- **Generated content cleanup**: Reports in `docs/generated/`
- **Improved project structure** following Python best practices

### Development Infrastructure
- **Enhanced Docker setup** with Jupyter Lab integration
- **Comprehensive testing** structure with integration tests
- **Modern packaging** with pyproject.toml
- **Development tooling** with pre-commit hooks and linting

## 🏁 Quick Start Commands

```bash
# Basic example (no dependencies needed)
python examples/pythonic_knowledge_graph.py

# Memory-enabled example (requires Qdrant)
docker-compose up -d qdrant
python examples/memory_demo.py

# Flagship business analyzer
python examples/venturelens.py

# Full development environment
docker-compose --profile dev up
# Access Jupyter at http://localhost:8888

# Run tests
pytest tests/ -v
```

---

**Praval transforms AI application development from complex, monolithic systems into simple, collaborative agent ecosystems. Like coral reefs in nature, complex intelligence emerges from the collaboration of simple, specialized agents.**

Start with the `pythonic_knowledge_graph.py` example to see the core concepts, then explore `venturelens.py` for a complete real-world application showcasing Praval's full potential.