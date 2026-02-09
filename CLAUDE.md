# Praval - AI Multi-Agent Framework

**The Pythonic Multi-Agent AI Framework for building intelligent, collaborative agent systems**

> *Praval (प्रवाल) - Sanskrit for coral, representing how simple agents collaborate to create complex, intelligent ecosystems.*

## IMPORTANT: Always Use Virtual Environment

```bash
source venv/bin/activate  # Always run this first!
```

All pytest, pip, python commands must be run within the activated venv.

## Project Overview

- **Version**: 0.7.20
- **Python Support**: 3.9, 3.10, 3.11, 3.12
- **License**: MIT

## Repository Structure

```
praval/
├── src/praval/                    # Core framework code
│   ├── __init__.py               # Main API exports
│   ├── decorators.py             # @agent decorator implementation
│   ├── composition.py            # Agent orchestration (start_agents)
│   ├── tools.py                  # @tool decorator implementation
│   ├── core/                     # Core components
│   │   ├── agent.py             # Agent base class
│   │   ├── agent_runner.py      # Agent execution engine
│   │   ├── reef.py              # Communication system (Spore protocol)
│   │   ├── reef_backend.py      # Reef backend implementations
│   │   ├── registry.py          # Agent discovery
│   │   ├── secure_reef.py       # Encrypted reef communication
│   │   ├── secure_spore.py      # Encrypted spore handling
│   │   ├── storage.py           # Core storage utilities
│   │   ├── exceptions.py        # Framework exceptions
│   │   ├── transport.py         # RabbitMQ/AMQP transport
│   │   └── tool_registry.py     # Tool registration
│   ├── memory/                   # Memory system
│   │   ├── memory_manager.py    # Unified memory interface
│   │   ├── memory_types.py      # Memory type definitions
│   │   ├── short_term_memory.py # Working memory
│   │   ├── long_term_memory.py  # Persistent vector storage
│   │   ├── episodic_memory.py   # Conversation tracking
│   │   ├── semantic_memory.py   # Knowledge retrieval
│   │   └── embedded_store.py    # ChromaDB integration
│   ├── storage/                  # Storage providers
│   │   ├── providers/           # Provider implementations
│   │   │   ├── filesystem.py    # Local filesystem
│   │   │   ├── postgresql.py    # PostgreSQL
│   │   │   ├── redis_provider.py # Redis
│   │   │   ├── s3_provider.py   # AWS S3
│   │   │   └── qdrant_provider.py # Qdrant vector DB
│   │   ├── base_provider.py     # Provider base class
│   │   ├── data_manager.py      # Unified data access
│   │   ├── decorators.py        # Storage decorators
│   │   └── storage_registry.py  # Provider registry
│   ├── observability/           # Tracing & monitoring
│   │   ├── tracing/             # Span & context management
│   │   ├── instrumentation/     # Auto-instrumentation
│   │   ├── storage/             # SQLite trace storage
│   │   └── export/              # OTLP & console exporters
│   └── providers/               # LLM providers (OpenAI, Anthropic, Cohere)
├── examples/                     # Working examples
│   ├── simple_multi_agent.py    # Basic multi-agent pattern (START HERE)
│   ├── 001_single_agent_identity.py
│   ├── 002_agent_communication.py
│   ├── 003_specialist_collaboration.py
│   ├── 004_registry_discovery.py
│   ├── 005_memory_enabled_agents.py
│   ├── 006_resilient_agents.py
│   ├── 007_adaptive_agent_systems.py
│   ├── 008_self_organizing_networks.py
│   ├── 009_emergent_collective_intelligence.py
│   ├── 010_unified_storage_demo.py
│   ├── 011_secure_spore_demo.py
│   └── distributed_agents_with_rabbitmq.py
├── tests/                        # Test suite
├── docs/                         # Documentation
│   └── sphinx/                  # Sphinx documentation source
└── pyproject.toml               # Package configuration
```

## Core Patterns

### Pattern 1: Single Agent
```python
from praval import Agent

agent = Agent("assistant", system_message="You are a helpful assistant")
response = agent.chat("What is machine learning?")
print(response)
```

### Pattern 2: Multi-Agent with @agent decorator
```python
from praval import agent, chat, broadcast, start_agents

@agent("researcher", responds_to=["research_request"])
def researcher(spore):
    result = chat(f"Research: {spore.knowledge['topic']}")
    broadcast({"type": "research_complete", "findings": result})
    return {"status": "done"}

@agent("writer", responds_to=["research_complete"])
def writer(spore):
    article = chat(f"Write about: {spore.knowledge['findings']}")
    return {"article": article}

start_agents(researcher, writer,
    initial_data={"type": "research_request", "topic": "AI agents"})
```

### Key Concepts

- **`responds_to`**: Filters messages by `spore.knowledge["type"]`
- **`broadcast()`**: Sends to all agents on "main" channel (default)
- **`chat()`**: Calls LLM within agent context (only works inside @agent functions)
- **`start_agents()`**: Runs the multi-agent system

## Code Standards

### Formatting & Linting
- **Black**: Line length 88, target Python 3.9+
- **isort**: Black-compatible profile
- **flake8**: Standard linting
- **mypy**: Strict type checking enabled

### Type Hints
All functions must have comprehensive type hints:
```python
def process_data(items: List[str], config: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
    ...
```

### Testing Requirements
- Minimum 80% code coverage
- Use pytest with pytest-asyncio for async tests
- Mark tests: `@pytest.mark.unit`, `@pytest.mark.integration`

## Development Commands

```bash
source venv/bin/activate

# Install dev dependencies
pip install -e .[dev]

# Run tests
pytest tests/ -v

# Run with coverage (must be >80%)
pytest --cov=praval --cov-report=html --cov-fail-under=80

# Format code
black src tests
isort src tests

# Lint
flake8 src tests

# Type check
mypy src

# Run all checks before commit
black src tests && isort src tests && flake8 src tests && mypy src && pytest tests/ -v
```

## Testing

### Test Structure
```
tests/
├── test_agent.py              # Agent class tests
├── test_decorators.py         # @agent decorator tests
├── test_reef.py               # Communication system tests
├── test_memory_manager.py     # Memory manager tests
├── test_tool_system.py        # Tool system tests
├── test_composition.py        # Agent composition tests
├── test_secure_spore.py       # Secure messaging tests
├── test_transport.py          # AMQP transport tests
├── storage/                   # Storage provider tests
│   ├── test_base_provider.py
│   ├── test_data_manager.py
│   ├── test_filesystem_provider.py
│   ├── test_postgresql_provider.py
│   ├── test_redis_provider.py
│   ├── test_s3_provider.py
│   └── test_qdrant_provider.py
├── observability/             # Observability tests
│   ├── test_tracer.py
│   ├── test_span.py
│   ├── test_context.py
│   └── test_instrumentation.py
├── integration/               # Integration tests
│   └── test_rabbitmq_distributed_workflow.py
└── validation/                # Validation scripts
```

### Running Specific Tests
```bash
pytest tests/test_decorators.py -v          # Single file
pytest tests/ -k "test_agent"               # Pattern match
pytest tests/ -m unit                       # Only unit tests
pytest tests/ -m integration                # Only integration tests
```

## Release Process

### Version Bumping
Version is defined in two places - keep them in sync:
- `pyproject.toml` line 7: `version = "X.Y.Z"`
- `src/praval/__init__.py` line 90: `__version__ = "X.Y.Z"`
- `src/praval/__init__.py` docstring (update release notes)

### Quick Release (Recommended)
Use the Makefile release wizard:
```bash
source venv/bin/activate
make release
# Follow prompts to select: patch/minor/major
# Updates version, builds, and prepares for upload
```

### Manual Release Steps
```bash
# 1. Ensure all tests pass
pytest tests/ -v --cov=praval --cov-fail-under=80

# 2. Update version in pyproject.toml, src/praval/__init__.py, and docstring

# 3. Commit version bump
git add pyproject.toml src/praval/__init__.py
git commit -m "🔖 Bump version: X.Y.Z → X.Y.Z+1"

# 4. Create and push tag
git tag vX.Y.Z
git push origin main --tags

# 5. Build wheel
python -m build

# 6. Upload to PyPI (wheel only)
twine upload dist/praval-X.Y.Z-py3-none-any.whl
```

### Post-Release
After PyPI release, update the pravalagents.com website:
1. Update version displayed on the site
2. Deploy new documentation (see Documentation Build section)

### Version Semantics
- **Major (X)**: Breaking API changes
- **Minor (Y)**: New features, backward compatible
- **Patch (Z)**: Bug fixes, documentation updates

## Environment Variables

```bash
# Required: at least one LLM API key
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
COHERE_API_KEY=your_key

# Framework settings
PRAVAL_DEFAULT_PROVIDER=openai
PRAVAL_DEFAULT_MODEL=gpt-4o-mini
PRAVAL_LOG_LEVEL=INFO

# Memory system (optional)
QDRANT_URL=http://localhost:6333
```

## Optional Dependencies

Install specific features as needed:
```bash
pip install praval[memory]    # ChromaDB, sentence-transformers
pip install praval[secure]    # RabbitMQ, encryption
pip install praval[storage]   # PostgreSQL, Redis, S3, Qdrant
pip install praval[pdf]       # PDF knowledge base support
pip install praval[all]       # Everything
pip install praval[dev]       # Development tools
```

## Documentation Build

### Build Sphinx Docs
```bash
source venv/bin/activate

# Clean and build
make docs-clean
make docs-html

# Output location
ls docs/_build/html/
```

### Serve Docs Locally
```bash
make docs-serve
# Opens http://localhost:8000
```

### Deploy to praval-ai Website
After a release, update the praval-ai repo with new docs:
```bash
# 1. Build docs in praval repo
make docs-clean && make docs-html

# 2. Copy to praval-ai repo (replace X.Y.Z with version)
cp -r docs/_build/html /path/to/praval-ai/docs/vX.Y.Z
cp -r docs/_build/html /path/to/praval-ai/docs/latest

# 3. Update praval-ai/docs/versions.json with new version

# 4. Commit and push praval-ai
```

## Key Documentation

- `docs/quickstart.md` - Single vs multi-agent patterns
- `docs/memory-api-reference.md` - Memory API
- `docs/reef-communication-specification.md` - Spore protocol
- `docs/secure_spores_architecture.md` - Secure Spores Enterprise
- `docs/tool-system-specification.md` - Tool system (@tool decorator)
- `docs/DEPLOYMENT.md` - Docker deployment guide
- `docs/praval-complete-guide.md` - Comprehensive framework guide
- `examples/simple_multi_agent.py` - Reference example

## Related Repositories

- **Website**: https://pravalagents.com (documentation and demos)
- **praval-ai repo**: Website source (https://github.com/aiexplorations/praval-ai)
- **PyPI**: https://pypi.org/project/praval/
- **GitHub**: https://github.com/aiexplorations/praval
