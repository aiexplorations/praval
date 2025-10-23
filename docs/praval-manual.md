# Praval: The Complete Manual
## Building Multi-Agent AI Systems from First Principles

<p align="center">
  <img src="logo.png" alt="Praval Logo" width="200"/>
</p>

**Version 0.7.6 | October 2025**

*Praval (प्रवाल) - Sanskrit for coral. Simple organisms, complex ecosystems.*

---

**By Rajesh Sampathkumar ([@aiexplorations](https://github.com/aiexplorations))**

---

## Table of Contents

**PART I: FUNDAMENTALS**
- [Chapter 1: Philosophy & Core Concepts](#chapter-1-philosophy--core-concepts)
- [Chapter 2: Getting Started](#chapter-2-getting-started)
- [Chapter 3: Architecture Deep Dive](#chapter-3-architecture-deep-dive)
- [Chapter 4: Building Multi-Agent Systems](#chapter-4-building-multi-agent-systems)

**PART II: ADVANCED CAPABILITIES**
- [Chapter 5: Memory & Persistence](#chapter-5-memory--persistence)
- [Chapter 6: Tools & Capabilities](#chapter-6-tools--capabilities)
- [Chapter 7: Enterprise Features](#chapter-7-enterprise-features)
- [Chapter 8: Production & Best Practices](#chapter-8-production--best-practices)

**APPENDICES**
- [API Quick Reference](#api-quick-reference)
- [Configuration Guide](#configuration-guide)
- [Troubleshooting](#troubleshooting)

---

# PART I: FUNDAMENTALS

## Chapter 1: Philosophy & Core Concepts

It's 2:47 AM, and I'm staring at an AI agent that's become unmaintainable.

Started simple: 50 lines. Analyze business ideas. But then feature requests: market research, competitive analysis, financial projections, SWOT analysis, PDF reports. Each reasonable alone. Together? 847 lines of complexity, nested conditionals, and debugging by archaeology.

**This is the monolith problem.** And it's not just about code—it's about thinking.

### The Problem with Monoliths

Monolithic agents force you to cram everything into one entity. They're responsible for multiple domains, maintain complex state, make cascading decisions. Your brain can hold ~7 items in working memory. When code exceeds that, you stop understanding and start guessing.

But here's the deeper problem: **monoliths prevent good thinking.** When one agent does everything, you can't think clearly about any one thing. Want to improve research? First untangle it from analysis, business logic, and error handling.

Everything touches everything. Change becomes expensive. Innovation becomes scary.

### What Nature Already Knows

Let me tell you about coral.

A coral polyp is absurdly simple. It filters nutrients and builds calcium carbonate. That's it. No complex decision-making. Just a specialist doing one job.

But thousands of these specialists create reef ecosystems so complex they sustain entire marine biomes. Fish that exist nowhere else. Symbiotic relationships layered infinitely.

**The polyps don't know they're building a reef.** They're doing their thing, broadcasting outputs, consuming inputs. System-level intelligence emerges from interaction, not from individual sophistication.

Now imagine that with AI agents.

Instead of one massive agent trying everything, imagine specialists: A researcher. An analyst. A writer. A curator. Each simple enough to understand completely. Each excellent at their specialty. Together, through clear communication, they create intelligence that feels almost magical.

**That's Praval.**

### Emergence: Intelligence from Collaboration

Praval agents don't orchestrate complexity—they enable emergence.

**Traditional approach**: Central controller calls agent A, then agent B, then agent C. Carefully orchestrated. Tightly coupled. Fragile.

**Praval approach**: Agents defined by identity, not instructions. They broadcast findings. Respond to relevant messages. Coordinate naturally based on message types.

```python
from praval import agent, chat, broadcast, start_agents

@agent("researcher", responds_to=["research_query"])
def research_agent(spore):
    """I find and analyze information."""
    query = spore.knowledge.get("query")
    findings = chat(f"Research this deeply: {query}")

    broadcast({
        "type": "research_complete",
        "findings": findings,
        "confidence": 0.9
    })

    return {"research": findings}


@agent("analyst", responds_to=["research_complete"])
def analyst_agent(spore):
    """I identify patterns and insights."""
    findings = spore.knowledge.get("findings")
    analysis = chat(f"Analyze these findings: {findings}")

    broadcast({
        "type": "analysis_complete",
        "insights": analysis
    })

    return {"analysis": analysis}
```

**Neither agent knows the other exists.** Researcher broadcasts findings. Analyst, configured with `responds_to=["research_complete"]`, activates when that message appears. No central controller. No explicit coupling.

This is emergence: system-level intelligence from agent-level simplicity.

### Identity Over Instruction

Here's a profound shift: Praval agents are defined by **what they are**, not **what they do**.

Traditional: "Step 1: Parse input. Step 2: Call API. Step 3: Format output..." Imperative programming. Brittle. Fails when conditions change.

Praval: "I am a philosopher who thinks deeply about questions." Identity-driven. When encountering new situations, the agent doesn't need new instructions—it acts according to its nature.

```python
@agent("philosopher")
def philosophical_agent(spore):
    """I think deeply about questions, exploring different perspectives."""

    question = spore.knowledge.get("question")
    response = chat(f"""
    You are a philosopher. Consider this from multiple angles: {question}
    Explore existentialist, pragmatic, and stoic perspectives.
    """)

    return {"response": response}
```

That docstring isn't documentation—it's **identity**. It tells the agent what it *is*. This enables robust, adaptive behavior.

### Why This Matters

We're at an interesting moment. LLMs are incredibly capable, but building systems with them often feels like fighting their nature.

Praval works *with* the grain:

**1. Specialization Over Generalization**
Each agent excels at one thing. Better to have five specialists than one generalist.

**2. Declarative Design**
Define identities and communication patterns. Let behavior emerge.

**3. Composability**
Agents combine naturally. Add specialists as needed. System grows organically.

**4. Maintainability**
Each agent is simple enough to understand completely. Changes are localized.

**5. Emergence**
Intelligence arises from collaboration, not from cramming capabilities into ever-larger models.

### The Transformation

Go back to that 847-line monolith. Rewritten with Praval:

- **Interviewer agent** (50 lines): Generates questions
- **Research agent** (40 lines): Gathers market data
- **Analyst agent** (55 lines): Evaluates viability
- **Reporter agent** (45 lines): Creates markdown reports
- **Presenter agent** (35 lines): Generates PDFs

**Total: 225 lines. Each agent understandable. System more capable.**

Not 847 lines reduced to 225. **489 lines reduced to 50 focused lines per specialist.**

This isn't about writing less code—it's about writing *clearer* code. About agents you can hold in your head. About systems that compose naturally.

Simple agents. Powerful emergence. That's Praval.

---

## Chapter 2: Getting Started

Enough philosophy. Let's build something.

### Installation

```bash
pip install praval
```

That's it. No complex setup. No configuration required. Though you'll want an LLM API key:

```bash
export OPENAI_API_KEY="your_key_here"
# or ANTHROPIC_API_KEY, or COHERE_API_KEY
```

Praval auto-selects from available providers. Just set a key and go.

### Your First Agent

Create `first_agent.py`:

```python
from praval import agent, chat, start_agents

@agent("philosopher")
def philosophical_agent(spore):
    """I think deeply about questions."""

    question = spore.knowledge.get("question", "What is the meaning of existence?")

    response = chat(f"""
    You are a philosopher. Consider this question: {question}
    Provide a thoughtful, multi-perspective analysis.
    """)

    print(f"🤔 Philosopher: {response}")

    return {"response": response}


# Start the agent
start_agents(
    philosophical_agent,
    initial_data={"question": "What makes a good life?"}
)
```

Run it:

```bash
python first_agent.py
```

**What just happened:**

1. `@agent("philosopher")` transformed the function into a registered agent
2. `spore` is a message object carrying knowledge between agents
3. `chat()` abstracts LLM calls (works with any provider)
4. `start_agents()` initialized the system and sent initial data
5. Agent received the spore, processed it, returned a result

**This is a complete, functional AI agent.** 15 lines.

### Understanding Spores

Spores are Praval's communication protocol. They're JSON messages carrying structured knowledge:

```python
{
    "id": "unique_identifier",
    "type": "question",
    "knowledge": {
        "question": "What makes a good life?",
        "context": "philosophical_inquiry"
    },
    "from_agent": "user",
    "timestamp": "2025-10-16T14:23:00Z"
}
```

Agents access knowledge via `spore.knowledge.get()`:

```python
question = spore.knowledge.get("question")
context = spore.knowledge.get("context", "default_value")
```

Simple. Structured. Enables clear communication.

### Two Agents: The Moment of Emergence

One agent is useful. Two collaborating is where magic starts.

Add a critic:

```python
from praval import agent, chat, broadcast, start_agents

@agent("philosopher", responds_to=["question"])
def philosophical_agent(spore):
    """I think deeply about questions."""

    question = spore.knowledge.get("question")

    response = chat(f"""
    Consider this philosophically: {question}
    Provide multi-perspective analysis.
    """)

    print(f"🤔 Philosopher: {response}\n")

    # Broadcast findings to other agents
    broadcast({
        "type": "philosophical_analysis",
        "original_question": question,
        "analysis": response
    })

    return {"response": response}


@agent("critic", responds_to=["philosophical_analysis"])
def critical_agent(spore):
    """I examine ideas for assumptions and weaknesses."""

    analysis = spore.knowledge.get("analysis")
    original = spore.knowledge.get("original_question")

    critique = chat(f"""
    Original question: {original}
    Analysis: {analysis}

    What assumptions are being made?
    What perspectives are missing?
    """)

    print(f"🔍 Critic: {critique}\n")

    return {"critique": critique}


# Start both agents
start_agents(
    philosophical_agent,
    critical_agent,
    initial_data={"type": "question", "question": "What makes a good life?"}
)
```

**What's happening:**

1. Philosopher receives question (matches `responds_to=["question"]`)
2. Thinks, generates analysis
3. Broadcasts `philosophical_analysis` message
4. Critic activates (matches `responds_to=["philosophical_analysis"]`)
5. Examines the philosopher's thinking
6. Provides critique

**Neither agent knows the other exists.** They communicate through message types. This is emergent coordination.

### Three Agents: Seeing the Pattern

Add a synthesizer:

```python
@agent("synthesizer", responds_to=["philosophical_analysis", "critique"])
def synthesis_agent(spore):
    """I integrate different perspectives into coherent insights."""

    # Check which messages we've received
    analysis = spore.knowledge.get("analysis", "")
    critique = spore.knowledge.get("critique", "")

    # Wait until we have both (simple approach)
    if not (analysis and critique):
        return {}

    synthesis = chat(f"""
    Given this analysis and critique, what deeper insights emerge?

    Analysis: {analysis}
    Critique: {critique}
    """)

    print(f"💎 Synthesis: {synthesis}\n")

    return {"synthesis": synthesis}
```

Now you have:
- **Philosopher**: Explores ideas broadly
- **Critic**: Examines rigorously
- **Synthesizer**: Integrates perspectives

Three specialists. No orchestration code. Intelligence emerging from their interaction.

### Key Concepts

**`@agent(name)`**: Decorator that registers a function as an agent

**`responds_to`**: List of message types this agent cares about. Agent only activates when these appear.

**`spore.knowledge`**: Dictionary of data in the message

**`broadcast(data)`**: Send a message to all agents (those with matching `responds_to` will activate)

**`chat(prompt)`**: Abstract LLM call, works with any provider

**`start_agents(*agents, initial_data)`**: Initialize system and send initial message

### What You Just Learned

In ~50 lines of code, you've:
- Created independent agents with distinct identities
- Enabled inter-agent communication through spores
- Built emergent coordination (no central controller)
- Watched system-level intelligence arise from simple components

This is the Praval pattern: **simple agents, clear communication, emergent behavior**.

Next chapter: how it actually works under the hood.

---

*See `examples/001_single_agent_identity.py` and `examples/002_agent_communication.py` for complete working examples.*

## Chapter 3: Architecture Deep Dive

Understanding how Praval works under the hood helps you build better systems. But don't worry—the architecture is as simple as the API.

### The Reef: Communication Hub

The Reef is Praval's message queue. It's where spores flow between agents.

```python
from praval import get_reef

reef = get_reef()  # Global singleton

# Reef manages:
# - Message routing
# - Agent subscriptions
# - Message history
# - Channel management
```

When you call `broadcast()`, you're sending a spore to the Reef. The Reef routes it to agents subscribed to that message type.

**Architecture**:

```
User/Agent → broadcast() → Reef → (Message Queue) → Subscribed Agents
```

**Key features**:
- In-process queue (fast, no network overhead)
- Topic-based routing (agents subscribe to message types)
- Message history (optional, for debugging)
- Thread-safe (multiple agents can broadcast simultaneously)

You rarely interact with the Reef directly—`broadcast()` and `responds_to` handle it. But knowing it exists helps understand message flow.

### Spore Protocol

Spores are structured messages. Full structure:

```python
{
    "id": "uuid4-string",
    "type": "message_type",  # e.g., "research_complete"
    "knowledge": {
        # Your data here
        "key": "value",
        "nested": {"data": "allowed"}
    },
    "from_agent": "sender_name",
    "to_agent": None,  # None for broadcast, specific for direct message
    "timestamp": "ISO8601-timestamp",
    "metadata": {
        "priority": 5,  # Optional priority
        "ttl": 3600,    # Time to live in seconds
        # Custom metadata
    }
}
```

Agents receive spores as objects:

```python
@agent("handler")
def handler_agent(spore):
    # Access fields
    message_type = spore.type
    data = spore.knowledge
    sender = spore.from_agent
    timestamp = spore.timestamp

    # Or just get knowledge
    value = spore.knowledge.get("key")
```

**Message types** are strings, typically descriptive:
- `"question"` - User asking something
- `"research_complete"` - Research agent finished
- `"analysis_ready"` - Analyst has insights
- `"error_occurred"` - Something failed

Convention: Use snake_case, be descriptive. These are your communication vocabulary.

### The Registry: Agent Discovery

The Registry tracks all agents:

```python
from praval import get_registry

registry = get_registry()

# What agents exist?
all_agents = registry.list_agents()

# Get specific agent
agent = registry.get_agent("philosopher")

# What does this agent respond to?
subscriptions = agent.responds_to
```

When you use `@agent("name")`, the decorator:
1. Wraps your function
2. Creates Agent metadata
3. Registers in global registry
4. Sets up Reef subscriptions

This enables:
- **Dynamic discovery**: Find agents at runtime
- **Introspection**: See what agents respond to what messages
- **Flexibility**: Add/remove agents dynamically

### How @agent Works

The decorator does several things:

```python
def agent(name, responds_to=None, memory=False):
    def decorator(func):
        # 1. Create Agent instance
        agent_instance = Agent(
            name=name,
            function=func,
            responds_to=responds_to or [],
            memory_enabled=memory
        )

        # 2. Register in global registry
        register_agent(agent_instance)

        # 3. Subscribe to message types in Reef
        if responds_to:
            for message_type in responds_to:
                reef.subscribe(message_type, agent_instance)

        # 4. Return enhanced function
        return agent_instance.execute

    return decorator
```

Your function becomes an Agent with:
- Identity (name)
- Communication patterns (responds_to)
- Execution context (memory, tools, storage)

### Message Filtering

Agents only activate for relevant messages. This happens through `responds_to`:

```python
@agent("researcher", responds_to=["research_query", "followup_needed"])
def researcher(spore):
    # Only called when spore.type in ["research_query", "followup_needed"]
    pass
```

**Without responds_to**, agent receives all messages (rare use case).

**With responds_to**, agent gets filtered messages:

```python
broadcast({"type": "research_query", "query": "..."})
# ✓ researcher activates

broadcast({"type": "analysis_complete", "results": "..."})
# ✗ researcher doesn't activate
```

This prevents agents from processing irrelevant messages, keeping code clean.

### Communication Patterns

**1. Broadcast (one-to-many)**:

```python
broadcast({"type": "event", "data": "value"})
# All agents with responds_to=["event"] receive it
```

**2. Direct message (one-to-one)**:

```python
from praval import get_reef

reef = get_reef()
reef.send_to_agent(
    to_agent="specific_agent",
    knowledge={"request": "data"}
)
```

**3. Request-response**:

```python
# Requester
broadcast({
    "type": "data_request",
    "request_id": "unique_id",
    "query": "..."
})

# Responder
@agent("data_provider", responds_to=["data_request"])
def provider(spore):
    request_id = spore.knowledge.get("request_id")
    result = fetch_data()

    broadcast({
        "type": "data_response",
        "request_id": request_id,
        "data": result
    })
```

**4. Pipeline**:

```python
# Stage 1 → Stage 2 → Stage 3

@agent("stage1", responds_to=["start"])
def stage1(spore):
    result = process_step1()
    broadcast({"type": "step1_complete", "data": result})

@agent("stage2", responds_to=["step1_complete"])
def stage2(spore):
    data = spore.knowledge.get("data")
    result = process_step2(data)
    broadcast({"type": "step2_complete", "data": result})

@agent("stage3", responds_to=["step2_complete"])
def stage3(spore):
    data = spore.knowledge.get("data")
    final = process_step3(data)
    return {"final": final}
```

### Error Handling

Agents should handle errors gracefully:

```python
@agent("resilient_agent")
def resilient_agent(spore):
    """I handle errors without crashing the system."""

    try:
        result = risky_operation()
        broadcast({"type": "success", "result": result})
    except Exception as e:
        # Log error
        print(f"Error in agent: {e}")

        # Broadcast error message
        broadcast({
            "type": "error_occurred",
            "error": str(e),
            "agent": "resilient_agent"
        })

        # Return fallback
        return {"status": "error", "fallback": default_value}
```

Errors in one agent don't crash other agents—they're isolated by design.

### Performance Characteristics

**Message routing**: O(1) lookup for subscribed agents
**Broadcast**: O(n) where n = number of subscribed agents (typically small)
**Memory**: Minimal—just agent metadata and recent message history

Praval is fast. The overhead is negligible compared to LLM calls.

### What You've Learned

The architecture is simple:
- **Reef**: Message queue routing spores
- **Spores**: Structured JSON messages
- **Registry**: Agent metadata and discovery
- **@agent**: Decorator that ties it together
- **responds_to**: Message filtering

Understanding these pieces helps you build more sophisticated systems. But day-to-day, you just use `@agent`, `broadcast`, and `responds_to`.

Architecture serves simplicity, not complexity.

---

*See `examples/004_registry_discovery.py` for advanced registry usage.*

## Chapter 4: Building Multi-Agent Systems

Now that you understand the basics and architecture, let's build real multi-agent systems with practical patterns.

###

 The Specialist Pattern

The most fundamental pattern: each agent excels at one thing.

```python
from praval import agent, chat, broadcast, start_agents

# Extractor: Knows document formats deeply
@agent("extractor", responds_to=["raw_document"])
def document_extractor(spore):
    """I extract and clean content from documents."""
    document = spore.knowledge.get("document")

    # Extract logic (PDF, HTML, etc.)
    cleaned_text = extract_and_clean(document)

    broadcast({
        "type": "extracted_content",
        "text": cleaned_text,
        "source": document
    })

    return {"extracted": cleaned_text}


# Analyzer: Understands semantic analysis
@agent("analyzer", responds_to=["extracted_content"])
def content_analyzer(spore):
    """I analyze content for key themes and concepts."""
    text = spore.knowledge.get("text")

    analysis = chat(f"""
    Analyze this text for key themes, concepts, and insights:
    {text}
    """)

    broadcast({
        "type": "analysis_complete",
        "analysis": analysis,
        "themes": extract_themes(analysis)
    })

    return {"analysis": analysis}


# Reporter: Excels at narrative and formatting
@agent("reporter", responds_to=["analysis_complete"])
def report_generator(spore):
    """I create well-formatted reports."""
    analysis = spore.knowledge.get("analysis")
    themes = spore.knowledge.get("themes")

    report = create_markdown_report(analysis, themes)

    return {"report": report}
```

**Why this works**: Each agent has focused responsibility. You can test them independently. Replace the analyzer without touching extraction or reporting. Swap in better implementations gradually.

### Pipeline Pattern

Sequential processing where each stage builds on the previous:

```python
@agent("stage1", responds_to=["pipeline_start"])
def first_stage(spore):
    data = spore.knowledge.get("input")
    result = process_step_one(data)

    broadcast({"type": "stage1_done", "data": result, "metadata": gather_metadata()})


@agent("stage2", responds_to=["stage1_done"])
def second_stage(spore):
    data = spore.knowledge.get("data")
    metadata = spore.knowledge.get("metadata")

    result = process_step_two(data, metadata)

    broadcast({"type": "stage2_done", "data": result})


@agent("stage3", responds_to=["stage2_done"])
def final_stage(spore):
    data = spore.knowledge.get("data")
    final_result = process_final(data)

    return {"output": final_result}
```

Data flows stage1 → stage2 → stage3. Each stage enriches or transforms.

### Collaborative Decision Pattern

Multiple perspectives before decisions:

```python
@agent("technical_reviewer", responds_to=["proposal"])
def technical_review(spore):
    """I evaluate technical feasibility."""
    proposal = spore.knowledge.get("proposal")

    assessment = chat(f"""
    Technical review of: {proposal}
    Assess feasibility, complexity, technical risks.
    """)

    broadcast({
        "type": "technical_assessment",
        "assessment": assessment,
        "feasibility_score": extract_score(assessment)
    })


@agent("business_reviewer", responds_to=["proposal"])
def business_review(spore):
    """I evaluate business viability."""
    proposal = spore.knowledge.get("proposal")

    assessment = chat(f"""
    Business review of: {proposal}
    Assess market fit, ROI, business risks.
    """)

    broadcast({
        "type": "business_assessment",
        "assessment": assessment,
        "viability_score": extract_score(assessment)
    })


@agent("decision_maker", responds_to=["technical_assessment", "business_assessment"])
def make_decision(spore):
    """I integrate assessments into decisions."""
    # Wait for both assessments
    tech_score = spore.knowledge.get("feasibility_score")
    biz_score = spore.knowledge.get("viability_score")

    if tech_score and biz_score:
        decision = "approve" if (tech_score + biz_score) / 2 > 0.7 else "reject"

        broadcast({
            "type": "decision_made",
            "decision": decision,
            "reasoning": f"Technical: {tech_score}, Business: {biz_score}"
        })

        return {"decision": decision}
```

Multiple perspectives → integrated decision. Better than single-agent assessment.

### Parallel Processing Pattern

Multiple agents working simultaneously:

```python
@agent("analyzer_A", responds_to=["analyze_request"])
def analyzer_a(spore):
    """I use method A for analysis."""
    data = spore.knowledge.get("data")
    result = analyze_with_method_a(data)

    broadcast({"type": "analysis_a_complete", "result": result})


@agent("analyzer_B", responds_to=["analyze_request"])
def analyzer_b(spore):
    """I use method B for analysis."""
    data = spore.knowledge.get("data")
    result = analyze_with_method_b(data)

    broadcast({"type": "analysis_b_complete", "result": result})


@agent("synthesizer", responds_to=["analysis_a_complete", "analysis_b_complete"])
def synthesize_results(spore):
    """I combine multiple analyses."""
    # Collect results from both methods
    result_a = spore.knowledge.get("result")  # From latest message
    # (In production, you'd track both explicitly)

    synthesis = combine_analyses(result_a, result_b)

    return {"synthesis": synthesis}
```

Both analyzers run in parallel on the same request. Synthesizer waits for both.

### Error Handling and Resilience

Agents fail independently without crashing the system:

```python
@agent("processor", responds_to=["task"])
def process_with_fallback(spore):
    """I process tasks with graceful fallback."""

    try:
        result = complex_processing(spore.knowledge)

        broadcast({"type": "processing_complete", "result": result})

    except Exception as e:
        print(f"Error in processor: {e}")

        # Broadcast error
        broadcast({
            "type": "error_occurred",
            "error": str(e),
            "agent": "processor"
        })

        # Use fallback
        fallback = simple_fallback(spore.knowledge)

        broadcast({
            "type": "processing_complete",
            "result": fallback,
            "fallback_used": True
        })


@agent("monitor", responds_to=["error_occurred"])
def error_monitor(spore):
    """I track errors and alert if patterns emerge."""
    error = spore.knowledge.get("error")
    agent_name = spore.knowledge.get("agent")

    track_error(agent_name, error)

    if error_rate_high(agent_name):
        broadcast({
            "type": "alert",
            "message": f"High error rate in {agent_name}"
        })
```

Errors are contained, logged, and monitored. System remains operational.

### State Management

Agents can maintain state (use sparingly):

```python
# Global state (simple approach for single-process)
conversation_state = {}

@agent("stateful_agent")
def stateful_agent(spore):
    """I maintain conversation state."""
    user_id = spore.knowledge.get("user_id")
    message = spore.knowledge.get("message")

    # Get or create user state
    if user_id not in conversation_state:
        conversation_state[user_id] = {"history": [], "preferences": {}}

    state = conversation_state[user_id]
    state["history"].append(message)

    # Use state in response
    response = chat(f"""
    User history: {state['history'][-5:]}
    Current message: {message}

    Provide contextual response.
    """)

    state["history"].append(response)

    return {"response": response}
```

For production, use the memory system (next chapter) instead of global state.

### Dynamic Agent Composition

Add agents at runtime:

```python
from praval import agent, get_registry

def create_specialized_agent(domain, keywords):
    """Factory function to create domain-specific agents."""

    @agent(f"{domain}_specialist", responds_to=keywords)
    def specialist(spore):
        f"""I specialize in {domain}."""
        query = spore.knowledge.get("query")

        response = chat(f"""
        As a {domain} expert, respond to: {query}
        """)

        return {"response": response}

    return specialist

# Create specialists dynamically
finance_agent = create_specialized_agent("finance", ["financial_query"])
legal_agent = create_specialized_agent("legal", ["legal_query"])
technical_agent = create_specialized_agent("technical", ["tech_query"])
```

Agents created and registered at runtime based on needs.

### Best Practices

**1. Single Responsibility**
Each agent does one thing well. Don't create "super agents."

**2. Clear Communication Vocabulary**
Use descriptive message types: `"research_complete"` not `"done"`.

**3. Loose Coupling**
Agents communicate through messages, not direct function calls.

**4. Error Isolation**
Use try/except. Broadcast errors. Don't let one agent crash the system.

**5. Testing**
Test agents independently. Mock spores for unit tests.

```python
def test_analyzer():
    mock_spore = Spore(
        knowledge={"text": "sample text"},
        type="extracted_content"
    )

    result = content_analyzer(mock_spore)

    assert "analysis" in result
```

**6. Observable Behavior**
Log important events. Broadcast status messages. Make agent activity visible.

**7. Gradual Complexity**
Start with 2-3 agents. Add specialists as needed. Let complexity emerge naturally.

### What You've Learned

Multi-agent patterns:
- **Specialist**: One agent, one job
- **Pipeline**: Sequential stages
- **Collaborative**: Multiple perspectives
- **Parallel**: Concurrent processing
- **Error handling**: Graceful degradation
- **State management**: When needed
- **Dynamic composition**: Runtime flexibility

These patterns combine. A real system might use specialists in pipelines with collaborative decision points and parallel processing stages.

The key: start simple, compose naturally, let emergence happen.

---

*See `examples/003_specialist_collaboration.py` and `examples/006_resilient_agents.py` for complete patterns.*

---

# PART II: ADVANCED CAPABILITIES

## Chapter 5: Memory & Persistence

Stateless agents are limited. Memory transforms them into learning systems.

### Why Memory Matters

Without memory, every conversation starts from zero. The agent doesn't remember:
- Previous conversations
- User preferences
- Successful patterns
- Domain knowledge accumulated over time

**Memory enables**:
- **Continuity**: Building on past conversations
- **Personalization**: Adapting to user patterns
- **Learning**: Recognizing what works
- **Expertise**: Accumulating domain knowledge

### The Four Memory Types

Praval implements four memory layers, mirroring human cognition:

**1. Short-Term Memory (Working Memory)**
- Fast, in-process storage
- ~1,000 entries, 24-hour retention
- Current conversation context
- Temporary state

**2. Long-Term Memory (Persistent Storage)**
- Qdrant vector database
- Millions of entries, permanent
- Semantic search via embeddings
- Important discoveries and patterns

**3. Episodic Memory (Experience Timeline)**
- Conversation history
- User interactions chronologically
- Learning from experiences
- Relationship context

**4. Semantic Memory (Knowledge Base)**
- Facts and concepts
- Domain expertise
- Concept relationships
- Confidence-scored knowledge

### Basic Usage

```python
from praval import agent, chat
from praval.memory import MemoryManager, MemoryType, MemoryQuery

# Initialize memory system
memory = MemoryManager(
    qdrant_url="http://localhost:6333",
    collection_name="agent_memories"
)

@agent("remembering_agent")
def memory_enabled_agent(spore):
    """I remember our conversations and learn over time."""

    query = spore.knowledge.get("query")
    agent_id = "remembering_agent"

    # Search relevant past memories
    relevant = memory.search_memories(MemoryQuery(
        query_text=query,
        agent_id=agent_id,
        memory_types=[MemoryType.LONG_TERM],
        limit=3
    ))

    # Get recent conversation
    recent = memory.get_conversation_context(
        agent_id=agent_id,
        turns=5
    )

    # Build context from memory
    memory_context = "\n".join([m.content for m in relevant.entries])

    # Generate response using memory
    response = chat(f"""
    Based on our history: {memory_context}
    Recent conversation: {recent}

    Current query: {query}

    Provide a response that builds on our shared context.
    """)

    # Store this interaction
    memory.store_conversation_turn(
        agent_id=agent_id,
        user_message=query,
        agent_response=response
    )

    # Store important insights
    if is_important(response):
        memory.store_memory(
            agent_id=agent_id,
            content=f"Q: {query} | A: {response[:200]}...",
            memory_type=MemoryType.LONG_TERM,
            importance=0.85
        )

    return {"response": response}
```

### Memory Storage

**Short-term** (fast, temporary):

```python
memory.store_memory(
    agent_id="analyst",
    content="User prefers Python examples",
    memory_type=MemoryType.SHORT_TERM,
    importance=0.7
)
```

**Long-term** (persistent, searchable):

```python
memory.store_memory(
    agent_id="analyst",
    content="Database performance issues resolved with indexing on user_events table",
    memory_type=MemoryType.LONG_TERM,
    importance=0.9,
    metadata={"domain": "performance", "solution": "indexing"}
)
```

**Conversation** (episodic):

```python
memory.store_conversation_turn(
    agent_id="chatbot",
    user_message="How do I optimize queries?",
    agent_response="Focus on indexing and use EXPLAIN...",
    metadata={"topic": "database", "satisfaction": "positive"}
)
```

**Knowledge** (semantic):

```python
memory.store_knowledge(
    agent_id="expert",
    knowledge="Praval agents communicate via spores",
    domain="praval_framework",
    confidence=0.95,
    metadata={"concept": "spores"}
)
```

### Memory Retrieval

**Semantic search** (finds similar meanings):

```python
results = memory.search_memories(MemoryQuery(
    query_text="database performance problems",
    agent_id="analyst",
    memory_types=[MemoryType.LONG_TERM],
    limit=5,
    similarity_threshold=0.7
))

for entry in results.entries:
    print(f"{entry.content} (similarity: {entry.similarity_score})")
```

Searches semantically—"database performance" finds memories about "indexing issues" even without exact matches.

**Conversation context**:

```python
context = memory.get_conversation_context(
    agent_id="chatbot",
    turns=10  # Last 10 turns
)

for turn in context:
    data = turn.metadata.get("conversation_data", {})
    print(f"User: {data.get('user_message')}")
    print(f"Agent: {data.get('agent_response')}")
```

**Domain knowledge**:

```python
knowledge = memory.get_domain_knowledge(
    agent_id="expert",
    domain="databases",
    limit=20
)
```

### Memory Configuration

```python
memory = MemoryManager(
    # Qdrant for vector storage
    qdrant_url="http://localhost:6333",
    collection_name="my_memories",

    # Short-term settings
    short_term_max_entries=2000,
    short_term_retention_hours=48,

    # Embedding model for semantic search
    embedding_model="sentence-transformers/all-MiniLM-L6-v2"
)
```

### Memory in Multi-Agent Systems

Agents can share memories:

```python
# Agent A stores discovery
memory.store_memory(
    agent_id="shared_knowledge",  # Shared ID
    content="Customer churn correlates with slow response times",
    memory_type=MemoryType.SEMANTIC,
    importance=0.9
)

# Agent B retrieves shared knowledge
knowledge = memory.search_memories(MemoryQuery(
    query_text="customer retention patterns",
    agent_id="shared_knowledge",
    limit=5
))
```

Shared agent_id creates shared memory space.

### Best Practices

**1. Importance Scoring**
High importance (>0.8) → long-term storage
Low importance (<0.5) → short-term only

**2. Cleanup**
Short-term auto-cleans after 24 hours
Long-term persists indefinitely
Archive old conversations periodically

**3. Search Thresholds**
similarity_threshold=0.7 is good default
Lower (0.5) for broader search
Higher (0.8) for precise matches

**4. Memory Types**
Short-term: Current session
Long-term: Important discoveries
Episodic: Conversation history
Semantic: Domain knowledge

Use the right type for the right data.

**5. Privacy**
Memory stores everything—be mindful of sensitive data
Implement retention policies
Allow memory deletion

### What You've Learned

Memory system:
- Four types: Short-term, Long-term, Episodic, Semantic
- Storage via `MemoryManager`
- Semantic search via Qdrant vectors
- Conversation tracking
- Knowledge accumulation

Memory transforms stateless agents into learning systems that remember, adapt, and improve over time.

---

*See `examples/005_memory_enabled_agents.py` for complete implementations and `docs/memory-system.md` for deep technical details.*

## Chapter 6: Tools & Capabilities

Agents need to *do* things, not just think about them. Tools give agents precise, deterministic capabilities.

### The Problem

LLMs are excellent at reasoning but terrible at:
- **Precise calculations**: 8,675,309 × 42 gets approximated, not calculated
- **External systems**: Can't actually query databases or APIs
- **Deterministic logic**: Need your exact business rules, not LLM's approximation
- **Performance**: LLM calls are slow for simple operations

**Tools solve this**: precise Python functions that agents can call.

### The @tool Decorator

Transform functions into agent capabilities:

```python
from praval import tool

@tool("calculate", owned_by="analyst", category="math")
def precise_calculation(x: float, y: float, operation: str) -> float:
    """
    Perform precise mathematical calculations.
    
    Args:
        x: First number
        y: Second number  
        operation: Operation (add, multiply, divide, subtract)
    """
    ops = {
        "add": lambda a, b: a + b,
        "multiply": lambda a, b: a * b,
        "divide": lambda a, b: a / b if b != 0 else float('inf'),
        "subtract": lambda a, b: a - b
    }
    return ops[operation](x, y)
```

**What happened**:
1. Function registered in ToolRegistry
2. Type hints extracted for metadata
3. Docstring became tool description
4. Tool associated with "analyst" agent
5. Became discoverable and callable

### Tool Metadata

Full decorator options:

```python
@tool(
    "validate_email",           # Tool name
    owned_by="data_processor",  # Owner agent
    category="validation",       # Organization
    shared=False,                # Not available to all
    version="2.0.0",            # Version tracking
    author="Team",              # Attribution
    tags=["email", "validation"] # Discovery tags
)
def validate_email(email: str) -> bool:
    """Validate email format."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
```

**Ownership**: Tools belong to specific agents
**Categories**: Organize by function (math, validation, data_access)
**Shared**: Mark `shared=True` for tools everyone needs
**Tags**: Metadata for discovery

### Using Tools with Agents

Agents call tools directly:

```python
from praval import agent, tool, chat

# Define tool
@tool("contemplate", owned_by="philosopher", category="reasoning")
def philosophical_contemplation(question: str, perspective: str = "existentialist") -> str:
    """Deep contemplation from a specific perspective."""
    perspectives = {
        "existentialist": f"From existentialism: '{question}' touches on individual responsibility.",
        "stoic": f"From stoicism: '{question}' reminds us to control what we can.",
        "pragmatic": f"From pragmatism: '{question}' should be evaluated by practical consequences."
    }
    return perspectives.get(perspective, f"Contemplating '{question}'...")

# Agent uses tool
@agent("philosopher")
def philosophical_agent(spore):
    """I think deeply using structured philosophical frameworks."""
    question = spore.knowledge.get("question")
    
    # Use tools for precise philosophical frameworks
    perspectives = ["existentialist", "stoic", "pragmatic"]
    insights = []
    
    for perspective in perspectives:
        insight = philosophical_contemplation(question, perspective)
        insights.append(f"**{perspective.title()}**: {insight}")
    
    response = f"Contemplating: '{question}'\n\n" + "\n\n".join(insights)
    
    return {"response": response}
```

The agent uses tools instead of prompting LLM for philosophical frameworks. **Precise definitions, not approximations.**

### Tool Registry

Discover tools at runtime:

```python
from praval import get_tool_registry

registry = get_tool_registry()

# Get tools for an agent
analyst_tools = registry.get_tools_for_agent("analyst")

# Get tools by category
math_tools = registry.get_tools_by_category("math")

# Get all shared tools
shared = registry.get_shared_tools()

# Search tools
validation_tools = registry.search_tools(
    category="validation",
    tags=["email"]
)
```

### Runtime Tool Assignment

Dynamically assign tools:

```python
from praval import register_tool_with_agent, unregister_tool_from_agent

# Give analyst access to validation tool
register_tool_with_agent("validate_email", "analyst")

# Remove access when done
unregister_tool_from_agent("validate_email", "analyst")
```

### Tool Collections

Group related tools:

```python
from praval import ToolCollection

# Create toolkit
data_toolkit = ToolCollection(
    name="data_processing",
    description="Complete data validation and transformation toolkit"
)

data_toolkit.add_tool("validate_email")
data_toolkit.add_tool("validate_phone")
data_toolkit.add_tool("parse_date")
data_toolkit.add_tool("format_currency")

# Assign entire toolkit to agent
data_toolkit.assign_to_agent("data_processor")
```

### Type Safety

Tools require type hints—this isn't optional:

```python
# ✓ Good - full type hints
@tool("good_tool")
def good_example(x: int, y: str) -> bool:
    return len(y) > x

# ✗ Bad - missing type hints  
@tool("bad_tool")
def bad_example(x, y):  # ToolError!
    return x + y
```

Type hints enable agents (and LLMs) to use tools correctly.

### When to Use Tools

**Use tools for**:
- Deterministic behavior (math, validation)
- External systems (databases, APIs)
- Precise domain logic (your business rules)
- Performance (faster than LLM calls)
- Consistency (same input → same output)

**Use LLM reasoning for**:
- Natural language understanding
- Creative synthesis
- Contextual judgment
- Pattern recognition in unstructured data

**Use both together**: LLM decides *what* to do, tools execute *how* to do it precisely.

### Complete Example

```python
from praval import agent, tool, chat, start_agents

# Mathematical tools
@tool("add", shared=True, category="math")
def add_numbers(x: float, y: float) -> float:
    """Add two numbers."""
    return x + y

@tool("multiply", shared=True, category="math")
def multiply_numbers(x: float, y: float) -> float:
    """Multiply two numbers."""
    return x * y

# Calculator agent using tools
@agent("calculator")
def calculator_agent(spore):
    """I perform precise calculations using mathematical tools."""
    expression = spore.knowledge.get("expression")
    
    # Parse expression (simplified example)
    # "What is 123 + 456?"
    if "+" in expression:
        numbers = [float(n.strip()) for n in expression.split("+")]
        result = add_numbers(numbers[0], numbers[1])
        operation = "addition"
    elif "*" in expression or "×" in expression:
        numbers = [float(n.strip()) for n in expression.replace("×", "*").split("*")]
        result = multiply_numbers(numbers[0], numbers[1])
        operation = "multiplication"
    else:
        return {"error": "Unsupported operation"}
    
    return {
        "result": result,
        "operation": operation,
        "expression": expression
    }

# Use it
start_agents(
    calculator_agent,
    initial_data={"expression": "123 + 456"}
)
```

### What You've Learned

Tools system:
- `@tool` decorator transforms functions into agent capabilities
- Ownership, categories, and metadata for organization
- ToolRegistry for discovery
- Runtime assignment for flexibility
- Type hints required for safety
- Combines LLM reasoning with deterministic execution

Tools transform agents from thinkers into doers.

---

*See `examples/001_single_agent_identity.py` for tools with the philosopher agent.*

## Chapter 7: Enterprise Features

Production systems need enterprise capabilities: persistent storage and secure communication.

### Unified Storage System

Agents need to store data across multiple backends. Praval provides one interface for PostgreSQL, Redis, S3, Qdrant, and filesystem.

**The problem**: Each storage system has its own API, patterns, failure modes. Writing adapters is tedious.

**The solution**: `@storage_enabled` decorator gives agents unified access.

```python
from praval import agent, storage_enabled
import asyncio

@storage_enabled(["filesystem", "redis"])
@agent("data_collector", responds_to=["collect_data"])
def data_collector_agent(spore, storage):
    """I collect and store data across multiple backends."""
    
    customer_data = {
        "customers": [
            {"id": 1, "name": "Acme Corp", "revenue": 1500000},
            {"id": 2, "name": "Global Systems", "revenue": 2300000}
        ]
    }
    
    # Store in filesystem
    result = asyncio.run(storage.store("filesystem", "data/customers.json", customer_data))
    if result.success:
        customer_ref = result.data_reference.to_uri()
        print(f"✅ Stored: {customer_ref}")
    
    # Cache in Redis for fast access
    asyncio.run(storage.store("redis", "customers:latest", customer_data))
    
    return {"status": "complete", "data_reference": customer_ref}
```

**Storage providers**:

**PostgreSQL** (structured relational data):
```python
await storage.store("postgresql", table="customers", data=customer_record)
await storage.query("postgresql", table="customers", conditions={"revenue__gt": 1000000})
```

**Redis** (fast key-value cache):
```python
await storage.store("redis", "session:user123", session_data, ttl=3600)
await storage.get("redis", "session:user123")
```

**S3** (object storage):
```python
await storage.store("s3", "reports/analysis.pdf", pdf_data)
await storage.get_url("s3", "reports/analysis.pdf", expires=3600)
```

**Qdrant** (vector embeddings):
```python
await storage.store("qdrant", "documents", embeddings_list)
await storage.query("qdrant", collection="documents", vector=query_vector, limit=5)
```

**FileSystem** (local files):
```python
await storage.store("filesystem", "data/results.json", results)
await storage.get("filesystem", "data/results.json")
```

### DataReferences: Cross-Agent Data Sharing

When agents store data, they get references to share:

```python
@agent("collector")
def collector(spore, storage):
    result = await storage.store("filesystem", "data/customers.json", data)
    
    # Broadcast reference
    broadcast({
        "type": "data_ready",
        "data_reference": result.data_reference.to_uri()
        # e.g., "storage://filesystem/data/customers.json"
    })

@agent("analyzer", responds_to=["data_ready"])
def analyzer(spore, storage):
    # Get reference
    data_uri = spore.knowledge.get("data_reference")
    
    # Resolve to actual data
    result = await storage.resolve_data_reference(data_uri)
    data = result.data
    
    # Analyze without knowing source
    analysis = analyze(data)
```

DataReferences decouple production from consumption. Producers store wherever makes sense. Consumers retrieve regardless of source.

### Storage Configuration

Auto-configures from environment:

```bash
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_DB=praval
POSTGRES_USER=praval
POSTGRES_PASSWORD=secure_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# S3/MinIO
S3_BUCKET_NAME=praval-data
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret

# Qdrant
QDRANT_URL=http://localhost:6333

# FileSystem
FILESYSTEM_BASE_PATH=/var/praval/data
```

Set variables, run agents. Storage works.

### Secure Spores Enterprise

Production deployments need secure communication: end-to-end encryption, digital signatures, multi-protocol support.

**The problem**: Network communication can be intercepted, tampered with, replayed.

**The solution**: SecureReef with encryption and signing.

```python
from praval.core.secure_reef import SecureReef
from praval.core.transport import TransportProtocol

# Create secure reef
reef = SecureReef(
    protocol=TransportProtocol.AMQP,
    transport_config={
        "url": "amqps://user:pass@rabbitmq:5671",
        "exchange": "secure_agents"
    }
)

# Initialize
await reef.initialize("agent_name")

# All communication encrypted and signed
await reef.send_secure_spore(
    to_agent="recipient",
    knowledge={"query": "sensitive_data"},
    spore_type=SporeType.REQUEST
)
```

**Security layers**:
1. **Transport encryption**: TLS/SSL for network
2. **Content encryption**: Curve25519 + XSalsa20 (NaCl)
3. **Digital signatures**: Ed25519 for authenticity

Messages are encrypted, signed, and verified automatically.

### Multi-Protocol Support

**AMQP** (RabbitMQ): High reliability, complex routing
**MQTT** (Mosquitto): Lightweight, IoT-friendly
**STOMP** (ActiveMQ): Simple, text-based

All protocols get the same security features.

### Key Management

```python
from praval.core.secure_spore import SporeKeyManager

# Each agent has key manager
key_manager = SporeKeyManager(agent_id="agent1")
public_keys = key_manager.get_public_keys()

# Register peer keys
await reef.key_registry.register_agent("agent2", agent2_public_keys)

# Rotate keys periodically
await reef.rotate_keys()
```

**Key rotation** provides forward secrecy. Compromised keys only affect messages from their validity period.

### Security Best Practices

1. **Rotate keys regularly** (daily in production)
2. **Use TLS for transport** (amqps://, port 8883 for MQTT)
3. **Secure key storage** (file permissions 600, HSMs for high security)
4. **Implement key revocation** for compromised agents
5. **Monitor security events** (log rotations, signature failures)

### Production Patterns

**Tiered Storage**:
```python
# Hot: Redis (ms latency)
# Warm: PostgreSQL (fast queries)
# Cold: S3 (cheap, slower)

result = await storage.get("redis", key)
if not result.success:
    result = await storage.get("postgresql", table, id)
    if result.success:
        # Promote to hot tier
        await storage.store("redis", key, result.data, ttl=3600)
```

**Polyglot Persistence**:
```python
# Metadata → PostgreSQL
await storage.store("postgresql", "documents", metadata)

# Embeddings → Qdrant
await storage.store("qdrant", "doc_vectors", embeddings)

# Files → S3
await storage.store("s3", f"documents/{doc_id}.pdf", pdf_bytes)
```

### What You've Learned

Enterprise features:
- **Unified Storage**: One interface, five providers (PostgreSQL, Redis, S3, Qdrant, FileSystem)
- **DataReferences**: Cross-agent data sharing
- **Secure Communication**: E2E encryption, digital signatures
- **Multi-Protocol**: AMQP, MQTT, STOMP support
- **Key Management**: Rotation, revocation, forward secrecy
- **Production Patterns**: Tiered storage, polyglot persistence

Your agents now have production-grade persistence and security.

---

*See `examples/010_unified_storage_demo.py` and `examples/011_secure_spore_demo.py` for complete implementations.*

## Chapter 8: Production & Best Practices

Let's talk about deploying Praval systems to production.

### VentureLens Case Study

The flagship example demonstrates real-world architecture:

**System**: Business idea analyzer that interviews users, researches markets, evaluates viability, generates PDF reports.

**Agents**:
1. **Interviewer** (50 lines): Generates contextual questions
2. **Researcher** (40 lines): Gathers market intelligence
3. **Analyst** (55 lines): Evaluates across 6 dimensions
4. **Reporter** (45 lines): Creates markdown reports
5. **Presenter** (35 lines): Generates PDFs

**Total**: 225 lines of focused code replacing 847-line monolith.

**Key insights**:
- Each agent understandable in isolation
- Agents coordinate through message types
- No central orchestrator needed
- System more capable than monolith
- Easier to test, modify, extend

### Deployment Architecture

**Single Process** (development, small deployments):
```python
# All agents in one process
from praval import start_agents

start_agents(
    interviewer_agent,
    researcher_agent,
    analyst_agent,
    reporter_agent,
    presenter_agent,
    initial_data={"type": "start_interview"}
)
```

**Docker Compose** (production, multi-service):
```yaml
version: '3.8'
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes: ["./qdrant_storage:/qdrant/storage"]
  
  redis:
    image: redis:alpine
    ports: ["6379:6379"]
  
  praval-app:
    build: .
    environment:
      - QDRANT_URL=http://qdrant:6333
      - REDIS_HOST=redis
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on: [qdrant, redis]
```

**Distributed** (horizontal scaling):
- Agents on separate machines
- SecureReef with AMQP/MQTT
- Shared Qdrant for memory
- Shared Redis for state

### Configuration Management

**Environment-based**:
```bash
# LLM Provider
export OPENAI_API_KEY="key"

# Memory
export QDRANT_URL="http://qdrant:6333"

# Storage
export POSTGRES_HOST="db.example.com"
export REDIS_HOST="redis.example.com"

# Logging
export PRAVAL_LOG_LEVEL="INFO"
```

**Programmatic**:
```python
from praval import configure

configure({
    "default_provider": "openai",
    "default_model": "gpt-4-turbo",
    "reef_config": {
        "channel_capacity": 1000,
        "message_ttl": 3600
    },
    "memory_config": {
        "qdrant_url": "http://qdrant:6333"
    }
})
```

### Monitoring and Observability

**Log important events**:
```python
import logging

logger = logging.getLogger("praval.agents")

@agent("monitored")
def monitored_agent(spore):
    logger.info(f"Processing {spore.type} from {spore.from_agent}")
    
    try:
        result = process(spore)
        logger.info(f"Success: {result}")
        return result
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise
```

**Track metrics**:
```python
from collections import defaultdict
import time

metrics = defaultdict(lambda: {
    "count": 0,
    "errors": 0,
    "total_time": 0
})

@agent("instrumented")
def instrumented_agent(spore):
    start = time.time()
    agent_name = "instrumented"
    
    try:
        result = process(spore)
        
        metrics[agent_name]["count"] += 1
        metrics[agent_name]["total_time"] += time.time() - start
        
        return result
    except Exception as e:
        metrics[agent_name]["errors"] += 1
        raise
```

**Health checks**:
```python
@agent("health_check", responds_to=["health_check_request"])
def health_check_agent(spore):
    """I report system health."""
    
    health = {
        "status": "healthy",
        "agents": get_registry().list_agents(),
        "uptime": get_uptime(),
        "memory_usage": get_memory_stats()
    }
    
    return health
```

### Testing Strategies

**Unit test agents**:
```python
def test_analyzer():
    from praval.core.reef import Spore
    
    mock_spore = Spore(
        knowledge={"data": "test data"},
        type="analyze_request"
    )
    
    result = analyzer_agent(mock_spore)
    
    assert "analysis" in result
    assert result["analysis"] is not None
```

**Integration test agent systems**:
```python
def test_agent_pipeline():
    from praval import start_agents
    
    result = start_agents(
        extractor_agent,
        analyzer_agent,
        reporter_agent,
        initial_data={"document": "test.pdf"}
    )
    
    assert "report" in result
```

**Mock LLM calls for testing**:
```python
from unittest.mock import patch

@patch('praval.decorators.chat')
def test_agent_with_mock_llm(mock_chat):
    mock_chat.return_value = "Mocked LLM response"
    
    result = agent_function(mock_spore)
    
    assert mock_chat.called
    assert result["response"] == "Mocked LLM response"
```

### Performance Optimization

**1. Minimize LLM calls**
LLM calls are slow—use tools for deterministic operations.

**2. Cache responses**
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_llm_call(prompt):
    return chat(prompt)
```

**3. Batch operations**
Process multiple items together when possible.

**4. Parallel agents**
Agents naturally run in parallel—leverage it.

**5. Memory pruning**
Clean short-term memory regularly. Archive old episodic memories.

### Security Considerations

**1. Input validation**
```python
@agent("secure_agent")
def secure_agent(spore):
    query = spore.knowledge.get("query", "")
    
    # Validate input
    if len(query) > 10000:
        return {"error": "Query too long"}
    
    if contains_injection_attempt(query):
        return {"error": "Invalid input"}
    
    # Process safely
    result = process(query)
    return {"result": result}
```

**2. Sanitize outputs**
Don't expose internal errors or sensitive data to users.

**3. Rate limiting**
```python
from collections import deque
import time

request_times = deque(maxlen=100)

@agent("rate_limited")
def rate_limited_agent(spore):
    now = time.time()
    request_times.append(now)
    
    # Check rate
    recent = [t for t in request_times if now - t < 60]
    if len(recent) > 10:  # Max 10 per minute
        return {"error": "Rate limit exceeded"}
    
    return process(spore)
```

**4. Environment secrets**
Never hardcode API keys. Use environment variables or secret managers.

**5. Secure communication**
Use SecureReef for distributed deployments.

### Cost Optimization

**1. Model selection**
- GPT-4: Expensive, high quality
- GPT-3.5-turbo: Cheaper, good for simple tasks
- Choose appropriately per agent

**2. Prompt efficiency**
Shorter prompts = lower costs. Be concise.

**3. Caching**
Cache frequently asked questions.

**4. Sampling strategy**
Not every operation needs LLM. Use tools where possible.

### Best Practices Summary

**Design**:
- ✓ Single responsibility per agent
- ✓ Clear communication vocabulary
- ✓ Loose coupling via messages
- ✓ Gradual complexity

**Development**:
- ✓ Test agents independently
- ✓ Mock LLM calls for tests
- ✓ Observable behavior (logging)
- ✓ Version control agents separately

**Production**:
- ✓ Environment-based configuration
- ✓ Health checks and monitoring
- ✓ Error isolation and fallbacks
- ✓ Rate limiting and validation
- ✓ Secure communication
- ✓ Performance optimization

**Operations**:
- ✓ Docker deployment
- ✓ Log aggregation
- ✓ Metrics tracking
- ✓ Backup and recovery
- ✓ Incident response plan

### What You've Learned

Production deployment:
- **VentureLens case study**: Real 5-agent system
- **Deployment options**: Single process, Docker, distributed
- **Configuration**: Environment variables, programmatic
- **Monitoring**: Logging, metrics, health checks
- **Testing**: Unit, integration, mocking
- **Performance**: Caching, batching, parallelism
- **Security**: Validation, sanitization, rate limiting
- **Cost optimization**: Model selection, prompt efficiency

Praval systems are production-ready. Deploy with confidence.

---

*See `examples/venturelens.py` for the complete flagship example.*

---

# APPENDICES

## API Quick Reference

### Core Decorators

```python
from praval import agent, tool

@agent(name, responds_to=None, memory=False)
def agent_function(spore):
    """Agent implementation"""
    pass

@tool(name, owned_by=None, category="general", shared=False)
def tool_function(param: type) -> return_type:
    """Tool implementation"""
    pass
```

### Communication

```python
from praval import broadcast, get_reef

# Broadcast to all subscribed agents
broadcast({"type": "message_type", "data": "value"})

# Direct message
reef = get_reef()
reef.send_to_agent("agent_name", {"data": "value"})
```

### LLM Integration

```python
from praval import chat, achat

# Synchronous
response = chat("prompt here")

# Async
response = await achat("prompt here")
```

### Memory System

```python
from praval.memory import MemoryManager, MemoryType, MemoryQuery

memory = MemoryManager(qdrant_url="http://localhost:6333")

# Store
memory.store_memory(
    agent_id="agent",
    content="content",
    memory_type=MemoryType.LONG_TERM,
    importance=0.8
)

# Search
results = memory.search_memories(MemoryQuery(
    query_text="query",
    agent_id="agent",
    limit=5
))

# Conversation
memory.store_conversation_turn(
    agent_id="agent",
    user_message="question",
    agent_response="answer"
)
```

### Tool System

```python
from praval import (
    get_tool_registry, register_tool_with_agent,
    ToolCollection
)

# Registry
registry = get_tool_registry()
tools = registry.get_tools_for_agent("agent_name")

# Runtime assignment
register_tool_with_agent("tool_name", "agent_name")

# Collections
collection = ToolCollection("name", "description")
collection.add_tool("tool_name")
collection.assign_to_agent("agent_name")
```

### Storage System

```python
from praval import storage_enabled
import asyncio

@storage_enabled(["filesystem", "redis", "postgresql"])
@agent("data_agent")
def agent_with_storage(spore, storage):
    # Store
    result = asyncio.run(storage.store("filesystem", "path", data))
    
    # Get
    result = asyncio.run(storage.get("redis", "key"))
    
    # Query
    result = asyncio.run(storage.query("postgresql", table="data"))
```

### Registry & Discovery

```python
from praval import get_registry

registry = get_registry()

# List all agents
agents = registry.list_agents()

# Get specific agent
agent = registry.get_agent("name")

# Check subscriptions
subscriptions = agent.responds_to
```

### Agent Composition

```python
from praval import start_agents

# Start agent system
result = start_agents(
    agent1,
    agent2,
    agent3,
    initial_data={"type": "start", "data": "value"}
)
```

---

## Configuration Guide

### Environment Variables

**LLM Providers** (at least one required):
```bash
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
COHERE_API_KEY=your_cohere_key
```

**Praval Framework**:
```bash
PRAVAL_DEFAULT_PROVIDER=openai        # openai, anthropic, cohere
PRAVAL_DEFAULT_MODEL=gpt-4-turbo     # Model name
PRAVAL_MAX_THREADS=10                 # Max concurrent agents
PRAVAL_LOG_LEVEL=INFO                 # DEBUG, INFO, WARNING, ERROR
```

**Memory System**:
```bash
QDRANT_URL=http://localhost:6333
PRAVAL_COLLECTION_NAME=praval_memories
SHORT_TERM_MAX_ENTRIES=1000
SHORT_TERM_RETENTION_HOURS=24
```

**Storage Providers**:
```bash
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=praval
POSTGRES_USER=praval
POSTGRES_PASSWORD=your_password

# Redis  
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_password

# S3/MinIO
S3_BUCKET_NAME=praval-data
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
S3_ENDPOINT_URL=http://localhost:9000  # MinIO

# Filesystem
FILESYSTEM_BASE_PATH=/var/praval/data
```

**Secure Communication**:
```bash
# AMQP
PRAVAL_AMQP_URL=amqps://user:pass@rabbitmq:5671/vhost

# MQTT
PRAVAL_MQTT_HOST=mosquitto
PRAVAL_MQTT_PORT=8883
PRAVAL_MQTT_TLS=true

# STOMP
PRAVAL_STOMP_HOST=activemq
PRAVAL_STOMP_PORT=61614
```

### Programmatic Configuration

```python
from praval import configure

configure({
    # LLM Provider
    "default_provider": "openai",
    "default_model": "gpt-4-turbo",
    "max_concurrent_agents": 10,
    
    # Reef
    "reef_config": {
        "channel_capacity": 1000,
        "message_ttl": 3600,
        "enable_history": True
    },
    
    # Memory
    "memory_config": {
        "qdrant_url": "http://qdrant:6333",
        "collection_name": "memories",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "short_term_max_entries": 2000,
        "short_term_retention_hours": 48
    },
    
    # Logging
    "log_config": {
        "level": "INFO",
        "format": "json",
        "output": "stdout"
    }
})
```

### Docker Compose Configuration

```yaml
version: '3.8'

services:
  # Qdrant for memory/vectors
  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes:
      - ./qdrant_storage:/qdrant/storage
    environment:
      - QDRANT__SERVICE__GRPC_PORT=6334

  # Redis for caching
  redis:
    image: redis:alpine
    ports: ["6379:6379"]
    command: redis-server --appendonly yes
    volumes:
      - ./redis_data:/data

  # PostgreSQL for structured data
  postgres:
    image: postgres:15
    ports: ["5432:5432"]
    environment:
      - POSTGRES_DB=praval
      - POSTGRES_USER=praval
      - POSTGRES_PASSWORD=praval_secure_password
    volumes:
      - ./postgres_data:/var/lib/postgresql/data

  # Praval application
  praval-app:
    build: .
    environment:
      - QDRANT_URL=http://qdrant:6333
      - REDIS_HOST=redis
      - POSTGRES_HOST=postgres
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - PRAVAL_LOG_LEVEL=INFO
    depends_on:
      - qdrant
      - redis
      - postgres
    volumes:
      - ./app:/app
```

---

## Troubleshooting

### Common Issues

**Problem**: `ImportError: cannot import name 'agent'`
- **Cause**: Praval not installed
- **Solution**: `pip install praval`

**Problem**: `No LLM provider available`
- **Cause**: No API keys set
- **Solution**: Set at least one: `export OPENAI_API_KEY="key"`

**Problem**: `Qdrant connection failed`
- **Cause**: Qdrant not running
- **Solution**: 
  ```bash
  docker run -p 6333:6333 qdrant/qdrant:latest
  # or
  docker-compose up qdrant
  ```

**Problem**: `Agent not receiving messages`
- **Cause**: `responds_to` doesn't match broadcast type
- **Solution**: Check message type matches:
  ```python
  @agent("handler", responds_to=["message_type"])
  # ...
  broadcast({"type": "message_type"})  # Must match!
  ```

**Problem**: `Tool not found`
- **Cause**: Tool not registered before agent uses it
- **Solution**: Define tools before agents that use them

**Problem**: `Memory search returns no results`
- **Cause**: Memories not embedded yet, or threshold too high
- **Solution**: Lower `similarity_threshold` to 0.5-0.6

**Problem**: `Storage provider not available`
- **Cause**: Missing environment variables
- **Solution**: Set required vars for the provider (see Configuration Guide)

**Problem**: `SecureReef encryption errors`
- **Cause**: Keys not registered between agents
- **Solution**: Ensure `key_registry.register_agent()` called for peers

**Problem**: `High LLM costs`
- **Cause**: Too many or too large prompts
- **Solution**:
  - Use tools for deterministic operations
  - Cache responses
  - Use cheaper models for simple tasks
  - Shorten prompts

**Problem**: `Agents running slowly`
- **Cause**: Sequential instead of parallel execution
- **Solution**: Ensure agents broadcast and respond rather than calling directly

**Problem**: `Memory growing too large`
- **Cause**: Short-term memory not cleaning up
- **Solution**:
  - Reduce `short_term_max_entries`
  - Lower `short_term_retention_hours`
  - Archive old memories

### Debug Mode

Enable verbose logging:

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Praval-specific loggers
logging.getLogger('praval.core.reef').setLevel(logging.DEBUG)
logging.getLogger('praval.memory').setLevel(logging.DEBUG)
logging.getLogger('praval.storage').setLevel(logging.DEBUG)
```

### Health Checks

Check system components:

```python
# Check Qdrant
import requests
response = requests.get("http://localhost:6333/health")
print(f"Qdrant: {response.json()}")

# Check Redis
import redis
r = redis.Redis(host='localhost', port=6379)
print(f"Redis: {r.ping()}")

# Check registered agents
from praval import get_registry
registry = get_registry()
print(f"Agents: {registry.list_agents()}")

# Check tools
from praval import get_tool_registry
tool_registry = get_tool_registry()
print(f"Tools: {len(tool_registry.list_all_tools())}")

# Check memory
from praval.memory import MemoryManager
memory = MemoryManager()
stats = memory.get_memory_stats()
print(f"Memory stats: {stats}")
```

### Getting Help

- **Documentation**: `docs/` directory
- **Examples**: `examples/001-011` numbered examples
- **GitHub Issues**: Report bugs at repository
- **Community**: Join discussions

---

## Conclusion

Praval transforms complex AI application development into simple, composable agent ecosystems. Like coral reefs in nature, complex intelligence emerges from the collaboration of simple, specialized agents.

**What you've learned**:
- Philosophy: Specialization over generalization, identity over instruction
- Core concepts: Agents, spores, the Reef, emergence
- Architecture: How it all fits together
- Patterns: Specialist, pipeline, collaborative, parallel
- Memory: Persistent, learning agents
- Tools: Deterministic capabilities
- Enterprise: Storage and security
- Production: Deployment and best practices

**Next steps**:
1. Run examples: `python examples/001_single_agent_identity.py`
2. Build your first system: Start with 2-3 agents
3. Add capabilities: Memory, tools, storage as needed
4. Deploy: Docker Compose for production

Simple agents. Clear communication. Powerful emergence.

That's Praval.

---

**Praval v0.7.6 Complete Manual**
© 2025 Rajesh Sampathkumar | MIT License

*Start with `examples/pythonic_knowledge_graph.py` to see core concepts, then explore `examples/venturelens.py` for a complete real-world application.*
