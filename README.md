<div align="center">
  <img src="logo.png" alt="Praval Logo" width="200"/>

  # Praval

  **The Pythonic Multi-Agent AI Framework**

  Build AI applications as ecosystems of specialized agents that collaborate naturally through simple, decorator-based APIs.

  *Praval (प्रवाल) - Sanskrit for coral, representing how simple agents collaborate to create complex, intelligent ecosystems.*

  [![Version](https://img.shields.io/badge/version-0.7.11-blue.svg)](https://github.com/aiexplorations/praval/releases)
  [![PyPI](https://img.shields.io/pypi/v/praval.svg)](https://pypi.org/project/praval/)
  [![Python](https://img.shields.io/pypi/pyversions/praval.svg)](https://pypi.org/project/praval/)
  [![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
</div>

---

## Why Praval?

**Transform complexity into simplicity.** Instead of monolithic AI systems with 800+ lines of tangled logic, Praval enables you to create specialized agents that collaborate naturally:

```python
from praval import agent, chat, broadcast, start_agents

@agent("researcher", responds_to=["research_query"])
def research_agent(spore):
    """I'm an expert at finding and analyzing information."""
    result = chat(f"Research: {spore.knowledge['query']}")
    broadcast({"type": "research_complete", "findings": result})
    return {"research": result}

@agent("analyst", responds_to=["research_complete"])
def analysis_agent(spore):
    """I analyze research findings for insights."""
    analysis = chat(f"Analyze: {spore.knowledge['findings']}")
    return {"analysis": analysis}

# They coordinate automatically!
start_agents(research_agent, analysis_agent,
    initial_data={"type": "research_query", "query": "quantum computing"})
```

**Result**: 489 lines → 50 lines. Complex coordination → Simple collaboration.

---

## Core Capabilities

### 🎯 **Decorator-Based Agents**
Transform functions into intelligent agents with `@agent()`. Agents are defined by identity, not procedures.

### 🧠 **Multi-Layered Memory**
ChromaDB-powered persistent memory with short-term, long-term, episodic, and semantic layers.

### 📡 **Reef Communication**
Knowledge-first messaging via "spores" - agents broadcast findings and respond to relevant messages.

### 📊 **Built-in Observability**
OpenTelemetry tracing with zero configuration. Export to Jaeger, Zipkin, DataDog, or view in console.

### 🔒 **Enterprise Security**
End-to-end encryption with PyNaCl, multi-protocol transport (AMQP, MQTT, STOMP), and TLS support.

### 🤖 **Multi-LLM Support**
Seamless integration with OpenAI, Anthropic, and Cohere with automatic provider selection.

### 🗃️ **Flexible Storage**
Multiple backends: PostgreSQL, Redis, S3, Qdrant, or local filesystem.

### 🔧 **Tool Ecosystem**
Equip agents with external capabilities through a simple decorator-based tool system.

---

## Installation

### Quick Start (Basic Agents)
```bash
pip install praval
```
**Includes**: Core framework, LLM providers (OpenAI, Anthropic, Cohere)

### With Memory (Recommended)
```bash
pip install praval[memory]
```
**Adds**: ChromaDB vector storage, semantic search, sentence transformers

### Full Installation (All Features)
```bash
pip install praval[all]
```
**Adds**: Secure messaging, storage providers, PDF support, enterprise features

### From Source
```bash
git clone https://github.com/aiexplorations/praval.git
cd praval
pip install -e .[all]
```

**Requirements**: Python 3.9+ and at least one LLM API key (OpenAI, Anthropic, or Cohere)

---

## 30-Second Example

```python
from praval import agent, chat, broadcast, start_agents

# Define specialized agents
@agent("researcher", responds_to=["query"])
def researcher(spore):
    """I research topics deeply."""
    findings = chat(f"Research: {spore.knowledge['topic']}")
    broadcast({"type": "analysis_request", "data": findings})

@agent("analyst", responds_to=["analysis_request"])
def analyst(spore):
    """I analyze data for insights."""
    insights = chat(f"Analyze: {spore.knowledge['data']}")
    broadcast({"type": "report_request", "insights": insights})

@agent("writer", responds_to=["report_request"])
def writer(spore):
    """I create polished reports."""
    report = chat(f"Write report: {spore.knowledge['insights']}")
    print(f"📄 Report: {report}")

# Launch the agent ecosystem
start_agents(researcher, analyst, writer,
    initial_data={"type": "query", "topic": "AI agents"})
```

**What happens**: Agents coordinate automatically through message passing. No central orchestrator needed.

---

## Architecture

<div align="center">

```
┌─────────────────────────────────────────────────┐
│           🎯 Agent Ecosystem                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │Researcher│  │ Analyst  │  │  Writer  │      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘      │
│       │             │             │             │
│       └─────────────┼─────────────┘             │
│                     │                           │
│           ┌─────────▼─────────┐                 │
│           │   🌊 Reef (Spores) │                 │
│           │  Message Passing   │                 │
│           └─────────┬─────────┘                 │
│                     │                           │
│       ┌─────────────┼─────────────┐             │
│       │             │             │             │
│  ┌────▼─────┐  ┌────▼─────┐  ┌───▼──────┐      │
│  │  Memory  │  │   LLM    │  │ Storage  │      │
│  │ (ChromaDB)│  │Providers │  │ Backends │      │
│  └──────────┘  └──────────┘  └──────────┘      │
└─────────────────────────────────────────────────┘
```

</div>

**Key Concepts**:
- **Agents**: Specialized functions decorated with `@agent()`
- **Spores**: JSON messages carrying structured knowledge
- **Reef**: Communication substrate connecting all agents
- **Emergence**: Complex intelligence from simple collaboration

---

## Real-World Examples

### Business Analysis Platform
**489 lines → 50 lines** of clean, maintainable code. [See full example →](examples/venturelens.py)

### Knowledge Graph Mining
Concurrent agents extract concepts and relationships. [See example →](examples/pythonic_knowledge_graph.py)

### RAG Chatbot
Memory-enabled conversational agents with semantic search. [See example →](examples/rag_chatbot.py)

### Research Assistant
Automated paper discovery and analysis. [See example →](examples/arxiv_paper_downloader.py)

**More examples** in the [`examples/`](examples/) directory covering memory systems, tool integration, and enterprise patterns.

---

## Key Features Deep Dive

### Memory System
Multi-layered architecture for persistent agent intelligence:
- **Short-term**: Fast working memory for immediate context
- **Long-term**: ChromaDB vector storage for semantic search
- **Episodic**: Conversation history and experience tracking
- **Semantic**: Factual knowledge and concept relationships

### Observability
Zero-config distributed tracing:
```python
from praval.observability import show_recent_traces, export_traces_to_otlp

# Automatic tracing - no code changes needed
@agent("researcher")
def research_agent(spore):
    return {"findings": chat(spore.knowledge['topic'])}

# View in console
show_recent_traces(limit=10)

# Export to monitoring platform
export_traces_to_otlp("http://localhost:4318/v1/traces")
```

### Secure Messaging
Enterprise-grade encryption for distributed deployments:
- End-to-end encryption (Curve25519 + XSalsa20 + Poly1305)
- Digital signatures (Ed25519)
- Multi-protocol support (AMQP, MQTT, STOMP)
- Automatic key rotation and forward secrecy

### Tool System
Equip agents with external capabilities:
```python
from praval.tools import tool

@tool(name="web_search", description="Search the web")
def search_web(query: str) -> str:
    return perform_search(query)

@agent("researcher", tools=[search_web])
def research_agent(spore):
    # Agent can now use web search
    results = search_web(spore.knowledge['query'])
```

---

## Configuration

### Environment Variables
```bash
# Required: At least one LLM API key
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
COHERE_API_KEY=your_cohere_key

# Framework settings
PRAVAL_DEFAULT_PROVIDER=openai
PRAVAL_DEFAULT_MODEL=gpt-4o-mini
PRAVAL_LOG_LEVEL=INFO
PRAVAL_MAX_THREADS=10

# Memory (optional)
QDRANT_URL=http://localhost:6333
PRAVAL_COLLECTION_NAME=praval_memories
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
    }
})
```

---

## Docker Deployment

### Development
```bash
docker-compose up -d
# Access Jupyter: http://localhost:8888
```

### Production (Secure)
```bash
docker-compose -f docker/docker-compose.secure.yml up -d
# Includes: RabbitMQ, MQTT, Qdrant, Redis with TLS
```

---

## Documentation

- **📘 [Complete Manual](docs/praval-manual.md)**: Comprehensive guide covering all features
- **🏗️ [Architecture](docs/architecture-diagram.md)**: System design and component overview
- **🧠 [Memory System](docs/memory-system.md)**: Multi-layered memory capabilities
- **📡 [Reef Communication](docs/reef-communication-specification.md)**: Spore protocol specification
- **🔒 [Secure Spores](docs/secure_spores_architecture.md)**: Enterprise security features
- **📊 [Observability](docs/observability/README.md)**: Tracing and monitoring guide
- **🔧 [Tool System](docs/tool-system-specification.md)**: External capability integration
- **🐳 [Deployment](docs/DEPLOYMENT.md)**: Production deployment guide

---

## Development

### Running Tests
```bash
# Full suite
pytest tests/ -v

# With coverage
pytest --cov=praval --cov-report=html

# Specific components
pytest tests/test_decorators.py -v
pytest tests/test_reef.py -v
pytest tests/test_memory.py -v
```

### Contributing
See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines on:
- Code style and standards
- Testing requirements
- Pull request process
- Version bumping conventions

---

## Roadmap

### ✅ Phase 1: Foundation (Complete)
Decorator API, Reef communication, multi-LLM support, self-organization

### ✅ Phase 2: Advanced Patterns (Complete)
Memory integration, semantic search, complex workflows, testing (99% coverage)

### 🚀 Phase 3: Enterprise Ready (Current - v0.7.x)
- ✓ Observability suite with OpenTelemetry
- ✓ Tool system for external capabilities
- ✓ Secure messaging with encryption
- 🚧 Streaming responses
- 🚧 Visual debugging tools

### 🎯 Phase 4: Advanced Intelligence (Planned)
Multi-modal agents, agent evolution, industry solutions

---

## Community

### Getting Help
- **🐛 [GitHub Issues](https://github.com/aiexplorations/praval/issues)**: Bug reports and feature requests
- **💬 [Discussions](https://github.com/aiexplorations/praval/discussions)**: Q&A and community support
- **📚 [Documentation](docs/)**: Comprehensive guides and tutorials
- **🎯 [Examples](examples/)**: Complete working applications

### Stay Updated
- **📦 [PyPI Releases](https://pypi.org/project/praval/)**: Latest stable versions
- **📝 [Changelog](CHANGELOG.md)**: Version history and release notes
- **🎆 [Releases](https://github.com/aiexplorations/praval/releases)**: Release announcements

---

## Philosophy

Praval is inspired by coral reefs - ecosystems where simple organisms create complex, thriving communities through natural collaboration. Similarly, Praval agents are:

- **Specialized**: Each excels at one thing
- **Autonomous**: Self-coordinating without central control
- **Collaborative**: Work together through natural communication
- **Emergent**: Complex intelligence from simple interactions

Read more: [Philosophy & Design Principles](praval.md)

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Quick Links

- 🚀 **[Get Started](#installation)** - Install and run your first agent
- 📘 **[Read the Manual](docs/praval-manual.md)** - Comprehensive documentation
- 🎯 **[See Examples](examples/)** - Real-world applications
- 🐛 **[Report Issues](https://github.com/aiexplorations/praval/issues)** - Bug reports
- 💬 **[Join Discussions](https://github.com/aiexplorations/praval/discussions)** - Community Q&A
- 📦 **[PyPI Package](https://pypi.org/project/praval/)** - Latest releases

---

<div align="center">

**Built with Praval?** [Share your work!](https://github.com/aiexplorations/praval/discussions)

*Simple agents. Powerful results.*

</div>
