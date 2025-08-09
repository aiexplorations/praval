# Contributing to Praval

Thank you for your interest in contributing to Praval! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Development Setup

1. **Clone and setup environment**:
```bash
git clone https://github.com/aiexplorations/praval.git
cd praval

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

2. **Install pre-commit hooks**:
```bash
pre-commit install
```

3. **Run tests to ensure everything works**:
```bash
pytest tests/ -v
```

## 📝 Commit Message Convention

Praval uses automated version bumping based on commit messages. Please follow this format:

### Version Bump Keywords

#### 🔴 Major Version (Breaking Changes - v0.x.0 → v1.0.0 or v1.0.0 → v2.0.0)
```
BREAKING CHANGE: Remove deprecated memory API
major: Redesign agent decorator interface
api change: Modify core reef communication protocol
```

#### 🟡 Minor Version (New Features - v0.5.0 → v0.6.0)
```
feat: Add streaming response capability
add: New tool integration system
enhance: Improve memory search performance
memory system: Add new episodic memory features
agent capability: Enable cross-agent knowledge sharing
```

#### 🟢 Patch Version (Bug Fixes - v0.5.0 → v0.5.1)
```
fix: Memory leak in agent cleanup
bug: Resolve reef channel subscription issue
docs: Update installation instructions
test: Add edge case coverage for decorators
refactor: Simplify memory manager initialization
```

### Examples
```bash
# These trigger minor version bumps:
git commit -m "feat: Add real-time agent communication streaming"
git commit -m "add: Knowledge base auto-indexing for PDF files"
git commit -m "enhance: Improve agent memory recall performance"

# These trigger patch version bumps:
git commit -m "fix: Agent memory persistence across sessions"
git commit -m "docs: Add memory system configuration examples"
git commit -m "test: Increase coverage for reef communication"

# These trigger major version bumps:
git commit -m "BREAKING CHANGE: Remove legacy agent registration API"
git commit -m "major: Redesign decorator interface for v1.0"
```

## 🧪 Testing Guidelines

### Running Tests
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/praval --cov-report=html

# Run specific test modules
pytest tests/test_memory_manager.py -v
pytest tests/test_decorators.py -v
```

### Test Coverage Expectations
- **New features**: Must have >90% test coverage
- **Bug fixes**: Must include regression tests
- **API changes**: Must update all relevant tests

### Writing Tests
- Place tests in the `tests/` directory
- Follow the naming convention: `test_<module_name>.py`
- Use descriptive test function names
- Include both positive and negative test cases

## 🏗️ Development Workflow

### 1. Create a Feature Branch
```bash
git checkout -b feat/streaming-responses
# or
git checkout -b fix/memory-leak-agent-cleanup
```

### 2. Make Changes
- Write code following existing patterns
- Add comprehensive tests
- Update documentation if needed
- Follow PEP 8 style guidelines

### 3. Test Your Changes
```bash
# Run tests
pytest tests/ -v

# Check formatting
black src/ tests/
isort src/ tests/

# Run examples to ensure they still work
python examples/001_single_agent_identity.py
```

### 4. Commit and Push
```bash
git add .
git commit -m "feat: Add streaming response capability to agents"
git push origin feat/streaming-responses
```

### 5. Create Pull Request
- Use GitHub's PR template
- Describe what changed and why
- Link any related issues
- Ensure CI passes

## 📦 Release Process

Releases are **fully automated** when you push to the main branch:

1. **Automatic Version Bumping**: Based on commit message keywords
2. **Git Tagging**: Automatically creates and pushes tags
3. **GitHub Releases**: Auto-creates releases with changelog
4. **Package Building**: Builds wheels and source distributions

### Manual Release (if needed)
```bash
# Install bump2version
pip install bump2version

# Bump version manually
bump2version patch  # or minor, major
```

## 🎯 Areas for Contribution

### High Priority
- **Streaming Responses**: Real-time token streaming from agents
- **Tool Integration**: External API and service connections
- **Visual Debugging**: Agent interaction visualization
- **Performance Optimization**: Caching and rate limiting

### Documentation
- **Example Improvements**: More real-world use cases
- **API Documentation**: Complete docstring coverage
- **Tutorial Content**: Step-by-step guides

### Testing
- **Integration Tests**: Multi-agent system scenarios
- **Performance Tests**: Memory usage and speed benchmarks
- **Edge Case Coverage**: Error conditions and failure modes

## 🔧 Code Style

### Python Style
- Follow **PEP 8**
- Use **Black** for formatting (line length: 88)
- Use **isort** for import sorting
- Type hints encouraged but not required

### Documentation Style
- Docstrings in **Google format**
- Clear, concise explanations
- Include usage examples where helpful

### Example Code Style
```python
@agent("example_agent", responds_to=["task_request"])
def example_agent(spore):
    """
    Example agent demonstrating best practices.
    
    Args:
        spore: The spore containing task information
        
    Returns:
        Dict containing task results
    """
    task_type = spore.knowledge.get("task_type")
    
    if not task_type:
        return {"error": "No task type specified"}
    
    result = process_task(task_type)
    
    broadcast({
        "type": "task_complete",
        "result": result,
        "agent": "example_agent"
    })
    
    return {"success": True, "result": result}
```

## 📞 Getting Help

- **Issues**: Create GitHub issues for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Examples**: Check the `examples/` directory for usage patterns
- **Documentation**: See `docs/` and `praval.md` for detailed guides

## 📄 License

By contributing to Praval, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Praval! Together we're building the future of multi-agent AI systems. 🚀