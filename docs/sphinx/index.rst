.. Praval documentation master file

====================================
Praval: Multi-Agent AI Framework
====================================

.. image:: https://img.shields.io/pypi/v/praval.svg
   :target: https://pypi.org/project/praval/
   :alt: PyPI version

.. image:: https://img.shields.io/pypi/pyversions/praval.svg
   :target: https://pypi.org/project/praval/
   :alt: Python versions

.. image:: https://img.shields.io/github/license/aiexplorations/praval.svg
   :target: https://github.com/aiexplorations/praval/blob/main/LICENSE
   :alt: License

**The Pythonic Multi-Agent AI Framework for building intelligent, collaborative agent systems**

*Praval (प्रवाल) - Sanskrit for coral, representing how simple agents collaborate to create complex, intelligent ecosystems.*

----

Overview
========

Praval is a revolutionary Python framework that transforms complex AI applications into simple, composable agent systems.
Instead of monolithic AI systems, Praval enables you to create ecosystems of specialized agents that collaborate
intelligently through a coral reef-inspired architecture.

**Key Features:**

🎯 **Decorator-Based API**
   Transform functions into intelligent agents with simple ``@agent()`` decorators

🌊 **Reef Communication**
   Knowledge-first messaging between agents through structured "spores"

🧠 **Comprehensive Memory**
   Multi-layered memory system with vector search and persistent storage

🔧 **Multi-LLM Support**
   Seamless integration with OpenAI, Anthropic, and Cohere

🏗️ **Self-Organizing**
   Agents coordinate without central orchestration

🎨 **Production-Ready**
   Built with type safety, error handling, and scalability in mind

Quick Start
===========

Installation
------------

.. code-block:: bash

   # Minimal installation
   pip install praval

   # With memory system
   pip install praval[memory]

   # With all features
   pip install praval[all]

Your First Agent
-----------------

Create a simple agent in just a few lines:

.. code-block:: python

   from praval import agent, chat, broadcast, start_agents

   @agent("researcher", responds_to=["research_query"])
   def research_agent(spore):
       """I'm an expert at finding and analyzing information."""
       query = spore.knowledge.get("query")
       result = chat(f"Research this topic deeply: {query}")

       broadcast({
           "type": "research_complete",
           "findings": result,
           "confidence": 0.9
       })

       return {"research": result}

   # Start the agent system
   start_agents()

   # Send a research query
   broadcast({
       "type": "research_query",
       "query": "What are the latest developments in multi-agent AI?"
   })

That's it! You've created an intelligent research agent that:

✓ Listens for research queries
✓ Uses AI to generate insights
✓ Broadcasts results to other agents
✓ Returns structured data

Architecture Philosophy
=======================

Praval is inspired by coral reef ecosystems:

.. admonition:: The Coral Reef Metaphor
   :class: tip

   Just as coral polyps are simple organisms that create complex reef ecosystems through collaboration,
   Praval agents are specialized functions that create sophisticated AI systems through communication.

**Design Principles:**

1. **Specialization Over Generalization** - Each agent excels at one thing
2. **Declarative Design** - Define what agents ARE, not what they DO
3. **Emergent Intelligence** - Complex behaviors from simple interactions
4. **Zero Configuration** - Sensible defaults, progressive enhancement
5. **Composability** - Agents combine naturally through standard interfaces

What's Inside
=============

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   guide/getting-started
   guide/core-concepts
   guide/memory-system
   guide/reef-protocol
   guide/tool-system
   guide/storage

.. toctree::
   :maxdepth: 2
   :caption: Tutorials

   tutorials/first-agent
   tutorials/agent-communication
   tutorials/memory-enabled-agents
   tutorials/tool-integration
   tutorials/multi-agent-systems

.. toctree::
   :maxdepth: 2
   :caption: Examples

   examples/index

.. toctree::
   :maxdepth: 3
   :caption: API Reference

   api/index

.. toctree::
   :maxdepth: 1
   :caption: Additional Resources

   changelog
   contributing
   license

Key Capabilities
================

Decorator-Based Agent Creation
-------------------------------

Transform any Python function into an intelligent agent:

.. code-block:: python

   @agent("explorer", channel="knowledge", responds_to=["concept_request"])
   def explore_concepts(spore):
       '''Find related concepts and broadcast discoveries.'''
       concepts = chat("Related to: " + spore.knowledge.get("concept", ""))
       return {"type": "discovery", "discovered": concepts.split(",")}

Reef Communication System
--------------------------

Agents communicate through a structured messaging protocol:

.. code-block:: python

   # Broadcast a message to all listening agents
   broadcast({
       "type": "task_request",
       "task": "analyze_data",
       "priority": "high"
   })

   # Agents automatically filter messages they care about
   @agent("analyst", responds_to=["task_request"])
   def handle_tasks(spore):
       if spore.knowledge.get("task") == "analyze_data":
           # Process the task
           return {"status": "completed"}

Memory System
-------------

Multi-layered memory for persistent, intelligent agents:

.. code-block:: python

   @agent("researcher", memory=True, knowledge_base="./docs/")
   def expert_agent(spore):
       '''Expert with pre-loaded knowledge base.'''
       question = spore.knowledge.get("question")

       # Search long-term memory
       relevant_info = expert_agent.recall(question)

       # Store new knowledge
       expert_agent.remember(f"Answered: {question}")

       return {"answer": chat(f"Answer based on: {relevant_info}")}

Community & Support
===================

- **GitHub**: `github.com/aiexplorations/praval <https://github.com/aiexplorations/praval>`_
- **Issues**: `Report bugs or request features <https://github.com/aiexplorations/praval/issues>`_
- **PyPI**: `pypi.org/project/praval <https://pypi.org/project/praval/>`_

Version Information
===================

Current version: |version|

**Changelog:**

- **v0.7.9** - Latest release with enhanced storage and tool systems
- **v0.7.x** - Tool system, secure spores, unified storage
- **v0.6.x** - Memory system integration
- **v0.5.x** - Knowledge base and PDF support
- **v0.3.x** - Multi-LLM provider support

See the :doc:`changelog` for detailed version history.

License
=======

Praval is released under the MIT License. See :doc:`license` for details.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
