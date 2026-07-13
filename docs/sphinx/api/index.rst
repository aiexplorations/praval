.. _api-reference:

=============
API Reference
=============

The API reference is generated from source docstrings. Public model runtime
contracts live in ``praval.models`` and ``praval.model_runtime``; provider
registrations and profiles live in ``praval.providers.registry``.

.. contents:: API Modules
   :local:
   :depth: 1

Core API
========

.. autosummary::
   :toctree: generated
   :recursive:

   praval.core.agent
   praval.core.reef
   praval.core.registry
   praval.core.exceptions

Model Runtime
=============

.. autosummary::
   :toctree: generated
   :recursive:

   praval.models
   praval.model_runtime
   praval.providers.registry

Decorators And Composition
==========================

.. autosummary::
   :toctree: generated

   praval.decorators
   praval.composition

Providers
=========

.. autosummary::
   :toctree: generated
   :recursive:

   praval.providers.factory
   praval.providers.openai
   praval.providers.anthropic
   praval.providers.cohere
   praval.providers.gemini
   praval.providers.openai_compatible

Tool System
===========

.. autosummary::
   :toctree: generated

   praval.tools
   praval.core.tool_registry

Memory System
=============

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
==============

.. autosummary::
   :toctree: generated
   :recursive:

   praval.storage.data_manager
   praval.storage.base_provider
   praval.storage.storage_registry
   praval.storage.decorators
   praval.storage.providers
