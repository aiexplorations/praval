.. _examples:

========
Examples
========

Working code examples demonstrating Praval's capabilities.

Examples that contact model providers are offline by default. Set
``PRAVAL_RUN_LIVE_EXAMPLES=1`` and the relevant provider credentials to execute
live requests. The full example smoke sweep removes ambient provider keys unless
that opt-in is present.

Overview
========

The Praval examples showcase progressively complex agent patterns, from simple single agents to sophisticated multi-agent systems.

.. contents:: Example Categories
   :local:
   :depth: 1

Model Runtime Examples
======================

Offline Runtime Contract
------------------------

**File**: ``examples/model_runtime_fake_provider.py``

This example needs no provider credentials. It demonstrates a fake provider
adapter, propagation of a structured-output request, and normalized streaming
events. It does not represent a provider constraint or local schema validation.

**Run it**:

.. code-block:: bash

   python examples/model_runtime_fake_provider.py

Local OpenAI-Compatible LLM
---------------------------

**File**: ``examples/local_llm_openai_compatible.py``

Connects to an already-running Ollama, vLLM, LM Studio, llama.cpp, or generic
OpenAI-compatible server.

**Run it**:

.. code-block:: bash

   PRAVAL_LOCAL_PROVIDER=ollama PRAVAL_LOCAL_MODEL=llama3 \
     python examples/local_llm_openai_compatible.py

Structured Output
-----------------

**File**: ``examples/structured_output_runtime.py``

Shows ``Agent.generate(..., response_schema=...)`` with a live provider. Use
``examples/model_runtime_fake_provider.py`` as the offline alternative.

Streaming Events
----------------

**File**: ``examples/streaming_events.py``

Shows normalized ``start``, ``delta``, ``usage``, and ``final`` event handling
for live provider streaming.

Multimodal Input
----------------

**File**: ``examples/multimodal_input_runtime.py``

Shows ``ContentPart`` lists for text plus image URL input. The runtime validates
that the selected provider/model profile supports image input before execution.

Gemini Multimodal File Input
----------------------------

**File**: ``examples/gemini_multimodal_file.py``

Shows how to pass a URI returned by the Gemini Files API as a
``ContentPart.file_url``. The example accepts PDF, audio, video, and other MIME
types supported by the selected Gemini model. Uploading local files is outside
the Praval 0.8.0 adapter.

**Run it**:

.. code-block:: bash

   python examples/gemini_multimodal_file.py \
     https://generativelanguage.googleapis.com/v1beta/files/FILE_ID \
     --mime-type application/pdf

Request-Based Voice Agent
-------------------------

**File**: ``examples/request_based_voice_agent.py``

Shows the 0.8 voice flow: transcribe a local audio file, send the transcript to
an agent, and synthesize the reply. It requires ``OPENAI_API_KEY`` and an audio
file path. Realtime voice sessions are not part of this example.

**Run it**:

.. code-block:: bash

   python examples/request_based_voice_agent.py question.wav --output reply.mp3

Gemini Client Tools
-------------------

**File**: ``examples/gemini_tool_runtime.py``

Shows a Gemini ``functionCall`` round trip executed by ``ModelRuntime``. It
requires ``GEMINI_API_KEY`` or ``GOOGLE_API_KEY``.

**Run it**:

.. code-block:: bash

   python examples/gemini_tool_runtime.py

Configurable Embeddings
-----------------------

**File**: ``examples/configurable_embeddings.py``

Shows chat model and memory embedding configuration as independent choices,
using local Chroma storage and ``text-embedding-3-small``.

**Run it**:

.. code-block:: bash

   python examples/configurable_embeddings.py

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

Make sure you wait for agents to complete:

.. code-block:: python

   from praval import get_reef

   # After start_agents(), wait for completion
   get_reef().wait_for_completion()
   get_reef().shutdown()

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
