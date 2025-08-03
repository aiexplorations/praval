# Praval

A pure Python framework for building and managing LLM-based agents with state management, prompt engineering, and behavioral evolution capabilities.

*Praval (प्रवाल) - Sanskrit for coral, representing the framework's ability to build complex, interconnected agent systems from simple components.*

## Overview

This framework provides a flexible and extensible architecture for creating intelligent agents that can:
- Connect to various LLM providers
- Manage conversational state and context
- Utilize base and system prompts effectively
- Evolve their behavior over time through learning mechanisms
- Solve a user-stated problem (supplied as part of an input to the agent) 

## Features

### Core Capabilities
- **LLM Integration**: Seamless connection to multiple LLM providers (OpenAI, Anthropic, Cohere, etc.)
- **State Management**: Persistent state tracking across conversations and sessions
- **Prompt Engineering**: Effective prompt templating, versioning and management system
- **Behavioral Evolution**: Adaptive learning mechanisms to improve agent performance
- **Pure Python**: Minimal dependencies for building the core functionality
- **Extensible Architecture**: Plugin system for custom components and behaviors
### Advanced Features
- **Tool Use & Function Calling**: Integration with external APIs and services with structured parameter validation
- **Memory Systems**: 
  - Short-term working memory
  - Long-term vector storage (Qdrant)
  - Episodic memory for interaction histories
  - Semantic memory with knowledge graphs
- **Multi-Agent Orchestration**: Coordinate multiple agents with different specializations
- **Reasoning & Planning**: Chain-of-thought, tree-of-thought, and ReAct patterns
- **Retrieval-Augmented Generation (RAG)**: Document processing and semantic search
- **Streaming Responses**: Real-time token streaming for better UX
- **Observability**: Comprehensive logging, tracing, and monitoring

### Safety & Reliability
- **Content Filtering**: Built-in safety rails for input/output
- **Hallucination Detection**: Validate agent outputs against known facts
- **Error Handling**: Robust retry mechanisms and graceful degradation
- **Rate Limiting**: Prevent API abuse and manage costs

## Installation

```bash
pip install -r requirements.txt
```
## Quick Start

```python
from praval import Agent, LLMProvider

# Initialize an agent
agent = Agent(
    name="MyAgent",
    llm_provider=LLMProvider.OPENAI,
    base_prompt="You are a helpful assistant specialized in Python programming."
)

# Have a conversation
response = agent.chat("How do I implement a singleton pattern in Python?")
print(response)

# Access agent state
state = agent.get_state()
print(f"Conversation history: {state.history}")
```

## Architecture

The framework is built around several core components:

### Agent
The main interface for interacting with LLMs. Handles:
- Message routing and conversation flow
- State persistence and recovery
- Prompt management and optimization
- Response processing and validation
- Tool execution and function calling
### State Manager
Manages agent state including:
- Conversation history with token optimization
- User preferences and personalization
- Learning data and performance metrics
- Context windows and memory pruning
- Session management and continuity

### Prompt Manager
Handles prompt engineering:
- Base prompt templates with version control
- System prompt injection and composition
- Dynamic prompt modification based on context
- Context-aware prompt building
- Prompt optimization and A/B testing
- Few-shot example management

### Memory System
Provides various memory capabilities:
- **Working Memory**: Current conversation context
- **Vector Store**: Long-term semantic memory using embeddings
- **Knowledge Graph**: Structured relationship storage
- **Episodic Buffer**: Recent interaction history
- **Cache Layer**: Response caching for efficiency

### Tool System
Enables external integrations:
- Structured tool definitions with JSON schemas
- Parameter validation and type checking
- Parallel tool execution
- Error handling and fallbacks
- Sandboxed execution environments
## Usage Examples

### Basic Agent Creation

```python
from praval import Agent

agent = Agent(
    name="CodeAssistant",
    base_prompt="You are an expert Python developer.",
    temperature=0.7
)
```

### Tool Integration

```python
from praval import Agent

agent = Agent("researcher")

@agent.tool
def get_weather(location: str) -> str:
    """Get current weather for a location"""
    return f"Weather in {location}: Sunny, 72°F"

response = agent.chat("What's the weather in New York?")
```

### State Management

```python
# Save state
agent.save_state("agent_state.json")

# Load state
agent = Agent.load_state("agent_state.json")```

## Configuration

Create a `config.yaml` file to configure the framework:

```yaml
# LLM Configuration
llm:
  default_provider: openai
  providers:
    openai:
      api_key: ${OPENAI_API_KEY}
      model: gpt-4
      temperature: 0.7

# State Management
state:
  persistence: true
  storage_path: ./agent_states
```

## Development

### Project Structure

```
praval/
├── __init__.py
├── core/           # Core agent implementation
├── llm/            # LLM provider integrations
├── memory/         # Memory management
├── tools/          # Tool system
├── prompts/        # Prompt management
└── utils/          # Utility functions
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=praval
```

## Roadmap

### Phase 1: Core Framework (Current)
- [x] Basic agent implementation
- [x] State management
- [x] Multiple LLM provider support
- [ ] Basic tool system
- [ ] Simple memory management
- [ ] Configuration system

### Phase 2: Advanced Features
- [ ] Vector memory integration
- [ ] Multi-agent orchestration
- [ ] Advanced reasoning patterns
- [ ] Streaming support

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions and support:
- Open an issue on GitHub
- Check the documentation in `/docs`
- See examples in `/examples`