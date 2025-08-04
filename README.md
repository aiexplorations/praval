<div align="center">
  <img src="logo.png" alt="Praval Logo" width="200"/>
  
  # Praval
  
  A pure Python framework for building and managing LLM-based agents with state management, prompt engineering, and behavioral evolution capabilities.
  
  *Praval (प्रवाल) - Sanskrit for coral, representing the framework's ability to build complex, interconnected agent systems from simple components.*
</div>

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

### Registry System
- **Agent Registry**: Global registration and discovery of agents across your application  
- **Tool Registry**: Automatic registration and discovery of agent tools with metadata
- **Dynamic Discovery**: Find agents and tools by name, type, or capability
- **Tool Validation**: Automatic type checking and parameter validation for tools
- **Namespaced Tools**: Tools are scoped by agent to prevent naming conflicts

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
from praval import Agent, register_agent, get_registry

# Create and register an agent
domain_expert = Agent(
    "domain_expert",
    system_message="You are a domain expert who understands concepts deeply."
)
register_agent(domain_expert)

# Use the agent
response = domain_expert.chat("Explain machine learning concepts")
print(response)

# Access registered agents
registry = get_registry()
agents = registry.list_agents()
print(f"Available agents: {agents}")
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

### Multi-Agent Knowledge Graph Mining

```python
from praval import Agent, register_agent, get_registry

# Set up specialized agents
domain_expert = Agent("domain_expert", system_message="You are a domain expert...")
relationship_analyst = Agent("relationship_analyst", system_message="You analyze relationships...")
graph_enricher = Agent("graph_enricher", system_message="You find hidden relationships...")

# Register agents
for agent in [domain_expert, relationship_analyst, graph_enricher]:
    register_agent(agent)

# Use agents collaboratively for knowledge mining
from examples.knowledge_graph_miner import mine_knowledge_graph
kg_data = mine_knowledge_graph("artificial intelligence", max_nodes=20)
```

### Agent Registry and Collaboration

```python
from praval import Agent, register_agent, get_registry

# Create specialized agents
code_agent = Agent("coder", system_message="You are an expert programmer.")
review_agent = Agent("reviewer", system_message="You review code for quality.")

# Register agents
register_agent(code_agent)
register_agent(review_agent)

# Agents can work together
code = get_registry().get_agent("coder").chat("Write a Python function to sort a list")
review = get_registry().get_agent("reviewer").chat(f"Review this code: {code}")
```

### Registry Features and Tool Management

```python
from praval import Agent, register_agent, get_registry

# Create agent with tools
calculator = Agent("calculator", system_message="You are a math assistant.")

@calculator.tool
def add(x: int, y: int) -> int:
    """Add two numbers together."""
    return x + y

@calculator.tool  
def multiply(x: float, y: float) -> float:
    """Multiply two numbers."""
    return x * y

# Register the agent (automatically registers tools too)
register_agent(calculator)

# Access registry information
registry = get_registry()

# List all agents
print("Available agents:", registry.list_agents())
# Output: ['calculator']

# List all tools
print("Available tools:", registry.list_tools())  
# Output: ['calculator.add', 'calculator.multiply']

# Get specific agent
calc_agent = registry.get_agent("calculator")

# Get tools for a specific agent
calc_tools = registry.get_tools_by_agent("calculator")
print("Calculator tools:", calc_tools.keys())

# Get specific tool details
add_tool = registry.get_tool("calculator.add")
print("Add tool:", add_tool["description"])
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

### Phase 1: Core Framework ✅
- [x] Basic agent implementation
- [x] Agent registry and discovery
- [x] Multiple LLM provider support (OpenAI, Anthropic, Cohere)
- [x] Multi-agent collaboration patterns
- [x] Knowledge graph mining example
- [x] Enhanced relationship discovery

### Phase 2: Advanced Features (In Progress)
- [x] Multi-agent orchestration
- [x] Advanced reasoning patterns (via specialized agents)
- [ ] Vector memory integration
- [ ] Streaming support
- [ ] Tool system integration
- [ ] Configuration system

### Phase 3: Production Features
- [ ] Performance monitoring and metrics
- [ ] Error handling and retry mechanisms
- [ ] Rate limiting and cost management
- [ ] Security and content filtering
- [ ] Deployment and scaling patterns

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Examples

Explore the `/examples` directory for complete working examples:

- **Knowledge Graph Miner** (`examples/knowledge_graph_miner.py`): Multi-agent system for building knowledge graphs from seed concepts with relationship enrichment
- **RAG Chatbot** (`examples/rag_chatbot.py`): Retrieval-augmented generation chatbot example
- **Target API Examples** (`examples/target_api_examples.py`): Demonstrates the desired API patterns

## Support

For questions and support:
- Open an issue on GitHub
- Check the documentation in `/docs`
- See examples in `/examples`
- Read the design philosophy in `praval.md`