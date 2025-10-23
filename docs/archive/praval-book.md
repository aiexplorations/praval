<p align="center">
  <img src="docs/logo.png" alt="Praval Logo" width="200"/>
</p>

# Praval: Practical Multi-Agent AI Development
## Building Production-Ready Agent Systems

**Version 1.0 | October 2025**

*Praval (प्रवाल) - Sanskrit for coral. Simple agents collaborating to create complex, intelligent ecosystems.*

---

**By Rajesh Sampathkumar ([@aiexplorations](https://github.com/aiexplorations))**

---

## Table of Contents

**PART I: Foundation**
- [Chapter 1: The Problem with Monoliths](#chapter-1-the-problem-with-monoliths)
- [Chapter 2: What Nature Already Knows](#chapter-2-what-nature-already-knows)
- [Chapter 3: Emergence](#chapter-3-emergence)

**PART II: Building**
- [Chapter 4: Building Multi-Agent Systems](#chapter-4-building-multi-agent-systems)
- [Chapter 5: Memory & Persistence](#chapter-5-memory--persistence)
- [Chapter 6: Tools & Capabilities](#chapter-6-tools--capabilities)

**PART III: Production**
- [Chapter 7: Enterprise Features](#chapter-7-enterprise-features)
- [Chapter 8: Production & Best Practices](#chapter-8-production--best-practices)

**Appendices**
- [Appendix A: API Reference](#appendix-a-api-reference)
- [Appendix B: Example Gallery](#appendix-b-example-gallery)
- [Appendix C: Configuration Guide](#appendix-c-configuration-guide)
- [Appendix D: Troubleshooting](#appendix-d-troubleshooting)

---

# PART I: Foundation

## Chapter 1: The Problem with Monoliths

It's 2:47 AM, and I'm staring at a function that has grown to 847 lines.

It started simple enough. Three months ago, it was 50 lines. Create an AI agent that could help users analyze business ideas. Straightforward. But then:

*"Can it also do market research?"*
*"We need it to generate competitive analysis."*
*"Oh, and financial projections would be nice."*
*"Users want SWOT analysis too."*
*"Can we add PDF report generation?"*

Each feature added felt reasonable in isolation. Just another 100 lines. Just one more capability. But complexity doesn't add linearly—it multiplies. Conditions nest inside conditions. State management becomes a puzzle. Error handling becomes whack-a-mole. And debugging? Debugging becomes archeology.

I'm looking at code that does too much, knows too much, is responsible for too much. A **monolith**.

And here's what I've learned about monoliths: they don't just make bad code. They make bad thinking.

### The Cognitive Load Problem

Your brain has a working memory capacity of about seven items, plus or minus two. This isn't a character flaw—it's neuroscience. When code exceeds what you can hold in working memory, you stop understanding it and start guessing.

Monolithic AI agents create this problem in spades:
- They're responsible for multiple domains (research AND analysis AND writing AND formatting)
- They maintain complex internal state (what stage are we at? what have we done?)
- They make decisions that cascade across concerns (if research fails, do we skip analysis? try a fallback? fail gracefully?)
- They mix abstraction levels (high-level business logic next to low-level API calls)

You can't hold all of that in your head simultaneously. So you don't. You work on one part while being vaguely nervous about what might break elsewhere. You add bandaids instead of fixes. Technical debt accumulates.

But here's the deeper problem: **monoliths prevent good thinking.**

When you have one agent responsible for everything, you can't think clearly about any one thing. Want to improve the research capability? First you have to understand how it intertwines with analysis, which depends on state managed by the business logic, which shares error handling with the report generator.

Everything touches everything. Change becomes expensive. Innovation becomes scary.

### The Brittleness Factor

Monolithic systems are brittle in predictable ways.

**Single Points of Failure**: When one capability breaks, the whole system is compromised. Your research API goes down? The entire agent fails. A prompt that worked for analysis doesn't work for research? Everything grinds to a halt.

**Tight Coupling**: Components that should be independent become entangled. Changing how you format reports requires understanding the research logic because they share state. Improving analysis means risking the financial projections because they're in the same execution flow.

**Testing Nightmares**: How do you test a 847-line function? You can't unit test it—it's too big. Integration tests become elaborate ceremony. So you end up testing in production, which means debugging at 2:47 AM.

**Optimization Impossibility**: Maybe research is slow but analysis is fast. With a monolith, you can't optimize them independently. Maybe research should be cached but analysis should be fresh. Too bad—they're the same system.

### The Expertise Dilution

Here's something subtler but equally important: monoliths dilute expertise.

When you prompt an LLM to be "an expert at business research AND competitive analysis AND financial modeling AND report writing," you're asking it to be a generalist. And generalists, by definition, aren't as good at any one thing as specialists would be.

Compare these prompts:

**Monolith Version**:
```python
agent = Agent("business_analyzer", system_message="""
You are a business analysis expert. You can:
- Conduct market research
- Perform competitive analysis
- Generate financial projections
- Create SWOT analyses
- Write executive summaries
- Format professional reports

Handle all business analysis tasks comprehensively.
""")
```

**Specialist Version**:
```python
researcher = Agent("researcher", system_message="""
You are a market research specialist. You excel at finding relevant
market data, identifying trends, and assessing market size and
opportunity. You think like a market analyst who has spent years
studying industry dynamics.
""")

analyst = Agent("analyst", system_message="""
You are a strategic analyst who excels at competitive analysis and
SWOT assessments. You think systematically about competitive
advantages, market positioning, and strategic opportunities.
""")

writer = Agent("writer", system_message="""
You are a business writer who creates clear, compelling executive
summaries. You know how to distill complex analysis into actionable
insights.
""")
```

Which produces better work?

The specialists. Every time. Because expertise is specific, not general. A researcher thinks like a researcher. An analyst thinks like an analyst. When you ask one agent to be both, you get mediocre research and mediocre analysis.

### The Maintenance Burden

Six months after you write monolithic code, you become a stranger to it.

You wrote it. You understand it. You're the expert. But six months later, trying to add a new feature, you'll spend more time understanding what you built than building what you need. The cognitive load returns.

And if someone else needs to maintain it? Good luck. They'll need to understand the entire system to change any part of it safely. Onboarding becomes bottleneck. Knowledge transfer becomes archaeological expedition.

Compare the maintenance story:

**Monolith**:
- "I need to add sentiment analysis to the business analyzer."
- *Reads 847 lines of code*
- *Traces execution flow through nested conditions*
- *Identifies where to inject new logic*
- *Carefully adds code without breaking existing flow*
- *Tests everything because anything might break*
- *Deploys nervously*

**Specialist System**:
- "I need to add sentiment analysis."
- *Creates new specialist agent in 30 lines*
- *Subscribes it to the right message types*
- *Tests it in isolation*
- *Deploys confidently*
- *Existing agents don't even know it exists*

Maintenance becomes additive, not invasive. New capabilities expand the system without compromising it.

### The Hidden Cost: Innovation Friction

The worst cost of monoliths isn't visible in the code—it's visible in what doesn't get built.

When adding features is expensive and risky, you stop experimenting. When changing behavior requires understanding everything, you stop innovating. When testing is hard, you stop iterating.

Monoliths create **innovation friction**: the psychological and practical resistance to trying new things.

"Could we add a different approach to analysis?"
*"Maybe, but it might break the report generator..."*

"What if we tried a different research methodology?"
*"We'd have to rewrite a lot of the state management..."*

"Should we experiment with a new LLM for the financial projections?"
*"Not sure how that would interact with the existing prompts..."*

Each "but" is innovation dying. Each hesitation is a path not explored.

### A Different Path

So here I am at 2:47 AM, looking at 847 lines of code that nobody should have to maintain, thinking: *there must be a better way.*

And there is.

What if, instead of one agent that tries to do everything, you had specialists? Each focused on one type of thinking. Each excellent at their domain. Each simple enough to understand completely.

What if they could communicate clearly? Pass knowledge between them without tight coupling?

What if the system's intelligence came not from any single agent's sophistication, but from how they collaborated?

What if adding new capabilities meant adding new specialists, not making existing agents more complex?

That's the path that leads to Praval. Not as a framework—frameworks are boring. As a different way of thinking about intelligence itself.

**Chapter Insight**: Monolithic AI agents create cognitive overload, brittleness, expertise dilution, maintenance nightmares, and innovation friction. The solution isn't better monoliths—it's a fundamentally different architecture based on specialist collaboration.

---

## Chapter 2: What Nature Already Knows

Before we had computers, we had biology. And biology has been solving the "how do you build complex, intelligent systems" problem for about 3.8 billion years.

Let me tell you about coral.

### The Polyp

A coral polyp is, by any measure, simple.

It's a small, soft-bodied organism that attaches to a hard surface. It has a mouth surrounded by tentacles for catching food. It filters nutrients from water. It secretes calcium carbonate to build a protective skeleton. That's basically it.

If you tried to describe a polyp's "algorithm," it would be maybe a dozen behaviors:
- Extend tentacles when hunting
- Retract when threatened
- Filter water for food
- Secrete calcium carbonate
- Reproduce by budding
- Respond to chemical signals from neighbors

Simple. Understandable. Specialized.

A polyp doesn't plan. It doesn't strategize. It doesn't try to "do everything." It does a few things well, responds to its environment, and communicates chemically with nearby polyps.

### The Reef

Now let me tell you about reefs.

The Great Barrier Reef is 2,300 kilometers long. It contains over 400 types of coral, 1,500 species of fish, 4,000 types of mollusk. It's visible from space. It's one of the most complex ecosystems on Earth.

And it's built by those simple polyps.

How?

**Not through central planning.** There's no "architect polyp" designing the structure. No master plan. No blueprint.

**Not through individual complexity.** The polyps didn't get smarter or more sophisticated. They stayed simple.

**Through collaboration and emergence.** Millions of simple organisms, each doing their specialized job, communicating through chemical signals, responding to their environment, building on each other's work.

The result is a structure so complex that scientists are still discovering new patterns, new interactions, new behaviors that emerge from the collective. The intelligence of the reef is not in any individual polyp—it's in the **system**.

### The Pattern

This pattern appears everywhere in nature:

**Ant Colonies**: Individual ants are simple. They follow pheromone trails, carry food, dig tunnels. That's it. But colonies solve complex problems: finding shortest paths between food and nest, regulating temperature, dividing labor efficiently, defending against threats. Colony-level intelligence emerges from simple individual behaviors and chemical communication.

**Neural Networks** (the biological kind): A single neuron is straightforward. It accumulates signals, fires if threshold is exceeded, passes signal to connected neurons. But billions of them, organized in layers, communicating through synapses, create human intelligence. Consciousness itself is emergent.

**Immune Systems**: Individual immune cells are specialists. T-cells identify threats. B-cells produce antibodies. Macrophages engulf pathogens. None of them "understand" the disease, but together they create a learning, adaptive defense system that remembers past infections and responds to new ones.

**Ecosystems**: Predators hunt. Prey hide. Plants photosynthesize. Decomposers recycle nutrients. Simple specialized behaviors, interacting through a food web, create stable, self-regulating systems that can persist for millennia.

The pattern is consistent: **simple specialists, clear communication, emergent complexity**.

### Why This Works

There are deep reasons why nature defaults to this architecture.

**Fault Tolerance**: When one polyp dies, the reef continues. When one ant is lost, the colony functions. Distributed systems are resilient to individual failures. Monolithic systems are fragile.

**Evolvability**: It's easier to evolve a better foraging ant than to redesign the entire colony. It's easier to add a new type of immune cell than to rebuild the immune system. Specialist systems can improve incrementally. Monoliths must be redesigned wholesale.

**Scalability**: Reefs grow by adding more polyps. Colonies grow by adding more ants. Complexity scales linearly with the number of components, not exponentially. Monolithic complexity grows geometrically—O(n²) or worse.

**Understandability**: You can understand what a polyp does. You can watch an ant and see its behavior. Individual components are comprehensible even when the system is complex. With monoliths, neither the parts nor the whole are understandable.

**Optimization**: Nature can optimize each specialist independently. Better hunting in ants doesn't require redesigning their communication system. Better photosynthesis in plants doesn't affect decomposer bacteria. Specialists can evolve without destabilizing the ecosystem.

### The Translation to AI

So what does this mean for building AI systems?

**Agents as Polyps**: Each agent should be simple enough to understand completely. It should specialize in one type of thinking or action. It should communicate clearly with other agents.

**The System as Reef**: Intelligence emerges from how agents interact, not from any individual agent's sophistication. The whole becomes greater than the sum of parts through collaboration patterns.

**Spores as Chemical Signals**: Just as polyps communicate through chemical signals in water, agents communicate through structured messages (we call them "spores"—more on why later). These signals carry semantic meaning that agents can respond to.

**Emergence as Intelligence**: Complex behaviors—analysis, reasoning, decision-making—emerge from simple specialists collaborating. You don't program the complexity; you create conditions where it can emerge.

This isn't just metaphor. It's architecture. It's a design principle that has worked for billions of years of evolution because it aligns with fundamental constraints: bounded complexity, fault tolerance, evolvability, scalability.

### What Nature Teaches Us to Avoid

Nature also shows us what doesn't work:

**Don't build Swiss army organisms**: Nature doesn't create organisms that can "do everything." Even organisms that seem generalist (like humans) are actually integrated systems of specialized components (specialized brain regions, organs, cell types).

**Don't centralize control**: Reefs don't have control centers. Ant colonies don't have "queen" making all decisions (the queen just reproduces—workers make operational decisions). Decentralized systems are robust and adaptive.

**Don't optimize prematurely**: Evolution doesn't design perfect organisms from scratch. It creates "good enough" specialists that evolve through iteration. Premature optimization creates brittle systems.

**Don't couple unnecessarily**: Organisms are modular. Your lungs can fail without stopping your kidneys. Your visual cortex can be damaged without destroying your motor control. Loose coupling enables resilience.

### The Coral as Design Pattern

When I named this framework Praval (Sanskrit for coral), it wasn't poetic license. It was design documentation.

The coral reef pattern suggests specific architectural decisions:

1. **Build Simple Specialists**: Each agent should excel at one type of thinking
2. **Enable Clear Communication**: Structured message passing, not tight coupling
3. **Allow Self-Organization**: Let agents discover collaboration patterns, don't orchestrate everything
4. **Embrace Emergence**: System intelligence arises from interactions
5. **Design for Evolution**: Make it easy to add, remove, improve specialists

This isn't the only way to build AI systems. But it's the way that nature—with 3.8 billion years of A/B testing—has consistently chosen when building complex, intelligent, resilient systems.

Maybe we should pay attention.

**Chapter Insight**: Nature consistently chooses simple specialists with clear communication over complex generalists. This pattern—demonstrated in coral reefs, ant colonies, immune systems, and human brains—provides a proven architecture for building complex, intelligent, resilient systems. Praval applies this biological pattern to AI.

---

## Chapter 3: Emergence

2:47 AM. I'm watching three AI agents do something I didn't program them to do.

Let me explain what I mean by that.

### What I Did Program

I created three agents:
- A **researcher** that finds information
- An **analyst** that identifies patterns
- A **critic** that questions assumptions

Simple. Each has a clear identity and specialty. They communicate by broadcasting findings and responding to relevant messages. Standard Praval pattern.

I sent them a business idea to evaluate: "An AI-powered personal finance advisor for freelancers."

### What I Expected

I expected a linear flow:
1. Researcher finds market data
2. Analyst identifies patterns in that data
3. Critic evaluates the analysis
4. Done

Neat. Predictable. Procedural.

### What Actually Happened

The researcher found market data and broadcasted it.

The analyst identified patterns and sent them out.

But then the critic, instead of just critiquing, asked a question that sent the research in a new direction: *"What about the specific challenges of irregular income? Did we research that?"*

The researcher, seeing that question, did deeper research on irregular income management.

This triggered the analyst to identify patterns in that new data.

Which prompted the critic to point out a market gap nobody had considered: *"Existing solutions assume steady income. This is fundamentally different."*

The researcher, following that thread, found data on behavioral economics and financial stress.

The analyst connected it to the original business idea in a way that reframed the entire opportunity.

By the end, they had collaboratively discovered an insight that was **more sophisticated than any of them individually could have produced**: The business isn't about budgeting tools (crowded market), it's about income smoothing and financial stress management (underserved need).

I didn't program that interaction pattern. I didn't orchestrate that discovery process. I certainly didn't code the insight.

**That's emergence.**

### Defining Emergence

Emergence is when a system exhibits properties or behaviors that its individual components don't possess.

*The consciousness you're experiencing right now? Emergent property of neurons.*
*The way traffic flows on highways? Emergent behavior of individual drivers.*
*The economy? Emergent system from individual transactions.*
*Reefs? Emergent structures from polyp behavior.*

Formally: **Emergence happens when simple components, interacting through local rules, create complex global patterns that can't be predicted from analyzing the components in isolation.**

In practical terms: the whole is greater than the sum of parts. And not just greater—**qualitatively different**.

### Why This Matters for AI

Traditional AI development is **compositional**: you break down a complex task into subtasks, program each subtask, then compose them together. The whole is the sum of parts you deliberately assembled.

Emergence is different. The whole is **more** than what you assembled. New behaviors, new capabilities, new intelligence appears that you didn't explicitly program.

This isn't magic. It's how complex systems work.

### The Conditions for Emergence

Emergence doesn't happen randomly. It requires specific conditions:

#### 1. **Simple Components with Clear Identities**

Emergence requires simplicity. Counter-intuitive but true.

When components are complex, they're brittle. Tiny changes cascade unpredictably. When components are simple, their interactions are more transparent, and emergent patterns are more stable.

In Praval:
```python
@agent("researcher")
def research_specialist(spore):
    """I find relevant information on specific topics."""
    # Simple, focused, understandable
```

Not:
```python
@agent("super_agent")
def do_everything(spore):
    """I can research, analyze, critique, synthesize, format, and deploy."""
    # Too complex for clean emergent behavior
```

#### 2. **Local Interactions, Not Global Control**

Emergence requires **decentralized** interaction. Agents respond to their immediate environment (messages they receive), not to global state or central orchestration.

In coral reefs, polyps don't communicate with every other polyp. They respond to their neighbors. This local interaction pattern creates global structure.

In Praval:
```python
@agent("analyst", responds_to=["research_findings"])
def analyst(spore):
    # Responds only to relevant local signals
    # Doesn't need to know about the whole system
```

#### 3. **Rich Communication Protocols**

Emergence requires information flow. Components must be able to signal each other in semantically rich ways.

In reefs, polyps release multiple types of chemical signals: danger warnings, reproductive readiness, nutrient availability. Rich vocabulary enables complex coordination.

In Praval, spores carry structured knowledge:
```python
broadcast({
    "type": "research_insight",
    "topic": "freelancer_finances",
    "insight": "Irregular income creates unique stress patterns",
    "confidence": 0.85,
    "sources": [...],
    "implications": [...]
})
```

The richness of the message enables sophisticated responses.

#### 4. **Feedback Loops**

Emergence requires that outputs can become inputs. Agent A's response influences Agent B, whose response influences Agent A again. Circular causality creates adaptive behavior.

In the business analysis example, the critic's questions fed back to the researcher, creating a conversation that refined understanding iteratively. That feedback loop is what enabled the system to discover insights neither agent had initially.

#### 5. **Time and Iteration**

Emergence doesn't happen instantly. It requires multiple interaction rounds. Simple patterns compound into complex behaviors.

Think about how reefs form: one polyp secretes calcium carbonate. Another settles nearby. Then another. Small actions, repeated over time, compound into massive structures.

In Praval systems, you often see this progression:
- **Round 1**: Initial responses, somewhat obvious
- **Round 2**: Responses to responses, getting more interesting
- **Round 3**: Synthesis of multiple perspectives
- **Round 4**: Novel insights that weren't in any initial response

Let the system run. Emergence takes time.

### Types of Emergence in Praval

#### **Behavioral Emergence**: Novel Interaction Patterns

Agents discover ways to collaborate that you didn't explicitly program.

Example: A document processing system where the extractor, analyzer, and formatter developed an implicit quality feedback loop. The formatter would request re-analysis when content was unclear. The analyzer would request re-extraction when data was malformed. Nobody programmed this loop—it emerged from agents responding to each other's output quality.

#### **Cognitive Emergence**: Insights Beyond Individual Capacity

The system as a whole thinks thoughts no individual agent can think.

Example: In a knowledge graph building system, individual agents extracted concepts, identified relationships, detected patterns. But the system as a whole discovered higher-order structures (concept hierarchies, thematic clusters, knowledge gaps) that weren't visible at any single level.

#### **Adaptive Emergence**: Self-Organizing Responses to Novel Situations

The system handles scenarios it was never explicitly programmed for.

Example: A customer service agent system where query routing, response generation, and escalation handling self-organized around patterns they discovered in actual queries, automatically creating specialized handling for question types the designers hadn't anticipated.

### The Difference Between Programmed and Emergent

Let's be precise about what we mean:

**Programmed Behavior**:
```python
def process_business_idea(idea):
    # Step 1: Research
    research = researcher.analyze(idea)

    # Step 2: Analyze
    analysis = analyst.process(research)

    # Step 3: Critique
    critique = critic.evaluate(analysis)

    # Return results
    return {
        "research": research,
        "analysis": analysis,
        "critique": critique
    }
```

This is **compositional**. You determine the sequence. The agents are functions you call in order.

**Emergent Behavior**:
```python
@agent("researcher", responds_to=["business_idea", "research_question"])
def researcher(spore):
    # Responds to ideas AND to questions from other agents
    pass

@agent("analyst", responds_to=["research_findings"])
def analyst(spore):
    # Responds to research, might raise new questions
    pass

@agent("critic", responds_to=["research_findings", "analysis"])
def critic(spore):
    # Can critique either research or analysis
    # Might trigger new research
    pass
```

This is **emergent**. You don't control the sequence. Agents respond to relevant messages. The interaction pattern emerges from their responses to each other.

The difference becomes profound at scale. Programmed systems grow in complexity geometrically—each new capability requires considering all existing capabilities. Emergent systems grow linearly—new agents just respond to relevant messages.

### Watching Emergence Happen

The most remarkable thing about emergent systems is that they surprise you.

I've built enough Praval systems now that I can predict what individual agents will do. But I'm routinely surprised by what the system as a whole discovers.

A few examples from real systems:

**The Knowledge Graph Builder** developed its own data validation layer. The concept extractor and relationship analyzer started challenging each other's outputs, creating an implicit peer review system. Made the final knowledge graph higher quality, but I never programmed peer review.

**The Research Assistant** developed specialization patterns I didn't design. When I added multiple agents that could all do "general research," they self-organized into specialists: one became better at academic papers, another at industry reports, another at news sources. They developed this through feedback from downstream agents about what sources were most useful for different queries.

**The Content Pipeline** discovered a caching strategy. The writing agent started referencing previous similar content, the research agent started noticing patterns in what got reused, and together they created a form of transfer learning where newer content built on refined versions of older patterns. Nobody programmed caching—it emerged.

These aren't programmed features. They're **discovered behaviors** that emerge from agents pursuing their identities and responding to their communication environment.

### Why Emergence Feels Different

Building with emergence is psychologically different from traditional programming.

**Traditional programming** feels like **control**: you specify exactly what happens, when, in what order. When it works, you feel competent. When it fails, you know where to look.

**Emergent systems** feel like **gardening**: you create conditions, plant seeds (agents), and watch what grows. You influence but don't control. When it works, you feel like you've discovered something. When it fails, you adjust conditions and try again.

The mindset shift is real. You move from:
- **"I will make this happen"** to **"I will create conditions where this can happen"**
- **"I control the behavior"** to **"I define identities and let behavior emerge"**
- **"Debugging is finding my mistake"** to **"Debugging is understanding what emerged and why"**

Some developers hate this. They want control. They want predictability. They want deterministic systems.

But here's what you get in exchange for accepting emergence:

**Robustness**: Emergent systems adapt to situations you didn't anticipate
**Scalability**: Adding capability means adding specialists, not refactoring the whole system
**Innovation**: The system discovers solutions you wouldn't have thought of
**Simplicity**: Each component remains understandable even as system behavior becomes sophisticated

That trade-off—giving up absolute control in exchange for emergent intelligence—that's the Praval bet.

### A Warning About Emergence

Emergence is powerful. It's also unpredictable.

You cannot guarantee what will emerge. You can create favorable conditions, but you can't force specific emergent behaviors. This means emergent systems require:

**Observation**: You must watch what actually happens, not assume you know
**Iteration**: First emergent patterns might not be what you want; you'll adjust
**Constraints**: Sometimes you need to limit what can emerge (we'll cover this in production patterns)
**Humility**: The system might discover something better than your design, or something worse—you need to be ready for both

This isn't a bug. It's fundamental to how emergence works. You're not building a machine that does exactly what you specify. You're creating an ecosystem where intelligence can grow.

Different paradigm. Different mindset. Different rewards.

**Chapter Insight**: Emergence is when simple components with clear identities, interacting through local rules with rich communication, create intelligence that surpasses any individual component. This isn't mystical—it's how complex systems work. Praval creates conditions where emergence can happen productively.

---

*End of Part I: Foundation*

You now understand why monoliths fail, how nature solves complexity through specialists, and what emergence means for AI systems. In Part II, we'll move from philosophy to practice—actually building multi-agent systems with Praval.

---

# PART II: Building

## Chapter 4: Building Multi-Agent Systems

It's Saturday morning. You've read about the philosophy—monoliths bad, specialists good, emergence real. Makes sense intellectually. But philosophy doesn't compile.

So let's build something. Not a tutorial. A real journey from "nothing installed" to "holy crap, three agents are actually collaborating."

This is what getting started with Praval actually looks like.

### Installation and Setup

First, the basics. You need Python 3.9+ and a virtual environment (because you're not a monster).

```bash
# Create project directory
mkdir my-agent-project
cd my-agent-project

# Virtual environment (always)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install Praval
pip install praval

# Or from source for bleeding edge
git clone https://github.com/aiexplorations/praval.git
cd praval
pip install -e .
```

**Why virtual environment?** Six months from now, you'll have multiple Praval projects. Each will have different dependencies. Future-you will thank present-you for the isolation.

### API Key Configuration

Praval talks to LLMs, which means API keys. The clean way:

```bash
# Create .env file in project root
cat > .env << 'EOF'
# At least one is required
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
COHERE_API_KEY=your_cohere_key_here

# Praval will auto-detect and use available providers
EOF

# IMPORTANT: Gitignore it immediately
echo ".env" >> .gitignore
```

Praval detects available keys automatically. Have OpenAI? It uses GPT-4. Have Anthropic? Claude works too. Have both? Your choice via configuration.

**Quick verification** - Does it work?

```python
# test_setup.py
from praval import agent, start_agents

@agent("test_agent")
def test(spore):
    print("✓ Praval is working!")
    return {"status": "success"}

if __name__ == "__main__":
    start_agents(test, initial_data={})
```

```bash
python test_setup.py
# Output: ✓ Praval is working!
```

If you see that, you're ready.

### Your First Agent

Let's create something useful. A philosopher agent that actually thinks:

```python
# philosopher.py
from praval import agent, chat, start_agents

@agent("philosopher")
def philosophical_agent(spore):
    """
    I am a philosopher who contemplates deep questions and provides
    thoughtful responses that explore different perspectives.
    """
    question = spore.knowledge.get("question", "What is the meaning of existence?")

    # The chat() function sends requests to your LLM
    response = chat(f"""
    You are a philosopher with deep knowledge of existentialism,
    stoicism, and pragmatism.

    Contemplate this question thoughtfully: "{question}"

    Provide insights from multiple philosophical perspectives, then
    synthesize them into a coherent reflection.
    """)

    print(f"🤔 Philosopher: {response}")
    return {"response": response}

if __name__ == "__main__":
    # Start the agent with a question
    result = start_agents(
        philosophical_agent,
        initial_data={"question": "What makes a good life?"}
    )
```

Run it:

```bash
python philosopher.py
```

**What just happened:**

1. **`@agent("philosopher")`** - Decorator transforms the function into an agent
2. **`spore.knowledge`** - Structured data passed to the agent
3. **`chat()`** - Sends prompt to your configured LLM (OpenAI/Anthropic/Cohere)
4. **`start_agents()`** - Executes agents with initial data
5. **`return`** - Agent's output (optional, useful for testing)

The agent has an **identity** ("I am a philosopher...") that drives its behavior. No step-by-step instructions. Just who it is and what it does.

### Agent Communication: The Spore System

One agent is nice. Multiple agents collaborating is where it gets interesting.

Agents communicate through **spores** - structured knowledge packets. Think of them as messages carrying semantic data, not just strings.

Here's two agents talking:

```python
# researcher_analyst.py
from praval import agent, chat, broadcast, start_agents

@agent("researcher", responds_to=["research_request"])
def researcher(spore):
    """
    I am a research specialist who finds and synthesizes information
    on specific topics with academic rigor.
    """
    topic = spore.knowledge.get("topic")

    # Research the topic (with LLM or your own logic)
    findings = chat(f"""
    Research this topic comprehensively: {topic}

    Find key facts, current trends, and important considerations.
    Present findings in a structured, clear format.
    """)

    print(f"🔬 Researcher found: {findings[:200]}...")

    # Broadcast findings to other agents
    broadcast({
        "type": "research_complete",
        "topic": topic,
        "findings": findings,
        "confidence": 0.85
    })

    return {"findings": findings}

@agent("analyst", responds_to=["research_complete"])
def analyst(spore):
    """
    I am a strategic analyst who identifies patterns, implications,
    and actionable insights from research data.
    """
    topic = spore.knowledge.get("topic")
    findings = spore.knowledge.get("findings")

    # Analyze the findings
    analysis = chat(f"""
    Based on this research about {topic}:

    {findings}

    As a strategic analyst, identify:
    - Key patterns and trends
    - Important implications
    - 3-4 actionable insights
    """)

    print(f"📊 Analyst insights: {analysis[:200]}...")

    return {"analysis": analysis}

if __name__ == "__main__":
    # Start both agents - they'll collaborate via spores
    start_agents(
        researcher,
        analyst,
        initial_data={
            "type": "research_request",
            "topic": "AI agents in healthcare"
        }
    )
```

**The Flow:**

1. Initial data has `type: "research_request"`
2. Researcher responds (matches `responds_to=["research_request"]`)
3. Researcher calls `broadcast()` with `type: "research_complete"`
4. Analyst responds (matches `responds_to=["research_complete"]`)
5. Analyst processes the findings from the spore

**No central coordinator.** No explicit wiring. Agents respond to message types they care about. That's it.

### Multi-Agent Orchestration

Let's build something real: a knowledge graph builder with three specialists.

```python
# knowledge_graph_builder.py
from praval import agent, chat, broadcast, start_agents

@agent("extractor", responds_to=["extract_concepts"])
def concept_extractor(spore):
    """
    I extract key concepts and entities from text with precision.
    """
    text = spore.knowledge.get("text")

    concepts = chat(f"""
    Extract key concepts and entities from this text:

    {text}

    List them as: concept_name (type)
    Example: "Machine Learning (Technology), Ethics (Principle)"
    """)

    print(f"📝 Extractor found: {concepts}")

    broadcast({
        "type": "concepts_extracted",
        "text": text,
        "concepts": concepts
    })

    return {"concepts": concepts}

@agent("linker", responds_to=["concepts_extracted"])
def relationship_linker(spore):
    """
    I identify relationships and connections between concepts.
    """
    concepts = spore.knowledge.get("concepts")

    relationships = chat(f"""
    Given these concepts: {concepts}

    Identify relationships between them.
    Format: Concept1 --[relationship]--> Concept2
    Example: "AI --[enables]--> Automation"
    """)

    print(f"🔗 Linker found: {relationships}")

    broadcast({
        "type": "relationships_found",
        "concepts": concepts,
        "relationships": relationships
    })

    return {"relationships": relationships}

@agent("grapher", responds_to=["relationships_found"])
def graph_builder(spore):
    """
    I build structured knowledge graphs from concepts and relationships.
    """
    concepts = spore.knowledge.get("concepts")
    relationships = spore.knowledge.get("relationships")

    graph = {
        "nodes": concepts.split(", "),
        "edges": relationships.split("\n"),
        "metadata": {
            "created": "now",
            "agents": ["extractor", "linker", "grapher"]
        }
    }

    print(f"📊 Knowledge Graph Built:")
    print(f"   Nodes: {len(graph['nodes'])}")
    print(f"   Edges: {len(graph['edges'])}")
    print(f"   Graph: {graph}")

    return {"graph": graph}

if __name__ == "__main__":
    sample_text = """
    Artificial intelligence is transforming healthcare through machine learning
    algorithms that can detect diseases earlier than traditional methods.
    Ethical considerations around patient privacy and algorithmic bias must be
    carefully addressed as these technologies scale.
    """

    start_agents(
        concept_extractor,
        relationship_linker,
        graph_builder,
        initial_data={
            "type": "extract_concepts",
            "text": sample_text
        }
    )
```

**What makes this work:**

- **Extractor** responds to `"extract_concepts"`, broadcasts `"concepts_extracted"`
- **Linker** responds to `"concepts_extracted"`, broadcasts `"relationships_found"`
- **Grapher** responds to `"relationships_found"`, builds final graph

It's a **pipeline**, but self-organizing. No explicit sequence defined. The message types create the flow.

### Parallel vs Sequential Processing

That was sequential (extractor → linker → grapher). What about parallel?

```python
@agent("summarizer", responds_to=["extract_concepts"])
@agent("categorizer", responds_to=["extract_concepts"])
@agent("validator", responds_to=["extract_concepts"])

# All three respond to the same message type
# They'll process in parallel, each doing their job
```

Or mixed patterns:

```python
# Step 1: Initial analysis (parallel)
@agent("researcher_a", responds_to=["analyze"])
@agent("researcher_b", responds_to=["analyze"])

# Step 2: Synthesis (sequential, after both finish)
@agent("synthesizer", responds_to=["research_complete"])

# Researchers broadcast "research_complete" when done
# Synthesizer waits for both, then processes
```

The system handles concurrency automatically. You define identities and message types. The flow emerges.

### Debugging and Monitoring

When things don't work (and they won't at first), you need visibility.

**Logging spore messages:**

```python
import logging

logging.basicConfig(level=logging.DEBUG)

# Now you'll see every spore:
# DEBUG:praval.reef:Spore sent: {"type": "research_request", ...}
# DEBUG:praval.reef:Agent 'researcher' activated
# DEBUG:praval.reef:Spore sent: {"type": "research_complete", ...}
```

**Tracking agent activation:**

```python
@agent("debuggable_agent")
def my_agent(spore):
    print(f"🔍 Activated with: {spore.knowledge}")
    print(f"🔍 Spore type: {spore.type}")
    print(f"🔍 From agent: {spore.from_agent}")
    # ... rest of logic
```

**Testing individual agents:**

```python
def test_researcher():
    """Test researcher in isolation"""
    result = researcher(
        Spore(
            type="research_request",
            knowledge={"topic": "test topic"},
            from_agent="test"
        )
    )
    assert result["findings"] is not None
    assert len(result["findings"]) > 0
```

**Common Pitfalls:**

1. **Wrong message type in `responds_to`**
   - Agent won't activate
   - Check: Does broadcast type match responds_to?

2. **Missing spore.knowledge keys**
   - KeyError or None values
   - Fix: Use `.get()` with defaults: `spore.knowledge.get("key", "default")`

3. **Agent not imported**
   - Won't be registered, won't activate
   - Fix: Import before `start_agents()`

4. **Circular message loops**
   - A broadcasts to B, B broadcasts to A, infinite loop
   - Fix: Add termination conditions or use `final_stage` flags

### A Complete Working Example

Let's put it all together - a problem solver with four specialists:

```python
# complete_example.py
from praval import agent, chat, broadcast, start_agents

@agent("analyzer", responds_to=["analyze_problem"])
def problem_analyzer(spore):
    """I break down complex problems into key aspects."""
    problem = spore.knowledge.get("problem")

    analysis = chat(f"Analyze this problem: {problem}. Identify 3-4 key aspects.")
    print(f"🔍 Analysis: {analysis[:150]}...")

    broadcast({
        "type": "analysis_complete",
        "problem": problem,
        "analysis": analysis
    })

@agent("creator", responds_to=["analysis_complete"])
def solution_creator(spore):
    """I generate creative solutions based on analysis."""
    analysis = spore.knowledge.get("analysis")

    solutions = chat(f"Based on: {analysis}\n\nGenerate 3 creative solutions.")
    print(f"💡 Solutions: {solutions[:150]}...")

    broadcast({
        "type": "solutions_generated",
        "solutions": solutions
    })

@agent("evaluator", responds_to=["solutions_generated"])
def solution_evaluator(spore):
    """I evaluate solutions for feasibility."""
    solutions = spore.knowledge.get("solutions")

    evaluation = chat(f"Evaluate these solutions: {solutions}\n\nRate feasibility.")
    print(f"⚖️ Evaluation: {evaluation[:150]}...")

    broadcast({
        "type": "evaluation_complete",
        "evaluation": evaluation,
        "final": True
    })

@agent("synthesizer", responds_to=["evaluation_complete"])
def final_synthesizer(spore):
    """I synthesize everything into actionable recommendations."""
    if not spore.knowledge.get("final"):
        return

    evaluation = spore.knowledge.get("evaluation")

    synthesis = chat(f"Create final recommendation based on: {evaluation}")
    print(f"🎯 Final: {synthesis}")

if __name__ == "__main__":
    start_agents(
        problem_analyzer,
        solution_creator,
        solution_evaluator,
        final_synthesizer,
        initial_data={
            "type": "analyze_problem",
            "problem": "How can we reduce food waste in cities?"
        }
    )
```

Run it. Watch four specialists collaborate to solve a problem none could handle alone.

That's emergence. That's Praval.

### What You've Built

Look what you have now:
- ✓ Working Praval installation
- ✓ Single agents with strong identities
- ✓ Multi-agent communication via spores
- ✓ Self-organizing collaboration patterns
- ✓ Debugging and monitoring capabilities
- ✓ A complete problem-solving system

And here's what's remarkable: you didn't write orchestration code. No workflow engine. No state machine. Just specialists who know when to respond.

### The Mental Model

Before moving forward, internalize this:

**Agents = Specialists with identities**
- Define what they ARE, not procedural steps
- Clear, focused expertise
- One thing, done well

**Spores = Knowledge packets**
- Structured data, not just strings
- Carry semantic meaning
- Type-based routing

**Communication = Self-organization**
- `responds_to` defines interest
- `broadcast()` shares knowledge
- Flow emerges from message types

**System = Emergent collaboration**
- No central control
- Local decisions, global intelligence
- The whole > sum of parts

This isn't just different syntax. It's different thinking.

### Next Steps

You can build multi-agent systems now. But they're stateless—agents forget everything between runs.

In Chapter 5, we'll add memory. Not just conversation history. Real, structured, persistent memory that makes agents intelligent over time.

That's when things get interesting.

**Chapter Insight**: Building multi-agent systems with Praval means defining specialist identities, structuring communication through spores, and letting collaboration patterns emerge. The framework handles orchestration, concurrency, and message routing—you focus on what agents are and what knowledge they share.

---

## Chapter 5: Memory & Persistence

It's 2:15 AM. You've built your first multi-agent system. Three specialists collaborating beautifully. Then you restart the script.

They forget everything.

Every conversation starts from zero. Every insight rediscovered. Every pattern relearned. Your agents are like the protagonist in *Memento*—capable but trapped in an eternal present.

This is the **stateless agent problem**, and it's killing your system's potential.

### Why Agents Need Memory

Think about human intelligence for a second. How much of your capability depends on memory?

You don't re-learn language every morning. Don't rediscover your expertise daily. Don't reset relationships with every conversation. **Memory isn't a feature of intelligence—it's foundational.**

An agent without memory is like a brilliant consultant with anterograde amnesia. Can analyze anything you put in front of them. Can't build on yesterday's insights. Can't remember what worked last time. Can't learn from experience.

**Without memory, agents are tools. With memory, they become collaborators.**

### What Memory Enables

When agents remember, capabilities emerge that are impossible with stateless execution:

**Continuity**: "Last time we discussed your API design, you preferred REST over GraphQL. Here's a new endpoint following that pattern." The agent builds on shared history.

**Personalization**: "You typically ask for Python examples first, then TypeScript. I've prepared both." The agent adapts to your patterns.

**Learning**: "The last three times you reported slow queries, the issue was missing database indexes. Should we check indexes first?" The agent recognizes patterns.

**Expertise**: "I've analyzed 147 customer conversations. There's a common complaint about onboarding. Want to discuss?" The agent accumulates domain knowledge.

**Relationships**: "You seem frustrated—the past two sessions ended abruptly. Want to approach this differently?" The agent develops context about interaction quality.

None of this works without memory. And not just any memory—**structured** memory that supports different cognitive functions.

### The Multi-Layered Approach

Human memory isn't monolithic. Cognitive science identifies different memory systems:

**Working Memory** (prefrontal cortex): What you're thinking about *right now*. Limited capacity (~7 items). Volatile—disappears when you switch context.

**Episodic Memory** (hippocampus): Personal experiences. "That conversation yesterday." Timeline-based. Contextual details.

**Semantic Memory** (temporal lobes): Facts and concepts. "Python is a programming language." Not tied to specific experiences.

**Procedural Memory** (basal ganglia): Skills and know-how. "How to debug code." Automatic after practice.

These aren't redundant—they're complementary. Each serves distinct functions.

Praval mirrors this: **short-term, episodic, semantic, and procedural memory for agents.**

### Praval's Memory Architecture

Here's the system:

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

**Short-term Memory** (working memory):
- Fast, in-process Python structures
- ~1000 entries (configurable)
- 24-hour retention (configurable)
- Use: Current conversation, active tasks, temporary state

**Long-term Memory** (persistent vector storage):
- Qdrant vector database
- Millions of entries
- Persistent across restarts
- Use: Important memories, learned patterns, semantic search

**Episodic Memory** (conversation tracking):
- Combines short-term + long-term
- Timeline tracking, context windows
- Use: Dialogue continuity, experience-based improvement

**Semantic Memory** (knowledge accumulation):
- Long-term memory with semantic organization
- Domain expertise, knowledge validation
- Use: Facts storage, domain learning

### Basic Memory Operations

Let's get practical. First, setup:

```bash
# Install memory dependencies
pip install praval[memory]

# Start Qdrant (vector database)
docker run -p 6333:6333 qdrant/qdrant

# Or use Docker Compose (recommended)
docker-compose up -d qdrant
```

Now, the simplest possible memory-enabled agent:

```python
# simple_memory.py
from praval import agent, chat, start_agents
from praval.memory import MemoryManager

# Initialize memory system
memory = MemoryManager(
    qdrant_url="http://localhost:6333",
    collection_name="my_first_memories"
)

@agent("remembering_agent")
def agent_with_memory(spore):
    """I remember our conversations and build on them."""
    user_message = spore.knowledge.get("message")
    agent_id = "remembering_agent"

    # Search for relevant past conversations
    past_memories = memory.search_memories(
        query_text=user_message,
        agent_id=agent_id,
        limit=3
    )

    if past_memories:
        context = "\n".join([m.content for m in past_memories])
        print(f"💭 I remember: {len(past_memories)} relevant past interactions")
    else:
        context = "This is our first interaction"
        print(f"🆕 First time we've talked about this")

    # Generate response using memory
    response = chat(f"""
    Memory context: {context}

    User says: {user_message}

    Respond in a way that shows you remember our conversation history.
    """)

    # Store this interaction for future
    memory.store_memory(
        agent_id=agent_id,
        content=f"User said: {user_message}. I responded: {response}",
        memory_type=MemoryType.EPISODIC,
        importance=0.7
    )

    print(f"🤖 Agent: {response}")
    return {"response": response}

if __name__ == "__main__":
    # Try multiple interactions - watch memory build
    messages = [
        "I'm working on a Python API project",
        "It needs authentication",
        "What did we discuss about my project?"
    ]

    for msg in messages:
        print(f"\n👤 User: {msg}")
        start_agents(agent_with_memory, initial_data={"message": msg})
```

Run it. Watch the agent remember:

```bash
python simple_memory.py

👤 User: I'm working on a Python API project
🆕 First time we've talked about this
🤖 Agent: Great! Python has excellent frameworks like FastAPI and Flask...

👤 User: It needs authentication
💭 I remember: 1 relevant past interactions
🤖 Agent: For your Python API project, you'll want JWT tokens or OAuth2...

👤 User: What did we discuss about my project?
💭 I remember: 2 relevant past interactions
🤖 Agent: We've been discussing your Python API project. You mentioned you're building it and need authentication...
```

**It remembers.** Not through prompt hacking. Through actual persistent memory.

### The Memory API

Let's break down what's available:

**Storing Memories:**

```python
from praval.memory import MemoryManager, MemoryType

memory = MemoryManager()

# Simple storage
memory.store_memory(
    agent_id="my_agent",
    content="User prefers detailed technical explanations",
    memory_type=MemoryType.SEMANTIC,  # This is a fact about the user
    importance=0.9  # High importance = longer retention
)

# Conversation turn
memory.store_conversation_turn(
    agent_id="chatbot",
    user_message="How do I optimize database queries?",
    agent_response="Use indexes on frequently queried columns...",
    importance=0.8
)

# Domain knowledge
memory.store_knowledge(
    agent_id="expert_system",
    knowledge="Vector databases use HNSW for approximate nearest neighbor search",
    domain="databases",
    confidence=0.95
)
```

**Searching Memories:**

```python
from praval.memory import MemoryQuery
from datetime import datetime, timedelta

# Basic search
results = memory.search_memories(
    query_text="database optimization",
    agent_id="my_agent",
    limit=5
)

# Advanced search with filters
complex_query = MemoryQuery(
    query_text="machine learning algorithms",
    memory_types=[MemoryType.SEMANTIC, MemoryType.EPISODIC],
    agent_id="ml_expert",
    limit=10,
    similarity_threshold=0.8,  # How similar to query (0-1)
    temporal_filter={
        "after": datetime.now() - timedelta(days=7),
        "before": datetime.now()
    }
)

results = memory.search_memories(complex_query)

for memory_entry in results:
    print(f"Found: {memory_entry.content}")
    print(f"Relevance: {memory_entry.similarity_score}")
    print(f"Age: {memory_entry.created_at}")
```

**Conversation Context:**

```python
# Get recent conversation history
context = memory.get_conversation_context(
    agent_id="chatbot",
    turns=10  # Last 10 conversation turns
)

for turn in context:
    conv_data = turn.metadata.get("conversation_data", {})
    print(f"User: {conv_data.get('user_message')}")
    print(f"Agent: {conv_data.get('agent_response')}")
```

### Memory-Enabled Agents

Now let's build something real: a RAG chatbot that actually remembers.

```python
# rag_chatbot_with_memory.py
from praval import agent, chat, broadcast, start_agents
from praval.memory import MemoryManager, MemoryType

# Initialize memory
memory = MemoryManager(qdrant_url="http://localhost:6333")

@agent("document_processor", responds_to=["process_document"])
def process_documents(spore):
    """I process documents and store knowledge in memory."""
    document = spore.knowledge.get("document")
    agent_id = "document_processor"

    # Extract key information
    summary = chat(f"""
    Summarize the key information from this document:

    {document}

    Extract facts, concepts, and important details.
    """)

    # Store as semantic knowledge
    memory.store_knowledge(
        agent_id=agent_id,
        knowledge=summary,
        domain="processed_documents",
        confidence=0.9
    )

    print(f"📚 Processed and stored document knowledge")

    broadcast({
        "type": "document_ready",
        "summary": summary
    })

@agent("chatbot", memory=True, responds_to=["user_query"])
def rag_chatbot(spore):
    """I answer questions using document knowledge and conversation memory."""
    query = spore.knowledge.get("query")
    user_id = spore.knowledge.get("user_id", "default")
    agent_id = f"chatbot_{user_id}"

    print(f"💬 Chatbot: Processing query for user {user_id}")

    # 1. Search document knowledge
    doc_knowledge = memory.search_memories(
        query_text=query,
        memory_types=[MemoryType.SEMANTIC],
        limit=3
    )

    # 2. Get conversation context
    conversation = memory.get_conversation_context(
        agent_id=agent_id,
        turns=5
    )

    # 3. Build context
    knowledge_context = "\n".join([k.content for k in doc_knowledge])
    conv_context = f"{len(conversation)} previous messages with this user"

    # 4. Generate response
    response = chat(f"""
    Document knowledge:
    {knowledge_context}

    Conversation context: {conv_context}
    User query: {query}

    Answer the query using the document knowledge. Reference previous
    conversation naturally if relevant.
    """)

    # 5. Store this interaction
    memory.store_conversation_turn(
        agent_id=agent_id,
        user_message=query,
        agent_response=response,
        importance=0.7
    )

    print(f"🤖 Response: {response}")
    return {"response": response}

if __name__ == "__main__":
    # First, process a document
    sample_doc = """
    Vector databases store data as high-dimensional vectors (embeddings).
    They use algorithms like HNSW for efficient similarity search.
    Popular options include Qdrant, Pinecone, and Weaviate.
    Use cases: semantic search, recommendation systems, RAG applications.
    """

    start_agents(
        process_documents,
        initial_data={
            "type": "process_document",
            "document": sample_doc
        }
    )

    # Now have a conversation
    queries = [
        {"query": "What are vector databases?", "user_id": "alice"},
        {"query": "How do they work?", "user_id": "alice"},
        {"query": "What can I build with them?", "user_id": "alice"},
    ]

    for q in queries:
        print(f"\n👤 User: {q['query']}")
        start_agents(
            rag_chatbot,
            initial_data={"type": "user_query", **q}
        )
```

**What makes this powerful:**

1. **Document knowledge** stored semantically (vector embeddings)
2. **Conversation history** tracked per user
3. **Context-aware responses** that reference both
4. **Persistent across restarts** - memory survives

This is a real RAG chatbot in ~80 lines. With memory. With context. With learning.

### Advanced Memory Features

Ready for the advanced stuff?

**Memory Importance Scoring:**

```python
# High importance = longer retention, higher retrieval priority
memory.store_memory(
    agent_id="agent",
    content="Critical security vulnerability found",
    importance=0.95,  # Will be retained and prioritized
    store_long_term=True  # Force long-term storage
)

memory.store_memory(
    agent_id="agent",
    content="User prefers dark mode",
    importance=0.5,  # Lower priority, may be cleaned up
    store_long_term=False  # Short-term only
)
```

**Domain Organization:**

```python
# Organize knowledge by domain
ml_knowledge = memory.get_domain_knowledge(
    agent_id="expert",
    domain="machine_learning",
    limit=20
)

# Store with domain tags
memory.store_knowledge(
    agent_id="expert",
    knowledge="Transformers use self-attention mechanisms",
    domain="machine_learning",
    confidence=0.95
)
```

**Knowledge Validation:**

```python
# Validate new information against existing knowledge
validation = memory.semantic_memory.validate_knowledge(
    agent_id="fact_checker",
    statement="Python was created in 1991",
    threshold=0.8
)

if validation.is_consistent:
    print(f"Consistent with known facts (confidence: {validation.confidence})")
else:
    print(f"Conflicts with existing knowledge")
```

**Memory Analytics:**

```python
# Get agent expertise level in a domain
expertise = memory.semantic_memory.get_domain_expertise_level(
    agent_id="expert_agent",
    domain="databases"
)
print(f"Expertise level: {expertise.expertise_level}")
print(f"Knowledge count: {expertise.knowledge_count}")
print(f"Average confidence: {expertise.confidence_average}")

# Memory usage statistics
stats = memory.get_memory_stats()
print(f"Total memories: {stats.total_count}")
print(f"By type: {stats.by_type}")
print(f"By agent: {stats.by_agent}")
```

**Memory Cleanup:**

```python
# Clear old, low-importance memories
memory.short_term_memory._cleanup_old_memories()

# Clear specific agent
memory.clear_agent_memories("old_agent")

# Archive old conversations
memory.episodic_memory.archive_old_episodes(cutoff_days=90)
```

### The Memory Pattern for Agents

Here's the pattern that works:

```python
@agent("smart_agent", memory=True)
def memory_aware_agent(spore):
    """The standard memory-enabled agent pattern."""
    query = spore.knowledge.get("query")
    agent_id = "smart_agent"

    # STEP 1: Search relevant memories
    relevant_memories = agent.recall(query, limit=5)

    # STEP 2: Get conversation context
    conversation = agent.get_conversation_context(turns=10)

    # STEP 3: Build context from memory
    memory_context = build_context(relevant_memories, conversation)

    # STEP 4: Generate response using context
    response = chat(f"""
    Context from memory: {memory_context}
    User query: {query}

    Respond using the context.
    """)

    # STEP 5: Store this interaction
    agent.remember(
        f"Query: {query}, Response: {response}",
        importance=calculate_importance(query, response)
    )

    return {"response": response}
```

**Always**: Search → Recall Context → Generate → Remember

### Docker Deployment

Production memory setup:

```yaml
# docker-compose.yml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

  praval-app:
    build: .
    environment:
      - QDRANT_URL=http://qdrant:6333
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - PRAVAL_COLLECTION_NAME=production_memories
      - SHORT_TERM_MAX_ENTRIES=5000
      - SHORT_TERM_RETENTION_HOURS=48
    depends_on:
      - qdrant

volumes:
  qdrant_data:
```

```bash
# Start everything
docker-compose up -d

# Run your memory-enabled agents
docker-compose exec praval-app python your_agent.py

# Check Qdrant health
curl http://localhost:6333/health
```

### Configuration Tips

**Environment variables:**

```bash
# Memory system config
QDRANT_URL=http://localhost:6333
PRAVAL_COLLECTION_NAME=my_memories
SHORT_TERM_MAX_ENTRIES=1000
SHORT_TERM_RETENTION_HOURS=24

# One LLM provider required
OPENAI_API_KEY=your_key
```

**Programmatic config:**

```python
memory = MemoryManager(
    qdrant_url="http://production-qdrant:6333",
    collection_name="production_memories",
    short_term_max_entries=2000,
    short_term_retention_hours=48
)

# Configure vector parameters
memory.long_term_memory.vector_size = 1536  # OpenAI embeddings
memory.long_term_memory.distance_metric = "cosine"
```

### Troubleshooting

**"Can't connect to Qdrant":**

```bash
# Check Qdrant is running
curl http://localhost:6333/health

# Check Docker
docker-compose logs qdrant

# Restart if needed
docker-compose restart qdrant
```

**"Memory storage errors":**

```python
# Check memory system health
health = memory.health_check()
print(health)

# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

**"Performance issues":**
- Increase Qdrant memory allocation in Docker
- Lower similarity thresholds (0.7 instead of 0.9)
- Use importance scoring to prioritize
- Implement regular cleanup

### What You've Gained

Your agents now:
- ✓ Remember conversations across sessions
- ✓ Build expertise over time
- ✓ Personalize responses to users
- ✓ Learn from experience
- ✓ Scale to millions of memories
- ✓ Work with production-grade vector storage

This isn't chatbot memory. This is **cognitive memory architecture** - the foundation for agents that genuinely learn and grow.

### The Paradigm Shift

Before: Stateless agents, fresh start every time
After: Persistent agents, building knowledge over time

Before: "What's your question?" (no context)
After: "Based on our last conversation about X..." (full context)

Before: Each interaction independent
After: Each interaction builds on history

You've transformed your agents from sophisticated autocomplete into something that starts to look like... actual intelligence.

### Next Steps

Memory gives your agents persistence. But they're still limited to what's in their prompts.

In Chapter 6, we'll give them **tools**—the ability to interact with the outside world. Web search. Databases. APIs. File systems.

That's when your agents become truly capable.

**Chapter Insight**: Memory transforms agents from stateless functions into persistent, learning entities. Praval's multi-layered memory architecture (short-term, long-term, episodic, semantic) enables agents to remember, learn, personalize, and build expertise over time—the foundation of genuine intelligence.

---

# PART III: Production

## Chapter 6: Tools & Capabilities

Your agents can think. They can remember. But they're stuck in their heads—isolated from the world.

They can't search the web. Can't query databases. Can't read files, call APIs, or interact with external systems. They're brilliant minds in sensory deprivation tanks.

Time to give them tools.

### Why Agents Need Tools

Think about human intelligence. How much of your capability comes from using tools?

You don't memorize every fact—you Google it. You don't calculate complex math mentally—you use a calculator. You don't store all knowledge internally—you access databases, APIs, documentation.

**Tools amplify intelligence.** An agent with tools isn't just smarter—it's capable of things that are impossible through reasoning alone.

### The Tool System

Praval's tool system is dead simple: functions become tools through the `@tool` decorator.

```python
from praval import tool

@tool("web_search", owned_by="researcher", category="research")
def search_web(query: str, num_results: int = 5) -> dict:
    """
    Search the web for information.

    Args:
        query: Search query string
        num_results: Number of results to return

    Returns:
        Dictionary with search results
    """
    # Implementation (simplified - use real search API in production)
    results = {
        "query": query,
        "results": [
            {"title": f"Result {i}", "url": f"https://example.com/{i}"}
            for i in range(num_results)
        ]
    }
    return results
```

That's it. The function is now a tool. Agents can discover it. Use it. The `@tool` decorator handles:
- **Registration** in the global tool registry
- **Metadata** extraction (name, description, parameters)
- **Type validation** from function signature
- **Ownership** tracking (which agents can use it)
- **Categorization** for discovery

### Building Your First Tool

Let's build something useful: a calculator tool for a math agent.

```python
# math_tools.py
from praval import tool, agent, chat, start_agents
import math

# Define tools
@tool("add", owned_by="calculator", category="arithmetic")
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b

@tool("multiply", owned_by="calculator", category="arithmetic")
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b

@tool("power", owned_by="calculator", category="advanced")
def power(base: float, exponent: float) -> float:
    """Raise a number to a power."""
    return base ** exponent

@tool("square_root", owned_by="calculator", category="advanced")
def square_root(n: float) -> float:
    """Calculate square root."""
    if n < 0:
        raise ValueError("Cannot calculate square root of negative number")
    return math.sqrt(n)

# Tool-enabled agent
@agent("calculator")
def calculator_agent(spore):
    """
    I am a calculator agent with access to mathematical tools.
    I can perform arithmetic and advanced calculations.
    """
    problem = spore.knowledge.get("problem")

    # Get available tools
    from praval import get_tool_registry
    registry = get_tool_registry()
    my_tools = registry.get_tools_for_agent("calculator")

    print(f"🔢 Calculator: I have {len(my_tools)} tools available")

    # Use LLM to decide which tool to use
    tool_descriptions = "\n".join([
        f"- {t.metadata.tool_name}: {t.metadata.description}"
        for t in my_tools
    ])

    response = chat(f"""
    I have these tools available:
    {tool_descriptions}

    Problem: {problem}

    Determine which tool(s) to use and with what parameters.
    Respond with: TOOL_NAME(param1, param2, ...)
    """)

    # Parse and execute (simplified - production needs better parsing)
    if "add" in response.lower():
        result = add(10, 5)
        print(f"✓ Used 'add' tool: 10 + 5 = {result}")
    elif "square_root" in response.lower():
        result = square_root(16)
        print(f"✓ Used 'square_root' tool: √16 = {result}")

    return {"result": result, "tool_used": response}

if __name__ == "__main__":
    start_agents(
        calculator_agent,
        initial_data={"problem": "What is 10 + 5?"}
    )
```

**Tool Discovery Flow:**
1. Tools register automatically via `@tool` decorator
2. Agent queries registry for tools it owns
3. Agent uses LLM to select appropriate tool
4. Agent executes tool with parameters
5. Tool returns results to agent

### Tool-Enabled Agents

Real agents use tools more sophisticatedly. Here's a research agent with web search and file storage:

```python
# research_agent.py
from praval import agent, tool, chat, broadcast, start_agents
import requests
import json
from pathlib import Path

# Web search tool
@tool("search", owned_by="researcher", category="search")
def web_search(query: str, max_results: int = 5) -> list:
    """Search the web and return results."""
    # Real implementation would use Google/Bing API
    # This is a mock for demonstration
    return [
        {"title": f"Result for: {query}", "snippet": "Relevant information...", "url": "https://example.com"}
    ] * max_results

# File storage tool
@tool("save_research", owned_by="researcher", category="storage")
def save_to_file(filename: str, content: str) -> dict:
    """Save research findings to a file."""
    path = Path(f"research/{filename}")
    path.parent.mkdir(exist_ok=True)
    path.write_text(content)
    return {"status": "saved", "path": str(path), "size": len(content)}

# Database query tool
@tool("query_db", owned_by="researcher", category="database")
def query_database(query: str) -> list:
    """Query the research database."""
    # Mock database query
    return [{"id": 1, "title": "Research Paper", "citations": 42}]

# Research agent using tools
@agent("researcher", responds_to=["research_request"])
def research_agent(spore):
    """
    I am a research agent. I search the web, query databases,
    and save my findings for future reference.
    """
    topic = spore.knowledge.get("topic")

    print(f"🔬 Researcher: Investigating '{topic}'")

    # Step 1: Web search
    search_results = web_search(topic, max_results=3)
    print(f"✓ Found {len(search_results)} web results")

    # Step 2: Database query
    db_results = query_database(topic)
    print(f"✓ Found {len(db_results)} database entries")

    # Step 3: Synthesize findings
    findings = chat(f"""
    Research topic: {topic}

    Web results: {json.dumps(search_results, indent=2)}
    Database results: {json.dumps(db_results, indent=2)}

    Synthesize these findings into a comprehensive research summary.
    """)

    # Step 4: Save for future use
    save_result = save_to_file(f"{topic.replace(' ', '_')}.txt", findings)
    print(f"✓ Saved research to {save_result['path']}")

    # Step 5: Broadcast findings
    broadcast({
        "type": "research_complete",
        "topic": topic,
        "findings": findings,
        "sources": len(search_results) + len(db_results),
        "saved_to": save_result['path']
    })

    return {"findings": findings, "saved": True}

if __name__ == "__main__":
    start_agents(
        research_agent,
        initial_data={
            "type": "research_request",
            "topic": "AI agent architectures"
        }
    )
```

**Tool Chaining Pattern:**
1. Use search tool to find information
2. Use database tool to get structured data
3. Use LLM to synthesize
4. Use storage tool to save
5. Broadcast results

Each tool does one thing well. The agent orchestrates.

### Storage and Retrieval

Praval has a unified storage system for persisting data across multiple backends:

**Supported Storage Providers:**
- **PostgreSQL**: Structured data, relational queries
- **Redis**: Fast caching, temporary data
- **S3/MinIO**: Documents, large files
- **Qdrant**: Vector embeddings (already using for memory)
- **FileSystem**: Local file storage

Here's how to use it:

```python
# unified_storage_example.py
from praval import agent, storage_enabled, start_agents
import asyncio

@storage_enabled(["filesystem", "redis"])
@agent("data_agent", responds_to=["store_data"])
def data_storage_agent(spore, storage):
    """
    I store data across multiple storage backends.
    The storage parameter is injected by @storage_enabled decorator.
    """
    data_type = spore.knowledge.get("type")
    content = spore.knowledge.get("content")

    if data_type == "document":
        # Store document in filesystem
        result = asyncio.run(storage.store(
            "filesystem",
            f"docs/{content['filename']}",
            content['data']
        ))

        if result.success:
            print(f"✓ Stored document: {result.data_reference.to_uri()}")
            return {"stored": True, "location": result.data_reference.to_uri()}

    elif data_type == "cache":
        # Store in Redis for fast access
        result = asyncio.run(storage.store(
            "redis",
            content['key'],
            content['value']
        ))

        if result.success:
            print(f"✓ Cached data with key: {content['key']}")
            return {"cached": True}

    return {"error": "Unknown data type"}

@storage_enabled(["filesystem", "redis"])
@agent("data_retriever", responds_to=["get_data"])
def data_retrieval_agent(spore, storage):
    """I retrieve data from storage backends."""
    source = spore.knowledge.get("source")
    key = spore.knowledge.get("key")

    # Retrieve from appropriate backend
    result = asyncio.run(storage.get(source, key))

    if result.success:
        print(f"✓ Retrieved data from {source}")
        return {"data": result.data, "source": source}
    else:
        print(f"✗ Failed to retrieve: {result.error}")
        return {"error": result.error}

if __name__ == "__main__":
    # Store a document
    start_agents(
        data_storage_agent,
        initial_data={
            "type": "store_data",
            "type": "document",
            "content": {
                "filename": "report.txt",
                "data": "Research findings..."
            }
        }
    )

    # Retrieve it
    start_agents(
        data_retrieval_agent,
        initial_data={
            "type": "get_data",
            "source": "filesystem",
            "key": "docs/report.txt"
        }
    )
```

**Key Features:**
- **Automatic backend selection** based on data type
- **Data references** - URIs that other agents can resolve
- **Cross-storage queries** - search across multiple backends
- **Health checking** - verify storage availability

### Complete Example: Document Processing Pipeline

Let's build a real system - a document processing pipeline with multiple tools:

```python
# document_pipeline.py
from praval import agent, tool, storage_enabled, chat, broadcast, start_agents
import asyncio
from pathlib import Path

# Tools
@tool("extract_text", owned_by="processor", category="processing")
def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF file."""
    # Mock - real version would use pypdf or similar
    return f"Extracted text from {file_path}: This is document content..."

@tool("analyze_sentiment", owned_by="analyzer", category="analysis")
def analyze_sentiment(text: str) -> dict:
    """Analyze sentiment of text."""
    # Mock - real version would use transformers or API
    return {
        "sentiment": "positive",
        "confidence": 0.87,
        "key_phrases": ["innovative", "promising", "effective"]
    }

@tool("summarize", owned_by="summarizer", category="processing")
def create_summary(text: str, max_length: int = 200) -> str:
    """Create a summary of the text."""
    # Use LLM for real summarization
    return chat(f"Summarize this in {max_length} chars: {text}")

# Agents
@storage_enabled(["filesystem"])
@agent("processor", responds_to=["process_document"])
def document_processor(spore, storage):
    """Extract and process document text."""
    file_path = spore.knowledge.get("file_path")

    # Extract text
    text = extract_text_from_pdf(file_path)
    print(f"📄 Extracted {len(text)} characters")

    # Store extracted text
    result = asyncio.run(storage.store(
        "filesystem",
        f"processed/{Path(file_path).stem}.txt",
        text
    ))

    broadcast({
        "type": "text_extracted",
        "text": text,
        "text_reference": result.data_reference.to_uri() if result.success else None
    })

@agent("analyzer", responds_to=["text_extracted"])
def sentiment_analyzer(spore):
    """Analyze document sentiment."""
    text = spore.knowledge.get("text")

    # Analyze
    sentiment = analyze_sentiment(text)
    print(f"😊 Sentiment: {sentiment['sentiment']} ({sentiment['confidence']:.0%})")

    broadcast({
        "type": "sentiment_analyzed",
        "text": text,
        "sentiment": sentiment
    })

@storage_enabled(["filesystem"])
@agent("summarizer", responds_to=["sentiment_analyzed"])
def document_summarizer(spore, storage):
    """Create and store document summary."""
    text = spore.knowledge.get("text")
    sentiment = spore.knowledge.get("sentiment")

    # Create summary
    summary = create_summary(text, max_length=200)

    # Add sentiment context
    full_report = f"""
DOCUMENT SUMMARY
{summary}

SENTIMENT ANALYSIS
- Sentiment: {sentiment['sentiment']}
- Confidence: {sentiment['confidence']:.0%}
- Key Phrases: {', '.join(sentiment['key_phrases'])}
"""

    # Store final report
    result = asyncio.run(storage.store(
        "filesystem",
        "reports/final_summary.md",
        full_report
    ))

    print(f"✅ Pipeline complete! Report saved.")
    return {"summary": summary, "sentiment": sentiment}

if __name__ == "__main__":
    start_agents(
        document_processor,
        sentiment_analyzer,
        document_summarizer,
        initial_data={
            "type": "process_document",
            "file_path": "input/document.pdf"
        }
    )
```

**Pipeline Flow:**
1. **Processor** uses `extract_text` tool → extracts PDF text → stores in filesystem → broadcasts
2. **Analyzer** receives text → uses `analyze_sentiment` tool → broadcasts results
3. **Summarizer** receives text + sentiment → uses `summarize` tool → creates final report → stores in filesystem

Three agents. Six tools (including storage). One complete document processing system.

### Docker Setup for Storage

Production setup with all storage backends:

```yaml
# docker-compose.yml
version: '3.8'

services:
  # Vector database (already have from Chapter 5)
  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes:
      - qdrant_data:/qdrant/storage

  # PostgreSQL for structured data
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: praval
      POSTGRES_USER: praval
      POSTGRES_PASSWORD: praval_secure_password
    ports: ["5432:5432"]
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # Redis for caching
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes:
      - redis_data:/data

  # MinIO for S3-compatible storage
  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data

  # Your Praval app
  praval-app:
    build: .
    environment:
      # LLM
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      # Storage
      - QDRANT_URL=http://qdrant:6333
      - POSTGRES_HOST=postgres
      - POSTGRES_DB=praval
      - POSTGRES_USER=praval
      - POSTGRES_PASSWORD=praval_secure_password
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - S3_ENDPOINT_URL=http://minio:9000
      - S3_BUCKET_NAME=praval-data
      - AWS_ACCESS_KEY_ID=minioadmin
      - AWS_SECRET_ACCESS_KEY=minioadmin
    depends_on:
      - qdrant
      - postgres
      - redis
      - minio

volumes:
  qdrant_data:
  postgres_data:
  redis_data:
  minio_data:
```

```bash
# Start everything
docker-compose up -d

# Run your tool-enabled agents
docker-compose exec praval-app python document_pipeline.py

# Check services
curl http://localhost:6333/health  # Qdrant
curl http://localhost:6379/ping     # Redis
```

### Configuration

**Environment variables:**

```bash
# Storage backends
QDRANT_URL=http://localhost:6333
POSTGRES_HOST=localhost
POSTGRES_DB=praval
REDIS_HOST=localhost
S3_ENDPOINT_URL=http://localhost:9000
S3_BUCKET_NAME=praval-data
FILESYSTEM_BASE_PATH=./data

# LLM provider
OPENAI_API_KEY=your_key
```

**Programmatic configuration:**

```python
from praval.storage import get_storage_registry

# Register custom storage provider
registry = get_storage_registry()

# Check what's available
providers = registry.list_providers()
print(f"Available: {providers}")

# Health check all
health = asyncio.run(registry.health_check_all())
for provider, status in health.items():
    print(f"{provider}: {status['status']}")
```

### Tool Best Practices

**1. Single Responsibility**
Each tool should do one thing:
```python
# Good: Focused tool
@tool("search_web")
def search(query: str) -> list:
    return web_search_api(query)

# Bad: Swiss army knife
@tool("do_everything")
def multi_tool(action: str, **kwargs):
    if action == "search": ...
    elif action == "save": ...
    # Too many responsibilities
```

**2. Type Hints Always**
```python
@tool("calculate")
def calc(a: float, b: float, operation: str) -> float:
    # Types enable automatic validation
    ...
```

**3. Error Handling**
```python
@tool("divide")
def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
```

**4. Descriptive Documentation**
```python
@tool("fetch_data", description="Fetch data from external API")
def fetch(url: str, timeout: int = 30) -> dict:
    """
    Fetch data from a URL.

    Args:
        url: The URL to fetch from
        timeout: Request timeout in seconds

    Returns:
        Dictionary with response data

    Raises:
        RequestError: If fetch fails
    """
    ...
```

### Troubleshooting Tools

**"Tool not found":**
```python
from praval import get_tool_registry

registry = get_tool_registry()

# List all tools
all_tools = registry.list_all_tools()
print(f"Registered tools: {all_tools}")

# Check specific agent's tools
agent_tools = registry.get_tools_for_agent("my_agent")
print(f"Agent tools: {[t.metadata.tool_name for t in agent_tools]}")
```

**"Storage connection failed":**
```python
# Health check before using
health = asyncio.run(storage.health_check("postgres"))
if health["status"] != "healthy":
    print(f"PostgreSQL unavailable: {health.get('error')}")
    # Use fallback storage
```

**"Tool execution error":**
```python
@tool("safe_tool")
def safe_operation(data: str) -> dict:
    try:
        result = risky_operation(data)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### What You've Built

Your agents now:
- ✓ Use external tools to amplify capabilities
- ✓ Store and retrieve data across multiple backends
- ✓ Chain tools together for complex operations
- ✓ Access databases, APIs, filesystems, web search
- ✓ Build complete processing pipelines

This isn't just "AI that can think." This is **AI that can act.**

### Next Steps

Tools give agents capabilities. But in production, you need more: security, scalability, observability.

In Chapter 7, we'll cover enterprise features—the things you need when your agent system leaves the lab and enters the real world.

Secure communications. Distributed deployment. Monitoring and metrics. Production-ready infrastructure.

That's where hobby projects become production systems.

**Chapter Insight**: Tools transform agents from thinking systems into acting systems. Praval's tool system (@tool decorator, storage backends, unified data access) enables agents to interact with the external world—web APIs, databases, files, and services—creating complete, capable AI applications.

---

## Chapter 7: Enterprise Features

Your agent system works beautifully on your laptop. Three agents collaborating, memory persisting, tools functioning. You demo it to your CTO.

"Great. Now make it production-ready."

That's when you realize: **working code ≠ production code.**

Production means security, scalability, observability, resilience. It means distributed deployment, encryption, monitoring, graceful degradation. It means infrastructure.

Let's build that.

### The Production Reality

Here's what changes when you go to production:

**Security**: Your agents communicate over the network now. That traffic needs encryption. Those messages need authentication. Keys need rotation.

**Scale**: One laptop → multiple servers. Local message passing → distributed messaging. Synchronous → asynchronous. Process crashes must not cascade.

**Observability**: When something breaks at 3 AM, you need logs, metrics, traces. You need to understand what agents are doing and why.

**Reliability**: Individual agent failures can't bring down the system. Network issues must be handled gracefully. Data must persist through crashes.

This is where hobby projects die. But Praval was built for this.

### Secure Communications

When agents communicate across the network, every message is an attack surface.

**The Problem**:
```python
# Insecure (what you have now)
broadcast({
    "type": "user_data",
    "ssn": "123-45-6789",
    "credit_card": "4111111111111111"
})
# Broadcast in plain text over network → MASSIVE security problem
```

**The Solution: Secure Spores**

Praval implements end-to-end encryption using PyNaCl (NaCl/libsodium):

```python
# secure_agents.py
from praval.core.secure_reef import SecureReef
from praval.core.transport import TransportProtocol
import asyncio

# Create secure communication reef
async def setup_secure_agent():
    reef = SecureReef(
        protocol=TransportProtocol.AMQP,  # Or MQTT, STOMP
        transport_config={
            "host": "rabbitmq.company.com",
            "port": 5671,  # TLS port
            "username": "agent_user",
            "password": "secure_password",
            "vhost": "/production",
            "ssl": True  # Enforce TLS
        }
    )

    # Initialize with encryption
    await reef.initialize("secure_agent")

    # Send encrypted message
    await reef.send_secure_spore(
        to_agent="recipient_agent",
        knowledge={
            "sensitive_data": "This is encrypted",
            "classification": "confidential"
        },
        expires_in_seconds=300  # Message expires after 5 minutes
    )

# Run
asyncio.run(setup_secure_agent())
```

**What This Gives You**:

- **End-to-end encryption**: Messages encrypted from sender to recipient
- **Digital signatures**: Verify message authenticity (prevents tampering)
- **Forward secrecy**: Key rotation ensures old keys can't decrypt new messages
- **Message expiration**: Time-sensitive data auto-expires
- **Transport security**: TLS/SSL for network layer

**Key Management**:

```python
from praval.core.secure_spore import SporeKeyManager

# Each agent gets its own key manager
key_manager = SporeKeyManager("my_agent")

# Keys auto-generated on first run
public_keys = key_manager.get_public_keys()
print(f"Encryption key: {public_keys['encryption']}")
print(f"Signing key: {public_keys['signing']}")

# Rotate keys periodically (security best practice)
await reef.rotate_keys()

# Keys stored encrypted at rest
# ~/.praval/keys/my_agent_keys.enc
```

**Security Checklist**:
- ✓ TLS/SSL for transport layer
- ✓ NaCl/Curve25519 for end-to-end encryption
- ✓ Ed25519 digital signatures
- ✓ Automated key rotation
- ✓ Message expiration
- ✓ Access control per agent
- ✓ Encrypted key storage

### Multi-Protocol Support

Production environments are heterogeneous. Some agents run on servers (use AMQP). Others on IoT devices (use MQTT). Web clients use STOMP.

**All must communicate seamlessly.**

Praval supports this through protocol abstraction:

```python
# Agent using AMQP (server-side, high reliability)
amqp_agent = SecureReef(
    protocol=TransportProtocol.AMQP,
    transport_config={
        "host": "rabbitmq.prod.company.com",
        "port": 5671,
        "ssl": True
    }
)

# Agent using MQTT (IoT device, lightweight)
mqtt_agent = SecureReef(
    protocol=TransportProtocol.MQTT,
    transport_config={
        "host": "mosquitto.prod.company.com",
        "port": 8883,
        "qos": 2,  # Exactly-once delivery
        "ssl": True
    }
)

# Agent using STOMP (web browser, simple)
stomp_agent = SecureReef(
    protocol=TransportProtocol.STOMP,
    transport_config={
        "host": "activemq.prod.company.com",
        "port": 61614,
        "ssl": True
    }
)
```

**They all talk to each other.** Protocol translation happens automatically.

**When to Use Which**:

**AMQP (RabbitMQ)**:
- Enterprise messaging
- Complex routing (topic exchanges, headers)
- Guaranteed delivery
- Transaction support
- Use for: Backend services, critical workflows

**MQTT**:
- IoT and mobile devices
- Bandwidth-constrained networks
- Last Will Testament (detect disconnects)
- QoS levels (0, 1, 2)
- Use for: Sensors, mobile apps, edge devices

**STOMP**:
- Web applications
- Simple text protocol
- Easy to implement clients
- Cross-language support
- Use for: Browser agents, simple integrations

### Observability

You can't fix what you can't see. Production systems need comprehensive observability.

**Logging Strategy**:

```python
import logging
from praval.observability import PravalLogger

# Configure structured logging
logger = PravalLogger(
    name="production_agent",
    level=logging.INFO,
    structured=True,  # JSON logs for parsing
    include_context=True  # Add spore IDs, agent names, etc.
)

@agent("observable_agent")
def observable_agent(spore):
    # Automatic structured logging
    logger.info("agent_activated",
                agent_name="observable_agent",
                spore_id=spore.id,
                spore_type=spore.type,
                from_agent=spore.from_agent)

    try:
        result = process_knowledge(spore.knowledge)

        logger.info("processing_complete",
                    result_size=len(result),
                    processing_time_ms=42)

        return result

    except Exception as e:
        logger.error("processing_failed",
                     error=str(e),
                     spore_id=spore.id,
                     exc_info=True)
        raise
```

**Output** (JSON for log aggregation):
```json
{
  "timestamp": "2024-01-15T14:23:45.123Z",
  "level": "INFO",
  "message": "agent_activated",
  "agent_name": "observable_agent",
  "spore_id": "spore_abc123",
  "spore_type": "knowledge",
  "from_agent": "upstream_agent",
  "environment": "production",
  "version": "0.7.6"
}
```

**Metrics Collection**:

```python
from praval.observability import MetricsCollector

metrics = MetricsCollector()

@agent("measured_agent")
def measured_agent(spore):
    # Track agent invocations
    metrics.increment("agent.invocations",
                      tags={"agent": "measured_agent"})

    # Track processing time
    with metrics.timer("agent.processing_time"):
        result = process(spore.knowledge)

    # Track result size
    metrics.histogram("agent.result_size", len(result))

    # Track custom business metrics
    metrics.gauge("agent.memory_usage_mb", get_memory_usage())

    return result
```

**Distributed Tracing**:

```python
from praval.observability import TracingContext

@agent("traced_agent")
def traced_agent(spore):
    # Create trace context from spore
    with TracingContext(spore) as trace:
        # All operations within this context are traced

        trace.add_event("starting_research")
        research = do_research()

        trace.add_event("starting_analysis")
        analysis = analyze(research)

        trace.add_event("completed")

        return analysis
```

Traces flow through the entire agent graph. You can see:
- Which agent triggered which
- How long each step took
- Where errors occurred
- Message flow visualization

**Dashboard Integration**:

Export to standard observability platforms:

```bash
# Prometheus (metrics)
PRAVAL_METRICS_EXPORTER=prometheus
PRAVAL_METRICS_PORT=9090

# Jaeger (tracing)
PRAVAL_TRACING_EXPORTER=jaeger
JAEGER_AGENT_HOST=jaeger.company.com

# ELK Stack (logs)
PRAVAL_LOG_OUTPUT=elasticsearch
ELASTICSEARCH_URL=https://elk.company.com:9200
```

### Error Resilience

Production agents must be resilient. Individual failures can't cascade.

**Circuit Breakers**:

```python
from praval.resilience import CircuitBreaker

# Protect external service calls
weather_api = CircuitBreaker(
    name="weather_api",
    failure_threshold=5,      # Open after 5 failures
    timeout_seconds=60,       # Reset after 60 seconds
    half_open_max_calls=3    # Test with 3 calls when half-open
)

@agent("weather_agent")
def weather_agent(spore):
    location = spore.knowledge.get("location")

    try:
        # Call protected by circuit breaker
        with weather_api:
            data = fetch_weather(location)
            return {"weather": data}

    except CircuitBreakerOpen:
        # Circuit open - use fallback
        return {
            "weather": "unavailable",
            "reason": "external_service_down",
            "fallback": True
        }
```

**Retry Policies**:

```python
from praval.resilience import RetryPolicy, ExponentialBackoff

retry_policy = RetryPolicy(
    max_attempts=3,
    backoff=ExponentialBackoff(initial=1, max=10),
    retry_on=[ConnectionError, TimeoutError],
    dont_retry_on=[ValueError]  # Don't retry logic errors
)

@agent("resilient_agent")
def resilient_agent(spore):
    @retry_policy.decorate
    def fetch_data():
        return external_api.get(spore.knowledge["url"])

    try:
        data = fetch_data()
        return {"data": data}
    except MaxRetriesExceeded:
        return {"error": "max_retries_exceeded", "fallback": use_cache()}
```

**Graceful Degradation**:

```python
@agent("degradable_agent")
def degradable_agent(spore):
    """Agent with multiple fallback levels."""

    # Try primary data source
    try:
        return get_from_database(spore.knowledge)
    except DatabaseError:
        logger.warning("database_unavailable", fallback="cache")

        # Try cache
        try:
            return get_from_cache(spore.knowledge)
        except CacheError:
            logger.warning("cache_unavailable", fallback="default")

            # Return safe default
            return get_default_response(spore.knowledge)
```

**Health Checks**:

```python
from praval.health import HealthCheck

health = HealthCheck()

# Register health check components
health.register("database", check_database_connection)
health.register("cache", check_cache_connection)
health.register("message_queue", check_mq_connection)

# Expose health endpoint (for load balancers)
@app.route("/health")
def health_endpoint():
    status = health.check_all()
    return {
        "status": "healthy" if all(status.values()) else "unhealthy",
        "components": status
    }, 200 if all(status.values()) else 503
```

### Docker Deployment

Production deployment with full observability and security:

```yaml
# docker-compose.production.yml
version: '3.8'

services:
  # Message Queue (AMQP)
  rabbitmq:
    image: rabbitmq:3-management-alpine
    ports:
      - "5672:5672"   # AMQP
      - "5671:5671"   # AMQP+TLS
      - "15672:15672" # Management UI
    environment:
      RABBITMQ_DEFAULT_USER: praval
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
      RABBITMQ_DEFAULT_VHOST: /production
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
      - ./rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf
      - ./ssl:/etc/rabbitmq/ssl  # TLS certificates
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Vector Database
  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT__SERVICE__API_KEY: ${QDRANT_API_KEY}

  # Structured Database
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: praval_production
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready"]
      interval: 10s

  # Cache
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    ports: ["6379:6379"]
    volumes:
      - redis_data:/data

  # Observability: Prometheus
  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus

  # Observability: Jaeger (tracing)
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # UI
      - "6831:6831/udp"  # Agent
    environment:
      COLLECTOR_OTLP_ENABLED: true

  # Observability: Grafana
  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana-dashboards:/etc/grafana/provisioning/dashboards

  # Praval Agents (scaled)
  praval-agent:
    build: .
    deploy:
      replicas: 3  # Run 3 instances
      restart_policy:
        condition: on-failure
        max_attempts: 3
    environment:
      # LLM
      - OPENAI_API_KEY=${OPENAI_API_KEY}

      # Transport
      - PRAVAL_TRANSPORT=amqp
      - PRAVAL_AMQP_URL=amqps://praval:${RABBITMQ_PASSWORD}@rabbitmq:5671/production

      # Storage
      - QDRANT_URL=http://qdrant:6333
      - QDRANT_API_KEY=${QDRANT_API_KEY}
      - POSTGRES_URL=postgresql://postgres:${POSTGRES_PASSWORD}@postgres/praval_production
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379

      # Observability
      - PRAVAL_METRICS_EXPORTER=prometheus
      - PRAVAL_METRICS_PORT=9090
      - PRAVAL_TRACING_EXPORTER=jaeger
      - JAEGER_AGENT_HOST=jaeger

      # Security
      - PRAVAL_ENABLE_ENCRYPTION=true
      - PRAVAL_KEY_ROTATION_HOURS=24
    depends_on:
      rabbitmq:
        condition: service_healthy
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  rabbitmq_data:
  qdrant_data:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:

networks:
  default:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16
```

**Deploy to Production**:

```bash
# Set secrets
export RABBITMQ_PASSWORD=$(openssl rand -base64 32)
export POSTGRES_PASSWORD=$(openssl rand -base64 32)
export REDIS_PASSWORD=$(openssl rand -base64 32)
export QDRANT_API_KEY=$(openssl rand -base64 32)
export GRAFANA_PASSWORD=$(openssl rand -base64 32)

# Deploy
docker-compose -f docker-compose.production.yml up -d

# Scale agents
docker-compose -f docker-compose.production.yml up -d --scale praval-agent=5

# Check health
curl http://localhost:8000/health

# View logs
docker-compose logs -f praval-agent

# View metrics
open http://localhost:3000  # Grafana
open http://localhost:9090  # Prometheus
open http://localhost:16686 # Jaeger
```

### Configuration Management

Production configuration via environment + secrets:

```bash
# .env.production (never commit)
# LLM
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Transport Security
PRAVAL_AMQP_URL=amqps://user:pass@rabbitmq.prod:5671/vhost
PRAVAL_ENABLE_TLS=true
PRAVAL_TLS_CERT_PATH=/etc/praval/ssl/cert.pem
PRAVAL_TLS_KEY_PATH=/etc/praval/ssl/key.pem

# Agent Security
PRAVAL_ENABLE_ENCRYPTION=true
PRAVAL_KEY_ROTATION_HOURS=24
PRAVAL_MESSAGE_TTL_SECONDS=300

# Observability
PRAVAL_LOG_LEVEL=INFO
PRAVAL_METRICS_ENABLED=true
PRAVAL_TRACING_ENABLED=true
PRAVAL_TRACING_SAMPLE_RATE=0.1  # Sample 10% of traces

# Performance
PRAVAL_MAX_CONCURRENT_AGENTS=50
PRAVAL_MESSAGE_BATCH_SIZE=100
PRAVAL_CONNECTION_POOL_SIZE=20

# Resilience
PRAVAL_CIRCUIT_BREAKER_ENABLED=true
PRAVAL_RETRY_MAX_ATTEMPTS=3
PRAVAL_HEALTH_CHECK_INTERVAL=30
```

### Monitoring Dashboards

Create Grafana dashboards for your agents:

```yaml
# grafana-dashboards/praval-agents.json
{
  "dashboard": {
    "title": "Praval Agents - Production",
    "panels": [
      {
        "title": "Agent Invocations/sec",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(agent_invocations_total[5m])"
          }
        ]
      },
      {
        "title": "Average Processing Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, agent_processing_time_bucket)"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(agent_errors_total[5m])"
          }
        ]
      },
      {
        "title": "Active Agents",
        "type": "stat",
        "targets": [
          {
            "expr": "agent_active_count"
          }
        ]
      }
    ]
  }
}
```

### What You've Built

Your agent system is now:
- ✓ **Secure**: End-to-end encryption, TLS, key rotation
- ✓ **Distributed**: Multi-protocol messaging across infrastructure
- ✓ **Observable**: Logs, metrics, traces integrated
- ✓ **Resilient**: Circuit breakers, retries, graceful degradation
- ✓ **Scalable**: Horizontal scaling, load balancing
- ✓ **Production-Ready**: Health checks, monitoring, secrets management

This isn't a prototype anymore. **This is enterprise infrastructure.**

### Next Steps

You have a production-ready system. But production deployment is one thing—production excellence is another.

In Chapter 8, we'll cover best practices: design patterns that work, real-world case studies, performance optimization, testing strategies, and operational wisdom.

The difference between a system that works and a system that's a pleasure to operate.

**Chapter Insight**: Enterprise features—secure communications, multi-protocol support, observability, error resilience—transform development systems into production-ready infrastructure. Praval provides encryption, distributed messaging, metrics/logging/tracing, circuit breakers, and horizontal scaling out of the box.

---

## Chapter 8: Production & Best Practices

You've built the system. Deployed it. Secured it. Scaled it.

Now the question isn't "does it work?" but "does it work *well*?"

This is operational excellence. The patterns that separate systems you maintain from systems you're proud of. Let's talk about what actually works in production.

### Design Patterns That Work

After building dozens of multi-agent systems, certain patterns emerge. Not theoretical—battle-tested.

**The Specialist Pattern** (you know this one):
```python
# One thing, done well
@agent("translator", responds_to=["translate_request"])
def translator(spore):
    """I translate text. That's all I do."""
    text = spore.knowledge.get("text")
    target_lang = spore.knowledge.get("target_language")

    translated = chat(f"Translate to {target_lang}: {text}")

    broadcast({
        "type": "translation_complete",
        "translated_text": translated,
        "original_text": text,
        "language": target_lang
    })

    return {"translated": translated}
```

**When to use**: Always. This is the default pattern.

**The Orchestrator Pattern**:
```python
# Coordinates multiple specialists
@agent("workflow_orchestrator", responds_to=["start_workflow"])
def orchestrator(spore):
    """I coordinate complex workflows across multiple specialists."""
    workflow_id = spore.knowledge.get("workflow_id")

    # Step 1: Data extraction
    broadcast({"type": "extract_data", "workflow_id": workflow_id})

    # Wait for extraction (in production, use async/await)

    # Step 2: Analysis
    broadcast({"type": "analyze_data", "workflow_id": workflow_id})

    # Step 3: Reporting
    broadcast({"type": "generate_report", "workflow_id": workflow_id})

    return {"status": "workflow_started", "id": workflow_id}
```

**When to use**: Complex multi-stage workflows, external system integration, state machines.

**The Pipeline Pattern**:
```python
# Sequential processing chain
@agent("stage_1", responds_to=["pipeline_start"])
def stage_1(spore):
    data = spore.knowledge.get("data")
    processed = process_stage_1(data)

    broadcast({"type": "stage_1_complete", "data": processed})

@agent("stage_2", responds_to=["stage_1_complete"])
def stage_2(spore):
    data = spore.knowledge.get("data")
    processed = process_stage_2(data)

    broadcast({"type": "stage_2_complete", "data": processed})

@agent("stage_3", responds_to=["stage_2_complete"])
def stage_3(spore):
    data = spore.knowledge.get("data")
    final = process_stage_3(data)

    broadcast({"type": "pipeline_complete", "result": final})
```

**When to use**: ETL processes, data transformation, document processing.

**The Federation Pattern**:
```python
# Multiple specialized systems collaborating
@agent("ml_federation", responds_to=["prediction_request"])
def ml_coordinator(spore):
    """Federate predictions across multiple ML models."""
    input_data = spore.knowledge.get("data")

    # Query multiple specialist models in parallel
    broadcast({"type": "get_prediction", "model": "model_a", "data": input_data})
    broadcast({"type": "get_prediction", "model": "model_b", "data": input_data})
    broadcast({"type": "get_prediction", "model": "model_c", "data": input_data})

    # Ensemble results (in real implementation, wait for responses)

@agent("model_a_specialist", responds_to=["get_prediction"])
def model_a(spore):
    if spore.knowledge.get("model") != "model_a":
        return

    prediction = run_model_a(spore.knowledge.get("data"))

    broadcast({
        "type": "prediction_result",
        "model": "model_a",
        "prediction": prediction
    })
```

**When to use**: Ensemble ML models, distributed decision-making, multi-region deployments.

### VentureLens Case Study

Remember the flagship example? Let's dissect why it works.

**The Problem**: Business idea analysis. Traditionally: 489 lines of monolithic code.

**The Solution**: 5 specialized agents in 50 lines.

```python
# VentureLens Architecture
@agent("interviewer", responds_to=["start_analysis"])
def interviewer(spore):
    """Dynamic question generation based on user responses."""
    # Generates contextual questions
    # Adapts based on previous answers
    # Knows when enough information is gathered

@agent("researcher", responds_to=["research_needed"])
def researcher(spore):
    """Market intelligence and competitive analysis."""
    # Web search for market data
    # Competitor identification
    # Industry trend analysis

@agent("analyst", responds_to=["analyze_idea"])
def analyst(spore):
    """Multi-dimensional business viability assessment."""
    # SWOT analysis
    # Financial projections
    # Risk assessment
    # Market opportunity sizing

@agent("reporter", responds_to=["generate_report"])
def reporter(spore):
    """Professional markdown report generation."""
    # Structured reporting
    # LaTeX-style formatting
    # Executive summary creation

@agent("presenter", responds_to=["create_pdf"])
def presenter(spore):
    """PDF generation and browser launching."""
    # Markdown → PDF conversion
    # Auto-open in browser
    # File management
```

**Why This Works**:

1. **Clear Separation**: Each agent has one job. Interviewer doesn't know about PDF generation. Reporter doesn't do analysis.

2. **Self-Organization**: No central controller. Agents respond to message types. Add a new specialist? Just broadcast the right message type.

3. **Easy Testing**: Test each agent in isolation. Mock spores. Verify responses. Unit tests are trivial.

4. **Iterative Improvement**: Want better interviews? Modify one agent. Better reports? Modify one agent. Changes are localized.

5. **Understandable**: Each agent is ~10 lines. Anyone can understand what it does.

**From 489 Lines to 50**:

```python
# Before: Monolithic approach
def analyze_business_idea(idea):
    # 489 lines of:
    # - Question generation
    # - Market research
    # - Competitive analysis
    # - SWOT analysis
    # - Financial projections
    # - Report generation
    # - PDF creation
    # - State management
    # - Error handling
    # All in one function

# After: Specialist approach
@agent("interviewer")
def interview(spore): ...  # 10 lines

@agent("researcher")
def research(spore): ...  # 10 lines

@agent("analyst")
def analyze(spore): ...  # 10 lines

@agent("reporter")
def report(spore): ...  # 10 lines

@agent("presenter")
def present(spore): ...  # 10 lines

# Total: 50 lines
# Each agent: Simple, testable, understandable
```

### Performance Optimization

Production systems must be fast. Here's what actually matters:

**Agent Concurrency**:
```python
# Let multiple agents process in parallel
start_agents(
    agent_1,
    agent_2,
    agent_3,
    initial_data={"type": "parallel_task"},
    max_concurrent=10  # Run up to 10 agents simultaneously
)
```

**Memory Caching**:
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def expensive_computation(input_data):
    # This result is cached
    return heavy_computation(input_data)

@agent("cached_agent")
def cached_agent(spore):
    result = expensive_computation(spore.knowledge.get("data"))
    return {"result": result}
```

**Connection Pooling**:
```python
# Don't create new connections per request
memory = MemoryManager(
    qdrant_url="http://localhost:6333",
    connection_pool_size=20  # Reuse connections
)

# Database connection pooling
postgres_provider = PostgreSQLProvider(
    pool_size=20,
    max_overflow=10
)
```

**Batch Processing**:
```python
@agent("batch_processor")
def batch_processor(spore):
    """Process multiple items in batches, not one-by-one."""
    items = spore.knowledge.get("items")

    # Bad: Process one at a time
    # for item in items:
    #     process(item)

    # Good: Batch process
    batch_size = 100
    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        process_batch(batch)  # Much faster
```

**Rate Limiting**:
```python
from praval.rate_limit import RateLimiter

# Prevent overwhelming external APIs
limiter = RateLimiter(requests_per_second=10)

@agent("api_caller")
def api_caller(spore):
    with limiter:
        result = external_api.call(spore.knowledge)
    return {"result": result}
```

**Cost Management**:
```python
# Use cheaper models for simple tasks
@agent("cheap_classifier")
def classifier(spore):
    """Use GPT-3.5 for classification, not GPT-4."""
    text = spore.knowledge.get("text")

    # Classification doesn't need GPT-4
    result = chat(
        f"Classify: {text}",
        model="gpt-3.5-turbo"  # 10x cheaper
    )

    return {"classification": result}

@agent("complex_analyzer")
def analyzer(spore):
    """Use GPT-4 for complex analysis."""
    data = spore.knowledge.get("data")

    # Complex analysis benefits from GPT-4
    result = chat(
        f"Deeply analyze: {data}",
        model="gpt-4-turbo"  # More capable
    )

    return {"analysis": result}
```

### Testing Strategies

Production systems must be tested. Here's how:

**Unit Testing Individual Agents**:
```python
# tests/test_translator.py
import pytest
from praval import Spore

def test_translator_basic():
    """Test translator with simple input."""
    spore = Spore(
        type="translate_request",
        knowledge={
            "text": "Hello, world!",
            "target_language": "Spanish"
        },
        from_agent="test"
    )

    result = translator(spore)

    assert "translated" in result
    assert len(result["translated"]) > 0

def test_translator_handles_empty_text():
    """Test translator handles edge cases."""
    spore = Spore(
        type="translate_request",
        knowledge={"text": "", "target_language": "French"},
        from_agent="test"
    )

    result = translator(spore)

    assert result["translated"] == ""
```

**Integration Testing Agent Conversations**:
```python
# tests/test_workflow.py
def test_data_pipeline():
    """Test complete data processing pipeline."""
    # Start pipeline
    start_agents(
        stage_1_agent,
        stage_2_agent,
        stage_3_agent,
        initial_data={"type": "pipeline_start", "data": test_data}
    )

    # Verify final output
    assert stage_3_agent.last_output["result"] == expected_result
```

**Mocking Spore Communications**:
```python
# tests/test_with_mocks.py
from unittest.mock import Mock, patch

def test_agent_with_mocked_broadcast():
    """Test agent in isolation by mocking broadcast."""
    with patch('praval.broadcast') as mock_broadcast:
        spore = create_test_spore()
        result = my_agent(spore)

        # Verify agent broadcasted correct message
        mock_broadcast.assert_called_once()
        call_args = mock_broadcast.call_args[0][0]

        assert call_args["type"] == "expected_message"
        assert "data" in call_args
```

**End-to-End Testing**:
```python
# tests/test_e2e.py
def test_full_venturelens_workflow():
    """Test complete VentureLens workflow from start to PDF."""
    # Start with business idea
    result = start_agents(
        interviewer,
        researcher,
        analyst,
        reporter,
        presenter,
        initial_data={
            "type": "start_analysis",
            "idea": "AI-powered task manager"
        }
    )

    # Verify PDF was created
    assert Path("output/analysis.pdf").exists()

    # Verify PDF contains expected sections
    pdf_text = extract_pdf_text("output/analysis.pdf")
    assert "SWOT Analysis" in pdf_text
    assert "Market Opportunity" in pdf_text
```

**Test Coverage Goals**:
- ✓ Individual agents: 90%+ coverage
- ✓ Integration tests: All critical workflows
- ✓ E2E tests: Main user journeys
- ✓ Performance tests: Measure agent latency
- ✓ Load tests: Verify system handles scale

### Going to Production

Final checklist before deploying:

**Pre-Deployment**:
- [ ] All tests passing
- [ ] Security audit completed
- [ ] Secrets managed via environment variables
- [ ] Monitoring dashboards created
- [ ] Error alerting configured
- [ ] Backup strategy implemented
- [ ] Rollback procedure documented
- [ ] Load testing completed

**Deployment**:
```bash
# 1. Set production environment
export ENV=production

# 2. Run security checks
./scripts/security-audit.sh

# 3. Run test suite
pytest tests/ --cov=src --cov-report=html

# 4. Build containers
docker-compose -f docker-compose.production.yml build

# 5. Deploy with zero-downtime
docker-compose -f docker-compose.production.yml up -d

# 6. Verify health
curl https://api.production.com/health

# 7. Monitor metrics
# Check Grafana dashboards
# Watch for errors in logs

# 8. Gradual rollout
# Start with 10% traffic
# Monitor error rates
# Gradually increase to 100%
```

**Post-Deployment**:
- [ ] Monitor error rates (should not increase)
- [ ] Check performance metrics (latency, throughput)
- [ ] Verify logs are flowing to aggregator
- [ ] Test critical user workflows
- [ ] Update documentation
- [ ] Notify team of deployment

### Operational Best Practices

**Daily Operations**:
```bash
# Morning routine
curl https://api.prod.com/health  # Check health
docker-compose logs --since 24h | grep ERROR  # Check for errors
open http://grafana.prod.com  # Review dashboards

# Weekly routine
# Review performance trends
# Check error patterns
# Update dependencies
# Rotate secrets

# Monthly routine
# Security audit
# Load testing
# Capacity planning
# Cost optimization review
```

**Troubleshooting Guide**:

**"Agent not responding"**:
1. Check agent is registered: `registry.list_agents()`
2. Verify responds_to matches broadcast type
3. Check agent isn't throwing exceptions
4. Enable debug logging: `PRAVAL_LOG_LEVEL=DEBUG`

**"High latency"**:
1. Check database connection pool exhaustion
2. Verify no N+1 queries in agent logic
3. Review LLM API response times
4. Check for synchronous operations that should be async

**"Messages not being delivered"**:
1. Verify message queue is running
2. Check network connectivity
3. Verify TLS certificates valid
4. Check for message expiration (TTL)

**"Memory usage growing"**:
1. Enable memory profiling
2. Check for memory leaks in agent code
3. Verify short-term memory cleanup running
4. Review connection pooling settings

### What You've Accomplished

Look at where you started: monolithic AI agents, brittle and hard to maintain.

Look at where you are now:
- ✓ Multi-agent systems with clean separation
- ✓ Persistent memory across sessions
- ✓ External tools for real-world interaction
- ✓ Secure, distributed, observable infrastructure
- ✓ Production-tested patterns and practices

**You've transformed how you build AI systems.**

Not through complexity. Through simplicity. Through specialization. Through patterns that actually work.

### The Praval Philosophy

Before we close, remember the core principles:

1. **Simple Agents, Complex Systems**: Individual agents should be trivially simple. Complexity emerges from collaboration.

2. **Identity Over Instruction**: Define what agents ARE, not procedural steps. Identity drives behavior.

3. **Knowledge-First Communication**: Agents share knowledge, not commands. Semantic messaging enables self-organization.

4. **Emergence as Intelligence**: The whole is greater than the sum of parts. Design for emergent behavior.

5. **Production from Day One**: Memory, tools, security, observability—built in, not bolted on.

### Where to Go From Here

**Experiment**: Build something new. Try a pattern you haven't used. Break something and fix it.

**Contribute**: Praval is open source. Found a bug? File an issue. Built a great tool? Submit a PR. [github.com/aiexplorations/praval](https://github.com/aiexplorations/praval)

**Share**: What you've built is remarkable. Show others. Write about it. Teach someone.

**Keep Building**: Multi-agent systems are still early. The patterns we use today will evolve. Stay curious.

---

You started this book asking "how do I build better AI systems?"

The answer: **stop building monoliths. Build coral reefs.**

Simple specialists. Clear communication. Emergent intelligence.

That's Praval. That's the future of AI development.

Welcome to the reef.

**Chapter Insight**: Production excellence comes from battle-tested patterns (Specialist, Orchestrator, Pipeline, Federation), comprehensive testing (unit, integration, e2e), performance optimization (caching, pooling, batching), and operational discipline (monitoring, troubleshooting, continuous improvement). Real-world case studies like VentureLens prove these approaches work at scale.

---

*End of Core Content*

---

# Appendices

## Appendix A: Quick API Reference

### Core Decorators

**`@agent(name, responds_to=None, memory=False)`**
```python
from praval import agent

@agent("agent_name", responds_to=["message_type"], memory=True)
def my_agent(spore):
    """Agent identity and purpose."""
    # Agent logic here
    return {"result": "data"}
```

**`@tool(name, owned_by, category, description="")`**
```python
from praval import tool

@tool("tool_name", owned_by="agent_name", category="category")
def my_tool(param: str) -> dict:
    """Tool description."""
    return {"result": "processed"}
```

**`@storage_enabled(providers)`**
```python
from praval import storage_enabled

@storage_enabled(["filesystem", "redis"])
@agent("data_agent")
def data_agent(spore, storage):
    # storage injected automatically
    pass
```

### Communication Functions

**`chat(prompt, model=None, **kwargs)`**
```python
from praval import chat

response = chat("Your prompt here", model="gpt-4-turbo")
```

**`broadcast(knowledge)`**
```python
from praval import broadcast

broadcast({
    "type": "message_type",
    "data": "payload"
})
```

**`start_agents(*agents, initial_data=None, max_concurrent=10)`**
```python
from praval import start_agents

result = start_agents(
    agent1,
    agent2,
    agent3,
    initial_data={"type": "start", "data": "value"}
)
```

### Memory System API

**MemoryManager**
```python
from praval.memory import MemoryManager, MemoryType

memory = MemoryManager(qdrant_url="http://localhost:6333")

# Store memory
memory.store_memory(
    agent_id="my_agent",
    content="Memory content",
    memory_type=MemoryType.EPISODIC,
    importance=0.8
)

# Search memories
results = memory.search_memories(
    query_text="search query",
    agent_id="my_agent",
    limit=5
)

# Conversation context
context = memory.get_conversation_context(agent_id="my_agent", turns=10)
```

### Configuration

**Environment Variables**
```bash
# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
COHERE_API_KEY=...

# Memory & Storage
QDRANT_URL=http://localhost:6333
POSTGRES_HOST=localhost
REDIS_HOST=localhost

# Security
PRAVAL_ENABLE_ENCRYPTION=true
PRAVAL_KEY_ROTATION_HOURS=24

# Observability
PRAVAL_LOG_LEVEL=INFO
PRAVAL_METRICS_ENABLED=true
```

---

## Appendix B: Example Gallery

### 1. Single Agent
```python
from praval import agent, chat, start_agents

@agent("greeter")
def greeter(spore):
    """I greet users warmly."""
    name = spore.knowledge.get("name", "friend")
    greeting = chat(f"Create a warm greeting for {name}")
    return {"greeting": greeting}

start_agents(greeter, initial_data={"name": "Alice"})
```

### 2. Two-Agent Communication
```python
@agent("asker", responds_to=["start"])
def asker(spore):
    broadcast({"type": "question", "query": "What is AI?"})

@agent("answerer", responds_to=["question"])
def answerer(spore):
    query = spore.knowledge.get("query")
    answer = chat(f"Answer: {query}")
    return {"answer": answer}

start_agents(asker, answerer, initial_data={"type": "start"})
```

### 3. Memory-Enabled Chatbot
```python
from praval.memory import MemoryManager

memory = MemoryManager()

@agent("chatbot")
def chatbot(spore):
    message = spore.knowledge.get("message")

    # Search relevant memories
    memories = memory.search_memories(message, agent_id="chatbot", limit=3)
    context = "\n".join([m.content for m in memories])

    # Generate response
    response = chat(f"Context: {context}\nUser: {message}\nRespond:")

    # Store conversation
    memory.store_conversation_turn("chatbot", message, response)

    return {"response": response}
```

### 4. Tool-Using Agent
```python
@tool("calculate", owned_by="calculator", category="math")
def add(a: float, b: float) -> float:
    return a + b

@agent("calculator")
def calculator(spore):
    a = spore.knowledge.get("a")
    b = spore.knowledge.get("b")
    result = add(a, b)
    return {"result": result}
```

### 5. Production Deployment
```yaml
# docker-compose.yml
version: '3.8'
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]

  rabbitmq:
    image: rabbitmq:3-management-alpine
    ports: ["5672:5672", "15672:15672"]

  praval-app:
    build: .
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - QDRANT_URL=http://qdrant:6333
    depends_on: [qdrant, rabbitmq]
```

---

## Appendix C: Configuration Guide

### Development Setup
```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate

# 2. Install Praval
pip install praval

# 3. Set API keys
export OPENAI_API_KEY=your_key_here

# 4. Run example
python examples/pythonic_knowledge_graph.py
```

### Production Setup
```bash
# 1. Docker deployment
docker-compose -f docker-compose.production.yml up -d

# 2. Verify services
curl http://localhost:6333/health  # Qdrant
curl http://localhost:8000/health  # App

# 3. Monitor
open http://localhost:3000  # Grafana
```

### Provider Selection
```python
# Automatic (uses first available key)
from praval import chat
response = chat("Your prompt")

# Explicit provider
response = chat("Your prompt", model="gpt-4-turbo")  # OpenAI
response = chat("Your prompt", model="claude-3-opus")  # Anthropic
response = chat("Your prompt", model="command-r-plus")  # Cohere
```

### Memory Configuration
```python
from praval.memory import MemoryManager

memory = MemoryManager(
    qdrant_url="http://localhost:6333",
    collection_name="my_memories",
    short_term_max_entries=1000,
    short_term_retention_hours=24
)
```

---

## Appendix D: Troubleshooting

### Common Issues

**"ModuleNotFoundError: No module named 'praval'"**
```bash
# Activate virtual environment
source venv/bin/activate

# Install Praval
pip install praval
```

**"Connection refused to Qdrant"**
```bash
# Start Qdrant
docker run -p 6333:6333 qdrant/qdrant

# Or use Docker Compose
docker-compose up -d qdrant
```

**"Agent not responding to messages"**
```python
# Check responds_to matches broadcast type
@agent("my_agent", responds_to=["exact_match"])  # Must match exactly

broadcast({"type": "exact_match"})  # This works
```

**"OpenAI API error"**
```bash
# Verify API key is set
echo $OPENAI_API_KEY

# Set if missing
export OPENAI_API_KEY=sk-...
```

**"Memory not persisting"**
```python
# Ensure Qdrant is running
curl http://localhost:6333/health

# Use long-term storage
memory.store_memory(..., store_long_term=True)
```

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# See all Praval internal logging
logger = logging.getLogger('praval')
logger.setLevel(logging.DEBUG)
```

### Getting Help
- **Documentation**: https://praval.readthedocs.io
- **GitHub Issues**: https://github.com/aiexplorations/praval/issues
- **Examples**: https://github.com/aiexplorations/praval/tree/main/examples
- **Community**: GitHub Discussions

---

## PDF Generation

To generate a PDF from this book:

```bash
# Install pandoc
brew install pandoc  # macOS
sudo apt install pandoc texlive-xelatex  # Linux

# Generate PDF
pandoc praval-book.md \
  -o praval-book.pdf \
  --pdf-engine=xelatex \
  --toc \
  --toc-depth=2 \
  --number-sections \
  -V geometry:margin=1in \
  -V fontsize=11pt \
  -V documentclass=book \
  -V linkcolor=blue \
  -V urlcolor=blue

# Result: praval-book.pdf (~100 pages)
```

---

**End of Praval: Practical Multi-Agent AI Development**

*Version 1.0 | October 2025*

Build coral reefs, not monoliths. 🐚

