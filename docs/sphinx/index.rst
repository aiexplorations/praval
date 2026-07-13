====================================
Praval: Multi-Agent AI Framework
====================================

Praval is a Python framework for building decentralized agent systems that use
provider-neutral model execution, structured tool orchestration, memory,
storage, observability, and Reef/Spore communication.

The current documentation is organized around the APIs users should build on
now. The legacy string-returning APIs still work, but new code should prefer the
structured model runtime APIs where provider capabilities, streaming events,
structured outputs, multimodal input, and local LLM behavior are explicit.

The model runtime is the execution boundary inside agents. It does not replace
Praval's core architecture: specialized agents still coordinate through Reef
messages and Spore knowledge payloads, with complex workflows emerging from
typed local interactions rather than a central manager.

Install
===========

.. code-block:: bash

   pip install praval

   # Optional feature groups
   pip install praval[memory]
   pip install praval[storage]
   pip install praval[mcp]  # Python 3.10+
   pip install praval[all]

Quick Example
=============

.. code-block:: python

   from praval import Agent

   agent = Agent(
       "assistant",
       provider="openai",
       model="gpt-5.4-mini",
       config={"system_message": "Be concise."},
   )

   response = agent.generate(
       "Summarize why capability validation matters.",
       response_schema={
           "type": "object",
           "properties": {"summary": {"type": "string"}},
           "required": ["summary"],
       },
   )

   print(response.content)

What To Read
============

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   guide/getting-started
   guide/core-concepts
   guide/model-runtime
   guide/providers
   guide/local-llms
   guide/streaming
   guide/structured-outputs
   guide/multimodal
   guide/tool-system
   guide/mcp
   guide/demo-certification
   guide/hitl-troubleshooting
   guide/reef-protocol
   guide/memory-system
   guide/storage
   guide/runtime-migration
   guide/troubleshooting
   guide/documentation-quality

.. toctree::
   :maxdepth: 2
   :caption: Tutorials

   tutorials/first-agent
   tutorials/agent-communication
   tutorials/memory-enabled-agents
   tutorials/tool-integration
   tutorials/hitl-interventions
   tutorials/multi-agent-systems

.. toctree::
   :maxdepth: 2
   :caption: Architecture

   architecture/emergent-coordination
   architecture/runtime-adr

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
   :caption: Project

   changelog
   contributing
   license

Documentation Policy
====================

Sphinx source under ``docs/sphinx`` is the canonical documentation surface.
Generated HTML, generated API pages, and generated PDFs are build artifacts.
Older long-form manuals live under ``docs/archive`` and should be treated as
legacy background unless their content has been ported into the current Sphinx
guide.
