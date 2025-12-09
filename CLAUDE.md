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
│   │   ├── reef.py              # Communication system (Spore protocol)
│   │   ├── registry.py          # Agent discovery
│   │   ├── secure_reef.py       # Encrypted communication
│   │   ├── transport.py         # RabbitMQ/AMQP transport
│   │   └── tool_registry.py     # Tool registration
│   ├── memory/                   # Memory system (ChromaDB)
│   ├── storage/                  # Storage providers (PostgreSQL, Redis, S3, Qdrant)
│   ├── observability/           # OpenTelemetry tracing
│   └── providers/               # LLM providers (OpenAI, Anthropic, Cohere)
├── examples/                     # Working examples
│   ├── simple_multi_agent.py    # Basic multi-agent pattern (START HERE)
│   ├── 001-011_*.py             # Numbered progressive examples
│   └── distributed_agents_with_rabbitmq.py
├── tests/                        # Test suite
├── docs/                         # Documentation
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
├── test_agent.py          # Agent class tests
├── test_decorators.py     # @agent decorator tests
├── test_reef.py           # Communication system tests
├── test_memory.py         # Memory system tests
├── test_tools.py          # Tool system tests
└── integration/           # Integration tests
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

### Release Steps
```bash
# 1. Ensure all tests pass
pytest tests/ -v --cov=praval --cov-fail-under=80

# 2. Update version in pyproject.toml and src/praval/__init__.py

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
- `examples/simple_multi_agent.py` - Reference example

## Related Repositories

- **praval-ai**: Website and hosted documentation (https://github.com/aiexplorations/praval-ai)
- **PyPI**: https://pypi.org/project/praval/
