---
title: "Praval v0.6.1: The Complete Guide to Multi-Agent AI Systems"
author: 
  - "Rajesh Sampathkumar (@aiexplorations)"
  - "Claude Code"
date: "August 2025"
version: "0.6.1"
---

<div style="text-align: center; page-break-after: always;">

![Praval Logo](logo.png)

# Praval: The Complete Guide to Multi-Agent AI Systems

**The Pythonic Multi-Agent AI Framework for building intelligent, collaborative systems**

*Praval (प्रवाल) - Sanskrit for coral, representing the framework's ability to build complex, interconnected agent systems from simple components.*

---

### Authors

**Rajesh Sampathkumar** ([@aiexplorations](https://github.com/aiexplorations))  
*Framework Creator & Lead Developer*

**Claude Code**  
*AI Assistant & Documentation Collaborator*

---

**Version:** 1.3  
**Last Updated:** August 2025  
**Framework Version:** 0.6.1 (with Unified Data Storage & Retrieval System)

</div>

# About This Guide

*Praval (प्रवाल) - Sanskrit for coral, representing the framework's ability to build complex, interconnected agent systems from simple components.*

This comprehensive guide serves as both philosophical manifesto and practical manual for building sophisticated multi-agent AI systems using the Praval framework. From foundational principles to advanced collective intelligence patterns, it provides everything needed to master the art of collaborative AI development.

## Table of Contents

**PART I: PHILOSOPHY & DESIGN**
- [Core Philosophy](#core-philosophy)
- [Design Principles](#design-principles) 
- [Patterns and Anti-Patterns](#patterns-and-anti-patterns)

**PART II: GETTING STARTED**
- [Your First Agent](#your-first-agent)
- [Basic Multi-Agent Communication](#basic-multi-agent-communication)

**PART III: CORE CONCEPTS**
- [The Decorator API](#the-decorator-api)
- [Reef Communication System](#reef-communication-system)

**PART IV: PROGRESSIVE LEARNING**
- [Learning Praval Through Practice](#learning-praval-through-practice)
- [The Three-Stage Learning Path](#the-three-stage-learning-path)
- [Running the Learning Journey](#running-the-learning-journey)

**PART V: VERSION 0.6.0 NEW FEATURES**
- [Comprehensive Memory System](#comprehensive-memory-system)
- [Production-Ready Testing](#production-ready-testing)
- [Enhanced Agent Capabilities](#enhanced-agent-capabilities)
- [Multi-Agent Communication Bug Fix](#multi-agent-communication-bug-fix)

**PART VI: UNIFIED DATA STORAGE & RETRIEVAL SYSTEM** *(v0.6.1)*
- [Storage Architecture Overview](#storage-architecture-overview)
- [Storage Provider Framework](#storage-provider-framework)
- [Built-in Storage Providers](#built-in-storage-providers)
- [Storage Decorators for Agents](#storage-decorators-for-agents)
- [Data References in Spore Communication](#data-references-in-spore-communication)
- [Memory-Storage Integration](#memory-storage-integration)
- [Production Examples](#production-examples)

**PART VII: SECURE SPORES ENTERPRISE EDITION**
- [Enterprise-Grade Security](#enterprise-grade-security)
- [Distributed Messaging Architecture](#distributed-messaging-architecture)
- [Multi-Protocol Transport Layer](#multi-protocol-transport-layer)
- [Docker Deployment Infrastructure](#docker-deployment-infrastructure)

**PART VIII: COGNITIVE MEMORY ARCHITECTURE**
- [The Foundation of Persistent Intelligence](#the-foundation-of-persistent-intelligence)
- [Theoretical Foundation](#theoretical-foundation)

**PART IX: ADVANCED TOPICS**
- [Configuration and Deployment](#configuration-and-deployment)
- [Best Practices](#best-practices)

---

# PART I: PHILOSOPHY & DESIGN

## Introduction

Just as coral reefs are built from countless simple organisms working together to create complex, thriving ecosystems, Praval embodies a philosophy where simple, specialized agents collaborate to solve complex problems. This document serves as both philosophical guide and practical manual for building multi-agent AI systems using the Praval framework.

## Introduction

Just as coral reefs are built from countless simple organisms working together to create complex, thriving ecosystems, Praval embodies a philosophy where simple, specialized agents collaborate to solve complex problems. This document outlines the core principles and philosophy behind agentic AI application design using the Praval framework.

## Core Philosophy

### 1. The Principle of Composable Simplicity

**"Simple agents, powerful results"**

Praval's foundational principle rests on a counter-intuitive insight: **intelligence emerges from simplicity, not complexity**. Traditional AI systems attempt to create comprehensive, monolithic agents that handle multiple concerns simultaneously. This approach leads to:

- **Cognitive Overload**: Single agents trying to master multiple domains poorly
- **Maintenance Nightmares**: Changes in one area breaking unrelated functionality  
- **Limited Adaptability**: Rigid systems that can't evolve or learn new capabilities

Praval inverts this paradigm through **composable simplicity**:

- **Single Responsibility Principle**: Each agent excels at one specific type of thinking or action
- **Clean Interfaces**: Agents communicate through well-defined, semantic message protocols
- **Emergent Intelligence**: Complex reasoning emerges from the orchestrated interaction of simple specialists

```python
# Instead of one complex agent
complex_agent = Agent(
    "do_everything", 
    system_message="You are an expert at everything..."
)

# Praval encourages specialized agents
domain_expert = Agent(
    "domain_expert", 
    system_message="You understand concepts deeply"
)
relationship_analyst = Agent(
    "relationship_analyst", 
    system_message="You analyze connections"
)
graph_enricher = Agent(
    "graph_enricher", 
    system_message="You find hidden relationships"
)
```

### 2. The Specialist-Collaboration Paradigm

**"The whole is greater than the sum of its parts"**

This principle draws from the biological concept of **specialized symbiosis**. In nature, complex ecosystems thrive not because individual organisms are generalists, but because specialists collaborate effectively. Praval applies this to AI systems:

**The Specialist Advantage:**
- **Deep Competency**: Focused agents develop superior performance in their domain
- **Cognitive Load Management**: Each agent manages only the complexity it's designed for
- **Clear Accountability**: System behavior is traceable to specific agent responsibilities

**The Collaboration Dynamic:**
- **Complementary Capabilities**: Different types of intelligence (analytical, creative, evaluative) work together
- **Dynamic Load Balancing**: Agents naturally distribute work based on their specializations
- **Fault Isolation**: Failures are contained within specific competency boundaries

**The Emergence Effect:**
- **Collective Intelligence**: The system exhibits intelligence beyond any individual component
- **Adaptive Behavior**: Agent networks can reorganize to handle new challenges
- **Scaling Intelligence**: Adding new specialists expands system capabilities non-linearly

### 3. Identity-Driven Agent Architecture

**"Tell agents what to be, not what to do"**

This principle represents a fundamental shift from **imperative programming** to **declarative intelligence**. Instead of scripting agent behavior through procedural instructions, Praval agents are defined by their **cognitive identity**:

**The Problem with Procedural Agents:**
- **Brittle Behavior**: Step-by-step instructions fail when conditions change
- **Limited Generalization**: Agents can't handle scenarios outside their programmed responses
- **Maintenance Overhead**: Every new situation requires new procedural code

**The Identity-Based Approach:**
- **Behavioral Consistency**: Agents act according to their defined nature and expertise
- **Contextual Adaptation**: Identity-driven agents can handle novel situations within their domain
- **Natural Language Interface**: Agent capabilities are defined in human-understandable terms

```python
# Declarative: Define what the agent IS
domain_expert = Agent(
    "domain_expert", 
    system_message="""
    You are a domain expert who understands concepts deeply and can 
    identify the most relevant related concepts that would be valuable 
    in a knowledge graph.
    """
)

# Not procedural: Define what the agent DOES
# agent.add_step("analyze_input")
# agent.add_step("find_concepts") 
# agent.add_step("format_output")
```

This approach leads to:
- **More Natural Behavior**: Agents act according to their identity
- **Better Adaptability**: Agents can handle unexpected situations within their domain
- **Easier Reasoning**: Agent behavior is more predictable and explainable

### 4. Emergence Through Interaction

**"Intelligence emerges from the network, not the nodes"**

The most powerful aspect of Praval is how intelligence emerges from agent interactions:

- **Collective Intelligence**: The system becomes smarter than any individual agent
- **Dynamic Adaptation**: Agent networks can adapt to new challenges
- **Knowledge Synthesis**: Different perspectives combine to create deeper understanding

Consider a document analysis system:
- Content Extractor specializes in parsing different formats
- Semantic Analyzer understands meaning and context  
- Relationship Detector finds connections between concepts
- Together they create understanding beyond what any single component could achieve

### 5. Registry-Based Orchestration

**"Agents find each other, not the other way around"**

Praval uses a registry pattern that promotes loose coupling and dynamic composition:

```python
# Agents register themselves
register_agent(domain_expert)
register_agent(relationship_analyst)

# Other agents can discover and use them
registry = get_registry()
expert = registry.get_agent("domain_expert")
analyst = registry.get_agent("relationship_analyst")
```

Benefits:
- **Discoverability**: Agents can find and use other agents
- **Modularity**: Easy to add, remove, or replace agents
- **Testability**: Individual agents can be tested in isolation
- **Scalability**: New capabilities can be added without changing existing code

## Design Principles

### 1. Autonomous Agency

**Agents as Independent Cognitive Units**

True autonomy means agents possess **agency** - the capacity for independent action and decision-making within their domain:

**Cognitive Autonomy:**
- **Internal State Management**: Agents maintain their own context and working memory
- **Decision Authority**: Agents can choose how to respond based on their expertise
- **Goal-Oriented Behavior**: Agents pursue objectives within their scope of responsibility

**Operational Independence:**
- **Self-Sufficiency**: Agents function without requiring external orchestration
- **Error Recovery**: Agents handle their own failure modes and edge cases
- **Resource Management**: Agents manage their own computational and memory resources

**Boundary Clarity:**
- **Domain Expertise**: Agents know what they do and don't handle
- **Interface Contracts**: Agents expose clear, stable communication interfaces
- **Responsibility Scope**: Agents have well-defined areas of accountability

### 2. Compositional Architecture

**Building Intelligence Through Combination**

Composability enables the creation of complex systems from simple, reusable components:

**Interface Standardization:**
- **Protocol Consistency**: All agents communicate through the same message-passing protocol
- **Semantic Compatibility**: Agents share common understanding of message meanings
- **Version Tolerance**: Agents can work with different versions of other agents

**Substitutability:**
- **Role-Based Interchangeability**: Agents with similar roles can replace each other
- **Performance Scaling**: Better agents can be swapped in without system changes
- **A/B Testing**: Different agent implementations can be compared in live systems

**Hierarchical Assembly:**
- **Agent Aggregation**: Multiple agents can be composed into higher-level agents
- **Recursive Composition**: Composite agents can themselves be composed
- **Emergent Specialization**: New specialist roles emerge from agent combinations

### 3. Evolutionary System Design

**Systems That Adapt and Improve**

Evolutionary design enables continuous system improvement without rewriting:

**Adaptation Mechanisms:**
- **Performance Feedback**: Agents receive feedback on their effectiveness
- **Behavioral Adjustment**: Agents can modify their approaches based on outcomes
- **Role Evolution**: Agent responsibilities can expand or specialize over time

**Emergence Patterns:**
- **Spontaneous Organization**: Agents naturally form effective collaboration patterns
- **Capability Discovery**: New system capabilities emerge from agent interactions
- **Problem-Solution Co-evolution**: System structure adapts to the problems it solves

**Learning Integration:**
- **Experience Accumulation**: Agents build knowledge from repeated interactions
- **Pattern Recognition**: Systems identify and leverage successful collaboration patterns
- **Meta-Learning**: Systems learn how to learn more effectively

### 4. Transparent Cognition

**Understandable and Debuggable Intelligence**

Transparency ensures that agent systems remain comprehensible and maintainable:

**Behavioral Observability:**
- **Communication Visibility**: All agent interactions are observable and loggable
- **Decision Traceability**: Agent choices can be traced back to their reasoning
- **Performance Metrics**: Agent effectiveness is measurable and comparable

**Explainable Intelligence:**
- **Reasoning Exposition**: Agents can explain their decision-making process
- **Confidence Indicators**: Agents express uncertainty about their conclusions
- **Alternative Analysis**: Agents can discuss options they didn't choose

**Predictable Patterns:**
- **Consistent Personality**: Agents behave according to their defined characteristics
- **Reliable Interfaces**: Agent communication patterns remain stable over time
- **Bounded Behavior**: Agents operate within predictable parameters

## Patterns and Anti-Patterns

### ✅ Praval Patterns

**The Specialist Pattern**
```python
# Each agent has a clear, focused specialty
validator = Agent(
    "validator", 
    system_message="You validate data quality"
)
enricher = Agent(
    "enricher", 
    system_message="You enhance data with additional context"
)
```

**The Collaboration Pattern**
```python
# Agents work together naturally
concepts = domain_expert.chat("Find concepts related to AI")
relationships = relationship_analyst.chat(
    f"Analyze relationships in: {concepts}"
)
enriched = graph_enricher.chat(
    f"Find hidden connections in: {relationships}"
)
```

**The Registry Pattern**
```python
# Agents register and discover each other
register_agent(specialist_agent)
specialist = get_registry().get_agent("specialist")
```

### ❌ Anti-Patterns to Avoid

**The God Agent**
```python
# DON'T: One agent that tries to do everything
super_agent = Agent(
    "everything", 
    system_message="You can do anything perfectly"
)
```

**Tight Coupling**
```python
# DON'T: Agents that depend on specific implementations
class AgentA:
    def __init__(self, agent_b_instance):
        self.agent_b = agent_b_instance  # Tight coupling
```

**Procedural Thinking**
```python
# DON'T: Step-by-step programming instead of identity-based design
agent.add_rule("if input contains X, do Y")
agent.add_rule("if condition Z, perform action W")
```

## Architectural Patterns

### The Specialist Constellation Pattern

Rather than building monolithic systems, Praval encourages creating constellations of specialist agents:

```python
# Each agent focuses on one aspect of intelligence
perception_agent = Agent("perceiver", system_message="You extract and interpret data")
reasoning_agent = Agent("reasoner", system_message="You analyze and draw conclusions") 
memory_agent = Agent("rememberer", system_message="You store and recall information")
action_agent = Agent("actor", system_message="You plan and execute responses")
```

### The Collaborative Intelligence Pattern

Intelligence emerges from the interaction between specialists:

```python
# Agents work together through natural communication
@agent("analyst")
def analytical_thinking(spore):
    data = spore.knowledge.get("problem")
    analysis = chat(f"Break down this problem: {data}")
    broadcast({"type": "analysis_ready", "breakdown": analysis})

@agent("synthesizer", responds_to=["analysis_ready"])
def creative_synthesis(spore):
    breakdown = spore.knowledge.get("breakdown")
    synthesis = chat(f"Generate creative solutions from: {breakdown}")
    return {"solutions": synthesis}
```

### The Adaptive System Pattern

Systems that learn and evolve through agent interactions:

```python
# Agents can modify system behavior based on outcomes
@agent("performance_monitor")
def monitor_system(spore):
    metrics = spore.knowledge.get("performance_data")
    if metrics["efficiency"] < threshold:
        broadcast({"type": "optimization_needed", "metrics": metrics})

@agent("system_optimizer", responds_to=["optimization_needed"])
def optimize_system(spore):
    # Agents can spawn new specialists or modify existing ones
    create_specialized_agent_for_bottleneck(spore.knowledge["metrics"])
```

## Benefits of the Praval Approach

### 1. **Maintainability**
- Small, focused agents are easier to understand and modify
- Changes to one agent don't break others
- Clear separation of concerns

### 2. **Testability**
- Individual agents can be tested in isolation
- Agent interactions can be validated separately
- Behavior is more predictable and debuggable

### 3. **Scalability**
- New capabilities can be added by creating new agents
- Existing agents can be improved without affecting others
- System complexity grows linearly, not exponentially

### 4. **Robustness**
- Failure of one agent doesn't crash the entire system
- Graceful degradation when agents are unavailable
- Multiple agents can provide redundancy

### 5. **Innovation**
- Easy to experiment with new agent types
- Rapid prototyping of new capabilities
- Natural evolution of system capabilities

## Conclusion

Praval represents a fundamental shift in how we think about AI application design. Instead of building monolithic systems, we create ecosystems of specialized agents that collaborate to solve complex problems.

Like a coral reef, a Praval system is:
- **Diverse**: Many different types of agents with specialized roles
- **Collaborative**: Agents work together to create something greater than themselves
- **Adaptive**: The system evolves and improves over time
- **Resilient**: Robust to individual component failures
- **Beautiful**: Elegant solutions emerge from simple interactions

By embracing simplicity, specialization, and emergence, Praval enables us to build AI systems that are not just powerful, but also understandable, maintainable, and continuously improving.

*"In simplicity lies the ultimate sophistication."* - Leonardo da Vinci

This is the philosophy of Praval: simple agents, working together, creating intelligence that emerges from their collaboration rather than their individual complexity.

---

# PART II: GETTING STARTED

## Installation & Setup

### Quick Installation

```bash
# Clone the repository
git clone https://github.com/your-org/praval.git
cd praval

# Install dependencies
pip install -r requirements.txt

# Or install in development mode
pip install -e .
```

### Environment Setup

Create a `.env` file with your API keys:

```bash
# Required: At least one LLM provider
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here  # Optional
COHERE_API_KEY=your_cohere_key_here        # Optional

# Optional: Framework configuration
PRAVAL_DEFAULT_PROVIDER=openai
PRAVAL_DEFAULT_MODEL=gpt-4-turbo
PRAVAL_LOG_LEVEL=INFO

# Optional: Memory system (requires Docker)
QDRANT_URL=http://localhost:6333
PRAVAL_COLLECTION_NAME=praval_memories
```

### Docker Setup (Recommended)

For full functionality including the memory system:

```bash
# Start Qdrant and other services
docker-compose up -d

# Verify services are running
docker-compose ps

# Run examples
docker-compose exec praval-app python examples/pythonic_knowledge_graph.py
```

### Verify Installation

```python
# test_installation.py
from praval import Agent, chat

# Test basic functionality
agent = Agent("test_agent", system_message="You are helpful.")
response = agent.chat("Hello!")
print(f"Agent says: {response}")

# Test decorator API
from praval import agent as agent_decorator

@agent_decorator("greeter")
def greet(spore):
    name = spore.knowledge.get("name", "friend")
    return f"Hello {name}! Welcome to Praval."

print("✅ Installation successful!")
```

## Your First Agent

Let's create your first Praval agent using the decorator API:

### Hello World Agent

```python
from praval import agent, chat, start_agents

@agent("greeter", responds_to=["greeting"])
def hello_agent(spore):
    """A simple agent that greets users."""
    name = spore.knowledge.get("name", "friend")
    response = chat(f"Create a friendly greeting for someone named {name}")
    return {"greeting": response}

# Start the agent with initial data
start_agents(
    hello_agent,
    initial_data={"type": "greeting", "name": "Alice"}
)
```

### Understanding the Agent Decorator

The `@agent()` decorator transforms a simple Python function into an intelligent agent:

```python
@agent(
    name="agent_name",           # Unique identifier
    responds_to=["message_type"], # Types of messages to handle
    channel="optional_channel"   # Communication channel (optional)
)
def agent_function(spore):
    """
    The agent function receives a 'spore' containing:
    - spore.knowledge: Dictionary with message data
    - spore.id: Unique message identifier
    - spore.from_agent: Who sent the message
    - spore.channel: Which channel it came from
    """
    # Process the spore data
    # Use chat() for LLM interactions
    # Return data or use broadcast() for communication
    pass
```

### Simple Chat Agent

```python
from praval import agent, chat, start_agents

@agent("assistant")
def chat_agent(spore):
    """A conversational assistant agent."""
    user_message = spore.knowledge.get("message", "")
    
    if not user_message:
        return {"response": "Please provide a message to respond to."}
    
    # Use the chat function to interact with LLM
    response = chat(f"""
    You are a helpful assistant. Respond to this user message:
    
    User: {user_message}
    
    Provide a helpful and friendly response.
    """)
    
    return {"response": response}

# Interactive loop
while True:
    user_input = input("You: ")
    if user_input.lower() in ['quit', 'exit']:
        break
    
    # Start agent with user input
    result = start_agents(
        chat_agent,
        initial_data={"message": user_input}
    )
    
    if result and result.get("response"):
        print(f"Assistant: {result['response']}")
```

## Basic Multi-Agent Communication

Agents become powerful when they work together. Here's a simple two-agent system:

### Question-Answer System

```python
from praval import agent, chat, broadcast, start_agents

@agent("questioner", responds_to=["start_conversation"])
def ask_questions(spore):
    """Agent that generates questions about a topic."""
    topic = spore.knowledge.get("topic", "artificial intelligence")
    
    question = chat(f"Ask an interesting question about {topic}")
    
    print(f"🤔 Questioner: {question}")
    
    # Broadcast the question to other agents
    broadcast({
        "type": "question_asked",
        "question": question,
        "topic": topic
    })
    
    return {"question": question}

@agent("answerer", responds_to=["question_asked"])
def provide_answers(spore):
    """Agent that answers questions with expertise."""
    question = spore.knowledge.get("question", "")
    topic = spore.knowledge.get("topic", "")
    
    if not question:
        return
    
    answer = chat(f"""
    You are an expert on {topic}. Answer this question thoroughly:
    
    Question: {question}
    
    Provide a detailed, accurate answer.
    """)
    
    print(f"🧠 Answerer: {answer}")
    
    # Broadcast the answer
    broadcast({
        "type": "answer_provided",
        "question": question,
        "answer": answer,
        "topic": topic
    })
    
    return {"answer": answer}

# Start both agents
start_agents(
    ask_questions, provide_answers,
    initial_data={"type": "start_conversation", "topic": "machine learning"}
)
```

### Communication Patterns

**1. Direct Response Pattern**
```python
@agent("processor", responds_to=["process_data"])
def process_data(spore):
    # Process and return result directly
    result = do_processing(spore.knowledge)
    return {"result": result}
```

**2. Broadcast Pattern**
```python
@agent("detector", responds_to=["input_data"])
def detect_patterns(spore):
    patterns = analyze(spore.knowledge)
    
    # Broadcast to all listening agents
    broadcast({
        "type": "patterns_found",
        "patterns": patterns
    })
```

**3. Pipeline Pattern**
```python
# Agent A processes data and sends to Agent B
@agent("stage_one", responds_to=["raw_data"])
def process_stage_one(spore):
    processed = transform(spore.knowledge)
    broadcast({
        "type": "stage_one_complete",
        "data": processed
    })

@agent("stage_two", responds_to=["stage_one_complete"]) 
def process_stage_two(spore):
    final_result = finalize(spore.knowledge["data"])
    return {"final": final_result}
```

---

# PART III: CORE CONCEPTS

## The Decorator API

The decorator API is Praval's signature feature, transforming ordinary Python functions into intelligent agents with just a single decorator.

### Basic Decorator Usage

```python
from praval import agent, chat

@agent("agent_name")
def my_agent(spore):
    """Transform any function into an intelligent agent."""
    # Access message data
    data = spore.knowledge
    
    # Use LLM capabilities
    response = chat("Process this data intelligently")
    
    # Return results
    return {"result": response}
```

### Decorator Parameters

```python
@agent(
    name="unique_agent_name",           # Required: unique identifier
    responds_to=["message_type1", "message_type2"],  # Message types to handle
    channel="channel_name",             # Optional: specific channel
    auto_broadcast=True,                # Auto-broadcast return values
    concurrent=True                     # Allow concurrent execution
)
def advanced_agent(spore):
    pass
```

### Message Filtering

Agents only respond to messages they're configured to handle:

```python
@agent("specialist", responds_to=["analyze_data"])
def data_specialist(spore):
    """Only responds to 'analyze_data' message types."""
    if spore.knowledge.get("type") == "analyze_data":
        # This agent will only process this specific message type
        return analyze(spore.knowledge)

@agent("generalist")  # No responds_to = handles all messages
def general_agent(spore):
    """Responds to any message type."""
    return handle_any_message(spore.knowledge)
```

### Agent States and Context

```python
# Stateful agent with shared context
context = {"processed_count": 0, "results": []}

@agent("stateful_processor", responds_to=["process_item"])
def stateful_agent(spore):
    """Agent that maintains state across invocations."""
    item = spore.knowledge.get("item")
    
    # Process item
    result = process(item)
    
    # Update shared state
    context["processed_count"] += 1
    context["results"].append(result)
    
    print(f"Processed {context['processed_count']} items so far")
    
    return {"result": result, "total_processed": context["processed_count"]}
```

## Reef Communication System

The Reef is Praval's communication backbone, enabling knowledge-first messaging between agents through structured "spores."

### Understanding Spores

Spores are JSON messages that carry structured knowledge between agents:

```python
# Example spore structure
spore = {
    "id": "unique_message_id",
    "type": "message_type",
    "knowledge": {
        "data": "actual_content",
        "metadata": {"priority": "high"},
        "context": {"session_id": "123"}
    },
    "from_agent": "sender_name",
    "to_agent": "receiver_name",  # Optional for broadcasts
    "channel": "channel_name",
    "timestamp": "2024-01-01T10:00:00Z"
}
```

### Communication Functions

**1. Direct Chat with LLMs**
```python
from praval import chat, achat

# Synchronous chat
response = chat("Explain quantum computing simply")

# Asynchronous chat
response = await achat("Process this complex analysis")

# Chat with specific model/provider
response = chat("Analyze data", model="gpt-4-turbo", provider="openai")
```

**2. Broadcasting Messages**
```python
from praval import broadcast

# Broadcast to all agents
broadcast({
    "type": "important_update",
    "message": "System maintenance in 10 minutes",
    "priority": "high"
})

# Broadcast to specific channel
broadcast({
    "type": "analysis_result",
    "data": results
}, channel="analytics")
```

**3. Agent-to-Agent Communication**
```python
@agent("sender")
def send_message(spore):
    # Send message to specific agent
    broadcast({
        "type": "direct_message",
        "content": "Hello specific agent",
        "target_agent": "receiver"
    })

@agent("receiver", responds_to=["direct_message"])
def receive_message(spore):
    if spore.knowledge.get("target_agent") == "receiver":
        content = spore.knowledge.get("content")
        print(f"Received: {content}")
```

### Channels and Message Routing

```python
# Agents can subscribe to specific channels
@agent("news_analyzer", channel="news_feed")
def analyze_news(spore):
    """Only receives messages on the news_feed channel."""
    pass

@agent("market_analyzer", channel="market_data")  
def analyze_market(spore):
    """Only receives messages on the market_data channel."""
    pass

# Start agents and broadcast to specific channels
start_agents(analyze_news, analyze_market)

# This only goes to news_analyzer
broadcast({"type": "breaking_news", "headline": "..."}, channel="news_feed")

# This only goes to market_analyzer  
broadcast({"type": "price_update", "symbol": "AAPL", "price": 150}, channel="market_data")
```

## Agent Orchestration

### Starting Agents

**Basic Startup**
```python
from praval import start_agents

# Start single agent
start_agents(my_agent)

# Start multiple agents
start_agents(agent1, agent2, agent3)

# Start with initial data
start_agents(
    processor_agent,
    initial_data={"type": "process_job", "data": input_data}
)
```

**Advanced Orchestration**
```python
from praval import AgentSession

# Create a managed agent session
session = AgentSession()
session.add_agent(data_processor)
session.add_agent(data_analyzer) 
session.add_agent(report_generator)

# Start session with configuration
session.start(
    initial_data={"type": "batch_process", "files": file_list},
    timeout=300,  # 5 minute timeout
    max_iterations=100
)

# Wait for completion
results = session.wait_for_completion()
```

### Agent Pipelines

```python
from praval import agent_pipeline

# Create a processing pipeline
@agent("input_processor", responds_to=["raw_input"])
def process_input(spore):
    processed = clean_and_validate(spore.knowledge["data"])
    return {"type": "cleaned_data", "data": processed}

@agent("data_analyzer", responds_to=["cleaned_data"])
def analyze_data(spore):
    analysis = run_analysis(spore.knowledge["data"])
    return {"type": "analysis_complete", "results": analysis}

@agent("report_generator", responds_to=["analysis_complete"])
def generate_report(spore):
    report = create_report(spore.knowledge["results"])
    return {"type": "report_ready", "report": report}

# Create and run pipeline
pipeline = agent_pipeline(process_input, analyze_data, generate_report)
results = pipeline.run({"type": "raw_input", "data": raw_data})
```

### Conditional Agents

```python
from praval import conditional_agent

@conditional_agent("error_handler", 
                  condition=lambda spore: spore.knowledge.get("error") is not None)
def handle_errors(spore):
    """Only runs when there's an error in the spore."""
    error = spore.knowledge["error"]
    return {"type": "error_handled", "resolution": fix_error(error)}

@conditional_agent("success_handler",
                  condition=lambda spore: spore.knowledge.get("status") == "success")
def handle_success(spore):
    """Only runs on successful operations."""
    return {"type": "success_logged", "timestamp": datetime.now()}
```

---

# PART IV: PROGRESSIVE LEARNING

## Learning Praval Through Practice

Understanding Praval's principles is one thing; applying them to build sophisticated multi-agent systems is another. This section presents a structured learning journey through nine carefully crafted examples that take you from basic agent concepts to advanced collective intelligence systems.

### The Three-Stage Learning Path

The examples follow a natural progression through three distinct stages, each building upon the previous:

#### 🌱 **Stage 1: Foundational Concepts (Examples 001-003)**
**Master the Core Principles**

These examples establish Praval's fundamental philosophy through hands-on practice:

- **001: Single Agent Identity** - Learn identity-driven behavior design
- **002: Agent Communication** - Master natural message-passing between agents  
- **003: Specialist Collaboration** - Discover emergent intelligence from specialization

**Stage Outcome:** You'll understand how simple agents with clear identities can collaborate to solve complex problems through natural communication patterns.

#### 🏗️ **Stage 2: Architectural Patterns (Examples 004-006)**
**Build Robust, Production-Ready Systems**

These examples demonstrate sophisticated patterns for building reliable systems:

- **004: Registry-Based Discovery** - Implement self-organizing coordination without central control
- **005: Memory-Enabled Agents** - Add continuity and learning across interactions
- **006: Resilient Agent Systems** - Ensure graceful handling of failures and errors

**Stage Outcome:** You'll master how to architect agent systems that are self-organizing, adaptive, and fault-tolerant.

#### 🚀 **Stage 3: Emergent Intelligence (Examples 007-009)**
**Achieve Collective Intelligence**

These examples explore the cutting edge of multi-agent systems:

- **007: Adaptive Agent Systems** - Create systems that learn and evolve their behavior
- **008: Self-Organizing Networks** - Enable network formation without hierarchy
- **009: Emergent Collective Intelligence** - Achieve system-level intelligence from individual interactions

**Stage Outcome:** You'll understand how the most sophisticated AI systems arise from the interaction of simple, autonomous agents.

### Running the Learning Journey

**Prerequisites:**
- Praval installed (see installation instructions)
- At least one LLM API key configured (OpenAI, Anthropic, or Cohere)

**Progressive Execution:**
```bash
# Stage 1: Foundational Concepts
python examples/001_single_agent_identity.py
python examples/002_agent_communication.py  
python examples/003_specialist_collaboration.py

# Stage 2: Architectural Patterns
python examples/004_registry_discovery.py
python examples/005_memory_enabled_agents.py
python examples/006_resilient_agents.py

# Stage 3: Emergent Intelligence
python examples/007_adaptive_agent_systems.py
python examples/008_self_organizing_networks.py
python examples/009_emergent_collective_intelligence.py
```

### Learning Methodology

**1. Sequential Progression**: Each example builds on concepts from previous ones. Follow the numerical order for optimal understanding.

**2. Code as Philosophy**: The implementations demonstrate Praval's principles in action. Read and understand the code, not just the output.

**3. Active Experimentation**: Modify the examples to explore different behaviors. Change agent identities, communication patterns, or collaboration structures.

**4. Emergence Observation**: Watch carefully for behaviors that arise from agent interactions—these demonstrate the core power of Praval.

**5. Principle Integration**: After each example, reflect on how it demonstrates the foundational principles discussed in earlier sections.

### The Coral Reef Development Pattern

The progression mirrors how coral reef ecosystems develop over time:

**Foundation Phase (001-003)**
- Individual coral polyps (agents) establish their basic life patterns
- Simple communication and collaboration patterns emerge
- Basic ecosystem relationships form

**Growth Phase (004-006)**  
- Different species (agent types) learn to coexist and collaborate effectively
- Robust structures develop that can handle environmental challenges
- System resilience and adaptation capabilities emerge

**Ecosystem Phase (007-009)**
- Complex relationships and emergent behaviors create a thriving whole
- The system exhibits intelligence and capabilities beyond any individual component
- Self-sustaining patterns of growth and evolution develop

### From Examples to Applications

After completing the learning journey, you'll be ready to:

1. **Design Agent Systems**: Apply Praval's principles to your specific use cases
2. **Implement Production Systems**: Build reliable, scalable multi-agent applications
3. **Explore Advanced Patterns**: Experiment with novel forms of collective intelligence
4. **Contribute to the Ecosystem**: Share your innovations and patterns with the community

The examples serve as both learning tools and reference implementations—patterns you can adapt and extend for real-world applications.

**Complete Learning Guide**: For detailed descriptions of each example, including specific learning objectives and key insights, see `examples/README_Examples.md`.

## Principles in Practice

### Emergence Through Simplicity

The examples demonstrate how Praval's power lies not in complex individual agents, but in how simple agents combine to create sophisticated behaviors:

```python
from praval import agent, chat, broadcast, start_agents

# Simple agents with clear purposes
@agent("observer")
def observe_environment(spore):
    """Observes and extracts relevant information."""
    data = spore.knowledge.get("input")
    observations = chat(f"What are the key observations about: {data}")
    broadcast({"type": "observations", "data": observations})
    return {"observations": observations}

@agent("reasoner", responds_to=["observations"])
def apply_reasoning(spore):
    """Applies logical reasoning to observations."""
    observations = spore.knowledge.get("data")
    reasoning = chat(f"What logical conclusions can be drawn from: {observations}")
    broadcast({"type": "reasoning", "conclusions": reasoning})
    return {"reasoning": reasoning}

@agent("synthesizer", responds_to=["reasoning"])
def synthesize_understanding(spore):
    """Synthesizes observations and reasoning into insights."""
    conclusions = spore.knowledge.get("conclusions")
    insights = chat(f"What deeper insights emerge from: {conclusions}")
    return {"insights": insights}
```

### The Communication-First Architecture

Praval systems are built around communication, not control:

```python
# Agents communicate through natural message passing
@agent("question_generator")
def generate_questions(spore):
    """Generates questions about a topic."""
    topic = spore.knowledge.get("subject")
    questions = chat(f"Generate thoughtful questions about {topic}")
    
    # Broadcast enables any interested agent to respond
    broadcast({
        "type": "questions_available",
        "topic": topic,
        "questions": questions
    })

@agent("answer_provider", responds_to=["questions_available"])
def provide_answers(spore):
    """Provides answers when questions are available."""
    questions = spore.knowledge.get("questions")
    topic = spore.knowledge.get("topic")
    
    answers = chat(f"Answer these questions about {topic}: {questions}")
    
    broadcast({
        "type": "dialogue_complete",
        "questions": questions,
        "answers": answers
    })
```

### Self-Organization Through Registry

Agents discover and coordinate with each other naturally:

```python
# Agents register their capabilities
@agent("capability_provider")
def provide_capabilities(spore):
    """Demonstrates self-registration and discovery."""
    
    # Agents can discover what capabilities exist
    available_agents = get_registry().list_agents()
    
    # And coordinate with others based on their roles
    for agent_info in available_agents:
        if "analyzer" in agent_info["name"]:
            # Found an analyzer - can collaborate
            broadcast({
                "type": "collaboration_request",
                "from": "capability_provider",
                "to": agent_info["name"]
            })
```

---

# PART V: COGNITIVE MEMORY ARCHITECTURE

## The Foundation of Persistent Intelligence

**Memory as the Bridge Between Interactions**

True intelligence requires continuity. Without memory, each agent interaction exists in isolation, unable to build upon previous experiences or maintain context across sessions. Praval's memory architecture addresses this fundamental need through a **multi-layered cognitive model** that mirrors human memory systems.

### Theoretical Foundation

**The Layered Memory Model:**

Human cognition employs multiple, specialized memory systems working in concert. Praval adapts this biological model:

1. **Working Memory** (Short-term): Immediate context and active processing
2. **Episodic Memory**: Experiential records of specific interactions and events  
3. **Semantic Memory**: Abstracted knowledge and learned patterns
4. **Procedural Memory**: Implicit knowledge about how to perform tasks

**The Persistence Challenge:**

Traditional AI systems are **stateless** - each interaction begins from scratch. This creates several problems:

- **Context Loss**: Agents can't build upon previous conversations
- **Repetitive Learning**: Agents must relearn the same patterns repeatedly
- **Limited Personalization**: Systems can't adapt to user preferences over time
- **Inefficient Processing**: Agents can't leverage cached insights or decisions

**The Praval Memory Solution:**

Praval's memory architecture provides **cognitive continuity** while maintaining the benefits of agent specialization.

### Memory Layers Overview

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

### Memory Types

**1. Short-term Memory**
- Fast, working memory for immediate context
- In-process Python data structures
- Capacity: ~1000 entries (configurable)
- Lifetime: 24 hours (configurable)

**2. Long-term Memory**
- Persistent vector storage using Qdrant
- Semantic similarity search capabilities
- Millions of entries capacity
- Persistent across restarts

**3. Episodic Memory**
- Conversation history and experience tracking
- Timeline-based organization
- Context windows for dialogue continuity

**4. Semantic Memory**
- Factual knowledge and concept relationships
- Domain-specific expertise building
- Knowledge validation and consistency

## Working with Memories

### Basic Memory Operations

```python
from praval.memory import MemoryManager, MemoryType, MemoryQuery

# Initialize memory system
memory = MemoryManager(
    qdrant_url="http://localhost:6333",
    collection_name="my_agent_memories"
)

# Store a memory
memory_id = memory.store_memory(
    agent_id="my_agent",
    content="User prefers technical documentation with code examples",
    memory_type=MemoryType.SHORT_TERM,
    importance=0.8
)

# Search memories
query = MemoryQuery(
    query_text="user preferences documentation",
    agent_id="my_agent",
    limit=5
)
results = memory.search_memories(query)

for entry in results.entries:
    print(f"Found: {entry.content}")
```

### Memory Configuration

```python
# Docker setup for full memory capabilities
# docker-compose.yml includes Qdrant service

# Environment variables
QDRANT_URL=http://localhost:6333
PRAVAL_COLLECTION_NAME=praval_memories
SHORT_TERM_MAX_ENTRIES=1000
SHORT_TERM_RETENTION_HOURS=24

# Programmatic configuration
memory = MemoryManager(
    qdrant_url="http://localhost:6333",
    collection_name="production_memories",
    short_term_max_entries=2000,
    short_term_retention_hours=48
)
```

### Advanced Memory Operations

```python
# Store conversation turn
memory.store_conversation_turn(
    agent_id="chatbot",
    user_message="How does machine learning work?",
    agent_response="Machine learning enables computers to learn patterns...",
    context={"session_id": "abc123", "timestamp": datetime.now()}
)

# Store domain knowledge
memory.store_knowledge(
    agent_id="expert_system",
    knowledge="Neural networks use backpropagation for training",
    domain="machine_learning",
    confidence=0.95
)

# Get conversation context
context = memory.get_conversation_context(
    agent_id="chatbot",
    turns=10  # Last 10 conversation turns
)

# Get domain knowledge
ml_knowledge = memory.get_domain_knowledge(
    agent_id="expert_system",
    domain="machine_learning",
    limit=20
)

# Advanced search with filters
query = MemoryQuery(
    query_text="neural network training",
    memory_types=[MemoryType.SEMANTIC, MemoryType.EPISODIC],
    agent_id="expert_system",
    limit=10,
    similarity_threshold=0.8,
    temporal_filter={
        "after": datetime.now() - timedelta(days=7),
        "before": datetime.now()
    }
)
```

## Memory-Enabled Agents

### Basic Memory-Aware Agent

```python
from praval import agent, chat
from praval.memory import MemoryManager, MemoryType, MemoryQuery

# Global memory manager
memory = MemoryManager()

@agent("memory_assistant", responds_to=["user_query"])
def memory_assistant(spore):
    """Agent that uses memory to provide personalized responses."""
    user_query = spore.knowledge.get("query")
    agent_id = "memory_assistant"
    
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

### Learning Agent Pattern

```python
@agent("learning_agent", responds_to=["learning_experience"])
def learning_agent(spore):
    """Agent that learns from successful interactions."""
    experience = spore.knowledge.get("experience")
    outcome = spore.knowledge.get("outcome")
    success = spore.knowledge.get("success", False)
    
    agent_id = "learning_agent"
    
    if success:
        # Store successful pattern
        memory.store_memory(
            agent_id=agent_id,
            content=f"Successful approach: {experience} led to {outcome}",
            memory_type=MemoryType.PROCEDURAL,
            importance=0.9
        )
        
        print(f"✅ Learned successful pattern: {experience[:50]}...")
    else:
        # Store failure to avoid
        memory.store_memory(
            agent_id=agent_id,
            content=f"Avoid: {experience} resulted in {outcome}",
            memory_type=MemoryType.PROCEDURAL,
            importance=0.7
        )
        
        print(f"⚠️ Learned to avoid: {experience[:50]}...")
    
    # Apply learned patterns to current situation
    similar_experiences = memory.search_memories(MemoryQuery(
        query_text=experience,
        agent_id=agent_id,
        memory_types=[MemoryType.PROCEDURAL],
        limit=5
    ))
    
    return {
        "learned": True,
        "similar_experiences": len(similar_experiences.entries)
    }
```

### Knowledge Building Agent

```python
@agent("knowledge_builder", responds_to=["new_information"])
def knowledge_builder(spore):
    """Agent that builds and validates knowledge."""
    information = spore.knowledge.get("information")
    domain = spore.knowledge.get("domain", "general")
    source = spore.knowledge.get("source", "unknown")
    
    agent_id = "knowledge_builder"
    
    # Validate against existing knowledge
    existing_knowledge = memory.get_domain_knowledge(
        agent_id=agent_id,
        domain=domain,
        limit=50
    )
    
    # Check for contradictions
    validation_prompt = f"""
    New information: {information}
    
    Existing knowledge in {domain} domain:
    {chr(10).join([k.content for k in existing_knowledge[:5]])}
    
    Is this new information:
    1. Consistent with existing knowledge?
    2. New and valuable?
    3. Reliable given the source: {source}?
    
    Respond with: ACCEPT, REJECT, or NEEDS_VERIFICATION
    Include brief reasoning.
    """
    
    validation = chat(validation_prompt)
    
    if "ACCEPT" in validation:
        # Store as knowledge
        memory.store_knowledge(
            agent_id=agent_id,
            knowledge=information,
            domain=domain,
            confidence=0.8,
            metadata={"source": source, "validation": validation}
        )
        
        print(f"✅ Knowledge accepted in {domain}: {information[:50]}...")
        
        return {"status": "accepted", "domain": domain}
    
    elif "NEEDS_VERIFICATION" in validation:
        # Store with lower confidence for future verification
        memory.store_memory(
            agent_id=agent_id,
            content=f"Unverified: {information}",
            memory_type=MemoryType.SEMANTIC,
            importance=0.5,
            metadata={"needs_verification": True, "source": source}
        )
        
        return {"status": "needs_verification", "reason": validation}
    
    else:
        print(f"❌ Knowledge rejected: {validation}")
        return {"status": "rejected", "reason": validation}
```

### Memory System Monitoring

```python
@agent("memory_monitor", responds_to=["memory_status"])
def memory_monitor(spore):
    """Monitors memory system health and usage."""
    
    # Get memory statistics
    stats = memory.get_memory_stats()
    
    print("📊 Memory System Status:")
    print(f"   Short-term: {stats['short_term_memory']['total_memories']} entries")
    
    if stats['long_term_memory']['available']:
        lt_stats = stats['long_term_memory']
        print(f"   Long-term: {lt_stats.get('total_memories', 'N/A')} entries")
        print(f"   Vector DB: {lt_stats.get('vector_size', 'N/A')} dimensions")
    else:
        print(f"   Long-term: Unavailable - {stats['long_term_memory'].get('error')}")
    
    # Check for cleanup needs
    if stats['short_term_memory']['total_memories'] > 800:
        print("⚠️ Short-term memory getting full, cleanup recommended")
        memory.short_term_memory._cleanup_old_memories()
        
    # Memory health check
    health = memory.health_check()
    print(f"   Health: {health}")
    
    return {"stats": stats, "health": health}

# Example: Complete memory-enabled system
def create_memory_enabled_system():
    """Creates a complete system with memory capabilities."""
    
    # Initialize memory
    global memory
    memory = MemoryManager(
        qdrant_url=os.getenv('QDRANT_URL', 'http://localhost:6333'),
        collection_name=os.getenv('PRAVAL_COLLECTION_NAME', 'praval_memories')
    )
    
    # Start memory-enabled agents
    start_agents(
        memory_assistant,
        learning_agent,
        knowledge_builder,
        memory_monitor,
        initial_data={"type": "system_ready"}
    )
    
    return memory

# Initialize and run
if __name__ == "__main__":
    memory_system = create_memory_enabled_system()
    print("🧠 Memory-enabled system ready!")
```

---

# PART VI: UNIFIED DATA STORAGE & RETRIEVAL SYSTEM

**Enterprise-Grade Data Ecosystem for Multi-Agent Systems**

Praval v0.6.1 introduces a comprehensive **Unified Data Storage & Retrieval System** that transforms the framework from a communication platform into a complete data ecosystem. This system provides agents with seamless access to multiple storage backends while maintaining Praval's core philosophy of simplicity through specialization.

## Storage Architecture Overview

**Data as the Foundation of Intelligence**

Modern AI agents require more than just communication—they need persistent state, shared data access, and the ability to work with diverse data types across multiple storage systems. The Unified Storage System addresses these needs through a carefully designed architecture that follows Praval's established patterns.

### Design Philosophy

**"Simple access to complex data"**

The storage system embodies Praval's core principles:

- **Registry Discovery**: Same pattern as agent and tool registries
- **Decorator Interface**: Consistent with `@agent()` decorator philosophy  
- **Spore Communication**: Data references flow through reef naturally
- **Zero Configuration**: Environment-based auto-setup with sensible defaults
- **Progressive Enhancement**: Start simple, add complexity as needed

### Architecture Components

```
┌─────────────────────────────────────────────────────────┐
│                Agent Decorator Layer                    │
│        (@storage_enabled, @requires_storage)           │
├─────────────────────────────────────────────────────────┤
│                  Data Manager                          │
│            (Unified Interface)                          │
├─────────────────────────────────────────────────────────┤
│                Storage Registry                         │
│          (Provider Discovery & Management)              │
├─────────────────────────────────────────────────────────┤
│  PostgreSQL │  Redis  │   S3    │ Qdrant │ FileSystem │
│ (Relational)│(Cache)  │(Object) │(Vector)│   (Files)   │
├─────────────────────────────────────────────────────────┤
│                Memory Integration                       │
│           (Unified Memory + Storage)                    │
├─────────────────────────────────────────────────────────┤
│                Spore Data References                    │
│         (Lightweight Data Sharing)                     │
└─────────────────────────────────────────────────────────┘
```

### Key Features

**Production-Ready Capabilities:**
- **Async Throughout**: Full async/await support across all providers
- **Connection Pooling**: Efficient resource management with health monitoring
- **Security**: Permission-based access control per agent
- **Error Handling**: Comprehensive exception hierarchy with graceful fallbacks
- **Smart Selection**: Automatic provider choice based on data characteristics

**Following Praval Patterns:**
- **Registry Pattern**: Consistent discovery mechanism
- **Decorator Interface**: Declarative storage access
- **Reef Communication**: Data references through spores
- **Memory Integration**: Unified interface combining memory + external storage

## Storage Provider Framework

### Base Provider Architecture

All storage providers inherit from `BaseStorageProvider`, ensuring consistent interfaces across different backend types:

```python
from praval.storage import BaseStorageProvider, StorageResult, StorageType

class CustomStorageProvider(BaseStorageProvider):
    """Custom storage provider following Praval patterns."""
    
    def _create_metadata(self) -> StorageMetadata:
        return StorageMetadata(
            name=self.name,
            description="Custom storage provider",
            storage_type=StorageType.DOCUMENT,
            supports_async=True,
            supports_transactions=False,
            required_config=["endpoint_url", "database_name"],
            optional_config=["timeout", "pool_size"]
        )
    
    async def connect(self) -> bool:
        """Establish connection to storage backend."""
        # Implementation specific to your storage system
        pass
    
    async def store(self, resource: str, data: Any, **kwargs) -> StorageResult:
        """Store data with provider-specific logic."""
        pass
    
    async def retrieve(self, resource: str, **kwargs) -> StorageResult:
        """Retrieve data with type-aware decoding."""
        pass
    
    async def query(self, resource: str, query: Union[str, Dict], **kwargs) -> StorageResult:
        """Execute queries with result formatting."""
        pass
    
    async def delete(self, resource: str, **kwargs) -> StorageResult:
        """Delete with confirmation and cleanup."""
        pass
```

### Storage Types Supported

The framework categorizes storage providers by their fundamental characteristics:

```python
from praval.storage import StorageType

# Supported storage types
StorageType.RELATIONAL    # PostgreSQL, MySQL, SQLite
StorageType.KEY_VALUE     # Redis, DynamoDB, Memcached
StorageType.OBJECT        # S3, MinIO, Azure Blob
StorageType.VECTOR        # Qdrant, Pinecone, Weaviate
StorageType.DOCUMENT      # MongoDB, CouchDB
StorageType.SEARCH        # Elasticsearch, Solr
StorageType.GRAPH         # Neo4j, Amazon Neptune
StorageType.FILE_SYSTEM   # Local files, NFS, HDFS
StorageType.CACHE         # Redis, Memcached (optimized)
StorageType.QUEUE         # RabbitMQ, Kafka, SQS
```

### Provider Registration

Storage providers auto-register based on environment configuration:

```python
from praval.storage import register_storage_provider, PostgreSQLProvider

# Manual registration
postgres_provider = PostgreSQLProvider("main_db", {
    "host": "localhost",
    "database": "business", 
    "user": "praval",
    "password": "secure_password"
})

await register_storage_provider(postgres_provider, permissions=["analytics_agent"])

# Environment-based auto-registration
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_DB"] = "business"
os.environ["POSTGRES_USER"] = "praval"
os.environ["POSTGRES_PASSWORD"] = "secure_password"

# Agent decorator automatically registers from environment
@storage_enabled(["postgres"])
@agent("business_analyst")
def analyze_data(spore, storage):
    # PostgreSQL provider auto-registered and available
    pass
```

## Built-in Storage Providers

### PostgreSQL Provider

**Enterprise Relational Database with Async Connection Pooling**

```python
from praval.storage import PostgreSQLProvider

# Advanced PostgreSQL configuration
postgres_config = {
    "host": "production-pg.company.com",
    "port": 5432,
    "database": "enterprise_data",
    "user": "praval_system",
    "password": "secure_enterprise_password",
    "pool_min_size": 5,
    "pool_max_size": 20,
    "ssl": True
}

# Agent with PostgreSQL access
@storage_enabled({"postgres": postgres_config})
@agent("data_analyst")
async def analyze_customer_data(spore, storage):
    # Complex SQL queries with parameters
    results = await storage.query(
        "postgres",
        "customer_analysis", 
        """
        SELECT customer_segment, AVG(revenue), COUNT(*) 
        FROM customers 
        WHERE created_date >= $1 AND status = $2
        GROUP BY customer_segment
        ORDER BY AVG(revenue) DESC
        """,
        params=[datetime(2024, 1, 1), "active"]
    )
    
    if results.success:
        segments = results.data
        broadcast({
            "type": "analysis_complete",
            "segments": segments,
            "total_analyzed": sum(row["count"] for row in segments)
        })
    
    return {"status": "analyzed", "segments": len(segments)}

# Bulk operations for high throughput
@storage_enabled(["postgres"])
@agent("data_ingestion")
async def ingest_customer_batch(spore, storage):
    customers = spore.knowledge.get("customer_batch", [])
    
    # Bulk insert with transaction safety
    result = await storage.store(
        "postgres", 
        "customers", 
        customers,  # List of customer dictionaries
        returning="id"  # Return inserted IDs
    )
    
    if result.success:
        print(f"✅ Ingested {len(customers)} customers")
        return {"ingested_count": len(customers)}
    else:
        print(f"❌ Ingestion failed: {result.error}")
        return {"error": result.error}
```

**Features:**
- Async connection pooling with configurable sizes
- SQL query execution with parameter binding  
- Bulk operations for high-throughput scenarios
- Transaction support with rollback capabilities
- Full-text search integration
- JSON column support for hybrid storage

### Redis Provider

**High-Performance Key-Value Cache with Data Structures**

```python
from praval.storage import RedisProvider

# Redis with advanced configuration
redis_config = {
    "host": "redis-cluster.company.com",
    "port": 6379,
    "password": "redis_secure_password",
    "database": 0,
    "pool_max_size": 20,
    "ssl": True
}

@storage_enabled({"redis": redis_config})
@agent("cache_manager")
async def manage_application_cache(spore, storage):
    cache_key = spore.knowledge.get("cache_key")
    data = spore.knowledge.get("data")
    operation = spore.knowledge.get("operation", "set")
    
    if operation == "set":
        # Store with expiration
        result = await storage.store(
            "redis",
            cache_key,
            data,
            ex=3600,  # Expire in 1 hour
            nx=True   # Only if key doesn't exist
        )
        
        if result.success:
            return {"cached": True, "key": cache_key}
    
    elif operation == "get":
        # Retrieve with JSON decoding
        result = await storage.get("redis", cache_key, decode_json=True)
        
        if result.success:
            return {"data": result.data, "found": True}
        else:
            return {"found": False}
    
    elif operation == "pattern_search":
        # Search for keys matching pattern
        pattern = spore.knowledge.get("pattern", "*")
        result = await storage.query("redis", pattern, "keys")
        
        if result.success:
            return {"matching_keys": result.data}

# Session management example
@storage_enabled(["redis"])
@agent("session_manager") 
async def manage_user_sessions(spore, storage):
    user_id = spore.knowledge.get("user_id")
    session_data = spore.knowledge.get("session_data")
    
    # Store session with hash operations
    session_key = f"session:{user_id}"
    
    # Use Redis hash for session fields
    result = await storage.query(
        "redis",
        session_key, 
        "hset",
        fields=session_data,
        ttl=86400  # 24 hours
    )
    
    # Track active sessions
    await storage.query("redis", "active_sessions", "sadd", members=[user_id])
    
    return {"session_created": result.success}
```

**Features:**
- All Redis data types (strings, hashes, lists, sets, sorted sets)
- Pub/Sub messaging capabilities
- Lua script execution for atomic operations
- TTL and expiration management
- Pipeline operations for batch processing
- Redis Cluster support for horizontal scaling

### S3 Provider

**Scalable Object Storage for Large Data and Assets**

```python
from praval.storage import S3Provider

# S3 configuration (works with AWS S3, MinIO, etc.)
s3_config = {
    "bucket_name": "enterprise-ai-data",
    "aws_access_key_id": "AKIA...",
    "aws_secret_access_key": "...",
    "region_name": "us-west-2",
    "endpoint_url": None,  # Use AWS S3, or specify MinIO endpoint
    "use_ssl": True
}

@storage_enabled({"s3": s3_config})
@agent("document_processor")
async def process_documents(spore, storage):
    document_content = spore.knowledge.get("document")
    doc_type = spore.knowledge.get("type", "pdf")
    doc_id = spore.knowledge.get("document_id")
    
    # Store document with metadata
    object_key = f"documents/{doc_type}/{doc_id}.{doc_type}"
    
    result = await storage.store(
        "s3",
        object_key,
        document_content,
        content_type=f"application/{doc_type}",
        metadata={
            "processed_by": "document_processor",
            "processing_date": datetime.now().isoformat(),
            "document_type": doc_type
        },
        server_side_encryption="AES256"
    )
    
    if result.success:
        # Create data reference for sharing
        doc_ref = result.data_reference.to_uri()
        
        broadcast({
            "type": "document_stored",
            "document_reference": doc_ref,
            "document_id": doc_id,
            "size": result.metadata.get("size", 0)
        })
        
        return {"stored": True, "reference": doc_ref}

# Report generation and storage
@storage_enabled(["s3"])
@agent("report_generator")
async def generate_business_report(spore, storage):
    analysis_data = spore.knowledge.get("analysis_data")
    report_format = spore.knowledge.get("format", "pdf")
    
    # Generate report from analysis
    if report_format == "pdf":
        report_content = generate_pdf_report(analysis_data)
        content_type = "application/pdf"
    elif report_format == "excel":
        report_content = generate_excel_report(analysis_data)
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    # Store with presigned URL for secure access
    report_key = f"reports/{datetime.now().strftime('%Y/%m/%d')}/business_analysis_{uuid.uuid4().hex[:8]}.{report_format}"
    
    result = await storage.store(
        "s3",
        report_key,
        report_content,
        content_type=content_type,
        cache_control="max-age=86400"  # Cache for 24 hours
    )
    
    if result.success:
        # Generate presigned URL for secure download
        url_result = await storage.query(
            "s3", 
            report_key, 
            "presigned_url",
            method="GET",
            expiration=7200  # 2 hours
        )
        
        return {
            "report_generated": True,
            "download_url": url_result.data.get("url"),
            "expires_at": datetime.now() + timedelta(hours=2)
        }
```

**Features:**
- Multipart uploads for large files
- Server-side encryption (SSE)
- Presigned URLs for secure temporary access
- Object metadata and tagging
- Lifecycle management integration
- Cross-region replication support
- Compatible with AWS S3, MinIO, and other S3-compatible services

### Qdrant Vector Provider

**Semantic Search and Vector Operations**

```python
from praval.storage import QdrantProvider

# Qdrant configuration for production
qdrant_config = {
    "url": "https://qdrant.company.com:6333",
    "api_key": "qdrant_production_key",
    "collection_name": "enterprise_embeddings",
    "vector_size": 1536,  # OpenAI embedding size
    "distance_metric": "cosine"
}

@storage_enabled({"qdrant": qdrant_config})
@agent("semantic_search") 
async def semantic_document_search(spore, storage):
    query_text = spore.knowledge.get("query")
    limit = spore.knowledge.get("limit", 10)
    
    # Generate embedding for query (in practice, use your embedding model)
    query_embedding = await generate_embedding(query_text)
    
    # Perform vector similarity search
    results = await storage.query(
        "qdrant",
        "enterprise_documents",
        "search",
        vector=query_embedding,
        limit=limit,
        with_payload=True,
        score_threshold=0.7,
        filter={
            "must": [
                {"key": "document_type", "match": {"value": "policy"}},
                {"key": "department", "match": {"any": ["legal", "hr", "finance"]}}
            ]
        }
    )
    
    if results.success:
        documents = []
        for result in results.data:
            documents.append({
                "id": result["id"],
                "score": result["score"],
                "title": result["payload"]["title"],
                "content_preview": result["payload"]["content"][:200],
                "department": result["payload"]["department"]
            })
        
        return {"documents": documents, "total_found": len(documents)}

# Document indexing for semantic search
@storage_enabled(["qdrant"])
@agent("document_indexer")
async def index_documents(spore, storage):
    documents = spore.knowledge.get("documents", [])
    
    # Prepare documents for vector storage
    vector_documents = []
    for doc in documents:
        # Generate embedding for document content
        embedding = await generate_embedding(doc["content"])
        
        vector_documents.append({
            "id": doc["id"],
            "vector": embedding,
            "payload": {
                "title": doc["title"],
                "content": doc["content"],
                "department": doc["department"],
                "document_type": doc["type"],
                "indexed_at": datetime.now().isoformat()
            }
        })
    
    # Batch insert into Qdrant
    result = await storage.store("qdrant", "enterprise_documents", vector_documents)
    
    if result.success:
        print(f"✅ Indexed {len(vector_documents)} documents")
        return {"indexed": len(vector_documents)}
    else:
        print(f"❌ Indexing failed: {result.error}")
        return {"error": result.error}
```

**Features:**
- High-performance vector similarity search
- Advanced filtering with metadata
- Batch operations for efficient indexing  
- Collection management and optimization
- Payload storage with vectors
- Distributed deployment support
- Integration with existing Praval memory system

### FileSystem Provider

**Local and Network File Operations**

```python
from praval.storage import FileSystemProvider

# FileSystem configuration
fs_config = {
    "base_path": "/data/praval/agent_storage",
    "create_directories": True,
    "permissions": 0o644,
    "max_file_size": 100 * 1024 * 1024  # 100MB
}

@storage_enabled({"filesystem": fs_config})
@agent("file_manager")
async def manage_agent_files(spore, storage):
    operation = spore.knowledge.get("operation")
    file_path = spore.knowledge.get("path")
    
    if operation == "store_config":
        config_data = spore.knowledge.get("config_data")
        
        result = await storage.store(
            "filesystem",
            f"configs/{file_path}.json",
            config_data,
            encoding="utf-8"
        )
        
        return {"config_stored": result.success}
    
    elif operation == "backup_logs":
        log_content = spore.knowledge.get("log_content")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        result = await storage.store(
            "filesystem",
            f"logs/agent_logs_{timestamp}.log",
            log_content,
            encoding="utf-8"
        )
        
        return {"backup_created": result.success}
    
    elif operation == "search_files":
        pattern = spore.knowledge.get("pattern", "*.json")
        directory = spore.knowledge.get("directory", ".")
        
        result = await storage.query(
            "filesystem",
            directory,
            "find",
            pattern=pattern,
            recursive=True
        )
        
        if result.success:
            return {"files_found": result.data}

# Configuration management example
@storage_enabled(["filesystem"])
@agent("config_manager")
async def manage_configurations(spore, storage):
    config_type = spore.knowledge.get("config_type")
    config_data = spore.knowledge.get("config_data")
    
    if config_data:
        # Store configuration
        result = await storage.store(
            "filesystem",
            f"configs/{config_type}_config.yaml",
            yaml.dump(config_data),
            encoding="utf-8"
        )
        
        if result.success:
            # Broadcast configuration update
            broadcast({
                "type": "config_updated",
                "config_type": config_type,
                "file_path": f"configs/{config_type}_config.yaml"
            })
    else:
        # Load configuration
        result = await storage.get(
            "filesystem",
            f"configs/{config_type}_config.yaml",
            encoding="utf-8"
        )
        
        if result.success:
            config_data = yaml.safe_load(result.data)
            return {"config": config_data}
    
    return {"operation_complete": True}
```

**Features:**
- Secure path management (prevents directory traversal)
- Automatic directory creation
- File permissions management
- Pattern-based file search
- Binary and text file handling
- Atomic file operations
- File metadata extraction

## Storage Decorators for Agents

### Basic Storage Decorator

The `@storage_enabled()` decorator provides declarative storage access:

```python
from praval.storage import storage_enabled
from praval import agent, broadcast

# Single provider
@storage_enabled("postgres")
@agent("data_analyst")
def analyze_sales_data(spore, storage):
    """Agent with PostgreSQL access."""
    pass

# Multiple providers
@storage_enabled(["postgres", "redis", "s3"])
@agent("business_intelligence")
def comprehensive_analysis(spore, storage):
    """Agent with access to multiple storage backends."""
    pass

# Providers with configuration
@storage_enabled({
    "postgres": {"database": "analytics", "host": "analytics-db.company.com"},
    "redis": {"database": 1, "host": "cache.company.com"},
    "s3": {"bucket_name": "analytics-reports"}
})
@agent("enterprise_analyst")
def enterprise_analysis(spore, storage):
    """Agent with custom provider configurations."""
    pass
```

### Advanced Storage Configuration

```python
# Environment-based auto-registration
@storage_enabled(
    providers=["postgres", "s3", "qdrant"],
    auto_register=True,  # Register from environment variables
    permissions=["analytics_team"],  # Restrict access
    postgres_host="analytics-db.company.com",
    postgres_database="enterprise_data", 
    s3_bucket_name="enterprise-analytics",
    qdrant_collection_name="enterprise_vectors"
)
@agent("enterprise_analytics")
def enterprise_analytics_agent(spore, storage):
    """
    Production agent with comprehensive storage access.
    Environment variables like POSTGRES_PASSWORD are auto-loaded.
    """
    analysis_type = spore.knowledge.get("analysis_type")
    
    if analysis_type == "customer_segmentation":
        # Complex multi-storage workflow
        
        # 1. Get customer data from PostgreSQL
        customers = await storage.query(
            "postgres",
            "customers",
            "SELECT * FROM customers WHERE status = 'active'"
        )
        
        # 2. Generate embeddings and search similar customers
        for customer in customers.data:
            embedding = await generate_customer_embedding(customer)
            similar = await storage.query(
                "qdrant", 
                "customer_vectors",
                "search",
                vector=embedding,
                limit=5
            )
            customer["similar_customers"] = similar.data
        
        # 3. Cache analysis results
        cache_key = f"customer_analysis:{datetime.now().strftime('%Y%m%d')}"
        await storage.store("redis", cache_key, customers.data, ex=86400)
        
        # 4. Generate and store report
        report = generate_customer_report(customers.data)
        report_ref = await storage.store(
            "s3",
            f"reports/customer_segmentation_{datetime.now():%Y%m%d}.pdf",
            report
        )
        
        # 5. Share results via spore
        broadcast({
            "type": "analysis_complete",
            "analysis_type": "customer_segmentation",
            "report_reference": report_ref.data_reference.to_uri(),
            "customers_analyzed": len(customers.data)
        })
        
        return {"status": "complete", "customers": len(customers.data)}
```

### Storage Requirements Decorator

```python
from praval.storage import requires_storage

# Require specific storage providers
@requires_storage("postgres", "s3")
@agent("financial_analyst")
def financial_analysis(spore, storage):
    """This agent requires both PostgreSQL and S3 to function."""
    
    # Get financial data from PostgreSQL
    financial_data = await storage.query(
        "postgres",
        "financial_records", 
        "SELECT * FROM quarterly_results WHERE year = $1",
        params=[2024]
    )
    
    # Store analysis in S3
    analysis = perform_financial_analysis(financial_data.data)
    await storage.store("s3", "analyses/financial_q4_2024.json", analysis)
    
    return {"analysis_complete": True}

# This will fail at startup if required storage isn't available
try:
    start_agents(financial_analysis)
except StorageConfigurationError as e:
    print(f"Missing required storage: {e}")
    # Handle missing storage gracefully
```

## Data References in Spore Communication

### Lightweight Data Sharing

Instead of embedding large data directly in spores, agents share lightweight references:

```python
from praval import agent, broadcast
from praval.storage import storage_enabled

@storage_enabled(["s3", "postgres"])
@agent("data_producer")
async def produce_large_dataset(spore, storage):
    """Generates large dataset and shares via reference."""
    
    # Generate large analysis results
    analysis_results = perform_complex_analysis()  # Large dataset
    
    # Store in appropriate backend
    result = await storage.store(
        "s3",
        f"analyses/complex_analysis_{uuid.uuid4().hex[:8]}.json",
        analysis_results
    )
    
    if result.success:
        # Share lightweight reference instead of full data
        broadcast({
            "type": "large_dataset_ready",
            "dataset_reference": result.data_reference.to_uri(),
            "dataset_size": len(analysis_results),
            "analysis_type": "complex_analysis"
        })
        
        return {"dataset_stored": True}

@storage_enabled(["s3"])
@agent("data_consumer", responds_to=["large_dataset_ready"])
async def consume_large_dataset(spore, storage):
    """Consumes dataset via reference resolution."""
    
    # Get the data reference from spore
    dataset_ref = spore.knowledge.get("dataset_reference")
    analysis_type = spore.knowledge.get("analysis_type")
    
    if dataset_ref:
        # Resolve reference to actual data
        result = await storage.resolve_data_reference(dataset_ref)
        
        if result.success:
            dataset = result.data
            
            # Process the dataset
            processed_results = process_analysis_results(dataset, analysis_type)
            
            # Share processed results
            processed_ref = await storage.store(
                "s3", 
                f"processed/{analysis_type}_{datetime.now():%Y%m%d}.json",
                processed_results
            )
            
            broadcast({
                "type": "dataset_processed",
                "original_reference": dataset_ref,
                "processed_reference": processed_ref.data_reference.to_uri()
            })
            
            return {"processed": True}
```

### Automatic Data Reference Management

The Praval spore system automatically handles data references:

```python
# Enhanced spore with data references
@agent("report_generator")
async def generate_comprehensive_report(spore, storage):
    """Demonstrates automatic data reference handling."""
    
    # Check if spore contains data references
    if spore.has_data_references():
        print(f"Found {len(spore.data_references)} data references in spore")
        
        # Automatically resolve all references
        resolved_data = {}
        for ref_uri in spore.data_references:
            result = await storage.resolve_data_reference(ref_uri)
            if result.success:
                # Extract meaningful name from URI
                ref_name = ref_uri.split('/')[-1].split('.')[0]
                resolved_data[ref_name] = result.data
        
        # Generate report from all resolved data
        comprehensive_report = generate_report(resolved_data)
        
        # Store and reference the report
        report_ref = await storage.store(
            "s3",
            f"reports/comprehensive_{datetime.now():%Y%m%d_%H%M}.pdf",
            comprehensive_report
        )
        
        return {
            "report_generated": True,
            "report_reference": report_ref.data_reference.to_uri(),
            "data_sources": len(resolved_data)
        }
```

### Cross-Agent Data Workflows

```python
# Complete workflow using data references
@storage_enabled(["postgres"])
@agent("data_extractor") 
async def extract_customer_data(spore, storage):
    """Extract customer data and share via reference."""
    
    extraction_params = spore.knowledge.get("extraction_params", {})
    
    # Extract data based on parameters
    customer_data = await storage.query(
        "postgres",
        "customers",
        "SELECT * FROM customers WHERE region = $1 AND status = $2",
        params=[extraction_params.get("region", "US"), "active"]
    )
    
    if customer_data.success:
        # Store extracted data
        data_ref = await storage.store(
            "s3",
            f"extractions/customers_{extraction_params['region']}_{datetime.now():%Y%m%d}.json",
            customer_data.data
        )
        
        broadcast({
            "type": "data_extracted",
            "data_reference": data_ref.data_reference.to_uri(),
            "extraction_params": extraction_params,
            "record_count": len(customer_data.data)
        })

@storage_enabled(["s3", "qdrant"])  
@agent("data_enricher", responds_to=["data_extracted"])
async def enrich_customer_data(spore, storage):
    """Enrich customer data with additional context."""
    
    # Resolve the extracted data
    data_ref = spore.knowledge.get("data_reference")
    result = await storage.resolve_data_reference(data_ref)
    
    if result.success:
        customers = result.data
        
        # Enrich with vector search
        enriched_customers = []
        for customer in customers:
            # Find similar customers
            customer_embedding = await generate_customer_embedding(customer)
            similar = await storage.query(
                "qdrant",
                "customer_vectors", 
                "search",
                vector=customer_embedding,
                limit=3
            )
            
            customer["similar_profiles"] = similar.data
            enriched_customers.append(customer)
        
        # Store enriched data
        enriched_ref = await storage.store(
            "s3",
            f"enriched/customers_enriched_{datetime.now():%Y%m%d_%H%M}.json",
            enriched_customers
        )
        
        broadcast({
            "type": "data_enriched",
            "original_reference": data_ref,
            "enriched_reference": enriched_ref.data_reference.to_uri(),
            "enriched_count": len(enriched_customers)
        })

@storage_enabled(["s3"])
@agent("report_finalizer", responds_to=["data_enriched"])
async def finalize_customer_report(spore, storage):
    """Generate final report from enriched data."""
    
    # Resolve enriched data
    enriched_ref = spore.knowledge.get("enriched_reference")
    result = await storage.resolve_data_reference(enriched_ref)
    
    if result.success:
        enriched_data = result.data
        
        # Generate final report
        final_report = generate_customer_insights_report(enriched_data)
        
        # Store final report with presigned URL
        report_result = await storage.store(
            "s3",
            f"reports/final_customer_insights_{datetime.now():%Y%m%d}.pdf",
            final_report,
            content_type="application/pdf"
        )
        
        # Generate shareable URL
        url_result = await storage.query(
            "s3",
            report_result.data_reference.resource_id,
            "presigned_url",
            expiration=86400  # 24 hours
        )
        
        print(f"✅ Final report ready: {url_result.data['url']}")
        
        return {
            "final_report": report_result.data_reference.to_uri(),
            "shareable_url": url_result.data["url"],
            "customers_analyzed": len(enriched_data)
        }
```

## Memory-Storage Integration

### Unified Data Interface

The storage system seamlessly integrates with Praval's existing memory architecture:

```python
from praval.storage import UnifiedDataInterface
from praval.memory import MemoryManager

# Initialize unified interface
memory_manager = MemoryManager(agent_id="unified_agent")
data_manager = get_data_manager()

unified_data = UnifiedDataInterface(
    agent_id="unified_agent",
    memory_manager=memory_manager,
    data_manager=data_manager
)

@agent("unified_intelligence")
async def intelligent_agent_with_unified_data(spore):
    """Agent using both memory and storage seamlessly."""
    
    user_query = spore.knowledge.get("query")
    
    # Search across memory and storage simultaneously
    search_results = await unified_data.search(
        query=user_query,
        locations=["memory:episodic", "memory:semantic", "postgres:knowledge_base", "qdrant:documents"]
    )
    
    # Combine results from all sources
    combined_context = []
    for result in search_results:
        if result.success:
            combined_context.extend(result.data)
    
    # Generate response using unified context
    response = chat(f"""
    Based on memory and storage context: {combined_context}
    
    User query: {user_query}
    
    Provide a comprehensive response using all available information.
    """)
    
    # Store interaction in both memory and external storage
    await unified_data.store("memory:episodic", {
        "user_query": user_query,
        "agent_response": response,
        "context_sources": len(search_results)
    })
    
    await unified_data.store("postgres:conversations", {
        "agent_id": "unified_agent",
        "query": user_query,
        "response": response,
        "timestamp": datetime.now()
    })
    
    return {"response": response, "context_sources": len(combined_context)}
```

### Memory-Storage Adapter

```python
from praval.storage import MemoryStorageAdapter

# Use memory system as storage provider
memory_adapter = MemoryStorageAdapter(memory_manager, "agent_id")

# Store memory through storage interface
result = await memory_adapter.store_memory_as_data(
    memory_type="episodic",
    content="Important conversation context",
    metadata={"session": "user_123"},
    importance=0.8
)

# Retrieve memory through storage interface
memory_result = await memory_adapter.retrieve_memory_as_data(
    memory_id="memory_123",
    include_embedding=True
)

# Search memory through storage interface  
search_result = await memory_adapter.search_memory_as_data(
    query="conversation context",
    memory_types=[MemoryType.EPISODIC],
    limit=5
)
```

## Production Examples

### Complete Business Intelligence System

```python
# examples/unified_storage_demo.py - Production-ready example
from praval import agent, chat, broadcast, start_agents
from praval.storage import storage_enabled, get_data_manager

@storage_enabled(["filesystem", "redis", "qdrant"])
@agent("data_collector", responds_to=["collect_data"])
def data_collector_agent(spore, storage):
    """Collects and stores data across multiple storage backends."""
    
    # Sample business data
    customer_data = {
        "customers": [
            {"id": 1, "name": "Acme Corp", "revenue": 1500000, "industry": "Technology"},
            {"id": 2, "name": "Global Systems", "revenue": 2300000, "industry": "Finance"}
        ]
    }
    
    # Store in filesystem for structured access
    customer_result = asyncio.run(storage.store("filesystem", "data/customers.json", customer_data))
    
    # Cache in Redis for fast access
    asyncio.run(storage.store("redis", "customers:cache", customer_data, ex=3600))
    
    # Create vector embeddings for semantic search
    customer_embeddings = []
    for customer in customer_data["customers"]:
        embedding = [random.random() for _ in range(384)]  # Mock embedding
        customer_embeddings.append({
            "id": f"customer_{customer['id']}",
            "vector": embedding,
            "payload": customer
        })
    
    # Store in Qdrant for vector search
    vector_result = asyncio.run(storage.store("qdrant", "customers", customer_embeddings))
    
    # Broadcast completion with references
    broadcast({
        "type": "data_collected", 
        "data_references": {
            "customers": customer_result.data_reference.to_uri(),
            "customer_vectors": vector_result.data_reference.to_uri()
        }
    })

@storage_enabled(["redis", "filesystem", "qdrant"])
@agent("business_analyst", responds_to=["data_collected"])
def business_analyst_agent(spore, storage):
    """Analyzes data from multiple storage backends."""
    
    # Resolve data references
    if spore.has_data_references():
        for ref_uri in spore.data_references:
            result = asyncio.run(storage.resolve_data_reference(ref_uri))
            if result.success:
                # Process resolved data
                if "customers" in ref_uri:
                    analysis = analyze_customers(result.data)
                    
                    # Store analysis report
                    report = generate_business_report(analysis)
                    report_result = asyncio.run(
                        storage.store("filesystem", "reports/business_analysis.md", report)
                    )
                    
                    broadcast({
                        "type": "analysis_complete",
                        "report_reference": report_result.data_reference.to_uri()
                    })

# Health monitoring and diagnostics
@storage_enabled(auto_register=True)
@agent("storage_monitor", responds_to=["health_check"])  
async def storage_health_monitor(spore, storage):
    """Monitors storage system health across all providers."""
    
    registry = get_storage_registry()
    
    # Get all registered providers
    providers = registry.list_providers()
    health_status = {}
    
    for provider_name in providers:
        try:
            provider = registry.get_provider(provider_name)
            health = await provider.health_check()
            health_status[provider_name] = health
        except Exception as e:
            health_status[provider_name] = {"status": "error", "error": str(e)}
    
    # Get registry statistics
    registry_info = registry.get_registry_info()
    
    return {
        "provider_health": health_status,
        "registry_stats": registry_info,
        "total_providers": len(providers)
    }
```

### Advanced Usage Patterns

```python
# Smart storage selection
@storage_enabled(auto_register=True)
@agent("smart_storage_agent")
async def smart_storage_demo(spore, storage):
    """Demonstrates smart storage selection."""
    
    data_manager = get_data_manager()
    
    # Different data types auto-select appropriate storage
    test_data = [
        ("Simple text", "Hello, World!"),
        ("Structured data", {"name": "John", "age": 30}),
        ("Large dataset", {"data": [{"id": i} for i in range(1000)]}),
        ("Vector data", {"vector": [0.1, 0.2, 0.3], "metadata": {"type": "embedding"}})
    ]
    
    results = []
    for data_type, data in test_data:
        result = await data_manager.smart_store(data)
        if result.success:
            provider_used = result.data_reference.provider
            results.append(f"{data_type} → {provider_used}")
    
    return {"smart_selections": results}

# Cross-storage operations
@storage_enabled(["postgres", "redis", "s3"])
@agent("cross_storage_coordinator")
async def coordinate_across_storage(spore, storage):
    """Coordinates operations across multiple storage types."""
    
    # Batch operations across different storage types
    operations = [
        {"provider": "postgres", "resource": "user_preferences", "data": {"user_id": 1, "theme": "dark"}},
        {"provider": "redis", "resource": "session:user1", "data": {"active": True, "login_time": datetime.now()}},
        {"provider": "s3", "resource": "avatars/user1.jpg", "data": b"binary_image_data"}
    ]
    
    # Execute batch operations
    batch_results = await storage.batch_store(operations)
    
    successful_operations = sum(1 for result in batch_results if result.success)
    
    return {
        "operations_attempted": len(operations),
        "successful_operations": successful_operations,
        "batch_success_rate": successful_operations / len(operations)
    }
```

### Configuration and Environment Setup

```bash
# Environment variables for auto-registration
export POSTGRES_HOST=localhost
export POSTGRES_DB=praval  
export POSTGRES_USER=praval_user
export POSTGRES_PASSWORD=secure_password

export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_PASSWORD=redis_password

export S3_BUCKET_NAME=praval-storage
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-west-2

export QDRANT_URL=http://localhost:6333
export QDRANT_API_KEY=your_qdrant_key
export QDRANT_COLLECTION_NAME=praval_vectors

export FILESYSTEM_BASE_PATH=/data/praval/storage
```

```python
# Programmatic configuration
from praval.storage import get_storage_registry, get_data_manager

# Configure providers programmatically
registry = get_storage_registry()

# Custom provider configurations
custom_configs = {
    "production_postgres": {
        "host": "prod-db.company.com",
        "database": "enterprise_data",
        "pool_size": 20
    },
    "analytics_redis": {
        "host": "analytics-cache.company.com",
        "database": 1
    }
}

# Initialize with custom configurations
for provider_name, config in custom_configs.items():
    provider_class = get_provider_class(provider_name.split('_')[1])  # extract type
    provider = provider_class(provider_name, config)
    await registry.register_provider(provider)

# Start agents with configured storage
start_agents(
    business_analyst_agent,
    data_collector_agent,
    storage_monitor,
    initial_data={"type": "system_ready"}
)
```

This unified storage system represents a fundamental evolution of Praval from a communication framework to a complete data ecosystem. By following the same design patterns that make Praval agents simple yet powerful, the storage system enables sophisticated data workflows while maintaining the framework's core philosophy of emergent intelligence through specialized collaboration.

---

# PART VII: SECURE SPORES ENTERPRISE EDITION

## Enterprise-Grade Security

**Cryptographic Foundation for Multi-Agent Communications**

Praval v0.6.0 introduces **Secure Spores**, an enterprise-grade messaging system that brings military-level cryptographic security to multi-agent communications. Built on modern cryptographic primitives, Secure Spores ensure that agent communications remain confidential, authenticated, and tamper-proof across distributed networks.

### Cryptographic Architecture

**End-to-End Encryption:**
- **Curve25519**: Elliptic curve key exchange for perfect forward secrecy
- **XSalsa20**: Stream cipher for message content encryption
- **Poly1305**: Message authentication codes for integrity verification

**Digital Signatures:**
- **Ed25519**: Fast, secure digital signatures for message authenticity
- **Message Integrity**: Cryptographic proof that messages haven't been tampered with
- **Non-repudiation**: Agents cannot deny sending authenticated messages

```python
from praval.core.secure_spore import SecureSporeFactory, SporeKeyManager
from praval.core.transport import TransportProtocol, transport_connection

# Initialize secure messaging
key_manager = SporeKeyManager("secure_agent")
secure_factory = SecureSporeFactory(key_manager)

# Create end-to-end encrypted message
async def secure_communication():
    # Get recipient's public keys
    recipient_keys = await get_agent_public_keys("target_agent")
    
    # Create encrypted, authenticated message
    secure_spore = secure_factory.create_secure_spore(
        to_agent="target_agent",
        knowledge={"sensitive_data": "classified_information"},
        spore_type=SporeType.REQUEST,
        priority=10,
        expires_in_seconds=3600,
        recipient_public_keys=recipient_keys
    )
    
    # Transmit over secure transport
    async with transport_connection(TransportProtocol.AMQP, amqp_config) as transport:
        await transport.publish("secure.channel", secure_spore.to_bytes())
```

### Key Management System

**Agent Identity & Key Lifecycle:**

Each agent maintains its own cryptographic identity with automatic key rotation capabilities:

```python
# Agent key initialization
key_manager = SporeKeyManager("production_agent")

# Key information
public_keys = key_manager.get_public_keys()
print(f"Agent public key: {public_keys['public_key'].hex()}")
print(f"Verify key: {public_keys['verify_key'].hex()}")

# Secure key rotation
rotation_result = key_manager.rotate_keys()
print(f"Keys rotated. Old keys archived for verification.")

# Key export for backup
exported_keys = key_manager.export_keys()
backup_secure_storage(exported_keys)  # Store securely

# Key import for recovery
recovered_manager = SporeKeyManager.import_keys("production_agent", exported_keys)
```

**Cryptographic Operations:**

```python
# Encrypt and sign knowledge for specific recipient
recipient_public_key = get_agent_public_key("target_agent")
encrypted_data, nonce, signature = key_manager.encrypt_and_sign(
    knowledge={"confidential": "data"},
    recipient_public_key=recipient_public_key
)

# Decrypt and verify received message
sender_public_key = get_agent_public_key("sender_agent")
sender_verify_key = get_agent_verify_key("sender_agent")

decrypted_knowledge = key_manager.decrypt_and_verify(
    encrypted_data=encrypted_data,
    nonce=nonce,
    signature=signature,
    sender_public_key=sender_public_key,
    sender_verify_key=sender_verify_key
)
```

### Security Features

**Perfect Forward Secrecy:**
- Each message uses ephemeral keys
- Compromise of long-term keys doesn't affect past communications
- Automatic key rotation capabilities

**Message Integrity:**
- Cryptographic proof of message authenticity
- Detection of any tampering attempts
- Replay attack prevention through nonces

**Agent Authentication:**
- Cryptographic proof of sender identity
- Public key infrastructure for agent verification
- Trust chain establishment

## Distributed Messaging Architecture

**Multi-Protocol Transport Layer**

Secure Spores support multiple enterprise messaging protocols, enabling deployment across diverse infrastructure environments:

### AMQP (Advanced Message Queuing Protocol)

**Enterprise Message Brokers:**
- RabbitMQ, Apache Qpid, Azure Service Bus
- Guaranteed message delivery with persistence
- Topic-based routing with wildcard support
- TLS/SSL encryption for transport security

```python
from praval.core.transport import AMQPTransport, TransportProtocol

# AMQP configuration with TLS
amqp_config = {
    'url': 'amqps://production-rabbit:5671/',
    'exchange_name': 'praval.secure.spores',
    'ca_cert': '/certs/ca.pem',
    'client_cert': '/certs/client.pem',
    'client_key': '/certs/client-key.pem',
    'verify_certs': True,
    'prefetch_count': 100
}

# Initialize secure AMQP transport
async with transport_connection(TransportProtocol.AMQP, amqp_config) as transport:
    # Publish encrypted message
    await transport.publish(
        topic="analytics.models.inference",
        message=secure_spore.to_bytes(),
        priority=8,
        ttl=3600
    )
    
    # Subscribe to secure channel
    async def secure_message_handler(encrypted_message):
        secure_spore = SecureSpore.from_bytes(encrypted_message)
        decrypted_knowledge = decrypt_secure_spore(secure_spore)
        await process_secure_knowledge(decrypted_knowledge)
    
    await transport.subscribe("analytics.models.*", secure_message_handler)
```

### MQTT (Message Queuing Telemetry Transport)

**IoT and Edge Computing:**
- Lightweight protocol for resource-constrained environments  
- Quality of Service levels for reliable delivery
- Hierarchical topic structure for organization
- MQTT over TLS (port 8883) for security

```python
# MQTT configuration with TLS
mqtt_config = {
    'host': 'secure-mqtt.company.com',
    'port': 8883,
    'client_id': 'praval-secure-agent-001',
    'username': 'production_user',
    'password': 'secure_password',
    'ca_cert': '/certs/mqtt-ca.pem',
    'client_cert': '/certs/mqtt-client.pem',
    'client_key': '/certs/mqtt-client-key.pem',
    'keepalive': 60
}

# Secure MQTT communication
async with transport_connection(TransportProtocol.MQTT, mqtt_config) as transport:
    # Publish to hierarchical topic
    await transport.publish(
        topic="production/ai/agents/analysis/results",
        message=secure_spore.to_bytes(),
        priority=7  # Maps to QoS level
    )
    
    # Subscribe with wildcards
    await transport.subscribe(
        topic="production/ai/agents/+/commands",
        callback=secure_command_handler
    )
```

### STOMP (Simple Text Oriented Messaging Protocol)

**Enterprise Integration:**
- Simple, interoperable messaging protocol
- Support for Apache ActiveMQ, RabbitMQ
- Transaction support for atomic operations
- Headers for metadata and routing

```python
# STOMP configuration with TLS
stomp_config = {
    'host': 'activemq.enterprise.local',
    'port': 61614,  # STOMP over TLS
    'username': 'praval_system',
    'password': 'enterprise_password',
    'ca_cert': '/certs/enterprise-ca.pem',
    'client_cert': '/certs/praval-client.pem',
    'client_key': '/certs/praval-key.pem'
}

# Secure STOMP messaging
async with transport_connection(TransportProtocol.STOMP, stomp_config) as transport:
    await transport.publish(
        topic="enterprise.ai.processing.results",
        message=secure_spore.to_bytes(),
        priority=9,
        ttl=7200
    )
```

### Transport Abstraction Benefits

**Protocol Independence:**
```python
# Same code works across different transports
async def deploy_secure_agent(transport_protocol, config):
    async with transport_connection(transport_protocol, config) as transport:
        # Identical code for all protocols
        await transport.publish("agents.deployment", secure_spore.to_bytes())
        await transport.subscribe("agents.commands.*", command_handler)

# Deploy on different infrastructure
await deploy_secure_agent(TransportProtocol.AMQP, production_amqp_config)
await deploy_secure_agent(TransportProtocol.MQTT, edge_mqtt_config)  
await deploy_secure_agent(TransportProtocol.STOMP, enterprise_stomp_config)
```

## Multi-Protocol Transport Layer

**Unified Transport Abstraction**

The transport layer provides a consistent interface across different messaging protocols, enabling seamless migration between infrastructure environments:

### Transport Factory Pattern

```python
from praval.core.transport import TransportFactory, TransportProtocol

# Protocol-agnostic transport creation
def create_transport_for_environment(environment):
    if environment == "production":
        return TransportFactory.create_transport(TransportProtocol.AMQP)
    elif environment == "edge":
        return TransportFactory.create_transport(TransportProtocol.MQTT)
    elif environment == "enterprise":
        return TransportFactory.create_transport(TransportProtocol.STOMP)
    
# Custom transport registration
class RedisTransport(MessageTransport):
    """Custom Redis-based transport implementation."""
    
    async def initialize(self, config):
        self.redis_client = await aioredis.create_redis_pool(
            config['redis_url'],
            ssl_context=self._create_tls_context(config)
        )
    
    async def publish(self, topic, message, **kwargs):
        await self.redis_client.publish(f"praval:{topic}", message)
    
    async def subscribe(self, topic, callback):
        channel = await self.redis_client.subscribe(f"praval:{topic}")
        async for message in channel.iter():
            await callback(message.data)

# Register custom transport
TransportFactory.register_transport(TransportProtocol.REDIS, RedisTransport)
```

### TLS/SSL Security by Default

**Mandatory Encryption:**
All transports enforce TLS/SSL encryption by default with comprehensive certificate management:

```python
# TLS configuration example
tls_config = {
    'ca_cert': '/etc/ssl/certs/company-ca.pem',        # Certificate Authority
    'client_cert': '/etc/ssl/certs/praval-client.pem', # Client certificate
    'client_key': '/etc/ssl/private/praval-key.pem',   # Client private key
    'verify_certs': True,                              # Verify server certificates
    'check_hostname': True,                            # Verify hostname matches
    'ssl_version': 'TLSv1.3'                          # Force TLS 1.3
}

# Mutual TLS authentication
mutual_tls_config = {
    **tls_config,
    'require_client_cert': True,  # Mutual authentication
    'crl_check': True            # Certificate revocation list check
}
```

### Performance and Scalability

**Optimized Message Handling:**

```python
# High-throughput configuration
high_performance_config = {
    'connection_pool_size': 20,      # Multiple connections
    'prefetch_count': 1000,          # Batch message processing
    'compression': 'gzip',           # Message compression
    'keepalive': 30,                 # Reduced keepalive for efficiency
    'tcp_nodelay': True,             # Disable Nagle's algorithm
    'buffer_size': 65536            # Larger network buffers
}

# Load balancing across multiple brokers
broker_cluster_config = {
    'brokers': [
        'broker1.company.com:5671',
        'broker2.company.com:5671', 
        'broker3.company.com:5671'
    ],
    'load_balancing': 'round_robin',
    'failover_timeout': 30,
    'reconnect_delay': 5
}
```

## Docker Deployment Infrastructure

**Production-Ready Containerization**

Secure Spores include comprehensive Docker infrastructure for rapid deployment across environments:

### Complete Service Stack

```yaml
# docker-compose.secure.yml
version: '3.8'
services:
  # RabbitMQ with TLS
  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "5671:5671"    # AMQP over TLS
      - "15671:15671"  # Management UI over HTTPS
    environment:
      RABBITMQ_DEFAULT_USER: praval
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
      RABBITMQ_SSL_CACERTFILE: /etc/rabbitmq/certs/ca.pem
      RABBITMQ_SSL_CERTFILE: /etc/rabbitmq/certs/server.pem
      RABBITMQ_SSL_KEYFILE: /etc/rabbitmq/certs/server-key.pem
    volumes:
      - ./docker/rabbitmq/certs:/etc/rabbitmq/certs:ro
      - ./docker/rabbitmq/config:/etc/rabbitmq/conf.d:ro
      - rabbitmq_data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5

  # Mosquitto MQTT with TLS  
  mosquitto:
    image: eclipse-mosquitto:2
    ports:
      - "8883:8883"    # MQTT over TLS
      - "9001:9001"    # WebSocket over TLS
    volumes:
      - ./docker/mosquitto/config:/mosquitto/config:ro
      - ./docker/mosquitto/certs:/mosquitto/certs:ro
      - mosquitto_data:/mosquitto/data
    healthcheck:
      test: ["CMD", "mosquitto_pub", "-h", "localhost", "-p", "1883", "-t", "test", "-m", "test"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ActiveMQ for STOMP
  activemq:
    image: apache/activemq-artemis:latest
    ports:
      - "61614:61614"  # STOMP over TLS
      - "8162:8162"    # Web console over HTTPS
    environment:
      ARTEMIS_USER: praval
      ARTEMIS_PASSWORD: ${ACTIVEMQ_PASSWORD}
    volumes:
      - ./docker/activemq/certs:/var/lib/artemis-instance/etc/certs:ro
      - activemq_data:/var/lib/artemis-instance/data
    healthcheck:
      test: ["CMD", "curl", "-f", "https://localhost:8162/console"]
      interval: 30s
      timeout: 10s
      retries: 5

  # Qdrant for vector storage
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    environment:
      QDRANT__SERVICE__HTTP_PORT: 6333
      QDRANT__SERVICE__GRPC_PORT: 6334
      QDRANT__STORAGE__STORAGE_PATH: /qdrant/storage
    volumes:
      - qdrant_storage:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 30s
      timeout: 10s
      retries: 5

  # Redis for caching and additional transport
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: >
      redis-server 
      --requirepass ${REDIS_PASSWORD}
      --tls-port 6380
      --tls-cert-file /certs/redis.pem
      --tls-key-file /certs/redis-key.pem
      --tls-ca-cert-file /certs/ca.pem
    volumes:
      - ./docker/redis/certs:/certs:ro
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "--tls", "--cert", "/certs/redis.pem", "--key", "/certs/redis-key.pem", "--cacert", "/certs/ca.pem", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5

  # Main Praval application
  praval-secure:
    build:
      context: .
      dockerfile: docker/Dockerfile.secure
    environment:
      # Core configuration
      PRAVAL_LOG_LEVEL: INFO
      PRAVAL_DEFAULT_PROVIDER: openai
      
      # LLM API keys
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      
      # Secure transport configuration
      RABBITMQ_URL: amqps://praval:${RABBITMQ_PASSWORD}@rabbitmq:5671/
      MQTT_HOST: mosquitto
      MQTT_PORT: 8883
      ACTIVEMQ_HOST: activemq
      ACTIVEMQ_PORT: 61614
      
      # Vector storage
      QDRANT_URL: http://qdrant:6333
      
      # Security
      PRAVAL_ENABLE_SECURE_SPORES: true
      PRAVAL_TLS_CERT_DIR: /app/certs
      
    volumes:
      - ./docker/certs:/app/certs:ro
      - ./logs:/app/logs
      - praval_data:/app/data
    depends_on:
      rabbitmq:
        condition: service_healthy
      mosquitto:
        condition: service_healthy
      activemq:
        condition: service_healthy
      qdrant:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

volumes:
  rabbitmq_data:
  mosquitto_data:
  activemq_data:
  qdrant_storage:
  redis_data:
  praval_data:
```

### Certificate Management

**Automatic TLS Certificate Generation:**

```bash
#!/bin/bash
# docker/scripts/generate-certs.sh

# Create certificate authority
openssl genrsa -out ca-key.pem 4096
openssl req -new -x509 -days 365 -key ca-key.pem -sha256 -out ca.pem \
    -subj "/C=US/ST=CA/L=San Francisco/O=Praval/CN=Praval CA"

# Generate server certificates for each service
for service in rabbitmq mosquitto activemq redis; do
    # Generate private key
    openssl genrsa -out ${service}-key.pem 4096
    
    # Generate certificate signing request
    openssl req -subj "/CN=${service}" -sha256 -new \
        -key ${service}-key.pem -out ${service}.csr
    
    # Sign certificate
    openssl x509 -req -days 365 -sha256 \
        -in ${service}.csr -CA ca.pem -CAkey ca-key.pem \
        -out ${service}.pem -CAcreateserial \
        -extensions v3_req \
        -extfile <(echo "subjectAltName=DNS:${service},DNS:localhost,IP:127.0.0.1")
done

# Generate client certificates for Praval
openssl genrsa -out client-key.pem 4096
openssl req -subj "/CN=praval-client" -new \
    -key client-key.pem -out client.csr
openssl x509 -req -days 365 -sha256 \
    -in client.csr -CA ca.pem -CAkey ca-key.pem \
    -out client.pem -CAcreateserial
```

### Secure Deployment Scripts

```bash
#!/bin/bash
# docker/scripts/deploy-secure.sh

# Generate certificates if they don't exist
if [ ! -f "docker/certs/ca.pem" ]; then
    echo "Generating TLS certificates..."
    ./docker/scripts/generate-certs.sh
fi

# Set secure environment variables
export RABBITMQ_PASSWORD=$(openssl rand -base64 32)
export ACTIVEMQ_PASSWORD=$(openssl rand -base64 32)
export REDIS_PASSWORD=$(openssl rand -base64 32)

# Store passwords securely
echo "RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}" >> .env.secure
echo "ACTIVEMQ_PASSWORD=${ACTIVEMQ_PASSWORD}" >> .env.secure
echo "REDIS_PASSWORD=${REDIS_PASSWORD}" >> .env.secure

# Deploy secure stack
docker-compose -f docker-compose.secure.yml up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 30

# Verify deployment
docker-compose -f docker-compose.secure.yml ps
docker-compose -f docker-compose.secure.yml logs praval-secure

echo "Secure Praval deployment complete!"
echo "RabbitMQ Management: https://localhost:15671"
echo "ActiveMQ Console: https://localhost:8162"
echo "Qdrant: http://localhost:6333"
```

### Production Security Configuration

```python
# config/secure_production.py
import os

SECURE_PRAVAL_CONFIG = {
    # Cryptographic settings
    "secure_spores": {
        "enabled": True,
        "key_rotation_interval": 86400,  # 24 hours
        "signature_algorithm": "ed25519",
        "encryption_algorithm": "curve25519_xsalsa20_poly1305",
        "key_backup_enabled": True,
        "key_backup_path": "/secure/backup/keys"
    },
    
    # Transport security
    "transport_security": {
        "enforce_tls": True,
        "min_tls_version": "1.3",
        "verify_certificates": True,
        "certificate_path": "/app/certs",
        "mutual_tls": True,
        "crl_check": True
    },
    
    # Message security
    "message_security": {
        "max_message_size": 10485760,  # 10MB
        "message_retention": 604800,    # 7 days
        "replay_protection": True,
        "rate_limiting": {
            "messages_per_minute": 1000,
            "burst_size": 100
        }
    },
    
    # Audit and compliance
    "audit": {
        "enabled": True,
        "log_all_messages": True,
        "log_path": "/app/logs/audit",
        "retention_days": 2555,  # 7 years
        "encryption_at_rest": True
    },
    
    # Monitoring
    "monitoring": {
        "metrics_enabled": True,
        "health_check_interval": 30,
        "performance_monitoring": True,
        "security_alerts": True
    }
}
```

### Secure Agent Deployment Example

```python
#!/usr/bin/env python3
# examples/secure_production_deployment.py

import asyncio
import os
from datetime import datetime, timedelta

from praval import agent, chat, start_agents
from praval.core.secure_spore import SecureSporeFactory, SporeKeyManager
from praval.core.transport import TransportProtocol, transport_connection

# Initialize secure environment
async def initialize_secure_environment():
    """Initialize production secure environment."""
    
    # Load environment configuration
    config = load_secure_config()
    
    # Initialize agent key managers
    agent_keys = {
        'analyzer': SporeKeyManager('secure_analyzer'),
        'processor': SporeKeyManager('secure_processor'), 
        'monitor': SporeKeyManager('secure_monitor')
    }
    
    # Create secure factories
    secure_factories = {
        name: SecureSporeFactory(km) 
        for name, km in agent_keys.items()
    }
    
    return config, agent_keys, secure_factories

# Secure production agents
@agent("secure_analyzer", responds_to=["secure_analysis_request"])
async def secure_analyzer(spore):
    """Production agent with enterprise security."""
    
    # Decrypt and verify incoming secure spore
    if hasattr(spore, 'encrypted_knowledge'):
        knowledge = decrypt_secure_spore(spore)
    else:
        knowledge = spore.knowledge
    
    analysis_request = knowledge.get("request")
    requester = knowledge.get("requester")
    
    # Perform secure analysis
    analysis_result = await chat(f"""
    Perform secure analysis on: {analysis_request}
    
    Requirements:
    - Classify sensitivity level
    - Identify potential security implications
    - Provide recommendations
    """)
    
    # Create secure response
    secure_factory = get_secure_factory("secure_analyzer")
    recipient_keys = await get_agent_public_keys(requester)
    
    secure_response = secure_factory.create_secure_spore(
        to_agent=requester,
        knowledge={
            "analysis_result": analysis_result,
            "classification": "CONFIDENTIAL",
            "timestamp": datetime.now().isoformat(),
            "analyst": "secure_analyzer"
        },
        spore_type=SporeType.RESPONSE,
        priority=9,
        expires_in_seconds=3600,
        recipient_public_keys=recipient_keys
    )
    
    # Transmit via secure transport
    async with transport_connection(TransportProtocol.AMQP, get_amqp_config()) as transport:
        await transport.publish(
            f"secure.responses.{requester}",
            secure_response.to_bytes(),
            priority=9,
            ttl=3600
        )
    
    # Audit log
    audit_log({
        "action": "secure_analysis_completed",
        "agent": "secure_analyzer",
        "requester": requester,
        "timestamp": datetime.now(),
        "classification": "CONFIDENTIAL"
    })
    
    return {"status": "analysis_complete", "secure": True}

@agent("secure_monitor", responds_to=["security_alert"])
async def security_monitor(spore):
    """Security monitoring and incident response agent."""
    
    alert = spore.knowledge.get("alert")
    severity = spore.knowledge.get("severity", "medium")
    source = spore.knowledge.get("source")
    
    # Analyze security event
    security_analysis = await chat(f"""
    Security Alert Analysis:
    Alert: {alert}
    Severity: {severity}
    Source: {source}
    
    Provide:
    1. Threat assessment
    2. Recommended actions
    3. Escalation requirements
    """)
    
    # Immediate response for high severity
    if severity == "high":
        await initiate_incident_response(alert, security_analysis)
    
    # Log security event
    security_log({
        "alert": alert,
        "severity": severity,
        "source": source,
        "analysis": security_analysis,
        "timestamp": datetime.now(),
        "response_time": calculate_response_time()
    })
    
    return {"security_analysis": security_analysis, "severity": severity}

# Production deployment
async def deploy_secure_production():
    """Deploy secure agent system in production."""
    
    print("🔒 Initializing Secure Praval Production Environment")
    
    # Initialize secure environment
    config, agent_keys, secure_factories = await initialize_secure_environment()
    
    # Start secure transport connections
    transport_tasks = []
    for protocol in [TransportProtocol.AMQP, TransportProtocol.MQTT]:
        task = asyncio.create_task(
            maintain_secure_transport(protocol, config[protocol.value])
        )
        transport_tasks.append(task)
    
    # Start secure agents
    await start_agents(
        secure_analyzer,
        secure_monitor,
        initial_data={
            "type": "system_initialized",
            "security_level": "production",
            "encryption": "enabled"
        }
    )
    
    print("✅ Secure Praval production environment active")
    
    # Monitor system health
    await monitor_secure_system()

if __name__ == "__main__":
    asyncio.run(deploy_secure_production())
```

This comprehensive secure infrastructure provides enterprise-grade security for multi-agent systems with:

- **Military-grade encryption** for all communications
- **Multi-protocol support** for diverse infrastructure
- **Automatic certificate management** for TLS/SSL
- **Production-ready containerization** with Docker
- **Complete audit trails** for compliance
- **High availability** through service redundancy
- **Performance optimization** for scale

The Secure Spores system transforms Praval from a development framework into an enterprise-ready platform capable of handling the most sensitive multi-agent communications in production environments.

---

# PART V: VERSION 0.6.0 NEW FEATURES

Praval v0.6.0 represents a major milestone in multi-agent AI development, introducing comprehensive memory capabilities, production-ready testing, enhanced agent intelligence, and critical bug fixes for multi-agent communication.

## Comprehensive Memory System

### Multi-Layered Memory Architecture

Praval v0.5.0 introduces a sophisticated memory system that enables agents to:
- **Remember** conversations and interactions across sessions
- **Learn** from experiences over time
- **Store** knowledge persistently with semantic search
- **Retrieve** relevant information contextually
- **Scale** to millions of memories with production-grade performance

```python
@agent("learning_agent", memory=True, responds_to=["learn"])
def memory_enabled_agent(spore):
    """I learn and remember from every interaction."""
    topic = spore.knowledge.get("topic")
    
    # Remember this interaction
    memory_id = memory_enabled_agent.remember(
        f"Learned about {topic}",
        importance=0.8
    )
    
    # Recall related knowledge
    related = memory_enabled_agent.recall(topic, limit=5)
    
    return {"learned": topic, "recalled": len(related)}
```

## Production-Ready Testing

### Comprehensive Test Coverage

Version 0.5.0 achieves exceptional test coverage across core components:

- **Decorators**: 99% coverage (4,750+ lines of tests)
- **Composition**: 100% coverage (comprehensive workflow testing)
- **Memory Manager**: 96% coverage (multi-backend validation)
- **Core Framework**: Extensive validation across all modules

### Enhanced Agent Capabilities

Agents in v0.5.0 feature advanced communication with lightweight knowledge references and dynamic memory management:

```python
# Lightweight knowledge sharing
spore_id = agent.send_lightweight_knowledge(
    to_agent="analyzer",
    large_content="...extensive research data...",
    summary="Market research findings"
)

# Knowledge base integration
@agent("researcher", memory=True, knowledge_base="/docs/research")
def knowledge_agent(spore):
    """I have access to comprehensive knowledge."""
    relevant = knowledge_agent.recall("quantum computing")
    return process_knowledge(relevant)

## Multi-Agent Communication Bug Fix

### Critical Issue Resolution

**Problem Identified:**
In Praval v0.5.0, a fundamental communication bug prevented multi-agent systems from working correctly. Only the first agent in a multi-agent example would respond, while subsequent agents remained silent despite receiving broadcast messages.

**Root Cause Analysis:**
The issue was located in `src/praval/decorators.py`:

1. **Channel Subscription Problem**: Agents were only subscribed to their private channels (e.g., `questioner_channel`, `responder_channel`)
2. **Broadcast Default Problem**: The `broadcast()` function defaulted to using the sender's private channel instead of a shared channel
3. **Communication Isolation**: Agents couldn't receive messages from other agents because they weren't listening on the sender's private channel

**The Fix:**
Two critical changes resolved the communication issue:

```python
# Before (Broken Communication)
underlying_agent.subscribe_to_channel(channel)  # Only private channel

def broadcast(data, channel=None, target_agent=None):
    target_channel = channel or _agent_context.channel  # Private channel default

# After (Fixed Communication)  
underlying_agent.subscribe_to_channel(channel)       # Private channel
underlying_agent.subscribe_to_channel("main")        # ADDED: Main channel subscription

def broadcast(data, channel=None, target_agent=None):
    target_channel = channel or "main"  # CHANGED: Main channel default
```

### Impact and Resolution

**Before the Fix:**
```python
@agent("questioner", responds_to=["start_conversation"])
def ask_questions(spore):
    broadcast({"type": "question_asked", "question": "What is AI?"})
    # This would broadcast on "questioner_channel" 

@agent("answerer", responds_to=["question_asked"]) 
def provide_answers(spore):
    # This agent subscribed only to "answerer_channel"
    # It would NEVER receive the question_asked message
    # Result: Silent failure, no response
    pass
```

**After the Fix:**
```python
@agent("questioner", responds_to=["start_conversation"])
def ask_questions(spore):
    broadcast({"type": "question_asked", "question": "What is AI?"})
    # This now broadcasts on "main" channel by default

@agent("answerer", responds_to=["question_asked"])
def provide_answers(spore):
    # This agent now subscribes to BOTH "answerer_channel" AND "main" 
    # It receives the question_asked message successfully
    # Result: Proper multi-agent collaboration
    pass
```

### Testing and Validation

**Comprehensive Example Testing:**
All examples (002-009) were updated and validated:

```python
# Added timing coordination to all examples
import time

@agent("questioner", responds_to=["start_conversation"])
def ask_questions(spore):
    question = chat("Ask an interesting question")
    broadcast({"type": "question_asked", "question": question})

@agent("answerer", responds_to=["question_asked"])
def provide_answers(spore):
    question = spore.knowledge.get("question")
    answer = chat(f"Answer: {question}")
    broadcast({"type": "answer_provided", "answer": answer})

# Fixed startup with timing
start_agents(ask_questions, provide_answers)
time.sleep(2)  # Allow async communication to complete
```

**Installation Fix:**
A critical discovery was made: changes weren't taking effect because the virtual environment was using an installed package version rather than the local development version.

```bash
# The problem
pip list | grep praval
# praval    0.5.0    # Old installed version was being used

# The solution  
pip install -e .     # Install in development/editable mode
# Now local changes take effect immediately
```

### Release Process

**Version 0.6.1 Release:**
- **Version bumped** in `pyproject.toml` and `__init__.py`
- **All examples fixed** with proper timing coordination
- **Comprehensive testing** across all multi-agent scenarios
- **Development installation** documented for contributors
- **Release notes** created documenting the critical fix

```python
# src/praval/__init__.py
__version__ = "0.6.1"
__doc__ = """
Praval v0.6.0: Multi-Agent AI Framework

🐛 CRITICAL BUG FIX: Multi-agent communication now works correctly
🧠 Comprehensive memory system with Qdrant integration  
🏗️ Production-ready testing and deployment
🚀 Enhanced agent capabilities and performance
"""
```

### Lessons Learned

**Development Best Practices:**
1. **Always use editable installs** for development: `pip install -e .`
2. **Test multi-agent interactions** in all examples
3. **Verify communication patterns** across different agent types
4. **Include timing considerations** for asynchronous operations
5. **Document critical fixes** thoroughly for users

**Communication Architecture Insights:**
1. **Shared channels are essential** for multi-agent collaboration
2. **Default behavior should favor collaboration** over isolation
3. **Agent subscription patterns** must support both private and shared messaging
4. **Broadcast defaults** should enable rather than hinder communication

This bug fix was fundamental to Praval's core functionality. Without it, the framework's primary value proposition - multi-agent collaboration - was broken. The fix ensures that all agents can communicate naturally through the reef system, enabling the emergent intelligence that makes Praval powerful.

**Impact:** This fix transformed Praval from a single-agent framework with broken multi-agent features into a truly collaborative multi-agent platform where agents can work together seamlessly.
```

---

# PART VI: ADVANCED TOPICS

## Production Deployment

### Docker Deployment

**Complete Production Stack**
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_storage:/qdrant/storage
    environment:
      QDRANT__SERVICE__HTTP_PORT: 6333
    restart: unless-stopped
  
  praval-app:
    build: .
    environment:
      - QDRANT_URL=http://qdrant:6333
      - PRAVAL_LOG_LEVEL=INFO
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      - qdrant
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
  
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: praval
      POSTGRES_USER: praval
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  qdrant_storage:
  postgres_data:
```

**Production Configuration**
```python
# config/production.py
import os

PRAVAL_CONFIG = {
    # Core settings
    "default_provider": "openai",
    "default_model": "gpt-4-turbo",
    "max_concurrent_agents": 20,
    "log_level": "INFO",
    
    # Memory settings
    "memory_config": {
        "qdrant_url": os.getenv("QDRANT_URL", "http://qdrant:6333"),
        "collection_name": os.getenv("PRAVAL_COLLECTION_NAME", "production_memories"),
        "short_term_max_entries": 5000,
        "short_term_retention_hours": 48
    },
    
    # Reef settings
    "reef_config": {
        "channel_capacity": 10000,
        "message_ttl": 7200,
        "cleanup_interval": 3600
    },
    
    # Performance settings
    "performance": {
        "enable_caching": True,
        "cache_ttl": 3600,
        "max_retries": 3,
        "timeout": 30
    }
}
```

### Scaling and Load Balancing

```python
from praval import agent, start_agents
from concurrent.futures import ThreadPoolExecutor
import asyncio

# Scalable agent pattern
@agent("scalable_processor", responds_to=["process_batch"])
def scalable_processor(spore):
    """Agent designed for high-throughput processing."""
    batch_data = spore.knowledge.get("batch", [])
    batch_id = spore.knowledge.get("batch_id")
    
    print(f"📦 Processing batch {batch_id} with {len(batch_data)} items")
    
    # Process batch efficiently
    results = []
    for item in batch_data:
        result = process_single_item(item)
        results.append(result)
    
    broadcast({
        "type": "batch_processed",
        "batch_id": batch_id,
        "results": results,
        "processed_count": len(results)
    })
    
    return {"batch_id": batch_id, "processed": len(results)}

# Load balancer for multiple agent instances
class AgentLoadBalancer:
    def __init__(self, agent_instances=5):
        self.executor = ThreadPoolExecutor(max_workers=agent_instances)
        self.active_batches = {}
    
    def distribute_load(self, large_dataset):
        """Distribute large dataset across multiple agent instances."""
        batch_size = len(large_dataset) // 5  # 5 parallel batches
        batches = [
            large_dataset[i:i + batch_size] 
            for i in range(0, len(large_dataset), batch_size)
        ]
        
        futures = []
        for i, batch in enumerate(batches):
            future = self.executor.submit(
                self.process_batch, batch, f"batch_{i}"
            )
            futures.append(future)
        
        # Collect results
        all_results = []
        for future in futures:
            batch_results = future.result()
            all_results.extend(batch_results)
        
        return all_results
    
    def process_batch(self, batch, batch_id):
        """Process individual batch."""
        start_agents(
            scalable_processor,
            initial_data={
                "type": "process_batch",
                "batch": batch,
                "batch_id": batch_id
            }
        )
        return batch  # Simplified return
```

### Monitoring and Observability

```python
import logging
import time
from functools import wraps

# Performance monitoring decorator
def monitor_agent_performance(func):
    """Decorator to monitor agent performance."""
    @wraps(func)
    def wrapper(spore):
        start_time = time.time()
        agent_name = func.__name__
        
        try:
            result = func(spore)
            execution_time = time.time() - start_time
            
            # Log performance metrics
            logging.info(f"Agent {agent_name} executed in {execution_time:.2f}s")
            
            # Store metrics for monitoring
            broadcast({
                "type": "agent_metrics",
                "agent_name": agent_name,
                "execution_time": execution_time,
                "status": "success",
                "timestamp": time.time()
            })
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logging.error(f"Agent {agent_name} failed after {execution_time:.2f}s: {e}")
            
            broadcast({
                "type": "agent_metrics",
                "agent_name": agent_name,
                "execution_time": execution_time,
                "status": "error",
                "error": str(e),
                "timestamp": time.time()
            })
            
            raise
    
    return wrapper

# Monitored agent
@agent("monitored_agent", responds_to=["monitored_task"])
@monitor_agent_performance
def monitored_agent(spore):
    """Agent with performance monitoring."""
    # Simulate work
    time.sleep(1)
    return {"result": "completed"}

# Metrics collector
@agent("metrics_collector", responds_to=["agent_metrics"])
def collect_metrics(spore):
    """Collects and analyzes agent performance metrics."""
    metrics = spore.knowledge
    
    agent_name = metrics.get("agent_name")
    execution_time = metrics.get("execution_time")
    status = metrics.get("status")
    
    # Store metrics (in production, use proper metrics store)
    print(f"📊 {agent_name}: {execution_time:.2f}s ({status})")
    
    # Alert on performance issues
    if execution_time > 5.0:
        print(f"⚠️ Slow performance alert: {agent_name} took {execution_time:.2f}s")
    
    if status == "error":
        print(f"🚨 Error alert: {agent_name} failed - {metrics.get('error')}")
```

## Performance Optimization

### Caching Strategies

```python
from functools import lru_cache
import hashlib
import json

# Response caching for expensive operations
class AgentCache:
    def __init__(self, max_size=1000, ttl=3600):
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl
    
    def get_cache_key(self, spore):
        """Generate cache key from spore content."""
        content = json.dumps(spore.knowledge, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, key):
        """Get cached result if available and not expired."""
        if key in self.cache:
            result, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return result
            else:
                del self.cache[key]
        return None
    
    def set(self, key, value):
        """Store result in cache."""
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            oldest_key = min(self.cache.keys(), 
                           key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        
        self.cache[key] = (value, time.time())

# Global cache instance
agent_cache = AgentCache()

# Cached agent decorator
def cached_agent(cache_duration=3600):
    """Decorator to add caching to agents."""
    def decorator(agent_func):
        @wraps(agent_func)
        def wrapper(spore):
            cache_key = agent_cache.get_cache_key(spore)
            
            # Try to get from cache
            cached_result = agent_cache.get(cache_key)
            if cached_result is not None:
                print(f"💾 Cache hit for {agent_func.__name__}")
                return cached_result
            
            # Execute agent function
            result = agent_func(spore)
            
            # Store in cache
            agent_cache.set(cache_key, result)
            print(f"💾 Cached result for {agent_func.__name__}")
            
            return result
        return wrapper
    return decorator

# Usage
@agent("expensive_analyzer", responds_to=["complex_analysis"])
@cached_agent(cache_duration=1800)  # 30 minute cache
def expensive_analyzer(spore):
    """Agent with expensive operations that benefits from caching."""
    data = spore.knowledge.get("data")
    
    # Simulate expensive operation
    time.sleep(2)  # Expensive computation
    
    analysis = chat(f"Perform complex analysis on: {data}")
    return {"analysis": analysis}
```

### Asynchronous Processing

```python
import asyncio
from praval import achat

# Async agent for concurrent operations
@agent("async_processor", responds_to=["async_task"])
async def async_processor(spore):
    """Asynchronous agent for concurrent processing."""
    tasks = spore.knowledge.get("tasks", [])
    
    # Process tasks concurrently
    async def process_single_task(task):
        result = await achat(f"Process task: {task}")
        return {"task": task, "result": result}
    
    # Execute all tasks concurrently
    results = await asyncio.gather(*[
        process_single_task(task) for task in tasks
    ])
    
    broadcast({
        "type": "async_processing_complete",
        "results": results,
        "task_count": len(results)
    })
    
    return {"processed": len(results), "results": results}

# Batch processor for high throughput
@agent("batch_processor", responds_to=["batch_job"])
def batch_processor(spore):
    """Processes large batches efficiently."""
    items = spore.knowledge.get("items", [])
    batch_size = spore.knowledge.get("batch_size", 10)
    
    results = []
    
    # Process in chunks
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        
        # Process batch
        batch_results = process_batch_efficiently(batch)
        results.extend(batch_results)
        
        # Progress update
        progress = min(i + batch_size, len(items))
        print(f"📊 Processed {progress}/{len(items)} items")
        
        # Yield control occasionally
        if i % (batch_size * 10) == 0:
            time.sleep(0.1)
    
    return {"processed": len(results), "results": results}
```

## Error Handling & Debugging

### Robust Error Handling

```python
from contextlib import contextmanager
import traceback

# Error handling decorator
def resilient_agent(max_retries=3, backoff_delay=1):
    """Decorator to add resilience to agents."""
    def decorator(agent_func):
        @wraps(agent_func)
        def wrapper(spore):
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    return agent_func(spore)
                
                except Exception as e:
                    last_error = e
                    
                    if attempt < max_retries - 1:
                        delay = backoff_delay * (2 ** attempt)  # Exponential backoff
                        print(f"⚠️ Agent {agent_func.__name__} failed (attempt {attempt + 1}), retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        print(f"❌ Agent {agent_func.__name__} failed after {max_retries} attempts")
                        
                        # Broadcast error for handling
                        broadcast({
                            "type": "agent_error",
                            "agent_name": agent_func.__name__,
                            "error": str(e),
                            "attempts": max_retries,
                            "spore_data": spore.knowledge
                        })
                        
                        raise
            
            return None
        return wrapper
    return decorator

# Error recovery agent
@agent("error_handler", responds_to=["agent_error"])
def handle_agent_errors(spore):
    """Handles errors from other agents."""
    agent_name = spore.knowledge.get("agent_name")
    error = spore.knowledge.get("error")
    attempts = spore.knowledge.get("attempts")
    original_data = spore.knowledge.get("spore_data", {})
    
    print(f"🚨 Handling error from {agent_name}: {error}")
    
    # Log error details
    logging.error(f"Agent {agent_name} failed after {attempts} attempts: {error}")
    
    # Attempt recovery strategies
    recovery_strategies = [
        "retry_with_simplified_data",
        "delegate_to_backup_agent", 
        "use_fallback_response",
        "manual_intervention_required"
    ]
    
    recovery_action = chat(f"""
    An agent failed with this error: {error}
    
    Original data: {original_data}
    
    What recovery strategy would be most appropriate:
    {', '.join(recovery_strategies)}
    
    Respond with just the strategy name.
    """)
    
    if "retry_with_simplified" in recovery_action:
        # Simplify data and retry
        simplified_data = simplify_data(original_data)
        broadcast({
            "type": "retry_request",
            "target_agent": agent_name,
            "simplified_data": simplified_data
        })
    
    elif "delegate_to_backup" in recovery_action:
        # Find backup agent
        broadcast({
            "type": "backup_request",
            "original_agent": agent_name,
            "data": original_data
        })
    
    elif "fallback_response" in recovery_action:
        # Provide fallback response
        fallback = provide_fallback_response(original_data)
        broadcast({
            "type": "fallback_response",
            "original_agent": agent_name,
            "response": fallback
        })
    
    return {"recovery_action": recovery_action, "error_handled": True}

# Resilient agent example
@agent("resilient_processor", responds_to=["risky_operation"])
@resilient_agent(max_retries=3, backoff_delay=2)
def risky_processor(spore):
    """Agent that might fail but is resilient."""
    data = spore.knowledge.get("data")
    
    # Simulate occasional failures
    import random
    if random.random() < 0.3:  # 30% failure rate
        raise ValueError("Simulated processing error")
    
    result = chat(f"Process this carefully: {data}")
    return {"result": result, "status": "success"}
```

### Debug Mode and Logging

```python
import logging
from datetime import datetime

# Debug configuration
DEBUG_MODE = os.getenv("PRAVAL_DEBUG", "false").lower() == "true"

if DEBUG_MODE:
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('praval_debug.log'),
            logging.StreamHandler()
        ]
    )

# Debug decorator
def debug_agent(func):
    """Decorator to add detailed debugging to agents."""
    @wraps(func)
    def wrapper(spore):
        if DEBUG_MODE:
            print(f"\n🐛 DEBUG: {func.__name__} started")
            print(f"   Spore ID: {spore.id}")
            print(f"   From: {spore.from_agent}")
            print(f"   Channel: {spore.channel}")
            print(f"   Knowledge: {json.dumps(spore.knowledge, indent=2)}")
        
        start_time = time.time()
        
        try:
            result = func(spore)
            execution_time = time.time() - start_time
            
            if DEBUG_MODE:
                print(f"   ✅ Completed in {execution_time:.3f}s")
                print(f"   Result: {json.dumps(result, indent=2) if result else 'None'}")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            if DEBUG_MODE:
                print(f"   ❌ Failed after {execution_time:.3f}s")
                print(f"   Error: {str(e)}")
                print(f"   Traceback: {traceback.format_exc()}")
            
            raise
    
    return wrapper

# Usage
@agent("debug_example", responds_to=["debug_test"])
@debug_agent
def debug_example(spore):
    """Example agent with debug information."""
    data = spore.knowledge.get("data")
    
    if DEBUG_MODE:
        logging.debug(f"Processing data: {data}")
    
    result = chat(f"Process: {data}")
    
    if DEBUG_MODE:
        logging.debug(f"Generated result: {result}")
    
    return {"result": result}

# System health check
@agent("health_monitor", responds_to=["health_check"])
def system_health_check(spore):
    """Monitors system health and reports status."""
    
    health_report = {
        "timestamp": datetime.now().isoformat(),
        "components": {}
    }
    
    # Check memory system
    try:
        memory_stats = memory.get_memory_stats()
        health_report["components"]["memory"] = {
            "status": "healthy",
            "stats": memory_stats
        }
    except Exception as e:
        health_report["components"]["memory"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Check reef system
    try:
        reef = get_reef()
        reef_health = reef.health_check()
        health_report["components"]["reef"] = {
            "status": "healthy" if reef_health else "warning",
            "details": reef_health
        }
    except Exception as e:
        health_report["components"]["reef"] = {
            "status": "error", 
            "error": str(e)
        }
    
    # Check providers
    providers_health = check_provider_health()
    health_report["components"]["providers"] = providers_health
    
    # Overall health
    component_statuses = [comp["status"] for comp in health_report["components"].values()]
    if "error" in component_statuses:
        health_report["overall_status"] = "error"
    elif "warning" in component_statuses:
        health_report["overall_status"] = "warning"
    else:
        health_report["overall_status"] = "healthy"
    
    print(f"🏥 System Health: {health_report['overall_status']}")
    
    return health_report

def check_provider_health():
    """Check health of LLM providers."""
    providers = ["openai", "anthropic", "cohere"]
    health = {}
    
    for provider in providers:
        try:
            # Simple test call
            test_response = chat("Test", provider=provider)
            health[provider] = {"status": "healthy", "test": "passed"}
        except Exception as e:
            health[provider] = {"status": "error", "error": str(e)}
    
    return health
```

---

# PART VII: API REFERENCE

## Core Functions

### Agent Creation

```python
from praval import Agent, agent

# Class-based agent
agent = Agent(
    name="agent_name",           # Required: unique identifier
    system_message="...",        # LLM system message
    model="gpt-4-turbo",        # Optional: specific model
    provider="openai"           # Optional: specific provider
)

# Decorator-based agent  
@agent(
    name="agent_name",                    # Required: unique identifier
    responds_to=["message_type"],         # Message types to handle
    channel="channel_name",               # Optional: specific channel
    auto_broadcast=True,                  # Auto-broadcast return values
    concurrent=True,                      # Allow concurrent execution
    system_message="You are helpful."    # LLM system message
)
def agent_function(spore):
    pass
```

### Communication Functions

```python
from praval import chat, achat, broadcast, get_agent_info

# Synchronous LLM interaction
response = chat(
    message="Your message here",
    model="gpt-4-turbo",           # Optional: specific model
    provider="openai",             # Optional: specific provider
    temperature=0.7,               # Optional: creativity level
    max_tokens=1000                # Optional: response length limit
)

# Asynchronous LLM interaction
response = await achat(
    message="Your message here",
    model="gpt-4-turbo",
    provider="anthropic"
)

# Broadcasting messages
broadcast(
    data={                         # Message data
        "type": "message_type",
        "content": "message content"
    },
    channel="channel_name",        # Optional: specific channel
    target_agent="agent_name"      # Optional: specific recipient
)

# Get agent information
info = get_agent_info("agent_name")
# Returns: {"name": "agent_name", "status": "active", "last_seen": "..."}
```

### Orchestration Functions

```python
from praval import start_agents, AgentSession
from praval import agent_pipeline, conditional_agent, throttled_agent

# Basic agent startup
start_agents(
    agent1, agent2, agent3,              # Agent functions
    initial_data={"type": "start"},       # Initial trigger data
    channel="main",                       # Optional: default channel
    timeout=60,                          # Optional: execution timeout
    max_iterations=100                   # Optional: max message iterations
)

# Agent session management
session = AgentSession(
    session_id="unique_session_id",      # Optional: custom session ID
    timeout=300,                         # Session timeout
    max_agents=10                        # Maximum concurrent agents
)
session.add_agent(agent_function)
session.start(initial_data={"type": "begin"})
results = session.wait_for_completion()

# Pipeline creation
pipeline = agent_pipeline(
    stage1_agent, stage2_agent, stage3_agent,
    pipeline_id="process_pipeline"
)
results = pipeline.run({"input": "data"})

# Conditional agents
@conditional_agent(
    "conditional_processor",
    condition=lambda spore: spore.knowledge.get("priority") == "high"
)
def high_priority_processor(spore):
    pass

# Throttled agents (rate limiting)
@throttled_agent(
    "throttled_processor", 
    max_calls_per_minute=10
)
def rate_limited_processor(spore):
    pass
```

### Registry Functions

```python
from praval import register_agent, get_registry, get_reef

# Agent registration
register_agent(agent_instance)
register_agent(agent_function, name="custom_name")

# Registry access
registry = get_registry()
agent = registry.get_agent("agent_name")
all_agents = registry.list_agents()
registry.unregister_agent("agent_name")

# Registry information
registry_status = registry.get_status()
# Returns: {"total_agents": 5, "active_agents": 3, "channels": ["main", "analysis"]}

# Reef (communication system) access
reef = get_reef()
reef_stats = reef.get_statistics()
reef.clear_channel("channel_name")
reef.broadcast_to_channel("channel_name", {"message": "data"})
```

## Configuration Options

### Environment Variables

```bash
# Core Framework Settings
PRAVAL_DEFAULT_PROVIDER=openai        # Default LLM provider
PRAVAL_DEFAULT_MODEL=gpt-4-turbo      # Default model
PRAVAL_LOG_LEVEL=INFO                 # Logging level
PRAVAL_MAX_THREADS=10                 # Thread pool size

# LLM Provider API Keys
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key  
COHERE_API_KEY=your_cohere_key

# Memory System Settings
QDRANT_URL=http://localhost:6333      # Qdrant vector database URL
QDRANT_API_KEY=your_qdrant_key        # Optional: Qdrant authentication
PRAVAL_COLLECTION_NAME=memories       # Memory collection name
SHORT_TERM_MAX_ENTRIES=1000           # Short-term memory capacity
SHORT_TERM_RETENTION_HOURS=24         # Short-term memory lifetime

# Reef Communication Settings  
PRAVAL_REEF_CAPACITY=1000             # Message queue capacity
PRAVAL_MESSAGE_TTL=3600               # Message time-to-live (seconds)
PRAVAL_CLEANUP_INTERVAL=1800          # Cleanup interval (seconds)

# Performance Settings
PRAVAL_ENABLE_CACHING=true            # Enable response caching
PRAVAL_CACHE_TTL=3600                 # Cache time-to-live
PRAVAL_MAX_RETRIES=3                  # Maximum retry attempts
PRAVAL_REQUEST_TIMEOUT=30             # Request timeout (seconds)
```

### Programmatic Configuration

```python
from praval import configure
from praval.memory import MemoryManager

# Framework configuration
configure({
    "default_provider": "openai",
    "default_model": "gpt-4-turbo",
    "max_concurrent_agents": 20,
    "log_level": "DEBUG",
    
    "reef_config": {
        "channel_capacity": 5000,
        "message_ttl": 7200,
        "cleanup_interval": 3600,
        "enable_persistence": True
    },
    
    "performance": {
        "enable_caching": True,
        "cache_ttl": 1800,
        "max_retries": 5,
        "timeout": 60,
        "batch_size": 10
    },
    
    "security": {
        "enable_content_filtering": True,
        "max_message_size": 10000,
        "rate_limit_requests": 100
    }
})

# Memory system configuration
memory_config = {
    "qdrant_url": "http://production-qdrant:6333",
    "qdrant_api_key": "your_production_key",
    "collection_name": "production_memories",
    "vector_size": 1536,                    # OpenAI embedding size
    "distance_metric": "cosine",
    "embedding_model": "text-embedding-3-small",
    "short_term_max_entries": 5000,
    "short_term_retention_hours": 48,
    "enable_compression": True,
    "cleanup_interval": 86400               # Daily cleanup
}

memory_manager = MemoryManager(**memory_config)
```

### Provider-Specific Configuration

```python
# OpenAI configuration
openai_config = {
    "api_key": "your_openai_key",
    "organization": "your_org_id",          # Optional
    "base_url": "https://api.openai.com/v1", # Custom endpoint
    "timeout": 60,
    "max_retries": 3,
    "default_model": "gpt-4-turbo",
    "temperature": 0.7,
    "max_tokens": 2000
}

# Anthropic configuration  
anthropic_config = {
    "api_key": "your_anthropic_key",
    "base_url": "https://api.anthropic.com", # Custom endpoint
    "timeout": 60,
    "max_retries": 3,
    "default_model": "claude-3-opus-20240229",
    "max_tokens": 4000
}

# Cohere configuration
cohere_config = {
    "api_key": "your_cohere_key",
    "base_url": "https://api.cohere.ai",    # Custom endpoint
    "timeout": 60,
    "default_model": "command-nightly",
    "temperature": 0.7,
    "max_tokens": 2000
}

# Apply provider configurations
from praval.providers import configure_providers

configure_providers({
    "openai": openai_config,
    "anthropic": anthropic_config,
    "cohere": cohere_config
})
```

## Provider Integration

### Supported Providers

**OpenAI**
```python
# Available models
openai_models = [
    "gpt-4-turbo",
    "gpt-4", 
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-16k"
]

# Usage
response = chat("Hello", provider="openai", model="gpt-4-turbo")
```

**Anthropic Claude**
```python
# Available models
anthropic_models = [
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229", 
    "claude-3-haiku-20240307",
    "claude-2.1",
    "claude-instant-1.2"
]

# Usage
response = chat("Hello", provider="anthropic", model="claude-3-opus-20240229")
```

**Cohere**
```python
# Available models
cohere_models = [
    "command-nightly",
    "command",
    "command-light-nightly",
    "command-light"
]

# Usage
response = chat("Hello", provider="cohere", model="command-nightly")
```

### Custom Provider Integration

```python
from praval.providers import BaseProvider, register_provider

class CustomProvider(BaseProvider):
    """Custom LLM provider implementation."""
    
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url
    
    def chat(self, messages, model=None, **kwargs):
        """Implement chat completion."""
        # Custom provider API call
        response = self._make_request(messages, model, **kwargs)
        return response.get("content", "")
    
    def _make_request(self, messages, model, **kwargs):
        """Make API request to custom provider."""
        import requests
        
        payload = {
            "messages": messages,
            "model": model or "default-model",
            **kwargs
        }
        
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=60
        )
        
        return response.json()
    
    def get_available_models(self):
        """Return list of available models."""
        return ["custom-model-1", "custom-model-2"]

# Register custom provider
custom_provider = CustomProvider(
    api_key="your_custom_key",
    base_url="https://api.customprovider.com"
)

register_provider("custom", custom_provider)

# Use custom provider
response = chat("Hello", provider="custom", model="custom-model-1")
```

### Provider Selection Logic

```python
from praval.providers import get_available_providers, select_best_provider

# Automatic provider selection
available_providers = get_available_providers()
# Returns: ["openai", "anthropic"] based on available API keys

# Smart provider selection
best_provider = select_best_provider(
    task_type="reasoning",           # Task type hint
    required_context_length=8000,    # Context requirements
    preferred_speed="fast",          # Speed preference
    budget_constraints="medium"      # Budget considerations
)

# Provider fallback chain
provider_chain = ["openai", "anthropic", "cohere"]

def robust_chat(message, **kwargs):
    """Chat with automatic provider fallback."""
    last_error = None
    
    for provider in provider_chain:
        try:
            return chat(message, provider=provider, **kwargs)
        except Exception as e:
            last_error = e
            print(f"Provider {provider} failed: {e}")
            continue
    
    raise Exception(f"All providers failed. Last error: {last_error}")
```

---

## Conclusion: The Path Forward

### Beyond Traditional AI Architecture

Praval represents more than a framework—it embodies a **fundamental shift in how we conceive of artificial intelligence**. By embracing the principles of simplicity, specialization, and emergence, we move beyond the limitations of monolithic AI systems toward something more powerful: **collaborative intelligence**.

### The Paradigm Transformation

**From Complexity to Emergence:**
The traditional approach of building increasingly complex, single-purpose AI systems has reached its limits. Praval offers an alternative: **simple agents that become powerful through collaboration**. This isn't just about technical architecture—it's about recognizing that intelligence itself is fundamentally collaborative.

**From Control to Coordination:**
Instead of trying to control every aspect of AI behavior through detailed programming, Praval enables systems that **coordinate naturally** through communication and shared purpose. Agents aren't controlled—they're guided by their identity and enabled to collaborate.

**From Static to Evolutionary:**
Praval systems don't just execute—they **evolve**. New capabilities emerge from agent interactions. New specialists join the ecosystem. The system grows in intelligence and capability over time without fundamental rewrites.

### The Coral Reef Vision Realized

Like the coral reefs that inspired its design, a mature Praval system exhibits:

- **Diversity**: A rich ecosystem of specialized agents, each excellent at their specific role
- **Resilience**: Robust behavior that gracefully handles individual component failures  
- **Adaptation**: The ability to evolve and respond to changing requirements
- **Beauty**: Elegant solutions that emerge from the natural interaction of simple parts
- **Sustainability**: Long-term viability through continuous growth and improvement

### The Developer's Journey

**Start Simple:**
Begin with basic agent interactions. Focus on clean separation of concerns and clear communication protocols. Let the patterns emerge naturally.

**Embrace Emergence:**
Don't try to predict or control every system behavior. Design for emergence—create the conditions where intelligent behavior can naturally arise from agent collaboration.

**Think in Specialists:**
When facing complex problems, resist the urge to create one super-agent. Instead, identify the different types of thinking or expertise needed, and create specialists for each.

**Build for Evolution:**
Design your systems to grow and change. The most successful Praval systems are those that surprise their creators with new capabilities that emerge from agent interactions.

### The Future of Collaborative Intelligence

Praval points toward a future where AI systems are:

- **Understandable**: Built from comprehensible parts with clear relationships
- **Adaptable**: Capable of learning and evolving without complete reconstruction
- **Scalable**: Growing in capability by adding new specialists rather than rebuilding existing ones
- **Resilient**: Robust to individual component failures through distributed intelligence
- **Natural**: Exhibiting behaviors that emerge from collaboration rather than explicit programming

### Final Reflection

The coral reef metaphor isn't just poetic—it's prophetic. Just as coral reefs represent some of the most complex and beautiful ecosystems on Earth, built from the collaboration of simple organisms, Praval systems point toward AI architectures of unprecedented sophistication emerging from the collaboration of simple agents.

**The invitation is simple:** Start building. Start with one agent. Then another. Let them talk to each other. Watch what emerges.

In simplicity lies the ultimate sophistication. In collaboration lies the future of intelligence.

*"The whole is greater than the sum of its parts"* — but only when the parts are designed to work together beautifully.
