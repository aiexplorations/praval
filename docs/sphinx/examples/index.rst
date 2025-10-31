.. _examples:

========
Examples
========

Working code examples demonstrating Praval's capabilities.

Overview
========

The Praval examples showcase progressively complex agent patterns, from simple single agents to sophisticated multi-agent systems.

.. contents:: Example Categories
   :local:
   :depth: 1

Beginner Examples
=================

Simple Calculator
-----------------

A basic calculator agent demonstrating tool integration.

**File**: ``examples/calculator.py``

.. literalinclude:: ../../../examples/calculator.py
   :language: python
   :lines: 1-50

**What it demonstrates**:

- Single agent with tools
- Basic `@tool` decorator usage
- Simple request-response pattern

**Run it**:

.. code-block:: bash

   python examples/calculator.py

Core Pattern Examples
=====================

001 - Single Agent Identity
----------------------------

The simplest possible agent.

**File**: ``examples/001_single_agent_identity.py``

**Demonstrates**:

- `@agent` decorator
- Basic agent creation
- Identity and system messages

002 - Agent Communication
--------------------------

Agents communicating through broadcasts.

**File**: ``examples/002_agent_communication.py``

**Demonstrates**:

- `broadcast()` messaging
- `responds_to` filtering
- Multi-agent coordination

003 - Specialist Collaboration
-------------------------------

Multiple specialized agents working together.

**File**: ``examples/003_specialist_collaboration.py``

**Demonstrates**:

- Specialized agent roles
- Workflow emergence
- Knowledge sharing

004 - Registry Discovery
-------------------------

Dynamic agent discovery and coordination.

**File**: ``examples/004_registry_discovery.py``

**Demonstrates**:

- Agent registry usage
- Dynamic agent lookup
- Runtime coordination

005 - Memory-Enabled Agents
----------------------------

Agents with persistent memory.

**File**: ``examples/005_memory_enabled_agents.py``

**Demonstrates**:

- `memory=True` configuration
- `remember()` and `recall()` API
- Persistent agent memory

006 - Resilient Agents
----------------------

Error handling and resilience patterns.

**File**: ``examples/006_resilient_agents.py``

**Demonstrates**:

- Error handling
- Graceful degradation
- Fault tolerance

Advanced Examples
=================

007 - Adaptive Agent Systems
-----------------------------

Agents that adapt based on feedback.

**File**: ``examples/007_adaptive_agent_systems.py``

**Demonstrates**:

- Learning from results
- Dynamic behavior adjustment
- Feedback loops

008 - Self-Organizing Networks
-------------------------------

Agents that organize themselves into networks.

**File**: ``examples/008_self_organizing_networks.py``

**Demonstrates**:

- Emergent organization
- Network topology formation
- Distributed coordination

009 - Emergent Collective Intelligence
---------------------------------------

Complex intelligence from simple agents.

**File**: ``examples/009_emergent_collective_intelligence.py``

**Demonstrates**:

- Collective decision making
- Consensus algorithms
- Swarm intelligence patterns

010 - Unified Storage Demo
---------------------------

Multi-provider storage system.

**File**: ``examples/010_unified_storage_demo.py``

**Demonstrates**:

- Storage providers (FileSystem, PostgreSQL, Redis, S3, Qdrant)
- Data persistence patterns
- Multi-backend coordination

011 - Secure Spore Demo
------------------------

Enterprise secure messaging.

**File**: ``examples/011_secure_spore_demo.py``

**Demonstrates**:

- Encrypted communication
- Message authentication
- Secure transport protocols

Docker Examples
===============

Containerized Praval applications.

**Directory**: ``examples/docker-examples/``

See the `Docker Examples README <../../../examples/docker-examples/README.md>`_ for:

- Dockerized agent deployments
- Multi-container coordination
- Production deployment patterns

Running Examples
================

Prerequisites
-------------

.. code-block:: bash

   # Install Praval with all features
   pip install praval[all]

   # Set API key
   export OPENAI_API_KEY="sk-..."

Run an Example
--------------

.. code-block:: bash

   # Simple examples
   python examples/001_single_agent_identity.py

   # Advanced examples
   python examples/009_emergent_collective_intelligence.py

   # With Docker
   cd examples/docker-examples
   docker-compose up

Example Output
--------------

Most examples print their progress:

.. code-block:: text

   Starting agent system...
   Agent 'researcher' registered
   Agent 'analyst' registered
   Broadcasting task...
   Researcher: Processing topic 'AI trends'
   Analyst: Analyzing results from researcher
   Complete!

Troubleshooting
===============

Example Doesn't Run
-------------------

**Check dependencies**:

.. code-block:: bash

   pip install praval[all]

**Verify API key**:

.. code-block:: bash

   echo $OPENAI_API_KEY

**Check Python version**:

.. code-block:: bash

   python --version  # Should be 3.9+

No Output
---------

Some examples run asynchronously. Add a sleep at the end:

.. code-block:: python

   import time
   time.sleep(3)  # Give agents time to complete

Memory Examples Fail
--------------------

Install memory dependencies:

.. code-block:: bash

   pip install praval[memory]

Storage Examples Fail
---------------------

Some examples require external services:

.. code-block:: bash

   # Start with Docker
   docker-compose up -d postgres redis qdrant

   # Or install locally
   # PostgreSQL, Redis, etc.

Next Steps
==========

After exploring examples:

- **Modify examples** - Experiment with the code
- **Combine patterns** - Mix different example patterns
- **Build your own** - Create custom agent systems
- **Read guides** - Deep dive into specific features

Additional Resources
====================

- :doc:`../guide/getting-started` - Setup and basics
- :doc:`../guide/core-concepts` - Architecture understanding
- :doc:`../api/index` - API reference
- `GitHub Examples <https://github.com/aiexplorations/praval/tree/main/examples>`_ - Latest code
