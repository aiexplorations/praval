# Tutorial: Creating Your First Agent

Learn to create a simple Praval agent from scratch.

## What You'll Build

A research agent that takes a topic, researches it using an LLM, and returns structured findings.

## Prerequisites

- Python 3.9+
- Praval installed (`pip install praval`)
- An OpenAI API key set (`export OPENAI_API_KEY="sk-..."`)

## Step 1: Basic Agent

Create a file `my_first_agent.py`:

```python
from praval import agent, chat, start_agents

@agent("researcher")
def research_agent(spore):
    """A simple research agent."""
    topic = spore.knowledge.get("topic", "artificial intelligence")
    result = chat(f"Provide a brief overview of: {topic}")
    return {"summary": result}

# Start the agent system
start_agents()

# Test the agent
result = research_agent({"topic": "quantum computing"})
print(result["summary"])
```

**Run it**:
```bash
python my_first_agent.py
```

## Step 2: Understanding the Code

### The `@agent` Decorator

```python
@agent("researcher")
```

This transforms your function into an autonomous agent with:
- Unique name: `"researcher"`
- Ability to receive messages
- Access to LLM through `chat()`
- Automatic registration with the system

### The Spore Parameter

```python
def research_agent(spore):
    topic = spore.knowledge.get("topic", "artificial intelligence")
```

`spore` is the message container. It has:
- `knowledge`: Dictionary of data
- `type`: Message type
- `sender`: Who sent it
- `metadata`: Extra context

### The `chat()` Function

```python
result = chat(f"Provide a brief overview of: {topic}")
```

Sends a prompt to your LLM and gets back a response.

## Step 3: Add a System Message

Improve the agent with better instructions:

```python
@agent("researcher", system_message="""
You are an expert researcher specializing in technology topics.
Provide concise, factual overviews with:
- Main definition
- Key applications
- Current state of development
Keep responses to 3-4 sentences.
""")
def research_agent(spore):
    topic = spore.knowledge.get("topic", "artificial intelligence")
    result = chat(f"Provide a brief overview of: {topic}")
    return {"summary": result}
```

**What changed**:
- Agent now has explicit instructions
- LLM knows exactly what format to use
- Responses are more consistent

## Step 4: Add Error Handling

Make it robust:

```python
@agent("researcher", system_message="""
You are an expert researcher specializing in technology topics.
Provide concise, factual overviews with:
- Main definition
- Key applications
- Current state of development
Keep responses to 3-4 sentences.
""")
def research_agent(spore):
    topic = spore.knowledge.get("topic")

    if not topic:
        return {"error": "No topic provided"}

    try:
        result = chat(f"Provide a brief overview of: {topic}")
        return {"summary": result, "topic": topic}
    except Exception as e:
        return {"error": str(e), "topic": topic}

# Start the system
start_agents()

# Test with valid topic
result1 = research_agent({"topic": "machine learning"})
print("Valid:", result1)

# Test without topic
result2 = research_agent({})
print("Invalid:", result2)
```

## Step 5: Add Broadcasting

Let other agents know about the research:

```python
from praval import agent, chat, broadcast, start_agents

@agent("researcher")
def research_agent(spore):
    topic = spore.knowledge.get("topic")

    if not topic:
        return {"error": "No topic provided"}

    result = chat(f"Research: {topic}")

    # Broadcast results to other agents
    broadcast({
        "type": "research_complete",
        "topic": topic,
        "findings": result
    })

    return {"summary": result}

# Start the system
start_agents()

# Trigger research
research_agent({"topic": "neural networks"})
```

## Step 6: Create a Listener

Add an agent that responds to research:

```python
from praval import agent, chat, broadcast, start_agents

@agent("researcher")
def research_agent(spore):
    topic = spore.knowledge.get("topic")
    result = chat(f"Research: {topic}")

    broadcast({
        "type": "research_complete",
        "topic": topic,
        "findings": result
    })

    return {"summary": result}

@agent("summarizer", responds_to=["research_complete"])
def summarizer(spore):
    """Listens for research and creates summaries."""
    findings = spore.knowledge.get("findings")
    summary = chat(f"Summarize in 3 bullet points:\n{findings}")

    print(f"Summary:\n{summary}")
    return {"summary": summary}

# Start the system
start_agents()

# Trigger the workflow
research_agent({"topic": "blockchain"})

# Give time for processing
import time
time.sleep(2)
```

**What happens**:
1. `research_agent` receives the topic
2. It researches and broadcasts `research_complete`
3. `summarizer` hears the broadcast
4. It creates and prints a summary

## Complete Example

Here's the full working code:

```python
"""
my_first_agent.py - A complete research agent example
"""

from praval import agent, chat, broadcast, start_agents
import time

@agent("researcher", system_message="""
You are an expert technology researcher.
Provide detailed but concise overviews covering:
- Core concept definition
- Key applications and use cases
- Current state and future outlook
""")
def research_agent(spore):
    """Research topics in depth."""
    topic = spore.knowledge.get("topic")

    if not topic:
        print("Error: No topic provided")
        return {"error": "No topic provided"}

    print(f"Researching: {topic}...")

    try:
        result = chat(f"Provide an overview of: {topic}")

        # Share findings with other agents
        broadcast({
            "type": "research_complete",
            "topic": topic,
            "findings": result
        })

        print(f"Research complete for: {topic}")
        return {"summary": result, "topic": topic}

    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}

@agent("summarizer", responds_to=["research_complete"], system_message="""
You create concise bullet-point summaries.
Format: Exactly 3 bullet points, each starting with •
Be clear and actionable.
""")
def summarizer(spore):
    """Create bullet-point summaries of research."""
    topic = spore.knowledge.get("topic")
    findings = spore.knowledge.get("findings")

    print(f"Creating summary for: {topic}...")

    summary = chat(f"Summarize in 3 bullet points:\n{findings}")

    print(f"\nSUMMARY - {topic}")
    print(summary)
    print("-" * 50)

    return {"summary": summary, "topic": topic}

if __name__ == "__main__":
    # Start the agent system
    start_agents()

    # Research a topic
    research_agent({"topic": "quantum computing"})

    # Give agents time to complete
    time.sleep(3)

    print("\nDone!")
```

## Running the Example

```bash
python my_first_agent.py
```

**Expected output**:
```
Researching: quantum computing...
Research complete for: quantum computing
Creating summary for: quantum computing...

SUMMARY - quantum computing
• Quantum computing leverages quantum mechanics principles...
• Applications include cryptography, drug discovery...
• Currently in early stages with active development...
--------------------------------------------------

Done!
```

## Key Concepts Learned

✓ Creating agents with `@agent`
✓ Using `chat()` to interact with LLMs
✓ Handling spore messages
✓ Broadcasting to other agents
✓ Filtering messages with `responds_to`
✓ Adding system messages for better control
✓ Error handling

## Next Steps

- **Tutorial 2**: [Agent Communication](agent-communication.md)
- **Tutorial 3**: [Memory-Enabled Agents](memory-enabled-agents.md)
- **Example**: See `examples/001_single_agent_identity.py`

## Troubleshooting

**Agent doesn't respond**:
- Check you called `start_agents()`
- Verify `responds_to` types match broadcast types

**No LLM response**:
- Verify API key is set: `echo $OPENAI_API_KEY`
- Check internet connection

**Import errors**:
- Ensure Praval is installed: `pip install praval`
- Check Python version: `python --version` (need 3.9+)
