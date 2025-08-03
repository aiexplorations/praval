# Praval Phase 1 - Application Specification

## Overview

Praval is a composable, user-friendly Python framework for building LLM-based agents. Phase 1 establishes the core foundation with minimal complexity while ensuring extensibility for future phases.

## Design Principles

1. **Simplicity First**: An agent should be functional in 3-5 lines of code
2. **Composability**: Components should work together seamlessly
3. **No Magic**: Explicit is better than implicit, clear abstractions
4. **Test-Driven**: Every feature must have comprehensive tests
5. **Real Implementation**: No mocks, stubs, or placeholders in production code

## Core Components for Phase 1

### 1. Agent (core/agent.py)
```python
# Minimal usage example
from praval import Agent

agent = Agent("assistant")
response = agent.chat("Hello, how are you?")
```

**Key Features:**
- Simple initialization with sensible defaults
- Support for OpenAI, Anthropic, and Cohere providers
- Automatic provider detection from environment variables
- Stateful conversations with history management
- Configurable via constructor or config file