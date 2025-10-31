.. _api-reference:

=============
API Reference
=============

Complete API documentation for the Praval framework, auto-generated from source code docstrings.

Overview
========

The Praval API is organized into logical modules:

.. contents:: API Modules
   :local:
   :depth: 1

Core API
--------

The fundamental building blocks of the Praval framework.

.. autosummary::
   :toctree: generated
   :recursive:

   praval.core.agent
   praval.core.reef
   praval.core.registry
   praval.core.exceptions

Decorators
----------

High-level decorator API for creating agents and tools.

.. autosummary::
   :toctree: generated

   praval.decorators
   praval.composition

Memory System
-------------

Multi-layered memory capabilities for persistent agents.

.. autosummary::
   :toctree: generated
   :recursive:

   praval.memory.memory_manager
   praval.memory.short_term_memory
   praval.memory.long_term_memory
   praval.memory.episodic_memory
   praval.memory.semantic_memory
   praval.memory.memory_types

Storage System
--------------

Unified data storage and retrieval across multiple providers.

.. autosummary::
   :toctree: generated
   :recursive:

   praval.storage.data_manager
   praval.storage.base_provider
   praval.storage.storage_registry
   praval.storage.decorators
   praval.storage.providers

Tool System
-----------

Tool integration and management for agent capabilities.

.. autosummary::
   :toctree: generated

   praval.tools
   praval.core.tool_registry

LLM Providers
-------------

Integration with multiple Large Language Model providers.

.. autosummary::
   :toctree: generated
   :recursive:

   praval.providers.factory
   praval.providers.openai
   praval.providers.anthropic
   praval.providers.cohere

Detailed Documentation
======================

Core Module
-----------

.. automodule:: praval.core.agent
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

.. automodule:: praval.core.reef
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

.. automodule:: praval.core.registry
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.core.exceptions
   :members:
   :undoc-members:
   :show-inheritance:

Decorators Module
-----------------

.. automodule:: praval.decorators
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.composition
   :members:
   :undoc-members:
   :show-inheritance:

Memory Module
-------------

.. automodule:: praval.memory.memory_manager
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

.. automodule:: praval.memory.short_term_memory
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.memory.long_term_memory
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.memory.episodic_memory
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.memory.semantic_memory
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.memory.memory_types
   :members:
   :undoc-members:
   :show-inheritance:

Storage Module
--------------

.. automodule:: praval.storage.data_manager
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.storage.base_provider
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.storage.storage_registry
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.storage.decorators
   :members:
   :undoc-members:
   :show-inheritance:

Storage Providers
^^^^^^^^^^^^^^^^^

.. automodule:: praval.storage.providers.filesystem
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.storage.providers.postgresql
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.storage.providers.redis_provider
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.storage.providers.s3_provider
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.storage.providers.qdrant_provider
   :members:
   :undoc-members:
   :show-inheritance:

Tool Module
-----------

.. automodule:: praval.tools
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.core.tool_registry
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Providers Module
----------------

.. automodule:: praval.providers.factory
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.providers.openai
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.providers.anthropic
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: praval.providers.cohere
   :members:
   :undoc-members:
   :show-inheritance:
